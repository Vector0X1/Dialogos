from datetime import datetime
import json
import os
from pathlib import Path
import re
import traceback
from collections import defaultdict
import logging

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

# Set up logging
logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)
background_processor = BackgroundProcessor()

# In-memory store for messages (loaded from/saved to file)
IN_MEMORY_MESSAGES = {
    "chatgpt": [],
    "claude": []
}

# In-memory store for chats
IN_MEMORY_CHATS = {}

# File-based persistence for messages
MESSAGES_FILE = "messages.json"

def load_messages():
    global IN_MEMORY_MESSAGES
    try:
        with open(MESSAGES_FILE, "r") as f:
            IN_MEMORY_MESSAGES = json.load(f)
        logger.info(f"Loaded messages from {MESSAGES_FILE}")
    except FileNotFoundError:
        logger.info(f"No {MESSAGES_FILE} found, using empty IN_MEMORY_MESSAGES")
        IN_MEMORY_MESSAGES = {"chatgpt": [], "claude": []}
    except Exception as e:
        logger.error(f"Error loading messages: {str(e)}")
        IN_MEMORY_MESSAGES = {"chatgpt": [], "claude": []}

def save_messages():
    try:
        with open(MESSAGES_FILE, "w") as f:
            json.dump(IN_MEMORY_MESSAGES, f)
        logger.info(f"Saved messages to {MESSAGES_FILE}")
    except Exception as e:
        logger.error(f"Error saving messages: {str(e)}")

# Load messages at startup
load_messages()

# ---------------------------------------------------------------------------
#  Data-processing routes
# ---------------------------------------------------------------------------

