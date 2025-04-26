from datetime import datetime
import json
import os
from pathlib import Path
import re
import traceback
from collections import defaultdict

import numpy as np
import pandas as pd
from flask import Flask, Blueprint, jsonify, request
from openai import OpenAI
import logging

from services.embedding import get_embeddings
from services.background_processor import BackgroundProcessor
from services.data_processing import analyze_branches
from services.topic_generation import generate_topic_for_cluster
from utils import load_visualization_data
from config import CLAUDE_DATA_DIR, CHATGPT_DATA_DIR, BASE_DATA_DIR, GENERATION_MODEL
from shared_data import models_data

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# CORS configuration is now handled in app.py, so no need to configure it here

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
#  Tags endpoint (added to fix 500 error)
# ---------------------------------------------------------------------------

@api_bp.route("/tags", methods=["GET"])
def get_tags():
    # The frontend expects an array of tags. Returning an empty array for now.
    return jsonify([])

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
        messages = IN_MEMORY_MESSAGES[chat_type]
        print(f"Messages in {chat_type}: {messages}")
        
        # If no messages exist, return an empty response
        if not messages:
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

        # Organize messages into chats
        chats = {}
        for msg in messages:
            # Validate message structure
            if not all(key in msg for key in ["chat_name", "branch_id", "message_id", "text", "timestamp"]):
                print(f"Invalid message structure, skipping: {msg}")
                continue
            chat_name = msg["chat_name"]
            if chat_name not in chats:
                chats[chat_name] = []
            chats[chat_name].append(msg)
        print(f"Chats: {chats}")

        # Prepare response structure
        branched_chats = {}
        stats = {
            "branching_structure": {},
            "edit_branches": {},
            "total_branched_chats": 0,
            "total_chats_analyzed": len(chats),
            "total_messages_processed": len(messages)
        }

        # Process each chat for branching
        for chat_name, chat_messages in chats.items():
            print(f"Processing chat: {chat_name}")
            main_branch = [msg for msg in chat_messages if msg["branch_id"] == "0"]
            print(f"Main branch for {chat_name}: {main_branch}")
            branches = {}
            branched_messages = [msg for msg in chat_messages if msg["branch_id"] != "0"]
            print(f"Branched messages for {chat_name}: {branched_messages}")

            for msg in branched_messages:
                branch_id = msg["branch_id"]
                print(f"Processing branched message: {msg}")
                if branch_id not in branches:
                    # Prefer parent from main branch
                    parent_msg = next(
                        (m for m in chat_messages if m["message_id"] == msg.get("parent_message") and m["branch_id"] == "0"),
                        None
                    )
                    # If not found in main branch, look in all messages
                    if parent_msg is None:
                        parent_msg = next(
                            (m for m in chat_messages if m["message_id"] == msg.get("parent_message")),
                            None
                        )
                    print(f"Parent message for {msg['message_id']}: {parent_msg}")
                    branches[branch_id] = {
                        "parent_message": parent_msg,
                        "branch_messages": []
                    }
                branches[branch_id]["branch_messages"].append(msg)
            print(f"Branches for {chat_name}: {branches}")

            # Include the chat in branched_chats if it has either a main branch or branches
            if main_branch or branches:
                print(f"Adding {chat_name} to branched_chats")
                branched_chats[chat_name] = {
                    "main_branch": main_branch,
                    "branches": branches
                }
                if branches:
                    stats["total_branched_chats"] += 1
                    # Compute additional stats for branching structure
                    stats["branching_structure"][chat_name] = {
                        "total_branches": len(branches),
                        "total_edit_points": 0,  # Not implemented in this version
                        "branch_lengths": [
                            len(branch["branch_messages"]) for branch in branches.values()
                        ],
                        "average_time_gap": 0  # Not computed in this version
                    }
                    stats["edit_branches"][chat_name] = {
                        "count": 0,  # Not implemented in this version
                        "average_branch_length": 0,
                        "time_gaps": []
                    }
            else:
                print(f"Skipping {chat_name}: no main branch or branches")

        print(f"Final branched_chats: {branched_chats}")
        print("\n=== Branch Analysis Complete ===")
        print(f"Total chats analyzed: {stats['total_chats_analyzed']}")
        print(f"Chats with branches: {stats['total_branched_chats']}")
        print(f"Total messages processed: {stats['total_messages_processed']}")
        return jsonify({
            "branched_chats": branched_chats,
            "stats": stats
        })

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

        # Check for duplicate message_id within the same chat_name
        existing_message = next(
            (msg for msg in IN_MEMORY_MESSAGES[chat_type] if msg["message_id"] == message_id and msg["chat_name"] == chat_name),
            None
        )
        if existing_message:
            print(f"Message with message_id {message_id} already exists for chat {chat_name}: {existing_message}")
            return jsonify({"success": False, "message": "Message with this ID already exists"}), 400

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
        print(f"Message added: {new_message}")
        return jsonify({"success": True, "message": "Message added successfully"})
    except Exception as e:
        print(f"Error in add_message: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/raw", methods=["GET"])
def get_raw_messages():
    chat_type = request.args.get("type", "chatgpt")
    if chat_type not in IN_MEMORY_MESSAGES:
        return jsonify({"error": "Invalid chat type"}), 400
    return jsonify(IN_MEMORY_MESSAGES[chat_type])

@api_bp.route("/messages/clear", methods=["POST"])
def clear_messages():
    chat_type = request.json.get("type", "chatgpt")
    if chat_type not in IN_MEMORY_MESSAGES:
        return jsonify({"error": "Invalid chat type"}), 400
    IN_MEMORY_MESSAGES[chat_type] = []
    return jsonify({"success": True, "message": "Messages cleared"})

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
    logger.info("Received request to /api/generate")
    prompt = request.json.get("prompt", "")
    logger.info(f"Prompt received: {prompt}")
    if not prompt:
        logger.warning("Empty prompt received")
        return jsonify({"error": "Empty prompt"}), 400
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Default to gpt-4o-mini
    api_key = os.getenv("OPENAI_API_KEY")
    logger.info(f"Using model: {model}")
    if not api_key:
        logger.error("Missing OPENAI_API_KEY")
        return jsonify({"error": "Missing OPENAI_API_KEY"}), 500
    try:
        logger.info("Initializing OpenAI client")
        client = OpenAI(api_key=api_key)
        logger.info("Sending request to OpenAI API")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Dialogos's helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )
        logger.info("Received response from OpenAI API")
        return jsonify({"response": response.choices[0].message.content})
    except Exception as e:
        logger.error(f"Error in OpenAI API call: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
#  Health check (useful for keeping Render warm)
# ---------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ---------------------------------------------------------------------------
#  Blueprint attachment
# ---------------------------------------------------------------------------

app.register_blueprint(api_bp, url_prefix="/api")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))