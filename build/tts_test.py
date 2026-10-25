# -*- coding: utf-8 -*-
"""Prüft Auftrag A (vorproduzierte Vorlese-Stimmen) und Auftrag B (der
"Gib mir was Schwereres"-Knopf).

  .venv/bin/python build/tts_test.py

Geprüft wird:
  1. Python- und JS-Bildung der Audio-ID sind für dieselben Texte identisch
     (crc32 über die normalisierte Kette) — die JS-Seite läuft dabei echt im
     Browser gegen die gebaute index.html, nicht nachgebaut.
  2. Die /audio-Route liefert eine hingelegte Testdatei mit korrektem
     Content-Type und Cache-Header aus und weist ungültige Pfade ab. Der Dienst
     spricht seit der Sicherheitsumstellung nur noch HTTPS; ihn startet
     HttpsDienst aus eltern_test.py (localhost, Dummy-Geheimnisse, wie in
     wunsch_test.py).
  3. speak() versucht bei gewählter Stimme die richtige URL und fällt bei
     einem Abspielfehler auf die Systemstimme (speechSynthesis) zurück.
  4. waehleUnit(true) liefert ein anderes Paket als waehleUnit(false), wenn
     ein "jetzt"-Wunsch zufällig genau das Paket trifft, das der Normal-Pfad
     ohnehin gewählt hätte — außer es gäbe gar kein anderes Paket mehr.
"""
import shutil
import socket
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T
import tts_erzeugen as TTS
from eltern_test import HttpsDienst

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
        # Die App spricht den Dienst nur noch über HTTPS an (serverUrl()), auch bei
        # einer eingetragenen Adresse ohne Schema.
        erwartete_url = f"https://127.0.0.1:9/audio/puck/{erwartete_id}.opus"
        add("speak() mit Stimme versucht die richtige URL",
            gemessen["url"] == erwartete_url, f'{gemessen["url"]!r}')
        add("speak() fällt bei einem Abspielfehler auf speechSynthesis zurück",
            gemessen["text"] == "Testsatz für Puck", f'{gemessen["text"]!r}')

        # ------------------------------ (3b) V3-Texte ohne vorproduzierten Clip
        # Für Legen-Aufgaben und den Denk-Check gibt es (noch) keine Aufnahmen:
        # der Dienst antwortet 404, und die Systemstimme muss den Satz sprechen.
        v3 = page.evaluate("""async () => {
          S = freshState(); S.settings.modus = 'v2'; S.settings.stimme = 'puck';
          S.settings.speech = true; S.server = '127.0.0.1:9'; save();
          const gesagt = [], urls = [];
          window.speechSynthesis.speak = u => gesagt.push(u.text);
          window.fetch = url => { urls.push(String(url));
            return Promise.resolve({ok: false, status: 404, blob: () => Promise.reject(new Error('404'))}); };
          const schlaf = ms => new Promise(r => setTimeout(r, ms));
          const legen = DATA.units.flatMap(u => u.tasks).find(x => x.type === 'legen');
          beginSession({kind:'unit', unitId:null, title:'T', intro:'', tasks:[legen]});
          await schlaf(700);
          const nachLegen = gesagt.slice();
          SESS = null; gesagt.length = 0;
          dcIntro('A', false);
          await schlaf(900);
          const nachIntro = gesagt.slice();
          gesagt.length = 0;
          dcLos('A');
          await schlaf(700);
          const aufgabe = SESS.tasks[SESS.i];
          return {legenQ: legen.q, nachLegen, intro: dcIntroText('A', false), nachIntro,
                  dcQ: aufgabe.q, nachDc: gesagt.slice(), urls};
        }""")
        add("Legen: der Satz q wird bei fehlendem Clip (404) mit der Systemstimme gesprochen",
            v3["legenQ"] in v3["nachLegen"], str(v3["nachLegen"])[:90])
        add("Denk-Check: die Einleitung wird bei fehlendem Clip mit der Systemstimme gesprochen",
            v3["intro"] in v3["nachIntro"], str(v3["nachIntro"])[:90])
        add("Denk-Check: jede Aufgabe wird vorgelesen (Systemstimme als Rückfall)",
            v3["dcQ"] in v3["nachDc"], str(v3["nachDc"])[:90])
        add("Alle Clip-Anfragen gehen über HTTPS an die kennungsbasierte Route",
            v3["urls"] and all(u.startswith("https://127.0.0.1:9/audio/puck/") and u.endswith(".opus")
                               for u in v3["urls"]), str(v3["urls"][:2]))

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
    dienst = HttpsDienst(PORT, tele)

    testdatei = ROOT / "data" / "audio" / "leda" / "deadbeef.opus"
    testinhalt = b"OggS-Testinhalt-fuer-den-Audio-Routentest"
    try:
        add("Dienst startet (HTTPS)", dienst.start())

        testdatei.parent.mkdir(parents=True, exist_ok=True)
        testdatei.write_bytes(testinhalt)

        r = dienst.get("/audio/leda/deadbeef.opus")
        add("Die Audio-Route liefert die hingelegte Testdatei aus",
            r.status == 200 and r.body == testinhalt, str(r.status))
        add("Content-Type ist audio/ogg", (r.header.get("Content-Type") or "").startswith("audio/ogg"),
            r.header.get("Content-Type"))
        add("Cache-Control ist unbegrenzt und inhaltsadressiert",
            r.header.get("Cache-Control") == "public, max-age=31536000, immutable",
            r.header.get("Cache-Control"))

        add('Ein Pfadangriff über ".." bei der Stimme wird nicht ausgeliefert',
            dienst.get("/audio/../deadbeef.opus").status != 200)
        add("Eine Kennung ohne 8-Hex-Form wird abgewiesen",
            dienst.get("/audio/leda/xyz.opus").status == 400)
        add("Eine falsche Dateiendung wird abgewiesen",
            dienst.get("/audio/leda/deadbeef.mp3").status == 400)
        add("Großschreibung bei der Stimme wird abgewiesen",
            dienst.get("/audio/LEDA/deadbeef.opus").status == 400)
        add("Eine gültige, aber fehlende Kennung ergibt 404",
            dienst.get("/audio/leda/00000000.opus").status == 404)
    finally:
        dienst.stop()
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
