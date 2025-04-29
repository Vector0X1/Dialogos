from src.config import models_data

def detect_chat_type(model_name):
    """Detect the chat type based on the model name."""
    if model_name.startswith("deepseek"):
        return "deepseek"
    return "chatgpt"

def process_messages(messages, chat_type):
    """Process messages for the given chat type."""
    formatted_messages = []
    for msg in messages:
        role = "Human" if msg["role"] == "user" else "Assistant"
        formatted_messages.append(f"{role}: {msg['content']}")
    return "\n".join(formatted_messages)

def validate_message_content(content):
    """Validate message content."""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Message content must be a non-empty string")
    return content.strip()