# -*- coding: utf-8 -*-
"""Prüft den deterministischen Grafikkern (grafik_kern.py).

Im selben Geist wie raetsel_kern_test.py und validator_test.py: Der Kern ist
die einzige Stelle, die künftig garantiert, dass ein Würfelgebäude wirklich
eindeutig ablesbar ist und dass bei spiegelbild/drehfigur genau eine der vier
Optionen die mathematisch korrekte Transformation ist. Deshalb wird hier
NICHT dasselbe Prüfverfahren wiederholt aufgerufen, sondern für die kritische
Eigenschaft – die Sichtbarkeitsprüfung des Würfelgebäudes, und die Korrektheit
der Spiegelung/Drehung – eine zweite, unabhängig geschriebene Implementierung
danebengestellt. Stimmen beide überein, ist das kein Zufall zweier gleich
falscher Annahmen, weil die Herangehensweisen unterschiedlich sind (dichte
Pixel-Rasterung statt gezielter Abtastpunkte; eigene Spiegel-/Dreh-Formeln
statt Aufruf der internen Funktionen von grafik_kern.py).

  .venv/bin/python build/grafik_kern_test.py
"""
import random
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grafik_kern as G

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


ERLAUBTE_FARBEN = set(G.PALETTE) | {G.KONTUR, G.RASTER}
HEX_FARBE = re.compile(r"#[0-9a-fA-F]{6}")


# ============================================================ SVG-Strukturtest

def pruefe_svg_struktur(svg, name):
    """Wohlgeformtes XML, quadratische viewBox, kein width/height am
    Wurzelelement, kein Text-Knoten, nur erlaubte Farben. Gibt eine Liste
    gefundener Probleme zurück (leer = alles in Ordnung)."""
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
            if abs(breite - hoehe) > 0.01:
                probleme.append(f"{name}: viewBox ist nicht quadratisch ({vb})")
    for knoten in wurzel.iter():
        if (knoten.text and knoten.text.strip()) or (knoten.tail and knoten.tail.strip()):
            probleme.append(f"{name}: enthält Textinhalt ({knoten.tag})")
    for farbe in HEX_FARBE.findall(svg):
        if farbe.lower() not in {f.lower() for f in ERLAUBTE_FARBEN}:
            probleme.append(f"{name}: Farbe {farbe} liegt außerhalb der Palette")
    return probleme


def svg_sammeln(aufgabe, praefix):
    """Holt alle SVG-Strings aus einer erzeuge_*-Rückgabe, egal ob 'svg' oder
    'svg_frage'/'optionen_svg' die Felder heißen."""
    gefunden = []
    if "svg" in aufgabe:
        gefunden.append((f"{praefix}.svg", aufgabe["svg"]))
    if "svg_frage" in aufgabe:
        gefunden.append((f"{praefix}.svg_frage", aufgabe["svg_frage"]))
    for i, s in enumerate(aufgabe.get("optionen_svg", [])):
        gefunden.append((f"{praefix}.optionen_svg[{i}]", s))
    return gefunden


# ================================================ unabhängige Sichtbarkeitsprüfung
# (wuerfelgebaeude) – dichte Pixel-Rasterung statt der gezielten Abtastpunkte,
# die grafik_kern.py selbst benutzt: eigene Hexagon-Formeln, eigener
# Punkt-in-Polygon-Test, eigene Malerprinzip-Schleife.

def _hex_unabhaengig(r, c, h, tw=60, th=30, ch=34):
    X = (c - r) * (tw / 2)
    Y = (r + c) * (th / 2)
    top = Y - h * ch
    return [(X, top - th / 2), (X + tw / 2, top), (X + tw / 2, Y),
            (X, Y + th / 2), (X - tw / 2, Y), (X - tw / 2, top)]


def _top_unabhaengig(r, c, h, tw=60, th=30, ch=34):
    X = (c - r) * (tw / 2)
    Y = (r + c) * (th / 2)
    top = Y - h * ch
    return [(X, top - th / 2), (X + tw / 2, top), (X, top + th / 2), (X - tw / 2, top)]


def _pip_unabhaengig(px, py, poly):
    innen = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xs = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xs:
                innen = not innen
    return innen


def _linspace(a, b, n):
    if n == 1:
        return [(a + b) / 2]
    schritt = (b - a) / (n - 1)
    return [a + i * schritt for i in range(n)]


