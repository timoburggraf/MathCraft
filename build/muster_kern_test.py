# -*- coding: utf-8 -*-
"""Prüft den deterministischen Musterkern (muster_kern.py).

Im selben Geist wie grafik_kern_test.py: muster_kern.py ist die einzige
Stelle, die künftig garantiert, dass eine Bildmatrix wirklich nur eine
lösbare Lücke hat und dass bei einer Analogie genau eine der vier Optionen
die tatsächliche Umwandlung von C ist. Deshalb wird hier NICHT dasselbe
Prüfverfahren wiederholt aufgerufen, sondern für beide Aufgabenarten eine
zweite, unabhängig geschriebene Implementierung danebengestellt:
  - matrix: eine eigene _regel_ok_unabhaengig(), die über Listen statt über
    (r,c)-Dicts rechnet und die Lateinquadrat-Eigenschaft über sortierte
    Multimengen statt über Mengenvergleich prüft.
  - analogie: eigene _spiegeln_unabhaengig()/_drehen_unabhaengig(), die die
    Koordinatenformeln neu herleiten statt muster_kern._anwenden() bzw.
    grafik_kern._spiegeln/_drehen aufzurufen.
Stimmen beide überein, ist das kein Zufall zweier gleich falscher Annahmen,
weil die Herangehensweisen unterschiedlich sind.

  .venv/bin/python build/muster_kern_test.py
"""
import os
import random
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import muster_kern as M

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


ERLAUBTE_FARBEN = set(M.PALETTE) | {M.KONTUR, M.RASTER}
HEX_FARBE = re.compile(r"#[0-9a-fA-F]{6}")


# ============================================================ SVG-Strukturtest
# Eigenständig geschrieben (nicht aus grafik_kern_test.py importiert), damit
# muster_kern_test.py unabhängig vom Testaufbau eines anderen Moduls bleibt.

def pruefe_svg_struktur(svg, name, quadratisch=True):
    """Wohlgeformtes XML, viewBox-Form je nach 'quadratisch' (Standardfall:
    quadratisch – Ausnahme ist einzig das Analogie-Fragebild, das bewusst
    BREITER als hoch ist, siehe muster_kern._svg_wrap_breit), kein
    width/height am Wurzelelement, kein Textinhalt, nur erlaubte Farben
    (egal ob als fill oder stroke, egal ob in <circle>/<rect>/<polygon>/
    <line>). Gibt eine Liste gefundener Probleme zurück (leer = alles in
    Ordnung)."""
    probleme = []
    try:
        wurzel = ET.fromstring(svg)
    except ET.ParseError as e:
        return [f"{name}: kein wohlgeformtes XML ({e})"]
    if not wurzel.tag.endswith("svg"):
        probleme.append(f"{name}: Wurzelelement ist nicht <svg> ({wurzel.tag})")
    if "width" in wurzel.attrib or "height" in wurzel.attrib:
        probleme.append(f"{name}: Wurzelelement trägt width/height ({wurzel.attrib})")
    vb = wurzel.attrib.get("viewBox")
    if not vb:
        probleme.append(f"{name}: kein viewBox-Attribut")
    else:
        teile = vb.split()
        if len(teile) != 4:
            probleme.append(f"{name}: viewBox hat nicht 4 Werte ({vb})")
        else:
            _, _, breite, hoehe = (float(t) for t in teile)
            if quadratisch:
                if abs(breite - hoehe) > 0.01:
                    probleme.append(f"{name}: viewBox ist nicht quadratisch ({vb})")
            else:
                if not (breite > hoehe):
                    probleme.append(f"{name}: viewBox ist nicht breiter als hoch ({vb})")
    if "<text" in svg:
        probleme.append(f"{name}: enthält ein <text>-Element")
    for knoten in wurzel.iter():
        if (knoten.text and knoten.text.strip()) or (knoten.tail and knoten.tail.strip()):
            probleme.append(f"{name}: enthält Textinhalt ({knoten.tag})")
    for farbe in HEX_FARBE.findall(svg):
        if farbe.lower() not in {f.lower() for f in ERLAUBTE_FARBEN}:
            probleme.append(f"{name}: Farbe {farbe} liegt außerhalb der Palette")
    return probleme


