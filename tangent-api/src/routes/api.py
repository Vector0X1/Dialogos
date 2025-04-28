# src/routes/api.py
from datetime import datetime
import json
import os
import re
import traceback
from collections import defaultdict

import numpy as np
import pandas as pd
from flask import Blueprint, request, jsonify
from openai import OpenAI
import logging

from src.services.embedding import get_embeddings
from src.services.background_processor import BackgroundProcessor
from src.services.data_processing import analyze_branches
from src.services.topic_generation import generate_topic_for_cluster
from src.utils import load_visualization_data
from src.config import CLAUDE_DATA_DIR, CHATGPT_DATA_DIR, BASE_DATA_DIR, IN_MEMORY_MESSAGES, models_data  # Updated import

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)
background_processor = BackgroundProcessor()

# In-memory store for chats
IN_MEMORY_CHATS = {}

@api_bp.route("/generate", methods=["POST"])
def generate_text():
    """Generate a response using OpenAI's ChatGPT API and store in IN_MEMORY_MESSAGES."""
    logger.info("Received request to /api/generate")
    data = request.json
    prompt = data.get("prompt", "")
    logger.info(f"Prompt received: {prompt}")
    if not prompt:
        logger.warning("Empty prompt received")
        return jsonify({"error": "Empty prompt"}), 400
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
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
        response_text = response.choices[0].message.content
        logger.info("Received response from OpenAI API")

        # Store in IN_MEMORY_MESSAGES
        chat_name = data.get("chat_name", "Default Chat")
        branch_id = data.get("branch_id", "0")
        timestamp = datetime.now().isoformat()
        IN_MEMORY_MESSAGES.setdefault("chatgpt", []).extend([
            {
                "chat_name": chat_name,
                "branch_id": branch_id,
                "message_id": f"msg_{timestamp}_human",
                "text": prompt,
                "timestamp": timestamp,
                "sender": "human"
            },
            {
                "chat_name": chat_name,
                "branch_id": branch_id,
                "message_id": f"msg_{timestamp}_assistant",
                "text": response_text,
                "timestamp": timestamp,
                "sender": "assistant"
            }
        ])

        # Trigger background processing
        background_processor.start_task()

        return jsonify({"response": response_text})

    except Exception as e:
        logger.error(f"Error in OpenAI API call: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/process", methods=["POST"])
