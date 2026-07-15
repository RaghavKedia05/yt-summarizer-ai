import logging
import os

from flask import Flask, jsonify, request, send_from_directory

from summarizer import process_video


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

    @app.get("/")
    def index():
        return send_from_directory(app.root_path, "index.html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "summarizer": "local-extractive"})

    @app.post("/summarize")
    def summarize():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get("url"), str):
            return jsonify({"error": "Provide a YouTube URL in the request body."}), 400

        url = data["url"].strip()
        if not url:
            return jsonify({"error": "YouTube URL cannot be empty."}), 400

        try:
            return jsonify(process_video(url))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 422
        except Exception:
            app.logger.exception("Unexpected error while summarizing a video")
            return jsonify({"error": "The video could not be summarized. Please try again."}), 500

    return app


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
