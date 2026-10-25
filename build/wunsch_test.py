# -*- coding: utf-8 -*-
"""Prüft Z4 aus ZIELE.md: wirken die Elternwünsche wirklich?

Ein Knopf, der nichts tut, ist schlimmer als keiner — er täuscht Einfluss vor.
Deshalb wird hier nicht geprüft, ob der Wunsch gespeichert wird, sondern ob er
danach die Auswahl auf dem Gerät verändert, im Protokoll auftaucht und sich
zurücknehmen lässt.

  .venv/bin/python build/wunsch_test.py

Der Dienst spricht seit der Sicherheitsumstellung nur noch HTTPS: Die Wünsche
werden über die angemeldete Elternseite gesetzt (Cookie, einmaliges CSRF-Token),
die Ereignisse kommen als signierte Geräteanfrage. Den Dienst dafür startet
HttpsDienst aus eltern_test.py mit Dummy-Geheimnissen auf localhost.
"""
import json
import shutil
import socket
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T
from eltern_test import HttpsDienst

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "index.html"
PORT = 8796

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


def form(pfad, felder):
    """Ein Formular der Elternseite abschicken — angemeldet, mit frischem
    Token; der Status kommt ungefolgt zurück (ob umgeleitet wird, zählt)."""
    return DIENST.formular(pfad, felder).status


DIENST = None


