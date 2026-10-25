# -*- coding: utf-8 -*-
"""Prüft den deterministischen Figurenkern (figur_kern.py): Punktmuster und Merkbild.

Im selben Geist wie muster_kern_test.py: Zu jeder Wahrheit des Kerns steht hier
ein zweiter, anders geschriebener Weg daneben.
  - Punktmuster: die Punktezahl wird zusätzlich über Zuwächse von Bild zu Bild
    (statt Formel oder Konstruktion) berechnet, und die Kreise im fertigen SVG
    werden gezählt — das Bild muss zur Wahrheit passen, nicht nur der Kern zu
    sich selbst.
  - Merkbild: die Zellen werden aus den Kreisen im SVG zurückgelesen und mit
    dem Kern verglichen; Strukturen (Symmetrie, Treppe, Linien) werden mit
    eigenem, neu geschriebenem Code bestätigt.

  .venv/bin/python build/figur_kern_test.py
"""
import copy
import itertools
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figur_kern as F

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


ERLAUBTE_FARBEN = set(F.PALETTE) | {F.KONTUR, F.RASTER}
HEX_FARBE = re.compile(r"#[0-9a-fA-F]{6}")
NS = "{http://www.w3.org/2000/svg}"


def svg_ok(svg):
    """Formale Anforderungen an jedes SVG; Rückgabe: Mangel oder None."""
    if not svg.startswith("<svg") or "<script" in svg or "<text" in svg:
        return "kein reines SVG ohne Skript/Text"
    wurzel = ET.fromstring(svg)
    if "width" in wurzel.attrib or "height" in wurzel.attrib:
        return "Breite/Höhe am Wurzelelement"
    if not wurzel.get("viewBox"):
        return "keine viewBox"
    fremd = set(HEX_FARBE.findall(svg)) - ERLAUBTE_FARBEN
    if fremd:
        return f"Farben außerhalb der Palette: {fremd}"
    return None


# ================================================================ Punktmuster

def zuwaechse(typ, param, bis):
    """Zweiter Weg zur Punktezahl: Anfangswert plus Zuwächse von Bild zu Bild."""
    zahlen, z = [], None
    for n in range(1, bis + 1):
        if typ == "linear":
            z = param if n == 1 else z + param
        elif typ == "lform":
            z = 3 if n == 1 else z + 2
        elif typ == "rahmen":
            z = 4 if n == 1 else z + 4
        elif typ == "quadrat":
            z = 1 if n == 1 else z + (2 * n - 1)
        elif typ == "rechteck":
            z = 2 if n == 1 else z + 2 * n
        elif typ == "dreieck":
            z = 1 if n == 1 else z + n
        zahlen.append(z)
    return zahlen


fehler = []
for typ in F.TYPEN:
    for param in ((2, 3, 4, 5) if typ == "linear" else (0,)):
        ref = zuwaechse(typ, param, 30)
        for n in range(1, 31):
            if F.formel(typ, param, n) != ref[n - 1]:
                fehler.append(f"Formel {typ}/{param} Bild {n}")
            if len(F.punkte_von(typ, param, n)) != ref[n - 1]:
                fehler.append(f"Konstruktion {typ}/{param} Bild {n}")
            if len(set(F.punkte_von(typ, param, n))) != ref[n - 1]:
                fehler.append(f"doppelter Punkt {typ}/{param} Bild {n}")
ok("alle sechs Typen: Formel, Konstruktion und Zuwachsrechnung stimmen für Bild 1..30",
   not fehler, "; ".join(fehler[:3]))

# Von Hand nachgerechnete Einzelwerte
HAND = [("linear", 2, 4, 8), ("linear", 3, 5, 15), ("lform", 0, 6, 13), ("rahmen", 0, 10, 40),
        ("quadrat", 0, 7, 49), ("rechteck", 0, 10, 110), ("dreieck", 0, 10, 55),
        ("dreieck", 0, 4, 10), ("rahmen", 0, 1, 4)]
