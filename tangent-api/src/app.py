from flask import Flask, request, jsonify
from flask_cors import CORS
from routes.api import api_bp
from utils import ensure_directories
from services.background_tasks import start_background_tasks
import os
import logging

# Set up logging for Render debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Restrict CORS to specific origins for security
CORS(app, resources={r"/api/*": {"origins": ["https://open-lac-six.vercel.app", "http://localhost:3000"]}})

app.register_blueprint(api_bp, url_prefix="/api")

# Health check endpoint to keep Render service alive
@app.route("/health")
def health():
    logger.info("Health check requested")
    return jsonify({"status": "OK"}), 200

@app.before_request
def before_request():
    if request.method == "OPTIONS":
        logger.info("Handling OPTIONS preflight request")
        response = jsonify({"status": "OK"})
        response.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin"))
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
        response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        return response, 200
    logger.info(f"Incoming request: {request.path} {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")

@app.after_request
def after_request(response):
    origin = request.headers.get("Origin")
    if origin in ["https://open-lac-six.vercel.app", "http://localhost:3000"]:
        response.headers.add("Access-Control-Allow-Origin", origin)
    logger.info(f"Outgoing response: {response.status_code}")
    logger.info(f"Headers: {dict(response.headers)}")
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    response = jsonify({"error": "Internal server error"})
    response.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin"))
    return response, 500

if __name__ == "__main__":
    try:
        logger.info("Starting application...")
        ensure_directories()
        start_background_tasks()
        port = int(os.environ.get("PORT", 5001))
        if os.environ.get("RENDER"):
            logger.info("Running on Render with gunicorn")
            import gunicorn.app.base

            class StandaloneApplication(gunicorn.app.base.BaseApplication):
                def __init__(self, app, options=None):
                    self.options = options or {}
                    self.application = app
                    super().__init__()

                def load_config(self):
                    config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
                    for key, value in config.items():
                        self.cfg.set(key.lower(), value)

                def load(self):
                    return self.application

            options = {
                "bind": f"0.0.0.0:{port}",
                "workers": 1,  # Single worker for free tier
                "worker_class": "sync",
                "timeout": 120,  # Increased for slow API calls
            }
            StandaloneApplication(app, options).run()
        else:
            logger.info("Running in development mode")
            app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}")
        raise