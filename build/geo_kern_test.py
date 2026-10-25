# -*- coding: utf-8 -*-
"""Prüft den Geometrie-Kern (geo_kern.py).

Im Geist von grafik_kern_test.py: Der Kern garantiert, dass jede Aufgabe
lösbar, eindeutig und ablesbar ist. Deshalb steht neben jedem Prüfer des
Kerns eine zweite, UNABHÄNGIG geschriebene Rechnung, die nicht auf dessen
Hilfsfunktionen zurückgreift:

  ansicht      Voxelmenge und Projektion statt Höhenkarten-Maxima; dichte
               Pixelabtastung statt gezielter Abtastpunkte für die Sichtbarkeit
  netzfalten   eigene Hexomino-Aufzählung; Faltung mit 3D-Normalenvektoren
               statt Würfelabrollen
  gitterfigur  Umfang über Kanten, die genau einmal vorkommen; Fläche über
               die Gaußsche Trapezformel
  quader       Voxelmenge, Sichtbarkeit wie bei ansicht
  karte        Wegesuche als Relaxation statt Breitensuche; Schritte Feld für Feld

  .venv/bin/python build/geo_kern_test.py
"""
import copy
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo_kern as G
import grafik_kern as GK
import validate as V

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


SEEDS = (0, 1, 2)
STUFEN = range(3, 9)
INDIZES = range(6)
ERLAUBTE_FARBEN = {f.lower() for f in set(G.PALETTE) | {G.KONTUR, G.RASTER}}
HEX_FARBE = re.compile(r"#[0-9a-fA-F]{6}")

# Meldungen von validate.py, die nur daher kommen, dass AP-3 die neuen kern.art
# noch nicht eingetragen hat. Alles andere zählt als Mangel.
NOCH_UNBEKANNT = (
    re.compile(r"^bildwahl: unbekannte kern\.art "),
    re.compile(r"^bildzahl ohne gültigen 'kern' \(kern\.art muss 'wuerfelgebaeude' sein\)$"),
)


# ================================================================ SVG-Struktur

def svg_probleme(svg, name):
    """Wohlgeformtes XML, quadratische viewBox, kein width/height, kein Text,
    keine Skripte, nur Palettenfarben."""
    try:
        wurzel = ET.fromstring(svg)
    except ET.ParseError as e:
        return [f"{name}: kein wohlgeformtes XML ({e})"]
    probleme = []
    if not svg.startswith("<svg"):
        probleme.append(f"{name}: beginnt nicht mit <svg")
    if "<script" in svg:
        probleme.append(f"{name}: enthält <script")
    if "width" in wurzel.attrib or "height" in wurzel.attrib:
        probleme.append(f"{name}: width/height am Wurzelelement")
    teile = wurzel.attrib.get("viewBox", "").split()
    if len(teile) != 4:
        probleme.append(f"{name}: keine gültige viewBox")
    elif abs(float(teile[2]) - float(teile[3])) > 0.01:
        probleme.append(f"{name}: viewBox nicht quadratisch ({teile})")
    for k in wurzel.iter():
        if k.tag.endswith("text"):
            probleme.append(f"{name}: <text>-Element")
        if (k.text and k.text.strip()) or (k.tail and k.tail.strip()):
            probleme.append(f"{name}: Textinhalt")
    for f in HEX_FARBE.findall(svg):
        if f.lower() not in ERLAUBTE_FARBEN:
            probleme.append(f"{name}: Farbe {f} außerhalb der Palette")
    return probleme


# ======================================== unabhängig: Würfelgebäude als Voxel

def voxel(hoehen):
    return {(r, c, z) for r, zeile in enumerate(hoehen) for c, h in enumerate(zeile) for z in range(h)}


def ansicht_unabhaengig(hoehen, richtung, hmax):
    """Projiziert die Voxelmenge: oben auf (r,c), vorne (linke Wand) auf
    (c,z), rechts (rechte Wand) auf (p,z) mit p = Zeilen-1-r."""
    v = voxel(hoehen)
    zeilen, spalten = len(hoehen), len(hoehen[0])
    if richtung == "oben":
        sicht = {(r, c) for r, c, z in v}
        return [[1 if (r, c) in sicht else 0 for c in range(spalten)] for r in range(zeilen)]
    if richtung == "vorne":
        sicht, breite = {(c, z) for r, c, z in v}, spalten
    else:
        sicht, breite = {(zeilen - 1 - r, z) for r, c, z in v}, zeilen
    return [[1 if (p, hmax - 1 - i) in sicht else 0 for p in range(breite)] for i in range(hmax)]


def _hex(r, c, h):
    x, y = (c - r) * 30, (r + c) * 15
    top = y - h * 34
    return [(x, top - 15), (x + 30, top), (x + 30, y), (x, y + 15), (x - 30, y), (x - 30, top)]


def _top(r, c, h):
    x, y = (c - r) * 30, (r + c) * 15 - h * 34
    return [(x, y - 15), (x + 30, y), (x, y + 15), (x - 30, y)]


def _innen(px, py, poly):
    drin = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > py) != (y2 > py) and px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
            drin = not drin
    return drin


def alle_sichtbar_unabhaengig(hoehen):
    """Jede Dach-/Bodenraute hat in einem dichten 9x9-Raster mindestens einen
    Punkt, den keine nähere Säule bedeckt."""
    zeilen, spalten = len(hoehen), len(hoehen[0])
    zellen = [(r, c) for r in range(zeilen) for c in range(spalten)]
    for r, c in zellen:
        dach = _top(r, c, hoehen[r][c])
        xs, ys = [p[0] for p in dach], [p[1] for p in dach]
        naeher = [(a, b) for a, b in zellen if a + b > r + c]
        sichtbar = False
        for i in range(9):
            for j in range(9):
                px = min(xs) + (max(xs) - min(xs)) * i / 8
                py = min(ys) + (max(ys) - min(ys)) * j / 8
                if _innen(px, py, dach) and not any(_innen(px, py, _hex(a, b, hoehen[a][b]))
                                                    for a, b in naeher):
                    sichtbar = True
        if not sichtbar:
            return False
    return True