def sichtbarkeit_unabhaengig(hoehen):
    """True, wenn JEDE Säule mindestens einen Rasterpunkt ihrer Dach-/
    Bodenfläche hat, der in einem dichten 9×9-Raster über deren eigener
    Bounding-Box von KEINER näheren Säule (größeres Zeile+Spalte) überdeckt
    wird. Rechnet für jede Zelle unabhängig, ohne grafik_kern._saeule_sichtbar
    oder grafik_kern._abtastpunkte zu benutzen."""
    n = len(hoehen)
    zellen = [(r, c) for r in range(n) for c in range(n)]
    for (r, c) in zellen:
        h = hoehen[r][c]
        schwelle = r + c
        naeher = [(rr, cc) for rr, cc in zellen if rr + cc > schwelle]
        top = _top_unabhaengig(r, c, h)
        xs = [p[0] for p in top]
        ys = [p[1] for p in top]
        sichtbar = False
        for px in _linspace(min(xs), max(xs), 9):
            for py in _linspace(min(ys), max(ys), 9):
                if not _pip_unabhaengig(px, py, top):
                    continue
                if any(_pip_unabhaengig(px, py, _hex_unabhaengig(rr, cc, hoehen[rr][cc])) for rr, cc in naeher):
                    continue
                sichtbar = True
                break
            if sichtbar:
                break
        if not sichtbar:
            return False, (r, c)
    return True, None


# ======================================== unabhängige Spiegel-/Dreh-Formeln
# (spiegelbild/drehfigur) – eigener Code, nicht grafik_kern._spiegeln/_drehen.

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
    return {(r, c) for r, c in liste}


# ==================================================== wuerfelgebaeude: Serie

def wuerfelgebaeude_serie(stufe, anzahl_seeds):
    geprueft = bestanden = 0
    erster_fehler = ""
    anzahlen = []
    for seed in range(anzahl_seeds):
        rng = random.Random(seed * 7919 + stufe)
        geprueft += 1
        try:
            aufgabe = G.erzeuge_wuerfelgebaeude(rng, stufe)
        except Exception as e:
            erster_fehler = erster_fehler or f"seed {seed}: erzeuge_wuerfelgebaeude wirft {e!r}"
            continue
        anzahlen.append(aufgabe["anzahl"])
        fehler = None
        eigen_ok, grund = G.pruefe_wuerfelgebaeude(aufgabe)
        if not eigen_ok:
            fehler = f"seed {seed}: pruefe_wuerfelgebaeude sagt nicht ok ({grund})"
        else:
            unabh_ok, zelle = sichtbarkeit_unabhaengig(aufgabe["hoehen"])
            if not unabh_ok:
                fehler = f"seed {seed}: unabhängige Sichtbarkeitsprüfung findet verdeckte Säule {zelle}"
            elif aufgabe["anzahl"] != sum(sum(z) for z in aufgabe["hoehen"]):
                fehler = f"seed {seed}: 'anzahl' stimmt nicht mit den Höhen überein"
            else:
                for name, svg in svg_sammeln(aufgabe, "wuerfelgebaeude"):
                    probleme = pruefe_svg_struktur(svg, name)
                    if probleme:
                        fehler = f"seed {seed}: {probleme[0]}"
                        break
        if fehler:
            erster_fehler = erster_fehler or fehler
        else:
            bestanden += 1
    return geprueft, bestanden, erster_fehler, anzahlen


GESAMT_WG = BESTANDEN_WG = 0
DURCHSCHNITT_JE_STUFE_WG = {}
for stufe in (1, 3, 4, 5, 6, 8):
    geprueft, bestanden, fehler, anzahlen = wuerfelgebaeude_serie(stufe, 300)
    GESAMT_WG += geprueft
    BESTANDEN_WG += bestanden
    DURCHSCHNITT_JE_STUFE_WG[stufe] = sum(anzahlen) / len(anzahlen) if anzahlen else 0
    ok(f"300 wuerfelgebaeude bei stufe={stufe}: erzeugt, pruefe_* ok, "
       f"unabhängig sichtbar, SVG sauber", geprueft == bestanden, fehler)

ok(f"insgesamt {GESAMT_WG} wuerfelgebaeude über alle Stufen erzeugt",
   GESAMT_WG >= 300 and BESTANDEN_WG == GESAMT_WG, f"{BESTANDEN_WG}/{GESAMT_WG} bestanden")

ok("Stufen-Monotonie wuerfelgebaeude: mittlere Blockzahl wächst von Stufe 1 zu 8",
   DURCHSCHNITT_JE_STUFE_WG[1] < DURCHSCHNITT_JE_STUFE_WG[4] < DURCHSCHNITT_JE_STUFE_WG[8],
   str(DURCHSCHNITT_JE_STUFE_WG))

