# -*- coding: utf-8 -*-
"""Der deterministische Musterkern für Mustererkennungs-Aufgaben (ZIELE-V2.md,
D1/D4, SPEC_lektionen_v2.md §5).

Wie raetsel_kern.py bei Logikgittern und grafik_kern.py bei Spiegelbild/
Drehfigur/Würfelgebäude dreht dieses Modul das Erzeugungsprinzip um: Ein
Sprachmodell erkennt keine Musterregeln zuverlässig und kann nicht rechnerisch
garantieren, dass unter vier Bildoptionen genau eine richtig ist – es würde
Lateinische Quadrate so zuverlässig hinbekommen wie unlösbare Logikrätsel.
Deshalb entsteht hier zuerst die Regel (bzw. die Transformation), die Zellen
werden aus ihr berechnet, und erst danach malt reiner SVG-Code das bereits
feststehende Ergebnis. Ein LLM kommt an dieser Stelle nicht vor.

Zwei Aufgabenfamilien, je als erzeuge_<name>(rng, stufe, schwierigkeit) /
pruefe_<name>(aufgabe)-Paar:

  1. matrix – eine 3×3-Bildmatrix aus Form/Farbe/Anzahl. Jedes Attribut folgt
     einer eigenen Regel (zeile/spalte/latin/zaehlt/konstant); das Feld unten
     rechts ist gesucht. Weil jede der drei Regeln den Wert an dieser Stelle
     aus den acht übrigen Zellen eindeutig bestimmt (eine Zeile UND eine
     Spalte sind dort bereits vollständig gegeben), kann es bei korrekt
     konstruierten Zellen nur eine gültige Lösung geben – pruefe_matrix()
     rechnet genau das nach, ohne die SVG-Bilder je anzusehen.

  2. analogie – "A verhält sich zu B wie C zu ?". Eine Umwandlung T (spiegeln
     oder eine 90/180/270°-Drehung) führt A nach B; gesucht ist T(C). Die
     Polyomino-Geometrie (Zellmengen, Spiegeln, Drehen, Zusammenhang) kommt
     unverändert aus grafik_kern.py – sie wird importiert, nicht neu
     erfunden, denn dieselbe Wahrheit gilt hier wie bei Spiegelbild/
     Drehfigur: eine Transformation ist entweder korrekt oder nicht, das
     lässt sich nur einmal richtig implementieren.

Für beide Familien gilt dieselbe Eindeutigkeits-Disziplin wie in
grafik_kern.py: Jede Eigenschaft, die eine Aufgabe lösbar/eindeutig macht,
wird über die reinen Daten (Attribut-Tripel bzw. Zellmengen) nachgerechnet,
nie über SVG-Text – die Rückgabe führt deshalb zusätzlich zu den Bildern
immer die zugrunde liegende Wahrheit mit (bei matrix: "zellen"/"optionen"
als Attribut-Tripel, bei analogie: "a"/"b"/"c"/"optionen_zellen" als
Zellmengen).

Alle SVGs: quadratische viewBox, kein width/height am Wurzelelement, kein
Text, Flächenfarben ausschließlich aus grafik_kern.PALETTE, Kontur KONTUR,
Raster RASTER; das gesuchte Feld bleibt leer mit gestricheltem Rand in
Farbe "#e9ecef" (das ist PALETTE[3] – keine Farbe außerhalb der Palette).
"""
import random

from grafik_kern import (
    PALETTE, KONTUR, RASTER,
    _zufallspolyomino, _spiegeln, _drehen, _normalisieren, _zusammenhaengend,
    _als_liste, _als_zellmenge, _grid_lines_svg, _zellen_svg, _svg_wrap,
    UNIT, RAND_FIGUR,
)

LEER_FARBE = "#e9ecef"  # == PALETTE[3]; eigener Name nur zur Lesbarkeit an den
                         # Stellen, an denen es um "das leere gesuchte Feld" geht