# ===================================== unabhängig: Hexominos und 3D-Faltung

def _dreh(z):
    return (z[1], -z[0])


def _spiegel(z):
    return (z[0], -z[1])


def _lagen(form):
    """Alle 8 Lagen (4 Drehungen, je gespiegelt), auf (0,0) verschoben."""
    ergebnis = []
    f = list(form)
    for _ in range(4):
        f = [_dreh(z) for z in f]
        for g in (f, [_spiegel(z) for z in f]):
            mr = min(a for a, b in g)
            mc = min(b for a, b in g)
            ergebnis.append(tuple(sorted((a - mr, b - mc) for a, b in g)))
    return ergebnis


def hexominos_unabhaengig():
    """Wachstum über die offene Nachbarschaft, dann Gruppierung nach Lage."""
    festen = {frozenset([(0, 0)])}
    for _ in range(5):
        neu = set()
        for f in festen:
            rand = {(r + a, c + b) for r, c in f for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))} - f
            for z in rand:
                g = f | {z}
                mr, mc = min(a for a, b in g), min(b for a, b in g)
                neu.add(frozenset((a - mr, b - mc) for a, b in g))
        festen = neu
    klassen = {}
    for f in festen:
        klassen.setdefault(min(_lagen(f)), []).append(f)
    return sorted(klassen), len(festen)


def falte_3d(zellen):
    """Faltet das Netz mit Normalenvektoren: jede Zelle bekommt ein Dreibein
    (Normale, Ost, Nord); über eine Kante nach Osten wird die Normale zum alten
    Ost-Vektor, der neue Ost-Vektor zeigt dorthin, wo die alte Normale
    war (negiert). Netz faltet, wenn die sechs Normalen verschieden sind.
    Rückgabe {zelle: normale} oder None."""
    zellen = set(map(tuple, zellen))
    if len(zellen) != 6:
        return None
    def neg(v):
        return tuple(-x for x in v)
    start = min(zellen)
    rahmen = {start: ((0, 0, -1), (1, 0, 0), (0, 1, 0))}
    offen = [start]
    while offen:
        z = offen.pop()
        n, e, t = rahmen[z]
        for (dr, dc), neu in (((0, 1), (e, neg(n), t)), ((0, -1), (neg(e), n, t)),
                              ((-1, 0), (t, e, neg(n))), ((1, 0), (neg(t), e, n))):
            nb = (z[0] + dr, z[1] + dc)
            if nb in zellen and nb not in rahmen:
                rahmen[nb] = neu
                offen.append(nb)
    if len(rahmen) != 6:
        return None
    normalen = {z: r[0] for z, r in rahmen.items()}
    return normalen if len(set(normalen.values())) == 6 else None


# ================================ unabhängig: Kästchenfiguren (Kanten, Trapeze)

_ECKPUNKTE = {"ol": lambda r, c: [(r, c), (r, c + 1), (r + 1, c)],
              "or": lambda r, c: [(r, c + 1), (r, c), (r + 1, c + 1)],
              "ul": lambda r, c: [(r + 1, c), (r, c), (r + 1, c + 1)],
              "ur": lambda r, c: [(r + 1, c + 1), (r, c + 1), (r + 1, c)]}


def _gauss(punkte):
    s = sum(punkte[i][0] * punkte[(i + 1) % len(punkte)][1]
            - punkte[(i + 1) % len(punkte)][0] * punkte[i][1] for i in range(len(punkte)))
    return abs(s) / 2


def flaeche_unabhaengig(zellen, halbe):
    """Summe der Polygonflächen nach der Gaußschen Trapezformel."""
    quadrate = sum(_gauss([(r, c), (r, c + 1), (r + 1, c + 1), (r + 1, c)]) for r, c in zellen)
    dreiecke = sum(_gauss(_ECKPUNKTE[e](z[0], z[1])) for z, e in halbe)
    return quadrate + dreiecke


def umfang_unabhaengig(zellen):
    """Jede Zelle bringt vier Randkanten; Kanten, die zwei Zellen teilen,
    kommen doppelt vor und gehören nicht zum Umfang."""
    kanten = {}
    for r, c in zellen:
        for k in (((r, c), (r, c + 1)), ((r + 1, c), (r + 1, c + 1)),
                  ((r, c), (r + 1, c)), ((r, c + 1), (r + 1, c + 1))):
            kanten[k] = kanten.get(k, 0) + 1
    return sum(1 for n in kanten.values() if n == 1)


def raetsel_unabhaengig(typ, zahl):
    """Alle Seitenpaare a<=b bis 40 durchprobieren."""
    paare = [(a, b) for a in range(1, 41) for b in range(a, 41)]
    if typ == "rechtecke_flaeche":
        return sum(1 for a, b in paare if a * b == zahl)
    if typ == "rechtecke_umfang":
        return sum(1 for a, b in paare if 2 * (a + b) == zahl)
    if typ == "max_flaeche":
        return max(a * b for a, b in paare if 2 * (a + b) == zahl)
    return min(2 * (a + b) for a, b in paare if a * b == zahl)


# ===================================================== unabhängig: Schatzkarte