def svg_sammeln(aufgabe, praefix):
    gefunden = []
    if "svg" in aufgabe:
        gefunden.append((f"{praefix}.svg", aufgabe["svg"]))
    if "svg_frage" in aufgabe:
        gefunden.append((f"{praefix}.svg_frage", aufgabe["svg_frage"]))
    for i, s in enumerate(aufgabe.get("optionen_svg", [])):
        gefunden.append((f"{praefix}.optionen_svg[{i}]", s))
    return gefunden


def _svg_serie_ok(aufgabe, praefix):
    for name, svg in svg_sammeln(aufgabe, praefix):
        # Einzige Ausnahme von "quadratisch": das Analogie-Fragebild reiht
        # sieben Elemente nebeneinander auf und ist deshalb bewusst breiter
        # als hoch (Auftrag "Abnahme-Befund" vom 03.09.2026) – alle anderen
        # SVGs (Matrix-Frage, alle Options-SVGs beider Arten) bleiben
        # quadratisch.
        quadratisch = not (praefix == "analogie" and name.endswith(".svg_frage"))
        probleme = pruefe_svg_struktur(svg, name, quadratisch=quadratisch)
        if probleme:
            return probleme[0]
    return None


# ================================================ Matrix: unabhängige Regelprüfung
# Andere Datenstruktur (verschachtelte Liste statt (r,c)-Dict) und andere
# Formulierung der Latin-Eigenschaft (sortierte Multimenge statt Mengenver-
# gleich je Zeile/Spalte) als muster_kern._regel_ok().

def _regel_ok_unabhaengig(regelname, werte_3x3):
    """werte_3x3: 3x3-Liste (Zeilen zuerst) der Werte EINES Attributs."""
    if regelname == "konstant":
        alle = set()
        for zeile in werte_3x3:
            alle.update(zeile)
        return len(alle) == 1
    if regelname == "zeile":
        zeilenwerte = []
        for zeile in werte_3x3:
            if zeile[0] != zeile[1] or zeile[1] != zeile[2]:
                return False
            zeilenwerte.append(zeile[0])
        return len(set(zeilenwerte)) == 3
    if regelname == "spalte":
        for c in range(3):
            spalte = [werte_3x3[r][c] for r in range(3)]
            if len(set(spalte)) != 1:
                return False
        spaltenwerte = [werte_3x3[0][c] for c in range(3)]
        return len(set(spaltenwerte)) == 3
    if regelname == "latin":
        gesamt = sorted({w for zeile in werte_3x3 for w in zeile}, key=repr)
        if len(gesamt) != 3:
            return False
        for zeile in werte_3x3:
            if sorted(zeile, key=repr) != gesamt:
                return False
        for c in range(3):
            spalte = [werte_3x3[r][c] for r in range(3)]
            if sorted(spalte, key=repr) != gesamt:
                return False
        return True
    if regelname == "zaehlt":
        for zeile in werte_3x3:
            if list(zeile) != [1, 2, 3]:
                return False
        return True
    return False


def _matrix_voll(aufgabe):
    """Baut aus den 8 gegebenen Zellen + der richtigen Option die volle
    3x3-Matrix als dict (r,c)->(form,farbe,anzahl), unabhängig von
    muster_kern-internem Code."""
    positionen = [(r, c) for r in range(3) for c in range(3) if (r, c) != (2, 2)]
    matrix = {pos: tuple(z) for pos, z in zip(positionen, aufgabe["zellen"])}
    matrix[(2, 2)] = tuple(aufgabe["optionen"][aufgabe["richtig"]])
    return matrix


def matrix_unabhaengig_ok(aufgabe):
    """True, wenn (unabhängig nachgerechnet) alle drei Regeln für die volle
    Matrix erfüllt sind UND jeder Ablenker mindestens eine verletzt."""
    matrix = _matrix_voll(aufgabe)
    regeln = aufgabe["regeln"]
    attr_index = {"form": 0, "farbe": 1, "anzahl": 2}
    for attr, idx in attr_index.items():
        werte_3x3 = [[matrix[(r, c)][idx] for c in range(3)] for r in range(3)]
        if not _regel_ok_unabhaengig(regeln[attr], werte_3x3):
            return False, f"Regel '{regeln[attr]}' für {attr} (unabhängig geprüft) nicht erfüllt"
    for i, o in enumerate(aufgabe["optionen"]):
        if i == aufgabe["richtig"]:
            continue
        test = dict(matrix)
        test[(2, 2)] = tuple(o)
        verletzt = False
        for attr, idx in attr_index.items():
            werte_3x3 = [[test[(r, c)][idx] for c in range(3)] for r in range(3)]
            if not _regel_ok_unabhaengig(regeln[attr], werte_3x3):
                verletzt = True
                break
        if not verletzt:
            return False, f"Ablenker {i} erfüllt (unabhängig geprüft) ebenfalls alle Regeln"
    return True, ""