def _fmt(x):
    """Formatiert eine Koordinate möglichst kompakt (ganzzahlig, wenn möglich).
    Eigene, kleine Kopie der Formatierlogik aus grafik_kern – reine
    Zahlenkosmetik, keine wahrheitstragende Geometrie, deshalb kein Import
    nötig (grafik_kern._fmt steht ohnehin nicht in der Importliste)."""
    r = round(x, 2)
    if r == int(r):
        return str(int(r))
    return f"{r:g}"


def _poly(punkte, fill, stroke=KONTUR, stroke_width=1.6):
    pts = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in punkte)
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>'


# ===================================================================
# Teil A — figürliche 3×3-Bildmatrix (must_matrix)
# ===================================================================

FORMEN = ("kreis", "quadrat", "dreieck", "raute")
ANZAHLEN = (1, 2, 3)

# Eigene Zeichenfunktionen je Form (Auftrag verlangt für die Matrix
# eigenständiges Rendering statt Import aus grafik_kern; die Formen selbst
# kommen dort auch nicht vor). Jede Funktion zeichnet EIN Exemplar,
# zentriert um (cx, cy), mit "Radius" r – _zelle_inhalt_svg() ruft sie
# 1..3 mal nebeneinander auf.

def _form_kreis(cx, cy, r, farbe):
    return f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(r)}" fill="{farbe}" stroke="{KONTUR}" stroke-width="1.6"/>'


def _form_quadrat(cx, cy, r, farbe):
    s = r * 1.7
    x, y = cx - s / 2, cy - s / 2
    return f'<rect x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(s)}" height="{_fmt(s)}" fill="{farbe}" stroke="{KONTUR}" stroke-width="1.6"/>'


def _form_dreieck(cx, cy, r, farbe):
    pts = [(cx, cy - r), (cx + r * 0.95, cy + r * 0.75), (cx - r * 0.95, cy + r * 0.75)]
    return _poly(pts, farbe)


def _form_raute(cx, cy, r, farbe):
    pts = [(cx, cy - r), (cx + r * 0.82, cy), (cx, cy + r), (cx - r * 0.82, cy)]
    return _poly(pts, farbe)


_FORM_ZEICHNER = {
    "kreis": _form_kreis,
    "quadrat": _form_quadrat,
    "dreieck": _form_dreieck,
    "raute": _form_raute,
}

MZELLE = 90   # Zellgröße der Bildmatrix (eigenständig, unabhängig von UNIT)
M_PAD = 13    # Innenabstand einer Zelle zum Formen-Bereich


def _zelle_inhalt_svg(form, farbe, anzahl):
    """Zeichnet 'anzahl' (1..3) Exemplare von 'form' in 'farbe' nebeneinander,
    zentriert innerhalb einer MZELLE×MZELLE großen Zelle (lokaler Ursprung
    oben links bei (0,0))."""
    zeichner = _FORM_ZEICHNER.get(form)
    if zeichner is None:
        raise ValueError(f"unbekannte Form {form!r}")
    innen = MZELLE - 2 * M_PAD
    slot = innen / anzahl
    r = slot / 2 * 0.68
    cy = MZELLE / 2
    teile = []
    for i in range(anzahl):
        cx = M_PAD + slot * (i + 0.5)
        teile.append(zeichner(cx, cy, r, farbe))
    return "".join(teile)


def _matrix_rasterlinien():
    """Eigene 3×3-Rasterlinien in RASTER-Farbe (eigenständig statt Import,
    siehe Moduldocstring: die Matrix bekommt bewusst eigenes Rendering)."""
    teile = []
    for i in range(4):
        teile.append(f'<line x1="0" y1="{i * MZELLE}" x2="{3 * MZELLE}" y2="{i * MZELLE}" '
                      f'stroke="{RASTER}" stroke-width="1"/>')
        teile.append(f'<line x1="{i * MZELLE}" y1="0" x2="{i * MZELLE}" y2="{3 * MZELLE}" '
                      f'stroke="{RASTER}" stroke-width="1"/>')
    return "".join(teile)


