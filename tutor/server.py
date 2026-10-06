# -*- coding: utf-8 -*-
"""Authentifizierte private MathCraft-Funktionen und öffentliche App-Ressourcen.

Produktionsbetrieb: mathcraft-secure.service unter dedizierter UID mit HTTPS,
minimaler Vault-Projektion und privatem Zustand außerhalb des Projektordners.
Der separate mathcraft-updates.service bietet auf dem alten HTTP-Port lediglich
öffentliche APK/Version/Status. Eltern und Geräte benötigen Authentifizierung.

Die direkte Python-CLI startet nur einen lokalen Entwicklungs-HTTP-Dienst.
Private Routen sind dort absichtlich durch die HTTPS-Prüfung gesperrt.
"""
import argparse
import json
import re
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "build"))     # der Lehrplan liegt beim Bau
import speicher as SP

DIST = ROOT / "dist"
APK = DIST / "MathCraft.apk"
VERSION = DIST / "version.json"

# A: vorproduzierte Vorlese-Stimmen, siehe build/tts_erzeugen.py. Die Kennung
# ist ein 8-stelliger Hex-crc32 über den vorgelesenen Text (dort audio_id(),
# in src/app.html die identische JS-Entsprechung) — inhaltsadressiert, ein
# Clip ändert sich also nie und darf ewig gecacht werden.
AUDIO_DIR = ROOT / "data" / "audio"
_STIMME_RE = re.compile(r"^[a-z]+$")
_CLIP_RE = re.compile(r"^([0-9a-f]{8})\.opus$")

MAX_BODY = 4 * 1024 * 1024      # eine Ladung von 90 Tagen bleibt weit darunter


