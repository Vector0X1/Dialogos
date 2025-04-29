import os
import json
import logging
from src.config import BASE_DATA_DIR, CHATGPT_DATA_DIR, DEEPSEEK_DATA_DIR

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_files_exist(data_dir: str) -> dict:
    """Check if required files exist in the specified directory."""
    REQUIRED_FILES = [
        "analytics.json",
        "embeddings_2d.json",
        "clusters.json",
        "topics.json",
        "chat_titles.json",
        "reflections.json",
    ]

    existing_files = {}
    try:
        for file in REQUIRED_FILES:
            path = os.path.join(data_dir, file)
            exists = os.path.exists(path)
            existing_files[file] = exists
            logger.debug(f"Checked file {path}: exists={exists}")
        logger.info(f"Checked files in {data_dir}: {existing_files}")
    except Exception as e:
        logger.error(f"Error checking files in {data_dir}: {str(e)}", exc_info=True)
        existing_files = {file: False for file in REQUIRED_FILES}
    return existing_files

def send_progress(step: str, progress: float = 0) -> str:
    """Send a progress update in SSE format."""
    try:
        message = f"data: {json.dumps({'type': 'progress', 'step': step, 'progress': progress})}\n\n"
        logger.info(f"Sending progress: step={step}, progress={progress}")
        return message
    except Exception as e:
        logger.error(f"Error sending progress: {str(e)}", exc_info=True)
        return f"data: {json.dumps({'type': 'error', 'message': 'Failed to send progress update'})}\n\n"

def send_error(message: str) -> str:
    """Send an error message in SSE format."""
    try:
        error_message = f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
        logger.error(f"Sending error: {message}")
        return error_message
    except Exception as e:
        logger.error(f"Error sending error message: {str(e)}", exc_info=True)
        return f"data: {json.dumps({'type': 'error', 'message': 'Failed to send error message'})}\n\n"

def send_complete() -> str:
    """Send a completion message in SSE format."""
    try:
        message = f"data: {json.dumps({'type': 'complete'})}\n\n"
        logger.info("Sending complete message")
        return message
    except Exception as e:
        logger.error(f"Error sending complete message: {str(e)}", exc_info=True)
        return f"data: {json.dumps({'type': 'error', 'message': 'Failed to send complete message'})}\n\n"

def ensure_directories():
    """Ensure all required data directories exist."""
    try:
        os.makedirs(BASE_DATA_DIR, exist_ok=True)
        logger.info(f"Ensured directory: {BASE_DATA_DIR}")

        os.makedirs(CHATGPT_DATA_DIR, exist_ok=True)
        os.makedirs(DEEPSEEK_DATA_DIR, exist_ok=True)
        logger.info(f"Ensured directory: {CHATGPT_DATA_DIR}")
        logger.info(f"Ensured directory: {DEEPSEEK_DATA_DIR}")

        os.makedirs(os.path.join(CHATGPT_DATA_DIR, "states"), exist_ok=True)
        os.makedirs(os.path.join(DEEPSEEK_DATA_DIR, "states"), exist_ok=True)
        logger.info(f"Ensured directory: {os.path.join(CHATGPT_DATA_DIR, 'states')}")
        logger.info(f"Ensured directory: {os.path.join(DEEPSEEK_DATA_DIR, 'states')}")
    except Exception as e:
        logger.error(f"Error ensuring directories: {str(e)}", exc_info=True)
        logger.warning("Proceeding without ensuring directories; file operations may fail later")

def load_visualization_data(data_dir: str) -> dict:
    """Load visualization data from the specified directory."""
    try:
        data = {
            "points": [],
            "clusters": [],
            "titles": [],
            "topics": {},
            "chats_with_reflections": []
        }
        logger.info(f"Loading visualization data from {data_dir}")

        embeddings_path = os.path.join(data_dir, "embeddings_2d.json")
        if os.path.exists(embeddings_path):
            with open(embeddings_path, "r") as f:
                data["points"] = json.load(f)
            logger.info(f"Loaded embeddings from {embeddings_path}")
        else:
            logger.warning(f"Embeddings file not found at {embeddings_path}")

        clusters_path = os.path.join(data_dir, "clusters.json")
        if os.path.exists(clusters_path):
            with open(clusters_path, "r") as f:
                data["clusters"] = json.load(f)
            logger.info(f"Loaded clusters from {clusters_path}")
        else:
            logger.warning(f"Clusters file not found at {clusters_path}")

        topics_path = os.path.join(data_dir, "topics.json")
        if os.path.exists(topics_path):
            with open(topics_path, "r") as f:
                data["topics"] = json.load(f)
            logger.info(f"Loaded topics from {topics_path}")
        else:
            logger.warning(f"Topics file not found at {topics_path}")

        titles_path = os.path.join(data_dir, "chat_titles.json")
        if os.path.exists(titles_path):
            with open(titles_path, "r") as f:
                data["titles"] = json.load(f)
            logger.info(f"Loaded titles from {titles_path}")
        else:
            logger.warning(f"Titles file not found at {titles_path}")

        reflections_path = os.path.join(data_dir, "chats_with_reflections.json")
        if os.path.exists(reflections_path):
            with open(reflections_path, "r") as f:
                data["chats_with_reflections"] = json.load(f)
            logger.info(f"Loaded reflections from {reflections_path}")
        else:
            logger.warning(f"Reflections file not found at {reflections_path}")

        return data

    except Exception as e:
        logger.error(f"Error loading visualization data from {data_dir}: {str(e)}", exc_info=True)
        return {
            "points": [],
            "clusters": [],
            "titles": [],
            "topics": {},
            "chats_with_reflections": [],
        }