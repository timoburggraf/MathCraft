# -*- coding: utf-8 -*-
"""Prüft die Update-Kette gegen einen wirklich laufenden Dienst.

Der Weg vom Knopf bis zur neuen APK hat viele Stellen, an denen es klemmen
kann: falsche Adresse, kein WLAN, Dienst aus, gleiche Fassung. Keine davon darf
die App umwerfen — sie muss in jedem Fall verständlich sagen, was los ist.

  .venv/bin/python build/update_test.py
"""
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "index.html"
DIST = ROOT / "dist"
PORT = 8799            # eigener Port, damit ein echter Dienst nebenher laufen darf

RESULTS = []


def add(name, ok, info=""):
    RESULTS.append((name, bool(ok), info))


def frei(port):
    s = socket.socket()
    # Wie die Dienste selbst: sonst meldet ein Socket aus dem letzten Lauf, der
    # noch in TIME-WAIT haengt, den Port faelschlich als belegt.
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def warte_auf_dienst(url, sekunden=15):
    import urllib.request
    for _ in range(sekunden * 5):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(.2)
    return False


def main():
    from playwright.sync_api import sync_playwright
    import urllib.request

    if not frei(PORT):
        sys.exit(f"Port {PORT} ist belegt")

    # --- Testaufbau: eine Fassung, die neuer ist als die gebaute -------------
    DIST.mkdir(exist_ok=True)
    version_datei = DIST / "version.json"
    apk_datei = DIST / "MathCraft.apk"
    sicherung = None
    if version_datei.exists():
        sicherung = version_datei.read_text("utf-8")
    apk_ersatz = not apk_datei.exists()
    if apk_ersatz:
        apk_datei.write_bytes(b"PK\x03\x04 Platzhalter fuer den Test")

    version_datei.write_text(json.dumps({
        "versionCode": 999, "versionName": "9.9",
        "notes": "Neue Knobelaufgaben und ein schnelleres Ziffernfeld.",
        "date": "2026-07-27"}, ensure_ascii=False), "utf-8")

    dienst = subprocess.Popen(
        [sys.executable, str(ROOT / "tutor/server.py"),
         "--port", str(PORT), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        add("Dienst startet", warte_auf_dienst(f"http://127.0.0.1:{PORT}/health"))

        # Der WebView laeuft unter https://localhost, der Dienst spricht http.
        # Ohne allowMixedContent blockt Android jeden Aufruf dorthin — und zwar
        # lautlos. Playwright merkt davon nichts, weil es file:// benutzt.
        cfg = json.loads((ROOT / "capacitor.config.json").read_text("utf-8"))
        schema = (cfg.get("server") or {}).get("androidScheme", "https")
        gemischt = (cfg.get("android") or {}).get("allowMixedContent", False)
        add("Die App darf den Heim-Dienst im WebView überhaupt erreichen",
            schema == "http" or gemischt,
            f"androidScheme={schema}, allowMixedContent={gemischt}")

        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/version", timeout=3) as r:
            info = json.loads(r.read())
        add("Dienst nennt die bereitstehende Fassung",
            info["versionCode"] == 999 and info["size"] > 0, f'Nr. {info["versionCode"]}')

        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/app.apk", timeout=10) as r:
            kopf = r.headers.get("Content-Type", "")
            laenge = int(r.headers.get("Content-Length", 0))
        add("APK wird zum Herunterladen angeboten",
            "android.package-archive" in kopf and laenge > 0, kopf)

        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_context(viewport={"width": 393, "height": 873}).new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            T.ohne_dienst(page)
            page.goto(APP.as_uri())
            page.wait_for_timeout(400)

            # --- Fall 1: Es gibt etwas Neues ---------------------------------
            page.evaluate(f"""async () => {{
              S.server = '127.0.0.1:{PORT}'; MEINE = {{code: 3, name: '1.3'}};
              save(); go('settings'); await checkUpdate();
            }}""")
            page.wait_for_timeout(400)
            gefunden = page.evaluate("() => UPD.info && UPD.info.versionCode")
            add("App erkennt eine neuere Fassung", gefunden == 999, f"gefunden: {gefunden}")
            add("Neuerungen stehen auf dem Bildschirm",
                page.locator("text=Knobelaufgaben").count() > 0)
            add("Der Knopf zum Herunterladen erscheint",
                page.locator("text=Herunterladen").count() > 0)
            add("Der Hinweis auf den Fortschritt fehlt nicht",
                page.locator("text=Fortschritt bleibt erhalten").count() > 0)

            # --- Fall 2: Schon aktuell ---------------------------------------
            page.evaluate("""async () => {
              MEINE = {code: 999, name: '9.9'}; UPD = {stand:'', info:null, laeuft:false};
              await checkUpdate();
            }""")
            page.wait_for_timeout(300)
            add("Bei gleicher Fassung meldet die App Entwarnung",
                "neueste" in page.evaluate("() => UPD.stand"),
                page.evaluate("() => UPD.stand"))
            add("Kein Download-Knopf, wenn nichts neu ist",
                page.locator("text=Herunterladen und aktualisieren").count() == 0)

            # --- Fall 3: Falsche Adresse -------------------------------------
            page.evaluate("""async () => {
              S.server = '10.255.255.1:9'; UPD = {stand:'', info:null, laeuft:false};
              save(); await checkUpdate();
            }""")
            page.wait_for_timeout(7000)     # der Abbruch greift nach 6 Sekunden
            stand = page.evaluate("() => UPD.stand")
            add("Falsche Adresse wird verständlich gemeldet",
                bool(stand) and "WLAN" in stand or "Kontakt" in stand, stand[:60])
            add("Die App läuft danach weiter",
                page.evaluate("() => !!document.querySelector('.card')"))

            # --- Fall 4: Gar keine Adresse -----------------------------------
            page.evaluate("""async () => {
              S.server = ''; UPD = {stand:'', info:null, laeuft:false};
              save(); await checkUpdate();
            }""")
            page.wait_for_timeout(300)
            add("Ohne Adresse kommt eine Aufforderung",
                "Adresse" in page.evaluate("() => UPD.stand"),
                page.evaluate("() => UPD.stand")[:50])

            # --- Fall 5: Eingetragene Adresse überlebt einen Neustart --------
            page.evaluate("""() => { S.server = '192.168.0.99:8790'; save(); }""")
            page.reload()
            page.wait_for_timeout(400)
            add("Eingetragene Adresse bleibt gespeichert",
                page.evaluate("() => S.server") == "192.168.0.99:8790",
                page.evaluate("() => S.server"))

            # --- Fall 6: Beim Öffnen sucht die App von selbst ----------------
            # Die Adresse in den Speicher legen und neu laden: Was danach ohne
            # jeden Tastendruck passiert, ist genau das, was beim Start passiert.
            page.evaluate(f"""() => {{
              const s = JSON.parse(localStorage.getItem('mathcraft_v1') || '{{}}');
              s.v = 1; s.server = '127.0.0.1:{PORT}';
              localStorage.setItem('mathcraft_v1', JSON.stringify(s));
            }}""")
            page.reload()
            page.wait_for_timeout(2500)          # keine Eingabe, nur warten
            selbst = page.evaluate("""() => ({
              gefunden: !!(UPD.info && UPD.info.versionCode),
              code: UPD.info ? UPD.info.versionCode : 0,
              ansicht: view.name,
              knopf: !!document.querySelector('.btn.wide')
            })""")
            add("Beim Öffnen sucht die App ohne Zutun nach einer neuen Fassung",
                selbst["gefunden"], f'gefunden: Nr. {selbst["code"]}')
            add("Sie bleibt dabei auf dem Startbildschirm",
                selbst["ansicht"] == "home", selbst["ansicht"])
            add("Auf dem Startbildschirm steht der Hinweis",
                page.locator("text=ist da").count() > 0)

            # --- Fall 7: Und schweigt, wenn der Rechner aus ist --------------
            page.evaluate("""() => {
              const s = JSON.parse(localStorage.getItem('mathcraft_v1') || '{}');
              s.v = 1; s.server = '10.255.255.1:9';
              localStorage.setItem('mathcraft_v1', JSON.stringify(s));
            }""")
            page.reload()
            page.wait_for_timeout(7000)          # der Abbruch greift nach 6 s
            sichtbar = page.locator("#app").inner_text()
            add("Ist der Rechner aus, bekommt das Kind davon nichts mit",
                not any(w in sichtbar for w in
                        ("Kontakt", "antwortet nicht", "Fehler", "ist da")),
                sichtbar[:60].replace("\n", " "))
            add("Die App läuft trotzdem normal weiter",
                page.evaluate("() => !!document.querySelector('.hero')"))

            add("keine JS-Fehler", not errs, errs[0][:70] if errs else "")
            b.close()
    finally:
        dienst.terminate()
        dienst.wait(timeout=5)
        if sicherung is not None:
            version_datei.write_text(sicherung, "utf-8")
        else:
            version_datei.unlink(missing_ok=True)
        if apk_ersatz:
            apk_datei.unlink(missing_ok=True)

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, info in RESULTS:
        print(f'{"✅" if ok else "❌"} {name}' + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS)-len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
