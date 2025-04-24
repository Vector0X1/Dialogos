from datetime import datetime
import json
import os
from pathlib import Path
import re
import traceback

import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request
from torch import cosine_similarity

from services.embedding import get_embeddings
from services.background_processor import BackgroundProcessor
from services.data_processing import analyze_branches
from utils import load_visualization_data
from config import CLAUDE_DATA_DIR, CHATGPT_DATA_DIR, BASE_DATA_DIR
from services.topic_generation import generate_topic_for_cluster
from shared_data import models_data

api_bp = Blueprint("api", __name__)
background_processor = BackgroundProcessor()

# ---------------------------------------------------------------------------
#  Data‑processing routes
# ---------------------------------------------------------------------------

@api_bp.route("/process", methods=["POST"])
def process_data():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        file = request.files["file"]
        if not file.filename.endswith(".json"):
            return jsonify({"error": "Invalid file type"}), 400
        data_dir = Path("./unprocessed")
        data_dir.mkdir(exist_ok=True)
        file_path = data_dir / "chat_data.json"
        file.save(file_path)
        task_id = background_processor.start_task(str(file_path))
        return jsonify({"task_id": task_id, "message": "Processing started"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/process/status/<task_id>", methods=["GET"])
def check_task_status(task_id):
    status = background_processor.get_task_status(task_id)
    if status:
        return jsonify({
            "status": status.status,
            "progress": status.progress,
            "error": status.error,
            "completed": status.completed,
        })
    return jsonify({"error": "Task not found"}), 404


# ---------------------------------------------------------------------------
#  Reflections / topics / models
# ---------------------------------------------------------------------------

@api_bp.route("/get-reflections", methods=["POST"])
def get_reflections():
    try:
        chat_type = request.args.get("type", "claude")
        data_dir = CLAUDE_DATA_DIR if chat_type == "claude" else CHATGPT_DATA_DIR
        current_context = request.json.get("context", "")
        if not current_context:
            return jsonify({"reflections": []})
        ctx_emb = np.array(get_embeddings([current_context])[0]).flatten()
        refl_file = os.path.join(data_dir, "reflections.json")
        if not os.path.exists(refl_file):
            return jsonify({"reflections": []})
        with open(refl_file, "r") as f:
            refl_data = json.load(f)
        sims = []
        for d in refl_data.values():
            ref_emb = d["embedding"]
            sim = np.dot(ctx_emb, ref_emb) / (
                np.linalg.norm(ctx_emb) * np.linalg.norm(ref_emb)
            )
            sims.append((sim, d["reflection"]))
        sims.sort(reverse=True)
        top = [r for sim, r in sims[:3] if sim > 0.5]
        return jsonify({"reflections": top})
    except Exception as e:
        return jsonify({"reflections": []})


@api_bp.route("/topics", methods=["GET"])
def get_topics():
    try:
        chat_type = request.args.get("type", "claude")
        data_dir = CLAUDE_DATA_DIR if chat_type == "claude" else CHATGPT_DATA_DIR
        with open(os.path.join(data_dir, "topics.json")) as f:
            topics = json.load(f)
        return jsonify(topics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/models/library", methods=["GET"])
def get_library_models():
    if not models_data:
        return jsonify({"error": "Models data not yet loaded"}), 503
    return jsonify({"models": models_data})


@api_bp.route("/models", methods=["GET"])
def get_models():
    return jsonify({
        "generation_model": os.getenv("GENERATION_MODEL", "Not Set"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "Not Set"),
    })


# ---------------------------------------------------------------------------
#  Embeddings & visualisation
# ---------------------------------------------------------------------------

@api_bp.route("/embeddings", methods=["POST"])
def embeddings():
    return jsonify({"embeddings": get_embeddings(request.json.get("texts", []))})


@api_bp.route("/visualization", methods=["GET"])
def get_visualization_data():
    chat_type = request.args.get("type", "claude")
    data_dir = CLAUDE_DATA_DIR if chat_type == "claude" else CHATGPT_DATA_DIR
    try:
        data = load_visualization_data(data_dir)
        if not data["points"]:
            return jsonify([])
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
#  Text generation (ChatGPT / GPT‑4o)
# ---------------------------------------------------------------------------
import openai
from openai import OpenAI
import os
from flask import request, jsonify

@api_bp.route("/generate", methods=["POST"])
def generate_text():
    prompt = request.json.get("prompt", "")
    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400

    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"error": "Missing OPENAI_API_KEY"}), 500

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Dialogos's helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )
        return jsonify({"response": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# ---------------------------------------------------------------------------
#  Blueprint attachment (keep last)
# ---------------------------------------------------------------------------

def register_routes(app):
    app.register_blueprint(api_bp, url_prefix="/api")
