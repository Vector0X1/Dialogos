# src/config.py
import os

# Base directory for data storage
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR", "/opt/render/project/data")
CHATGPT_DATA_DIR = os.path.join(BASE_DATA_DIR, "chatgpt")
CLAUDE_DATA_DIR = os.path.join(BASE_DATA_DIR, "claude")

# In-memory message storage
IN_MEMORY_MESSAGES = {"chatgpt": [], "claude": []}

# Placeholder for models data (used in api.py)
models_data = [
    {"name": "chatgpt", "type": "generation"},
    {"name": "claude", "type": "generation"}
]