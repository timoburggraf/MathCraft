# -*- coding: utf-8 -*-
"""Prüft Z6 aus ZIELE.md: die Erklärung am Beispiel.

Kein Aufruf ans Sprachmodell — das kostet Geld und wäre für diese Fragen auch
gar nicht nötig. Geprüft wird, was das Modell nicht in der Hand hat: dass eine
falsch gerechnete Erklärung verworfen wird, dass ein Kind bei einem Ausfall
keine Fehlermeldung zu sehen bekommt, und dass vom Gerät nichts weggeht außer
Paketnummer und Aufgabennummer.

Die Antwortzeit lässt sich nur an einem echten Aufruf messen; dafür gibt es
tutor/erklaerer.py auf der Kommandozeile.

  .venv/bin/python build/erklaer_test.py
"""
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "index.html"
PORT = 8795          # echter Dienst
STUB = 8794          # Attrappe, die die Anfrage mitschreibt

RESULTS = []
GESEHEN = []


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


class Attrappe(http.server.BaseHTTPRequestHandler):
    """Schreibt mit, was die App schickt, und antwortet wie der Dienst.

    Bewusst in mehreren Häppchen mit Pausen dazwischen: Nur so zeigt sich, ob
    die App wirklich mitliest, statt am Ende alles auf einmal zu bekommen.
    """

    protocol_version = "HTTP/1.1"

    HAEPPCHEN = [
        {"t": "bsp", "v": {"frage": "Was ist 8 + 5?", "rechnung": "8+2+3", "ergebnis": 13}},
        {"t": "txt", "v": "Zähl erst bis zum Zehner, "},
        {"t": "txt", "v": "dann die restlichen Schritte weiter."},
        {"t": "fertig", "v": {"ms": 900, "erste_worte": 300, "aus_ablage": False}},
    ]

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        GESEHEN.append(self.rfile.read(n).decode("utf-8", "replace"))
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for h in self.HAEPPCHEN:
            zeile = (json.dumps(h, ensure_ascii=False) + "\n").encode("utf-8")
            self.wfile.write(b"%x\r\n%s\r\n" % (len(zeile), zeile))
            self.wfile.flush()
            time.sleep(0.3)
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def log_message(self, *a):
        pass


