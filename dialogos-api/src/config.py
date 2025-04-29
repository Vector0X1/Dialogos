import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

models_data = [
    {"name": "gpt-4o-mini", "provider": "OpenAI", "type": "generation"},
    {"name": "deepseek-chat", "provider": "DeepSeek", "type": "generation"},
]