def _render_matrix(gegeben, leer):
    """gegeben: {(r,c): (form,farbe,anzahl)} für die belegten Felder.
    leer: (r,c)-Position, die leer mit gestricheltem Rand bleibt."""
    teile = [_matrix_rasterlinien()]
    for (r, c), (form, farbe, anzahl) in gegeben.items():
        inhalt = _zelle_inhalt_svg(form, farbe, anzahl)
        teile.append(f'<g transform="translate({c * MZELLE},{r * MZELLE})">{inhalt}</g>')
    if leer is not None:
        r, c = leer
        x, y = c * MZELLE, r * MZELLE
        rand = 5
        teile.append(f'<rect x="{x + rand}" y="{y + rand}" width="{MZELLE - 2 * rand}" '
                      f'height="{MZELLE - 2 * rand}" fill="none" stroke="{LEER_FARBE}" '
                      f'stroke-width="3" stroke-dasharray="6,5"/>')
    inhalt = "".join(teile)
    return _svg_wrap(3 * MZELLE, 3 * MZELLE, RAND_FIGUR, inhalt)


def _render_matrix_zelle(form, farbe, anzahl):
    """Eine einzelne Zelle als eigenes Options-SVG (mit dünnem Rasterrahmen
    zur optischen Konsistenz mit der Frage-Matrix)."""
    rahmen = f'<rect x="0" y="0" width="{MZELLE}" height="{MZELLE}" fill="none" stroke="{RASTER}" stroke-width="1"/>'
    inhalt = rahmen + _zelle_inhalt_svg(form, farbe, anzahl)
    return _svg_wrap(MZELLE, MZELLE, RAND_FIGUR, inhalt)


def _baue_belegung(regelname, werte, rng):
    """Liefert ein dict {(r,c): wert} für r,c in 0..2, gemäß Regeltyp.
    'werte' ist die (für konstant: einelementige, sonst dreielementige)
    Werteliste, aus der die Regel schöpft."""
    if regelname == "konstant":
        wert = werte[0]
        return {(r, c): wert for r in range(3) for c in range(3)}
    if regelname == "zeile":
        zw = list(werte)
        rng.shuffle(zw)
        return {(r, c): zw[r] for r in range(3) for c in range(3)}
    if regelname == "spalte":
        zw = list(werte)
        rng.shuffle(zw)
        return {(r, c): zw[c] for r in range(3) for c in range(3)}
    if regelname == "latin":
        zw = list(werte)
        rng.shuffle(zw)
        # Zyklisches Basisquadrat, zusätzlich zeilen-/spaltenweise durch-
        # mischt – bleibt lateinisch (Standardfakt), liefert aber mehr
        # Variation als immer dasselbe Diagonalmuster.
        zp = list(range(3))
        rng.shuffle(zp)
        sp = list(range(3))
        rng.shuffle(sp)
        return {(r, c): zw[(zp[r] + sp[c]) % 3] for r in range(3) for c in range(3)}
    if regelname == "zaehlt":
        return {(r, c): c + 1 for r in range(3) for c in range(3)}
    raise ValueError(f"unbekannte Regel {regelname!r}")


def _regel_ok(regelname, werte):
    """werte: vollständiges dict {(r,c): wert} für ein einzelnes Attribut
    über die ganze 3×3-Matrix. Prüft rein aus den tatsächlichen Werten,
    unabhängig davon, wie sie erzeugt wurden."""
    if regelname == "konstant":
        return len(set(werte.values())) == 1
    if regelname == "zeile":
        zeilenwerte = []
        for r in range(3):
            zeile = {werte[(r, c)] for c in range(3)}
            if len(zeile) != 1:
                return False
            zeilenwerte.append(next(iter(zeile)))
        return len(set(zeilenwerte)) == 3
    if regelname == "spalte":
        spaltenwerte = []
        for c in range(3):
            spalte = {werte[(r, c)] for r in range(3)}
            if len(spalte) != 1:
                return False
            spaltenwerte.append(next(iter(spalte)))
        return len(set(spaltenwerte)) == 3
    if regelname == "latin":
        gesamt = set(werte.values())
        if len(gesamt) != 3:
            return False
        for r in range(3):
            if {werte[(r, c)] for c in range(3)} != gesamt:
                return False
        for c in range(3):
            if {werte[(r, c)] for r in range(3)} != gesamt:
                return False
        return True
    if regelname == "zaehlt":
        return all(werte[(r, c)] == c + 1 for r in range(3) for c in range(3))
    return False


