from datetime import datetime
import json
import os
import re
import time
import traceback
from collections import defaultdict

import numpy as np
import pandas as pd
from flask import Blueprint, request, jsonify, make_response
from openai import OpenAI
import requests
import logging

from src.services.embedding import get_embeddings
from src.services.background_processor import BackgroundProcessor
from src.services.data_processing import analyze_branches
from src.services.topic_generation import generate_topic_for_cluster
from src.utils import load_visualization_data
from src.config import CHATGPT_DATA_DIR, DEEPSEEK_DATA_DIR, BASE_DATA_DIR, IN_MEMORY_MESSAGES, models_data

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)
background_processor = BackgroundProcessor()

# In-memory store for chats
IN_MEMORY_CHATS = {}

# Middleware to ensure CORS headers are added to all responses
@api_bp.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "*")
    allowed_origins = ["https://open-lac-six.vercel.app", "http://localhost:3000", "http://localhost:3001"]
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "null"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Max-Age"] = "86400"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@api_bp.route("/generate", methods=["POST"])
def generate_text():
    """Generate a response using OpenAI or DeepSeek API and store in IN_MEMORY_MESSAGES."""
    logger.info("Received request to /api/generate")
    data = request.json
    logger.debug(f"Request data: {data}")
    prompt = data.get("prompt", "")
    model = data.get("model", "gpt-4o-mini")
    chat_type = data.get("chat_type", "chatgpt")
    logger.info(f"Prompt received: {prompt}, Model: {model}, Chat Type: {chat_type}")
    if not prompt:
        logger.warning("Empty prompt received")
        return jsonify({"error": "Empty prompt"}), 400
    if chat_type not in IN_MEMORY_MESSAGES:
        logger.warning(f"Invalid chat type: {chat_type}")
        return jsonify({"error": "Invalid chat type"}), 400

    chat_name = data.get("chat_name", "Default Chat")
    branch_id = data.get("branch_id", "0")
    timestamp = datetime.now().isoformat()

    try:
        if model.startswith("deepseek"):
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                logger.error("Missing DEEPSEEK_API_KEY")
                return jsonify({"error": "Missing DEEPSEEK_API_KEY"}), 500
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": data.get("system", "You are Dialogos's helpful assistant.")},
                    {"role": "user", "content": prompt},
                ],
                "temperature": data.get("options", {}).get("temperature", 0.8)
            }
            logger.info("Sending request to DeepSeek API")
            response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()
            if not response_data.get("choices") or not response_data["choices"][0].get("message"):
                logger.error("Invalid DeepSeek API response")
                return jsonify({"error": "Invalid response from DeepSeek API"}), 500
            response_text = response_data["choices"][0]["message"]["content"]
            logger.info("Received response from DeepSeek API")

        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("Missing OPENAI_API_KEY")
                return jsonify({"error": "Missing OPENAI_API_KEY"}), 500
            logger.info("Initializing OpenAI client")
            client = OpenAI(api_key=api_key)
            logger.info("Sending request to OpenAI API")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": data.get("system", "You are Dialogos's helpful assistant.")},
                    {"role": "user", "content": prompt},
                ],
                temperature=data.get("options", {}).get("temperature", 0.8)
            )
            response_text = response.choices[0].message.content
            logger.info("Received response from OpenAI API")

        IN_MEMORY_MESSAGES.setdefault(chat_type, []).extend([
            {
                "chat_name": chat_name,
                "branch_id": branch_id,
                "message_id": f"msg_{timestamp}_human",
                "text": prompt,
                "timestamp": timestamp,
                "sender": "human",
                "model": model
            },
            {
                "chat_name": chat_name,
                "branch_id": branch_id,
                "message_id": f"msg_{timestamp}_assistant",
                "text": response_text,
                "timestamp": timestamp,
                "sender": "assistant",
                "model": model
            }
        ])
        logger.debug(f"Updated IN_MEMORY_MESSAGES for {chat_type}: {len(IN_MEMORY_MESSAGES[chat_type])} messages")

        logger.info("Triggering background processing")
        background_processor.start_task()

        logger.info("Returning response to client")
        return jsonify({"response": response_text})

    except requests.RequestException as e:
        logger.error(f"DeepSeek API request failed: {str(e)}", exc_info=True)
        return jsonify({"error": f"DeepSeek API error: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error in API call: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/process", methods=["POST"])
def process_data():
    """Process uploaded chat data file (fallback for manual uploads)."""
    try:
        logger.info("Received request to /api/process")
        if "file" not in request.files:
            logger.warning("No file uploaded in request")
            return jsonify({"error": "No file uploaded"}), 400
        file = request.files["file"]
        if not file.filename.endswith(".json"):
            logger.warning(f"Invalid file type: {file.filename}")
            return jsonify({"error": "Invalid file type"}), 400
        
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.warning(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400
        
        temp_dir = os.path.join(BASE_DATA_DIR, "temp")
        logger.info(f"Creating temp directory: {temp_dir}")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"{time.time()}.json")
        logger.info(f"Saving file to: {file_path}")
        file.save(file_path)
        
        logger.info("Starting background task")
        task_id = background_processor.start_task(file_path)
        logger.info(f"Background task started with ID: {task_id}")
        return jsonify({"task_id": task_id, "message": "Processing started"}), 202
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/process/status/<task_id>", methods=["GET"])
def check_task_status(task_id):
    """Check the status of a processing task."""
    logger.info(f"Received request to /api/process/status/{task_id}")
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
        logger.warning(f"Task not found: {task_id}")
        return jsonify({"error": "Task not found"}), 404
    except Exception as e:
        logger.error(f"Error checking task status: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/get-reflections", methods=["POST"])
def get_reflections():
    """Placeholder for reflections."""
    logger.info("Received request to /api/get-reflections")
    try:
        chat_type = request.args.get("type", "chatgpt")
        current_context = request.json.get("context", "")
        if not current_context:
            logger.info("No context provided, returning empty reflections")
            return jsonify({"reflections": []})
        logger.info("Generating embeddings for context")
        ctx_emb = np.array(get_embeddings([current_context])[0]).flatten()
        logger.info("Returning placeholder reflections")
        return jsonify({"reflections": []})
    except Exception as e:
        logger.error(f"Error getting reflections: {str(e)}", exc_info=True)
        return jsonify({"reflections": []})

@api_bp.route("/topics", methods=["GET"])
def get_topics():
    """Return available topics."""
    logger.info("Received request to /api/topics")
    return jsonify({"topics": []})

@api_bp.route("/topics/generate", methods=["POST"])
def generate_topic():
    """Generate a topic for a cluster of titles."""
    logger.info("Received request to /api/topics/generate")
    try:
        data = request.json
        logger.debug(f"Request data: {data}")
        titles = data.get("titles", [])
        if not titles:
            logger.warning("No titles provided")
            return jsonify({"error": "No titles provided"}), 400
        logger.info(f"Generating topic for {len(titles)} titles")
        topic = generate_topic_for_cluster(titles)
        logger.info(f"Generated topic: {topic}")
        return jsonify({"topic": topic})
    except Exception as e:
        logger.error(f"Error generating topic: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/models/library", methods=["GET"])
def get_library_models():
    """Return available models."""
    logger.info("Received request to /api/models/library")
    try:
        logger.info(f"Returning {len(models_data)} models")
        return jsonify({"models": models_data if models_data else []})
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}", exc_info=True)
        return jsonify({"models": [], "error": str(e)}), 500

