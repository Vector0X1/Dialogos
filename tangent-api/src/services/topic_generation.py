import os
import time
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
GENERATION_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def generate_topic_for_cluster(messages):
    """Generate a topic label for a cluster of chat conversation messages"""
    # Concatenate messages with a separator
    messages_text = "\n- ".join(messages)
    prompt = f"""You are a technical topic analyzer. Review the following chat conversation messages and provide a single concise topic label (2-4 words) that best describes their common theme.

Conversation messages:
- {messages_text}

Provide ONLY the topic label, nothing else. Examples:
"Network Security Tools"
"UI Animation Design"
"Data Visualization"
"API Integration"
"""
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=GENERATION_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            topic = response.choices[0].message.content.strip()
            return topic if topic else "Miscellaneous"
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            print(f"Error generating topic: {str(e)}")
            return "Error"
    return "Error"