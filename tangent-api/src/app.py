from flask import Flask, request
from flask_cors import CORS
from routes.api import api_bp
from utils import ensure_directories
from services.background_tasks import start_background_tasks
import os

app = Flask(__name__)
CORS(app)

app.register_blueprint(api_bp, url_prefix="/api")

@app.before_request
def before_request():
    print("Incoming request:")
    print(f"Path: {request.path}")
    print(f"Method: {request.method}")
    print(f"Headers: {dict(request.headers)}")

@app.after_request
def after_request(response):
    print("Outgoing response:")
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    return response

if __name__ == "__main__":
    ensure_directories()
    start_background_tasks()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
