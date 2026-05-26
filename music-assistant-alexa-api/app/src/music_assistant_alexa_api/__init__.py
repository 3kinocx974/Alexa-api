"""Vendored Python implementation of music-assistant-alexa-api.
This implements the small HTTP API used by the Alexa skill and the
Music Assistant push mechanism. It mirrors the behavior of the
original `server.js`: optional basic auth, a POST endpoint to push
stream metadata and a GET endpoint to return the latest pushed URL.
Routes provided:
- GET  /latest-url         : simple status URL (kept for compatibility)
- POST /ma/push-url        : accept JSON payload with stream metadata
- GET  /ma/latest-url      : return last pushed stream metadata
- GET  /favicon.ico        : serve package favicon if present
- POST /alexa/intents      : receive commands from Music Assistant and forward to HA
"""
import json
import os
import requests as req
from env_secrets import get_env_secret
from flask import Blueprint, Flask, Response, jsonify, request, send_file

STORE_NAME = "/tmp/ma_alexa_api_store.json"


def _unauthorized():
    resp = Response("Access denied", 401)
    resp.headers["WWW-Authenticate"] = 'Basic realm="music-assistant-alexa-api"'
    return resp


def call_ha_service(service, entity_id):
    """Call the Home Assistant API to execute a media player command."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    url = f"http://supervisor/core/api/services/{service}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        r = req.post(url, json={"entity_id": entity_id}, headers=headers, timeout=5)
        print(f"HA API: {service} -> {r.status_code}", flush=True)
    except Exception as e:
        print(f"HA API error: {e}", flush=True)


def create_blueprint():
    bp = Blueprint("music_assistant_alexa_api", __name__)

    # Optional basic auth if USERNAME and PASSWORD are provided.
    USERNAME = get_env_secret("API_USERNAME")
    PASSWORD = get_env_secret("API_PASSWORD")

    if USERNAME is not None and PASSWORD is not None:
        @bp.before_request
        def _check_basic_auth():
            auth = request.authorization
            if not auth or auth.username != USERNAME or auth.password != PASSWORD:
                return _unauthorized()

    @bp.route("/favicon.ico", methods=["GET"])
    def favicon():
        pkg_root = os.path.dirname(__file__)
        fav_path = os.path.join(pkg_root, "favicon.ico")
        if os.path.exists(fav_path):
            return send_file(fav_path)
        return ("", 204)

    @bp.route("/push-url", methods=["POST"])
    def push_url():
        """Accept JSON with streamUrl and optional metadata and store it."""
        data = request.get_json(silent=True) or {}
        stream_url = data.get("streamUrl")
        if not stream_url:
            return jsonify({"error": "Missing required fields"}), 400
        _store = {
            "streamUrl": stream_url,
            "title": data.get("title"),
            "artist": data.get("artist"),
            "album": data.get("album"),
            "imageUrl": data.get("imageUrl"),
        }
        print("Received:", _store)
        with open(STORE_NAME, "w", encoding="utf-8") as f:
            json.dump(_store, f)
        return jsonify({"status": "ok"})

    @bp.route("/latest-url", methods=["GET"])
    def latest_url_ma():
        """Return the last pushed stream metadata for the Alexa skill."""
        if os.path.exists(STORE_NAME):
            with open(STORE_NAME, "r", encoding="utf-8") as f:
                _store = json.load(f)
                if "streamUrl" in _store:
                    return jsonify(_store)
        return jsonify(
            {
                "error": "No URL available, please check if Music Assistant has pushed a URL to the API"
            }
        ), 404

    @bp.route("/alexa/intents", methods=["POST"])
    def alexa_intents():
        """Receive commands from Music Assistant and forward to Home Assistant."""
        data = request.get_json(silent=True) or {}
        print("ALEXA_INTENTS received:", data, flush=True)

        command = data.get("command", "").lower()
        player_id = data.get("player_id", "")

        service_map = {
            "stop":     "media_player/media_stop",
            "pause":    "media_player/media_pause",
            "play":     "media_player/media_play",
            "next":     "media_player/media_next_track",
            "previous": "media_player/media_previous_track",
        }

        ha_service = service_map.get(command)
        if ha_service and player_id:
            call_ha_service(ha_service, player_id)

        return jsonify({"status": "ok"})

    return bp


def create_app():
    app = Flask("music_assistant_alexa_api")
    app.register_blueprint(create_blueprint(), url_prefix="")
    return app