for typ, param, n, soll in HAND:
    ok(f"von Hand: {typ} (param {param}) Bild {n} hat {soll} Punkte",
       F.formel(typ, param, n) == soll == len(F.punkte_von(typ, param, n)))
try:
    F.formel("kreis", 0, 3)
    ok("formel lehnt unbekannten Typ ab", False)
except ValueError:
    ok("formel lehnt unbekannten Typ ab", True)

# Richtung je Stufe laut Auftrag
RICHTUNG = {2: "linear", 3: "linear", 4: "lform", 5: "rahmen", 6: "quadrat",
            7: "rechteck", 8: "dreieck"}


def kreise(svg):
    return [(float(c.get("cx")), float(c.get("cy"))) for c in ET.fromstring(svg).iter(NS + "circle")]


fehler, n_aufgaben = [], 0
for stufe in range(2, 9):
    for seed in range(8):
        a = F.erzeuge_punktmuster(stufe, seed)
        n_aufgaben += 1
        k = a["kern"]
        wo = f"stufe={stufe} seed={seed}"
        if not F.pruefe_punktmuster(k)[0]:
            fehler.append(f"{wo}: eigene Aufgabe fällt durch: {F.pruefe_punktmuster(k)[1]}")
        if k["typ"] != RICHTUNG[stufe]:
            fehler.append(f"{wo}: Typ {k['typ']}")
        if a["a"] != zuwaechse(k["typ"], k["param"], k["bild"])[-1] or a["a"] != k["anzahl"]:
            fehler.append(f"{wo}: a={a['a']} weicht von der Zuwachsrechnung ab")
        if a["type"] != "bildzahl" or a["q"] != f"Wie viele Punkte hat Bild {k['bild']}?":
            fehler.append(f"{wo}: type/q: {a['type']} {a['q']!r}")
        m = svg_ok(a["svg"])
        if m:
            fehler.append(f"{wo}: SVG: {m}")
        elif len(kreise(a["svg"])) != sum(zuwaechse(k["typ"], k["param"], 3)):
            fehler.append(f"{wo}: {len(kreise(a['svg']))} Kreise im SVG, erwartet "
                          f"{sum(zuwaechse(k['typ'], k['param'], 3))}")
        if not a["hint"] or json.loads(json.dumps(a, ensure_ascii=False)) != a:
            fehler.append(f"{wo}: Tipp fehlt oder nicht JSON-fest")
        if k["bild"] <= 3:
            fehler.append(f"{wo}: gefragtes Bild {k['bild']} ist nicht weiter als das letzte gezeigte")
ok(f"{n_aufgaben} Punktmuster (Stufe 2..8 x 8 Seeds): prüfbar, Typ nach Richtung, Kreise im SVG "
   f"= Summe der Bilder 1..3, SVG formal sauber", not fehler, "; ".join(fehler[:3]))

ok("Punktmuster: Bild-Nummer steigt mit der Stufe nicht unter die Richtung (Stufe 5: 8..12, Stufe 8: 10..20)",
   all(8 <= F.erzeuge_punktmuster(5, s)["kern"]["bild"] <= 12 for s in range(20))
   and all(10 <= F.erzeuge_punktmuster(8, s)["kern"]["bild"] <= 20 for s in range(20)))
ok("Punktmuster: Determinismus",
   all(F.erzeuge_punktmuster(s, 5) == F.erzeuge_punktmuster(s, 5) for s in range(2, 9)))
ok("Punktmuster: verschiedene Seeds liefern verschiedene Aufgaben (je Stufe >= 3 in 12 Seeds)",
   all(len({json.dumps(F.erzeuge_punktmuster(s, sd), sort_keys=True) for sd in range(12)}) >= 3
       for s in range(2, 9)))
for s in (1, 9):
    try:
        F.erzeuge_punktmuster(s, 0)
        ok(f"erzeuge_punktmuster({s}) lehnt Stufe ab", False)
    except ValueError:
        ok(f"erzeuge_punktmuster({s}) lehnt Stufe ab", True)