# Determinismus
a = G.erzeuge_wuerfelgebaeude(random.Random(2026), stufe=6)
b = G.erzeuge_wuerfelgebaeude(random.Random(2026), stufe=6)
ok("gleicher Seed liefert byte-identisches wuerfelgebaeude", a == b)
c = G.erzeuge_wuerfelgebaeude(random.Random(2027), stufe=6)
ok("unterschiedlicher Seed liefert ein anderes wuerfelgebaeude", a != c)


# ============================================= wuerfelgebaeude: kaputte Fälle
# Handgebaute Höhenraster, die pruefe_wuerfelgebaeude erkennen MUSS.

r = G.pruefe_wuerfelgebaeude({"hoehen": [[0, 0], [0, 0]], "anzahl": 0})
ok("ein leeres Raster (0 Blöcke) wird als zu wenig erkannt", not r[0], str(r))

r = G.pruefe_wuerfelgebaeude({"hoehen": [[1, 1], [1, 0]], "anzahl": 3})
ok("ein gültiges, kleines Raster wird akzeptiert (Kontrollfall)", r[0], str(r))

r = G.pruefe_wuerfelgebaeude({"hoehen": [[1, 1], [1, 0]], "anzahl": 99})
ok("eine falsch angegebene 'anzahl' wird erkannt", not r[0], str(r))

r = G.pruefe_wuerfelgebaeude({"hoehen": [[5, 1], [1, 1]], "anzahl": 8})
ok("eine Höhe außerhalb 0..4 wird erkannt", not r[0], str(r))

# Ein Raster, bei dem eine hintere Säule von einer sehr hohen vorderen
# Säule komplett verschluckt wird: (0,0) mit Höhe 1 hinter (2,2) mit
# Höhe 4 auf einem 3x3-Gitter – muss von der Sichtbarkeitsprüfung
# abgelehnt werden.
VERSTECKT = [[1, 0, 0], [0, 0, 0], [0, 0, 4]]
r = G.pruefe_wuerfelgebaeude({"hoehen": VERSTECKT, "anzahl": 5})
unabh_ok, versteckte_zelle = sichtbarkeit_unabhaengig(VERSTECKT)
ok("eine von einer hohen Säule komplett verdeckte hintere Säule wird von "
   "pruefe_wuerfelgebaeude UND der unabhängigen Prüfung abgelehnt",
   not r[0] and not unabh_ok, f"pruefe={r}, unabhängig sichtbar={unabh_ok} versteckt bei {versteckte_zelle}")


# ==================================================== spiegelbild: Serie

def spiegelbild_serie(stufe, anzahl_seeds):
    geprueft = bestanden = 0
    erster_fehler = ""
    groessen = []
    for seed in range(anzahl_seeds):
        rng = random.Random(seed * 7919 + stufe)
        geprueft += 1
        try:
            aufgabe = G.erzeuge_spiegelbild(rng, stufe)
        except Exception as e:
            erster_fehler = erster_fehler or f"seed {seed}: erzeuge_spiegelbild wirft {e!r}"
            continue
        groessen.append(len(aufgabe["zellen"]))
        fehler = None
        eigen_ok, grund = G.pruefe_spiegelbild(aufgabe)
        if not eigen_ok:
            fehler = f"seed {seed}: pruefe_spiegelbild sagt nicht ok ({grund})"
        else:
            zellen = _als_menge(aufgabe["zellen"])
            optionen = [_als_menge(o) for o in aufgabe["optionen_zellen"]]
            richtig = aufgabe["richtig"]
            mengen = {frozenset(o) for o in optionen}
            if len(mengen) != 4:
                fehler = f"seed {seed}: die 4 Optionen sind als Zellmengen nicht paarweise verschieden"
            elif not all(_zusammenhaengend_unabhaengig(o) for o in optionen):
                fehler = f"seed {seed}: mindestens eine Option ist (unabhängig geprüft) nicht zusammenhängend"
            else:
                erwartet = _spiegeln_unabhaengig(zellen)
                treffer = [i for i, o in enumerate(optionen) if frozenset(o) == frozenset(erwartet)]
                if treffer != [richtig]:
                    fehler = (f"seed {seed}: unabhängig berechnete korrekte Spiegelung passt zu "
                              f"Optionen {treffer}, als richtig markiert ist aber {richtig}")
                else:
                    for name, svg in svg_sammeln(aufgabe, "spiegelbild"):
                        probleme = pruefe_svg_struktur(svg, name)
                        if probleme:
                            fehler = f"seed {seed}: {probleme[0]}"
                            break
        if fehler:
            erster_fehler = erster_fehler or fehler
        else:
            bestanden += 1
    return geprueft, bestanden, erster_fehler, groessen