def weg_unabhaengig(n, felsen, start, ziel):
    """Kürzester Weg durch wiederholtes Entspannen aller Entfernungen
    (Bellman-Ford auf dem Raster) statt Breitensuche."""
    felsen = set(map(tuple, felsen))
    unendlich = 10 ** 6
    d = {(r, c): unendlich for r in range(n) for c in range(n) if (r, c) not in felsen}
    d[tuple(start)] = 0
    geaendert = True
    while geaendert:
        geaendert = False
        for (r, c), wert in list(d.items()):
            for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (r + a, c + b)
                if nb in d and d[nb] + 1 < wert:
                    wert = d[nb] + 1
                    d[(r, c)] = wert
                    geaendert = True
    return d[tuple(ziel)] if d[tuple(ziel)] < unendlich else None


def ziel_unabhaengig(anker, schritte):
    """Geht jeden Schritt einzeln, Feld für Feld."""
    r, c = anker
    for richtung, laenge in schritte:
        for _ in range(laenge):
            if richtung == "rechts":
                c += 1
            elif richtung == "links":
                c -= 1
            elif richtung == "oben":
                r -= 1
            else:
                r += 1
    return (r, c)


# ===================================================================== Prüfstand

ARTEN = {"geo_ansicht": "ansicht", "geo_netzfalten": "netzfalten",
         "geo_flaeche_umfang": "gitterfigur", "geo_quader": "quader", "geo_karte": "karte"}
GEMELDET = {"filter": 0}
ALLE = {}


def erwartete_typen(skill, stage, index):
    """Welchen Aufgabentyp die Tabelle in ZIELE-V3 G3 an dieser Stelle vorsieht."""
    if skill in ("geo_ansicht", "geo_netzfalten"):
        return "bildwahl"
    if skill == "geo_flaeche_umfang":
        return "bildzahl" if index < 4 else "zahl"
    if skill == "geo_quader":
        return "bildzahl"
    return "bildwahl" if G._karte_modus(stage, index) == "schritte" else "bildzahl"


def pruefe_aufgabe_form(skill, stage, index, seed, aufgabe, kern):
    """Form, Schema, Prüfer und validate.check_task für eine Aufgabe."""
    tag = f"{skill} s{stage} i{index} seed{seed}"
    probleme = []
    typ = aufgabe["type"]
    if typ != erwartete_typen(skill, stage, index):
        probleme.append(f"{tag}: Typ {typ} statt {erwartete_typen(skill, stage, index)}")
    if len(aufgabe["q"].split()) > 14:
        probleme.append(f"{tag}: Frage hat {len(aufgabe['q'].split())} Wörter")
    erlaubt = {"bildwahl": {"type", "q", "svg", "optionen_svg", "richtig", "kern", "hint"},
               "bildzahl": {"type", "q", "svg", "a", "kern", "hint", "papier"},
               "zahl": {"type", "q", "a", "check", "hint", "papier", "kern"}}[typ]
    if set(aufgabe) - erlaubt:
        probleme.append(f"{tag}: fremde Felder {set(aufgabe) - erlaubt}")
    if typ == "bildwahl":
        svgs = [aufgabe["svg"]] + aufgabe["optionen_svg"]
        if len(aufgabe["optionen_svg"]) != 4 or len(set(aufgabe["optionen_svg"])) != 4:
            probleme.append(f"{tag}: Optionen nicht 4 verschiedene SVGs")
        if aufgabe["kern"]["richtig"] != aufgabe["richtig"]:
            probleme.append(f"{tag}: kern.richtig != richtig")
    elif typ == "bildzahl":
        svgs = [aufgabe["svg"]]
        if aufgabe["kern"]["anzahl"] != aufgabe["a"]:
            probleme.append(f"{tag}: kern.anzahl != a")
    else:
        svgs = []
    for i, s in enumerate(svgs):
        probleme += svg_probleme(s, f"{tag} svg{i}")
    if kern.get("art") != ARTEN[skill]:
        probleme.append(f"{tag}: kern.art {kern.get('art')!r}")
    gut, grund = G.PRUEFER[ARTEN[skill]](kern)
    if not gut:
        probleme.append(f"{tag}: Prüfer lehnt ab: {grund}")
    papier = (skill == "geo_flaeche_umfang" and index >= 4) or \
             (skill == "geo_karte" and G._karte_modus(stage, index) == "massstab")
    if bool(aufgabe.get("papier")) != papier:
        probleme.append(f"{tag}: papier={aufgabe.get('papier')} (erwartet {papier})")
    for m in V.check_task(aufgabe, stage):
        if any(muster.search(m) for muster in NOCH_UNBEKANNT):
            GEMELDET["filter"] += 1
        else:
            probleme.append(f"{tag}: validate: {m}")
    return probleme


def sammle():
    """Baut alle 540 Aufgaben (5 Fertigkeiten x 6 Stufen x 6 Indizes x 3 Seeds)."""
    for skill in G.SKILLS:
        for stage in STUFEN:
            for index in INDIZES:
                for seed in SEEDS:
                    ALLE[(skill, stage, index, seed)] = G._baue(skill, stage, index, seed)


sammle()
alle_probleme = []
for (skill, stage, index, seed), (aufgabe, kern) in ALLE.items():
    alle_probleme += pruefe_aufgabe_form(skill, stage, index, seed, aufgabe, kern)
ok(f"{len(ALLE)} Aufgaben (5 Fertigkeiten x Stufe 3..8 x Index 0..5 x 3 Seeds): Form, Prüfer, "
   f"validate.check_task ohne Mängel", not alle_probleme, "; ".join(alle_probleme[:3]))
