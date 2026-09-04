# -*- coding: utf-8 -*-
"""Prüft Z2 aus ZIELE.md: sagt die Elternseite die Wahrheit, und zwar lückenlos?

Die Schwellen für „sitzt“ und „hakt“ sind eine Setzung, keine Naturkonstante.
Genau deshalb müssen sie geprüft werden: Verschiebt sie jemand aus Versehen,
ändert sich stillschweigend, was Eltern über ihr Kind erfahren.

  .venv/bin/python build/eltern_test.py
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 8797

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


def antwort(nr, skill, stufe, ok, t, typ="zahl"):
    return {"i": nr, "t": t, "s": "abcd1234", "e": "a", "u": f"{skill}@{stufe}",
            "k": skill, "g": stufe, "y": typ, "o": 1 if ok else 0,
            "ms": 5000, "r": 0, "h": 0}


def main():
    tele = Path(tempfile.mkdtemp(prefix="mathcraft_eltern_"))
    os.environ["MC_TELE"] = str(tele)
    sys.path.insert(0, str(ROOT / "tutor"))
    sys.path.insert(0, str(ROOT / "build"))
    import auswertung as A
    import curriculum as C
    import eltern as E

    jetzt = int(time.time() * 1000)
    tag = 86400000

    # ------------------------------------------------- Schwellen für sich
    ids = [s["id"] for s in C.SKILLS]
    s_sitzt, s_hakt, s_arbeit, s_serie, s_knapp = ids[0], ids[1], ids[2], ids[3], ids[4]
    ev, nr = [], 1

    def reihe(skill, muster, ab):
        nonlocal nr
        for k, ok in enumerate(muster):
            ev.append(antwort(nr, skill, 1, ok, jetzt - (ab - k) * 3600000))
            nr += 1

    reihe(s_sitzt,  [1] * 9 + [0], 40)               # 10 Antworten, 90 % richtig
    reihe(s_hakt,   [1, 0, 0, 1, 0, 0], 30)          # 6 Antworten, 33 % richtig
    reihe(s_arbeit, [1, 1, 0], 20)                   # zu wenige für beide Schwellen
    reihe(s_serie,  [1] * 17 + [0, 0, 0], 15)        # 85 % richtig, aber dreimal daneben
    reihe(s_knapp,  [1] * 9, 10)                     # 100 %, aber nur 9 Antworten

    fert = {f["id"]: f for f in A.fertigkeiten(ev)}
    add("10 Antworten mit 90 % gelten als „sitzt“",
        fert[s_sitzt]["zustand"] == "sitzt", fert[s_sitzt]["zustand"])
    add("6 Antworten mit 33 % gelten als „hakt“",
        fert[s_hakt]["zustand"] == "hakt", fert[s_hakt]["zustand"])
    add("Wenige Antworten gelten als „in Arbeit“",
        fert[s_arbeit]["zustand"] == "arbeit", fert[s_arbeit]["zustand"])
    add("Drei Fehlversuche in Folge schlagen die gute Gesamtquote",
        fert[s_serie]["zustand"] == "hakt",
        f'{fert[s_serie]["zustand"]}, Quote {fert[s_serie]["quote"]:.0%}')
    add("Eine Antwort zu wenig reicht nicht für „sitzt“",
        fert[s_knapp]["zustand"] == "arbeit",
        f'{fert[s_knapp]["n"]} Antworten, {fert[s_knapp]["zustand"]}')
    add("Ungeübtes heißt „noch nicht geübt“, nicht 0 %",
        fert[ids[-1]]["zustand"] == "unberuehrt")

    add("Jede Fertigkeit des Lehrplans kommt genau einmal vor",
        len(fert) == len(C.SKILLS) == len(A.fertigkeiten(ev)),
        f"{len(fert)} von {len(C.SKILLS)}")

    # -------------------------------------------------------------- Verlauf
    v = A.verlauf(ereignisse=ev)
    add(f"Der Verlauf umfasst {A.WOCHEN} Wochen", len(v["wochen"]) == A.WOCHEN)
    add("Jede Welt hat eine Reihe im Verlauf",
        all(len(v["bereiche"][a["id"]]) == A.WOCHEN for a in C.AREAS))
    add("Wochen ohne Aufgaben sind 0 und nicht leer",
        all(w["n"] >= 0 and "quote" in w for w in v["gesamt"]))

    # ------------------------------------------------------------ Nordstern
    sess = [
        {"i": 900, "t": jetzt, "s": "z1", "e": "s", "q": "unit", "n": 10, "c": 8, "ms": 1, "z": 0},
        {"i": 901, "t": jetzt, "s": "z2", "e": "s", "q": "unit", "n": 10, "c": 10, "ms": 1, "z": 0},
        {"i": 902, "t": jetzt, "s": "z3", "e": "s", "q": "unit", "n": 10, "c": 4, "ms": 1, "z": 0},
        {"i": 903, "t": jetzt, "s": "z4", "e": "s", "q": "unit", "n": 3, "c": 3, "ms": 1, "z": 1},
    ]
    n = A.nordstern(ev + sess)
    add("Zielband zählt nur die gewerteten Sitzungen",
        n["gewertet"] == 3 and n["im_band"] == 1, f'{n["im_band"]}/{n["gewertet"]}')
    add("Zu leicht und zu schwer werden getrennt gezählt",
        n["zu_leicht"] == 1 and n["zu_schwer"] == 1)
    add("Kurze Sitzungen zählen als Abbruch",
        n["kurz"] == 1 and abs(n["anteil_kurz"] - .25) < 1e-9, f'{n["anteil_kurz"]:.2f}')

    # ------------------------------------------------------ Die Seite selbst
    if not frei(PORT):
        sys.exit(f"Port {PORT} ist belegt")

    # 90 Tage Daten, damit die Ladezeit unter realistischer Last gemessen wird
    viele, nr2 = [], 1
    for t in range(90):
        for k in range(30):
            viele.append(antwort(nr2, ids[t % len(ids)], 1 + t % 6,
                                 (nr2 % 4) != 0, jetzt - t * tag + k * 60000))
            nr2 += 1
    import speicher as SP
    # Spielername (Elternwunsch 02.09.2026): dieses Gerät trägt einen Namen,
    # damit die Gerätetabelle ihn statt der nackten Kennung zeigen kann.
    SP.schreibe("00aa11bb22cc33dd", viele, {"answers": len(viele), "lost": 0}, jetzt,
                name="Alex")

    # ---------------------------------------------- D6: Motivations-Ereignisse
    # Abbruchgründe ("g") und Spaß-Signale ("f") für den neuen Abschnitt
    # "Wie es ihm damit geht" — dasselbe Paket wie oben (s_hakt@1), damit sich
    # der Fertigkeitstitel im Fließtext wiederfindet.
    mot_unit = f"{s_hakt}@1"
    titel_hakt = next(s["title"] for s in C.SKILLS if s["id"] == s_hakt)
    mot_ev = [
        {"i": 1, "t": jetzt - 2*3600000, "s": "mot1", "e": "g", "u": mot_unit, "w": 3},  # zu schwer
        {"i": 2, "t": jetzt - 1*3600000, "s": "mot1", "e": "g", "u": mot_unit, "w": 2},  # zu langweilig
        {"i": 3, "t": jetzt - 50*60000, "s": "mot1", "e": "f", "u": mot_unit, "w": 3},
        {"i": 4, "t": jetzt - 40*60000, "s": "mot1", "e": "f", "u": mot_unit, "w": 3},
        {"i": 5, "t": jetzt - 30*60000, "s": "mot1", "e": "f", "u": mot_unit, "w": 2},
        {"i": 6, "t": jetzt - 20*60000, "s": "mot1", "e": "f", "u": mot_unit, "w": 1},
        # zwei 0/0-Sitzungen: Paket geöffnet, sofort ohne Antwort wieder verlassen
        {"i": 7, "t": jetzt - 15*60000, "s": "mot2", "e": "s", "q": "unit",
         "u": mot_unit, "n": 0, "c": 0, "ms": 400, "z": 1},
        {"i": 8, "t": jetzt - 10*60000, "s": "mot3", "e": "s", "q": "unit",
         "u": mot_unit, "n": 0, "c": 0, "ms": 400, "z": 1},
    ]
    SP.schreibe("22bb33cc44dd55ee", mot_ev, {"answers": 0}, jetzt)
    # Dieses zweite Gerät dient gleich zweifach: als Spieler mit eigenen,
    # vom ersten Gerät klar unterscheidbaren Ereignissen (keine einzige Antwort, dafür
    # die Motivations-Ereignisse) für die Spieler-Auswahl (Elternwunsch
    # 03.09.2026), und — als ignoriertes Gerät — für die Testgerät-Kennzeichnung.
    SP.ignoriert_setzen("22bb33cc44dd55ee", True)

    dienst = subprocess.Popen(
        [str(ROOT / ".venv/bin/python"), str(ROOT / "tutor/server.py"),
         "--port", str(PORT), "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=dict(os.environ, MC_TELE=str(tele)))
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1)
                break
            except Exception:
                time.sleep(.2)

        t0 = time.time()
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/eltern", timeout=10) as r:
            seite = r.read().decode("utf-8")
        dauer = time.time() - t0
        add("Die Seite lädt bei 90 Tagen Daten unter 1 Sekunde", dauer < 1.0,
            f"{dauer*1000:.0f} ms für {len(viele)} Antworten")

        # --------------------------------------- Spieler-Auswahl (Elternwunsch 03.09.2026)
        # Zwei Geräte mit klar unterscheidbaren Ereignissen: Alex (00aa11bb…,
        # 2700 Antworten, keine Motivations-Ereignisse) gegen das zweite,
        # ignorierte Gerät (22bb33cc…, keine einzige Antwort, dafür die
        # Motivations-Ereignisse von oben).
        kind_kpi = f'>{len(viele)}</b>'
        with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/eltern?spieler=22bb33cc44dd55ee", timeout=10) as r:
            seite_b = r.read().decode("utf-8")
        with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/eltern?spieler=00aa11bb22cc33dd", timeout=10) as r:
            seite_a = r.read().decode("utf-8")
        with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/eltern?spieler=nichtvorhanden999", timeout=10) as r:
            status_unbekannt = r.status
            seite_unbekannt = r.read().decode("utf-8")

        add("(1) Die Auswahl erscheint und listet Geräte mit Namen bzw. Kennung",
            '<select name="spieler"' in seite and 'Alex</option>' in seite
            and '22bb33cc… · Testgerät</option>' in seite)
        add("(2) ?spieler=B zeigt Bs Zahlen und nicht die von A",
            kind_kpi not in seite_b and "0/0-Sitzungen" in seite_b
            and kind_kpi in seite_a and "0/0-Sitzungen" not in seite_a)
        add("(3) Ohne Parameter gewinnt das zählende Gerät mit den meisten Antworten",
            kind_kpi in seite and seite_a == seite)
        add("(4) Ein Testgerät ist wählbar und als solches gekennzeichnet",
            '22bb33cc… · Testgerät</option>' in seite
            and "Testgerät ausgeblendet" in seite_b)
        add("(5) Ein ungültiger spieler-Parameter fällt still auf die Voreinstellung zurück",
            status_unbekannt == 200 and kind_kpi in seite_unbekannt)

        add("Alle Fertigkeiten stehen auf der Seite",
            all(s["title"] in seite for s in C.SKILLS),
            next((s["title"] for s in C.SKILLS if s["title"] not in seite), ""))
        # Weltnamen wie „Plus & Minus“ stehen im HTML als &amp; — richtig so
        add("Jede Welt hat einen Abschnitt",
            all(E.esc(a["title"]) in seite for a in C.AREAS),
            next((a["title"] for a in C.AREAS if E.esc(a["title"]) not in seite), ""))
        for z, text in A.ZUSTAND_TEXT.items():
            add(f'Der Zustand „{text}“ wird benannt', text in seite)
        add("Die Definition von „sitzt“ steht dabei", A.DEFINITION["sitzt"] in seite)
        add("Die Definition von „hakt“ steht dabei", A.DEFINITION["hakt"] in seite)
        add("Das Zielband wird erklärt", "70 bis 85 % richtig" in seite)
        add("Die Vorratslücke wird beziffert",
            "Fertigkeiten ohne ein einziges Paket" in seite)
        add("Die Seite verweist auf ihre eigenen Schwellen", "ZIELE.md" in seite)
        add("Ein Gerät mit Spielername wird namentlich angezeigt",
            "Alex (00aa11bb…)" in seite)

        # ------------------------------------------- D6: "Wie es ihm damit geht"
        add("Der neue Abschnitt 'Wie es ihm damit geht' erscheint",
            "Wie es ihm damit geht" in seite)
        add("Er steht nach 'Kurz gesagt'",
            seite.find("Kurz gesagt") < seite.find("Wie es ihm damit geht"))
        add("Die Wochenmenge wird in ganzen Sätzen genannt",
            "Aufgaben je Woche gerechnet" in seite)
        # Alex’ Gerät (die Standardansicht) hat selbst keine Motivations-Ereignisse
        # — die liegen auf dem zweiten Gerät, geprüft über dessen eigene Ansicht
        # (?spieler=…), denn seit dem spielerspezifischen Umbau (03.09.2026)
        # wertet jede Ansicht nur noch ihr gewähltes Gerät aus.
        add("Die Sofort-Abbrüche (0/0-Sitzungen) werden genannt",
            "0/0-Sitzungen" in seite_b)
        add("Die Abbruchgründe erscheinen im Klartext dessen, was angetippt wurde",
            "zu schwer" in seite_b and "zu langweilig" in seite_b
            and titel_hakt in seite_b)
        add("Die Spaß-Verteilung wird genannt",
            "super" in seite_b and "ging so" in seite_b and "nicht gut" in seite_b)
        add("Die Denkschule-Tabelle mit Antworten und Trefferquote je Disziplin erscheint",
            "Die Denkschule" in seite)

        # Leerer Zustand darf nicht nach 0 % aussehen
        leer = Path(tempfile.mkdtemp(prefix="mathcraft_leer_"))
        alt = SP.TELE
        SP.TELE = leer
        SP._cache["stand"] = None
        A.SP.TELE = leer
        # lehrer.py wird hier zum ersten Mal in diesem Prozess importiert
        # (durch _tutor()) und läse sonst den echten Tutorplan des Projekts
        # ein — mit seinen eigenen, ganz realen Prozentzahlen im Text.
        os.environ["MC_PLAN"] = str(leer / "tutorplan.json")
        s_leer = E.seite()
        add("Ohne Daten steht das da, statt überall 0 %",
            "Noch sind keine Daten angekommen" in s_leer and "0 %" not in s_leer)

        # D6: auch im Leerzustand erscheint der Abschnitt — ehrlich, ohne
        # leere Tabelle oder falsche Null.
        add("'Wie es ihm damit geht' erscheint auch ohne jede Daten",
            "Wie es ihm damit geht" in s_leer)
        add("Zur Wochenmenge steht ein ehrlicher Satz statt einer Zahl",
            "Zur Wochenmenge liegen noch keine Angaben vor." in s_leer)
        add("Zu Sofort-Abbrüchen steht ein ehrlicher Satz",
            "Zu Sofort-Abbrüchen liegen noch keine Angaben vor." in s_leer)
        add("Zu Abbruchgründen steht ein ehrlicher Satz",
            "Abbruchgründe hat er noch keine genannt." in s_leer)
        add("Zum Spaß-Signal steht ein ehrlicher Satz",
            "Zum Spaß-Signal liegen noch keine Angaben vor." in s_leer)
        add("Die Denkschule-Tabelle bleibt im Leerzustand keine leere Tabelle,"
            " sondern ein ehrlicher Satz",
            "Zur Denkschule liegen noch keine Angaben vor." in s_leer and "<table>" not in
            s_leer[s_leer.find("Die Denkschule"):s_leer.find("Die Denkschule")+600])

        # --------------------------------------------- D: Status je Planposten
        # V0/ZIELE-V2.md: die Elternseite muss je Planposten sagen, ob er
        # gestellt wurde, verweigert wird, noch nicht dran war oder gar nicht
        # mehr stellbar ist — sonst bleibt unsichtbar, dass ein Plan wirkungslos
        # verpufft (genau das ist dem Plan vom 26.08. passiert).
        import json as _json
        units_roh = _json.loads((ROOT / "data" / "units_seed.json").read_text("utf-8"))["units"]
        je_fertigkeit = {}
        for un in units_roh:
            je_fertigkeit.setdefault(un["skill"], []).append(f'{un["skill"]}@{un["stage"]}')
        unversorgt = [s["id"] for s in A.vorratsdeckung()["liste"]]
        kandidaten = [i for i in ids if i in je_fertigkeit]
        sk_gestellt, sk_verweigert, sk_dran = kandidaten[0], kandidaten[1], kandidaten[2]
        sk_keins = unversorgt[0] if unversorgt else kandidaten[3]

        planzeit = jetzt - 5 * 3600000
        d_tele = Path(tempfile.mkdtemp(prefix="mathcraft_status_"))
        SP.TELE = d_tele
        SP._cache["stand"] = None
        A.SP.TELE = d_tele

        d_ev, nr3 = [], 1
        d_ev.append(antwort(nr3, sk_gestellt, 1, True, planzeit + 60000)); nr3 += 1
        unit_verweigert = je_fertigkeit[sk_verweigert][0]
        for k in range(2):
            d_ev.append({"i": nr3, "t": planzeit + 60000 * (k + 1), "s": "d3v1x", "e": "s",
                         "q": "unit", "u": unit_verweigert, "n": 0, "c": 0, "ms": 500, "z": 1})
            nr3 += 1
        offen_ids = je_fertigkeit.get(sk_dran, []) + je_fertigkeit.get(sk_verweigert, [])
        SP.schreibe("ff001122334455aa", d_ev, {"answers": len(d_ev), "offen": offen_ids}, jetzt)

        # dieselbe Datei, auf die MC_PLAN weiter oben schon isoliert wurde
        (leer / "tutorplan.json").write_text(_json.dumps({
            "t": planzeit, "datum": "01.09.2026 00:00",
            "beobachtung": "Testbeobachtung.", "eltern": "Testabsatz.",
            "plan": [
                {"skill": sk_gestellt, "art": "vor", "grund": "Testgrund"},
                {"skill": sk_verweigert, "art": "vor", "grund": "Testgrund"},
                {"skill": sk_dran, "art": "vor", "grund": "Testgrund"},
                {"skill": sk_keins, "art": "vor", "grund": "Testgrund"},
            ],
            "erzeugen": [], "grundlage": {"antworten": 10, "ereignisse": 10},
            "kosten": {}, "hinweise": [],
        }, ensure_ascii=False), "utf-8")

        # dieselben Wünsche-Zustände, dieselben Sofort-Abbrüche
        SP.wunsch_setzen("skill", sk_gestellt, "jetzt", planzeit)
        SP.wunsch_erfuellen("skill", sk_gestellt, planzeit, jetzt)
        SP.wunsch_setzen("skill", sk_verweigert, "jetzt", planzeit)
        SP.wunsch_setzen("skill", sk_dran, "jetzt", planzeit)

        seite_status = E.seite()
        add("(D) Ein gestellter Planposten wird als solcher erkannt",
            "seit diesem Plan: gestellt" in seite_status)
        add("(D) Eine Verweigerung wird erkannt",
            "seit diesem Plan: verweigert" in seite_status)
        add("(D) Ein noch nicht gestellter Planposten wird erkannt",
            "seit diesem Plan: noch nicht dran" in seite_status)
        add("(D) Ein nicht stellbarer Planposten wird erkannt",
            "nicht stellbar — kein offenes Paket" in seite_status)
        add("(D) Ein erfüllter Wunsch zeigt sein Erfüllungsdatum",
            "erfüllt am " in seite_status)
        add("(D) Ein verweigerter Wunsch wird als solcher erkannt",
            "wird verweigert (" in seite_status and "weggetippt" in seite_status)
        add("(D) Ein wirkender Wunsch wird als solcher erkannt",
            "wirkt</span>" in seite_status)

        SP.wunsch_loeschen("skill", sk_gestellt)
        SP.wunsch_loeschen("skill", sk_verweigert)
        SP.wunsch_loeschen("skill", sk_dran)
        shutil.rmtree(d_tele, ignore_errors=True)

        SP.TELE = alt
        SP._cache["stand"] = None
        shutil.rmtree(leer, ignore_errors=True)
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
