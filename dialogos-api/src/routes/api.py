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

# In-memory store for chats
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
    """Generate a response using OpenAI or DeepSeek API and store in IN_MEMORY_MESSAGES."""
    data = request.json or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400

    # choose model, key, base_url, and which in-memory bucket
    model = data.get("model", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    if model.startswith("deepseek"):
        api_key     = os.getenv("DEEPSEEK_API_KEY")
        base_url    = "https://api.deepseek.com"
        storage_key = "deepseek"
    else:
        api_key     = os.getenv("OPENAI_API_KEY")
        base_url    = None
        storage_key = "chatgpt"

    if not api_key:
        missing = "DEEPSEEK_API_KEY" if storage_key=="deepseek" else "OPENAI_API_KEY"
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

        # persist
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

        background_processor.start_task()
        return jsonify({"response": response_text})
    except Exception as e:
        logger.error("Error in /generate", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/models/library", methods=["GET"])
def get_library_models():
    """Return available models."""
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
    return jsonify([])

@api_bp.route("/embeddings", methods=["POST"])
def embeddings():
    texts = request.json.get("texts", [])
    embeddings_data = get_embeddings(texts)
    return jsonify({"embeddings": embeddings_data})

@api_bp.route("/visualization", methods=["GET"])
def get_visualization_data():
    """Serve visualization data—both ChatGPT & DeepSeek share the same data dir."""
    try:
        chat_type = request.args.get("type", "chatgpt")
        if chat_type not in ["chatgpt", "deepseek"]:
            return jsonify({"error": "Invalid chat type"}), 400

        data_dir = CHATGPT_DATA_DIR
        viz = load_visualization_data(data_dir)
        # validate
        if not all(isinstance(viz.get(k), t) for k,t in [
            ("points", list), ("clusters", list), ("titles", list), ("topics", dict)
        ]):
            return jsonify({
                "error": "No visualization data available",
                "points": [], "clusters": [], "titles": [], "topics": {}, "chats_with_reflections": []
            }), 200

        return jsonify(viz)

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
            "sender": data.get("sender", "human")
        }
        if parent_message:
            new_message["parent_message"] = parent_message

        IN_MEMORY_MESSAGES[chat_type].append(new_message)
        logger.info(f"Message added: {new_message}")

        # Trigger background processing
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
    logger.info(f"Received request to /api/state/{month_year}")a
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