# validate.py kennt die Arten inzwischen: Es darf nichts mehr ausgefiltert werden.
ok("validate.py kennt alle fünf Arten: keine Meldung musste ausgefiltert werden",
   GEMELDET["filter"] == 0, f"{GEMELDET['filter']} Meldungen ausgefiltert")
ok("jede Frage eines Pakets ist anders (genug Schablonen, kein Vorspann nötig)",
   all(len({ALLE[(sk, st, ix, sd)][0]["q"] for ix in range(6)}) == 6
       for sk in G.SKILLS for st in range(3, 9) for sd in range(3)))


# ============================================================ Stufenhülle (G3)

def kerne(skill):
    return [(st, ix, k) for (sk, st, ix, sd), (a, k) in ALLE.items() if sk == skill]


huelle = []
for st, ix, k in kerne("geo_ansicht"):
    zeilen, spalten, hmax = len(k["hoehen"]), len(k["hoehen"][0]), max(map(max, k["hoehen"]))
    if st <= 4 and not (k["richtung"] == "oben" and max(zeilen, spalten) <= 3 and hmax <= 2):
        huelle.append(f"ansicht s{st}: {k['richtung']} {zeilen}x{spalten} h{hmax}")
    if st == 5 and not (k["richtung"] in ("vorne", "rechts") and (zeilen, spalten) == (3, 3) and hmax <= 3):
        huelle.append(f"ansicht s5: {k['richtung']} {zeilen}x{spalten} h{hmax}")
    if st >= 6 and not (3 <= zeilen <= 4 and 3 <= spalten <= 4 and hmax <= 4):
        huelle.append(f"ansicht s{st}: {zeilen}x{spalten} h{hmax}")
ok("ansicht: Stufenhülle (3-4 nur oben, 2x2/3x3, Höhe<=2; 5 vorne/rechts 3x3, Höhe<=3; 6-8 bis 4x4, Höhe<=4)",
   not huelle, "; ".join(huelle[:2]))
richtungen = {(st, k["richtung"]) for st, ix, k in kerne("geo_ansicht")}
ok("ansicht: Stufe 6-8 zeigt alle drei Richtungen",
   all({r for s, r in richtungen if s == st} == {"oben", "vorne", "rechts"} for st in (6, 7, 8)))
modi = {}
for st, ix, k in kerne("geo_netzfalten"):
    modi.setdefault(st, set()).add(k["modus"])
ok("netzfalten: Stufe 3-4 nur wuerfel, 5-6 beides, 7-8 nur gegenueber",
   modi[3] == modi[4] == {"wuerfel"} and modi[5] == modi[6] == {"wuerfel", "gegenueber"}
   and modi[7] == modi[8] == {"gegenueber"}, str(modi))
untypisch = [G._max_linie([tuple(z) for z in k["netz"]]) for st, ix, k in kerne("geo_netzfalten")
             if st == 8 and k["modus"] == "gegenueber"]
ok("netzfalten: Stufe 8 nimmt nur untypische Netze (keine Reihe aus 4)", untypisch and max(untypisch) <= 3,
   str(sorted(set(untypisch))))
modi = {}
for st, ix, k in kerne("geo_karte"):
    modi.setdefault(st, set()).add(k["modus"])
ok("karte: Maßstab erst ab Stufe 5, weg ab Stufe 3",
   all("massstab" not in modi[s] for s in (3, 4)) and all("massstab" in modi[s] for s in (5, 6, 7, 8))
   and all("weg" in modi[s] for s in STUFEN), str(modi))
groessen = {st: {k["n"] for s2, i2, k in kerne("geo_karte") if s2 == st} for st in STUFEN}
ok("karte: Kartengröße wächst von 5x5 bis 8x8", min(groessen[3]) == 5 and max(groessen[8]) == 8
   and all(max(groessen[a]) <= max(groessen[b]) for a, b in ((3, 5), (5, 6), (6, 7), (7, 8))), str(groessen))
dim = [(k["laenge"], k["breite"], k["hoehe"]) for st, ix, k in kerne("geo_quader")]
ok("quader: von 2x2x2 bis 4x3x3", (2, 2, 2) in dim and (4, 3, 3) in dim
   and all(l * b * h <= 36 and l <= 4 and b <= 3 and h <= 3 for l, b, h in dim))
ok("quader: Antwort höchstens 36 (2 Multiplikationen + 1 Subtraktion)",
   all(k["anzahl"] <= 36 for st, ix, k in kerne("geo_quader")))
gitter_figuren = [(st, ix, k) for st, ix, k in kerne("geo_flaeche_umfang") if k["modus"] == "figur"]
ok("gitterfigur: Treppen ab Stufe 5 (Index 3), halbe Kästchen ab Stufe 6 (Index 2)",
   all(k["halbe"] == [] for st, ix, k in gitter_figuren if st < 6)
   and all(k["halbe"] for st, ix, k in gitter_figuren if st >= 6 and ix == 2)
   and all(k["anzahl"] == 2 * (max(r for r, c in k["zellen"]) + max(c for r, c in k["zellen"]) + 2)
           for st, ix, k in gitter_figuren if st >= 5 and ix == 3))
raetsel = [k for st, ix, k in kerne("geo_flaeche_umfang") if k["modus"] == "raetsel"]
ok("gitterfigur: Rätsel-Zahlen klein (Fläche<=36, Umfang<=30)",
   all(k["zahl"] <= (36 if k["typ"] in ("rechtecke_flaeche", "min_umfang") else 30) for k in raetsel))
ok("gitterfigur: Index 0-3 Fläche/Umfang abwechselnd, Index 4-5 Rätsel",
   all((k["modus"] == "figur") == (ix < 4) for st, ix, k in kerne("geo_flaeche_umfang")))


