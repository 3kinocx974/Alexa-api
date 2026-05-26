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
    USER
