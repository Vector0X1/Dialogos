# utils.py
import os
import json
import logging
from config import BASE_DATA_DIR, CLAUDE_DATA_DIR, CHATGPT_DATA_DIR

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_files_exist(data_dir: str) -> dict:
    REQUIRED_FILES = [
        "analytics.json",
        "embeddings_2d.json",
        "clusters.json",
        "topics.json",
        "chat_titles.json",
        "reflections.json",
    ]

    existing_files = {}
    for file in REQUIRED_FILES:
        path = os.path.join(data_dir, file)
        existing_files[file] = os.path.exists(path)
    logger.info(f"Checked files in {data_dir}: {existing_files}")
    return existing_files

def send_progress(step, progress=0):
    message = f"data: {json.dumps({'type': 'progress', 'step': step, 'progress': progress})}\n\n"
    logger.info(f"Sending progress: {message}")
    return message

def send_error(message):
    error_message = f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
    logger.error(f"Sending error: {error_message}")
    return error_message

def send_complete():
    message = f"data: {json.dumps({'type': 'complete'})}\n\n"
    logger.info("Sending complete message")
    return message

def ensure_directories():
    """Ensure all required data directories exist"""
    try:
        # Create base data directory
        os.makedirs(BASE_DATA_DIR, exist_ok=True)
        logger.info(f"Ensured directory: {BASE_DATA_DIR}")

        # Create chat-specific directories
        os.makedirs(CLAUDE_DATA_DIR, exist_ok=True)
        os.makedirs(CHATGPT_DATA_DIR, exist_ok=True)
        logger.info(f"Ensured directory: {CLAUDE_DATA_DIR}")
        logger.info(f"Ensured directory: {CHATGPT_DATA_DIR}")

        # Create states directories for both chat types
        os.makedirs(os.path.join(CLAUDE_DATA_DIR, "states"), exist_ok=True)
        os.makedirs(os.path.join(CHATGPT_DATA_DIR, "states"), exist_ok=True)
        logger.info(f"Ensured directory: {os.path.join(CLAUDE_DATA_DIR, 'states')}")
        logger.info(f"Ensured directory: {os.path.join(CHATGPT_DATA_DIR, 'states')}")
    except Exception as e:
        logger.error(f"Error ensuring directories: {str(e)}")

def load_visualization_data(data_dir: str) -> dict:
    """Load visualization data from the specified directory."""
    try:
        data = {}
        logger.info(f"Loading visualization data from {data_dir}")

        # Load embeddings
        embeddings_path = os.path.join(data_dir, "embeddings_2d.json")
        if os.path.exists(embeddings_path):
            with open(embeddings_path, "r") as f:
                data["points"] = json.load(f)
            logger.info(f"Loaded embeddings from {embeddings_path}")
        else:
            data["points"] = []
            logger.warning(f"Embeddings file not found at {embeddings_path}")

        # Load clusters
        clusters_path = os.path.join(data_dir, "clusters.json")
        if os.path.exists(clusters_path):
            with open(clusters_path, "r") as f:
                data["clusters"] = json.load(f)
            logger.info(f"Loaded clusters from {clusters_path}")
        else:
            data["clusters"] = []
            logger.warning(f"Clusters file not found at {clusters_path}")

        # Load topics
        topics_path = os.path.join(data_dir, "topics.json")
        if os.path.exists(topics_path):
            with open(topics_path, "r") as f:
                data["topics"] = json.load(f)
            logger.info(f"Loaded topics from {topics_path}")
        else:
            data["topics"] = {}
            logger.warning(f"Topics file not found at {topics_path}")

        # Load chat titles (now include branch info)
        titles_path = os.path.join(data_dir, "chat_titles.json")
        if os.path.exists(titles_path):
            with open(titles_path, "r") as f:
                data["titles"] = json.load(f)
            logger.info(f"Loaded titles from {titles_path}")
        else:
            data["titles"] = []
            logger.warning(f"Titles file not found at {titles_path}")

        # Load chats with reflections
        reflections_path = os.path.join(data_dir, "chats_with_reflections.json")
        if os.path.exists(reflections_path):
            with open(reflections_path, "r") as f:
                data["chats_with_reflections"] = json.load(f)
            logger.info(f"Loaded reflections from {reflections_path}")
        else:
            data["chats_with_reflections"] = []
            logger.warning(f"Reflections file not found at {reflections_path}")

        return data

    except Exception as e:
        logger.error(f"Error loading visualization data: {str(e)}")
        return {
            "points": [],
            "clusters": [],
            "titles": [],
            "topics": {},
            "chats_with_reflections": [],
        }