# ====================================================== unabhängige Nachrechnung

abweichungen = []
for st, ix, k in kerne("geo_ansicht"):
    if not alle_sichtbar_unabhaengig(k["hoehen"]):
        abweichungen.append(f"ansicht s{st} i{ix}: Säule unsichtbar (Pixelabtastung)")
    erw = ansicht_unabhaengig(k["hoehen"], k["richtung"], k["hmax"])
    gleich = [i for i, o in enumerate(k["optionen"]) if o == erw]
    if gleich != [k["richtig"]]:
        abweichungen.append(f"ansicht s{st} i{ix}: Voxel-Projektion passt zu {gleich}, richtig={k['richtig']}")
ok("ansicht: Voxel-Projektion bestätigt jede richtige Option, genau eine passt; Pixelabtastung: jede Säule sichtbar",
   not abweichungen, "; ".join(abweichungen[:2]))

# Orientierung gegen die Bildprojektion: in der linken Wand läuft das Bild von
# links nach rechts mit wachsender Spalte, in der rechten mit fallender Zeile.
def bildx(r, c):
    return (c - r) * 30

orient = True
for n in (2, 3, 4):
    links = sorted(range(n), key=lambda c: bildx(n - 1, c))
    rechts = sorted(range(n), key=lambda r: bildx(r, n - 1))
    probe = [[0] * n for _ in range(n)]
    for c in range(n):
        probe[0][c] = c + 1 if c + 1 <= 4 else 4
    orient &= links == list(range(n)) and rechts == list(reversed(range(n)))
    profil = G._profil_von_raster(G.ansicht_raster(probe, "vorne", 4))
    orient &= profil == [min(c + 1, 4) for c in range(n)]
    probe2 = [[0] * n for _ in range(n)]
    for r in range(n):
        probe2[r][0] = min(r + 1, 4)
    profil2 = G._profil_von_raster(G.ansicht_raster(probe2, "rechts", 4))
    orient &= profil2 == [min(r + 1, 4) for r in reversed(range(n))]
ok("ansicht: Reihenfolge der Wandansichten stimmt mit der Isometrie-Projektion überein", orient)

hex35, fest = hexominos_unabhaengig()
ok("netzfalten: es gibt 35 freie Hexominos (216 feste), eigene Aufzählung = Kern",
   len(hex35) == 35 and fest == 216 and hex35 == G.alle_hexominos(), f"{len(hex35)} frei / {fest} fest")
faltet_kern = [f for f in hex35 if G.falte_netz(f)]
faltet_3d = [f for f in hex35 if falte_3d(f)]
ok("netzfalten: von allen 35 freien Hexominos falten genau 11 zum Würfel (Abrollen)",
   len(faltet_kern) == 11, str(len(faltet_kern)))
ok("netzfalten: 3D-Faltung mit Normalenvektoren findet dieselben 11",
   faltet_3d == faltet_kern, f"{len(faltet_3d)} vs {len(faltet_kern)}")
signaturen = sorted(G._max_linie(f) for f in faltet_kern)
ok("netzfalten: die 11 sind 6x '4 in einer Reihe' und 5 untypische (Reihe höchstens 3)",
   signaturen.count(4) == 6 and len(signaturen) == 11 and max(signaturen) == 4, str(signaturen))

abweichungen = []
for st, ix, k in kerne("geo_netzfalten"):
    if k["modus"] == "wuerfel":
        faltend = [i for i, o in enumerate(k["optionen"]) if falte_3d(o)]
        if faltend != [k["richtig"]]:
            abweichungen.append(f"netz s{st} i{ix}: 3D-Faltung findet {faltend}, richtig={k['richtig']}")
    else:
        normalen = falte_3d(k["netz"])
        zeichen = {tuple(z): n for z, n in zip(k["netz"], k["zeichen"])}
        zg = next(z for z, n in zeichen.items() if n == k["gefragt"])
        gegen = [n for z, n in zeichen.items() if normalen[z] == tuple(-x for x in normalen[zg])]
        if gegen != [k["optionen"][k["richtig"]]]:
            abweichungen.append(f"netz s{st} i{ix}: gegenüber ist {gegen}, markiert {k['optionen'][k['richtig']]}")
ok("netzfalten: 3D-Faltung bestätigt jede richtige Option bzw. jedes Gegenüber", not abweichungen,
   "; ".join(abweichungen[:2]))

abweichungen = []
for st, ix, k in kerne("geo_flaeche_umfang"):
    if k["modus"] == "figur":
        zellen = {tuple(z) for z in k["zellen"]}
        halbe = [(tuple(z), e) for z, e in k["halbe"]]
        if k["frage"] == "flaeche":
            if flaeche_unabhaengig(zellen, halbe) != k["anzahl"]:
                abweichungen.append(f"gitter s{st} i{ix}: Fläche {flaeche_unabhaengig(zellen, halbe)} != {k['anzahl']}")
        elif umfang_unabhaengig(zellen) != k["anzahl"]:
            abweichungen.append(f"gitter s{st} i{ix}: Umfang {umfang_unabhaengig(zellen)} != {k['anzahl']}")
    elif raetsel_unabhaengig(k["typ"], k["zahl"]) != k["anzahl"]:
        abweichungen.append(f"gitter s{st} i{ix}: Rätsel {raetsel_unabhaengig(k['typ'], k['zahl'])} != {k['anzahl']}")
ok("gitterfigur: Gaußsche Trapezformel, Randkanten und Durchprobieren bestätigen jede Antwort",
   not abweichungen, "; ".join(abweichungen[:2]))