def main():
    from playwright.sync_api import sync_playwright

    if not APP.exists():
        sys.exit("index.html fehlt — zuerst build/build.py laufen lassen.")
    if not frei(PORT) or not frei(STUB):
        sys.exit("Ports 8794/8795 sind belegt")

    sys.path.insert(0, str(ROOT / "tutor"))
    sys.path.insert(0, str(ROOT / "build"))
    import erklaerer as E

    # ------------------------------------------------ Der Prüfer für sich
    aufgabe = {"q": "Was ist 7 + 6?", "a": 13, "type": "zahl"}
    andere = {"q": "Was ist 7 + 6?", "a": 99, "type": "zahl"}
    text_gut = ("Zerleg die zweite Zahl so, dass du erst auf zehn kommst. "
                "Dann rechnest du den Rest dazu.")

    add("Ein sauberes Beispiel geht durch",
        not E.pruefe_beispiel("8+2+3", 13, "Was ist 8 + 5?", andere))
    p = E.pruefe_beispiel("8+2+3", 14, "Was ist 8 + 5?", andere)
    add("Ein Beispiel, das nicht aufgeht, wird verworfen", bool(p), p[0][:60] if p else "")
    add("Eine Rechnung in Worten wird verworfen",
        bool(E.pruefe_beispiel("acht plus fünf", 13, "Was ist 8 + 5?", andere)))
    add("Ein untergeschobener Ausdruck wird nicht ausgeführt",
        bool(E.pruefe_beispiel("__import__('os').system('ls')", 0, "x", andere)))
    add("Die vorliegende Aufgabe als Beispiel wird verworfen",
        any("vorliegende" in x for x in
            E.pruefe_beispiel("8+2+3", 13, "Was ist 7 + 6?", andere)))
    add("Ein Beispiel mit derselben Antwort wird verworfen",
        any("dieselbe Antwort" in x for x in
            E.pruefe_beispiel("8+2+3", 13, "Was ist 8 + 5?", aufgabe)))

    add("Eine zu kurze Erklärung wird verworfen", bool(E.pruefe_text("Rechne.")))
    add("Eine brauchbare Erklärung geht durch", not E.pruefe_text(text_gut))
    add("Durchgerutschtes Markup wird verworfen",
        any("Markup" in x for x in
            E.pruefe_text("<thinking>ich überlege</thinking> " + text_gut)))

    # ------------------------------------------------------- Die Kopfzeilen
    kopf, grund = E._kopfzeilen(["RECHNUNG: 8+2+3 = 13", "BEISPIEL: Was ist 8 + 5?"])
    add("Die Kopfzeilen werden auseinandergenommen",
        kopf and kopf["rechnung"] == "8+2+3" and kopf["ergebnis"] == 13
        and kopf["frage"] == "Was ist 8 + 5?", grund or json.dumps(kopf or {}))
    add("Ein Ergebnis mit Komma wird gelesen",
        (E._kopfzeilen(["RECHNUNG: 5/2 = 2,5", "BEISPIEL: x"])[0] or {}).get("ergebnis") == 2.5)
    add("Fehlt die Form, wird abgebrochen",
        E._kopfzeilen(["Also, das geht so:", "erst dies, dann das"])[0] is None)
    add("Eine Rechnung ohne Ergebnis wird abgebrochen",
        E._kopfzeilen(["RECHNUNG: 8+2+3", "BEISPIEL: x"])[0] is None)

    # Beobachtet: Das Modell verwirft mitten in der Antwort einen eigenen
    # Entwurf und fängt neu an. Der Entwurf darf nicht beim Kind landen.
    selbstkorrektur = ("RECHNUNG: 12+5 = 17\n\nUps — das darf ich so nicht nehmen. "
                       "Hier neu:\n\nRECHNUNG: 11+5 = 16\nBEISPIEL: Elf und fünf.\n\n"
                       "Fang bei der großen Zahl an.")
    kopf, rest, grund = E._kopf_suchen(selbstkorrektur)
    add("Ein verworfener Entwurf des Modells fällt weg",
        kopf and kopf["rechnung"] == "11+5" and kopf["ergebnis"] == 16,
        json.dumps(kopf or {}, ensure_ascii=False))
    add("Und sein Gerede landet nicht beim Kind",
        rest is not None and "Ups" not in rest and rest.startswith("Fang bei"),
        (rest or "")[:40])

    add("Ohne Kopfpaar wird weiter gesammelt",
        E._kopf_suchen("RECHNUNG: 8+2+3 = 13\n")[1] is None)
    add("Irgendwann ist aber Schluss",
        E._kopf_suchen("Bla. " * 300)[2] != "")

    # ------------------------------------ Kein Schlüssel auf dem Kindergerät
    text = APP.read_text("utf-8", errors="replace")
    add("Kein API-Schlüssel in der ausgelieferten App",
        "sk-ant" not in text and "ANTHROPIC" not in text.upper())
    add("Die App kennt das Modell gar nicht", "claude-" not in text)
    add("Die App ruft nur den Heim-Dienst", "api.anthropic.com" not in text)

    # ---------------------------------------- Der Dienst mit fertiger Ablage
    tele = Path(tempfile.mkdtemp(prefix="mathcraft_erk_"))
    cache_alt = E.CACHE
    cache = Path(tempfile.mkdtemp(prefix="mathcraft_cache_"))
    units = json.loads((ROOT / "data" / "units_seed.json").read_text("utf-8"))["units"]
    erste = units[0]
    unit_id = f'{erste["skill"]}@{erste["stage"]}'
    (cache / f'{unit_id.replace("@","_")}_0.json').write_text(json.dumps({
        "erklaerung": "Zerleg die zweite Zahl bis zum Zehner.",
        "beispiel": {"frage": "Was ist 8 + 5?", "rechnung": "8+2+3", "ergebnis": 13},
        "ms": 1234, "aus_ablage": False}), "utf-8")

    dienst = subprocess.Popen(
        [str(ROOT / ".venv/bin/python"), str(ROOT / "tutor/server.py"),
         "--port", str(PORT), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=dict(os.environ, MC_TELE=str(tele), MC_ERK_CACHE=str(cache)))
    attrappe = http.server.HTTPServer(("127.0.0.1", STUB), Attrappe)
    threading.Thread(target=attrappe.serve_forever, daemon=True).start()

    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1)
                break
            except Exception:
                time.sleep(.2)

        def post(pfad, daten, port=PORT):
            """Der Dienst antwortet strömend: eine JSON-Zeile je Häppchen."""
            r = urllib.request.Request(f"http://127.0.0.1:{port}{pfad}",
                                       data=json.dumps(daten).encode(),
                                       headers={"Content-Type": "text/plain"}, method="POST")
            with urllib.request.urlopen(r, timeout=15) as resp:
                zeilen = [json.loads(z) for z in resp.read().decode("utf-8").splitlines()
                          if z.strip()]
                return resp.status, zeilen

        t0 = time.time()
        status, m = post("/erklaer", {"u": unit_id, "i": 0})
        aus_ablage = time.time() - t0
        arten = [x["t"] for x in m]
        txt = "".join(x["v"] for x in m if x["t"] == "txt")
        bsp = next((x["v"] for x in m if x["t"] == "bsp"), None)
        add("Eine fertige Erklärung kommt aus der Ablage",
            status == 200 and txt and bsp and "weg" not in arten, txt[:40])
        add("Das geprüfte Beispiel kommt vor dem Text",
            arten and arten[0] == "bsp", " → ".join(arten))
        add("Aus der Ablage dauert es keine halbe Sekunde", aus_ablage < 0.5,
            f"{aus_ablage*1000:.0f} ms")

        status, m = post("/erklaer", {"u": "gibtsnicht@9", "i": 0})
        add("Eine unbekannte Aufgabe meldet keinen Fehler an das Kind",
            status == 200 and [x["t"] for x in m] == ["weg"], f'{status}')

        status2 = None
        try:
            post("/erklaer", {"u": unit_id})
        except urllib.error.HTTPError as e:
            status2 = e.code
        add("Eine Anfrage ohne Aufgabennummer wird abgewiesen", status2 == 400, str(status2))

        # ---------------------------------------------------- Die App dazu
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_context(viewport={"width": 393, "height": 873}).new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            T.ohne_dienst(page)
            page.goto(APP.as_uri())
            page.wait_for_timeout(400)

            # Eine Aufgabe zweimal falsch beantworten, gegen die Attrappe
            lauf = page.evaluate(f"""async () => {{
              S = freshState(); S.server = '127.0.0.1:{STUB}'; S.profile.name = 'Alex'; save();
              const u = DATA.units.find(x => x.tasks.some(t => t.type === 'zahl'));
              startUnit(u.id);
              const i = SESS.tasks.findIndex(t => t.type === 'zahl');
              SESS.i = i;
              grade(false);                       // erster Fehlversuch
              const nachEins = JSON.parse(JSON.stringify(ERK));
              // die Wiederholung derselben Aufgabe ans Ende gelegt
              SESS.i = SESS.tasks.length - 1;
              Object.assign(SESS, {{answered:false}});
              grade(false);                       // zweiter Fehlversuch
              // Die Attrappe schickt in Häppchen im Abstand von 300 ms:
              // bsp bei 0, txt bei 300, txt bei 600, fertig bei 900. Wer bei
              // 520 ms erst das halbe Stück hat, liest wirklich unterwegs mit.
              await new Promise(r => setTimeout(r, 520));
              const fruh = {{text: ERK.text, beispiel: ERK.beispiel, laeuft: ERK.laeuft}};
              await new Promise(r => setTimeout(r, 1400));
              return {{nachEins, fruh, text: ERK.text, beispiel: ERK.beispiel,
                      laeuft: ERK.laeuft,
                      redo: SESS.tasks[SESS.tasks.length-1].redo === true}};
            }}""")
            add("Beim ersten Fehlversuch wird noch nicht gefragt",
                not lauf["nachEins"]["laeuft"] and not lauf["nachEins"]["text"])
            add("Die Wiederholung derselben Aufgabe wird erkannt", lauf["redo"])
            add("Beim zweiten Fehlversuch kommt die Erklärung",
                bool(lauf["text"]), (lauf["text"] or "")[:45])

            fruh = lauf["fruh"]
            add("Der Text steht schon da, bevor der Strom zu Ende ist",
                bool(fruh["text"]) and len(fruh["text"]) < len(lauf["text"]),
                f'nach 380 ms: {len(fruh["text"] or "")} von {len(lauf["text"] or "")} Zeichen')
            add("Das geprüfte Beispiel liegt vor dem ersten Wort vor",
                bool(fruh["beispiel"]))
            add("Am Ende ist der Strom abgeschlossen", not lauf["laeuft"])
            add("Das Beispiel kommt mit", bool(lauf["beispiel"]),
                json.dumps(lauf["beispiel"] or {}, ensure_ascii=False)[:50])

            add("Die App fragt überhaupt an", bool(GESEHEN))
            if GESEHEN:
                nutzlast = json.loads(GESEHEN[-1])
                add("Geschickt werden nur Paket und Nummer",
                    set(nutzlast) == {"u", "i"}, ", ".join(sorted(nutzlast)))
                add("Kein Aufgabentext und kein Name verlassen das Gerät",
                    "Alex" not in GESEHEN[-1] and "?" not in str(nutzlast.get("u", "")),
                    GESEHEN[-1][:60])

            add("Die Erklärung steht auf dem Bildschirm",
                page.locator("text=Zehner").count() > 0)

            # ------------------------------------- Der Knopf „Erklär es mir“
            # Die Lösung steht nach einem Fehler ohnehin da. Wer wissen will,
            # wie man daraufkommt, soll nicht erst ein zweites Mal danebenliegen
            # müssen — aber auch nicht ungefragt aufgehalten werden, wenn er
            # sich nur vertippt hat.
            knopf = page.evaluate(f"""() => {{
              S = freshState(); S.server = '127.0.0.1:{STUB}'; save();
              ERK = {{fuer:'', laeuft:false, text:'', beispiel:null}};
              const u = DATA.units.find(x => x.tasks.some(t => t.type === 'zahl'));
              startUnit(u.id);
              SESS.i = SESS.tasks.findIndex(t => t.type === 'zahl');
              grade(false);
              return {{da: !!document.querySelector('.erk'), laeuft: ERK.laeuft,
                      text: ERK.text}};
            }}""")
            add("Nach dem ersten Fehler steht „Erklär es mir“ zur Wahl", knopf["da"])
            add("Von allein wird dabei nichts angefragt",
                not knopf["laeuft"] and not knopf["text"])

            if knopf["da"]:
                page.click(".erk")
                page.wait_for_timeout(1800)
                nach = page.evaluate("""() => ({text: ERK.text, laeuft: ERK.laeuft,
                                               knopf: !!document.querySelector('.erk')})""")
                add("Ein Tipp darauf holt die Erklärung", bool(nach["text"]),
                    (nach["text"] or "")[:45])
                add("Danach ist der Knopf verschwunden, die Erklärung steht da",
                    not nach["knopf"] and not nach["laeuft"])

            stumm = page.evaluate("""() => {
              const richtig = (() => {
                S = freshState(); S.server = '127.0.0.1:1'; save();
                ERK = {fuer:'', laeuft:false, text:'', beispiel:null};
                const u = DATA.units.find(x => x.tasks.some(t => t.type === 'zahl'));
                startUnit(u.id);
                SESS.i = SESS.tasks.findIndex(t => t.type === 'zahl');
                grade(true);
                return !!document.querySelector('.erk');
              })();
              // ohne eingetragenen Rechner darf kein Knopf erscheinen, der nichts tut
              S = freshState(); S.server = ''; save();
              const u2 = DATA.units.find(x => x.tasks.some(t => t.type === 'zahl'));
              startUnit(u2.id);
              SESS.i = SESS.tasks.findIndex(t => t.type === 'zahl');
              grade(false);
              return {richtig, ohneDienst: !!document.querySelector('.erk')};
            }""")
            add("Bei richtiger Antwort erscheint er nicht", not stumm["richtig"])
            add("Ohne eingetragenen Rechner erscheint er auch nicht",
                not stumm["ohneDienst"])

            # Dienst weg: der feste Tipp muss übernehmen, ohne Fehlermeldung
            zurueck = page.evaluate("""async () => {
              S.server = '10.255.255.1:9'; save();
              ERK = {fuer:'', laeuft:false, text:'', beispiel:null};
              const u = DATA.units.find(x => x.tasks.some(t => t.type === 'zahl' && t.hint));
              if(!u) return {ohne:true};
              startUnit(u.id);
              const i = u.tasks.findIndex(t => t.type === 'zahl' && t.hint);
              SESS.i = i; grade(false);
              SESS.i = SESS.tasks.length - 1; Object.assign(SESS, {answered:false});
              grade(false);
              await new Promise(r => setTimeout(r, 300));
              return {ohne:false, tipp: SESS.tasks[SESS.i].hint || '', laeuft: ERK.laeuft};
            }""")
            if not zurueck.get("ohne"):
                page.wait_for_timeout(400)
                # Nur der sichtbare Text zählt. page.content() enthält auch den
                # Quelltext der eingebetteten Skripte und würde jede
                # Fehlermeldung finden, die dort bloß als Zeichenkette steht.
                sichtbar = page.locator("#app").inner_text()
                add("Ohne Dienst steht der feste Tipp da",
                    zurueck["tipp"] and zurueck["tipp"][:20] in sichtbar,
                    zurueck["tipp"][:40])
                add("Ohne Dienst erscheint keine Fehlermeldung",
                    not any(w in sichtbar for w in
                            ("Fehler", "Kontakt zum Rechner", "antwortet nicht", "⚠")),
                    sichtbar[:70].replace("\n", " "))

            add("keine JS-Fehler", not errs, errs[0][:70] if errs else "")
            b.close()
    finally:
        attrappe.shutdown()
        dienst.terminate()
        dienst.wait(timeout=5)
        shutil.rmtree(tele, ignore_errors=True)
        shutil.rmtree(cache, ignore_errors=True)
        E.CACHE = cache_alt

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, info in RESULTS:
        print(f'{"✅" if ok else "❌"} {name}' + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS)-len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
