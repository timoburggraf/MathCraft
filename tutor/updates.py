"""Public compatibility service: downloads and health only, no secrets or learner storage."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, jsonify, request, send_file

ROOT = Path(__file__).resolve().parents[1]
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 4096
HOSTS = set(os.environ.get("MC_ALLOWED_HOSTS", "localhost,127.0.0.1").split(","))

@app.before_request
def only_public_downloads():
    if urlsplit(request.host_url).hostname not in HOSTS:
        return jsonify(error="unbekannter Dienstname"), 400
    if request.path not in {"/", "/health", "/version", "/app.apk"} or request.method not in {"GET", "HEAD", "OPTIONS"}:
        return jsonify(error="Private MathCraft-Funktionen ausschließlich über HTTPS:8792"), 403

@app.after_request
def safety_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    origin = request.headers.get("Origin")
    if origin in {"https://localhost", "capacitor://localhost", "null"}:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    return response

@app.get("/health")
def health():
    return jsonify(ok=True, dienst="mathcraft-updates", private_port=8792)

@app.get("/")
def start():
    return "MathCraft: APK unter /app.apk; private Elternseite ausschließlich über HTTPS:8792."

@app.get("/version")
def version():
    file = ROOT / "dist/version.json"
    apk = ROOT / "dist/MathCraft.apk"
    if not file.is_file() or not apk.is_file():
        return jsonify(error="Noch keine APK bereit"), 404
    info = json.loads(file.read_text())
    info.update(size=apk.stat().st_size, apk="/app.apk")
    return jsonify(info)

@app.get("/app.apk")
def download():
    apk = ROOT / "dist/MathCraft.apk"
    if not apk.is_file():
        return jsonify(error="Noch keine APK bereit"), 404
    return send_file(apk, as_attachment=True, download_name="MathCraft.apk",
                     mimetype="application/vnd.android.package-archive")