abweichungen = []
for st, ix, k in kerne("geo_quader"):
    v = voxel(k["hoehen"])
    fehlt = k["laenge"] * k["breite"] * k["hoehe"] - len(v)
    if fehlt != k["anzahl"] or not alle_sichtbar_unabhaengig(k["hoehen"]):
        abweichungen.append(f"quader s{st} i{ix}: fehlt {fehlt} vs {k['anzahl']}")
    if any((r, c, z - 1) not in v for r, c, z in v if z > 0):
        abweichungen.append(f"quader s{st} i{ix}: schwebender Würfel")
    if any(z >= k["hoehe"] or r >= k["breite"] or c >= k["laenge"] for r, c, z in v):
        abweichungen.append(f"quader s{st} i{ix}: Würfel außerhalb des Quaders")
ok("quader: Voxelzählung und Pixelabtastung bestätigen jede Antwort; nichts schwebt, nichts ragt heraus",
   not abweichungen, "; ".join(abweichungen[:2]))

abweichungen = []
for st, ix, k in kerne("geo_karte"):
    anker = tuple(k["anker"])
    if k["modus"] == "schritte":
        ziel = ziel_unabhaengig(anker, k["schritte"])
        symbole = {(r, c): n for r, c, n in k["zeichen"]}
        if symbole.get(ziel) != k["optionen"][k["richtig"]]:
            abweichungen.append(f"karte s{st} i{ix}: am Ziel liegt {symbole.get(ziel)}")
        if sum(1 for n in symbole.values() if n == "anker") != 1:
            abweichungen.append(f"karte s{st} i{ix}: Anker nicht eindeutig")
        # kein Ablenker-Zeichen liegt am Ziel: genau eine Option stimmt
        if sum(1 for o in k["optionen"] if o == symbole.get(ziel)) != 1:
            abweichungen.append(f"karte s{st} i{ix}: mehrere Optionen passen")
    else:
        d = weg_unabhaengig(k["n"], k["felsen"], anker, tuple(k["schatz"]))
        erw = d * k.get("meter", 1) if d is not None else None
        if erw != k["anzahl"]:
            abweichungen.append(f"karte s{st} i{ix}: Weg {erw} vs {k['anzahl']}")
        if st >= 5:
            manh = abs(anker[0] - k["schatz"][0]) + abs(anker[1] - k["schatz"][1])
            if d == manh:
                abweichungen.append(f"karte s{st} i{ix}: kein Umweg nötig")
ok("karte: Relaxations-Wegesuche und Schritt-für-Schritt-Gehen bestätigen jede Antwort; ab Stufe 5 immer ein Umweg",
   not abweichungen, "; ".join(abweichungen[:2]))


# ====================================================== manipulierte Kerne

def kern_von(skill, stage, index, seed=0):
    return copy.deepcopy(G._baue(skill, stage, index, seed)[1])


def abgelehnt(art, kern, stichwort=None):
    gut, grund = G.PRUEFER[art](kern)
    return (not gut) and (stichwort is None or stichwort in grund), grund


k = kern_von("geo_ansicht", 6, 1)
k["richtig"] = (k["richtig"] + 1) % 4
ok("Prüfer ansicht: falsches 'richtig' wird abgelehnt", *abgelehnt("ansicht", k, "markiert ist"))
k = kern_von("geo_ansicht", 6, 1)
k["optionen"][(k["richtig"] + 1) % 4] = copy.deepcopy(k["optionen"][k["richtig"]])
ok("Prüfer ansicht: doppelte Option wird abgelehnt", *abgelehnt("ansicht", k, "verschieden"))
k = kern_von("geo_ansicht", 3, 0)
k["hoehen"] = [[1, 0], [0, 2]]       # die Säule hinten links verschwindet hinter der vorderen
ok("Prüfer ansicht: unsichtbare Säule wird abgelehnt", *abgelehnt("ansicht", k, "nicht sichtbar"))
ok("unabhängige Pixelabtastung sieht dieselbe Säule als verdeckt", not alle_sichtbar_unabhaengig([[1, 0], [0, 2]]))
k = kern_von("geo_ansicht", 6, 1)
k["optionen"][0] = [[0, 1], [1, 0]]
ok("Prüfer ansicht: Option im falschen Format wird abgelehnt", *abgelehnt("ansicht", k, "Raster"))
k = kern_von("geo_ansicht", 5, 0)
k["richtung"] = "unten"
ok("Prüfer ansicht: unbekannte Richtung wird abgelehnt", *abgelehnt("ansicht", k, "Richtung"))

k = kern_von("geo_netzfalten", 3, 0)
ungueltig = next(i for i, o in enumerate(k["optionen"]) if i != k["richtig"])
k["richtig"] = ungueltig
ok("Prüfer netzfalten: ungültiges Netz als richtig markiert wird abgelehnt", *abgelehnt("netzfalten", k, "falten"))
k = kern_von("geo_netzfalten", 3, 0)
anderes_gueltig = next(f for f in G.alle_hexominos() if G.falte_netz(f)
                       and G._kanonisch(f) != G._kanonisch([tuple(z) for z in k["optionen"][k["richtig"]]]))
k["optionen"][(k["richtig"] + 1) % 4] = [list(z) for z in anderes_gueltig]
ok("Prüfer netzfalten: zwei faltende Netze unter den Optionen werden abgelehnt",
   *abgelehnt("netzfalten", k, "falten"))