_ATTRIBUTE = ("form", "farbe", "anzahl")
_ATTR_INDEX = {"form": 0, "farbe": 1, "anzahl": 2}
_ERLAUBT_FORM_FARBE = {"zeile", "spalte", "latin", "konstant"}
_ERLAUBT_ANZAHL = {"zeile", "spalte", "latin", "zaehlt", "konstant"}


def _domaene(attribut):
    if attribut == "form":
        return FORMEN
    if attribut == "farbe":
        return PALETTE
    return ANZAHLEN


def erzeuge_matrix(rng, stufe, schwierigkeit):
    """Baut eine 3×3-Bildmatrix. Stufe 4: zwei Attribute variieren (eines ist
    'konstant'); Stufe 5: alle drei. Schwierigkeit ≥3 erzwingt mindestens
    eine 'latin'-Regel, Schwierigkeit ≤1 verbietet sie – beides über
    Neuwürfeln, nicht über nachträgliches Zurechtbiegen einer Regelwahl."""
    if stufe not in (4, 5):
        raise ValueError(f"unbekannte Matrix-Stufe {stufe!r}, erlaubt sind 4/5")

    for _ in range(200):
        if stufe == 4:
            konstant_attr = rng.choice(_ATTRIBUTE)
            variierend = [a for a in _ATTRIBUTE if a != konstant_attr]
        else:
            konstant_attr = None
            variierend = list(_ATTRIBUTE)

        regeln = {}
        if konstant_attr is not None:
            regeln[konstant_attr] = "konstant"
        for attr in variierend:
            optionen_regel = ["zeile", "spalte", "latin"]
            if attr == "anzahl":
                optionen_regel.append("zaehlt")
            regeln[attr] = rng.choice(optionen_regel)

        anzahl_latin = sum(1 for a in variierend if regeln[a] == "latin")
        if schwierigkeit >= 3 and anzahl_latin == 0:
            continue
        if schwierigkeit <= 1 and anzahl_latin > 0:
            continue

        belegungen = {}
        for attr in _ATTRIBUTE:
            domaene = _domaene(attr)
            regel = regeln[attr]
            if regel == "konstant":
                werte = [rng.choice(domaene)]
            elif regel == "zaehlt":
                werte = list(ANZAHLEN)
            elif attr == "anzahl":
                werte = list(ANZAHLEN)
            else:
                werte = rng.sample(domaene, 3)
            belegungen[attr] = _baue_belegung(regel, werte, rng)

        matrix = {
            (r, c): (belegungen["form"][(r, c)], belegungen["farbe"][(r, c)], belegungen["anzahl"][(r, c)])
            for r in range(3) for c in range(3)
        }
        richtige_zelle = matrix[(2, 2)]

        attr_reihenfolge = list(_ATTRIBUTE)
        rng.shuffle(attr_reihenfolge)
        ablenker = []
        erfolg = True
        for attr in attr_reihenfolge:
            domaene = _domaene(attr)
            idx = _ATTR_INDEX[attr]
            kandidaten = [w for w in domaene if w != richtige_zelle[idx]]
            if not kandidaten:
                erfolg = False
                break
            neu = list(richtige_zelle)
            neu[idx] = rng.choice(kandidaten)
            ablenker.append(tuple(neu))
        if not erfolg:
            continue

        kandidaten_optionen = [richtige_zelle] + ablenker
        if len(set(kandidaten_optionen)) != 4:
            continue  # Kollision (Ablenker zufällig gleich einer anderen Option) – neu würfeln

        reihenfolge = list(range(4))
        rng.shuffle(reihenfolge)
        optionen = [kandidaten_optionen[i] for i in reihenfolge]
        richtig = reihenfolge.index(0)

        gegeben = {(r, c): matrix[(r, c)] for r in range(3) for c in range(3) if (r, c) != (2, 2)}
        zellen_liste = [
            list(matrix[(r, c)]) for r in range(3) for c in range(3) if (r, c) != (2, 2)
        ]

        return {
            "svg_frage": _render_matrix(gegeben, leer=(2, 2)),
            "optionen_svg": [_render_matrix_zelle(*o) for o in optionen],
            "optionen": [list(o) for o in optionen],
            "richtig": richtig,
            "zellen": zellen_liste,
            "regeln": dict(regeln),
            "stufe": stufe,
        }
    raise ValueError("konnte nach 200 Versuchen keine eindeutige Bildmatrix erzeugen")