# ==================================================== Matrix: Serie über Seeds

def matrix_serie(stufe, schwierigkeit, anzahl_seeds):
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        rng = random.Random(seed * 7919 + stufe * 31 + schwierigkeit)
        geprueft += 1
        try:
            aufgabe = M.erzeuge_matrix(rng, stufe, schwierigkeit)
        except Exception as e:
            erster_fehler = erster_fehler or f"seed {seed}: erzeuge_matrix wirft {e!r}"
            continue
        fehler = None
        eigen_ok, grund = M.pruefe_matrix(aufgabe)
        if not eigen_ok:
            fehler = f"seed {seed}: pruefe_matrix sagt nicht ok ({grund})"
        else:
            unabh_ok, grund2 = matrix_unabhaengig_ok(aufgabe)
            if not unabh_ok:
                fehler = f"seed {seed}: unabhängige Regelprüfung widerspricht ({grund2})"
            else:
                svg_fehler = _svg_serie_ok(aufgabe, "matrix")
                if svg_fehler:
                    fehler = f"seed {seed}: {svg_fehler}"
        if fehler:
            erster_fehler = erster_fehler or fehler
        else:
            bestanden += 1
    return geprueft, bestanden, erster_fehler


GESAMT_MX = BESTANDEN_MX = 0
for stufe in (4, 5):
    for schwierigkeit in (0, 1, 2, 3, 4, 5):
        geprueft, bestanden, fehler = matrix_serie(stufe, schwierigkeit, 60)
        GESAMT_MX += geprueft
        BESTANDEN_MX += bestanden
        ok(f"60 matrix bei stufe={stufe} schwierigkeit={schwierigkeit}: erzeugt, "
           f"pruefe_matrix ok, unabhängig nachgerechnet ok, SVG sauber",
           geprueft == bestanden, fehler)

ok(f"insgesamt {GESAMT_MX} matrix-Aufgaben über alle Stufen/Schwierigkeiten erzeugt",
   GESAMT_MX >= 40 and BESTANDEN_MX == GESAMT_MX, f"{BESTANDEN_MX}/{GESAMT_MX} bestanden")

# Latin-Staffel: Schwierigkeit 0/1 nie 'latin', Schwierigkeit >=3 immer mind. 1 'latin'
verletzung = ""
for stufe in (4, 5):
    for schwierigkeit in (0, 1):
        for seed in range(40):
            rng = random.Random(seed * 131 + stufe * 17 + schwierigkeit)
            aufgabe = M.erzeuge_matrix(rng, stufe, schwierigkeit)
            if "latin" in aufgabe["regeln"].values():
                verletzung = f"stufe={stufe} schwierigkeit={schwierigkeit} seed={seed}: latin trotz Verbot"
ok("Schwierigkeit 0/1 erzeugt nie eine 'latin'-Regel (40 Seeds je Stufe geprüft)",
   verletzung == "", verletzung)

verletzung = ""
for stufe in (4, 5):
    for schwierigkeit in (3, 4, 5):
        for seed in range(40):
            rng = random.Random(seed * 131 + stufe * 17 + schwierigkeit)
            aufgabe = M.erzeuge_matrix(rng, stufe, schwierigkeit)
            if "latin" not in aufgabe["regeln"].values():
                verletzung = f"stufe={stufe} schwierigkeit={schwierigkeit} seed={seed}: kein latin trotz Pflicht"
ok("Schwierigkeit >=3 erzeugt immer mindestens eine 'latin'-Regel (40 Seeds je Stufe geprüft)",
   verletzung == "", verletzung)