k = kern_von("geo_netzfalten", 3, 0)
gedreht = [list(z) for z in G._acht_lagen([tuple(z) for z in k["optionen"][k["richtig"]]])[5]]
k["optionen"][(k["richtig"] + 1) % 4] = gedreht
ok("Prüfer netzfalten: dieselbe Form gedreht gilt als doppelt", *abgelehnt("netzfalten", k, "dieselbe Form"))
k = kern_von("geo_netzfalten", 7, 0)
k["richtig"] = (k["richtig"] + 1) % 4
ok("Prüfer netzfalten gegenueber: falsches Gegenüber wird abgelehnt", *abgelehnt("netzfalten", k, "gegenüber liegt"))
k = kern_von("geo_netzfalten", 7, 0)
k["netz"] = [[0, 0], [0, 1], [1, 0], [1, 1], [2, 0], [2, 1]]       # 2x3-Rechteck faltet nicht
ok("Prüfer netzfalten gegenueber: nicht faltendes Netz wird abgelehnt", *abgelehnt("netzfalten", k, "faltet sich nicht"))
k = kern_von("geo_netzfalten", 7, 0)
k["optionen"][(k["richtig"] + 1) % 4] = k["gefragt"]
ok("Prüfer netzfalten gegenueber: gefragtes Zeichen unter den Optionen wird abgelehnt",
   *abgelehnt("netzfalten", k))

k = kern_von("geo_flaeche_umfang", 5, 0)
k["anzahl"] += 1
ok("Prüfer gitterfigur: falsche Fläche wird abgelehnt", *abgelehnt("gitterfigur", k, "nachgezählt"))
k = kern_von("geo_flaeche_umfang", 5, 1)
k["anzahl"] -= 2
ok("Prüfer gitterfigur: falscher Umfang wird abgelehnt", *abgelehnt("gitterfigur", k, "nachgezählt"))
k = kern_von("geo_flaeche_umfang", 5, 0)
k["zellen"] = [[r, c] for r in range(3) for c in range(3) if (r, c) != (1, 1)]
k["anzahl"] = 8
ok("Prüfer gitterfigur: Figur mit Loch wird abgelehnt", *abgelehnt("gitterfigur", k, "Loch"))
k = kern_von("geo_flaeche_umfang", 5, 0)
k["zellen"] = [[0, 0], [0, 1], [0, 2], [3, 0], [3, 1], [3, 2]]
k["anzahl"] = 6
ok("Prüfer gitterfigur: unzusammenhängende Figur wird abgelehnt", *abgelehnt("gitterfigur", k, "hängt nicht"))
k = kern_von("geo_flaeche_umfang", 6, 2)
k["halbe"] = k["halbe"][:1]
k["anzahl"] = len(k["zellen"])
ok("Prüfer gitterfigur: ungerade Zahl halber Kästchen wird abgelehnt", *abgelehnt("gitterfigur", k, "gerade"))
k = kern_von("geo_flaeche_umfang", 6, 2)
k["halbe"][0] = [[20, 20], "ol"]
ok("Prüfer gitterfigur: halbes Kästchen ohne Anschluss wird abgelehnt", *abgelehnt("gitterfigur", k, "Kathete"))
k = kern_von("geo_flaeche_umfang", 6, 2)
k["frage"] = "umfang"
ok("Prüfer gitterfigur: Umfang mit halben Kästchen wird abgelehnt", *abgelehnt("gitterfigur", k, "Umfang"))
k = kern_von("geo_flaeche_umfang", 5, 4)
k["anzahl"] += 1
ok("Prüfer gitterfigur: falsches Rätsel wird abgelehnt", *abgelehnt("gitterfigur", k, "durchprobiert"))
k = kern_von("geo_flaeche_umfang", 5, 4)
k["typ"] = "unfug"
ok("Prüfer gitterfigur: unbekannte Rätselart wird abgelehnt", *abgelehnt("gitterfigur", k))
k = kern_von("geo_flaeche_umfang", 5, 0)
k["anzahl"] = float(k["anzahl"])
ok("Prüfer gitterfigur: Antwort als Kommazahl wird abgelehnt", *abgelehnt("gitterfigur", k, "ganze Zahl"))

k = kern_von("geo_quader", 6, 2)
k["anzahl"] += 1
ok("Prüfer quader: falsche Anzahl wird abgelehnt", *abgelehnt("quader", k, "nachgerechnet"))
k = kern_von("geo_quader", 3, 0)
k["hoehen"] = [[1, 0], [0, 2]]
k["anzahl"] = 8 - 3
ok("Prüfer quader: unsichtbare Säule wird abgelehnt", *abgelehnt("quader", k, "nicht sichtbar"))
k = kern_von("geo_quader", 3, 0)
k["hoehen"] = [[2, 2], [2, 2]]
k["anzahl"] = 0
ok("Prüfer quader: schon voller Quader wird abgelehnt", *abgelehnt("quader", k, "voll"))
k = kern_von("geo_quader", 6, 2)
k["breite"] = 2
ok("Prüfer quader: Maße passen nicht zur Höhenkarte", *abgelehnt("quader", k, "passt nicht"))

k = kern_von("geo_karte", 3, 0)
k["richtig"] = (k["richtig"] + 1) % 4
ok("Prüfer karte schritte: falsches 'richtig' wird abgelehnt", *abgelehnt("karte", k, "markiert ist"))
k = kern_von("geo_karte", 3, 0)
k["schritte"][0][1] = 9
ok("Prüfer karte schritte: Weg von der Karte hinunter wird abgelehnt", *abgelehnt("karte", k))
k = kern_von("geo_karte", 3, 0)
k["zeichen"].append([k["anker"][0], (k["anker"][1] + 1) % 5, "anker"])
ok("Prüfer karte schritte: zweiter Anker wird abgelehnt", *abgelehnt("karte", k))
k = kern_von("geo_karte", 4, 3)
k["anzahl"] += 1
ok("Prüfer karte weg: falsche Länge wird abgelehnt", *abgelehnt("karte", k, "nachgerechnet"))
k = kern_von("geo_karte", 4, 3)
k["felsen"].append(list(k["anker"]))
ok("Prüfer karte weg: Fels auf dem Anker wird abgelehnt", *abgelehnt("karte", k, "überschneiden"))
k = kern_von("geo_karte", 4, 3)
ar, ac = k["anker"]
k["felsen"] = [[ar + a, ac + b] for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
               if 0 <= ar + a < k["n"] and 0 <= ac + b < k["n"] and [ar + a, ac + b] != k["schatz"]]