def _tripel_ok(t):
    return (isinstance(t, (list, tuple)) and len(t) == 3
            and t[0] in FORMEN and t[1] in PALETTE and t[2] in ANZAHLEN)


def pruefe_matrix(aufgabe):
    """Rechnet nach: Die acht gegebenen Zellen plus die als richtig markierte
    Option erfüllen alle drei Regeln; jeder der drei Ablenker verletzt an
    Position (2,2) mindestens eine davon; alle vier Optionen sind als
    Tripel paarweise verschieden. Verträgt beliebig kaputte Eingaben, ohne
    abzustürzen."""
    try:
        zellen = aufgabe["zellen"]
        optionen = aufgabe["optionen"]
        richtig = aufgabe["richtig"]
        regeln = aufgabe["regeln"]
        stufe = aufgabe["stufe"]
    except (KeyError, TypeError):
        return False, "Aufgabe hat kein gültiges Format"

    if stufe not in (4, 5):
        return False, f"Stufe {stufe!r} ist nicht 4 oder 5"
    if not isinstance(zellen, list) or len(zellen) != 8:
        return False, f"{len(zellen) if isinstance(zellen, list) else zellen!r} gegebene Zellen statt 8"
    if not isinstance(optionen, list) or len(optionen) != 4:
        return False, f"{len(optionen) if isinstance(optionen, list) else optionen!r} Optionen statt 4"
    if not isinstance(richtig, int) or not (0 <= richtig < 4):
        return False, f"'richtig'={richtig!r} ist kein gültiger Options-Index"
    if not isinstance(regeln, dict) or set(regeln) != {"form", "farbe", "anzahl"}:
        return False, f"'regeln' hat nicht genau die Schlüssel form/farbe/anzahl ({regeln!r})"
    if regeln["form"] not in _ERLAUBT_FORM_FARBE or regeln["farbe"] not in _ERLAUBT_FORM_FARBE:
        return False, f"ungültige Regel für form/farbe: {regeln!r}"
    if regeln["anzahl"] not in _ERLAUBT_ANZAHL:
        return False, f"ungültige Regel für anzahl: {regeln['anzahl']!r}"
    if not all(_tripel_ok(z) for z in zellen):
        return False, "mindestens eine gegebene Zelle ist kein gültiges (form,farbe,anzahl)-Tripel"
    if not all(_tripel_ok(o) for o in optionen):
        return False, "mindestens eine Option ist kein gültiges (form,farbe,anzahl)-Tripel"
    if len({tuple(o) for o in optionen}) != 4:
        return False, "die vier Optionen sind nicht paarweise verschieden"

    positionen = [(r, c) for r in range(3) for c in range(3) if (r, c) != (2, 2)]
    matrix = {pos: tuple(z) for pos, z in zip(positionen, zellen)}
    matrix[(2, 2)] = tuple(optionen[richtig])

    for attr in _ATTRIBUTE:
        idx = _ATTR_INDEX[attr]
        werte = {pos: t[idx] for pos, t in matrix.items()}
        if not _regel_ok(regeln[attr], werte):
            return False, f"die gegebenen Zellen plus die richtige Option erfüllen die Regel '{regeln[attr]}' für {attr} nicht"

    for i, o in enumerate(optionen):
        if i == richtig:
            continue
        testmatrix = dict(matrix)
        testmatrix[(2, 2)] = tuple(o)
        verletzt = False
        for attr in _ATTRIBUTE:
            idx = _ATTR_INDEX[attr]
            werte = {pos: t[idx] for pos, t in testmatrix.items()}
            if not _regel_ok(regeln[attr], werte):
                verletzt = True
                break
        if not verletzt:
            return False, f"Ablenker {i} erfüllt an der gesuchten Stelle ebenfalls alle Regeln – wäre eine zweite Lösung"

    return True, "Bildmatrix ist eindeutig: die gegebenen Zellen und die richtige Option erfüllen alle Regeln, jeder Ablenker verletzt mindestens eine"