# Staffel: Stufe 4 hat genau ein konstantes Attribut, Stufe 5 keins
verletzung = ""
for seed in range(40):
    rng = random.Random(seed * 271 + 4)
    aufgabe = M.erzeuge_matrix(rng, 4, seed % 6)
    if list(aufgabe["regeln"].values()).count("konstant") != 1:
        verletzung = f"stufe 4 seed={seed}: nicht genau ein konstantes Attribut ({aufgabe['regeln']})"
    rng = random.Random(seed * 271 + 5)
    aufgabe = M.erzeuge_matrix(rng, 5, seed % 6)
    if "konstant" in aufgabe["regeln"].values():
        verletzung = verletzung or f"stufe 5 seed={seed}: konstantes Attribut vorhanden ({aufgabe['regeln']})"
ok("Stufe 4 hat genau ein konstantes Attribut, Stufe 5 keins (40 Seeds)", verletzung == "", verletzung)

# Determinismus
a = M.erzeuge_matrix(random.Random(2026), stufe=4, schwierigkeit=3)
b = M.erzeuge_matrix(random.Random(2026), stufe=4, schwierigkeit=3)
ok("gleicher Seed liefert byte-identische matrix-Aufgabe", a == b)
c = M.erzeuge_matrix(random.Random(2027), stufe=4, schwierigkeit=3)
ok("unterschiedlicher Seed liefert eine andere matrix-Aufgabe", a != c)


# ==================================================== Matrix: kaputte Fälle

_BASIS = M.erzeuge_matrix(random.Random(99), stufe=5, schwierigkeit=4)

# 1) Zelle verletzt Regel: eine der 8 gegebenen Zellen wird auf einen Wert
#    gesetzt, der die für ihre Zeile/Spalte geltende Regel bricht.
kaputt = dict(_BASIS)
kaputt["zellen"] = [list(z) for z in _BASIS["zellen"]]
alt_form = kaputt["zellen"][0][0]
fremd = next(f for f in M.FORMEN if f != alt_form)
kaputt["zellen"][0][0] = fremd
r = M.pruefe_matrix(kaputt)
ok("eine gegebene Zelle, die die Formregel bricht, wird abgelehnt", not r[0], str(r))

# 2) richtig außerhalb des gültigen Bereichs
kaputt2 = dict(_BASIS)
kaputt2["richtig"] = 4
r = M.pruefe_matrix(kaputt2)
ok("'richtig'=4 (außerhalb 0..3) wird abgelehnt", not r[0], str(r))

# 3) nur drei Optionen statt vier
kaputt3 = dict(_BASIS)
kaputt3["optionen"] = _BASIS["optionen"][:3]
kaputt3["optionen_svg"] = _BASIS["optionen_svg"][:3]
r = M.pruefe_matrix(kaputt3)
ok("nur drei Optionen statt vier werden abgelehnt", not r[0], str(r))

# 4) Ablenker gleich richtig: ein Ablenker wird zur exakten Kopie der
#    markierten richtigen Option (Duplikat) – zugleich eine "zweite
#    richtige Option" im engsten Sinn (identisch mit der Lösung).
kaputt4 = dict(_BASIS)
kaputt4["optionen"] = [list(o) for o in _BASIS["optionen"]]
andere_index = (_BASIS["richtig"] + 1) % 4
kaputt4["optionen"][andere_index] = list(_BASIS["optionen"][_BASIS["richtig"]])
r = M.pruefe_matrix(kaputt4)
ok("ein Ablenker als exakte Kopie der richtigen Option (Duplikat) wird abgelehnt", not r[0], str(r))

# 5) zweite richtige Option: die markierte Option und die tatsächlich
#    korrekte werden vertauscht, ohne den 'richtig'-Index anzupassen – an
#    Position 'richtig' steht jetzt ein falsches Tripel, während die echte
#    Lösung unmarkiert unter den Ablenkern liegt.
kaputt5 = dict(_BASIS)
kaputt5["optionen"] = [list(o) for o in _BASIS["optionen"]]
andere_index2 = (_BASIS["richtig"] + 2) % 4
kaputt5["optionen"][_BASIS["richtig"]], kaputt5["optionen"][andere_index2] = (
    kaputt5["optionen"][andere_index2], kaputt5["optionen"][_BASIS["richtig"]])
r = M.pruefe_matrix(kaputt5)
ok("die als richtig markierte Option zeigt auf ein falsches Tripel, während die "
   "echte Lösung unmarkiert im Array liegt ('zweite richtige Option')", not r[0], str(r))

