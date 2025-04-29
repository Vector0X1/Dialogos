# src/config.py

import os

# Use /tmp for ephemeral storage on Render
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR", "/tmp/data")
CHATGPT_DATA_DIR = os.path.join(BASE_DATA_DIR, "chatgpt")

# In-memory message storage (only ChatGPT now)
IN_MEMORY_MESSAGES = {
    "chatgpt": []
}

# Models data for /models/library endpoint
models_data = [
    # OpenAI
    {"name": "gpt-4o-mini",    "provider": "OpenAI", "type": "generation"},
    {"name": "gpt-4",          "provider": "OpenAI", "type": "generation"},
    {"name": "gpt-3.5-turbo",  "provider": "OpenAI", "type": "generation"},
    # DeepSeek
    {"name": "deepseek-chat",  "provider": "DeepSeek", "type": "generation"},
]
