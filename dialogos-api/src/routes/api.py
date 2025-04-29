from flask import Blueprint, jsonify, request
from src.config import models_data, OPENAI_API_KEY, DEEPSEEK_API_KEY
from src.utils import logger
from src.services.data_processing import detect_chat_type, process_messages, validate_message_content, analyze_branches
from src.services.background_processor import BackgroundProcessor
import requests
import json
import time

api_bp = Blueprint('api', __name__)
processor = BackgroundProcessor()

@api_bp.route('/tags', methods=['GET'])
def get_tags():
    """Return available models."""
    try:
        logger.info("Fetching available models")
        return jsonify(models_data), 200
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}")
        return jsonify({"error": "Failed to fetch models"}), 500

@api_bp.route('/generate', methods=['POST'])
def generate_response():
    """Generate a response using OpenAI or DeepSeek API and store with branch metadata."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No input data provided"}), 400

        model = data.get('model')
        prompt = data.get('prompt')
        chat_type = data.get('chat_type')
        chat_name = data.get('chat_name', 'Default Chat')
        branch_id = data.get('branch_id', '0')
        system_prompt = data.get('system', 'You are Dialogos\'s helpful assistant.')
        options = data.get('options', {})
        parent_message_id = data.get('parent_message_id', None)
        message_id = data.get('message_id', str(hash(prompt + str(time.time()))))

        if not model or not prompt:
            return jsonify({"error": "Model and prompt are required"}), 400

        validated_chat_type = chat_type or detect_chat_type(model)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": validate_message_content(prompt),
                "message_id": message_id,
                "parent_message_id": parent_message_id,
                "branch_id": branch_id,
                "chat_name": chat_name,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                "sender": "human",
                "model": model
            }
        ]

        if validated_chat_type == "chatgpt":
            if not OPENAI_API_KEY:
                return jsonify({"error": "OpenAI API key not configured"}), 500
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            api_url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": options.get('temperature', 0.8),
                "max_tokens": options.get('num_predict', 2048),
                "top_p": options.get('top_p', 0.9)
            }
        elif validated_chat_type == "deepseek":
            if not DEEPSEEK_API_KEY:
                return jsonify({"error": "DeepSeek API key not configured"}), 500
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
            api_url = "https://api.deepseek.com/v1/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": options.get('temperature', 0.8),
                "max_tokens": options.get('num_predict', 2048),
                "top_p": options.get('top_p', 0.9)
            }
        else:
            return jsonify({"error": f"Unsupported chat type: {validated_chat_type}"}), 400

        headers["Content-Type"] = "application/json"
        response = requests.post(api_url, headers=headers, json=payload, stream=True)

        if response.status_code != 200:
            logger.error(f"API request failed: {response.text}")
            return jsonify({"error": "Failed to generate response"}), response.status_code

        def generate():
            accumulated_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data: '):
                            data = decoded_line[6:]
                            if data == '[DONE]':
                                break
                            json_data = json.loads(data)
                            delta = json_data['choices'][0]['delta']
                            content = delta.get('content', '')
                            if content:
                                accumulated_response += content
                                yield f'{{"response": "{content}"}}\n'
                    except Exception as e:
                        logger.error(f"Error processing stream: {str(e)}")
                        continue
            response_message = {
                "role": "assistant",
                "content": accumulated_response,
                "message_id": str(hash(accumulated_response + str(time.time()))),
                "parent_message_id": message_id,
                "branch_id": branch_id,
                "chat_name": chat_name,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                "sender": "assistant",
                "model": model
            }
            processor.process_messages(validated_chat_type, messages + [response_message])

        return generate(), 200, {'Content-Type': 'text/event-stream'}

    except Exception as e:
        logger.error(f"Error in generate_response: {str(e)}")
        return jsonify({"error": str(e)}), 500

@api_bp.route('/branches/<chat_name>', methods=['GET'])
def get_branches(chat_name):
    """Retrieve branch structure for a specific chat."""
    try:
        branches = analyze_branches(processor.messages.get('chatgpt', []) + processor.messages.get('deepseek', []))
        if chat_name in branches:
            return jsonify(branches[chat_name]), 200
        return jsonify({"error": f"Chat {chat_name} not found"}), 404
    except Exception as e:
        logger.error(f"Error fetching branches: {str(e)}")
        return jsonify({"error": str(e)}), 500