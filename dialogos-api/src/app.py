# src/app.py
import os
import sys
import logging
import threading
import time
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import json

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.routes.api import api_bp
from src.utils import ensure_directories
from src.services.background_processor import BackgroundProcessor
from src.config import BASE_DATA_DIR, IN_MEMORY_MESSAGES

# Set up logging for Render debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure CORS globally for all routes
CORS(app, resources={ r"/api/*": {
        "origins": ["https://open-lac-six.vercel.app", "http://localhost:3000", "https://app.dialogos.tech", "http://localhost:3001"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

app.register_blueprint(api_bp, url_prefix="/api")

# Explicitly handle OPTIONS requests for all routes
@app.route("/<path:path>", methods=["OPTIONS"])
def handle_options(path):
    logger.info(f"Handling OPTIONS request for path: {path}")
    response = make_response()
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Max-Age"] = "86400"
    return response

# Initialize BackgroundProcessor
background_processor = BackgroundProcessor()

def load_in_memory_messages():
    """Load persisted messages from disk into IN_MEMORY_MESSAGES."""
    for chat_type in ["chatgpt", "deepseek"]:
        file_path = os.path.join(BASE_DATA_DIR, f"{chat_type}_messages.json")
        try:
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    IN_MEMORY_MESSAGES[chat_type] = json.load(f)
                logger.info(f"Loaded {len(IN_MEMORY_MESSAGES[chat_type])} messages for {chat_type}")
            else:
                logger.info(f"No persisted messages found for {chat_type} at {file_path}")
        except Exception as e:
            logger.error(f"Error loading messages for {chat_type}: {str(e)}", exc_info=True)
            IN_MEMORY_MESSAGES[chat_type] = []  # Fallback to empty list

def periodic_processing():
    """Periodically process in-memory messages to generate visualization data."""
    while True:
        logger.info("Starting periodic processing of in-memory messages")
        try:
            task_id = background_processor.start_task()  # No file_path for in-memory
            logger.info(f"Started background task with ID: {task_id}")
        except Exception as e:
            logger.error(f"Error in periodic processing: {str(e)}", exc_info=True)
        time.sleep(300)  # Process every 5 minutes

# Health check endpoint
@app.route("/health")
def health():
    logger.info("Health check requested")
    return jsonify({"status": "OK"}), 200

@app.before_request
def before_request():
    logger.info(f"Incoming request: {request.path} {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")

@app.after_request
def after_request(response):
    logger.info(f"Outgoing response: {response.status_code}")
    logger.info(f"Headers: {dict(response.headers)}")
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    response = jsonify({"error": "Internal server error"})
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    return response, 500

if __name__ == "__main__":
    try:
        logger.info("Starting application...")
        try:
            ensure_directories()
        except Exception as e:
            logger.error(f"Failed to ensure directories: {str(e)}", exc_info=True)
        try:
            load_in_memory_messages()
        except Exception as e:
            logger.error(f"Failed to load in-memory messages: {str(e)}", exc_info=True)
        try:
            processing_thread = threading.Thread(target=periodic_processing, daemon=True)
            processing_thread.start()
        except Exception as e:
            logger.error(f"Failed to start periodic processing thread: {str(e)}", exc_info=True)
        port = int(os.environ.get("PORT", 5001))
        logger.info(f"Starting Flask app on port {port}")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}", exc_info=True)
        raise