# gespiegelte und ungespiegelte Bilder kommen beide vor, die Punktzahl bleibt gleich
spiegel = {F.erzeuge_punktmuster(8, s)["kern"]["spiegel"] for s in range(20)}
ok("Punktmuster: gespiegelte und ungespiegelte Lage kommen vor", spiegel == {True, False})


# ---------------------------------------------------- manipulierte Punktmuster

def pm_ablehnen(name, aendere):
    k = copy.deepcopy(F.erzeuge_punktmuster(6, 1)["kern"])   # Quadrat, Bild 7/8/9
    aendere(k)
    gut, grund = F.pruefe_punktmuster(k)
    ok(f"Punktmuster abgelehnt: {name}", not gut, grund)


gut, grund = F.pruefe_punktmuster(F.erzeuge_punktmuster(6, 1)["kern"])
ok("Ausgangsaufgabe für die Punktmuster-Negativfälle ist in Ordnung", gut, grund)
pm_ablehnen("falsche Antwort", lambda k: k.update(anzahl=k["anzahl"] + 1))
pm_ablehnen("Antwort als Text", lambda k: k.update(anzahl=str(k["anzahl"])))
pm_ablehnen("Antwort als Wahrheitswert", lambda k: k.update(anzahl=True))
pm_ablehnen("anderes gefragtes Bild, gleiche Antwort", lambda k: k.update(bild=k["bild"] + 1))
pm_ablehnen("Typ passt nicht zu den Punkten", lambda k: k.update(typ="dreieck"))
pm_ablehnen("Typ unbekannt", lambda k: k.update(typ="kreis"))
pm_ablehnen("ein Punkt fehlt in Bild 3", lambda k: k["punkte"][2].pop())
pm_ablehnen("ein Punkt zu viel in Bild 2", lambda k: k["punkte"][1].append([9, 9]))
pm_ablehnen("ein Punkt doppelt in Bild 3", lambda k: k["punkte"][2].append(list(k["punkte"][2][0])))
pm_ablehnen("Punkt versetzt", lambda k: k["punkte"][2].__setitem__(0, [7, 7]))
# Das Quadrat ist spiegelsymmetrisch, dort fiele ein falscher Spiegel-Schalter nicht auf;
# darum für diesen Fall das Dreieck nehmen.
dr = copy.deepcopy(F.erzeuge_punktmuster(8, 1)["kern"])
dr["spiegel"] = not dr["spiegel"]
ok("Punktmuster abgelehnt: Spiegelung passt nicht zu den Punkten (Dreieck)",
   not F.pruefe_punktmuster(dr)[0], F.pruefe_punktmuster(dr)[1])
pm_ablehnen("Bilder vertauscht", lambda k: k["punkte"].reverse())
pm_ablehnen("nur zwei Bilder", lambda k: k["punkte"].pop())
pm_ablehnen("gezeigt falsch", lambda k: k.update(gezeigt=[2, 3, 4]))
pm_ablehnen("gefragtes Bild nicht weiter als gezeigt", lambda k: k.update(bild=3, anzahl=9))
pm_ablehnen("gefragtes Bild zu weit", lambda k: k.update(bild=99, anzahl=99 * 99))
pm_ablehnen("param bei Quadrat ungleich 0", lambda k: k.update(param=3))
pm_ablehnen("spiegel als Zahl", lambda k: k.update(spiegel=1))
pm_ablehnen("Punkte keine Paare", lambda k: k["punkte"][0].__setitem__(0, "ab"))
pm_ablehnen("Koordinate als Text", lambda k: k["punkte"][0].__setitem__(0, ["0", "0"]))
pm_ablehnen("art falsch", lambda k: k.update(art="merkbild"))
pm_ablehnen("Stufe ungültig", lambda k: k.update(stufe=12))
ok("Punktmuster abgelehnt: Kern ist kein dict", not F.pruefe_punktmuster("x")[0])
ok("Punktmuster abgelehnt: leerer Kern", not F.pruefe_punktmuster({})[0])
# Linear: falscher Parameter (3 statt 2 Reihen) gegen die gezeigten Punkte
lin = copy.deepcopy(F.erzeuge_punktmuster(2, 0)["kern"])
lin["param"] = 3 if lin["param"] == 2 else 2
ok("Punktmuster abgelehnt: linear mit anderem param als gezeigt", not F.pruefe_punktmuster(lin)[0])

