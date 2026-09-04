# -*- coding: utf-8 -*-
"""Prüft Auftrag A (vorproduzierte Vorlese-Stimmen) und Auftrag B (der
"Gib mir was Schwereres"-Knopf).

  .venv/bin/python build/tts_test.py

Geprüft wird:
  1. Python- und JS-Bildung der Audio-ID sind für dieselben Texte identisch
     (crc32 über die normalisierte Kette) — die JS-Seite läuft dabei echt im
     Browser gegen die gebaute index.html, nicht nachgebaut.
  2. Die /audio-Route liefert eine hingelegte Testdatei mit korrektem
     Content-Type und Cache-Header aus und weist ungültige Pfade ab.
  3. speak() versucht bei gewählter Stimme die richtige URL und fällt bei
     einem Abspielfehler auf die Systemstimme (speechSynthesis) zurück.
  4. waehleUnit(true) liefert ein anderes Paket als waehleUnit(false), wenn
     ein "jetzt"-Wunsch zufällig genau das Paket trifft, das der Normal-Pfad
     ohnehin gewählt hätte — außer es gäbe gar kein anderes Paket mehr.
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T
import tts_erzeugen as TTS

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "index.html"
PORT = 8799            # eigener Port, damit der echte Dienst weiterlaufen darf

RESULTS = []


def add(name, ok, info=""):
    RESULTS.append((name, bool(ok), info))


def frei(port):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def warte_auf_dienst(url, sekunden=15):
    for _ in range(sekunden * 5):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(.2)
    return False


def status_von(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


# 20 Beispieltexte für die Audio-ID, mit Umlauten, ß, Satzzeichen und
# Whitespace-Eigenheiten (führend/nachgestellt, mehrfach, Tab, Zeilenumbruch) —
# genau das, was normalisiere()/normalisiereVorlesetext() auffangen muss.
BEISPIELTEXTE = [
    "Hallo Welt",
    "Wie viele Äpfel sind das?",
    "Straße",
    "Grüße von Fuchs Kiko!",
    "  führende und   mehrere Leerzeichen  ",
    "\tTabulator\tim Text\t",
    "Zeilen\numbruch\nim Text",
    "Zwölf mal drei ist sechsunddreißig.",
    "Über den Wolken ist die Freiheit grenzenlos.",
    "ß ist ein scharfes S.",
    "Fünf plus sieben ist zwölf.",
    "Ähnlichkeiten prüfen: äöüÄÖÜß",
    "Was ist 7 + 5?",
    "100 % richtig!",
    "Ordne: 3, 8, 11, 15, 20",
    "Käse, Brötchen & Marmelade",
    "Straßenbahnhaltestelle",
    "Fußball spielen macht Spaß",
    "   ",
    "Grün, Gelb, Blau — welche Farbe magst du?",
]


def teste_im_browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 393, "height": 873}).new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        T.ohne_dienst(page)
        page.goto(APP.as_uri())
        page.wait_for_timeout(300)
        if page.locator("#spielerNameFeld").count():
            page.click("button:has-text('Später')")
            page.wait_for_timeout(100)
        if page.locator(".gef-vorschlag").count():
            page.locator(".gef-vorschlag").first.click()
            page.wait_for_timeout(100)

        # -------------------------------------------------- (1) Audio-ID
        for text in BEISPIELTEXTE:
            js_id = page.evaluate("t => audioId(t)", text)
            py_id = TTS.audio_id(text)
            add(f"Audio-ID Python==JS: {text!r}", js_id == py_id, f"js={js_id} py={py_id}")

        # ------------------------------------------ (3) speak() mit Stimme
        erg = page.evaluate("""() => {
          S.server = '127.0.0.1:9';           // wird nie wirklich angefragt (fetch gestubbt)
          S.settings.stimme = 'puck';
          S.settings.speech = true;
          window.__url = null;
          window.__systemText = null;
          window.speechSynthesis.speak = (u) => { window.__systemText = u.text; };
          // speak() holt den Clip seit dem WebView-Befund vom 03.09.2026 per
          // fetch (Blob-Abspielweg) — abgefangen wird deshalb fetch, nicht Audio.
          window.fetch = (url) => {
            window.__url = String(url);
            return Promise.reject(new Error('kein Netz im Test'));
          };
          speak('Testsatz für Puck');
          return true;
        }""")
        page.wait_for_timeout(200)
        gemessen = page.evaluate("() => ({url: window.__url, text: window.__systemText})")
        erwartete_id = TTS.audio_id("Testsatz für Puck")
        erwartete_url = f"http://127.0.0.1:9/audio/puck/{erwartete_id}.opus"
        add("speak() mit Stimme versucht die richtige URL",
            gemessen["url"] == erwartete_url, f'{gemessen["url"]!r}')
        add("speak() fällt bei einem Abspielfehler auf speechSynthesis zurück",
            gemessen["text"] == "Testsatz für Puck", f'{gemessen["text"]!r}')

        # ---------------------------------------------------- (4) Auftrag B
        b_erg = page.evaluate("""() => {
          S = freshState(); S.server = ''; save(); go('home');
          const x = waehleUnit(false).unit;    // was der Normal-Pfad ohnehin wählt

          // Ein "jetzt"-Wunsch trifft genau dieses Paket X.
          S.wishes = [{ziel:'skill', id:x.skill, art:'jetzt', t:Date.now()}];
          save();
          const ohneMehr = waehleUnit(false).unit;
          const mitMehr  = waehleUnit(true).unit;

          // Jetzt alle anderen Pakete als erledigt markieren: X bleibt als
          // einziger Kandidat übrig.
          DATA.units.forEach(u => { if(u.id !== x.id)
            S.units[u.id] = {stars:3, plays:1, sofort:0, pausiertBis:0, rev:''}; });
          save();
          const nurXohneMehr = waehleUnit(false).unit;
          const nurXmitMehr  = waehleUnit(true).unit;

          return {x:x.id, ohneMehr:ohneMehr.id, mitMehr:mitMehr.id,
                  nurXohneMehr:nurXohneMehr.id, nurXmitMehr:nurXmitMehr.id};
        }""")
        add("waehleUnit(false) liefert weiterhin das gewünschte Paket X",
            b_erg["ohneMehr"] == b_erg["x"], str(b_erg))
        add('waehleUnit(true) liefert NICHT X, obwohl der Wunsch darauf zeigt',
            b_erg["mitMehr"] != b_erg["x"], str(b_erg))
        add("Bleibt nur X als Kandidat übrig, liefert waehleUnit(false) X",
            b_erg["nurXohneMehr"] == b_erg["x"], str(b_erg))
        add("Bleibt nur X als Kandidat übrig, liefert auch waehleUnit(true) X",
            b_erg["nurXmitMehr"] == b_erg["x"], str(b_erg))

        add("keine JS-Fehler im Browser", not errs, errs[0][:100] if errs else "")
        b.close()


def teste_audio_route():
    tele = Path(tempfile.mkdtemp(prefix="mathcraft_tts_tele_"))
    umgebung = dict(os.environ, MC_TELE=str(tele))
    dienst = subprocess.Popen(
        [sys.executable, str(ROOT / "tutor/server.py"),
         "--port", str(PORT), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=umgebung)

    testdatei = ROOT / "data" / "audio" / "leda" / "deadbeef.opus"
    testinhalt = b"OggS-Testinhalt-fuer-den-Audio-Routentest"
    try:
        add("Dienst startet", warte_auf_dienst(f"http://127.0.0.1:{PORT}/health"))

        testdatei.parent.mkdir(parents=True, exist_ok=True)
        testdatei.write_bytes(testinhalt)

        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/audio/leda/deadbeef.opus") as r:
            inhalt, kopf = r.read(), r.headers
        add("Die Audio-Route liefert die hingelegte Testdatei aus", inhalt == testinhalt)
        add("Content-Type ist audio/ogg", kopf.get("Content-Type", "").startswith("audio/ogg"),
            kopf.get("Content-Type"))
        add("Cache-Control ist unbegrenzt und inhaltsadressiert",
            kopf.get("Cache-Control") == "public, max-age=31536000, immutable",
            kopf.get("Cache-Control"))

        add('Ein Pfadangriff über ".." bei der Stimme wird nicht ausgeliefert',
            status_von(f"http://127.0.0.1:{PORT}/audio/../deadbeef.opus") != 200)
        add("Eine Kennung ohne 8-Hex-Form wird abgewiesen",
            status_von(f"http://127.0.0.1:{PORT}/audio/leda/xyz.opus") == 400)
        add("Eine falsche Dateiendung wird abgewiesen",
            status_von(f"http://127.0.0.1:{PORT}/audio/leda/deadbeef.mp3") == 400)
        add("Großschreibung bei der Stimme wird abgewiesen",
            status_von(f"http://127.0.0.1:{PORT}/audio/LEDA/deadbeef.opus") == 400)
        add("Eine gültige, aber fehlende Kennung ergibt 404",
            status_von(f"http://127.0.0.1:{PORT}/audio/leda/00000000.opus") == 404)
    finally:
        dienst.terminate()
        dienst.wait(timeout=5)
        shutil.rmtree(tele, ignore_errors=True)
        try:
            testdatei.unlink()
        except FileNotFoundError:
            pass


def teste_korpus():
    korpus = TTS.sammle_korpus()
    add("Der Korpus enthält mindestens 600 Einträge", len(korpus) >= 600, str(len(korpus)))
    alle_hex = all(len(e["id"]) == 8 and all(c in "0123456789abcdef" for c in e["id"])
                   for e in korpus)
    add("Alle Kennungen sind 8-stellig hexadezimal", alle_hex)
    gesehen = {}
    kollision = False
    for e in korpus:
        if e["id"] in gesehen and gesehen[e["id"]] != e["text"]:
            kollision = True
        gesehen[e["id"]] = e["text"]
    add("Keine Kennung mit unterschiedlichem Text doppelt vergeben", not kollision)


def main():
    if not APP.exists():
        sys.exit("index.html fehlt — zuerst build/build.py laufen lassen.")
    if not frei(PORT):
        sys.exit(f"Port {PORT} ist belegt")

    teste_korpus()
    teste_im_browser()
    teste_audio_route()

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, info in RESULTS:
        print(f'{"✅" if ok else "❌"} {name}' + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS)-len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