@api_bp.route("/models", methods=["GET"])
def get_models():
    """Return current model configuration."""
    logger.info("Received request to /api/models")
    try:
        models_config = {
            "generation_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "deepseek_model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        }
        logger.info(f"Returning models config: {models_config}")
        return jsonify(models_config)
    except Exception as e:
        logger.error(f"Error fetching models config: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/tags", methods=["GET"])
def get_tags():
    """Return available models (for DialogosChat compatibility)."""
    logger.info("Received request to /api/tags")
    try:
        logger.info(f"Returning {len(models_data)} models")
        return jsonify(models_data)  # Return array directly
    except Exception as e:
        logger.error(f"Error fetching tags: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/embeddings", methods=["POST"])
def embeddings():
    """Generate embeddings for provided texts."""
    logger.info("Received request to /api/embeddings")
    try:
        texts = request.json.get("texts", [])
        logger.info(f"Generating embeddings for {len(texts)} texts")
        embeddings_data = get_embeddings(texts)
        logger.info("Returning embeddings")
        return jsonify({"embeddings": embeddings_data})
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/visualization", methods=["GET"])
def get_visualization_data():
    """Serve visualization data for the frontend."""
    logger.info("Received request to /api/visualization")
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in ["chatgpt", "deepseek"]:
            logger.warning(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400

        data_dir = {
            "chatgpt": CHATGPT_DATA_DIR,
            "deepseek": DEEPSEEK_DATA_DIR
        }[chat_type]
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
        logger.error(f"Error fetching visualization data: {str(e)}", exc_info=True)
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
    logger.info("Received request to /api/chats/save")
    try:
        data = request.json
        logger.debug(f"Request data: {data}")
        chat_id = data.get("chatId", str(datetime.now().timestamp()))
        chat_data = {
            "id": chat_id,
            "nodes": data.get("nodes", []),
            "lastModified": datetime.now().isoformat(),
            "title": data.get("title", "Untitled Chat"),
            "metadata": data.get("metadata", {}),
        }
        IN_MEMORY_CHATS[chat_id] = chat_data
        logger.info(f"Saved chat with ID: {chat_id}")
        return jsonify({
            "success": True,
            "chatId": chat_id,
            "message": "Chat saved successfully"
        })
    except Exception as e:
        logger.error(f"Error saving chat: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/chats/load/<chat_id>", methods=["GET"])
def load_chat(chat_id):
    """Load chat data."""
    logger.info(f"Received request to /api/chats/load/{chat_id}")
    try:
        if chat_id not in IN_MEMORY_CHATS:
            logger.warning(f"Chat not found: {chat_id}")
            return jsonify({"success": False, "error": "Chat not found"}), 404
        logger.info(f"Loaded chat with ID: {chat_id}")
        return jsonify({"success": True, "data": IN_MEMORY_CHATS[chat_id]})
    except Exception as e:
        logger.error(f"Error loading chat: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/chats/list", methods=["GET"])
def list_chats():
    """List all chats."""
    logger.info("Received request to /api/chats/list")
    try:
        chats = []
        for chat_id, chat_data in IN_MEMORY_CHATS.items():
            chats.append({
                "id": chat_data["id"],
                "title": chat_data.get("title", "Untitled Chat"),
                "lastModified": chat_data.get("lastModified"),
                "metadata": chat_data.get("metadata", {}),
            })
        logger.info(f"Returning {len(chats)} chats")
        return jsonify({
            "success": True,
            "chats": sorted(chats, key=lambda x: x["lastModified"], reverse=True),
        })
    except Exception as e:
        logger.error(f"Error listing chats: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/chats/delete/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    """Delete a chat."""
    logger.info(f"Received request to /api/chats/delete/{chat_id}")
    try:
        if chat_id not in IN_MEMORY_CHATS:
            logger.warning(f"Chat not found: {chat_id}")
            return jsonify({"success": False, "error": "Chat not found"}), 404
        del IN_MEMORY_CHATS[chat_id]
        logger.info(f"Deleted chat with ID: {chat_id}")
        return jsonify({"success": True, "message": "Chat deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting chat: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/messages/<path:chat_name>", methods=["GET"])
def get_chat_messages(chat_name):
    """Retrieve messages for a specific chat and branch."""
    logger.info(f"Received request to /api/messages/{chat_name}")
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.warning(f"Invalid chat type: {chat_type}")
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
            logger.warning(f"No messages found for chat: {chat_name}")
            return jsonify({"error": f"No messages found for chat: {chat_name}"}), 404
        chat_messages.sort(key=lambda x: pd.to_datetime(x.get("timestamp", "0")))
        logger.info(f"Returning {len(chat_messages)} messages for chat: {chat_name}")
        return jsonify({"messages": chat_messages})
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages_all/<path:chat_name>", methods=["GET"])
def get_all_chat_messages(chat_name):
    """Retrieve all branches for a chat."""
    logger.info(f"Received request to /api/messages_all/{chat_name}")
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.warning(f"Invalid chat type: {chat_type}")
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
            logger.warning(f"No messages found for chat: {chat_name}")
            return jsonify({"error": f"No messages found for chat: {chat_name}"}), 404
        
        branches = defaultdict(list)
        for msg in chat_messages:
            branch_id = msg.get("branch_id", "0")
            branches[branch_id].append(msg)
        
        for branch_msgs in branches.values():
            branch_msgs.sort(key=lambda x: pd.to_datetime(x.get("timestamp", "0")))
        logger.info(f"Returning branches for chat: {chat_name}")
        return jsonify({"branches": dict(branches)})
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/branched", methods=["GET"])
def get_branched_messages():
    """Retrieve branched chat structure."""
    logger.info("Received request to /api/messages/branched")
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.warning(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400

        messages = IN_MEMORY_MESSAGES[chat_type]
        if not messages:
            logger.info("No messages available")
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

        logger.info("Returning branched chat structure")
        return jsonify({
            "branched_chats": branched_chats,
            "stats": stats
        })

    except Exception as e:
        logger.error(f"Error processing branched messages: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/add", methods=["POST"])
def add_message():
    """Add a message to IN_MEMORY_MESSAGES."""
    logger.info("Received request to /api/messages/add")
    try:
        data = request.json
        logger.debug(f"Request data: {data}")
        chat_type = data.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.warning(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400

        chat_name = data.get("chat_name")
        branch_id = data.get("branch_id", "0")
        message_id = data.get("message_id")
        text = data.get("text")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        parent_message = data.get("parent_message", None)
        model = data.get("model", "gpt-4o-mini")

        if not all([chat_name, message_id, text]):
            logger.warning("Missing required fields (chat_name, message_id, text)")
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
            "sender": data.get("sender", "human"),
            "model": model
        }
        if parent_message:
            new_message["parent_message"] = parent_message

        IN_MEMORY_MESSAGES[chat_type].append(new_message)
        logger.info(f"Message added: {new_message}")

        logger.info("Triggering background processing")
        background_processor.start_task()

        logger.info("Message added successfully")
        return jsonify({"success": True, "message": "Message added successfully"})
    except Exception as e:
        logger.error(f"Error in add_message: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/raw", methods=["GET"])
def get_raw_messages():
    """Return all raw messages for a chat type."""
    logger.info("Received request to /api/messages/raw")
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.warning(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400
        logger.info(f"Returning raw messages for chat type: {chat_type}")
        return jsonify(IN_MEMORY_MESSAGES[chat_type])
    except Exception as e:
        logger.error(f"Error retrieving raw messages: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/messages/clear", methods=["POST"])
def clear_messages():
    """Clear all messages for a chat type."""
    logger.info("Received request to /api/messages/clear")
    try:
        chat_type = request.json.get("type", "chatgpt")
        if chat_type not in IN_MEMORY_MESSAGES:
            logger.warning(f"Invalid chat type: {chat_type}")
            return jsonify({"error": "Invalid chat type"}), 400
        IN_MEMORY_MESSAGES[chat_type] = []
        logger.info(f"Cleared messages for chat type: {chat_type}")
        return jsonify({"success": True, "message": "Messages cleared"})
    except Exception as e:
        logger.error(f"Error clearing messages: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/content/identify-messages", methods=["POST"])
def identify_relevant_messages():
    """Placeholder for identifying relevant messages."""
    logger.info("Received request to /api/content/identify-messages")
    try:
        logger.info("Returning placeholder for relevant messages")
        return jsonify([])
    except Exception as e:
        logger.error(f"Error identifying relevant messages: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/states", methods=["GET"])
def get_available_states():
    """Return available states (placeholder)."""
    logger.info("Received request to /api/states")
    try:
        logger.info("Returning placeholder states")
        return jsonify({"states": []})
    except Exception as e:
        logger.error(f"Error fetching states: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/state/<month_year>", methods=["GET"])
def get_state(month_year):
    """Return state data (placeholder)."""
    logger.info(f"Received request to /api/state/{month_year}")
    try:
        logger.info("Returning placeholder state data")
        return jsonify({"error": "State not found"}), 404
    except Exception as e:
        logger.error(f"Error fetching state: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    logger.info("Received request to /api/health")
    try:
        logger.info("Returning health status")
        return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500