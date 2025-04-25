# routes/api.py
from flask import Blueprint, jsonify, request
import logging
from utils import load_visualization_data, CLAUDE_DATA_DIR, CHATGPT_DATA_DIR

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

@api_bp.route('/generate', methods=['POST'])
def generate():
    try:
        logger.info("Received request to /api/generate")
        data = request.get_json()
        if not data:
            logger.warning("No data provided in /api/generate request")
            return jsonify({"error": "No data provided"}), 400
        # Add your generation logic here
        # For now, return a mock response
        response = {"message": "Generated response", "data": data}
        logger.info("Successfully generated response")
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error in /api/generate: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/messages/branched', methods=['GET'])
def get_branched_messages():
    try:
        logger.info("Received request to /api/messages/branched")
        chat_type = request.args.get('type')
        if not chat_type:
            logger.warning("Chat type not provided in /api/messages/branched request")
            return jsonify({"error": "Chat type not provided"}), 400

        # Determine the data directory based on chat type
        data_dir = CLAUDE_DATA_DIR if chat_type == "claude" else CHATGPT_DATA_DIR
        data = load_visualization_data(data_dir)

        # Transform data into the expected format
        chats_with_reflections = data.get("chats_with_reflections", [])
        titles = data.get("titles", [])

        # Build branched chats structure
        branched_chats = {}
        for chat in chats_with_reflections:
            chat_id = chat.get("chat_id")
            if not chat_id:
                continue

            # Find the chat title
            title_entry = next((t for t in titles if t.get("chat_id") == chat_id), None)
            chat_name = title_entry.get("title", chat_id) if title_entry else chat_id

            main_branch = chat.get("messages", [])
            branches = chat.get("branches", {})

            # Ensure messages have required fields
            main_branch = [
                msg for msg in main_branch
                if msg.get("message_id") and msg.get("text") and msg.get("timestamp")
            ]

            # Process branches
            processed_branches = {}
            for branch_id, branch_data in branches.items():
                branch_messages = branch_data.get("branch_messages", [])
                parent_message = branch_data.get("parent_message", {})
                if not parent_message.get("message_id"):
                    continue
                branch_messages = [
                    msg for msg in branch_messages
                    if msg.get("message_id") and msg.get("text") and msg.get("timestamp")
                ]
                processed_branches[branch_id] = {
                    "parent_message": parent_message,
                    "branch_messages": branch_messages,
                }

            branched_chats[chat_name] = {
                "main_branch": main_branch,
                "branches": processed_branches,
            }

        response = {
            "branched_chats": branched_chats,
            "stats": {
                "total_chats_analyzed": len(chats_with_reflections),
                "total_branched_chats": sum(1 for chat in chats_with_reflections if chat.get("branches")),
                "total_messages_processed": sum(len(chat.get("messages", [])) for chat in chats_with_reflections),
            }
        }
        logger.info("Successfully fetched branched messages")
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error in /api/messages/branched: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/chats/list', methods=['GET'])
def list_chats():
    try:
        logger.info("Received request to /api/chats/list")
        # Load titles from both Claude and ChatGPT directories
        claude_data = load_visualization_data(CLAUDE_DATA_DIR)
        chatgpt_data = load_visualization_data(CHATGPT_DATA_DIR)

        claude_titles = claude_data.get("titles", [])
        chatgpt_titles = chatgpt_data.get("titles", [])

        chats = [
            {"id": title["chat_id"], "title": title.get("title", title["chat_id"]), "type": "claude"}
            for title in claude_titles
        ] + [
            {"id": title["chat_id"], "title": title.get("title", title["chat_id"]), "type": "chatgpt"}
            for title in chatgpt_titles
        ]

        response = {
            "success": True,
            "chats": chats,
        }
        logger.info("Successfully fetched chat list")
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error in /api/chats/list: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/chats/load/<chat_id>', methods=['GET'])
def load_chat(chat_id):
    try:
        logger.info(f"Received request to /api/chats/load/{chat_id}")
        # Determine chat type (we'll check both directories)
        claude_data = load_visualization_data(CLAUDE_DATA_DIR)
        chatgpt_data = load_visualization_data(CHATGPT_DATA_DIR)

        # Find the chat in either Claude or ChatGPT data
        chat = None
        chat_type = None
        for data, c_type in [(claude_data, "claude"), (chatgpt_data, "chatgpt")]:
            chats = data.get("chats_with_reflections", [])
            chat = next((c for c in chats if c.get("chat_id") == chat_id), None)
            if chat:
                chat_type = c_type
                break

        if not chat:
            logger.warning(f"Chat {chat_id} not found")
            return jsonify({"error": "Chat not found"}), 404

        # Find the chat title
        titles = data.get("titles", [])
        title_entry = next((t for t in titles if t.get("chat_id") == chat_id), None)
        title = title_entry.get("title", chat_id) if title_entry else chat_id

        response = {
            "success": True,
            "data": {
                "id": chat_id,
                "title": title,
                "nodes": [
                    {
                        "id": 1,
                        "type": "main",
                        "title": title,
                        "messages": chat.get("messages", []),
                        "x": 50,
                        "y": 150,
                    }
                ],
                "type": chat_type,
            }
        }
        logger.info(f"Successfully loaded chat {chat_id}")
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error in /api/chats/load/{chat_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500