@api_bp.route("/process", methods=["POST"])
def process_data():
    try:
        if "file" not in request.files:
            logger.error("No file uploaded")
            return jsonify({"error": "No file uploaded"}), 400
        file = request.files["file"]
        if not file.filename.endswith(".json"):
            logger.error("Invalid file type")
            return jsonify({"error": "Invalid file type"}), 400
        
        # Read the uploaded file and store in memory
        data = json.load(file)
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.error(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400
        
        # Append the uploaded messages to the in-memory store
        IN_MEMORY_MESSAGES[chat_type].extend(data)
        save_messages()
        
        # Start a background task (if needed)
        task_id = background_processor.start_task(json.dumps(data))
        logger.info(f"Processing started for task_id: {task_id}")
        return jsonify({"task_id": task_id, "message": "Processing started"}), 202
    except Exception as e:
        logger.error(f"Error in process_data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/process/status/<task_id>", methods=["GET"])
def check_task_status(task_id):
    try:
        status = background_processor.get_task_status(task_id)
        if status:
            logger.info(f"Task status for {task_id}: {status.status}")
            return jsonify({
                "status": status.status,
                "progress": status.progress,
                "error": status.error,
                "completed": status.completed,
            })
        logger.error(f"Task not found: {task_id}")
        return jsonify({"error": "Task not found"}), 404
    except Exception as e:
        logger.error(f"Error in check_task_status: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
#  Reflections / topics / models
# ---------------------------------------------------------------------------

@api_bp.route("/get-reflections", methods=["POST"])
def get_reflections():
    try:
        chat_type = request.args.get("type", "claude")
        current_context = request.json.get("context", "")
        logger.info(f"Fetching reflections for chat_type: {chat_type}")
        if not current_context:
            logger.info("Empty context, returning empty reflections")
            return jsonify({"reflections": []})
        ctx_emb = np.array(get_embeddings([current_context])[0]).flatten()
        return jsonify({"reflections": []})  # Implement actual logic if needed
    except Exception as e:
        logger.error(f"Error in get_reflections: {str(e)}")
        return jsonify({"reflections": []})

@api_bp.route("/topics", methods=["GET"])
def get_topics():
    try:
        logger.info("Fetching topics")
        return jsonify({"topics": []})  # Implement actual logic if needed
    except Exception as e:
        logger.error(f"Error in get_topics: {str(e)}")
        return jsonify({"topics": []})

@api_bp.route("/topics/generate", methods=["POST"])
def generate_topic():
    try:
        data = request.json
        titles = data.get("titles", [])
        if not titles:
            logger.error("No titles provided")
            return jsonify({"error": "No titles provided"}), 400
        topic = generate_topic_for_cluster(titles)
        logger.info(f"Generated topic: {topic}")
        return jsonify({"topic": topic})
    except Exception as e:
        logger.error(f"Error in generate_topic: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/models/library", methods=["GET"])
def get_library_models():
    try:
        if not models_data:
            logger.error("Models data not yet loaded")
            return jsonify({"error": "Models data not yet loaded"}), 503
        logger.info("Fetching library models")
        return jsonify({"models": models_data})
    except Exception as e:
        logger.error(f"Error in get_library_models: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/models", methods=["GET"])
def get_models():
    try:
        logger.info("Fetching model configurations")
        return jsonify({
            "generation_model": os.getenv("GENERATION_MODEL", "Not Set"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "Not Set"),
        })
    except Exception as e:
        logger.error(f"Error in get_models: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
#  Embeddings & visualization
# ---------------------------------------------------------------------------

@api_bp.route("/embeddings", methods=["POST"])
def embeddings():
    try:
        texts = request.json.get("texts", [])
        logger.info(f"Generating embeddings for {len(texts)} texts")
        return jsonify({"embeddings": get_embeddings(texts)})
    except Exception as e:
        logger.error(f"Error in embeddings: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/visualization", methods=["GET"])
def get_visualization_data():
    try:
        logger.info("Fetching visualization data")
        data = []  # Replace with actual logic if implemented
        logger.info(f"Visualization data: {data}")
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error in get_visualization_data: {str(e)}")
        return jsonify({"error": str(e)}), 500

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
        logger.info(f"Saved chat: {chat_id}")
        return jsonify({
            "success": True,
            "chatId": chat_id,
            "message": "Chat saved successfully"
        })
    except Exception as e:
        logger.error(f"Error in save_chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/chats/load/<chat_id>", methods=["GET"])
def load_chat(chat_id):
    try:
        if chat_id not in IN_MEMORY_CHATS:
            logger.error(f"Chat not found: {chat_id}")
            return jsonify({"success": False, "error": "Chat not found"}), 404
        logger.info(f"Loaded chat: {chat_id}")
        return jsonify({"success": True, "data": IN_MEMORY_CHATS[chat_id]})
    except Exception as e:
        logger.error(f"Error in load_chat: {str(e)}")
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
        logger.info(f"Listed {len(chats)} chats")
        return jsonify({
            "success": True,
            "chats": sorted(chats, key=lambda x: x["lastModified"], reverse=True),
        })
    except Exception as e:
        logger.error(f"Error in list_chats: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/chats/delete/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    try:
        if chat_id not in IN_MEMORY_CHATS:
            logger.error(f"Chat not found: {chat_id}")
            return jsonify({"success": False, "error": "Chat not found"}), 404
        del IN_MEMORY_CHATS[chat_id]
        logger.info(f"Deleted chat: {chat_id}")
        return jsonify({"success": True, "message": "Chat deleted successfully"})
    except Exception as e:
        logger.error(f"Error in delete_chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------------------------------------------------------------------
#  Message retrieval and branching
# ---------------------------------------------------------------------------

@api_bp.route("/messages/<path:chat_name>", methods=["GET"])
def get_chat_messages(chat_name):
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.error(f"Invalid chat type: {chat_type}")
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
            logger.error(f"No messages found for chat: {chat_name}")
            return jsonify({"error": f"No messages found for chat: {chat_name}"}), 404
        chat_messages.sort(key=lambda x: pd.to_datetime(x.get("timestamp", "0")))
        logger.info(f"Fetched {len(chat_messages)} messages for chat: {chat_name}")
        return jsonify({"messages": chat_messages})
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages_all/<path:chat_name>", methods=["GET"])
def get_all_chat_messages(chat_name):
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.error(f"Invalid chat type: {chat_type}")
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
            logger.error(f"No messages found for chat: {chat_name}")
            return jsonify({"error": f"No messages found for chat: {chat_name}"}), 404
        
        branches = defaultdict(list)
        for msg in chat_messages:
            branch_id = msg.get("branch_id", "0")
            branches[branch_id].append(msg)
        
        for branch_msgs in branches.values():
            branch_msgs.sort(key=lambda x: pd.to_datetime(x.get("timestamp", "0")))
        logger.info(f"Fetched {len(chat_messages)} messages across {len(branches)} branches for chat: {chat_name}")
        return jsonify({"branches": dict(branches)})
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/branched", methods=["GET"])
def get_branched_messages():
    try:
        logger.info("\n=== Starting Enhanced Branch Analysis ===")
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.error(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400

        messages = IN_MEMORY_MESSAGES[chat_type]
        logger.info(f"Messages in {chat_type}: {len(messages)} messages")
        
        if not messages:
            logger.info("No messages found in memory. Returning empty response...")
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

        chats = {}
        for msg in messages:
            if not all(key in msg for key in ["chat_name", "branch_id", "message_id", "text", "timestamp"]):
                logger.warning(f"Invalid message structure, skipping: {msg}")
                continue
            chat_name = msg["chat_name"]
            if chat_name not in chats:
                chats[chat_name] = []
            chats[chat_name].append(msg)
        logger.info(f"Chats: {len(chats)}")

        branched_chats = {}
        stats = {
            "branching_structure": {},
            "edit_branches": {},
            "total_branched_chats": 0,
            "total_chats_analyzed": len(chats),
            "total_messages_processed": len(messages)
        }

        for chat_name, chat_messages in chats.items():
            logger.info(f"Processing chat: {chat_name}")
            main_branch = [msg for msg in chat_messages if msg["branch_id"] == "0"]
            logger.info(f"Main branch for {chat_name}: {len(main_branch)} messages")
            branches = {}
            branched_messages = [msg for msg in chat_messages if msg["branch_id"] != "0"]
            logger.info(f"Branched messages for {chat_name}: {len(branched_messages)}")

            for msg in branched_messages:
                branch_id = msg["branch_id"]
                logger.debug(f"Processing branched message: {msg['message_id']}")
                if branch_id not in branches:
                    parent_msg = next(
                        (m for m in chat_messages if m["message_id"] == msg.get("parent_message") and m["branch_id"] == "0"),
                        None
                    )
                    if parent_msg is None:
                        parent_msg = next(
                            (m for m in chat_messages if m["message_id"] == msg.get("parent_message")),
                            None
                        )
                    logger.debug(f"Parent message for {msg['message_id']}: {parent_msg['message_id'] if parent_msg else 'None'}")
                    branches[branch_id] = {
                        "parent_message": parent_msg,
                        "branch_messages": []
                    }
                branches[branch_id]["branch_messages"].append(msg)

            if main_branch or branches:
                logger.info(f"Adding {chat_name} to branched_chats")
                branched_chats[chat_name] = {
                    "main_branch": main_branch,
                    "branches": branches
                }
                if branches:
                    stats["total_branched_chats"] += 1
                    stats["branching_structure"][chat_name] = {
                        "total_branches": len(branches),
                        "total_edit_points": 0,
                        "branch_lengths": [
                            len(branch["branch_messages"]) for branch in branches.values()
                        ],
                        "average_time_gap": 0
                    }
                    stats["edit_branches"][chat_name] = {
                        "count": 0,
                        "average_branch_length": 0,
                        "time_gaps": []
                    }

        logger.info(f"Final branched_chats: {len(branched_chats)} chats")
        logger.info("\n=== Branch Analysis Complete ===")
        logger.info(f"Total chats analyzed: {stats['total_chats_analyzed']}")
        logger.info(f"Chats with branches: {stats['total_branched_chats']}")
        logger.info(f"Total messages processed: {stats['total_messages_processed']}")
        return jsonify({
            "branched_chats": branched_chats,
            "stats": stats
        })

    except Exception as e:
        error_msg = f"Error processing branched messages: {str(e)}"
        logger.error(error_msg)
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500

@api_bp.route("/messages/add", methods=["POST"])
def add_message():
    try:
        data = request.json
        chat_type = data.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.error(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400

        chat_name = data.get("chat_name")
        branch_id = data.get("branch_id", "0")
        message_id = data.get("message_id")
        text = data.get("text")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        parent_message = data.get("parent_message", None)

        if not all([chat_name, message_id, text]):
            logger.error("Missing required fields (chat_name, message_id, text)")
            return jsonify({"error": "Missing required fields (chat_name, message_id, text)"}), 400

        existing_message = next(
            (msg for msg in IN_MEMORY_MESSAGES[chat_type] if msg["message_id"] == message_id and msg["chat_name"] == chat_name),
            None
        )
        if existing_message:
            logger.error(f"Message with message_id {message_id} already exists for chat {chat_name}")
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
        save_messages()
        logger.info(f"Message added: {new_message}")
        return jsonify({"success": True, "message": "Message added successfully"})
    except Exception as e:
        logger.error(f"Error in add_message: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/raw", methods=["GET"])
def get_raw_messages():
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.error(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400
        logger.info(f"Fetched raw messages for {chat_type}: {len(IN_MEMORY_MESSAGES[chat_type])} messages")
        return jsonify(IN_MEMORY_MESSAGES[chat_type])
    except Exception as e:
        logger.error(f"Error in get_raw_messages: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/clear", methods=["POST"])
def clear_messages():
    try:
        chat_type = request.json.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.error(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400
        IN_MEMORY_MESSAGES[chat_type] = []
        save_messages()
        logger.info(f"Cleared messages for {chat_type}")
        return jsonify({"success": True, "message": "Messages cleared"})
    except Exception as e:
        logger.error(f"Error in clear_messages: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/content/identify-messages", methods=["POST"])
def identify_relevant_messages():
    try:
        logger.info("Identifying relevant messages")
        return jsonify([])  # Implement actual logic if needed
    except Exception as e:
        logger.error(f"Error in identify_relevant_messages: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
#  State management
# ---------------------------------------------------------------------------

@api_bp.route("/states", methods=["GET"])
def get_available_states():
    try:
        logger.info("Fetching available states")
        states = []  # Replace with actual logic if implemented
        logger.info(f"Available states: {states}")
        return jsonify({"states": states})
    except Exception as e:
        logger.error(f"Error in get_available_states: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/state/<month_year>", methods=["GET"])
def get_state(month_year):
    try:
        logger.info(f"Fetching state for {month_year}")
        return jsonify({"error": "State not found"}), 404  # Implement actual logic if needed
    except Exception as e:
        logger.error(f"Error in get_state: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
#  Text generation (ChatGPT / GPT-4o)
# ---------------------------------------------------------------------------

@api_bp.route("/generate", methods=["POST"])
def generate_text():
    try:
        prompt = request.json.get("prompt", "")
        if not prompt:
            logger.error("Empty prompt received")
            return jsonify({"error": "Empty prompt"}), 400

        model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("Missing OPENAI_API_KEY")
            return jsonify({"error": "Missing OPENAI_API_KEY"}), 500

        client = OpenAI(api_key=api_key)
        logger.info(f"Calling OpenAI API with model: {model}")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Dialogos's helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            timeout=30
        )
        logger.info("OpenAI API call successful")
        return jsonify({"response": response.choices[0].message.content})
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return jsonify({"error": f"OpenAI API error: {str(e)}"}), 500
    except openai.APITimeoutError:
        logger.error("OpenAI API timeout")
        return jsonify({"error": "OpenAI API request timed out"}), 504
    except Exception as e:
        logger.error(f"Unexpected error in generate_text: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
#  Blueprint attachment (keep last)
# ---------------------------------------------------------------------------

def register_routes(app):
    app.register_blueprint(api_bp, url_prefix="/api")