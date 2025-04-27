import os
import sys
import logging
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

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
CORS(app, resources={
    r"/*": {
        "origins": ["https://open-l confounders-six.vercel.app", "http://localhost:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

app.register_blueprint(api_bp, url_prefix="/api")

# Initialize BackgroundProcessor
background_processor = BackgroundProcessor()

def load_in_memory_messages():
    """Load persisted messages from disk into IN_MEMORY_MESSAGES."""
    for chat_type in ["chatgpt", "claude"]:
        file_path = os.path.join(BASE_DATA_DIR, f"{chat_type}_messages.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                IN_MEMORY_MESSAGES[chat_type] = json.load(f)
            logger.info(f"Loaded {len(IN_MEMORY_MESSAGES[chat_type])} messages for {chat_type}")

def periodic_processing():
    """Periodically process in-memory messages to generate visualization data."""
    while True:
        logger.info("Starting periodic processing of in-memory messages")
        task_id = background_processor.start_task()  # No file_path for in-memory
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
    logger.error(f"Unhandled exception: {str(e)}")
    response = jsonify({"error": "Internal server error"})
    return response, 500

if __name__ == "__main__":
    try:
        logger.info("Starting application...")
        ensure_directories()
        load_in_memory_messages()
        processing_thread = threading.Thread(target=periodic_processing, daemon=True)
        processing_thread.start()
        port = int(os.environ.get("PORT", 5001))
        if os.environ.get("RENDER"):
            logger.info("Running on Render with gunicorn")
            app.run(host="0.0.0.0", port=port)
        else:
            logger.info("Running in development mode")
            app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}")
        raise