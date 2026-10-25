# -*- coding: utf-8 -*-
"""Misst die Textlast der Aufgaben (ZIELE-V3.md, G2) — je Disziplin und gesamt.

Das Kind, für das die App gebaut ist, liest langsam; was ihm gefällt (Roboter,
Spiegeln), hat höchstens zwölf Wörter. Dieses Programm zählt nach, wie viel
vom Vorrat noch Text zum Lesen ist.

Textaufgabe heißt hier (wörtlich aus ZIELE-V3.md): kein Bildtyp
(bildwahl, bildzahl, roboter, positionen, logikgitter, gitter, ordnen, legen)
UND mehr als 12 Wörter in der Frage.

  - "Frage" ist der Fragetext `q`; bei `mehrschritt` zählt die Geschichte samt
    den Fragen der Schritte, denn auch die muss das Kind lesen.
  - Ein Wort ist, was zwischen Leerzeichen steht und mindestens einen
    Buchstaben oder eine Ziffer enthält (Pfeile, "…" und "?" allein zählen
    nicht): "3, 5, 9, 17, … Welche Zahl kommt als Nächstes?" sind 10 Wörter.
  - Die Disziplinen sind die fünf aus disziplinen.py; "Disziplinen gesamt" ist
    alles, was einer davon zugeordnet ist, "alles" der ganze Vorrat.

  .venv/bin/python build/textlast.py                 # data/units_seed.json
  .venv/bin/python build/textlast.py --datei x.json  # ein anderer Stand (Vorher/Nachher)

Rückgabewert 1, wenn der Anteil in den Disziplinen über 35 % liegt (Ziel G2).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import disziplinen as D

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "data" / "units_seed.json"
DENKCHECK = ROOT / "data" / "denkcheck.json"

BILDTYPEN = ("bildwahl", "bildzahl", "roboter", "positionen", "logikgitter", "gitter",
             "ordnen", "legen")
MAX_WOERTER = 12          # darüber ist es eine Textaufgabe (wenn kein Bildtyp)
ZIEL = 0.35               # Obergrenze des Anteils in den Disziplinen


def woerter(text):
    """Zahl der Wörter: Teile zwischen Leerzeichen mit mindestens einem Buchstaben oder einer Ziffer."""
    if not isinstance(text, str):
        return 0
    return sum(1 for w in text.split() if re.search(r"\w", w))


def frage_text(task):
    """Alles, was das Kind zur Frage lesen muss."""
    teile = [task.get("q")]
    if task.get("type") == "mehrschritt":
        teile += [s.get("q") for s in (task.get("steps") or []) if isinstance(s, dict)]
    return " ".join(t for t in teile if isinstance(t, str))


def ist_textaufgabe(task):
    """Kein Bildtyp und mehr als 12 Wörter in der Frage."""
    if not isinstance(task, dict) or task.get("type") in BILDTYPEN:
        return False
    return woerter(frage_text(task)) > MAX_WOERTER


def messen(units):
    """Zählt (Aufgaben, Textaufgaben) je Disziplin, für alle Disziplinen zusammen
    und für alles. Rückgabe: Liste von (Name, Aufgaben, Text), in Tabellenreihenfolge."""
    zaehler = {name: [0, 0] for name in D.DISZIPLINEN}
    pre = [0, 0]
    for u in units:
        name = D.disziplin_von(u.get("skill"))
        ziel = zaehler[name] if name else pre
        for t in u.get("tasks") or []:
            ziel[0] += 1
            ziel[1] += ist_textaufgabe(t)
    zeilen = [(D.DISZIPLINEN[n]["titel"], *zaehler[n]) for n in D.DISZIPLINEN]
    dis = [sum(z[0] for z in zaehler.values()), sum(z[1] for z in zaehler.values())]
    zeilen.append(("Disziplinen gesamt", *dis))
    zeilen.append(("Rechenfertigkeiten (Pre-Lesson)", *pre))
    zeilen.append(("alles", dis[0] + pre[0], dis[1] + pre[1]))
    return zeilen


def tabelle(zeilen, titel):
    print(titel)
    print(f"  {'':34s}{'Aufgaben':>9s}{'Text':>7s}{'Anteil':>8s}")
    for name, n, text in zeilen:
        anteil = f"{100 * text / n:.1f} %" if n else "–"
        trenner = "  " if name not in ("Disziplinen gesamt", "alles") else "» "
        print(f"{trenner}{name:34s}{n:9d}{text:7d}{anteil:>8s}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datei", type=Path, default=UNITS,
                    help="Paketdatei (Standard: data/units_seed.json)")
    a = ap.parse_args()

    units = json.loads(a.datei.read_text("utf-8")).get("units", [])
    zeilen = messen(units)
    tabelle(zeilen, f"Textlast ({a.datei.name}, {len(units)} Pakete)")

    # Zur Information: der Denk-Check soll möglichst ohne Lesen auskommen.
    if DENKCHECK.exists():
        aufgaben = json.loads(DENKCHECK.read_text("utf-8")).get("aufgaben", [])
        text = sum(ist_textaufgabe(x["task"]) for x in aufgaben)
        print(f"\nDenk-Check: {text} von {len(aufgaben)} Aufgaben sind Textaufgaben")

    n, text = next((n, t) for name, n, t in zeilen if name == "Disziplinen gesamt")
    anteil = text / n if n else 0
    print(f"\nDisziplinen: {100 * anteil:.1f} % Textaufgaben (Ziel: höchstens {100 * ZIEL:.0f} %)")
    if anteil > ZIEL:
        print("[xx] Ziel verfehlt")
        return 1
    print("[ok] Ziel erreicht")
    return 0


if __name__ == "__main__":
    sys.exit(main())