# Kontrollfall: die unveränderte Basis-Aufgabe wird akzeptiert
r = M.pruefe_matrix(_BASIS)
ok("eine unveränderte, gültig erzeugte matrix-Aufgabe wird akzeptiert (Kontrollfall)", r[0], str(r))


# ============================================ Analogie: unabhängige Transformation
# Eigene Koordinatenformeln, nicht muster_kern._anwenden()/grafik_kern._spiegeln/
# _drehen aufgerufen.

def _normalisieren_unabhaengig(zellen):
    minr = min(r for r, c in zellen)
    minc = min(c for r, c in zellen)
    return {(r - minr, c - minc) for r, c in zellen}


def _spiegeln_unabhaengig(zellen):
    z = _normalisieren_unabhaengig(zellen)
    breite = max(c for r, c in z) + 1
    return _normalisieren_unabhaengig({(r, breite - 1 - c) for r, c in z})


def _drehen_unabhaengig(zellen, winkel):
    z = _normalisieren_unabhaengig(zellen)
    hoehe = max(r for r, c in z) + 1
    breite = max(c for r, c in z) + 1
    if winkel == 90:
        neu = {(c, hoehe - 1 - r) for r, c in z}
    elif winkel == 180:
        neu = {(hoehe - 1 - r, breite - 1 - c) for r, c in z}
    elif winkel == 270:
        neu = {(breite - 1 - c, r) for r, c in z}
    else:
        raise ValueError(f"unbekannter Winkel {winkel!r}")
    return _normalisieren_unabhaengig(neu)


def _anwenden_unabhaengig(transformation, zellen):
    if transformation == "spiegeln":
        return _spiegeln_unabhaengig(zellen)
    if transformation == "drehen90":
        return _drehen_unabhaengig(zellen, 90)
    if transformation == "drehen180":
        return _drehen_unabhaengig(zellen, 180)
    if transformation == "drehen270":
        return _drehen_unabhaengig(zellen, 270)
    raise ValueError(f"unbekannte Transformation {transformation!r}")


def _zusammenhaengend_unabhaengig(zellen):
    zellen = set(zellen)
    if not zellen:
        return False
    start = next(iter(zellen))
    besucht = {start}
    stapel = [start]
    while stapel:
        r, c = stapel.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n2 = (r + dr, c + dc)
            if n2 in zellen and n2 not in besucht:
                besucht.add(n2)
                stapel.append(n2)
    return besucht == zellen


def _als_menge(liste):
    return {(int(r), int(c)) for r, c in liste}


# ==================================================== Analogie: Serie über Seeds

def analogie_serie(stufe, schwierigkeit, anzahl_seeds):
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        rng = random.Random(seed * 7919 + stufe * 31 + schwierigkeit)
        geprueft += 1
        try:
            aufgabe = M.erzeuge_analogie(rng, stufe, schwierigkeit)
        except Exception as e:
            erster_fehler = erster_fehler or f"seed {seed}: erzeuge_analogie wirft {e!r}"
            continue
        fehler = None
        eigen_ok, grund = M.pruefe_analogie(aufgabe)
        if not eigen_ok:
            fehler = f"seed {seed}: pruefe_analogie sagt nicht ok ({grund})"
        else:
            a = _als_menge(aufgabe["a"])
            c = _als_menge(aufgabe["c"])
            optionen = [_als_menge(o) for o in aufgabe["optionen_zellen"]]
            richtig = aufgabe["richtig"]
            transformation = aufgabe["transformation"]
            if schwierigkeit >= 3 and transformation not in ("drehen270", "spiegeln"):
                fehler = f"seed {seed}: Schwierigkeit>=3 erlaubt nur drehen270/spiegeln, war {transformation!r}"
            elif len({frozenset(o) for o in optionen}) != 4:
                fehler = f"seed {seed}: die 4 Optionen sind als Zellmengen nicht paarweise verschieden"
            elif not all(_zusammenhaengend_unabhaengig(o) for o in optionen):
                fehler = f"seed {seed}: mindestens eine Option ist (unabhängig geprüft) nicht zusammenhängend"
            else:
                erwartet = _anwenden_unabhaengig(transformation, c)
                treffer = [i for i, o in enumerate(optionen) if frozenset(o) == frozenset(erwartet)]
                if treffer != [richtig]:
                    fehler = (f"seed {seed}: unabhängig berechnete korrekte Umwandlung von C passt zu "
                              f"Optionen {treffer}, als richtig markiert ist aber {richtig}")
                else:
                    svg_fehler = _svg_serie_ok(aufgabe, "analogie")
                    if svg_fehler:
                        fehler = f"seed {seed}: {svg_fehler}"
        if fehler:
            erster_fehler = erster_fehler or fehler
        else:
            bestanden += 1
    return geprueft, bestanden, erster_fehler


