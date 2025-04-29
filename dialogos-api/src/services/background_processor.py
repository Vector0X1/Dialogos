# src/services/background_processor.py

import os
import json
import time
import threading
import queue
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.manifold import TSNE

from src.utils import logger
from src.services.data_processing import process_chatgpt_messages
from src.services.embedding import get_embeddings
from src.services.clustering import perform_clustering
from src.services.topic_generation import generate_topic_for_cluster
from src.config import BASE_DATA_DIR, IN_MEMORY_MESSAGES

class Task:
    def __init__(self, task_id: str, file_path: str = None):
        self.task_id = task_id
        self.file_path = file_path

class BackgroundProcessor:
    def __init__(self):
        self.task_queue = queue.Queue()
        thread = threading.Thread(target=self._process_queue, daemon=True)
        thread.start()

    def start_task(self, file_path: str = None) -> str:
        """
        Enqueue a new processing task.
        If file_path is None, we'll process IN_MEMORY_MESSAGES['chatgpt'].
        """
        task_id = f"{time.time()}"
        self.task_queue.put(Task(task_id, file_path))
        logger.info(f"Enqueued background task {task_id}")
        return task_id

    def _process_queue(self):
        while True:
            task = self.task_queue.get()
            try:
                logger.info(f"[{task.task_id}] Starting processing")

                # 1) Load data
                if task.file_path:
                    with open(task.file_path, "r") as f:
                        raw = json.load(f)
                else:
                    raw = IN_MEMORY_MESSAGES.get("chatgpt", [])

                if not raw:
                    logger.warning(f"[{task.task_id}] No messages to process")
                    continue

                # 2) Turn into DataFrame
                df = process_chatgpt_messages(raw)
                logger.info(f"[{task.task_id}] {len(df)} messages loaded")

                # 3) Embed
                texts = df["text"].tolist()
                embs = get_embeddings(texts)
                if len(embs) != len(texts):
                    logger.error(f"[{task.task_id}] Embedding count mismatch")
                    continue

                # 4) Project to 2D
                embs_arr = np.array(embs)
                embs_2d = TSNE(n_components=2, random_state=42).fit_transform(embs_arr)

                # 5) Cluster
                clusters = perform_clustering(embs, min_cluster_size=max(2, len(embs)//10))

                # 6) Topics per cluster
                topics = {}
                for cid in set(clusters):
                    if cid == -1:  # noise
                        continue
                    idxs = [i for i, c in enumerate(clusters) if c == cid]
                    msgs = df.iloc[idxs]["text"].tolist()[:5]
                    topics[cid] = generate_topic_for_cluster(msgs) if msgs else "Miscellaneous"

                # 7) Write out everything
                out_dir = os.path.join(BASE_DATA_DIR, "chatgpt")
                os.makedirs(out_dir, exist_ok=True)

                with open(os.path.join(out_dir, "embeddings_2d.json"), "w") as f:
                    json.dump(embs_2d.tolist(), f)
                with open(os.path.join(out_dir, "clusters.json"), "w") as f:
                    json.dump(clusters.tolist(), f)
                with open(os.path.join(out_dir, "topics.json"), "w") as f:
                    json.dump(topics, f)
                with open(os.path.join(out_dir, "chat_titles.json"), "w") as f:
                    json.dump(df["chat_name"].unique().tolist(), f)
                with open(os.path.join(out_dir, "chats_with_reflections.json"), "w") as f:
                    json.dump([], f)  # placeholder

                # 8) Persist raw messages
                with open(os.path.join(BASE_DATA_DIR, "chatgpt_messages.json"), "w") as f:
                    json.dump(raw, f)

                logger.info(f"[{task.task_id}] Completed successfully")

            except Exception as e:
                logger.error(f"[{task.task_id}] Failed: {e}", exc_info=True)
