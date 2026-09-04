# -*- coding: utf-8 -*-
"""Prüft den deterministischen Nim-Kern (spiel_kern.py).

Im selben Geist wie raetsel_kern_test.py: eine große Menge frisch erzeugter
Nim-Aufgaben muss ausnahmslos in Ordnung sein, und absichtlich kaputte
Aufgaben müssen ausnahmslos erkannt werden. Die Gewinnstrategie wird hier
sogar DREIFACH unabhängig berechnet: einmal beim Erzeugen (spiel_kern.py,
Modulo-Formel), einmal beim Prüfen (spiel_kern.py, Rückwärtsinduktion) und
hier im Test noch ein drittes Mal (eigene, komplett separat geschriebene
Rückwärtsinduktion) – ein Fehler müsste sich also in drei unabhängigen
Rechnungen gleich falsch wiederholen, um unentdeckt zu bleiben.

  .venv/bin/python build/spiel_kern_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spiel_kern as S

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


def eigene_gewinntabelle(n, k):
    """Rückwärtsinduktion, komplett unabhängig von spiel_kern._gewinntabelle
    neu geschrieben: gewinnt[0] = False (wer bei 0 Steinen ziehen soll, hat
    schon verloren); gewinnt[i] = True, sobald irgendein Zug 1..min(k, i)
    den Gegner in eine Stellung mit gewinnt[...] == False zwingt.
    """
    gewinnt = [False] * (n + 1)
    for i in range(1, n + 1):
        kann_gewinnen = False
        for m in range(1, min(k, i) + 1):
            if not gewinnt[i - m]:
                kann_gewinnen = True
                break
        gewinnt[i] = kann_gewinnen
    return gewinnt


# ==================================================== Nim: viele Aufgaben

def nim_serie(stufe, schwierigkeit, anzahl_seeds):
    """Erzeugt anzahl_seeds Nim-Aufgaben für eine Stufe/Schwierigkeit-
    Kombination und prüft für jede zweierlei, komplett unabhängig
    voneinander: dass spiel_kern.pruefe_nim() sie akzeptiert, UND dass die
    eigene, hier im Test neu geschriebene Rückwärtsinduktion bestätigt: die
    Stellung, in der das Kind zieht, ist eine Gewinnstellung, 'zug' ist
    darin der einzige Gewinnzug, und 'rest' ist eine Verluststellung für
    den Gegner.

    Rückgabe: (geprüft, bestanden, erster Fehler als Text).
    """
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        a = S.erzeuge_nim(stufe, seed, schwierigkeit)
        geprueft += 1
        fehler = None
        kontext = f"stufe={stufe} schwierigkeit={schwierigkeit} seed={seed}"

        ok_kern, grund = S.pruefe_nim(a)
        if not ok_kern:
            fehler = f"{kontext}: pruefe_nim lehnt eine selbst erzeugte Aufgabe ab ({grund})"
        else:
            k = a["k"]
            n_kind = a["n_nach_gegner"] if a["variante"] == "gegner" else a["n"]
            if a["rest"] != n_kind - a["zug"]:
                fehler = f"{kontext}: rest ({a['rest']}) ≠ n_kind - zug ({n_kind - a['zug']})"
            else:
                gewinnt = eigene_gewinntabelle(n_kind, k)
                if not gewinnt[n_kind]:
                    fehler = f"{kontext}: eigene Rückwärtsinduktion sagt, n_kind={n_kind} ist gar keine Gewinnstellung"
                else:
                    gewinnzuege = [m for m in range(1, min(k, n_kind) + 1) if not gewinnt[n_kind - m]]
                    if gewinnzuege != [a["zug"]]:
                        fehler = (f"{kontext}: eigene Rückwärtsinduktion findet Gewinnzüge {gewinnzuege}, "
                                  f"nicht nur den angegebenen zug={a['zug']}")
                    elif gewinnt[a["rest"]]:
                        fehler = f"{kontext}: eigene Rückwärtsinduktion sagt, rest={a['rest']} ist noch eine Gewinnstellung"

        if fehler:
            erster_fehler = erster_fehler or fehler
        else:
            bestanden += 1
    return geprueft, bestanden, erster_fehler


GESAMT_NIM = 0
GESAMT_BESTANDEN_NIM = 0
for stufe in (5, 6):
    for schwierigkeit in (0, 2, 4):
        geprueft, bestanden, fehler = nim_serie(stufe, schwierigkeit, anzahl_seeds=60)
        GESAMT_NIM += geprueft
        GESAMT_BESTANDEN_NIM += bestanden
        ok(f"{geprueft} Nim-Aufgaben (Stufe {stufe}, Schwierigkeit {schwierigkeit}): "
           f"Gewinnzug eindeutig, Rest ist Verluststellung",
           geprueft == bestanden, fehler)

ok(f"insgesamt {GESAMT_NIM} Nim-Aufgaben über beide Stufen und drei Schwierigkeiten erzeugt",
   GESAMT_NIM >= 360 and GESAMT_BESTANDEN_NIM == GESAMT_NIM,
   f"{GESAMT_BESTANDEN_NIM}/{GESAMT_NIM} bestanden")

# Variantenwahl nach Schwierigkeit, wie in _variante_aus_schwierigkeit dokumentiert.
for schwierigkeit, erwartete_variante in ((0, "zug"), (1, "zug"), (2, "rest"), (3, "rest"), (4, "gegner"), (5, "gegner")):
    a = S.erzeuge_nim(5, seed=7, schwierigkeit=schwierigkeit)
    ok(f"Schwierigkeit {schwierigkeit} wählt Variante '{erwartete_variante}'",
       a["variante"] == erwartete_variante, str(a))

# Reproduzierbarkeit: derselbe Seed liefert byte-gleich dieselbe Aufgabe.
gleich_a = S.erzeuge_nim(6, seed=2026, schwierigkeit=4)
gleich_b = S.erzeuge_nim(6, seed=2026, schwierigkeit=4)
ok("gleicher Seed liefert byte-gleiche Nim-Aufgabe", gleich_a == gleich_b)

verschieden = S.erzeuge_nim(6, seed=2027, schwierigkeit=4)
ok("unterschiedlicher Seed liefert eine andere Nim-Aufgabe", gleich_a != verschieden)

# Bereichsgrenzen aus der Spezifikation (Stufe 5: k=2, n ∈ 5..15; Stufe 6: k=3, n ∈ 7..20).
def bereich_haelt(stufe, k_erwartet, n_min, n_max):
    for seed in range(60):
        a = S.erzeuge_nim(stufe, seed=seed, schwierigkeit=seed % 6)
        if not (a["k"] == k_erwartet and n_min <= a["n"] <= n_max):
            return False, str(a)
    return True, ""


bestanden, info = bereich_haelt(5, 2, 5, 15)
ok("Stufe 5 hält k=2 und n ∈ 5..15 ein (60 Seeds)", bestanden, info)

bestanden, info = bereich_haelt(6, 3, 7, 20)
ok("Stufe 6 hält k=3 und n ∈ 7..20 ein (60 Seeds)", bestanden, info)

try:
    S.erzeuge_nim(7, seed=1, schwierigkeit=0)
    ok("erzeuge_nim lehnt stufe=7 mit ValueError ab", False)
except ValueError:
    ok("erzeuge_nim lehnt stufe=7 mit ValueError ab", True)


# ======================================================= Nim: kaputte Fälle
# Handgebaute Aufgaben, die pruefe_nim() erkennen MUSS. Ausgangspunkt ist die
# von Hand nachgerechnete Gewinnstellung n=7, k=2 (7 mod 3 = 1, einziger
# Gewinnzug ist also 1, der Gegner bleibt bei 6 Steinen – 6 mod 3 = 0, eine
# Verluststellung).
GUELTIG_7_2 = {"n": 7, "k": 2, "zug": 1, "rest": 6, "variante": "zug", "gegner_nimmt": None, "stufe": 5}

ok_kern, grund = S.pruefe_nim(GUELTIG_7_2)
ok("die von Hand nachgerechnete Beispielaufgabe (n=7, k=2, zug=1) wird akzeptiert",
   ok_kern, grund)

falscher_zug = dict(GUELTIG_7_2, zug=2, rest=5)  # 2 ist ein Zug, aber nicht der einzige Gewinnzug (7-2=5 ist Gewinnstellung)
ok_kern, grund = S.pruefe_nim(falscher_zug)
ok("Negativfall 'falscher Zug': ein Zug, der den Gegner nicht in eine Verluststellung schickt, wird abgelehnt",
   not ok_kern, grund)

verluststellung = dict(GUELTIG_7_2, n=6, rest=5)  # 6 mod 3 = 0: das Kind steht schon vor einer Verluststellung
ok_kern, grund = S.pruefe_nim(verluststellung)
ok("Negativfall 'Verluststellung': eine Aufgabe, in der das Kind schon verloren hat, wird abgelehnt",
   not ok_kern, grund)

k_ausserhalb = dict(GUELTIG_7_2, k=0)
ok_kern, grund = S.pruefe_nim(k_ausserhalb)
ok("Negativfall 'k außerhalb': k=0 (keine erlaubte Zugweite mehr) wird abgelehnt",
   not ok_kern, grund)

k_negativ = dict(GUELTIG_7_2, k=-1)
ok_kern, grund = S.pruefe_nim(k_negativ)
ok("Negativfall 'k außerhalb': ein negatives k wird abgelehnt",
   not ok_kern, grund)

rest_falsch = dict(GUELTIG_7_2, rest=5)  # 7 - 1 = 6, nicht 5
ok_kern, grund = S.pruefe_nim(rest_falsch)
ok("Negativfall 'rest falsch': ein rest, der nicht zu n - zug passt, wird abgelehnt",
   not ok_kern, grund)

zug_ausserhalb_k = dict(GUELTIG_7_2, zug=3, rest=4)  # 3 > k=2, kein erlaubter Zug
ok_kern, grund = S.pruefe_nim(zug_ausserhalb_k)
ok("ein Zug größer als k wird abgelehnt", not ok_kern, grund)

ok_kern, grund = S.pruefe_nim({"n": "sieben", "k": 2, "zug": 1, "rest": 6, "variante": "zug"})
ok("eine kaputte Steinzahl (Text statt Zahl) stürzt nicht ab, sondern wird abgelehnt",
   not ok_kern, grund)

ok_kern, grund = S.pruefe_nim({"typ": "unbekannt"})
ok("eine Aufgabe ganz ohne die erwarteten Felder stürzt nicht ab, sondern wird abgelehnt",
   not ok_kern, grund)

ok_kern, grund = S.pruefe_nim("das ist kein dict")
ok("eine Nicht-dict-Eingabe stürzt nicht ab, sondern wird abgelehnt",
   not ok_kern, grund)

ok_kern, grund = S.pruefe_nim(dict(GUELTIG_7_2, variante="unbekannt"))
ok("eine unbekannte Variante wird abgelehnt", not ok_kern, grund)

# gegner-Variante: von Hand nachgerechnet. n=9, k=2, Gegner nimmt g=2 → n'=7
# (dieselbe Stellung wie oben: einziger Gewinnzug 1, rest 6).
GUELTIG_GEGNER = {"n": 9, "k": 2, "zug": 1, "rest": 6, "variante": "gegner",
                  "gegner_nimmt": 2, "n_nach_gegner": 7, "stufe": 5}
ok_kern, grund = S.pruefe_nim(GUELTIG_GEGNER)
ok("die von Hand nachgerechnete gegner-Aufgabe (n=9, g=2 → n'=7) wird akzeptiert",
   ok_kern, grund)

gegner_ausserhalb = dict(GUELTIG_GEGNER, gegner_nimmt=5)  # 5 > k=2
ok_kern, grund = S.pruefe_nim(gegner_ausserhalb)
ok("ein gegner_nimmt-Wert außerhalb 1..k wird abgelehnt", not ok_kern, grund)

n_nach_gegner_falsch = dict(GUELTIG_GEGNER, n_nach_gegner=8)  # 9 - 2 = 7, nicht 8
ok_kern, grund = S.pruefe_nim(n_nach_gegner_falsch)
ok("ein n_nach_gegner, das nicht zu n - gegner_nimmt passt, wird abgelehnt",
   not ok_kern, grund)


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
