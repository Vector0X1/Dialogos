# src/routes/api.py
from datetime import datetime
import os
import re
import logging
from collections import defaultdict

import numpy as np
import pandas as pd
from flask import Blueprint, request, jsonify
from openai import OpenAI

from src.services.embedding import get_embeddings
from src.services.background_processor import BackgroundProcessor
from src.services.topic_generation import generate_topic_for_cluster
from src.utils import load_visualization_data
from src.config import (
    BASE_DATA_DIR,
    CHATGPT_DATA_DIR,
    IN_MEMORY_MESSAGES,
    models_data,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)
background_processor = BackgroundProcessor()

# In-memory store for saved chats
IN_MEMORY_CHATS = {}

# CORS middleware
@api_bp.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "*")
    allowed_origins = [
        "https://open-lac-six.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
    ]
    response.headers["Access-Control-Allow-Origin"] = origin if origin in allowed_origins else "null"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Max-Age"] = "86400"
    return response


@api_bp.route("/generate", methods=["POST"])
def generate_text():
    """Generate via OpenAI or DeepSeek and store in memory."""
    data = request.json or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400

    model = data.get("model", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    if model.startswith("deepseek"):
        api_key     = os.getenv("DEESEEK_API_KEY")
        base_url    = "https://api.deepseek.com"
        storage_key = "deepseek"
    else:
        api_key     = os.getenv("OPENAI_API_KEY")
        base_url    = None
        storage_key = "chatgpt"

    if not api_key:
        missing = "DEESEEK_API_KEY" if storage_key == "deepseek" else "OPENAI_API_KEY"
        return jsonify({"error": f"Missing {missing}"}), 500

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Dialogos's helpful assistant."},
                {"role": "user",   "content": prompt},
            ],
            temperature=data.get("temperature", 0.8),
        )
        response_text = resp.choices[0].message.content

        # Persist human + assistant messages
        chat_name = data.get("chat_name", "Default Chat")
        branch_id = data.get("branch_id", "0")
        ts        = datetime.now().isoformat()
        IN_MEMORY_MESSAGES.setdefault(storage_key, []).extend([
            {
                "chat_name": chat_name,
                "branch_id": branch_id,
                "message_id": f"msg_{ts}_human",
                "text": prompt,
                "timestamp": ts,
                "sender": "human",
            },
            {
                "chat_name": chat_name,
                "branch_id": branch_id,
                "message_id": f"msg_{ts}_assistant",
                "text": response_text,
                "timestamp": ts,
                "sender": "assistant",
            },
        ])

        # Kick off background analytics
        background_processor.start_task()
        return jsonify({"response": response_text})
    except Exception as e:
        logger.error("Error in /generate", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/process/status/<task_id>", methods=["GET"])
def check_task_status(task_id):
    """Poll background processing progress."""
    try:
        status = background_processor.get_task_status(task_id)
        if not status:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({
            "status":    status.status,
            "progress":  status.progress,
            "error":     status.error,
            "completed": status.completed,
        })
    except Exception as e:
        logger.error("Error in /process/status", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/get-reflections", methods=["POST"])
def get_reflections():
    """Generate or fetch reflections (placeholder)."""
    try:
        current_context = request.json.get("context", "")
        if not current_context:
            return jsonify({"reflections": []})
        # pretend embeddings → reflections
        _ = np.array(get_embeddings([current_context])[0]).flatten()
        return jsonify({"reflections": []})
    except Exception as e:
        logger.error("Error in /get-reflections", exc_info=True)
        return jsonify({"reflections": []})


@api_bp.route("/topics", methods=["GET"])
def get_topics():
    """List saved topics (placeholder)."""
    return jsonify({"topics": []})


@api_bp.route("/topics/generate", methods=["POST"])
def generate_topic():
    """Cluster‐based topic generation."""
    try:
        titles = request.json.get("titles", [])
        if not titles:
            return jsonify({"error": "No titles provided"}), 400
        topic = generate_topic_for_cluster(titles)
        return jsonify({"topic": topic})
    except Exception as e:
        logger.error("Error in /topics/generate", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/models/library", methods=["GET"])
def get_library_models():
    """Return the list of available models."""
    return jsonify({"models": models_data})


@api_bp.route("/models", methods=["GET"])
def get_models():
    """Return current model configuration."""
    return jsonify({
        "generation_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "embedding_model":  os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
    })


@api_bp.route("/tags", methods=["GET"])
def get_tags():
    """Return tag list (placeholder)."""
    return jsonify([])


@api_bp.route("/embeddings", methods=["POST"])
def embeddings():
    """Return embeddings for a list of texts."""
    try:
        texts = request.json.get("texts", [])
        embs  = get_embeddings(texts)
        return jsonify({"embeddings": embs})
    except Exception as e:
        logger.error("Error in /embeddings", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/visualization", methods=["GET"])
def get_visualization_data():
    """Serve t-SNE / clusters / topics for front‐end viz."""
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in ["chatgpt", "deepseek"]:
            return jsonify({"error": "Invalid chat type"}), 400

        # both chatgpt & deepseek share the same storage dir
        data_dir = CHATGPT_DATA_DIR
        viz = load_visualization_data(data_dir)

        # quick sanity check
        if not all(isinstance(viz.get(k), t) for k,t in [
            ("points", list),
            ("clusters", list),
            ("titles", list),
            ("topics", dict),
        ]):
            return jsonify({
                "error": "No visualization data available",
                "points": [], "clusters": [], "titles": [], "topics": {}, "chats_with_reflections": []
            }), 200

        return jsonify(viz)
    except Exception as e:
        logger.error("Error in /visualization", exc_info=True)
        return jsonify({
            "error": str(e),
            "points": [], "clusters": [], "titles": [], "topics": {}, "chats_with_reflections": []
        }), 500


@api_bp.route("/chats/save", methods=["POST"])
def save_chat():
    """Save a graph “chat” definition."""
    try:
        data    = request.json
        chat_id = data.get("chatId", str(datetime.now().timestamp()))
        IN_MEMORY_CHATS[chat_id] = {
            "id":           chat_id,
            "nodes":        data.get("nodes", []),
            "lastModified": datetime.now().isoformat(),
            "title":        data.get("title", "Untitled Chat"),
            "metadata":     data.get("metadata", {}),
        }
        return jsonify({"success": True, "chatId": chat_id})
    except Exception as e:
        logger.error("Error in /chats/save", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/chats/load/<chat_id>", methods=["GET"])
def load_chat(chat_id):
    """Load a previously saved graph chat."""
    if chat_id not in IN_MEMORY_CHATS:
        return jsonify({"success": False, "error": "Chat not found"}), 404
    return jsonify({"success": True, "data": IN_MEMORY_CHATS[chat_id]})


@api_bp.route("/chats/list", methods=["GET"])
def list_chats():
    """List all saved chats."""
    try:
        chats = [{
            "id":           d["id"],
            "title":        d["title"],
            "lastModified": d["lastModified"],
            "metadata":     d["metadata"],
        } for d in IN_MEMORY_CHATS.values()]
        # newest first
        chats.sort(key=lambda x: x["lastModified"], reverse=True)
        return jsonify({"success": True, "chats": chats})
    except Exception as e:
        logger.error("Error in /chats/list", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/chats/delete/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    """Delete a saved chat."""
    if chat_id not in IN_MEMORY_CHATS:
        return jsonify({"success": False, "error": "Chat not found"}), 404
    del IN_MEMORY_CHATS[chat_id]
    return jsonify({"success": True})


@api_bp.route("/messages/<path:chat_name>", methods=["GET"])
def get_chat_messages(chat_name):
    """Fetch messages for a specific chat & branch."""
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400

        all_msgs = IN_MEMORY_MESSAGES[chat_type]
        m = re.match(r"^(.*) \(Branch (\d+)\)$", chat_name)
        if m:
            base, branch = m.groups()
        else:
            base, branch = chat_name, "0"

        msgs = [m for m in all_msgs if m["chat_name"] == base and m.get("branch_id","0") == branch]
        if not msgs:
            return jsonify({"error": "No messages found"}), 404

        msgs.sort(key=lambda x: pd.to_datetime(x["timestamp"]))
        return jsonify({"messages": msgs})
    except Exception as e:
        logger.error("Error in /messages/<chat_name>", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/messages_all/<path:chat_name>", methods=["GET"])
def get_all_chat_messages(chat_name):
    """Fetch every branch’s messages for a chat."""
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400

        all_msgs = IN_MEMORY_MESSAGES[chat_type]
        m = re.match(r"^(.*) \(Branch \d+\)$", chat_name)
        base = m.group(1) if m else chat_name

        # group by branch_id
        branches = defaultdict(list)
        for msg in all_msgs:
            if msg["chat_name"] == base:
                branches[msg.get("branch_id","0")].append(msg)

        for b in branches.values():
            b.sort(key=lambda x: pd.to_datetime(x["timestamp"]))

        return jsonify({"branches": branches})
    except Exception as e:
        logger.error("Error in /messages_all/<chat_name>", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/messages/branched", methods=["GET"])
def get_branched_messages():
    """Return a nested structure of main + edit branches."""
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400

        msgs = IN_MEMORY_MESSAGES[chat_type]
        if not msgs:
            return jsonify({
                "branched_chats": {},
                "stats": {
                    "total_chats_analyzed": 0,
                    "total_branched_chats": 0,
                    "total_messages_processed": 0,
                    "branching_structure": {},
                    "edit_branches": {}
                }
            })

        # group by chat_name, then split into main/branches
        chats = defaultdict(list)
        for m in msgs:
            if all(k in m for k in ("chat_name","branch_id","message_id","text","timestamp")):
                chats[m["chat_name"]].append(m)

        branched_chats = {}
        stats = {
            "branching_structure": {},
            "edit_branches": {},
            "total_branched_chats": 0,
            "total_chats_analyzed": len(chats),
            "total_messages_processed": len(msgs)
        }

        for name, cm in chats.items():
            main = [m for m in cm if m["branch_id"]=="0"]
            edits = [m for m in cm if m["branch_id"]!="0"]
            branches = {}
            for m in edits:
                bid = m["branch_id"]
                if bid not in branches:
                    # find its parent_message in the main branch
                    parent = next((x for x in cm if x["message_id"]==m.get("parent_message")), None)
                    branches[bid] = {"parent_message": parent, "branch_messages": []}
                branches[bid]["branch_messages"].append(m)
            if main or branches:
                branched_chats[name] = {"main_branch": main, "branches": branches}
                if branches:
                    stats["total_branched_chats"] += 1
                    stats["branching_structure"][name] = {
                        "total_branches": len(branches),
                        "branch_lengths": [len(b["branch_messages"]) for b in branches.values()],
                        "total_edit_points": 0,
                        "average_time_gap": 0,
                    }
                    stats["edit_branches"][name] = {"count": 0, "average_branch_length": 0, "time_gaps": []}

        return jsonify({"branched_chats": branched_chats, "stats": stats})
    except Exception as e:
        logger.error("Error in /messages/branched", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/messages/add", methods=["POST"])
def add_message():
    """Append a single message to in-memory store."""
    data = request.json or {}
    chat_type    = data.get("type", "chatgpt")
    if chat_type not in IN_MEMORY_MESSAGES:
        return jsonify({"error": "Invalid chat type"}), 400

    chat_name    = data.get("chat_name")
    branch_id    = data.get("branch_id", "0")
    message_id   = data.get("message_id")
    text         = data.get("text")
    timestamp    = data.get("timestamp", datetime.now().isoformat())
    parent_msg   = data.get("parent_message")

    if not (chat_name and message_id and text):
        return jsonify({"error": "Missing required fields"}), 400

    # dedupe
    for m in IN_MEMORY_MESSAGES[chat_type]:
        if m["message_id"]==message_id and m["chat_name"]==chat_name:
            return jsonify({"success": False, "message": "Already exists"}), 400

    new_msg = {
        "chat_name": chat_name,
        "branch_id": branch_id,
        "message_id": message_id,
        "text": text,
        "timestamp": timestamp,
        "sender": data.get("sender","human")
    }
    if parent_msg:
        new_msg["parent_message"] = parent_msg

    IN_MEMORY_MESSAGES[chat_type].append(new_msg)
    background_processor.start_task()
    return jsonify({"success": True})


@api_bp.route("/messages/raw", methods=["GET"])
def get_raw_messages():
    """Return entire message list for a chat type."""
    chat_type = request.args.get("type", "chatgpt")
    if chat_type not in IN_MEMORY_MESSAGES:
        return jsonify({"error": "Invalid chat type"}), 400
    return jsonify(IN_MEMORY_MESSAGES[chat_type])


@api_bp.route("/messages/clear", methods=["POST"])
def clear_messages():
    """Wipe all messages for a chat type."""
    chat_type = request.json.get("type", "chatgpt")
    if chat_type not in IN_MEMORY_MESSAGES:
        return jsonify({"error": "Invalid chat type"}), 400
    IN_MEMORY_MESSAGES[chat_type] = []
    return jsonify({"success": True})


@api_bp.route("/content/identify-messages", methods=["POST"])
def identify_relevant_messages():
    """Placeholder: identify relevant messages in context."""
    return jsonify([])


@api_bp.route("/states", methods=["GET"])
def get_available_states():
    """Placeholder for historical state list."""
    return jsonify({"states": []})


@api_bp.route("/state/<month_year>", methods=["GET"])
def get_state(month_year):
    """Placeholder for a single month/year’s state."""
    return jsonify({"error": "State not found"}), 404


@api_bp.route("/health", methods=["GET"])
def health_check():
    """Simple health check."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})