GESAMT_SB = BESTANDEN_SB = 0
DURCHSCHNITT_JE_STUFE_SB = {}
for stufe in (1, 3, 4, 5, 6, 8):
    geprueft, bestanden, fehler, groessen = spiegelbild_serie(stufe, 300)
    GESAMT_SB += geprueft
    BESTANDEN_SB += bestanden
    m, _ = G._spiegel_drehfigur_groessen(stufe)
    DURCHSCHNITT_JE_STUFE_SB[stufe] = m
    ok(f"300 spiegelbild bei stufe={stufe}: erzeugt, Optionen paarweise "
       f"verschieden, genau die richtige Option ist die korrekte Spiegelung (unabhängig nachgerechnet)",
       geprueft == bestanden, fehler)

ok(f"insgesamt {GESAMT_SB} spiegelbild-Rätsel über alle Stufen erzeugt",
   GESAMT_SB >= 300 and BESTANDEN_SB == GESAMT_SB, f"{BESTANDEN_SB}/{GESAMT_SB} bestanden")

ok("Stufen-Monotonie spiegelbild: Rastergröße m wächst von Stufe 1 zu 8",
   DURCHSCHNITT_JE_STUFE_SB[1] < DURCHSCHNITT_JE_STUFE_SB[4] < DURCHSCHNITT_JE_STUFE_SB[8],
   str(DURCHSCHNITT_JE_STUFE_SB))

a = G.erzeuge_spiegelbild(random.Random(2026), stufe=4)
b = G.erzeuge_spiegelbild(random.Random(2026), stufe=4)
ok("gleicher Seed liefert byte-identisches spiegelbild", a == b)
c = G.erzeuge_spiegelbild(random.Random(2027), stufe=4)
ok("unterschiedlicher Seed liefert ein anderes spiegelbild", a != c)


# ============================================== spiegelbild: kaputte Fälle

SYMMETRISCH = [[0, 0], [0, 1], [0, 2], [1, 1]]  # T-Form, spiegelsymmetrisch zur Mittelachse
basis = {
    "zellen": SYMMETRISCH,
    "optionen_zellen": [SYMMETRISCH, [[0, 0], [0, 1]], [[0, 0], [0, 1], [0, 2], [1, 0]], [[1, 0], [1, 1]]],
    "richtig": 0,
}
r = G.pruefe_spiegelbild(basis)
ok("eine spiegelsymmetrische Figur wird abgelehnt (Kopie-Ablenker wäre zweite Lösung)", not r[0], str(r))

L_FORM = [[0, 0], [1, 0], [2, 0], [2, 1]]
gespiegelt = [[0, 1], [1, 1], [2, 1], [2, 0]]
doppelt = {
    "zellen": L_FORM,
    "optionen_zellen": [gespiegelt, gespiegelt, [[0, 0], [1, 0], [2, 0], [2, 1]], [[0, 0], [1, 0]]],
    "richtig": 0,
}
r = G.pruefe_spiegelbild(doppelt)
ok("zwei identische Optionen werden als nicht paarweise verschieden erkannt", not r[0], str(r))

falsch_markiert = {
    "zellen": L_FORM,
    "optionen_zellen": [L_FORM, gespiegelt, [[0, 0], [0, 1], [0, 2], [1, 0]], [[3, 3], [3, 4], [3, 5], [4, 4]]],
    "richtig": 0,  # Option 0 ist die UNGESPIEGELTE Kopie, nicht die Spiegelung
}
r = G.pruefe_spiegelbild(falsch_markiert)
ok("eine falsch als richtig markierte Option (Kopie statt Spiegelung) wird erkannt",
   not r[0] and "richtig markierte" in r[1], str(r))


# ==================================================== drehfigur: Serie