GESAMT_AN = BESTANDEN_AN = 0
for stufe in (6, 7):
    for schwierigkeit in (0, 1, 2, 3, 4, 5):
        geprueft, bestanden, fehler = analogie_serie(stufe, schwierigkeit, 60)
        GESAMT_AN += geprueft
        BESTANDEN_AN += bestanden
        ok(f"60 analogie bei stufe={stufe} schwierigkeit={schwierigkeit}: erzeugt, "
           f"pruefe_analogie ok, T(C) unabhängig nachgerechnet ok, Schwierigkeitsregel eingehalten, SVG sauber",
           geprueft == bestanden, fehler)

ok(f"insgesamt {GESAMT_AN} analogie-Aufgaben über alle Stufen/Schwierigkeiten erzeugt",
   GESAMT_AN >= 40 and BESTANDEN_AN == GESAMT_AN, f"{BESTANDEN_AN}/{GESAMT_AN} bestanden")

a = M.erzeuge_analogie(random.Random(2026), stufe=6, schwierigkeit=2)
b = M.erzeuge_analogie(random.Random(2026), stufe=6, schwierigkeit=2)
ok("gleicher Seed liefert byte-identische analogie-Aufgabe", a == b)
c = M.erzeuge_analogie(random.Random(2027), stufe=6, schwierigkeit=2)
ok("unterschiedlicher Seed liefert eine andere analogie-Aufgabe", a != c)


# ================================================== Analogie: kaputte Fälle

_BASIS_AN = M.erzeuge_analogie(random.Random(77), stufe=6, schwierigkeit=1)

# 1) falsche Transformation: das Feld 'transformation' behauptet etwas
#    anderes, als B tatsächlich zeigt.
kaputt = dict(_BASIS_AN)
andere_t = next(t for t in M.TRANSFORMATIONEN if t != _BASIS_AN["transformation"])
kaputt["transformation"] = andere_t
r = M.pruefe_analogie(kaputt)
ok("ein falsch angegebenes Transformationsfeld (B passt nicht zu 'transformation') wird abgelehnt",
   not r[0], str(r))

# 2) richtig außerhalb
kaputt2 = dict(_BASIS_AN)
kaputt2["richtig"] = -1
r = M.pruefe_analogie(kaputt2)
ok("'richtig'=-1 (außerhalb 0..3) wird abgelehnt", not r[0], str(r))

# 3) nur drei Optionen
kaputt3 = dict(_BASIS_AN)
kaputt3["optionen_zellen"] = _BASIS_AN["optionen_zellen"][:3]
kaputt3["optionen_svg"] = _BASIS_AN["optionen_svg"][:3]
r = M.pruefe_analogie(kaputt3)
ok("nur drei Optionen statt vier werden abgelehnt", not r[0], str(r))

# 4) Ablenker gleich richtig: ein Ablenker wird zur exakten Kopie der
#    korrekten Option (Duplikat).
kaputt4 = dict(_BASIS_AN)
kaputt4["optionen_zellen"] = [list(o) for o in _BASIS_AN["optionen_zellen"]]
andere_index = (_BASIS_AN["richtig"] + 1) % 4
kaputt4["optionen_zellen"][andere_index] = list(_BASIS_AN["optionen_zellen"][_BASIS_AN["richtig"]])
r = M.pruefe_analogie(kaputt4)
ok("ein Ablenker als exakte Kopie der richtigen Option (Duplikat) wird abgelehnt", not r[0], str(r))

# 5) zweite richtige Option: 'richtig' und die tatsächlich korrekte Option
#    werden vertauscht, ohne den Index anzupassen – an 'richtig' steht jetzt
#    ein Ablenker, während die echte Lösung unmarkiert im Array liegt.
kaputt5 = dict(_BASIS_AN)
kaputt5["optionen_zellen"] = [list(o) for o in _BASIS_AN["optionen_zellen"]]
andere_index2 = (_BASIS_AN["richtig"] + 2) % 4
kaputt5["optionen_zellen"][_BASIS_AN["richtig"]], kaputt5["optionen_zellen"][andere_index2] = (
    kaputt5["optionen_zellen"][andere_index2], kaputt5["optionen_zellen"][_BASIS_AN["richtig"]])