# ===================================================================
# Teil B — Analogie "A verhält sich zu B wie C zu ?" (must_analogie)
# ===================================================================

TRANSFORMATIONEN = ("spiegeln", "drehen90", "drehen180", "drehen270")

PFEIL_BREITE = UNIT * 1.15
PFEIL_LUECKE = UNIT * 0.3
TRENNER_BREITE = UNIT * 0.55


def _anwenden(transformation, zellen):
    if transformation == "spiegeln":
        return _spiegeln(zellen)
    if transformation == "drehen90":
        return _drehen(zellen, 90)
    if transformation == "drehen180":
        return _drehen(zellen, 180)
    if transformation == "drehen270":
        return _drehen(zellen, 270)
    raise ValueError(f"unbekannte Transformation {transformation!r}")


def _analogie_groessen(stufe):
    if stufe == 6:
        return 5, (5, 7)
    if stufe == 7:
        return 6, (6, 9)
    raise ValueError(f"unbekannte Analogie-Stufe {stufe!r}, erlaubt sind 6/7")


def _pfeil_svg(x0, mitte_y, breite, farbe=LEER_FARBE):
    """Ein nach rechts zeigender Pfeil als EIN Polygon (Schaft + Kopf) –
    kein Text, wie an allen Rendering-Stellen des Projekts gefordert."""
    schaft_h = UNIT * 0.14
    kopf_h = UNIT * 0.42
    kopf_breite = breite * 0.42
    schaft_breite = breite - kopf_breite
    pts = [
        (x0, mitte_y - schaft_h / 2),
        (x0 + schaft_breite, mitte_y - schaft_h / 2),
        (x0 + schaft_breite, mitte_y - kopf_h / 2),
        (x0 + breite, mitte_y),
        (x0 + schaft_breite, mitte_y + kopf_h / 2),
        (x0 + schaft_breite, mitte_y + schaft_h / 2),
        (x0, mitte_y + schaft_h / 2),
    ]
    return _poly(pts, farbe, stroke=KONTUR, stroke_width=1.2)


def _render_analogie_option(zellen, m, farbe):
    inhalt = _grid_lines_svg(m) + _zellen_svg(zellen, farbe)
    return _svg_wrap(m * UNIT, m * UNIT, RAND_FIGUR, inhalt)


def _svg_wrap_breit(breite, hoehe, rand, inhalt):
    """Wie grafik_kern._svg_wrap(), aber OHNE die quadratische viewBox: Das
    Analogie-Fragebild reiht sieben Elemente (A, Pfeil, B, Trenner, C, Pfeil,
    leeres Raster) nebeneinander auf – bei einer erzwungenen quadratischen
    viewBox bliebe oben/unten mehr als die Hälfte der Fläche leer, und auf
    einem schmalen Handybildschirm würden die Figuren winzig. Die viewBox
    folgt hier stattdessen der tatsächlichen Inhaltsform: Höhe = Rasterhöhe
    + 2·Rand, Breite = tatsächliche Inhaltsbreite + 2·Rand. Options-SVGs und
    die Bildmatrix bleiben unverändert quadratisch (_svg_wrap oben)."""
    w = breite + 2 * rand
    h = hoehe + 2 * rand
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(w)} {_fmt(h)}">'
            f'<g transform="translate({_fmt(rand)},{_fmt(rand)})">{inhalt}</g></svg>')