def process_data():
    """Process uploaded chat data file (fallback for manual uploads)."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        file = request.files["file"]
        if not file.filename.endswith(".json"):
            return jsonify({"error": "Invalid file type"}), 400
        
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400
        
        # Save file temporarily
        temp_dir = os.path.join(BASE_DATA_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"{time.time()}.json")
        file.save(file_path)
        
        # Start background task
        task_id = background_processor.start_task(file_path)
        return jsonify({"task_id": task_id, "message": "Processing started"}), 202
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/process/status/<task_id>", methods=["GET"])
def check_task_status(task_id):
    """Check the status of a processing task."""
    status = background_processor.get_task_status(task_id)
    if status:
        return jsonify({
            "status": status.status,
            "progress": status.progress,
            "error": status.error,
            "completed": status.completed,
        })
    return jsonify({"error": "Task not found"}), 404

@api_bp.route("/get-reflections", methods=["POST"])
def get_reflections():
    """Placeholder for reflections."""
    try:
        chat_type = request.args.get("type", "chatgpt")
        current_context = request.json.get("context", "")
        if not current_context:
            return jsonify({"reflections": []})
        ctx_emb = np.array(get_embeddings([current_context])[0]).flatten()
        return jsonify({"reflections": []})
    except Exception as e:
        logger.error(f"Error getting reflections: {str(e)}")
        return jsonify({"reflections": []})

@api_bp.route("/topics", methods=["GET"])
def get_topics():
    """Return available topics."""
    return jsonify({"topics": []})

@api_bp.route("/topics/generate", methods=["POST"])
def generate_topic():
    """Generate a topic for a cluster of titles."""
    try:
        data = request.json
        titles = data.get("titles", [])
        if not titles:
            return jsonify({"error": "No titles provided"}), 400
        topic = generate_topic_for_cluster(titles)
        return jsonify({"topic": topic})
    except Exception as e:
        logger.error(f"Error generating topic: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/models/library", methods=["GET"])
def get_library_models():
    """Return available models."""
    if not models_data:
        return jsonify({"error": "Models data not yet loaded"}), 503
    return jsonify({"models": models_data})

@api_bp.route("/models", methods=["GET"])
def get_models():
    """Return current model configuration."""
    return jsonify({
        "generation_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
    })

@api_bp.route("/tags", methods=["GET"])
def get_tags():
    """Return available tags (placeholder)."""
    return jsonify([])

@api_bp.route("/embeddings", methods=["POST"])
def embeddings():
    """Generate embeddings for provided texts."""
    return jsonify({"embeddings": get_embeddings(request.json.get("texts", []))})

@api_bp.route("/visualization", methods=["GET"])
def get_visualization_data():
    """Serve visualization data for the frontend."""
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in ["chatgpt", "claude"]:
            return jsonify({"error": "Invalid chat type"}), 400

        data_dir = CHATGPT_DATA_DIR if chat_type == "chatgpt" else CLAUDE_DATA_DIR
        logger.info(f"Fetching visualization data for chat_type={chat_type} from {data_dir}")

        visualization_data = load_visualization_data(data_dir)

        if (
            not isinstance(visualization_data.get("points"), list) or
            not isinstance(visualization_data.get("clusters"), list) or
            not isinstance(visualization_data.get("titles"), list) or
            not isinstance(visualization_data.get("topics"), dict)
        ):
            logger.warning(f"Invalid or incomplete visualization data in {data_dir}")
            return jsonify({
                "error": "No visualization data available for this chat type",
                "points": [],
                "clusters": [],
                "titles": [],
                "topics": {},
                "chats_with_reflections": []
            }), 200

        logger.info(f"Successfully loaded visualization data")
        return jsonify(visualization_data)

    except Exception as e:
        logger.error(f"Error fetching visualization data: {str(e)}")
        return jsonify({
            "error": str(e),
            "points": [],
            "clusters": [],
            "titles": [],
            "topics": {},
            "chats_with_reflections": []
        }), 500

@api_bp.route("/chats/save", methods=["POST"])
def save_chat():
    """Save chat data."""
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
        logger.error(f"Error saving chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/chats/load/<chat_id>", methods=["GET"])
def load_chat(chat_id):
    """Load chat data."""
    try:
        if chat_id not in IN_MEMORY_CHATS:
            return jsonify({"success": False, "error": "Chat not found"}), 404
        return jsonify({"success": True, "data": IN_MEMORY_CHATS[chat_id]})
    except Exception as e:
        logger.error(f"Error loading chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/chats/list", methods=["GET"])
def list_chats():
    """List all chats."""
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
        logger.error(f"Error listing chats: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/chats/delete/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    """Delete a chat."""
    try:
        if chat_id not in IN_MEMORY_CHATS:
            return jsonify({"success": False, "error": "Chat not found"}), 404
        del IN_MEMORY_CHATS[chat_id]
        return jsonify({"success": True, "message": "Chat deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/messages/<path:chat_name>", methods=["GET"])
def get_chat_messages(chat_name):
    """Retrieve messages for a specific chat and branch."""
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
        logger.error(f"Error retrieving messages: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages_all/<path:chat_name>", methods=["GET"])
def get_all_chat_messages(chat_name):
    """Retrieve all branches for a chat."""
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
        logger.error(f"Error retrieving messages: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/branched", methods=["GET"])
def get_branched_messages():
    """Retrieve branched chat structure."""
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400

        messages = IN_MEMORY_MESSAGES[chat_type]
        if not messages:
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
                logger.warning(f"Invalid message structure: {msg}")
                continue
            chat_name = msg["chat_name"]
            if chat_name not in chats:
                chats[chat_name] = []
            chats[chat_name].append(msg)

        branched_chats = {}
        stats = {
            "branching_structure": {},
            "edit_branches": {},
            "total_branched_chats": 0,
            "total_chats_analyzed": len(chats),
            "total_messages_processed": len(messages)
        }

        for chat_name, chat_messages in chats.items():
            main_branch = [msg for msg in chat_messages if msg["branch_id"] == "0"]
            branches = {}
            branched_messages = [msg for msg in chat_messages if msg["branch_id"] != "0"]

            for msg in branched_messages:
                branch_id = msg["branch_id"]
                if branch_id not in branches:
                    parent_msg = next(
                        (m for m in chat_messages if m["message_id"] == msg.get("parent_message") and m["branch_id"] == "0"),
                        None
                    ) or next(
                        (m for m in chat_messages if m["message_id"] == msg.get("parent_message")),
                        None
                    )
                    branches[branch_id] = {
                        "parent_message": parent_msg,
                        "branch_messages": []
                    }
                branches[branch_id]["branch_messages"].append(msg)

            if main_branch or branches:
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

        return jsonify({
            "branched_chats": branched_chats,
            "stats": stats
        })

    except Exception as e:
        logger.error(f"Error processing branched messages: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/add", methods=["POST"])
def add_message():
    """Add a message to IN_MEMORY_MESSAGES."""
    try:
        data = request.json
        chat_type = data.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            return jsonify({"error": "Invalid chat type"}), 400

        chat_name = data.get("chat_name")
        branch_id = data.get("branch_id", "0")
        message_id = data.get("message_id")
        text = data.get("text")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        parent_message = data.get("parent_message", None)

        if not all([chat_name, message_id, text]):
            return jsonify({"error": "Missing required fields (chat_name, message_id, text)"}), 400

        existing_message = next(
            (msg for msg in IN_MEMORY_MESSAGES[chat_type] if msg["message_id"] == message_id and msg["chat_name"] == chat_name),
            None
        )
        if existing_message:
            logger.warning(f"Message with message_id {message_id} already exists for chat {chat_name}")
            return jsonify({"success": False, "message": "Message with this ID already exists"}), 400

        new_message = {
            "chat_name": chat_name,
            "branch_id": branch_id,
            "message_id": message_id,
            "text": text,
            "timestamp": timestamp,
            "sender": data.get("sender", "human")
        }
        if parent_message:
            new_message["parent_message"] = parent_message

        IN_MEMORY_MESSAGES[chat_type].append(new_message)
        logger.info(f"Message added: {new_message}")

        # Trigger background processing
        background_processor.start_task()

        return jsonify({"success": True, "message": "Message added successfully"})
    except Exception as e:
        logger.error(f"Error in add_message: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/raw", methods=["GET"])
def get_raw_messages():
    """Return all raw messages for a chat type."""
    chat_type = request.args.get("type", "chatgpt")
    if chat_type not in IN_MEMORY_MESSAGES:
        return jsonify({"error": "Invalid chat type"}), 400
    return jsonify(IN_MEMORY_MESSAGES[chat_type])

@api_bp.route("/messages/clear", methods=["POST"])
def clear_messages():
    """Clear all messages for a chat type."""
    chat_type = request.json.get("type", "chatgpt")
    if chat_type not in IN_MEMORY_MESSAGES:
        return jsonify({"error": "Invalid chat type"}), 400
    IN_MEMORY_MESSAGES[chat_type] = []
    return jsonify({"success": True, "message": "Messages cleared"})

@api_bp.route("/content/identify-messages", methods=["POST"])
def identify_relevant_messages():
    """Placeholder for identifying relevant messages."""
    return jsonify([])

@api_bp.route("/states", methods=["GET"])
def get_available_states():
    """Return available states (placeholder)."""
    return jsonify({"states": []})

@api_bp.route("/state/<month_year>", methods=["GET"])
def get_state(month_year):
    """Return state data (placeholder)."""
    return jsonify({"error": "State not found"}), 404

@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})