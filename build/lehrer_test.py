# -*- coding: utf-8 -*-
"""Prüft den Tutor, der selbst entscheidet.

Kein Aufruf ans Modell — was hier interessiert, ist nicht, ob es klug
entscheidet, sondern ob seine Entscheidung durchkommt.

Der wichtigste Fall steht deshalb ganz oben: Ein kühner Plan darf NICHT
abgeschwächt werden. Will der Tutor eine Fertigkeit sechs Stufen über dem
Stand des Kindes, dann bekommt er sie, und die Elternseite zeigt den Sprung
an, statt ihn zu verhindern. Alles andere wäre eine Attrappe von Freiheit.

Was geprüft wird, ist die Betriebssicherheit drumherum: dass ein erfundener
Bezeichner nicht die Auswahl leerlaufen lässt, dass er trotzdem sichtbar wird,
dass jede Entscheidung im Protokoll landet, und dass ein Elternwunsch gewinnt.

  .venv/bin/python build/lehrer_test.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "index.html"
PORT = 8793

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


def main():
    from playwright.sync_api import sync_playwright

    if not APP.exists():
        sys.exit("index.html fehlt — zuerst build/build.py laufen lassen.")
    if not frei(PORT):
        sys.exit(f"Port {PORT} ist belegt")

    tele = Path(tempfile.mkdtemp(prefix="mathcraft_lehrer_"))
    planfile = tele / "plan.json"
    os.environ["MC_TELE"] = str(tele)
    os.environ["MC_PLAN"] = str(planfile)
    sys.path.insert(0, str(ROOT / "tutor"))
    sys.path.insert(0, str(ROOT / "build"))
    import curriculum as C
    import lehrer as L

    niedrig = next(s for s in C.SKILLS if s["stage"] <= 2)
    hoch = next(s for s in C.SKILLS if s["stage"] >= 7)

    # ------------------------------------------- Der kühne Plan bleibt kühn
    kuehn = {
        "beobachtung": "Er löst Knobelaufgaben auf Anhieb.",
        "eltern": "Ich probiere etwas weit über seinem Stand.",
        "plan": [{"skill": hoch["id"], "art": "vor",
                  "grund": "Weit über seinem Niveau. Ich will sehen, wie weit das trägt."}],
        "erzeugen": [],
    }
    sauber, hinweise = L.saeubere(kuehn)
    add("Ein Sprung weit über das Niveau wird NICHT abgeschwächt",
        len(sauber["plan"]) == 1 and sauber["plan"][0]["skill"] == hoch["id"],
        f'{hoch["id"]} (Stufe {hoch["stage"]}) bleibt drin')
    add("Und es gibt dazu keine Beanstandung", not hinweise, "; ".join(hinweise))
    add("Seine Begründung wird nicht gekürzt oder umformuliert",
        sauber["plan"][0]["grund"].startswith("Weit über seinem Niveau"))

    # ---------------------------------- Nur kaputte Verweise fallen weg
    kaputt = {"beobachtung": "x", "eltern": "y", "erzeugen": [],
              "plan": [{"skill": "gibtsnicht", "art": "vor", "grund": "a"},
                       {"skill": niedrig["id"], "art": "erfunden", "grund": "b"},
                       {"skill": niedrig["id"], "art": "ueber", "grund": "c"}]}
    sauber2, hinweise2 = L.saeubere(kaputt)
    add("Eine erfundene Fertigkeit fällt weg", len(sauber2["plan"]) == 1)
    add("Und wird dabei benannt, nicht verschwiegen",
        any("gibtsnicht" in h for h in hinweise2), "; ".join(hinweise2))
    add("Eine erfundene Entscheidungsart fällt weg",
        any("erfunden" in h for h in hinweise2))
    add("Der brauchbare Rest bleibt", sauber2["plan"][0]["art"] == "ueber")

    add("Mehr als 15 Entscheidungen werden gekappt",
        len(L.saeubere({"beobachtung": "", "eltern": "", "erzeugen": [],
                        "plan": [{"skill": niedrig["id"], "art": "vor", "grund": "x"}] * 40
                        })[0]["plan"]) == L.MAX_PLAN)

    # ------------------------------------------------- D3: Pre-Lesson-Kette
    ziel = next(s for s in C.SKILLS if s["id"] != niedrig["id"])
    kette = {"beobachtung": "x", "eltern": "y", "erzeugen": [], "plan": [
        {"skill": niedrig["id"], "art": "vor", "grund": "Vorlauf.", "fuer": ziel["id"]},
        {"skill": ziel["id"], "art": "vor", "grund": "Das eigentliche Ziel."},
    ]}
    sauber3, hinweise3 = L.saeubere(kette)
    add("Ein 'fuer' auf eine bekannte Fertigkeit wird angenommen und weitergereicht",
        sauber3["plan"][0]["fuer"] == ziel["id"], sauber3["plan"][0])
    add("Ein Posten ohne 'fuer' bekommt ein leeres Feld, keinen Fehler",
        sauber3["plan"][1]["fuer"] == "", sauber3["plan"][1])
    add("Dazu gibt es keine Beanstandung", not hinweise3, "; ".join(hinweise3))

    kette_kaputt = {"beobachtung": "x", "eltern": "y", "erzeugen": [], "plan": [
        {"skill": niedrig["id"], "art": "vor", "grund": "Vorlauf.", "fuer": "gibtsnicht"},
        {"skill": niedrig["id"], "art": "zurueck", "grund": "z", "fuer": ziel["id"]},
    ]}
    sauber4, hinweise4 = L.saeubere(kette_kaputt)
    add("Eine unbekannte Ziel-Fertigkeit im Vorlauf wird toleriert und benannt, "
        "reißt den Posten aber nicht mit",
        len(sauber4["plan"]) == 2 and sauber4["plan"][0]["fuer"] == "",
        "; ".join(hinweise4))
    add("Die unbekannte Kennung wird dabei genannt",
        any("gibtsnicht" in h for h in hinweise4), "; ".join(hinweise4))
    add("'fuer' gilt nur bei art=vor — bei anderer Art bleibt es leer, auch wenn "
        "eine bekannte Fertigkeit genannt wurde",
        sauber4["plan"][1]["fuer"] == "")

    # ------------------------------------------------- D6: Motivation im Prompt
    prompt_abschnitt = L.motivationsauszug([], 0)
    add("Der Prompt trägt einen eigenen Abschnitt 'Wie es dem Kind gerade geht'",
        "WIE ES DEM KIND GERADE GEHT" in prompt_abschnitt)
    add("Er nennt die Wochenmenge", "Antworten je Woche" in prompt_abschnitt)
    add("Er nennt die 0/0-Sitzungen", "0/0-Sitzungen" in prompt_abschnitt)
    add("Ohne Ereignisse ist er trotzdem ehrlich, keine Fehlermeldung",
        "Spaß-Signale: noch keine" in prompt_abschnitt
        and "Abbruchgründe: noch keine genannt" in prompt_abschnitt)
    add("Das SYSTEM erklärt das Feld 'fuer' und die Pre-Lesson-Kette",
        '"fuer"' in L.SYSTEM and "Vorlauf" in L.SYSTEM)
    add("Das SYSTEM setzt Motivation als Nordstern, nicht als starre Schwelle",
        "Nordstern" in L.SYSTEM and "verweigert" in L.SYSTEM)
    add("Der volle Auszug enthält den Motivationsabschnitt",
        "WIE ES DEM KIND GERADE GEHT" in L.auszug())

    # ------------------------------------------------------- Wann er denkt
    add("Ohne Verlauf denkt er nicht nach", not L.faellig())

    # ------------------------------------------- Der Dienst mit fertigem Plan
    planfile.write_text(json.dumps({
        "t": int(time.time() * 1000), "datum": "29.07.2026 12:00",
        "beobachtung": "Freitags bricht er ab, und zwar nur bei Sachaufgaben.",
        "eltern": "Rechnen kann er. Lange Texte bremsen ihn.",
        "plan": [
            {"skill": hoch["id"], "art": "vor", "fuer": niedrig["id"],
             "grund": "Weit über seinem Stand, aber Knobeln liegt ihm."},
            {"skill": niedrig["id"], "art": "ueber",
             "grund": "Das sitzt seit Wochen, da ist nichts mehr zu holen."},
            {"skill": "sach_gibtsnicht", "art": "vor", "grund": "Ausgedacht."}],
        "erzeugen": [], "grundlage": {"antworten": 40}, "hinweise": [],
    }, ensure_ascii=False), "utf-8")

    ev = [{"i": i + 1, "t": int(time.time() * 1000) - (60 - i) * 60000, "s": "aa11",
           "e": "a", "u": f'{niedrig["id"]}@{niedrig["stage"]}', "k": niedrig["id"],
           "g": niedrig["stage"], "y": "zahl", "o": 1, "ms": 4000, "r": 0, "h": 0}
          for i in range(40)]

    dienst = subprocess.Popen(
        [sys.executable, str(ROOT / "tutor/server.py"),
         "--port", str(PORT), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=dict(os.environ, MC_TELE=str(tele), MC_PLAN=str(planfile)))
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1)
                break
            except Exception:
                time.sleep(.2)

        r = urllib.request.Request(f"http://127.0.0.1:{PORT}/sync",
                                   data=json.dumps({"v": 1, "dev": "aabb00112233ccdd",
                                                    "ev": ev,
                                                    "stats": {"answers": len(ev)}}).encode(),
                                   headers={"Content-Type": "text/plain"}, method="POST")
        antwort = json.loads(urllib.request.urlopen(r, timeout=15).read())
        add("Der Plan geht mit der Sync-Antwort ans Handy",
            len(antwort.get("plan", [])) == 3,
            f'{len(antwort.get("plan", []))} Punkte')
        add("Und die Begründungen reisen mit",
            all(p.get("grund") for p in antwort.get("plan", [])))
        add("D3: das 'fuer' des Vorlauf-Postens reist mit an die App",
            antwort["plan"][0].get("fuer") == niedrig["id"])

        seite = urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/eltern", timeout=10).read().decode("utf-8")
        add("Die Elternseite gibt seine Beobachtung wieder",
            "Freitags bricht er ab" in seite)
        add("Und seinen Absatz für die Eltern", "Lange Texte bremsen ihn" in seite)
        add("D3: die Elternseite zeigt die Pre-Lesson-Kette (Vorlauf für ...)",
            "Vorlauf für" in seite and niedrig["title"] in seite)
        add("Seine Begründung steht bei der Entscheidung",
            "Knobeln liegt ihm" in seite)
        add("Der Sprung über mehrere Stufen wird angezeigt",
            "Sprung über" in seite)
        add("Aber als Hinweis, nicht als Sperre — die Entscheidung steht trotzdem da",
            "Der Tutor will das so" in seite)
        add("Eine erfundene Fertigkeit wird offengelegt",
            "sach_gibtsnicht" in seite and "nicht alles ausführen" in seite)
        add("Die Eltern können daneben widersprechen", 'value="spaeter"' in seite)

        # ------------------------------------------------- Wirkung im Gerät
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_context(viewport={"width": 393, "height": 873}).new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            T.ohne_dienst(page)
            page.goto(APP.as_uri())
            page.wait_for_timeout(400)

            hat = page.evaluate(f"() => DATA.units.some(u => u.skill === '{hoch['id']}')")
            ziel = hoch["id"] if hat else page.evaluate("() => DATA.units[0].skill")

            wirkung = page.evaluate(f"""() => {{
              S = freshState(); S.server = ''; save();
              const ohne = nextUnit().skill;
              S.plan = [{{skill:'{ziel}', art:'vor', grund:'Weil ich es will.'}}];
              save();
              const mit = waehleUnit();
              const vorher = S.log.ev.filter(e => e.e === 'd').length;
              startNext(); SESS = null; view = {{name:'home', opts:{{}}}};
              const neu = S.log.ev.filter(e => e.e === 'd').slice(vorher);
              return {{ohne, mit: mit.unit.skill, gruende: neu.map(e => e.w)}};
            }}""")
            add("Der Plan des Tutors steuert die Auswahl",
                wirkung["mit"] == ziel,
                f'ohne Plan {wirkung["ohne"]}, mit Plan {wirkung["mit"]}')
            add("Seine Entscheidung landet im Protokoll",
                "tutor" in wirkung["gruende"], ", ".join(wirkung["gruende"]))

            vorrang = page.evaluate(f"""() => {{
              S = freshState(); S.server = ''; save();
              S.plan = [{{skill:'{ziel}', art:'vor', grund:'Ich will das.'}}];
              S.wishes = [{{ziel:'skill', id:'{ziel}', art:'spaeter', t:Date.now()}}];
              save();
              return {{gewaehlt: waehleUnit().unit.skill,
                      plan: !!planFuer(UNITS[Object.keys(UNITS).find(
                        k => UNITS[k].skill === '{ziel}')])}};
            }}""")
            add("Ein Elternwunsch schlägt den Plan des Tutors",
                vorrang["gewaehlt"] != ziel and not vorrang["plan"],
                f'gewählt: {vorrang["gewaehlt"]}')

            leer = page.evaluate("""() => {
              S = freshState(); S.server = ''; save();
              S.plan = [{skill:'gibtsnicht', art:'vor', grund:'x'}]; save();
              const u = nextUnit();
              return !!(u && u.id);
            }""")
            add("Ein kaputter Plan lässt die App nicht leerlaufen", leer)

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


if __name__ == "__main__":
    sys.exit(main())
