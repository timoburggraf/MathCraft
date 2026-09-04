# -*- coding: utf-8 -*-
"""Startet die gebaute App mit einem Lernstand der Fassung 1.12 — so, wie er
auf Eriks Gerät vor dem Denkschule-Update lag.

Hintergrund: Am 01.09.2026 legte die Fassung 1.13 die App auf dem Gerät lahm
(schwarzer Bildschirm), weil pruefeRevisionen() beim Start save() aufrief,
bevor die const-Definition ausgeführt war — ein Pfad, der NUR bei bestehendem
Lernstand betreten wird. Alle übrigen Tests starten mit frischem Zustand und
waren für diese Fehlerklasse blind. Dieser Test schließt genau diese Lücke:
Er muss bei jeder Änderung am Lade-/Migrationspfad grün bleiben.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"

JETZT = int(time.time() * 1000)

# Ein realistischer Zustand der Fassung 1.12: gefüllte Einheiten samt Sternen,
# Fertigkeits-Gedächtnis, Ereignispuffer, Elternwünsche und Tutorplan — aber
# OHNE alles, was erst V2 kennt (modus, avatar, wishesDone, rev, sofort, …).
ALTZUSTAND = {
    "v": 1, "dev": "76c78c404d732f19",
    "profile": {"name": "", "xp": 3120, "streak": 0, "bestStreak": 6,
                "lastDay": 20690, "goal": 15, "todayDay": 20690,
                "todayCount": 4, "badges": ["first", "five", "streak3"],
                "lastUnitId": "sach_zuviel@5"},
    "skills": {"plus_bis10": {"l": 4, "d": JETZT, "c": 20, "w": 2, "h": [1, 1, 1, 0, 1]},
               "komb_reihen": {"l": 1, "d": JETZT, "c": 7, "w": 12, "h": [0, 0, 1, 0, 1]},
               "must_verdopp": {"l": 3, "d": JETZT, "c": 18, "w": 3, "h": [1, 1, 1, 1]}},
    "units": {"plus_bis10@1": {"stars": 3, "plays": 2},
              "komb_reihen@5": {"stars": 1, "plays": 12},
              "must_verdopp@5": {"stars": 2, "plays": 3},
              "zahl_bis100@3": {"stars": 3, "plays": 1},
              "sach_zuviel@5": {"stars": 2, "plays": 2}},
    "stats": {"packs": 68, "answers": 570, "correct": 420, "knobel": 30, "bestCombo": 12},
    "typLog": ["zahl", "wahl", "zahl", "wahrfalsch", "zuordnen"] * 10,
    "settings": {"sound": True, "speech": True},
    "log": {"lost": 0, "next": 741,
            "ev": [{"e": "a", "i": 740, "t": JETZT - 86400000, "s": "abc12345",
                    "u": "sach_zuviel@5", "k": "sach_zuviel", "g": 5, "y": "zahl",
                    "o": 1, "ms": 12000, "r": 0, "h": 0}]},
    "wishes": [{"ziel": "skill", "id": "zahl_bis100", "art": "jetzt",
                "t": JETZT - 8 * 86400000, "titel": ""},
               {"ziel": "skill", "id": "komb_reihen", "art": "jetzt",
                "t": JETZT - 8 * 86400000, "titel": ""}],
    "plan": [{"skill": "zahl_bis100", "art": "vor", "gewicht": 1.9, "dosis": 4,
              "wann": "frueh", "grund": "x"},
             {"skill": "mal_rest", "art": "vor", "gewicht": 1.8, "dosis": 4,
              "wann": "frueh", "grund": "y"},
             {"skill": "mal_gross", "art": "ueber", "grund": "z"}],
    # Testnetz-Adresse (RFC 5737) mit gesperrtem Port: Der Sync läuft bewusst
    # ins Leere, damit der Test niemals echte Telemetrie beim Dienst ablegt.
    "server": "192.0.2.1:1",
}

FAELLE, GRUEN = [], 0


def t(name, ok, extra=""):
    global GRUEN
    FAELLE.append(name)
    GRUEN += 1 if ok else 0
    print(("✅" if ok else "❌") + f" {name}" + (f"   ({extra})" if extra else ""))


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        fehler = []
        page.on("pageerror", lambda e: fehler.append(str(e)))
        page.add_init_script(
            f"localStorage.setItem('mathcraft_v1', {json.dumps(json.dumps(ALTZUSTAND))});")
        page.goto(INDEX.as_uri())
        page.wait_for_timeout(2500)

        t("kein JS-Fehler beim Start mit 1.12-Lernstand", not fehler,
          fehler[0][:120] if fehler else "")
        t("die App rendert", page.evaluate(
            "() => !!document.querySelector('#app')"
            " && document.querySelector('#app').children.length > 0"))
        z = page.evaluate("""() => ({
            dev: S.dev, xp: S.profile.xp, modus: S.settings.modus,
            begleiter: S.settings.begleiter, getauft: S.avatar.getauft,
            sterneAlt: S.units['plus_bis10@1'].stars,
            revGemerkt: typeof S.units['plus_bis10@1'].rev,
            wuensche: S.wishes.length, plan: S.plan.length})""")
        t("Geräte-Kennung bleibt erhalten", z["dev"] == "76c78c404d732f19")
        t("XP und Sterne bleiben erhalten", z["xp"] == 3120 and z["sterneAlt"] == 3)
        t("V2-Felder entstehen mit Standardwerten",
          z["modus"] == "v2" and z["begleiter"] is True and z["getauft"] is False)
        t("Paket-Fassungen werden beim ersten Start gemerkt", z["revGemerkt"] == "string")
        t("Wünsche und Plan überleben die Migration",
          z["wuensche"] == 2 and z["plan"] == 3)
        b.close()

    print(f"\n{GRUEN}/{len(FAELLE)} bestanden")
    return 0 if GRUEN == len(FAELLE) else 1


if __name__ == "__main__":
    sys.exit(main())
