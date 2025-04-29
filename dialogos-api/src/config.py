import os

# Use /tmp for ephemeral storage on Render
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR", "/tmp/data")
CHATGPT_DATA_DIR = os.path.join(BASE_DATA_DIR, "chatgpt")
DEEPSEEK_DATA_DIR = os.path.join(BASE_DATA_DIR, "deepseek")

# In-memory message storage
IN_MEMORY_MESSAGES = {"chatgpt": [], "deepseek": []}

# Models data for /tags endpoint
models_data = [
    {"name": "gpt-4o-mini", "provider": "OpenAI", "type": "generation"},
    {"name": "deepseek-chat", "provider": "DeepSeek", "type": "generation"},
]