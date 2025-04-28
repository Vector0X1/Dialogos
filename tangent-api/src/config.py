# src/config.py
import os

# Use /tmp for ephemeral storage on Render
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR", "/tmp/data")
CHATGPT_DATA_DIR = os.path.join(BASE_DATA_DIR, "chatgpt")
CLAUDE_DATA_DIR = os.path.join(BASE_DATA_DIR, "claude")

# In-memory message storage
IN_MEMORY_MESSAGES = {"chatgpt": [], "claude": []}

# Models data for /models/library endpoint
models_data = [
    {"name": "chatgpt", "type": "generation"},
    {"name": "claude", "type": "generation"}
]