# ============================================================= Pakete must_figur

PAKET_SOLL = {
    7: [("lform", 17), ("rahmen", 40), ("quadrat", 81), ("rechteck", 132),
        ("dreieck", 78), ("rechteck", 182)],
    8: [("lform", 35), ("quadrat", 225), ("rahmen", 100), ("rechteck", 272),
        ("dreieck", 171), ("rechteck", 420)],
}
fehler, n_aufgaben = [], 0
for stage in (7, 8):
    for seed in range(4):
        fragen = []
        for i in range(6):
            a = F.baue_aufgabe("must_figur", stage, i, seed)
            n_aufgaben += 1
            k = a["kern"]
            soll_typ, soll_a = PAKET_SOLL[stage][i]
            wo = f"must_figur@{stage} #{i} seed={seed}"
            if not F.pruefe_punktmuster(k)[0]:
                fehler.append(f"{wo}: {F.pruefe_punktmuster(k)[1]}")
            if k["typ"] != soll_typ or a["a"] != soll_a:
                fehler.append(f"{wo}: Typ {k['typ']} a={a['a']}, erwartet {soll_typ} {soll_a}")
            if svg_ok(a["svg"]):
                fehler.append(f"{wo}: SVG {svg_ok(a['svg'])}")
            if k["stufe"] != stage:
                fehler.append(f"{wo}: stufe {k['stufe']}")
            fragen.append(a["q"])
        if len(set(fragen)) != 6:
            fehler.append(f"must_figur@{stage} seed={seed}: Fragetexte nicht verschieden")
ok(f"{n_aufgaben} must_figur-Aufgaben (Stufe 7/8 x 6 x 4 Seeds): prüfbar, Typen und Antworten "
   f"von Hand nachgerechnet, Fragen im Paket verschieden", not fehler, "; ".join(fehler[:3]))
ok("must_figur: Determinismus",
   all(F.baue_aufgabe("must_figur", st, i, 3) == F.baue_aufgabe("must_figur", st, i, 3)
       for st in (7, 8) for i in range(6)))
ok("must_figur: Stufe 8 fragt weiter als Stufe 7 (größtes gefragtes Bild)",
   max(F.baue_aufgabe("must_figur", 8, i, 0)["kern"]["bild"] for i in range(6))
   > max(F.baue_aufgabe("must_figur", 7, i, 0)["kern"]["bild"] for i in range(6)))
for ung in (("must_figur", 6, 0), ("must_matrix", 7, 0), ("must_figur", 7, 6), ("must_figur", 7, -1)):
    try:
        F.baue_aufgabe(ung[0], ung[1], ung[2], 0)
        ok(f"baue_aufgabe{ung} lehnt Unmögliches ab", False)
    except ValueError:
        ok(f"baue_aufgabe{ung} lehnt Unmögliches ab", True)

# Denk-Check darstellung
dc = [F.denkcheck_punktmuster(s, sd) for s in range(2, 9) for sd in range(3)]
ok("Denk-Check darstellung: Stufe 2..8 x 3 Seeds sind prüfbar und gleich den Erzeugern",
   all(F.pruefe_punktmuster(a["kern"])[0] for a in dc)
   and dc[0] == F.erzeuge_punktmuster(2, 0) and len(dc) == 21)


# ================================================================== Merkbild

