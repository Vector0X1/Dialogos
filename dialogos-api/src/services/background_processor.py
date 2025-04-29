from src.config import IN_MEMORY_MESSAGES
from src.utils import logger

class BackgroundProcessor:
    def __init__(self):
        self.messages = IN_MEMORY_MESSAGES

    def process_messages(self, chat_type, messages):
        """Store messages with branch metadata in IN_MEMORY_MESSAGES."""
        if chat_type not in self.messages:
            self.messages[chat_type] = []
        self.messages[chat_type].extend(messages)
        logger.info(f"Stored {len(messages)} messages for {chat_type}")