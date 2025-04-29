# src/services/data_processing.py

import json
import os
import traceback
from collections import defaultdict
from typing import List, Tuple

import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform
import umap

from src.config import CHATGPT_DATA_DIR
from src.services.embedding import get_embeddings
from src.services.clustering import perform_clustering, generate_cluster_metadata

def save_state(state_data: dict, month_year: str, data_dir: str):
    """Save a specific snapshot (month_year) to disk."""
    state_dir = os.path.join(data_dir, "states")
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, f"state_{month_year}.json"), "w") as f:
        json.dump({
            "month_year": month_year,
            "points": state_data["points"],
            "clusters": state_data["clusters"],
            "titles": state_data["titles"],
            "topics": state_data["topics"],
            "total_conversations": state_data["total_conversations"],
        }, f)


def save_latest_state(update: dict, data_dir: str):
    """Overwrite the 'latest' files in data_dir with the given update."""
    with open(os.path.join(data_dir, "embeddings_2d.json"), "w") as f:
        json.dump(update["points"], f)
    with open(os.path.join(data_dir, "clusters.json"), "w") as f:
        json.dump(update["clusters"], f)
    with open(os.path.join(data_dir, "topics.json"), "w") as f:
        json.dump(update["topics"], f)
    with open(os.path.join(data_dir, "chat_titles.json"), "w") as f:
        json.dump(update["titles"], f)


def process_chatgpt_messages(data: List[dict]) -> List[dict]:
    """
    Flatten your in-memory ChatGPT conversation nodes into a
    timestamped list of messages for downstream embedding & clustering.
    """
    messages = []

    for conv in data:
        title = conv.get("title", "Untitled Chat")
        conv_id = conv.get("id", "")

        mapping = conv.get("mapping", {})
        for node_id, node_data in mapping.items():
            msg = node_data.get("message")
            if not msg:
                continue

            # parse timestamp
            created = msg.get("create_time")
            try:
                if isinstance(created, (int, float)):
                    ts = pd.to_datetime(created, unit="s")
                else:
                    ts = pd.to_datetime(created)
                if pd.isna(ts):
                    continue
            except Exception:
                continue

            # extract text
            content = msg.get("content", "")
            if isinstance(content, dict) and "parts" in content:
                text = " ".join(str(p) for p in content["parts"])
            else:
                text = str(content)

            # role
            role = msg.get("author", {}).get("role")
            sender = "human" if role == "user" else "assistant"

            messages.append({
                "chat_name": title,
                "chat_id": conv_id,
                "message_id": msg.get("id", ""),
                "parent_message_id": node_data.get("parent"),
                "branch_id": "0",
                "sender": sender,
                "timestamp": ts,
                "text": text,
            })

    if not messages:
        return []

    df = pd.DataFrame(messages)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    return df.to_dict("records")


def identify_struggle_messages(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return only those messages containing common 'struggle' keywords.
    """
    keywords = [
        "struggling", "don't understand", "confusing", "stuck", "need help",
        "doesn't make sense", "can't figure", "issue", "error", "failing"
    ]
    pattern = "|".join(keywords)
    return df[df["text"].str.contains(pattern, case=False, na=False)]


def process_data_by_month(df: pd.DataFrame):
    """
    Yield a processed snapshot for each month in the DataFrame.
    """
    df = df.dropna(subset=["timestamp"])
    df["month_year"] = df["timestamp"].dt.strftime("%Y-%m")
    months = sorted(df["month_year"].unique())
    accumulated = pd.DataFrame()

    for month in months:
        mask = df["month_year"] <= month
        accumulated = df[mask].copy()
        grouped = accumulated.groupby(["chat_name", "branch_id"])["text"].agg(list)
        titles = [f"{cn} (Branch {bid})" for cn, bid in grouped.index]

        if len(titles) < 2:
            continue

        update = process_single_month(titles, month)
        if update:
            yield update


def process_single_month(chat_titles: List[str], month: str) -> dict:
    """
    Build embeddings, UMAP projection, clustering & topics
    for one month's worth of chat_titles.
    """
    try:
        embs = get_embeddings(chat_titles)
        arr = np.array(embs)
        reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, random_state=42)
        pts_2d = reducer.fit_transform(arr)

        dists = pdist(arr, metric="cosine")
        dm = squareform(dists)
        clusters = perform_clustering(dists, len(chat_titles))
        metadata = generate_cluster_metadata(clusters, chat_titles, dm)

        return {
            "month_year": month,
            "points": pts_2d.tolist(),
            "clusters": clusters.tolist(),
            "titles": chat_titles,
            "topics": metadata,
            "total_conversations": len(chat_titles),
        }
    except Exception as e:
        traceback.print_exc()
        return None


def analyze_branches(messages: List[dict]) -> dict:
    """
    Build a tree of each conversation and detect explicit edit-branches
    based on timing gaps between siblings.
    """
    chats = defaultdict(lambda: {
        "messages": [], "parent_children": defaultdict(list), "edit_branches": []
    })

    # collect
    for m in messages:
        ts = pd.to_datetime(m["timestamp"])
        msg = {**m, "timestamp_obj": ts}
        chats[m["chat_name"]]["messages"].append(msg)
        pid = m.get("parent_message_id")
        if pid:
            chats[m["chat_name"]]["parent_children"][pid].append(msg)

    # detect
    stats = {}
    for name, data in chats.items():
        for parent, children in data["parent_children"].items():
            if len(children) <= 1:
                continue
            children.sort(key=lambda x: x["timestamp_obj"])
            gaps = np.diff([c["timestamp_obj"].timestamp() for c in children])
            for i, gap in enumerate(gaps):
                if gap > 60:
                    branch = {
                        "parent_message": parent,
                        "original": children[i],
                        "edit": children[i+1],
                        "time_gap": gap,
                        "branch_messages": []
                    }
                    def collect(msg):
                        branch["branch_messages"].append(msg)
                        for c in data["parent_children"].get(msg["message_id"], []):
                            collect(c)
                    collect(children[i+1])
                    data["edit_branches"].append(branch)
        stats[name] = data

    return stats