r = M.pruefe_analogie(kaputt5)
ok("die als richtig markierte Option ist nicht T(C), während die echte Lösung "
   "unmarkiert im Array liegt ('zweite richtige Option')", not r[0], str(r))

# 6) C verletzt die Grundvoraussetzung: C ist nicht zusammenhängend (kein
#    gültiges Polyomino mehr).
kaputt6 = dict(_BASIS_AN)
kaputt6["c"] = [[0, 0], [5, 5]]  # zwei isolierte Zellen, weit auseinander
r = M.pruefe_analogie(kaputt6)
ok("ein nicht zusammenhängendes C (kein Polyomino) wird abgelehnt", not r[0], str(r))

# Kontrollfall
r = M.pruefe_analogie(_BASIS_AN)
ok("eine unveränderte, gültig erzeugte analogie-Aufgabe wird akzeptiert (Kontrollfall)", r[0], str(r))


# ==================================================================== Demo-HTML

# Ablageort der Anschauungsdateien: MC_DEMO_DIR schlaegt alles, sonst ein
# Unterordner im Temp-Verzeichnis dieses Rechners.
DEMO_DIR = os.environ.get("MC_DEMO_DIR") or os.path.join(
    tempfile.gettempdir(), "mathcraft_demo", "muster")


def _demo_seite(titel, block_html):
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{titel}</title>'
            f'<style>body{{background:#0d1420;color:#e9ecef;font-family:sans-serif;padding:20px}}'
            f'.reihe{{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}}'
            f'.kachel{{width:150px;text-align:center}}'
            f'.kachel svg{{width:100%;height:auto;display:block;background:#111a2b;'
            f'border:1px solid #26334a;border-radius:8px}}'
            f'.marke{{margin-top:4px;font-size:13px}}'
            f'h1{{font-size:18px}} .kachel.gross{{width:420px}}</style></head><body>'
            f'<h1>{titel}</h1>{block_html}</body></html>')


def _demo_kachel(svg, marke, gross=False):
    klasse = "kachel gross" if gross else "kachel"
    return f'<div class="{klasse}">{svg}<div class="marke">{marke}</div></div>'


def _schreibe_demo():
    os.makedirs(DEMO_DIR, exist_ok=True)

    mx = M.erzeuge_matrix(random.Random(42), stufe=5, schwierigkeit=4)
    kacheln = "".join(
        _demo_kachel(svg, "richtig" if i == mx["richtig"] else f"Option {i}")
        for i, svg in enumerate(mx["optionen_svg"])
    )
    html = _demo_seite(
        "must_matrix – Demo",
        f'<div class="reihe"><div class="kachel gross">{mx["svg_frage"]}'
        f'<div class="marke">Frage (Regeln: {mx["regeln"]})</div></div></div>'
        f'<h1>Optionen</h1><div class="reihe">{kacheln}</div>',
    )
    with open(os.path.join(DEMO_DIR, "matrix.html"), "w", encoding="utf-8") as f:
        f.write(html)

    an = M.erzeuge_analogie(random.Random(42), stufe=6, schwierigkeit=2)
    kacheln = "".join(
        _demo_kachel(svg, "richtig" if i == an["richtig"] else f"Option {i}")
        for i, svg in enumerate(an["optionen_svg"])
    )
    html = _demo_seite(
        "must_analogie – Demo",
        f'<div class="reihe"><div class="kachel gross">{an["svg_frage"]}'
        f'<div class="marke">Frage (Transformation: {an["transformation"]})</div></div></div>'
        f'<h1>Optionen</h1><div class="reihe">{kacheln}</div>',
    )
    with open(os.path.join(DEMO_DIR, "analogie.html"), "w", encoding="utf-8") as f:
        f.write(html)

    return DEMO_DIR


# ==================================================================== Ausgabe

def main():
    fails = [r for r in RESULTS if not r[1]]
    for name, good, info in RESULTS:
        mark = "✅" if good else "❌"
        print(f"{mark} {name}" + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} bestanden")

    pfad = _schreibe_demo()
    print(f"\nAnschauungsdateien geschrieben nach {pfad}/")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
