# -*- coding: utf-8 -*-
"""Prüft den Rechenkern für den Denk-Check (rechen_kern.py).

Die Antwort wird hier ein zweites Mal aus dem Fragetext gelesen und neu
gerechnet (nicht aus `check.expr`), dazu zählt der Test die Stellenübergänge
selbst nach. So fällt ein Fehler auf, der in Antwort, Term und Text
gleichermaßen steckt.

  .venv/bin/python build/rechen_kern_test.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rechen_kern as R
import validate as V
import validate_v2 as V2

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


FRAGE = re.compile(r"^([\d.]+) ([+\-×:]) ([\d.]+) = \?$")


def aus_text(q):
    """Liest Zahlen und Rechenzeichen aus dem Fragetext und rechnet selbst."""
    m = FRAGE.match(q)
    if not m:
        return None
    a, op, b = int(m.group(1).replace(".", "")), m.group(2), int(m.group(3).replace(".", ""))
    return a, op, b, {"+": a + b, "-": a - b, "×": a * b, ":": a / b if b else None}[op]


def uebergang_plus(a, b):
    return (a % 10) + (b % 10) >= 10


def uebergang_minus(a, b):
    return (a % 10) < (b % 10)


def stufe_pruefen(stufe, a, op, b, erg):
    """Die Eigenschaft der Stufe (Lehrplanstufe), unabhängig nachgeprüft."""
    if stufe == 2:      # ZR 20 mit Übergang
        return (op in "+-" and max(a, b, erg) <= 20
                and (uebergang_plus(a, b) if op == "+" else uebergang_minus(a, b)))
    if stufe == 3:      # ZR 100 mit Übergang oder kleines Einmaleins
        if op == "×":
            return 2 <= a <= 10 and 2 <= b <= 10
        return (op in "+-" and max(a, b, erg) <= 100
                and (uebergang_plus(a, b) if op == "+" else uebergang_minus(a, b)))
    if stufe == 4:      # glatt geteilt oder schwere Reihen, ZR 100
        if op == ":":
            return b <= 10 and a % b == 0 and erg <= 10 and a <= 100
        return op == "×" and 6 <= a <= 9 and 6 <= b <= 9
    if stufe == 5:      # ZR 1000 plus/minus oder mal 10
        if op == "×":
            return b == 10 and 10 < a < 100
        return op in "+-" and 100 < max(a, b) < 1000 and 0 < erg <= 1000 and min(a, b) >= 100
    if stufe == 6:      # zweistellig mal einstellig
        return op == "×" and 10 <= a <= 99 and 2 <= b <= 9
    if stufe == 7:      # ZR 100 000 plus, volle Hunderter
        return op == "+" and a >= 10000 and b >= 10000 and erg <= 100000 and a % 100 == 0 == b % 100
    if stufe == 8:      # zweistellig mal zweistellig
        return op == "×" and 10 <= a <= 99 and 10 <= b <= 99


fehler, n_aufgaben = [], 0
for stufe in range(2, 9):
    for seed in range(40):
        a = R.denkcheck_aufgabe(stufe, seed)
        n_aufgaben += 1
        wo = f"stufe={stufe} seed={seed}"
        gelesen = aus_text(a["q"])
        if gelesen is None:
            fehler.append(f"{wo}: Fragetext nicht im Muster 'a op b = ?': {a['q']!r}")
            continue
        x, op, y, erg = gelesen
        if abs(erg - a["a"]) > 1e-9:
            fehler.append(f"{wo}: Text rechnet {erg}, a={a['a']}")
        if set(a) != {"type", "q", "a", "check", "hint"} or a["type"] != "zahl":
            fehler.append(f"{wo}: Felder {sorted(a)}")
        if not isinstance(a["a"], int) or isinstance(a["a"], bool):
            fehler.append(f"{wo}: a ist keine ganze Zahl")
        if not stufe_pruefen(stufe, x, op, y, erg):
            fehler.append(f"{wo}: Eigenschaft der Stufe verletzt: {a['q']}")
        if not a["hint"].strip() or json.loads(json.dumps(a, ensure_ascii=False)) != a:
            fehler.append(f"{wo}: Tipp leer oder nicht JSON-fest")
        # derselbe Term im check
        wert, _ = V.eval_term(a["check"]["expr"])
        if abs(wert - a["a"]) > 1e-9:
            fehler.append(f"{wo}: check.expr ergibt {wert}, a={a['a']}")
        # Rechenlast-Budget D2: hier höchstens 3 Schritte, Deckel der Disziplinen 6
        gut, grund = V2.pruefe_kalkuel(a["check"]["expr"], 6)
        kosten = V2.kalkuel_kosten(a["check"]["expr"])
        if not gut or kosten > 3:
            fehler.append(f"{wo}: Rechenlast {kosten} ({grund})")
ok(f"{n_aufgaben} Aufgaben (Stufe 2..8 x 40 Seeds): Antwort aus dem Fragetext neu gerechnet, "
   f"Eigenschaft der Stufe, Term, Rechenlast <= 3 Schritte", not fehler, "; ".join(fehler[:3]))

# validate.check_task bei der eigenen Stufe: Die Stufen SIND die
# Lehrplanstufen, also darf hier gar nichts zu beanstanden sein.
maengel = [f"stufe={stufe} seed={seed}: {m}"
           for stufe in range(2, 9) for seed in range(20)
           for m in V.check_task(R.denkcheck_aufgabe(stufe, seed), stufe)]
ok("validate.check_task bei der eigenen Stufe: Stufe 2..8 x 20 Seeds ohne jeden Mangel",
   not maengel, "; ".join(maengel[:3]))

ok("Determinismus: gleicher (Stufe, Seed), gleiche Aufgabe",
   all(R.denkcheck_aufgabe(s, sd) == R.denkcheck_aufgabe(s, sd)
       for s in range(2, 9) for sd in range(10)))
ok("verschiedene Seeds liefern verschiedene Aufgaben (je Stufe >= 8 in 12 Seeds)",
   all(len({R.denkcheck_aufgabe(s, sd)["q"] for sd in range(12)}) >= 8 for s in range(2, 9)))
ok("Stufe 3 kennt beide Gestalten: Übergang und Einmaleins",
   {R.denkcheck_aufgabe(3, sd)["q"].split()[1] for sd in range(40)} >= {"+", "-", "×"})
ok("Stufe 4 kennt beide Gestalten: Geteilt und schwere Reihen",
   {R.denkcheck_aufgabe(4, sd)["q"].split()[1] for sd in range(40)} == {":", "×"})
ok("Stufe 5 kennt alle Gestalten: plus, minus und mal 10",
   {R.denkcheck_aufgabe(5, sd)["q"].split()[1] for sd in range(40)} == {"+", "-", "×"})
ok("Stufe 7: große Zahlen mit Tausenderpunkt, Term ohne Punkt",
   all("." in R.denkcheck_aufgabe(7, sd)["q"] and "." not in R.denkcheck_aufgabe(7, sd)["check"]["expr"]
       for sd in range(10)))
ok("Rechenarten steigen: Stufe 2 nur plus/minus, Stufe 6 und 8 nur mal",
   all(R.denkcheck_aufgabe(2, sd)["q"].split()[1] in "+-" for sd in range(20))
   and all(R.denkcheck_aufgabe(6, sd)["q"].split()[1] == "×" for sd in range(20))
   and all(R.denkcheck_aufgabe(8, sd)["q"].split()[1] == "×" for sd in range(20)))
for s in (1, 9):
    try:
        R.denkcheck_aufgabe(s, 0)
        ok(f"denkcheck_aufgabe({s}) lehnt Stufe ab", False)
    except ValueError:
        ok(f"denkcheck_aufgabe({s}) lehnt Stufe ab", True)


# ==================================================================== Ausgabe

def main():
    fails = [r for r in RESULTS if not r[1]]
    for name, good, info in RESULTS:
        mark = "✅" if good else "❌"
        print(f"{mark} {name}" + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