def main():
    from playwright.sync_api import sync_playwright

    if not APP.exists():
        sys.exit("index.html fehlt — zuerst build/build.py laufen lassen.")
    if not frei(PORT):
        sys.exit(f"Port {PORT} ist belegt")

    tele = Path(tempfile.mkdtemp(prefix="mathcraft_wunsch_"))
    sys.path.insert(0, str(ROOT / "build"))
    import curriculum as C

    # Ein Kind, das auf Stufe 1/2 steht — damit ein Wunsch auf Stufe 6 auffällt.
    jetzt = int(time.time() * 1000)
    stufe1 = [s for s in C.SKILLS if s["stage"] <= 2][:3]
    hoch = next(s for s in C.SKILLS if s["stage"] >= 6)
    ev = []
    for i, sk in enumerate(stufe1):
        for k in range(10):
            ev.append({"i": len(ev) + 1, "t": jetzt - (200 - k) * 60000, "s": "aa11",
                       "e": "a", "u": f'{sk["id"]}@{sk["stage"]}', "k": sk["id"],
                       "g": sk["stage"], "y": "zahl", "o": 1 if k < 8 else 0,
                       "ms": 4000, "r": 0, "h": 0})

    global DIENST
    dev = "aa11bb22cc33dd44"
    dienst = DIENST = HttpsDienst(PORT, tele)
    try:
        if not dienst.start():
            sys.exit("HTTPS-Dienst startet nicht")
        add("Die Elternanmeldung klappt mit dem Test-Passwort", dienst.anmelden())
        schluessel = dienst.koppeln(dev)

        r = dienst.signiert(dev, schluessel, "/sync",
                            {"v": 1, "dev": dev, "ev": ev, "stats": {"answers": len(ev)}})
        add("Die Ereignisse des Kindes kommen als signierte Anfrage an",
            r.status == 200 and r.json().get("neu") == len(ev), str(r.status))

        # ------------------------------------------------------ Der Dienst
        add("Ein Wunsch lässt sich setzen",
            form("/wunsch", {"ziel": "skill", "id": hoch["id"], "art": "jetzt"}) == 303)
        add("Ein unbekanntes Ziel wird abgewiesen",
            form("/wunsch", {"ziel": "skill", "id": "gibtsnicht", "art": "mehr"}) == 400)
        add("Eine unbekannte Wunschart wird abgewiesen",
            form("/wunsch", {"ziel": "bereich", "id": C.AREAS[0]["id"], "art": "sofort"}) == 400)

        form("/wunsch", {"ziel": "skill", "id": hoch["id"], "art": "mehr"})
        gespeichert = json.loads((tele / "wuensche.json").read_text("utf-8"))
        add("Ein zweiter Wunsch zum selben Ziel ersetzt den ersten",
            len([w for w in gespeichert if w["id"] == hoch["id"]]) == 1
            and gespeichert[-1]["art"] == "mehr")
        form("/wunsch", {"ziel": "skill", "id": hoch["id"], "art": "jetzt"})

        antw = dienst.signiert(dev, schluessel, "/sync", {"v": 1, "dev": dev, "ev": []}).json()
        add("Der Wunsch geht mit der Sync-Antwort ans Handy",
            any(w["id"] == hoch["id"] and w["art"] == "jetzt" for w in antw["wishes"]),
            json.dumps(antw["wishes"])[:60])

        # ------------------------------------------------- Wirkung im Gerät
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_context(viewport={"width": 393, "height": 873}).new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            T.ohne_dienst(page)
            page.goto(APP.as_uri())
            page.wait_for_timeout(400)

            hat_paket = page.evaluate(
                f"() => DATA.units.some(u => u.skill === '{hoch['id']}')")
            ziel_skill = hoch["id"] if hat_paket else page.evaluate(
                "() => DATA.units[DATA.units.length-1].skill")

            wirkung = page.evaluate(f"""() => {{
              S = freshState(); S.server = ''; save();
              const ohne = nextUnit().skill;
              S.wishes = [{{ziel:'skill', id:'{ziel_skill}', art:'jetzt', t:Date.now()}}];
              save();
              const treffer = [];
              for(let i = 0; i < 2; i++){{
                const w = waehleUnit();
                treffer.push(w.unit.skill);
                if(w.unit.skill === '{ziel_skill}') break;
              }}
              const vorher = S.log.ev.filter(e => e.e === 'd').length;
              startNext(); SESS = null; view = {{name:'home', opts:{{}}}};
              const eintraege = S.log.ev.filter(e => e.e === 'd');
              return {{ohne, treffer, gruende: eintraege.slice(vorher).map(e => e.w)}};
            }}""")
            add("„jetzt dran“ zieht die Fertigkeit spätestens ins 2. Paket",
                ziel_skill in wirkung["treffer"],
                f'ohne Wunsch {wirkung["ohne"]}, mit: {", ".join(wirkung["treffer"])}')
            add("Der Wunsch steht als Begründung im Protokoll",
                "wunsch_jetzt" in wirkung["gruende"], ", ".join(wirkung["gruende"]))

            weg = page.evaluate(f"""() => {{
              S = freshState(); S.server = ''; save();
              const ohne = nextUnit().id;
              const sk = UNITS[ohne].skill;
              S.wishes = [{{ziel:'skill', id:sk, art:'spaeter', t:Date.now()}}];
              save();
              const w = waehleUnit();
              const vorher = S.log.ev.filter(e => e.e === 'd').length;
              startNext(); SESS = null; view = {{name:'home', opts:{{}}}};
              const gruende = S.log.ev.filter(e => e.e === 'd').slice(vorher).map(e => e.w);
              // zurücknehmen: das nächste Paket darf es wieder sein
              S.wishes = []; save();
              return {{ohne, mit: w.unit.id, gruende, zurueck: nextUnit().id}};
            }}""")
            add("„erst später“ schiebt das Paket beiseite", weg["mit"] != weg["ohne"],
                f'{weg["ohne"]} -> {weg["mit"]}')
            add("Auch das steht begründet im Protokoll",
                any(g.startswith("wunsch") for g in weg["gruende"]), ", ".join(weg["gruende"]))
            add("Nach dem Zurücknehmen greift wieder die normale Reihenfolge",
                weg["zurueck"] == weg["ohne"], f'{weg["zurueck"]}')

            # ------------------------------------------------------ A: einmalig
            # Ein „jetzt“-Wunsch erlischt nicht mehr von selbst — er gilt aber
            # als erfüllt, sobald ein Paket der gewünschten Fertigkeit einmal
            # VOLLSTÄNDIG gespielt wurde. Genau das hat vorher gefehlt: „jetzt:
            # komb_reihen“ wurde zwölfmal vorgelegt, obwohl es längst gespielt war.
            einmalig = page.evaluate(f"""() => {{
              S = freshState(); S.server = ''; save();
              const sk = '{ziel_skill}';
              S.wishes = [{{ziel:'skill', id: sk, art:'jetzt', t: Date.now() - 5000}}];
              save();
              const w = waehleUnit();
              const vorAktiv = wunschFuer(w.unit);
              startUnit(w.unit.id);
              while(SESS){{ grade(true); nextTask(); }}   // Paket vollständig, alles richtig
              const nachAktiv = wunschFuer(w.unit);
              const erfuellt = (S.wishesDone||[]).some(d => d.ziel==='skill' && d.id===sk);
              const wEvent = S.log.ev.some(e => e.e === 'w' && e.k === sk);
              return {{skill: w.unit.skill, sk, vorAktiv, nachAktiv, erfuellt, wEvent}};
            }}""")
            add("Der Wunsch zieht eine Fertigkeit mit offenem Paket heran",
                einmalig["skill"] == einmalig["sk"], einmalig["skill"])
            add("Vor dem vollständigen Spiel gilt der Wunsch noch als aktiv",
                einmalig["vorAktiv"] == "jetzt", str(einmalig["vorAktiv"]))
            add("(A) Nach einem vollständig gespielten Paket gilt „jetzt“ als erfüllt "
                "und wird nicht erneut vorgezogen",
                einmalig["nachAktiv"] is None and einmalig["erfuellt"],
                f'wunschFuer={einmalig["nachAktiv"]}, erfuellt={einmalig["erfuellt"]}')
            add("(A) Die Erfüllung erzeugt ein Ereignis für den Dienst",
                einmalig["wEvent"])

            add("keine JS-Fehler", not errs, errs[0][:70] if errs else "")
            b.close()

        # ------------------------------------------------- Warnung und Zahlen
        seite = dienst.get("/eltern").text
        add("Ein Sprung über mehrere Stufen wird gewarnt",
            "Das ist ein Sprung über" in seite and "trotzdem ausgeführt" in seite)
        add("Die Warnung nennt die Stufen", f'Stufe {hoch["stage"]}, er steht bei' in seite,
            f'gewünscht Stufe {hoch["stage"]}')
        add("Die Wirkung des Wunsches steht in Zahlen dabei",
            "seither noch nichts geübt" in seite or "Aufgaben, davon" in seite)
        add("Zurücknehmen ist auf der Seite möglich", 'value="weg"' in seite)
        add("Wünsche lassen sich auch je Welt stellen", 'value="bereich"' in seite)

        form("/wunsch", {"ziel": "skill", "id": hoch["id"], "art": "weg"})
        add("Zurückgenommene Wünsche verschwinden",
            not any(w["id"] == hoch["id"]
                    for w in json.loads((tele / "wuensche.json").read_text("utf-8"))))
    finally:
        dienst.stop()
        shutil.rmtree(tele, ignore_errors=True)

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, info in RESULTS:
        print(f'{"✅" if ok else "❌"} {name}' + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS)-len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