ok("Prüfer karte weg: eingemauerter Anker (unerreichbarer Schatz) wird abgelehnt", *abgelehnt("karte", k, "erreichbar"))
k = kern_von("geo_karte", 6, 4)
k["anzahl"] = k["anzahl"] // k["meter"]
ok("Prüfer karte massstab: Antwort ohne Maßstab wird abgelehnt", *abgelehnt("karte", k, "nachgerechnet"))
k = kern_von("geo_karte", 6, 4)
del k["meter"]
ok("Prüfer karte massstab: fehlender Maßstab wird abgelehnt", *abgelehnt("karte", k, "Maßstab"))
for art in G.PRUEFER:
    ok(f"Prüfer {art}: leerer oder falscher Kern stürzt nicht ab, wird abgelehnt",
       G.PRUEFER[art]({})[0] is False and G.PRUEFER[art](None)[0] is False)


# ====================================================== Determinismus, Streuung

def als_text(aufgabe):
    return json.dumps(aufgabe, sort_keys=True, ensure_ascii=False)


gleich = True
for schluessel in reversed(list(ALLE)):          # andere Reihenfolge, frischer Aufruf
    aufgabe, kern = ALLE[schluessel]
    if aufgabe["type"] == "zahl":                   # baue_aufgabe hängt den Rätsel-Kern an
        aufgabe = dict(aufgabe, kern=kern)
    gleich &= als_text(G.baue_aufgabe(*schluessel)) == als_text(aufgabe)
ok("Determinismus: gleicher Seed (andere Aufrufreihenfolge) gibt dieselbe Aufgabe, alle 540", gleich)

streuung = 0
zellen = 0
for skill in G.SKILLS:
    for stage in STUFEN:
        for index in INDIZES:
            zellen += 1
            if len({als_text(ALLE[(skill, stage, index, s)][0]) for s in SEEDS}) >= 2:
                streuung += 1
ok("Streuung: verschiedene Seeds geben fast immer verschiedene Aufgaben", streuung >= 0.9 * zellen,
   f"{streuung} von {zellen} Stellen")
lagen = {}
for (skill, stage, index, seed), (a, k) in ALLE.items():
    if a["type"] == "bildwahl":
        lagen.setdefault(skill, set()).add(a["richtig"])
ok("Streuung: die richtige Option steht nicht immer an derselben Stelle",
   all(len(v) == 4 for v in lagen.values()), str({k: sorted(v) for k, v in lagen.items()}))

for schlecht in (("geo_unbekannt", 4, 0, 0), ("geo_karte", 2, 0, 0), ("geo_karte", 9, 0, 0),
                 ("geo_karte", 4, 6, 0), ("geo_karte", 4, -1, 0)):
    try:
        G.baue_aufgabe(*schlecht)
        gefangen = False
    except ValueError:
        gefangen = True
    ok(f"baue_aufgabe{schlecht} wird mit ValueError abgelehnt", gefangen)

ok("SKILLS und PRUEFER wie im Auftrag",
   G.SKILLS == ("geo_ansicht", "geo_netzfalten", "geo_flaeche_umfang", "geo_quader", "geo_karte")
   and set(G.PRUEFER) == {"ansicht", "netzfalten", "gitterfigur", "quader", "karte"})
ok("Optionen-Texte: Frage nennt bei Netz-Gegenüber den richtigen Kasus ('vom'/'von der')",
   all(re.search(r"gegenüber (vom|von der) ", a["q"]) for (sk, st, ix, sd), (a, k) in ALLE.items()
       if sk == "geo_netzfalten" and k["modus"] == "gegenueber"))
ok("Frage nennt bei Netz-Gegenüber das Zeichen aus dem Kern",
   all({"kreis": "Kreis", "dreieck": "Dreieck", "quadrat": "Quadrat", "stern": "Stern",
        "raute": "Raute", "kreuz": "Kreuz"}[k["gefragt"]] in a["q"]
       for (sk, st, ix, sd), (a, k) in ALLE.items() if sk == "geo_netzfalten" and k["modus"] == "gegenueber"))

quelle = (Path(__file__).resolve().parent / "geo_kern.py").read_text(encoding="utf-8")
ok("Leitplanke: kein hash(), kein eval(), kein Sprachmodell-Import im Kern",
   "hash(" not in quelle and "eval(" not in quelle and "anthropic" not in quelle.lower()
   and "openai" not in quelle.lower())
ok("Leitplanke: Zufall nur über random.Random(...) (kein globaler random-Aufruf)",
   not re.findall(r"\brandom\.(?!Random\b)\w+\(", quelle))
ok("Leitplanke: Seeds aus zlib.crc32", "zlib.crc32" in quelle)
ok("Leitplanke: kein <script und keine Heimnetz-Adresse in den neuen Dateien",
   "<script" not in quelle and not re.search(r"\b(?:192\.168|10\.\d+\.\d+)\.\d+", quelle))


# ==================================================================== Ausgabe

def main():
    fails = [r for r in RESULTS if not r[1]]
    for name, good, info in RESULTS:
        print(("✅ " if good else "❌ ") + name + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