def lan_ip():
    """Die Adresse, unter der das Handy den Rechner im WLAN erreicht."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.1.1", 1))       # es fließt nichts, nur Routen-Abfrage
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def version_info():
    """Was gerade zum Herunterladen bereitsteht."""
    if not VERSION.exists() or not APK.exists():
        return None
    info = json.loads(VERSION.read_text("utf-8"))
    info["size"] = APK.stat().st_size
    info["apk"] = "/app.apk"
    return info


def build_app(security_config=None):
    from flask import Flask, jsonify, request, send_file, Response, g
    from security import Security, COOKIE, LOGIN_COOKIE
    import html

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY
    if security_config is not None:
        if security_config.get("TESTING") is not True:
            raise RuntimeError("Authentication overrides are only supported for synthetic tests")
        app.config.update(security_config)
    access = Security(app)
    app.extensions["mathcraft_security"] = access

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            token, status = access.login()
            if not token:
                return jsonify(error="Anmeldung abgelehnt; Anmeldeseite neu öffnen"), status
            response = Response(status=303, headers={"Location": "/eltern"})
            response.set_cookie(COOKIE, token, secure=True, httponly=True, samesite="Strict", max_age=8*3600, path="/")
            response.delete_cookie(LOGIN_COOKIE, secure=True, httponly=True, samesite="Strict", path="/")
            return response
        if not access.limit("login-form:" + request.remote_addr, 20, 60):
            return jsonify(error="Bitte kurz warten"), 429
        token = access.login_form()
        response = Response('<!doctype html><html lang="de"><meta charset="utf-8"><title>MathCraft Elternzugang</title>'
                            '<h1>Elternzugang</h1><form method="post" action="/login">'
                            f'<input type="hidden" name="csrf" value="{html.escape(token, quote=True)}">'
                            '<label>Elternpasswort <input type="password" name="password" required autocomplete="current-password"></label>'
                            '<button>Anmelden</button></form></html>', mimetype="text/html")
        response.set_cookie(LOGIN_COOKIE, token, secure=True, httponly=True, samesite="Strict", max_age=600, path="/")
        return response

    @app.post("/logout")
    def logout():
        with access.connect() as db:
            db.execute("DELETE FROM sessions WHERE digest=?", (g.parent_session["digest"],))
        response = Response(status=303, headers={"Location": "/login"})
        response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="Strict", path="/")
        return response

    @app.post("/device/pair-code")
    def pair_code():
        try:
            code = access.pair_code(request.form.get("dev", ""), request.form.get("paid") == "1")
        except ValueError:
            return jsonify(error="Ungültige Gerätekennung"), 400
        return Response('<!doctype html><html lang="de"><meta charset="utf-8"><title>Gerät verbinden</title>'
                        '<h1>Gerät verbinden</h1><p>Diesen einmaligen Code in der App unter Einstellungen eingeben. '
                        'Er gilt fünf Minuten nur für die gewählte Gerätekennung.</p>'
                        f'<p><strong>{code}</strong></p><a href="/eltern">Zurück</a></html>', mimetype="text/html")

    @app.post("/device/revoke")
    def revoke_device():
        dev = request.form.get("dev", "")
        if not SP.DEV_RE.fullmatch(dev):
            return jsonify(error="Ungültige Gerätekennung"), 400
        with access.connect() as db:
            db.execute("DELETE FROM devices WHERE dev=?", (dev,))
            db.execute("DELETE FROM pairings WHERE dev=?", (dev,))
        return Response(status=303, headers={"Location": "/eltern"})

    @app.post("/pair")
    def pair():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or request.content_length is None or request.content_length > 4096:
            return jsonify(error="Ungültige Verbindungsanfrage"), 400
        result, status = access.pair(data)
        return jsonify(result or {"error": "Verbindungs-Code abgelehnt"}), status

    @app.get("/health")
    def health():
        return jsonify(ok=True, dienst="mathcraft")

    @app.post("/sync")
    def sync():
        """Ereignisse vom Handy annehmen, Elternwünsche zurückgeben.

        Der Rumpf wird nach Prüfung der gerätespezifischen Signatur gelesen.
        CORS-Vorabfragen erlauben ausschließlich die freigegebenen App-Herkünfte.
        """
        roh = request.get_data(cache=False)
        if len(roh) > MAX_BODY:
            return jsonify(error="Ladung zu groß"), 413
        try:
            d = json.loads(roh.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return jsonify(error="kein lesbares JSON"), 400
        if not isinstance(d, dict):
            return jsonify(error="kein Objekt"), 400

        dev = d.get("dev")
        if dev != g.device["dev"]:
            return jsonify(error="Dieses Gerät darf nur den eigenen Lernstand übertragen"), 403
        ereignisse = d.get("ev")
        if not isinstance(ereignisse, list):
            ereignisse = []
        # Spielername (Elternwunsch 02.09.2026): ein Sync-Metadatum neben den
        # Ereignissen, kein Ereignisfeld — die Säuberung übernimmt speicher.py.
        try:
            ack, neu = SP.schreibe(dev, ereignisse, d.get("stats"),
                                    int(time.time() * 1000), d.get("name"))
        except ValueError as e:
            return jsonify(error=str(e)), 400

        import lehrer as L
        # Paid generation requires a parent action; authenticated sync never triggers it.

        plan = L.lies_plan() or {}
        return jsonify(ok=True, ack=ack, neu=neu, wishes=SP.wuensche_lesen(),
                       plan=plan.get("plan") or [])

    @app.post("/tutor")
    def tutor():
        """Den Tutor von Hand anstoßen — für die Elternseite und zum Ausprobieren."""
        import lehrer as L
        p, log = L.denk_nach()
        if not p:
            return jsonify(ok=False, grund=" | ".join(log)), 200
        return jsonify(ok=True, entscheidungen=len(p["plan"]), ms=p["ms"])

    @app.get("/zaehlstand")
    def zaehlstand():
        """Die Gegenprobe aus Z1: was die Geräte gezählt haben gegen das, was hier liegt."""
        return jsonify(SP.zaehlstand())

    @app.post("/erklaer")
    def erklaer():
        """Z6: eine geprüfte Erklärung an einem gleichartigen Beispiel.

        Die App schickt nur Paket und Aufgabennummer — den Text schlägt der
        Dienst selbst nach. So verlässt nichts über das Kind das Gerät, und
        der Schlüssel bleibt hier.

        Geantwortet wird strömend, eine JSON-Zeile je Häppchen. Sonst säße das
        Kind sechs Sekunden vor einem leeren Feld; so steht das erste Wort nach
        gut zwei da. Das Beispiel ist zu diesem Zeitpunkt schon nachgerechnet.
        """
        from flask import stream_with_context
        import erklaerer as E
        try:
            d = json.loads(request.get_data(cache=False)[:4096].decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return jsonify(error="kein lesbares JSON"), 400
        if not isinstance(d, dict):
            return jsonify(error="kein Objekt"), 400

        unit = str(d.get("u") or "")[:80]
        try:
            index = int(d.get("i"))
        except (TypeError, ValueError):
            return jsonify(error="keine Aufgabennummer"), 400

        def zeilen():
            # "weg" ist kein Fehler für die App: Sie fällt still auf den festen
            # Tipp zurück. Ein Kind soll keine Fehlermeldung zu sehen bekommen.
            for art, wert in E.erklaere_stream(unit, index):
                yield json.dumps({"t": art, "v": wert}, ensure_ascii=False) + "\n"

        return Response(stream_with_context(zeilen()),
                        mimetype="application/x-ndjson",
                        headers={"Cache-Control": "no-cache",
                                 "X-Accel-Buffering": "no"})

    @app.post("/tutor-jetzt")
    def tutor_jetzt():
        """Der Knopf auf der Elternseite. Danach zurück zur Seite."""
        import lehrer as L
        try:
            L.denk_nach()
        except Exception as e:
            print(f"Tutor gescheitert: {type(e).__name__}")
        return Response(status=303, headers={"Location": "/eltern"})

    @app.get("/eltern")
    def eltern():
        import eltern as E
        page = E.seite(spieler=request.args.get("spieler"))
        token = html.escape(g.parent_session["csrf"], quote=True)
        page = re.sub(r'(<form\b[^>]*method="post"[^>]*>)',
                      lambda m: m.group(1) + f'<input type="hidden" name="csrf" value="{token}">', page)
        page = page.replace('onchange="this.form.submit()"', '')
        page = page.replace('</select>', '</select><button type="submit">Ansicht wählen</button>')
        page = page.replace('</body>', access.parent_panel(g.parent_session["csrf"]) + '</body>')
        if '</body>' not in page:
            page = page.replace('</html>', access.parent_panel(g.parent_session["csrf"]) + '</html>')
        return Response(page, mimetype="text/html")

    @app.post("/wunsch")
    def wunsch():
        """Einen Elternwunsch setzen oder zurücknehmen (Z4).

        Danach zurück auf die Seite statt eine Antwort auszugeben: Sonst
        wiederholt ein Neuladen im Browser die Eingabe.
        """
        import curriculum as C
        ziel = (request.form.get("ziel") or "").strip()
        kennung = (request.form.get("id") or "").strip()
        art = (request.form.get("art") or "").strip()

        bekannt = ({s["id"] for s in C.SKILLS} if ziel == "skill"
                   else {a["id"] for a in C.AREAS} if ziel == "bereich" else set())
        if kennung not in bekannt:
            return jsonify(error="unbekanntes Ziel"), 400

        try:
            if art == "weg":
                SP.wunsch_loeschen(ziel, kennung)
            else:
                SP.wunsch_setzen(ziel, kennung, art, int(time.time() * 1000))
        except ValueError as e:
            return jsonify(error=str(e)), 400
        return Response(status=303, headers={"Location": "/eltern"})

    @app.post("/geraet")
    def geraet():
        """Ein Gerät aus der Auswertung nehmen oder wieder hereinholen.

        Gelöscht wird dabei nichts — ein Testlauf soll die Zahlen des Kindes
        nicht verfälschen, aber wer sich vertut, soll ihn zurückholen können.
        """
        dev = (request.form.get("dev") or "").strip()
        art = (request.form.get("art") or "").strip()
        if art not in ("aus", "ein"):
            return jsonify(error="unbekannte Anweisung"), 400
        try:
            SP.ignoriert_setzen(dev, art == "aus")
        except ValueError as e:
            return jsonify(error=str(e)), 400
        return Response(status=303, headers={"Location": "/eltern#technik"})

    @app.get("/version")
    def version():
        info = version_info()
        if not info:
            return jsonify(error="noch keine APK gebaut"), 404
        return jsonify(info)

    @app.get("/audio/<stimme>/<datei>")
    def audio(stimme, datei):
        """Eine vorproduzierte Vorlese-Aufnahme (A, siehe build/tts_erzeugen.py).

        Nur [a-z]+ als Stimme und ein 8-stelliger Hex-Wert als Kennung sind
        gültig — alles andere (insbesondere ein Pfadangriff über "..") wird
        abgewiesen, bevor daraus ein Dateipfad gebaut wird.
        """
        if not _STIMME_RE.match(stimme):
            return jsonify(error="unbekannte Stimme"), 400
        m = _CLIP_RE.match(datei)
        if not m:
            return jsonify(error="unbekannte Kennung"), 400
        pfad = AUDIO_DIR / stimme / f"{m.group(1)}.opus"
        if not pfad.is_file():
            return jsonify(error="kein Klang vorhanden"), 404
        resp = send_file(pfad, mimetype="audio/ogg")
        # Inhaltsadressiert: derselbe Text ergibt immer dieselbe Kennung und
        # denselben Klang — der Browser darf ihn für immer behalten.
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    @app.get("/app.apk")
    def apk():
        if not APK.exists():
            return jsonify(error="keine APK vorhanden"), 404
        # as_attachment sorgt dafür, dass Android die Datei herunterlädt und
        # anschließend zum Installieren anbietet, statt sie anzuzeigen.
        return send_file(APK, as_attachment=True, download_name="MathCraft.apk",
                         mimetype="application/vnd.android.package-archive")

    @app.get("/")
    def start():
        info = version_info()
        stand = (f"<p>Bereit: <b>Version {html.escape(str(info['versionName']))}</b> "
                 f"(Code {info['versionCode']}, {info['size']/1024/1024:.1f} MB)</p>"
                 f"<p>{html.escape(str(info.get('notes','')))}</p>") if info else \
                "<p>Noch keine APK gebaut — <code>build/android.sh</code> laufen lassen.</p>"
        return Response(f"""<!doctype html><html lang=de><meta charset=utf-8>
          <title>MathCraft-Dienst</title>
          <style>body{{font-family:system-ui;background:#0b1020;color:#eef3ff;
            max-width:34rem;margin:3rem auto;padding:0 1rem;line-height:1.5}}
            a{{color:#25d0c0}} code{{background:#1b2340;padding:.1rem .3rem;border-radius:.2rem}}</style>
          <h1>MathCraft</h1>{stand}
          <p><a href="/app.apk">MathCraft.apk herunterladen</a></p>
          <p><a href="/eltern">Zur Elternseite</a> — was das Kind geübt hat, was sitzt
          und was hakt.</p>
          <p style="color:#94a6c8;font-size:.9rem">Dieser Dienst läuft nur im
          Heimnetz. In der App: Einstellungen ▸ Update.</p>""", mimetype="text/html")

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()

    info = version_info()
    print(f"MathCraft Entwicklungs-HTTP auf http://{a.host}:{a.port}")
    print(f"  Bereit: Version {info['versionName']} (Code {info['versionCode']})"
          if info else "  Noch keine APK gebaut.")
    print("  Private Funktionen nur über den HTTPS-Produktionsdienst auf Port 8792.")

    try:
        from flask import Flask  # noqa: F401
    except ImportError:
        sys.exit("Flask fehlt:  .venv/bin/pip install flask")

    build_app().run(host=a.host, port=a.port, threaded=True)


if __name__ == "__main__":
    main()
