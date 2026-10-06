"""Parent sessions and narrowly scoped, paired device requests. Never log credentials."""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
from urllib.parse import urlsplit

from flask import g, jsonify, request

COOKIE = "__Host-mathcraft_parent"
LOGIN_COOKIE = "__Host-mathcraft_login"
DEVICE = re.compile(r"[0-9a-f]{8,32}\Z")
NONCE = re.compile(r"[0-9a-f]{32}\Z")
PARENT_ROUTES = {"/eltern", "/zaehlstand", "/wunsch", "/geraet", "/tutor", "/tutor-jetzt",
                 "/logout", "/device/pair-code", "/device/revoke"}
DEVICE_ROUTES = {"/sync", "/erklaer", "/pair"}
PUBLIC_ROUTES = {"/", "/health", "/version", "/app.apk", "/login"}


class Security:
    def __init__(self, app):
        from _project_vault import get_secret
        def credential(name):
            value = app.config.get(name) if app.testing else get_secret(name)
            if not isinstance(value, str) or len(value) < 24 or value.startswith("USE_VAULT"):
                raise RuntimeError("Required MathCraft authentication credential unavailable")
            return value
        self.password = credential("MATHCRAFT_PARENT_PASSWORD")
        self.session_key = credential("MATHCRAFT_SESSION_KEY").encode()
        self.device_key = credential("MATHCRAFT_DEVICE_KEY").encode()
        self.clock = app.config.get("MC_TEST_CLOCK", time.time) if app.testing else time.time
        self.home = Path(app.config.get("MC_STATE_HOME") or os.environ.get("MC_STATE_HOME")
                         or Path.home() / ".local/share/mathcraft/private")
        self.home.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.home.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError("Unsafe MathCraft private state directory")
        self.db = self.home / "access.sqlite3"
        if self.db.exists() or self.db.is_symlink():
            info = self.db.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise RuntimeError("Unsafe MathCraft authentication state")
        else:
            fd = os.open(self.db, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        with self.connect() as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, csrf TEXT, expires INTEGER);
              CREATE TABLE IF NOT EXISTS login_forms (digest TEXT PRIMARY KEY, expires INTEGER);
              CREATE TABLE IF NOT EXISTS devices (dev TEXT PRIMARY KEY, generation TEXT, paid INTEGER, expires INTEGER);
              CREATE TABLE IF NOT EXISTS pairings (digest TEXT PRIMARY KEY, dev TEXT, paid INTEGER, expires INTEGER);
              CREATE TABLE IF NOT EXISTS nonces (dev TEXT, nonce TEXT, expires INTEGER, PRIMARY KEY(dev,nonce));
              CREATE TABLE IF NOT EXISTS limits (bucket TEXT PRIMARY KEY, count INTEGER, expires INTEGER);
            """)
        hosts = app.config.get("MC_ALLOWED_HOSTS") or os.environ.get("MC_ALLOWED_HOSTS", "localhost,127.0.0.1")
        self.hosts = set(hosts.split(",")) if isinstance(hosts, str) else set(hosts)
        app.before_request(self.authorize)
        app.after_request(self.headers)

    def connect(self):
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def digest(self, value, purpose):
        return hmac.new(self.session_key, (purpose + "\n" + value).encode(), hashlib.sha256).hexdigest()

    def limit(self, bucket, maximum, interval):
        now = int(self.clock())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT count,expires FROM limits WHERE bucket=?", (bucket,)).fetchone()
            count = row["count"] if row and row["expires"] > now else 0
            if count >= maximum:
                return False
            expiry = row["expires"] if row and row["expires"] > now else now + interval
            db.execute("INSERT OR REPLACE INTO limits VALUES (?,?,?)", (bucket, count + 1, expiry))
            db.execute("DELETE FROM limits WHERE expires<?", (now - 86400,))
        return True

    def parent_session(self):
        token = request.cookies.get(COOKIE, "")
        if not token or len(token) > 128:
            return None
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE digest=? AND expires>?",
                             (self.digest(token, "session"), int(self.clock()))).fetchone()
        return dict(row) if row else None

    def csrf(self, session):
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            return False
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf", "")
        if not hmac.compare_digest(str(supplied).encode(), session["csrf"].encode()):
            return False
        # Each rendered form token can mutate state once. The redirect renders a new token.
        with self.connect() as db:
            changed = db.execute("UPDATE sessions SET csrf=? WHERE digest=? AND csrf=?",
                                 (secrets.token_urlsafe(24), session["digest"], session["csrf"])).rowcount
        return bool(changed)

    def authorize(self):
        host = urlsplit(request.host_url).hostname
        if host not in self.hosts:
            return jsonify(error="unbekannter Dienstname"), 400
        known = PUBLIC_ROUTES | PARENT_ROUTES | DEVICE_ROUTES
        if request.path not in known and not request.path.startswith("/audio/"):
            return jsonify(error="unbekannter Pfad"), 404
        if request.path not in PUBLIC_ROUTES and not request.path.startswith("/audio/") and not request.is_secure:
            return jsonify(error="HTTPS für private Daten erforderlich"), 426
        if request.path == "/login" and not request.is_secure:
            return jsonify(error="Anmeldung ausschließlich über HTTPS"), 426
        if request.path in PARENT_ROUTES:
            session = self.parent_session()
            if not session:
                return jsonify(error="Elternanmeldung erforderlich", login="/login"), 401
            g.parent_session = session
            if request.method not in ("GET", "HEAD") and not self.csrf(session):
                return jsonify(error="Formular abgelaufen; Seite neu öffnen"), 403
            if request.path in {"/tutor", "/tutor-jetzt"} and not self.limit("parent-tutor", 3, 3600):
                return jsonify(error="Tutor-Limit erreicht"), 429
        if request.path in DEVICE_ROUTES:
            origin = request.headers.get("Origin")
            allowed = {"https://localhost", "capacitor://localhost", "null", request.host_url.rstrip("/")}
            if origin and origin not in allowed:
                return jsonify(error="Herkunft nicht freigegeben"), 403
            if request.method == "OPTIONS":
                return "", 204
            if request.path == "/pair":
                return None
            return self.authorize_device()

    def device_secret(self, dev, generation):
        return hmac.new(self.device_key, ("mathcraft-device-v1\n" + dev + "\n" + generation).encode(),
                        hashlib.sha256).hexdigest()

    def authorize_device(self):
        dev = request.headers.get("X-MC-Device", "")
        nonce = request.headers.get("X-MC-Nonce", "")
        stamp = request.headers.get("X-MC-Time", "")
        signature = request.headers.get("X-MC-Signature", "")
        if not DEVICE.fullmatch(dev) or not NONCE.fullmatch(nonce) or not re.fullmatch(r"[0-9]{10}", stamp):
            return jsonify(error="Gerät zuerst durch Eltern verbinden"), 401
        now = int(self.clock())
        if abs(now - int(stamp)) > 300 or not re.fullmatch(r"[0-9a-f]{64}", signature):
            return jsonify(error="Geräteanmeldung abgelaufen"), 401
        with self.connect() as db:
            device = db.execute("SELECT * FROM devices WHERE dev=? AND expires>?", (dev, now)).fetchone()
        if not device:
            return jsonify(error="Gerät nicht freigegeben"), 401
        body = request.get_data(cache=True)
        try:
            target = request.path + ("?" + request.query_string.decode("ascii") if request.query_string else "")
        except UnicodeError:
            return jsonify(error="Ungültiger Anfragepfad"), 400
        canonical = "\n".join((request.method, target, stamp, nonce, hashlib.sha256(body).hexdigest()))
        expected = hmac.new(self.device_secret(dev, device["generation"]).encode(), canonical.encode(),
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return jsonify(error="Geräteanmeldung ungültig"), 401
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            still_allowed = db.execute("SELECT 1 FROM devices WHERE dev=? AND generation=? AND expires>?",
                                       (dev, device["generation"], now)).fetchone()
            if not still_allowed:
                return jsonify(error="Gerätefreigabe geändert"), 401
            db.execute("DELETE FROM nonces WHERE expires<?", (now,))
            try:
                db.execute("INSERT INTO nonces VALUES (?,?,?)", (dev, nonce, now + 610))
            except sqlite3.IntegrityError:
                return jsonify(error="Anfrage bereits verwendet"), 409
        if request.path == "/erklaer":
            if not device["paid"]:
                return jsonify(error="KI-Erklärungen nicht durch Eltern freigegeben"), 403
            if not self.limit("explain-day:" + dev, 10, 86400) or not self.limit("explain-minute:" + dev, 3, 60):
                return jsonify(error="Erklärungs-Limit erreicht"), 429
        if not self.limit("device-minute:" + dev, 30, 60):
            return jsonify(error="Geräte-Limit erreicht"), 429
        g.device = dict(device)
        return None

    def login_form(self):
        token = secrets.token_urlsafe(24)
        with self.connect() as db:
            now = int(self.clock())
            db.execute("DELETE FROM login_forms WHERE expires<?", (now,))
            db.execute("INSERT INTO login_forms VALUES (?,?)", (self.digest(token, "login"), now + 600))
        return token

    def login(self):
        if not self.limit("login-ip:" + request.remote_addr, 5, 900) or not self.limit("login-global", 30, 900):
            return None, 429
        origin = request.headers.get("Origin")
        token = request.cookies.get(LOGIN_COOKIE, "")
        posted = request.form.get("csrf", "")
        if origin and origin != request.host_url.rstrip("/"):
            return None, 403
        if not token or len(token) > 128 or not hmac.compare_digest(token.encode(), posted.encode()):
            return None, 403
        with self.connect() as db:
            consumed = db.execute("DELETE FROM login_forms WHERE digest=? AND expires>?",
                                  (self.digest(token, "login"), int(self.clock()))).rowcount
        if not consumed:
            return None, 403
        password = request.form.get("password", "")
        if not hmac.compare_digest(password.encode(), self.password.encode()):
            return None, 401
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            now = int(self.clock())
            db.execute("DELETE FROM sessions WHERE expires<?", (now,))
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (self.digest(token, "session"),
                       secrets.token_urlsafe(24), now + 8 * 3600))
        return token, 200

    def pair_code(self, dev, paid=False):
        if not DEVICE.fullmatch(dev):
            raise ValueError("Gerätekennung muss aus 8–32 Hex-Zeichen bestehen")
        code = base64.b32encode(secrets.token_bytes(10)).decode()
        with self.connect() as db:
            db.execute("DELETE FROM pairings WHERE dev=? OR expires<?", (dev, int(self.clock())))
            db.execute("INSERT INTO pairings VALUES (?,?,?,?)", (self.digest(code, "pair"), dev,
                       int(paid), int(self.clock()) + 300))
        return code

    def pair(self, data):
        if not self.limit("pair-ip:" + request.remote_addr, 10, 300) or not self.limit("pair-global", 30, 300):
            return None, 429
        dev, code = data.get("dev"), data.get("code")
        if not isinstance(dev, str) or not DEVICE.fullmatch(dev) or not isinstance(code, str) or len(code) > 64:
            return None, 400
        code = code.replace(" ", "").upper()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = int(self.clock())
            row = db.execute("SELECT * FROM pairings WHERE digest=? AND dev=? AND expires>?",
                             (self.digest(code, "pair"), dev, now)).fetchone()
            if not row:
                return None, 401
            db.execute("DELETE FROM pairings WHERE digest=?", (row["digest"],))
            generation = secrets.token_urlsafe(24)
            db.execute("INSERT OR REPLACE INTO devices VALUES (?,?,?,?)", (dev, generation, row["paid"], now + 365 * 86400))
        return {"ok": True, "dev": dev, "key": self.device_secret(dev, generation),
                "expires": now + 365 * 86400}, 200

    def parent_panel(self, csrf):
        with self.connect() as db:
            rows = db.execute("SELECT dev,paid,expires FROM devices ORDER BY dev").fetchall()
        token = html.escape(csrf, quote=True)
        entries = "".join(f'<li>{row["dev"]} — KI-Erklärungen: {"ja" if row["paid"] else "nein"}'
                          f'<form method="post" action="/device/revoke"><input type="hidden" name="csrf" value="{token}">'
                          f'<input type="hidden" name="dev" value="{row["dev"]}"><button>Freigabe sperren</button></form></li>' for row in rows)
        return ('<section class="card"><h2>Sicherer Zugang</h2><p>Gerätekennung in der App unter Einstellungen ablesen. '
                'Der Verbindungs-Code gilt fünf Minuten und nur für dieses Gerät.</p>'
                f'<form method="post" action="/device/pair-code"><input type="hidden" name="csrf" value="{token}">'
                '<input name="dev" required pattern="[0-9a-f]{8,32}" placeholder="Gerätekennung">'
                '<label><input type="checkbox" name="paid" value="1"> KI-Erklärungen erlauben (höchstens 10/Tag)</label>'
                '<button>Verbindungs-Code erstellen</button></form>'
                f'<ul>{entries}</ul><form method="post" action="/logout"><input type="hidden" name="csrf" value="{token}">'
                '<button>Abmelden</button></form></section>')

    def headers(self, response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=86400"
        if request.path in PARENT_ROUTES | DEVICE_ROUTES | {"/login"}:
            response.headers["Cache-Control"] = "no-store"
        if request.path in PARENT_ROUTES | {"/login", "/pair"}:
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        if request.path in DEVICE_ROUTES | {"/health", "/version", "/app.apk"} or request.path.startswith("/audio/"):
            origin = request.headers.get("Origin")
            if origin in {"https://localhost", "capacitor://localhost", "null", request.host_url.rstrip("/")}:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Vary"] = "Origin"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-MC-Device, X-MC-Time, X-MC-Nonce, X-MC-Signature"
        return response