def _render_analogie_frage(a, b, c, m, farbe):
    y_mitte = m * UNIT / 2
    x = 0.0
    teile = []

    teile.append(f'<g transform="translate({_fmt(x)},0)">{_grid_lines_svg(m)}{_zellen_svg(a, farbe)}</g>')
    x += m * UNIT

    teile.append(_pfeil_svg(x + PFEIL_LUECKE, y_mitte, PFEIL_BREITE))
    x += PFEIL_BREITE + 2 * PFEIL_LUECKE

    teile.append(f'<g transform="translate({_fmt(x)},0)">{_grid_lines_svg(m)}{_zellen_svg(b, farbe)}</g>')
    x += m * UNIT

    tx = x + TRENNER_BREITE / 2
    teile.append(f'<line x1="{_fmt(tx)}" y1="0" x2="{_fmt(tx)}" y2="{_fmt(m * UNIT)}" '
                 f'stroke="{RASTER}" stroke-width="2" stroke-dasharray="4,4"/>')
    x += TRENNER_BREITE

    teile.append(f'<g transform="translate({_fmt(x)},0)">{_grid_lines_svg(m)}{_zellen_svg(c, farbe)}</g>')
    x += m * UNIT

    teile.append(_pfeil_svg(x + PFEIL_LUECKE, y_mitte, PFEIL_BREITE))
    x += PFEIL_BREITE + 2 * PFEIL_LUECKE

    teile.append(f'<g transform="translate({_fmt(x)},0)">{_grid_lines_svg(m)}</g>')
    rand = 4
    teile.append(f'<rect x="{_fmt(x + rand)}" y="{rand}" width="{_fmt(m * UNIT - 2 * rand)}" '
                 f'height="{_fmt(m * UNIT - 2 * rand)}" fill="none" stroke="{LEER_FARBE}" '
                 f'stroke-width="3" stroke-dasharray="6,5"/>')
    x += m * UNIT

    inhalt = "".join(teile)
    return _svg_wrap_breit(x, m * UNIT, RAND_FIGUR, inhalt)


def erzeuge_analogie(rng, stufe, schwierigkeit):
    """Baut eine Analogie-Aufgabe A:B :: C:?. Schwierigkeit ≥3 beschränkt die
    Umwandlung auf drehen270/spiegeln (kognitiv aufwendiger nachzuvollziehen
    als eine Vierteldrehung nach rechts oder eine Punktspiegelung um 180°) –
    Denktiefe-Staffel statt Zahlenraum, wie überall in diesem Projekt."""
    m, groessen = _analogie_groessen(stufe)
    for _ in range(200):
        if schwierigkeit >= 3:
            transformation = rng.choice(("drehen270", "spiegeln"))
        else:
            transformation = rng.choice(TRANSFORMATIONEN)

        try:
            a = _zufallspolyomino(rng, m, rng.randint(*groessen))
            c_roh = _zufallspolyomino(rng, m, rng.randint(*groessen))
        except ValueError:
            continue

        b = _anwenden(transformation, a)
        if b == _normalisieren(a):
            continue  # T(A) == A: keine erkennbare Umwandlung
        c = _normalisieren(c_roh)
        if c == _normalisieren(a):
            continue  # C darf nicht zellengleich mit A sein

        richtige_antwort = _anwenden(transformation, c)
        if richtige_antwort == c:
            continue  # T(C) == C: keine eindeutige Antwort

        andere_transformationen = [t for t in TRANSFORMATIONEN if t != transformation]
        gewaehlt = rng.sample(andere_transformationen, 2)
        ablenker_c = [c] + [_anwenden(t, c) for t in gewaehlt]

        kandidaten = [richtige_antwort] + ablenker_c
        if len({frozenset(k) for k in kandidaten}) != 4:
            continue
        if not all(_zusammenhaengend(k) for k in kandidaten):
            continue

        reihenfolge = list(range(4))
        rng.shuffle(reihenfolge)
        optionen = [kandidaten[i] for i in reihenfolge]
        richtig = reihenfolge.index(0)

        farbe = rng.choice(PALETTE)
        return {
            "svg_frage": _render_analogie_frage(a, b, c, m, farbe),
            "optionen_svg": [_render_analogie_option(o, m, farbe) for o in optionen],
            "optionen_zellen": [_als_liste(o) for o in optionen],
            "richtig": richtig,
            "a": _als_liste(a),
            "b": _als_liste(b),
            "c": _als_liste(c),
            "transformation": transformation,
            "stufe": stufe,
        }
    raise ValueError("konnte nach 200 Versuchen keine eindeutige Analogie erzeugen")


