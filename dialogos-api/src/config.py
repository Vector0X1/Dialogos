import os

# Use /tmp for ephemeral storage on Render
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR", "/tmp/data")
CHATGPT_DATA_DIR = os.path.join(BASE_DATA_DIR, "chatgpt")
CLAUDE_DATA_DIR = os.path.join(BASE_DATA_DIR, "claude")
DEEPSEEK_DATA_DIR = os.path.join(BASE_DATA_DIR, "deepseek")

# In-memory message storage
IN_MEMORY_MESSAGES = {
    "chatgpt": [],
    "claude": [],
    "deepseek": []
}

# Models data for /models/library endpoint
models_data = [
    {"name": "gpt-4o-mini",    "provider": "OpenAI",    "type": "generation"},
    {"name": "deepseek-chat",  "provider": "DeepSeek",  "type": "generation"},
    {"name": "claude",         "provider": "Anthropic","type": "generation"},
]