def drehfigur_serie(stufe, anzahl_seeds):
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        rng = random.Random(seed * 7919 + stufe)
        geprueft += 1
        try:
            aufgabe = G.erzeuge_drehfigur(rng, stufe)
        except Exception as e:
            erster_fehler = erster_fehler or f"seed {seed}: erzeuge_drehfigur wirft {e!r}"
            continue
        fehler = None
        eigen_ok, grund = G.pruefe_drehfigur(aufgabe)
        if not eigen_ok:
            fehler = f"seed {seed}: pruefe_drehfigur sagt nicht ok ({grund})"
        else:
            zellen = _als_menge(aufgabe["zellen"])
            optionen = [_als_menge(o) for o in aufgabe["optionen_zellen"]]
            richtig = aufgabe["richtig"]
            winkel = aufgabe["winkel"]
            mengen = {frozenset(o) for o in optionen}
            if len(mengen) != 4:
                fehler = f"seed {seed}: die 4 Optionen sind als Zellmengen nicht paarweise verschieden"
            elif not all(_zusammenhaengend_unabhaengig(o) for o in optionen):
                fehler = f"seed {seed}: mindestens eine Option ist (unabhängig geprüft) nicht zusammenhängend"
            else:
                erwartet = _drehen_unabhaengig(zellen, winkel)
                treffer = [i for i, o in enumerate(optionen) if frozenset(o) == frozenset(erwartet)]
                if treffer != [richtig]:
                    fehler = (f"seed {seed}: unabhängig berechnete korrekte Drehung passt zu "
                              f"Optionen {treffer}, als richtig markiert ist aber {richtig}")
                else:
                    for name, svg in svg_sammeln(aufgabe, "drehfigur"):
                        probleme = pruefe_svg_struktur(svg, name)
                        if probleme:
                            fehler = f"seed {seed}: {probleme[0]}"
                            break
        if fehler:
            erster_fehler = erster_fehler or fehler
        else:
            bestanden += 1
    return geprueft, bestanden, erster_fehler


GESAMT_DF = BESTANDEN_DF = 0
for stufe in (1, 3, 4, 5, 6, 8):
    geprueft, bestanden, fehler = drehfigur_serie(stufe, 300)
    GESAMT_DF += geprueft
    BESTANDEN_DF += bestanden
    ok(f"300 drehfigur bei stufe={stufe}: erzeugt, Optionen paarweise "
       f"verschieden, genau die richtige Option ist die korrekte Drehung (unabhängig nachgerechnet)",
       geprueft == bestanden, fehler)

ok(f"insgesamt {GESAMT_DF} drehfigur-Rätsel über alle Stufen erzeugt",
   GESAMT_DF >= 300 and BESTANDEN_DF == GESAMT_DF, f"{BESTANDEN_DF}/{GESAMT_DF} bestanden")

a = G.erzeuge_drehfigur(random.Random(2026), stufe=4)
b = G.erzeuge_drehfigur(random.Random(2026), stufe=4)
ok("gleicher Seed liefert byte-identische drehfigur", a == b)
c = G.erzeuge_drehfigur(random.Random(2027), stufe=4)
ok("unterschiedlicher Seed liefert eine andere drehfigur", a != c)


# =============================================== drehfigur: kaputte Fälle

QUADRAT_2X2 = [[0, 0], [0, 1], [1, 0], [1, 1]]  # unter 90/180/270 drehsymmetrisch
r = G.pruefe_drehfigur({"zellen": QUADRAT_2X2, "winkel": 90,
                        "optionen_zellen": [QUADRAT_2X2, [[0, 0]], [[0, 0], [0, 1]], [[1, 1]]],
                        "richtig": 0})
ok("eine unter dem gewürfelten Winkel drehsymmetrische Figur wird abgelehnt", not r[0], str(r))

L_FORM2 = [[0, 0], [1, 0], [2, 0], [2, 1]]
gedreht_90 = sorted(_drehen_unabhaengig(_als_menge(L_FORM2), 90))
gedreht_90 = [list(z) for z in gedreht_90]
r = G.pruefe_drehfigur({
    "zellen": L_FORM2, "winkel": 90,
    "optionen_zellen": [gedreht_90, gedreht_90, [[0, 0], [1, 0]], [[3, 3], [3, 4]]],
    "richtig": 0,
})
ok("zwei identische Options-Zellmengen bei drehfigur werden erkannt", not r[0], str(r))

r = G.pruefe_drehfigur({
    "zellen": L_FORM2, "winkel": 90,
    "optionen_zellen": [L_FORM2, gedreht_90, [[5, 5], [5, 6], [6, 5], [6, 6]], [[3, 3], [3, 4], [3, 5], [4, 4]]],
    "richtig": 0,  # Option 0 ist das UNGEDREHTE Original, nicht die 90°-Drehung
})
ok("eine falsch als richtig markierte Option (Original statt Drehung) wird erkannt",
   not r[0] and "richtig markierte" in r[1], str(r))

r = G.pruefe_drehfigur({"zellen": L_FORM2, "winkel": 45,
                        "optionen_zellen": [gedreht_90, [[0, 0]], [[0, 1]], [[1, 1]]], "richtig": 0})
ok("ein ungültiger Winkel (nicht 90/180/270) wird abgelehnt", not r[0], str(r))


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
