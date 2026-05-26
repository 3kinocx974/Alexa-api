import os
from flask import Flask, request, jsonify, Response
from flask_ask_sdk.skill_adapter import SkillAdapter
from lambda_function import sb
import requests
from requests.exceptions import RequestException
import music_assistant_alexa_api as maa_api
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from env_secrets import get_env_secret

app = Flask(__name__)

skill_adapter = SkillAdapter(
    skill=sb.create(),
    skill_id="",
    app=app)

ma_app = maa_api.create_app()
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {'/ma': ma_app.wsgi_app})
app.logger.info('Mounted music-assistant-alexa-api app at /ma')


@app.route("/", methods=["POST"])
def invoke_skill():
    return skill_adapter.dispatch_request()


@app.route("/alexa/intents", methods=["POST"])
def alexa_intents_root():
    data = request.get_json(silent=True) or {}
    print("ALEXA_INTENTS received:", data, flush=True)
    command = data.get("command", "").lower()
    player_id = data.get("player_id", "")
    service_map = {
        "stop": "media_player/media_stop",
        "pause": "media_player/media_pause",
        "play": "media_player/media_play",
        "next": "media_player/media_next_track",
        "previous": "media_player/media_previous_track",
    }
    ha_service = service_map.get(command)
    if ha_service and player_id:
        token = get_env_secret("HA_TOKEN") or os.environ.get("SUPERVISOR_TOKEN", "")
        url = "http://172.30.32.1:8123/api/services/" + ha_service
        headers = {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(url, json={"entity_id": player_id}, headers=headers, timeout=5)
            print("HA API: " + ha_service + " -> " + str(r.status_code), flush=True)
        except Exception as e:
            print("HA API error: " + str(e), flush=True)
    return jsonify({"status": "ok"})


@app.route("/status", methods=["GET"])
def status():
    api_user = get_env_secret('API_USERNAME')
    api_pass = get_env_secret('API_PASSWORD')
    skill_html = '<span class="led green"></span> Skill adapter running'
    endpoint = request.host_url.rstrip('/') + '/ma/latest-url'
    try:
        auth = (api_user, api_pass) if api_user and api_pass else None
        resp = requests.get(endpoint, timeout=2, auth=auth)
        if resp.ok:
            api_html = '<span class="led green"></span> API reachable'
        else:
            api_html = '<span class="led red"></span> API error'
    except RequestException as e:
        api_html = '<span class="led red"></span> Error: ' + str(e)
    html = """<!doctype html><html><head><meta charset="utf-8"><title>Status</title>
<style>body{font-family:Arial,sans-serif;padding:20px}.led{display:inline-block;width:14px;height:14px;border-radius:50%;margin-right:8px}.green{background:#2ecc71}.red{background:#e74c3c}.row{margin:8px 0}</style>
</head><body><h1>Service Status</h1>
<div class="row">""" + skill_html + """</div>
<div class="row">""" + api_html + """</div>
</body></html>"""
    return Response(html, status=200, mimetype="text/html")


if __name__ == "__main__":
    port = int(os.environ.get('PORT', '5000'))
    app.run(debug=True, host="0.0.0.0", port=port)