def zellen_aus_svg(svg, k):
    """Liest die Punkte aus den Kreisen im SVG zurück (Zelle = Kreismitte / Zellbreite)."""
    z = set()
    for cx, cy in kreise(svg):
        z.add((int(cy // F.M_ZELLE), int(cx // F.M_ZELLE)))
    return frozenset(z)


def eigene_symmetrie(z, k):
    """Unabhängig: spiegelt Punkt für Punkt und sucht das Bild in der Menge."""
    z = set(z)
    for f in (lambda r, c: (r, k - 1 - c), lambda r, c: (k - 1 - r, c),
              lambda r, c: (k - 1 - r, k - 1 - c), lambda r, c: (c, r)):
        if all(f(r, c) in z for r, c in z):
            return True
    return False


def eigene_linien(z):
    """Unabhängig: probiert alle Teilmengen von höchstens drei Strecken, die
    sich aus (Start, Richtung, Länge) ergeben."""
    z = set(z)
    strecken = []
    for (r, c) in z:
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            for laenge in range(2, 6):
                s = {(r + i * dr, c + i * dc) for i in range(laenge)}
                if s <= z:
                    strecken.append(s)
    for m in (1, 2, 3):
        for kombi in itertools.combinations(strecken, m):
            if set().union(*kombi) == z:
                return True
    return False


def eigene_treppe(z):
    """Unabhängig: Spaltenhöhen (und nach dem Kippen Zeilenhöhen) müssen
    1,2,3,… oder 3,2,1 sein, mit gemeinsamer Grundlinie."""
    for lage in (set(z), {(c, r) for r, c in z}):
        cols = sorted({c for _, c in lage})
        if len(cols) < 2 or cols != list(range(cols[0], cols[-1] + 1)):
            continue
        spalten = [sorted(r for r, c in lage if c == col) for col in cols]
        if any(s != list(range(s[0], s[-1] + 1)) for s in spalten):
            continue
        hs = [len(s) for s in spalten]
        if not (hs == list(range(hs[0], hs[0] + len(hs))) or hs == list(range(hs[0], hs[0] - len(hs), -1))):
            continue
        if len({s[0] for s in spalten}) == 1 or len({s[-1] for s in spalten}) == 1:
            return True
    return False


EIGENE = {"symmetrie": lambda z, k: eigene_symmetrie(z, k), "linien": lambda z, k: eigene_linien(z),
          "treppe": lambda z, k: eigene_treppe(z)}
TABELLE = {2: (3, 3), 3: (3, 4), 4: (4, 5), 5: (4, 6), 6: (5, 7), 7: (5, 8), 8: (5, 10)}

fehler, n_aufgaben, muster_gesehen = [], 0, set()
for stufe in range(2, 9):
    for seed in range(25):
        a = F.erzeuge_merkbild(stufe, seed)
        n_aufgaben += 1
        k = a["kern"]
        wo = f"stufe={stufe} seed={seed}"
        gut, grund = F.pruefe_merkbild(k)
        if not gut:
            fehler.append(f"{wo}: eigene Aufgabe fällt durch: {grund}")
            continue
        raster, n = TABELLE[stufe]
        orig = frozenset(map(tuple, k["original"]))
        opts = [frozenset(map(tuple, o)) for o in k["optionen"]]
        if k["raster"] != raster or len(orig) != n:
            fehler.append(f"{wo}: Raster {k['raster']} / {len(orig)} Punkte, erwartet {raster}/{n}")
        if sum(1 for o in opts if o == orig) != 1 or opts[a["richtig"]] != orig:
            fehler.append(f"{wo}: nicht genau eine Option gleich dem Original")
        if len(set(opts)) != 4 or len({len(o) for o in opts}) != 1:
            fehler.append(f"{wo}: Optionen nicht verschieden oder verschieden viele Punkte")
        if a["merken_ms"] != (6000 if stufe <= 4 else 5000) or k["merken_ms"] != a["merken_ms"]:
            fehler.append(f"{wo}: merken_ms {a['merken_ms']}")
        if a["richtig"] != k["richtig"] or a["type"] != "bildwahl" or len(a["optionen_svg"]) != 4:
            fehler.append(f"{wo}: Felder")
        for teil in [a["svg"]] + a["optionen_svg"]:
            if svg_ok(teil):
                fehler.append(f"{wo}: SVG {svg_ok(teil)}")
        if zellen_aus_svg(a["svg"], raster) != orig:
            fehler.append(f"{wo}: Fragebild zeigt nicht das Original")
        for i, o in enumerate(a["optionen_svg"]):
            if zellen_aus_svg(o, raster) != opts[i]:
                fehler.append(f"{wo}: Options-SVG {i} zeigt andere Zellen als der Kern")
        if not EIGENE[k["muster"]](orig, raster):
            fehler.append(f"{wo}: eigene Prüfung findet die Struktur {k['muster']} nicht")
        muster_gesehen.add(k["muster"])
        # Ablenker: ab Stufe 5 nur ein verschobener Punkt, bis Stufe 4 höchstens ein gespiegelter
        diffs = [len(o - orig) for i, o in enumerate(opts) if i != a["richtig"]]
        if stufe >= 5 and diffs != [1, 1, 1]:
            fehler.append(f"{wo}: Ablenker unterscheiden sich um {diffs} Punkte, erwartet 1,1,1")
        if stufe <= 4 and sum(1 for d in diffs if d != 1) > 1:
            fehler.append(f"{wo}: mehr als ein Ablenker mit grobem Unterschied: {diffs}")
        if json.loads(json.dumps(a, ensure_ascii=False)) != a:
            fehler.append(f"{wo}: nicht JSON-fest")
ok(f"{n_aufgaben} Merkbilder (Stufe 2..8 x 25 Seeds): prüfbar, genau eine richtige Option, "
   f"SVG = Kern, Struktur mit eigenem Code bestätigt, Ablenker wie beschrieben",
   not fehler, "; ".join(fehler[:3]))
ok("alle drei Strukturarten (Symmetrie, Linien, Treppe) kommen vor", muster_gesehen == set(F.MUSTER))
ok("Merkbild: Determinismus", all(F.erzeuge_merkbild(s, 4) == F.erzeuge_merkbild(s, 4) for s in range(2, 9)))
ok("Merkbild: verschiedene Seeds liefern verschiedene Aufgaben (je Stufe >= 8 in 12 Seeds)",
   all(len({json.dumps(F.erzeuge_merkbild(s, sd), sort_keys=True) for sd in range(12)}) >= 8
       for s in range(2, 9)))
ok("Merkbild: Fragetext kurz und ohne Zahl", re.fullmatch(r"[^\d]{1,80}", F.erzeuge_merkbild(3, 0)["q"]) is not None)
for s in (1, 9):
    try:
        F.erzeuge_merkbild(s, 0)
        ok(f"erzeuge_merkbild({s}) lehnt Stufe ab", False)
    except ValueError:
        ok(f"erzeuge_merkbild({s}) lehnt Stufe ab", True)
dcm = [F.denkcheck_merkbild(s, sd) for s in range(2, 9) for sd in range(3)]
ok("Denk-Check merken: Stufe 2..8 x 3 Seeds prüfbar und gleich dem Erzeuger",
   all(F.pruefe_merkbild(a["kern"])[0] for a in dcm) and dcm[0] == F.erzeuge_merkbild(2, 0))
ok("PRUEFER ordnet beide Arten zu",
   F.PRUEFER == {"punktmuster": F.pruefe_punktmuster, "merkbild": F.pruefe_merkbild})

# ----------------------------------------------- manipulierte Merkbild-Kerne

def mb_ablehnen(name, aendere):
    k = copy.deepcopy(F.erzeuge_merkbild(5, 2)["kern"])
    aendere(k)
    gut, grund = F.pruefe_merkbild(k)
    ok(f"Merkbild abgelehnt: {name}", not gut, grund)


def andere(k, i):
    """Index einer falschen Option."""
    return [j for j in range(4) if j != k["richtig"]][i]


gut, grund = F.pruefe_merkbild(F.erzeuge_merkbild(5, 2)["kern"])
ok("Ausgangsaufgabe für die Merkbild-Negativfälle ist in Ordnung", gut, grund)
mb_ablehnen("zwei Optionen gleich dem Original",
            lambda k: k["optionen"].__setitem__(andere(k, 0), copy.deepcopy(k["original"])))
def original_verschieben(k):
    frei = [[r, c] for r in range(k["raster"]) for c in range(k["raster"])
            if [r, c] not in k["original"]][0]
    k["original"][0] = frei


mb_ablehnen("keine Option gleich dem Original", original_verschieben)
mb_ablehnen("richtig zeigt auf die falsche Option", lambda k: k.update(richtig=andere(k, 0)))
mb_ablehnen("richtig außerhalb", lambda k: k.update(richtig=4))
mb_ablehnen("richtig als Text", lambda k: k.update(richtig="1"))
mb_ablehnen("Optionen doppelt", lambda k: k["optionen"].__setitem__(
    andere(k, 1), copy.deepcopy(k["optionen"][andere(k, 0)])))
mb_ablehnen("nur drei Optionen", lambda k: k["optionen"].pop())
mb_ablehnen("fünf Optionen", lambda k: k["optionen"].append([[0, 0]]))
mb_ablehnen("Option mit anderer Punktzahl", lambda k: k["optionen"][andere(k, 0)].pop())
mb_ablehnen("Zelle außerhalb des Rasters", lambda k: k["optionen"][andere(k, 0)].__setitem__(0, [9, 9]))
mb_ablehnen("Zelle doppelt", lambda k: k["optionen"][andere(k, 0)].__setitem__(
    0, list(k["optionen"][andere(k, 0)][1])))
mb_ablehnen("Zelle als Text", lambda k: k["original"].__setitem__(0, "ab"))
mb_ablehnen("Raster zu groß", lambda k: k.update(raster=6))
mb_ablehnen("Raster zu klein für die Zellen", lambda k: k.update(raster=3))
mb_ablehnen("Muster unbekannt", lambda k: k.update(muster="zufall"))
mb_ablehnen("Muster behauptet, aber nicht vorhanden",
            lambda k: k.update(muster=[m for m in F.MUSTER if m != k["muster"]
                                       and not EIGENE[m](map(tuple, k["original"]), k["raster"])][0]))
mb_ablehnen("Punktzahl passt nicht zur Stufe", lambda k: k.update(stufe=2))
mb_ablehnen("merken_ms passt nicht zur Stufe", lambda k: k.update(merken_ms=6000))
mb_ablehnen("art falsch", lambda k: k.update(art="punktmuster"))
ok("Merkbild abgelehnt: Kern ist kein dict", not F.pruefe_merkbild([])[0])
ok("Merkbild abgelehnt: leerer Kern", not F.pruefe_merkbild({})[0])
ok("Merkbild abgelehnt: Optionen sind keine Liste",
   not F.pruefe_merkbild(dict(F.erzeuge_merkbild(5, 2)["kern"], optionen=None))[0])


# ======================== validate.py kennt die neuen kern.art noch nicht
# Erwartet (AP-3 trägt es nach): bildzahl/bildwahl sind bekannte Typen, nur die
# beiden Kernarten nicht. Diese zwei Meldungen werden ausgefiltert, jede
# andere (Textlänge, Zahlenraum, Feldform …) würde auffallen.
try:
    import validate as V
    ERWARTET = ("bildzahl ohne gültigen 'kern' (kern.art muss 'wuerfelgebaeude' sein)",
                "bildwahl: unbekannte kern.art 'merkbild'")
    fremd = []
    proben = [(a, a["kern"]["stufe"]) for a in dc]
    proben += [(a, a["kern"]["stufe"]) for a in dcm]
    proben += [(F.baue_aufgabe("must_figur", st, i, 1), st) for st in (7, 8) for i in range(6)]
    for a, stufe in proben:
        fremd += [m for m in V.check_task(a, stufe) if m not in ERWARTET]
    ok(f"validate.py: {len(proben)} Aufgaben bestehen alle Prüfungen außer den zwei "
       f"erwarteten Meldungen zu unbekannter kern.art (ausgefiltert)", not fremd, "; ".join(fremd[:3]))
except ImportError as e:
    ok("validate.py importierbar", False, str(e))


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
