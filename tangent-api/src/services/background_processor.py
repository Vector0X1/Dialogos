import os
import json
import time
import threading
import queue
import pandas as pd
import numpy as np
from src.utils import logger
from src.services.data_processing import detect_chat_type, process_chatgpt_messages, process_claude_messages
from src.services.embedding import get_embeddings
from src.services.clustering import perform_clustering
from src.services.topic_generation import generate_topic_for_cluster
from src.config import BASE_DATA_DIR, IN_MEMORY_MESSAGES

class BackgroundProcessor:
    def __init__(self):
        self.task_queue = queue.Queue()
        self.processing_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.processing_thread.start()

    def start_task(self, file_path: str = None):
        """
        Start a processing task for a file or in-memory messages.
        
        Args:
            file_path (str, optional): Path to uploaded JSON file. If None, processes IN_MEMORY_MESSAGES.
        
        Returns:
            str: Task ID.
        """
        task_id = f"{time.time()}"
        self.task_queue.put(Task(task_id, file_path))
        logger.info(f"Started task {task_id}")
        return task_id

    def process_queue(self):
        while True:
            task = self.task_queue.get()
            try:
                logger.info(f"Processing task {task.task_id}")
                if task.file_path:
                    # File-based processing
                    data = self.load_json(task.file_path)
                    chat_type = detect_chat_type(data)
                else:
                    # In-memory processing
                    chat_type = "chatgpt"  # Adjust for claude if needed
                    data = IN_MEMORY_MESSAGES.get(chat_type, [])

                if not data:
                    logger.warning(f"No data to process for task {task.task_id}")
                    continue

                # Convert to DataFrame
                df = process_chatgpt_messages(data) if chat_type == "chatgpt" else process_claude_messages(data)
                logger.info(f"Loaded {len(df)} messages for {chat_type}")

                # Generate embeddings
                messages = df["text"].tolist()
                embeddings = get_embeddings(messages)
                if not embeddings or len(embeddings) != len(messages):
                    logger.error(f"Failed to generate embeddings for task {task.task_id}")
                    continue

                # Dimensionality reduction
                from sklearn.manifold import TSNE
                embeddings_array = np.array(embeddings)
                embeddings_2d = TSNE(n_components=2, random_state=42).fit_transform(embeddings_array)

                # Clustering
                clusters = perform_clustering(embeddings, min_cluster_size=max(2, len(embeddings) // 10))

                # Generate topics for each cluster based on conversation content
                topics = {}
                for cluster_id in set(clusters):
                    if cluster_id == -1:  # Skip noise points
                        continue
                    # Get messages in this cluster
                    cluster_indices = [i for i, c in enumerate(clusters) if c == cluster_id]
                    cluster_messages = df.iloc[cluster_indices]["text"].tolist()
                    if cluster_messages:
                        # Sample up to 5 messages or concatenate for brevity
                        sample_messages = cluster_messages[:5]  # Adjust as needed
                        topic = generate_topic_for_cluster(sample_messages)
                        topics[cluster_id] = topic
                    else:
                        topics[cluster_id] = "Miscellaneous"

                # Save results
                output_dir = os.path.join(BASE_DATA_DIR, chat_type)
                os.makedirs(output_dir, exist_ok=True)
                
                with open(os.path.join(output_dir, "embeddings_2d.json"), "w") as f:
                    json.dump(embeddings_2d.tolist(), f)
                with open(os.path.join(output_dir, "clusters.json"), "w") as f:
                    json.dump(clusters.tolist(), f)
                with open(os.path.join(output_dir, "topics.json"), "w") as f:
                    json.dump(topics, f)
                with open(os.path.join(output_dir, "chat_titles.json"), "w") as f:
                    json.dump(df["chat_name"].unique().tolist(), f)
                with open(os.path.join(output_dir, "chats_with_reflections.json"), "w") as f:
                    json.dump([], f)  # Placeholder; add reflection logic if needed

                # Persist IN_MEMORY_MESSAGES
                with open(os.path.join(BASE_DATA_DIR, f"{chat_type}_messages.json"), "w") as f:
                    json.dump(IN_MEMORY_MESSAGES.get(chat_type, []), f)

                logger.info(f"Task {task.task_id} completed successfully")

            except Exception as e:
                logger.error(f"Task {task.task_id} failed: {str(e)}")

    def load_json(self, file_path: str):
        with open(file_path, "r") as f:
            return json.load(f)

class Task:
    def __init__(self, task_id: str, file_path: str = None):
        self.task_id = task_id
        self.file_path = file_path