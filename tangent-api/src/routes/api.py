from datetime import datetime
import json
import os
from pathlib import Path
import re
import traceback
from collections import defaultdict

import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request
from torch import cosine_similarity
import openai
from openai import OpenAI

from services.embedding import get_embeddings
from services.background_processor import BackgroundProcessor
from services.data_processing import analyze_branches
from utils import load_visualization_data
from config import CLAUDE_DATA_DIR, CHATGPT_DATA_DIR, BASE_DATA_DIR
from services.topic_generation import generate_topic_for_cluster
from shared_data import models_data

api_bp = Blueprint("api", __name__)
background_processor = BackgroundProcessor()

# In-memory store for messages (reset on server restart)
IN_MEMORY_MESSAGES = {
    "chatgpt": [],
    "claude": []
}

# In-memory store for chats
IN_MEMORY_CHATS = {}

# ---------------------------------------------------------------------------
#  Data-processing routes
# ---------------------------------------------------------------------------

@api_bp.route("/process", methods=["POST"])
def process_data():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        file = request.files["file"]
        if not file.filename.endswith(".json"):
            return jsonify({"error": "Invalid file type"}), 400
        
        # Read the uploaded file and store in memory
        data = json.load(file)
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400
        
        # Append the uploaded messages to the in-memory store
        IN_MEMORY_MESSAGES[chat_type].extend(data)
        
        # Start a background task (if needed)
        task_id = background_processor.start_task(json.dumps(data))
        return jsonify({"task_id": task_id, "message": "Processing started"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/process/status/<task_id>", methods=["GET"])
def check_task_status(task_id):
    status = background_processor.get_task_status(task_id)
    if status:
        return jsonify({
            "status": status.status,
            "progress": status.progress,
            "error": status.error,
            "completed": status.completed,
        })
    return jsonify({"error": "Task not found"}), 404


# ---------------------------------------------------------------------------
#  Reflections / topics / models
# ---------------------------------------------------------------------------

@api_bp.route("/get-reflections", methods=["POST"])
def get_reflections():
    try:
        chat_type = request.args.get("type", "claude")
        current_context = request.json.get("context", "")
        if not current_context:
            return jsonify({"reflections": []})
        ctx_emb = np.array(get_embeddings([current_context])[0]).flatten()
        return jsonify({"reflections": []})
    except Exception as e:
        return jsonify({"reflections": []})


@api_bp.route("/topics", methods=["GET"])
def get_topics():
    return jsonify({"topics": []})


@api_bp.route("/topics/generate", methods=["POST"])
def generate_topic():
    try:
        data = request.json
        titles = data.get("titles", [])
        if not titles:
            return jsonify({"error": "No titles provided"}), 400
        topic = generate_topic_for_cluster(titles)
        return jsonify({"topic": topic})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/models/library", methods=["GET"])
def get_library_models():
    if not models_data:
        return jsonify({"error": "Models data not yet loaded"}), 503
    return jsonify({"models": models_data})


@api_bp.route("/models", methods=["GET"])
def get_models():
    return jsonify({
        "generation_model": os.getenv("GENERATION_MODEL", "Not Set"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "Not Set"),
    })


# ---------------------------------------------------------------------------
#  Embeddings & visualization
# ---------------------------------------------------------------------------

@api_bp.route("/embeddings", methods=["POST"])
def embeddings():
    return jsonify({"embeddings": get_embeddings(request.json.get("texts", []))})


@api_bp.route("/visualization", methods=["GET"])
def get_visualization_data():
    return jsonify([])


# ---------------------------------------------------------------------------
#  Chat management
# ---------------------------------------------------------------------------

@api_bp.route("/chats/save", methods=["POST"])
def save_chat():
    try:
        data = request.json
        chat_id = data.get("chatId", str(datetime.now().timestamp()))
        chat_data = {
            "id": chat_id,
            "nodes": data.get("nodes", []),
            "lastModified": datetime.now().isoformat(),
            "title": data.get("title", "Untitled Chat"),
            "metadata": data.get("metadata", {}),
        }
        IN_MEMORY_CHATS[chat_id] = chat_data
        return jsonify({
            "success": True,
            "chatId": chat_id,
            "message": "Chat saved successfully"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/chats/load/<chat_id>", methods=["GET"])
def load_chat(chat_id):
    try:
        if chat_id not in IN_MEMORY_CHATS:
            return jsonify({"success": False, "error": "Chat not found"}), 404
        return jsonify({"success": True, "data": IN_MEMORY_CHATS[chat_id]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/chats/list", methods=["GET"])
def list_chats():
    try:
        chats = []
        for chat_id, chat_data in IN_MEMORY_CHATS.items():
            chats.append({
                "id": chat_data["id"],
                "title": chat_data.get("title", "Untitled Chat"),
                "lastModified": chat_data.get("lastModified"),
                "metadata": chat_data.get("metadata", {}),
            })
        return jsonify({
            "success": True,
            "chats": sorted(chats, key=lambda x: x["lastModified"], reverse=True),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/chats/delete/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    try:
        if chat_id not in IN_MEMORY_CHATS:
            return jsonify({"success": False, "error": "Chat not found"}), 404
        del IN_MEMORY_CHATS[chat_id]
        return jsonify({"success": True, "message": "Chat deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
#  Message retrieval and branching
# ---------------------------------------------------------------------------

@api_bp.route("/messages/<path:chat_name>", methods=["GET"])
def get_chat_messages(chat_name):
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400
        
        all_messages = IN_MEMORY_MESSAGES[chat_type]
        match = re.match(r"^(.*) \(Branch (\d+)\)$", chat_name)
        if match:
            base_chat_name = match.group(1)
            branch_id = match.group(2)
        else:
            base_chat_name = chat_name
            branch_id = "0"
        
        chat_messages = [
            msg for msg in all_messages
            if msg.get("chat_name") == base_chat_name and msg.get("branch_id", "0") == branch_id
        ]
        if not chat_messages:
            return jsonify({"error": f"No messages found for chat: {chat_name}"}), 404
        chat_messages.sort(key=lambda x: pd.to_datetime(x.get("timestamp", "0")))
        return jsonify({"messages": chat_messages})
    except Exception as e:
        print(f"Error retrieving messages: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@api_bp.route("/messages_all/<path:chat_name>", methods=["GET"])
def get_all_chat_messages(chat_name):
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400
        
        all_messages = IN_MEMORY_MESSAGES[chat_type]
        match = re.match(r"^(.*) \(Branch \d+\)$", chat_name)
        if match:
            base_chat_name = match.group(1)
        else:
            base_chat_name = chat_name
        
        chat_messages = [
            msg for msg in all_messages if msg.get("chat_name") == base_chat_name
        ]
        if not chat_messages:
            return jsonify({"error": f"No messages found for chat: {chat_name}"}), 404
        
        branches = defaultdict(list)
        for msg in chat_messages:
            branch_id = msg.get("branch_id", "0")
            branches[branch_id].append(msg)
        
        for branch_msgs in branches.values():
            branch_msgs.sort(key=lambda x: pd.to_datetime(x.get("timestamp", "0")))
        return jsonify({"branches": dict(branches)})
    except Exception as e:
        print(f"Error retrieving messages: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@api_bp.route("/messages/branched", methods=["GET"])
def get_branched_messages():
    try:
        print("\n=== Starting Enhanced Branch Analysis ===")
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400

        # Use in-memory messages
        all_messages = IN_MEMORY_MESSAGES[chat_type]

        # If no messages exist, return an empty response
        if not all_messages:
            print("No messages found in memory. Returning empty response...")
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

        print(f"\nAnalyzing {len(all_messages)} messages for branches")
        branched_data = analyze_branches(all_messages)
        response_data = {
            "branched_chats": {},
            "stats": {
                "total_chats_analyzed": len(branched_data),
                "total_branched_chats": 0,
                "total_messages_processed": len(all_messages),
                "branching_structure": {},
                "edit_branches": {},
            },
        }

        for chat_name, chat_data in branched_data.items():
            edit_branches = chat_data.get("edit_branches", [])
            if edit_branches:
                chat_branches = {"main_branch": [], "branches": {}, "edit_points": []}
                for idx, branch in enumerate(edit_branches):
                    branch_id = f"branch_{idx + 1}"
                    parent_message = next(
                        (
                            msg for msg in chat_data["messages"]
                            if msg.get("message_id") == branch["parent_message"]
                        ),
                        None,
                    )
                    if parent_message:
                        if parent_message not in chat_branches["main_branch"]:
                            chat_branches["main_branch"].append(parent_message)
                        chat_branches["branches"][branch_id] = {
                            "parent_message": parent_message,
                            "branch_start": branch["edit_branch"],
                            "branch_messages": branch["branch_messages"],
                            "branch_length": len(branch["branch_messages"]),
                            "time_gap": branch["time_gap"],
                            "is_edit_branch": True,
                        }
                        chat_branches["edit_points"].append({
                            "parent_message_id": branch["parent_message"],
                            "original_message": branch["original_branch"],
                            "edit_message": branch["edit_branch"],
                            "time_gap": branch["time_gap"],
                        })
                if chat_branches["branches"]:
                    response_data["branched_chats"][chat_name] = chat_branches
                    response_data["stats"]["total_branched_chats"] += 1
                    response_data["stats"]["branching_structure"][chat_name] = {
                        "total_branches": len(chat_branches["branches"]),
                        "total_edit_points": len(chat_branches["edit_points"]),
                        "branch_lengths": [
                            data["branch_length"]
                            for data in chat_branches["branches"].values()
                        ],
                        "average_time_gap": np.mean(
                            [
                                branch["time_gap"]
                                for branch in chat_branches["branches"].values()
                            ] or [0]
                        ) if chat_branches["branches"] else 0,
                    }
                    response_data["stats"]["edit_branches"][chat_name] = {
                        "count": len(edit_branches),
                        "average_branch_length": np.mean(
                            [len(branch["branch_messages"]) for branch in edit_branches] or [0]
                        ),
                        "time_gaps": [branch["time_gap"] for branch in edit_branches],
                    }

        print("\n=== Branch Analysis Complete ===")
        print(f"Total chats analyzed: {response_data['stats']['total_chats_analyzed']}")
        print(f"Chats with edit branches: {response_data['stats']['total_branched_chats']}")
        print(f"Total messages processed: {response_data['stats']['total_messages_processed']}")
        return jsonify(response_data)

    except Exception as e:
        error_msg = f"Error processing branched messages: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500


@api_bp.route("/messages/add", methods=["POST"])
def add_message():
    try:
        data = request.json
        chat_type = data.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400

        chat_name = data.get("chat_name")
        branch_id = data.get("branch_id", "0")  # Default to main branch
        message_id = data.get("message_id")
        text = data.get("text")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        parent_message = data.get("parent_message", None)

        if not all([chat_name, message_id, text]):
            return jsonify({"error": "Missing required fields (chat_name, message_id, text)"}), 400

        new_message = {
            "chat_name": chat_name,
            "branch_id": branch_id,
            "message_id": message_id,
            "text": text,
            "timestamp": timestamp
        }
        if parent_message:
            new_message["parent_message"] = parent_message

        IN_MEMORY_MESSAGES[chat_type].append(new_message)
        return jsonify({"success": True, "message": "Message added successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/content/identify-messages", methods=["POST"])
def identify_relevant_messages():
    return jsonify([])


# ---------------------------------------------------------------------------
#  State management
# ---------------------------------------------------------------------------

@api_bp.route("/states", methods=["GET"])
def get_available_states():
    return jsonify({"states": []})


@api_bp.route("/state/<month_year>", methods=["GET"])
def get_state(month_year):
    return jsonify({"error": "State not found"}), 404


# ---------------------------------------------------------------------------
#  Text generation (ChatGPT / GPT-4o)
# ---------------------------------------------------------------------------

@api_bp.route("/generate", methods=["POST"])
def generate_text():
    prompt = request.json.get("prompt", "")
    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"error": "Missing OPENAI_API_KEY"}), 500
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Dialogos's helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )
        return jsonify({"response": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
#  Blueprint attachment (keep last)
# ---------------------------------------------------------------------------

def register_routes(app):
    app.register_blueprint(api_bp, url_prefix="/api")