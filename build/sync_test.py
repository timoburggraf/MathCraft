# -*- coding: utf-8 -*-
"""Prüft Z1 aus ZIELE.md: erreicht der Lernstand den Dienst, und zwar vollständig?

Die Elternseite und der Tutor stehen und fallen mit dieser Kette. Geprüft wird
gegen einen wirklich laufenden Dienst, nicht gegen Attrappen — die Stellen, an
denen es klemmt, liegen erfahrungsgemäß dazwischen.

Die Zielwerte stehen in ZIELE.md, Abschnitt Z1:
  · je beantworteter Aufgabe genau ein Ereignis, Abweichung 0
  · doppelte Übertragung verändert den Bestand nicht
  · eine Offline-Phase kostet kein Ereignis
  · 30 Tage passen in unter 200 KB
  · kein Klarname verlässt das Gerät

  .venv/bin/python build/sync_test.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T
from smoke_test import play

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "index.html"
PORT = 8798            # eigener Port, damit der echte Dienst weiterlaufen darf

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
    for _ in range(sekunden * 5):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(.2)
    return False


def post(pfad, daten):
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}{pfad}",
                               data=json.dumps(daten).encode("utf-8"),
                               headers={"Content-Type": "text/plain;charset=UTF-8"},
                               method="POST")
    with urllib.request.urlopen(r, timeout=5) as resp:
        return json.loads(resp.read())


def hole(pfad):
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{pfad}", timeout=5) as r:
        return json.loads(r.read())


def formular(pfad, felder):
    """Ein abgeschicktes Formular wie von der Elternseite. Gibt den Status zurück."""
    r = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{pfad}",
        data=urllib.parse.urlencode(felder).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    class _ohneUmleitung(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        with urllib.request.build_opener(_ohneUmleitung).open(r, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def main():
    from playwright.sync_api import sync_playwright

    if not APP.exists():
        sys.exit("index.html fehlt — zuerst build/build.py laufen lassen.")
    if not frei(PORT):
        sys.exit(f"Port {PORT} ist belegt")

    tele = Path(tempfile.mkdtemp(prefix="mathcraft_tele_"))
    umgebung = dict(os.environ, MC_TELE=str(tele))
    dienst = subprocess.Popen(
        [sys.executable, str(ROOT / "tutor/server.py"),
         "--port", str(PORT), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=umgebung)

    try:
        add("Dienst startet", warte_auf_dienst(f"http://127.0.0.1:{PORT}/health"))

        # ---------------------------------------------- Der Dienst für sich
        ladung = {"v": 1, "dev": "0123456789abcdef", "stats": {"answers": 2, "lost": 0},
                  "ev": [
                      {"i": 1, "t": 1753776000000, "s": "aa11", "e": "a", "u": "x@1",
                       "k": "x", "g": 1, "y": "zahl", "o": 1, "ms": 3000, "r": 0, "h": 0},
                      {"i": 2, "t": 1753776009000, "s": "aa11", "e": "a", "u": "x@1",
                       "k": "x", "g": 1, "y": "wahl", "o": 0, "ms": 7000, "r": 0, "h": 1,
                       "name": "Alex", "notiz": "geheim"}]}
        a1 = post("/sync", ladung)
        add("Dienst nimmt Ereignisse an", a1.get("neu") == 2 and a1.get("ack") == 2,
            f'ack={a1.get("ack")}')

        a2 = post("/sync", ladung)
        add("Dieselbe Ladung ein zweites Mal verändert nichts",
            a2.get("neu") == 0 and a2.get("ack") == 2, f'neu={a2.get("neu")}')

        z = hole("/zaehlstand")
        add("Ereigniszahl im Dienst deckt sich mit dem Gerät",
            z["abweichung"] == 0 and z["antworten_hier"] == 2,
            f'hier={z["antworten_hier"]} Gerät={z["antworten_geraete"]}')

        auf_platte = (tele / "0123456789abcdef.jsonl").read_text("utf-8")
        add("Unbekannte Felder landen nicht auf der Platte",
            "Alex" not in auf_platte and "geheim" not in auf_platte)

        add("Eine unbrauchbare Geräte-Id wird abgewiesen",
            _wirft_400({"v": 1, "dev": "../../etc/passwd", "ev": []}))

        # ------------------------------- Ein Gerät aus der Auswertung nehmen
        # Ein Testlauf, der einmal mitgezählt hat, verfälscht jede Zahl auf der
        # Elternseite. Er muss sich ausblenden lassen — und zurückholen, ohne
        # dass dabei eine Aufzeichnung verloren geht.
        formular("/geraet", {"dev": "0123456789abcdef", "art": "aus"})
        z_aus = hole("/zaehlstand")
        add("Ein ausgeblendetes Gerät zählt nicht mehr mit",
            z_aus["antworten_hier"] == 0 and z_aus["geraete"] == 0,
            f'hier={z_aus["antworten_hier"]}, {z_aus["geraete"]} Geräte')
        add("Seine Aufzeichnung bleibt trotzdem liegen",
            (tele / "0123456789abcdef.jsonl").exists())
        formular("/geraet", {"dev": "0123456789abcdef", "art": "ein"})
        z_ein = hole("/zaehlstand")
        add("Zurückgeholt zählt es wieder vollständig",
            z_ein["antworten_hier"] == 2 and z_ein["geraete"] == 1,
            f'hier={z_ein["antworten_hier"]}')
        add("Eine unbrauchbare Geräte-Id wird auch hier abgewiesen",
            formular("/geraet", {"dev": "../../etc/passwd", "art": "aus"}) == 400)

        # ----------------------------------------------- Spielername (02.09.2026)
        # Elternwunsch: der Name, den sich das Kind selbst gibt, ist ab jetzt
        # das einzige übertragene Freitextfeld. Er reist als Sync-Metadatum
        # neben den Ereignissen, nicht als Ereignisfeld — und landet nur in
        # den Kopfdaten, nie in der .jsonl. Ein eigenes Gerät, damit diese
        # Fälle die Zählstände der übrigen Tests nicht verfälschen.
        dev_name = "aabbccdd11223344"
        post("/sync", {"v": 1, "dev": dev_name, "ev": [], "name": "Alex"})
        kopf_name = json.loads((tele / f"{dev_name}.json").read_text("utf-8"))
        add("Der Spielername kommt an und steht in den Kopfdaten",
            kopf_name.get("name") == "Alex", kopf_name.get("name"))

        roh_name = "\x00Alex\x01" + "X" * 30
        erwartet_name = "Alex" + "X" * 14
        post("/sync", {"v": 1, "dev": dev_name, "ev": [], "name": roh_name})
        kopf_name2 = json.loads((tele / f"{dev_name}.json").read_text("utf-8"))
        add("Steuerzeichen und Überlänge werden beim Spielernamen gesäubert",
            kopf_name2.get("name") == erwartet_name, kopf_name2.get("name"))

        post("/sync", {"v": 1, "dev": dev_name, "ev": [], "name": ""})
        kopf_name3 = json.loads((tele / f"{dev_name}.json").read_text("utf-8"))
        add("Ein leerer Spielername überschreibt einen vorhandenen nicht",
            kopf_name3.get("name") == erwartet_name, kopf_name3.get("name"))

        post("/sync", {"v": 1, "dev": dev_name,
                       "ev": [{"i": 1, "t": 1753776000000, "s": "nn11", "e": "g",
                               "u": "x@1", "w": 1}],
                       "name": "Alex"})
        inhalt_name = (tele / f"{dev_name}.jsonl").read_text("utf-8")
        add('Der Spielername landet nie in der .jsonl',
            "Alex" not in inhalt_name and erwartet_name not in inhalt_name)

        # --------------------------------------- A: ein "w"-Ereignis erfüllt
        # einen Wunsch beim Dienst. Der Rundlauf über den echten, laufenden
        # Dienst prüft insbesondere, dass die Verarbeitung nicht blockiert
        # (schreibe() hält für die Ablage selbst eine Sperre, wunsch_erfuellen()
        # sperrt ebenfalls) und dass ein zweites Mal folgenlos bleibt.
        sys.path.insert(0, str(ROOT / "build"))
        import curriculum as C
        ein_skill = C.SKILLS[0]["id"]
        formular("/wunsch", {"ziel": "skill", "id": ein_skill, "art": "jetzt"})
        wunschzeit = json.loads((tele / "wuensche.json").read_text("utf-8"))[-1]["t"]
        w_ladung = {"v": 1, "dev": "0123456789abcdef",
                    "ev": [{"i": 3, "t": 1753776010000, "s": "aa11", "e": "w",
                            "z": "skill", "k": ein_skill, "wz": wunschzeit}]}
        post("/sync", w_ladung)
        erfuellt = json.loads((tele / "wuensche.json").read_text("utf-8"))
        add('Ein "w"-Ereignis markiert den Wunsch beim Dienst als erfüllt',
            any(w["id"] == ein_skill and w.get("art") == "jetzt"
                and w.get("status") == "erfuellt" for w in erfuellt))
        post("/sync", w_ladung)
        add("Eine doppelte Erfüllung bleibt folgenlos",
            json.loads((tele / "wuensche.json").read_text("utf-8")) == erfuellt)
        formular("/wunsch", {"ziel": "skill", "id": ein_skill, "art": "weg"})

        # Ein AUSGEBLENDETES Gerät (Testlauf) darf keinen Wunsch erfüllen —
        # es spielt ja nicht für das Kind (Befund 03.09.2026: der Emulator
        # hakte einen für das Kind gedachten "jetzt"-Wunsch ab).
        ign_datei = tele / "ignoriert.json"
        ign = json.loads(ign_datei.read_text("utf-8")) if ign_datei.exists() else {"geraete": []}
        ign["geraete"] = sorted(set(ign.get("geraete", [])) | {"eeff00112233aabb"})
        ign_datei.write_text(json.dumps(ign), "utf-8")
        formular("/wunsch", {"ziel": "skill", "id": ein_skill, "art": "jetzt"})
        wunschzeit2 = json.loads((tele / "wuensche.json").read_text("utf-8"))[-1]["t"]
        post("/sync", {"v": 1, "dev": "eeff00112233aabb",
                       "ev": [{"i": 1, "t": 1753776020000, "s": "bb22", "e": "w",
                               "z": "skill", "k": ein_skill, "wz": wunschzeit2}]})
        nach_test = json.loads((tele / "wuensche.json").read_text("utf-8"))
        add("Ein ausgeblendetes Gerät erfüllt keinen Wunsch",
            not any(w["id"] == ein_skill and w.get("status") == "erfuellt"
                    for w in nach_test))
        formular("/wunsch", {"ziel": "skill", "id": ein_skill, "art": "weg"})

        # ------------------------------------------------- D: Offen-Stand
        post("/sync", {"v": 1, "dev": "0123456789abcdef",
                       "ev": [], "stats": {"answers": 2, "offen": [f"{ein_skill}@1"]}})
        kopf_datei = json.loads((tele / "0123456789abcdef.json").read_text("utf-8"))
        add("Der gemeldete Offen-Stand wird beim Gerät abgelegt",
            kopf_datei.get("offen") == [f"{ein_skill}@1"])

        # ---------------------------- D6: Rundlauf des neuen Grund-Ereignisses
        # Der Würfelfuchs fragt sparsam nach dem Abbruchgrund; die Antwort ist
        # eine Zahl 1..4, kein Freitext — auch hier darf ein mitgeschickter
        # Klarname den Dienst nicht erreichen.
        g_ladung = {"v": 1, "dev": "0123456789abcdef",
                    "ev": [{"i": 4, "t": 1753776011000, "s": "aa11", "e": "g",
                            "u": f"{ein_skill}@1", "w": 3, "name": "Alex"}]}
        post("/sync", g_ladung)
        inhalt_g = (tele / "0123456789abcdef.jsonl").read_text("utf-8")
        alle_zeilen_g = [json.loads(z) for z in inhalt_g.splitlines() if z.strip()]
        grund_ev = [e for e in alle_zeilen_g if e.get("e") == "g"]
        add("Das neue Abbruchgrund-Ereignis kommt beim Dienst an",
            len(grund_ev) == 1 and grund_ev[0].get("u") == f"{ein_skill}@1"
            and grund_ev[0].get("w") == 3, f"{len(grund_ev)} 'g'-Ereignisse")
        add("Auch beim Abbruchgrund werden unbekannte Felder verworfen",
            "Alex" not in inhalt_g)
        post("/sync", g_ladung)
        inhalt_g2 = (tele / "0123456789abcdef.jsonl").read_text("utf-8")
        grund_ev2 = [json.loads(z) for z in inhalt_g2.splitlines() if z.strip()
                     and json.loads(z).get("e") == "g"]
        add("Ein doppelt gesendeter Abbruchgrund verdoppelt sich nicht", len(grund_ev2) == 1)

        # ---------------------------- D6: Rundlauf des neuen Spaß-Signal-Ereignisses
        # Höchstens 1×/Sitzung, ein Tipp auf ein Gesicht — die Antwort ist eine
        # Zahl 1..3, kein Freitext, und muss wie jedes andere Ereignis idempotent
        # ankommen: derselbe Tipp zweimal gesendet darf sich nicht verdoppeln.
        f_ladung = {"v": 1, "dev": "0123456789abcdef",
                    "ev": [{"i": 5, "t": 1753776012000, "s": "aa11", "e": "f",
                            "u": f"{ein_skill}@1", "w": 3, "name": "Alex"}]}
        post("/sync", f_ladung)
        inhalt_f = (tele / "0123456789abcdef.jsonl").read_text("utf-8")
        alle_zeilen_f = [json.loads(z) for z in inhalt_f.splitlines() if z.strip()]
        spass_ev = [e for e in alle_zeilen_f if e.get("e") == "f"]
        add("Das neue Spaß-Signal-Ereignis kommt beim Dienst an",
            len(spass_ev) == 1 and spass_ev[0].get("u") == f"{ein_skill}@1"
            and spass_ev[0].get("w") == 3, f"{len(spass_ev)} 'f'-Ereignisse")
        add("Auch beim Spaß-Signal werden unbekannte Felder verworfen",
            "Alex" not in inhalt_f)
        post("/sync", f_ladung)
        inhalt_f2 = (tele / "0123456789abcdef.jsonl").read_text("utf-8")
        spass_ev2 = [json.loads(z) for z in inhalt_f2.splitlines() if z.strip()
                     and json.loads(z).get("e") == "f"]
        add("Ein doppelt gesendetes Spaß-Signal verdoppelt sich nicht", len(spass_ev2) == 1)

        # ---------------------------------------------------- Die App dazu
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_context(viewport={"width": 393, "height": 873}).new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            T.ohne_dienst(page)
            page.goto(APP.as_uri())
            page.wait_for_timeout(400)

            # Ohne Adresse: es wird gepuffert, nichts geht verloren.
            page.evaluate("""() => {
              S = freshState(); S.server = ''; S.profile.name = 'Alex'; save();
              go('home');
            }""")
            page.evaluate("() => startUnit(nextUnit().id)")
            page.wait_for_timeout(200)
            play(page)
            page.wait_for_timeout(400)

            stand = page.evaluate("""() => ({
              antworten: S.stats.answers,
              ereignisse: S.log.ev.filter(e => e.e === 'a').length,
              sitzungen: S.log.ev.filter(e => e.e === 's').length,
              verfallen: S.log.lost,
              vollstaendig: S.log.ev.filter(e => e.e === 'a').every(e =>
                typeof e.i === 'number' && typeof e.t === 'number' && e.s &&
                typeof e.u === 'string' && typeof e.k === 'string' &&
                typeof e.g === 'number' && typeof e.y === 'string' &&
                (e.o === 0 || e.o === 1) && typeof e.ms === 'number' &&
                (e.r === 0 || e.r === 1) && (e.h === 0 || e.h === 1)),
              dauern: S.log.ev.filter(e => e.e === 'a').every(e => e.ms >= 0)
            })""")
            add("Je Antwort genau ein Ereignis",
                stand["antworten"] > 0 and stand["ereignisse"] == stand["antworten"],
                f'{stand["ereignisse"]} Ereignisse, {stand["antworten"]} Antworten')
            add("Jedes Ereignis trägt alle geforderten Felder", stand["vollstaendig"])
            add("Antwortdauern werden gemessen", stand["dauern"])
            add("Das Sitzungsende wird festgehalten", stand["sitzungen"] >= 1,
                f'{stand["sitzungen"]}')
            add("Ohne Dienst geht nichts verloren", stand["verfallen"] == 0)

            # Jetzt die Adresse setzen und übertragen.
            page.evaluate(f"""async () => {{
              S.server = '127.0.0.1:{PORT}'; save(); await syncNow(true);
            }}""")
            page.wait_for_timeout(600)
            offen = page.evaluate("() => S.log.ev.length")
            add("Nach dem Übertragen ist der Puffer leer", offen == 0, f"{offen} offen")

            z2 = hole("/zaehlstand")
            add("Der Dienst zählt genauso viele Antworten wie das Gerät",
                z2["abweichung"] == 0,
                f'hier={z2["antworten_hier"]} Geräte={z2["antworten_geraete"]}')

            dev = page.evaluate("() => S.dev")
            inhalt = (tele / f"{dev}.jsonl").read_text("utf-8")
            add("Kein Klarname im übertragenen Bestand", "Alex" not in inhalt)

            # Zweiter Durchlauf: doppelt übertragen bleibt folgenlos.
            vorher = hole("/zaehlstand")["antworten_hier"]
            page.evaluate("async () => { await syncNow(true); await syncNow(true); }")
            page.wait_for_timeout(500)
            add("Doppeltes Übertragen verdoppelt nichts",
                hole("/zaehlstand")["antworten_hier"] == vorher, f"{vorher}")

            # Offline-Phase: falsche Adresse, weiterspielen, danach nachholen.
            page.evaluate("() => { S.server = '10.255.255.1:9'; save(); }")
            page.evaluate("() => startUnit(nextUnit().id)")
            page.wait_for_timeout(200)
            play(page)
            page.wait_for_timeout(300)
            page.evaluate("async () => { await syncNow(true); }")
            page.wait_for_timeout(7000)          # der Abbruch greift nach 8 Sekunden
            gepuffert = page.evaluate("() => S.log.ev.length")
            add("Ohne Verbindung bleibt alles im Puffer liegen", gepuffert > 0,
                f"{gepuffert} Ereignisse")

            page.evaluate(f"""async () => {{
              S.server = '127.0.0.1:{PORT}'; save(); await syncNow(true);
            }}""")
            page.wait_for_timeout(800)
            add("Nach der Offline-Phase wird alles nachgeholt",
                page.evaluate("() => S.log.ev.length") == 0)
            z3 = hole("/zaehlstand")
            add("Auch danach stimmt die Zählung", z3["abweichung"] == 0,
                f'hier={z3["antworten_hier"]}')

            # Nutzlast: 30 Tage bei 30 Aufgaben am Tag.
            groesse = page.evaluate("""() => {
              const ev = [];
              for(let i = 1; i <= 900; i++)
                ev.push({i, t: Date.now() - i*6e4, s: 'abcd1234', e: 'a',
                         u: 'sach_geld@5', k: 'sach_geld', g: 5, y: 'mehrschritt',
                         o: i % 3 ? 1 : 0, ms: 12345, r: 0, h: 0});
              return JSON.stringify({v:1, dev:S.dev, ev, stats:{answers:900, lost:0}}).length;
            }""")
            add("30 Tage passen in unter 200 KB", groesse < 200 * 1024,
                f"{groesse/1024:.1f} KB für 900 Antworten")

            # Dauer einer Übertragung
            t0 = time.time()
            page.evaluate("async () => { await syncNow(true); }")
            page.wait_for_timeout(200)
            add("Eine Übertragung bleibt unter 2 Sekunden", time.time() - t0 < 2.0,
                f"{time.time()-t0:.2f} s")

            # Der Takt: Der Fortschritt muss das Gerät verlassen, BEVOR die
            # Sitzung endet. Bricht das Kind mittendrin ab, wäre sonst alles
            # bis dahin ungesehen.
            mitten = page.evaluate(f"""async () => {{
              S = freshState(); S.server = '127.0.0.1:{PORT}'; save();
              startUnit(nextUnit().id);
              // drei Aufgaben beantworten, Sitzung bewusst NICHT beenden
              for(let k = 0; k < 3; k++){{
                if(!SESS) break;
                grade(true);
                SESS.i++; Object.assign(SESS, {{answered:false, typed:''}});
              }}
              const vorTakt = S.log.ev.filter(e => e.e === 'a').length;
              SYNC.naechster = 0;
              syncTakt();
              await new Promise(r => setTimeout(r, 900));
              return {{vorTakt, offen: S.log.ev.length, laeuftNoch: !!SESS}};
            }}""")
            add("Mitten in der Sitzung sind Antworten aufgelaufen",
                mitten["vorTakt"] >= 3, f'{mitten["vorTakt"]} Antworten')
            add("Die Sitzung läuft dabei noch", mitten["laeuftNoch"])
            add("Der Takt überträgt sie, ohne das Sitzungsende abzuwarten",
                mitten["offen"] == 0, f'{mitten["offen"]} noch offen')

            # Scheitert es, wird der Abstand gestreckt statt stur weiterzuklopfen.
            backoff = page.evaluate("""async () => {
              S.server = '10.255.255.1:9'; save();
              SYNC.fehler = 0; SYNC.naechster = 0;
              const t = [];
              for(let k = 0; k < 2; k++){
                await syncNow(true);
                t.push({fehler: SYNC.fehler, wartet: SYNC.naechster - Date.now()});
                SYNC.naechster = 0;
              }
              return t;
            }""")
            add("Ein Fehlschlag wird gezählt",
                backoff[0]["fehler"] == 1 and backoff[1]["fehler"] == 2)
            add("Und der nächste Versuch rückt weiter weg",
                backoff[1]["wartet"] > backoff[0]["wartet"],
                f'{backoff[0]["wartet"]/1000:.0f} s → {backoff[1]["wartet"]/1000:.0f} s')

            # Zurücksetzen darf den Strom nicht durcheinanderbringen.
            alt = page.evaluate("() => S.dev")
            page.evaluate("() => { S = freshState(); save(); }")
            neu = page.evaluate("() => S.dev")
            add("Nach dem Zurücksetzen beginnt ein eigener Strom",
                neu != alt and len(neu) == 16, f"{alt[:6]}… -> {neu[:6]}…")

            add("keine JS-Fehler", not errs, errs[0][:70] if errs else "")
            b.close()
    finally:
        dienst.terminate()
        dienst.wait(timeout=5)
        shutil.rmtree(tele, ignore_errors=True)

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, info in RESULTS:
        print(f'{"✅" if ok else "❌"} {name}' + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS)-len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


def _wirft_400(daten):
    try:
        post("/sync", daten)
        return False
    except urllib.error.HTTPError as e:
        return e.code == 400


if __name__ == "__main__":
    sys.exit(main())
