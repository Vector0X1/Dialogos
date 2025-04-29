# services/background_tasks.py
import re
import threading
import traceback
import time
import logging
import requests
from shared_data import models_data

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_background_tasks_started = False
_lock = threading.Lock()  # To prevent race conditions

def start_background_tasks():
    global _background_tasks_started
    with _lock:
        if not _background_tasks_started:
            try:
                _background_tasks_started = True
                logger.info("Starting background task to fetch models...")
                threading.Thread(target=fetch_and_store_models, daemon=True).start()
                logger.info("Background task started successfully")
            except Exception as e:
                logger.error(f"Failed to start background tasks: {str(e)}")
                traceback.print_exc()

def fetch_and_store_models():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }

        logger.info("Fetching models from ollama.com/library...")
        try:
            models_response = requests.get(
                "https://ollama.com/library", headers=headers, timeout=10
            )
            logger.info(f"Initial response status: {models_response.status_code}")
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.error(f"Connection error or timeout occurred: {str(e)}")
            return
        except requests.RequestException as e:
            logger.error(f"An error occurred during the request: {str(e)}")
            return

        if models_response.status_code != 200:
            logger.error(f"Failed to fetch models: Status {models_response.status_code}")
            return

        try:
            model_links = re.findall(r'href="/library/([^"]+)', models_response.text)
            logger.info(f"Found {len(model_links)} model links")
        except re.error as e:
            logger.error(f"Regex error: {str(e)}")
            return

        if not model_links:
            logger.warning("No models found")
            return

        model_names = [link for link in model_links if link]
        logger.info(f"Processing models: {model_names}")

        for name in model_names:
            try:
                logger.info(f"Fetching tags for {name}...")
                try:
                    tags_response = requests.get(
                        f"https://ollama.com/library/{name}/tags",
                        headers=headers,
                        timeout=10,
                    )
                    logger.info(f"Tags response status for {name}: {tags_response.status_code}")
                except (requests.ConnectionError, requests.Timeout) as e:
                    logger.error(f"Connection error or timeout occurred for {name}: {str(e)}")
                    continue
                except requests.RequestException as e:
                    logger.error(f"An error occurred during the request for {name}: {str(e)}")
                    continue

                if tags_response.status_code == 200:
                    try:
                        tags = re.findall(f'{name}:[^"\\s]*', tags_response.text)
                        filtered_tags = [
                            tag
                            for tag in tags
                            if not any(x in tag for x in ["text", "base", "fp"])
                            and not re.match(r".*q[45]_[01]", tag)
                        ]

                        model_type = (
                            "vision"
                            if "vision" in name
                            else "embedding"
                            if "minilm" in name
                            else "text"
                        )

                        models_data.append(
                            {"name": name, "tags": filtered_tags, "type": model_type}
                        )
                        logger.info(f"Successfully processed {name}")
                    except re.error as e:
                        logger.error(f"Regex error while processing tags for {name}: {str(e)}")
                        continue
                else:
                    logger.warning(f"Failed to get tags for {name}: Status {tags_response.status_code}")
            except Exception as e:
                logger.error(f"Error processing {name}: {str(e)}")
                continue
            # Rate limiting to avoid overwhelming Render or ollama.com
            time.sleep(1)

        logger.info(f"Fetched and stored {len(models_data)} models")
    except Exception as e:
        logger.error(f"Error fetching library models: {str(e)}")
        traceback.print_exc()