def pruefe_analogie(aufgabe):
    """Rechnet T(C) unabhängig vom SVG über die Zellmengen nach – identisch
    im Aufbau zu pruefe_spiegelbild/pruefe_drehfigur in grafik_kern.py."""
    try:
        a = _als_zellmenge(aufgabe["a"])
        b = _als_zellmenge(aufgabe["b"])
        c = _als_zellmenge(aufgabe["c"])
        optionen = [_als_zellmenge(o) for o in aufgabe["optionen_zellen"]]
        richtig = aufgabe["richtig"]
        transformation = aufgabe["transformation"]
        stufe = aufgabe["stufe"]
    except (KeyError, TypeError, ValueError):
        return False, "Aufgabe hat kein gültiges Zellenformat"

    if transformation not in TRANSFORMATIONEN:
        return False, f"Transformation {transformation!r} ist ungültig"
    if stufe not in (6, 7):
        return False, f"Stufe {stufe!r} ist nicht 6 oder 7"
    if not (_zusammenhaengend(a) and _zusammenhaengend(b) and _zusammenhaengend(c)):
        return False, "A, B oder C ist nicht zusammenhängend"
    if len(optionen) != 4:
        return False, f"{len(optionen)} Optionen statt 4"
    if len({frozenset(o) for o in optionen}) != 4:
        return False, "die vier Optionen sind als Zellmengen nicht paarweise verschieden"
    if not all(_zusammenhaengend(o) for o in optionen):
        return False, "mindestens eine Option ist nicht zusammenhängend"
    if not isinstance(richtig, int) or not (0 <= richtig < 4):
        return False, f"'richtig'={richtig!r} ist kein gültiger Options-Index"

    erwartet_b = _anwenden(transformation, a)
    if frozenset(erwartet_b) != frozenset(_normalisieren(b)):
        return False, "B ist nicht die angegebene Transformation von A"
    if frozenset(erwartet_b) == frozenset(_normalisieren(a)):
        return False, "A ist unter der Transformation symmetrisch (T(A)=A) – keine erkennbare Umwandlung"
    if frozenset(_normalisieren(c)) == frozenset(_normalisieren(a)):
        return False, "C ist zellengleich mit A"

    erwartet = _anwenden(transformation, c)
    if erwartet == _normalisieren(c):
        return False, "C ist unter der Transformation symmetrisch (T(C)=C) – keine eindeutige Antwort"
    if frozenset(optionen[richtig]) != frozenset(erwartet):
        return False, "die als richtig markierte Option ist nicht T(C)"
    for i, o in enumerate(optionen):
        if i != richtig and frozenset(o) == frozenset(erwartet):
            return False, f"Ablenker {i} ist zellengleich mit der korrekten Umwandlung von C"

    return True, "Analogie ist eindeutig: genau eine Option ist die korrekte Umwandlung von C"
