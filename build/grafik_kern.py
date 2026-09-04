# -*- coding: utf-8 -*-
"""Der deterministische Grafikkern für Raum-&-Form-Aufgaben (ZIELE-V2.md, D2/D4).

Genau wie raetsel_kern.py bei Logikgittern und Zahlenfolgen kehrt dieses Modul
das Erzeugungsprinzip um: Ein Sprachmodell malt keine Bilder und zeichnet
keine geometrischen Wahrheiten – es bekäme isometrische Perspektive,
Verdeckung und Spiegelsymmetrie so zuverlässig hin wie unlösbare Logikrätsel,
nämlich gar nicht zuverlässig. Deshalb entsteht hier zuerst die Geometrie
(Zellmengen, Höhenlisten, Transformationen), ausschließlich mit Standard-
bibliotheks-Mitteln und vollständig seedbar; das SVG ist nur das Rendering
dieser bereits feststehenden Wahrheit. Ein LLM kommt an dieser Stelle des
Projekts noch gar nicht vor.

Drei Aufgabenfamilien, jede als erzeuge_<name>(rng, stufe) / pruefe_<name>(
aufgabe)-Paar:

  1. wuerfelgebaeude – Ein n×n-Säulenraster aus Einheitswürfeln wird isometrisch
     gerendert. "Nichts schwebt" gilt konstruktiv: Das Datenmodell kennt nur
     eine Höhe je Rasterfeld (eine massive Säule von der Grundfläche bis h),
     schwebende Blöcke sind also gar nicht erst darstellbar. Die einzige noch
     offene Fehlerquelle ist Verdeckung: Eine komplett verdeckte Säule ließe
     sich durch jede andere, ebenfalls verdeckt bleibende Höhe ersetzen, ohne
     das Bild zu verändern – das wäre eine zweite, andere Lösung mit anderer
     Blockzahl. erzeuge_wuerfelgebaeude() verwirft deshalb jedes Höhenraster,
     bei dem irgendeine Säule keinen einzigen sichtbaren Bildpunkt ihrer
     Deckfläche hat (siehe _alle_saeulen_sichtbar()).

  2. spiegelbild – Eine zusammenhängende Figur (Polyomino) wird an einer
     senkrechten Achse gespiegelt; vier Antwortbilder zeigen die korrekte
     Spiegelung und drei rechnerisch nachweisbar falsche Ablenker.

  3. drehfigur – dieselbe Art Figur wird um 90°/180°/270° gedreht; vier
     Antwortbilder zeigen die korrekte Drehung und drei Ablenker.

Für (2) und (3) gilt: Jede Eigenschaft, die die Aufgabe lösbar/eindeutig
macht (Nicht-Symmetrie der Ausgangsfigur, Verschiedenheit der vier Optionen,
Zusammenhang), wird über Zellmengen nachgerechnet – nie über SVG-Text. Damit
pruefe_* das ohne SVG-Parsing tun kann, führt die Rückgabe zusätzlich zu den
in der Aufgabenstellung genannten Feldern "optionen_zellen" mit (die
Zellmenge jeder der vier angezeigten Optionen) – die einzige Möglichkeit,
Korrektheit rechnerisch statt über SVG-Stringvergleiche zu prüfen.

Alle SVGs: quadratische viewBox, kein width/height am Wurzelelement (die App
skaliert selbst), kein Text, Flächenfarben ausschließlich aus PALETTE, Kontur
KONTUR, Rasterlinien RASTER. Dieselbe Farbe erscheint bei den Würfelgebäude-
Flächen in drei Helligkeiten – nicht durch neue Farbwerte (das würde die
Palette verlassen), sondern durch fill-opacity auf ein und demselben
Palettenwert, was auf dem dunklen App-Hintergrund optisch drei Helligkeiten
ergibt, ohne je einen Hex-Wert außerhalb der Palette zu erzeugen.
"""
import os
import random
import tempfile

PALETTE = ("#4cc9f0", "#f08b3e", "#59c37a", "#e9ecef")
KONTUR = "#0d1420"
RASTER = "#26334a"


def _fmt(x):
    """Formatiert eine Koordinate möglichst kompakt (ganzzahlig, wenn möglich)."""
    r = round(x, 2)
    if r == int(r):
        return str(int(r))
    return f"{r:g}"


def _poly(punkte, fill, opacity=1.0, stroke=KONTUR, stroke_width=1.5):
    pts = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in punkte)
    op = "" if opacity >= 1.0 else f' fill-opacity="{opacity}"'
    return f'<polygon points="{pts}" fill="{fill}"{op} stroke="{stroke}" stroke-width="{stroke_width}"/>'


def _svg_wrap(breite, hoehe, rand, inhalt, dx0=0, dy0=0):
    """Bettet 'inhalt' (dessen lokaler Ursprung bei (dx0,dy0) liegt) zentriert
    in eine QUADRATISCHE viewBox ein – Pflicht laut Vorgabe, unabhängig davon,
    ob der eigentliche Bildinhalt breiter oder höher ist als die andere Seite.
    """
    seite = max(breite, hoehe) + 2 * rand
    dx = (seite - breite) / 2 - dx0
    dy = (seite - hoehe) / 2 - dy0
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(seite)} {_fmt(seite)}">'
            f'<g transform="translate({_fmt(dx)},{_fmt(dy)})">{inhalt}</g></svg>')


# ============================================================ Zellmengen-Basis
# Gemeinsame Geometrie-Hilfsfunktionen für spiegelbild und drehfigur: Figuren
# sind Mengen von (Zeile, Spalte)-Tupeln auf einem ganzzahligen Gitter.

_NACHBARN = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _zusammenhaengend(zellen):
    """Prüft per Breitensuche, ob alle Zellen über Kantennachbarschaft
    verbunden sind. Eine leere Menge gilt als nicht zusammenhängend."""
    zellen = set(zellen)
    if not zellen:
        return False
    start = next(iter(zellen))
    besucht = {start}
    stapel = [start]
    while stapel:
        r, c = stapel.pop()
        for dr, dc in _NACHBARN:
            n2 = (r + dr, c + dc)
            if n2 in zellen and n2 not in besucht:
                besucht.add(n2)
                stapel.append(n2)
    return besucht == zellen


def _normalisieren(zellen):
    """Verschiebt eine Zellmenge so, dass ihre Bounding-Box bei (0,0) beginnt.
    Das macht Transformationen (spiegeln/drehen) und Vergleiche translations-
    unabhängig – zwei gleich geformte, nur verschobene Figuren gelten als
    identisch, weil sie in ihrem eigenen Options-Raster auch identisch
    gezeichnet würden."""
    zellen = list(zellen)
    minr = min(r for r, c in zellen)
    minc = min(c for r, c in zellen)
    return frozenset((r - minr, c - minc) for r, c in zellen)


def _spiegeln(zellen):
    """Spiegelt an der senkrechten Achse durch die Mitte der Bounding-Box."""
    zellen = _normalisieren(zellen)
    breite = max(c for r, c in zellen) + 1
    return frozenset((r, breite - 1 - c) for r, c in zellen)


def _drehen(zellen, winkel):
    """Dreht im Uhrzeigersinn um 90/180/270°, neu normalisiert."""
    zellen = _normalisieren(zellen)
    hoehe = max(r for r, c in zellen) + 1
    breite = max(c for r, c in zellen) + 1
    if winkel == 90:
        neu = [(c, hoehe - 1 - r) for r, c in zellen]
    elif winkel == 180:
        neu = [(hoehe - 1 - r, breite - 1 - c) for r, c in zellen]
    elif winkel == 270:
        neu = [(breite - 1 - c, r) for r, c in zellen]
    else:
        raise ValueError(f"unbekannter Winkel {winkel!r}, erlaubt sind 90/180/270")
    return _normalisieren(neu)


def _als_zellmenge(liste):
    """Wandelt eine JSON-taugliche Liste von [Zeile,Spalte]-Paaren in eine
    Menge von Tupeln – die Form, in der alle Geometrie-Funktionen rechnen."""
    return {(int(r), int(c)) for r, c in liste}


def _als_liste(zellen):
    return [[r, c] for r, c in sorted(zellen)]


def _zufallspolyomino(rng, m, groesse, versuche=200):
    """Würfelt eine zusammenhängende Figur aus 'groesse' Zellen im m×m-Gitter
    aus (Eden-Wachstum: von einer Startzelle aus wird wiederholt eine
    zufällige Randzelle angefügt). Ein Fehlschlag (Sackgasse am Rand) führt
    zu einem neuen Versuch, nicht zum Absturz."""
    for _ in range(versuche):
        start = (rng.randrange(m), rng.randrange(m))
        zellen = {start}
        rand = set()
        for dr, dc in _NACHBARN:
            n2 = (start[0] + dr, start[1] + dc)
            if 0 <= n2[0] < m and 0 <= n2[1] < m:
                rand.add(n2)
        ok = True
        while len(zellen) < groesse:
            if not rand:
                ok = False
                break
            kandidaten = sorted(rand)
            kandidat = kandidaten[rng.randrange(len(kandidaten))]
            rand.discard(kandidat)
            zellen.add(kandidat)
            for dr, dc in _NACHBARN:
                n2 = (kandidat[0] + dr, kandidat[1] + dc)
                if 0 <= n2[0] < m and 0 <= n2[1] < m and n2 not in zellen:
                    rand.add(n2)
        if ok and len(zellen) == groesse:
            return _normalisieren(zellen)
    raise ValueError(f"konnte kein {groesse}-Zellen-Polyomino im {m}x{m}-Gitter erzeugen")


def _einzelne_zelle_versetzen(rng, zellen, m, versuche=100):
    """Baut aus 'zellen' den 'genau ein Zellfehler'-Ablenker: eine Zelle wird
    entfernt (Rest muss zusammenhängend bleiben) und durch eine andere,
    an den Rest angrenzende Zelle ersetzt. Liefert None, wenn das innerhalb
    der Versuche nicht gelingt (z. B. weil die Figur zu kompakt ist)."""
    zellen = set(zellen)
    liste = sorted(zellen)
    ausgangsform = _normalisieren(zellen)
    for _ in range(versuche):
        weg = liste[rng.randrange(len(liste))]
        rest = zellen - {weg}
        if not _zusammenhaengend(rest):
            continue
        rand_kandidaten = set()
        for r, c in rest:
            for dr, dc in _NACHBARN:
                n2 = (r + dr, c + dc)
                if n2 not in rest and n2 != weg:
                    rand_kandidaten.add(n2)
        if not rand_kandidaten:
            continue
        rand_liste = sorted(rand_kandidaten)
        neu = rand_liste[rng.randrange(len(rand_liste))]
        ergebnis = rest | {neu}
        normiert = _normalisieren(ergebnis)
        breite = max(c for r, c in normiert) + 1
        hoehe = max(r for r, c in normiert) + 1
        if breite <= m and hoehe <= m and normiert != ausgangsform:
            return normiert
    return None


def _spiegel_drehfigur_groessen(stufe):
    """Rastergröße m und Figurgröße-Bereich je Stufe – wächst mit der Stufe,
    wie von der Rechenlast-/Schwierigkeitslogik aus ZIELE-V2.md/D2 gefordert."""
    if stufe <= 3:
        return 4, (4, 6)
    if stufe <= 5:
        return 5, (5, 7)
    return 6, (6, 9)


# ==================================================== Rendering: Rasterfiguren

UNIT = 40
RAND_FIGUR = UNIT // 2


def _grid_lines_svg(m, unit=UNIT):
    teile = []
    for i in range(m + 1):
        teile.append(f'<line x1="0" y1="{i * unit}" x2="{m * unit}" y2="{i * unit}" '
                      f'stroke="{RASTER}" stroke-width="1"/>')
        teile.append(f'<line x1="{i * unit}" y1="0" x2="{i * unit}" y2="{m * unit}" '
                      f'stroke="{RASTER}" stroke-width="1"/>')
    return "".join(teile)


def _zellen_svg(zellen, farbe, unit=UNIT):
    teile = []
    for r, c in sorted(zellen):
        teile.append(f'<rect x="{c * unit}" y="{r * unit}" width="{unit}" height="{unit}" '
                      f'fill="{farbe}" stroke="{KONTUR}" stroke-width="2"/>')
    return "".join(teile)


def _render_grid_figur(zellen, m, farbe):
    inhalt = _grid_lines_svg(m) + _zellen_svg(zellen, farbe)
    return _svg_wrap(m * UNIT, m * UNIT, RAND_FIGUR, inhalt)


def _render_spiegel_frage(zellen, m, farbe):
    """Links die Figur, rechts ein leeres Spiegel-Raster gleicher Größe,
    dazwischen eine deutlich gezeichnete gestrichelte Achse in Palettenfarbe
    e9ecef. Die vier Antwortbilder zeigen jeweils nur die rechte Seite –
    dieses Bild hier zeigt sie bewusst leer, damit nichts vorwegnimmt."""
    links = _grid_lines_svg(m) + _zellen_svg(zellen, farbe)
    rechts = f'<g transform="translate({m * UNIT},0)">{_grid_lines_svg(m)}</g>'
    achse = (f'<line x1="{m * UNIT}" y1="0" x2="{m * UNIT}" y2="{m * UNIT}" '
             f'stroke="#e9ecef" stroke-width="4" stroke-dasharray="6,5"/>')
    inhalt = links + rechts + achse
    return _svg_wrap(2 * m * UNIT, m * UNIT, RAND_FIGUR, inhalt)


# ============================================================== spiegelbild

def erzeuge_spiegelbild(rng, stufe):
    """Erzeugt ein Spiegel-Rätsel: Figur links, Achse in der Mitte, vier
    rechte Optionen zur Auswahl.

    Ablenker-Bau (drei Stück, alle rechnerisch als Zellmengen von der
    korrekten Spiegelung UND voneinander verschieden – siehe Prüfschleife
    unten):
      1. unspiegelte Kopie der Originalfigur (Standardfehler: gar nicht
         gespiegelt);
      2. 180°-Drehung der Originalfigur (Verwechslung Spiegelung↔Drehung);
      3. die korrekte Spiegelung mit genau einer versetzten Zelle (Fehler im
         Detail statt im Prinzip).

    Eindeutigkeitsprüfung: Eine Figur, die bereits selbst spiegelsymmetrisch
    zur Achse ist, wird verworfen – sonst wäre Ablenker 1 (die unspiegelte
    Kopie) zellenidentisch mit der korrekten Antwort, also eine zweite
    richtige Lösung. Danach werden alle vier Kandidaten paarweise als
    Zellmengen verglichen; jede Kollision (z. B. weil die Figur zufällig auch
    180°-drehsymmetrisch ist) führt zu einem neuen Versuch mit einer neuen
    Figur, nicht zu einer stillschweigend fehlerhaften Aufgabe.
    """
    m, groessen = _spiegel_drehfigur_groessen(stufe)
    for _ in range(200):
        try:
            zellen = _zufallspolyomino(rng, m, rng.randint(*groessen))
        except ValueError:
            continue
        gespiegelt = _spiegeln(zellen)
        if gespiegelt == zellen:
            continue
        kopie = zellen
        drehung180 = _drehen(zellen, 180)
        versetzt = _einzelne_zelle_versetzen(rng, gespiegelt, m)
        if versetzt is None:
            continue
        kandidaten = [gespiegelt, kopie, drehung180, versetzt]
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
            "svg_frage": _render_spiegel_frage(zellen, m, farbe),
            "optionen_svg": [_render_grid_figur(o, m, farbe) for o in optionen],
            "optionen_zellen": [_als_liste(o) for o in optionen],
            "richtig": richtig,
            "zellen": _als_liste(zellen),
            "stufe": stufe,
        }
    raise ValueError("konnte nach 200 Versuchen kein eindeutiges Spiegelbild-Rätsel erzeugen")


def pruefe_spiegelbild(aufgabe):
    """Rechnet alle Eindeutigkeits- und Korrektheitseigenschaften direkt über
    die Zellmengen nach – ohne die SVG-Felder überhaupt anzusehen."""
    try:
        zellen = _als_zellmenge(aufgabe["zellen"])
        optionen = [_als_zellmenge(o) for o in aufgabe["optionen_zellen"]]
        richtig = aufgabe["richtig"]
    except (KeyError, TypeError, ValueError):
        return False, "Aufgabe hat kein gültiges Zellenformat"

    if not (4 <= len(zellen) <= 9):
        return False, f"Figur hat {len(zellen)} Zellen, gefordert sind 4..9"
    if not _zusammenhaengend(zellen):
        return False, "Ausgangsfigur ist nicht zusammenhängend"
    if _spiegeln(zellen) == _normalisieren(zellen):
        return False, "Figur ist spiegelsymmetrisch – die unspiegelte Kopie wäre eine zweite Lösung"
    if len(optionen) != 4:
        return False, f"{len(optionen)} Optionen statt 4"
    if len({frozenset(o) for o in optionen}) != 4:
        return False, "die vier Optionen sind als Zellmengen nicht paarweise verschieden"
    if not all(_zusammenhaengend(o) for o in optionen):
        return False, "mindestens eine Option ist nicht zusammenhängend"
    if not isinstance(richtig, int) or not (0 <= richtig < 4):
        return False, f"'richtig'={richtig!r} ist kein gültiger Options-Index"

    erwartet = _spiegeln(zellen)
    if frozenset(optionen[richtig]) != frozenset(erwartet):
        return False, "die als richtig markierte Option ist nicht die korrekte Spiegelung"
    for i, o in enumerate(optionen):
        if i != richtig and frozenset(o) == frozenset(erwartet):
            return False, f"Ablenker {i} ist zellengleich mit der korrekten Spiegelung"
    return True, "Spiegelbild-Rätsel ist eindeutig: genau eine Option ist die korrekte Spiegelung"


# =============================================================== drehfigur

def erzeuge_drehfigur(rng, stufe):
    """Erzeugt ein Dreh-Rätsel: die Originalfigur soll gedanklich um winkel
    (90/180/270°) gedreht werden; vier Optionen stehen zur Auswahl.

    Ablenker-Bau:
      1. die Originalfigur gespiegelt statt gedreht (Verwechslung der beiden
         Transformationsarten);
      2. dieselbe Figur um einen ANDEREN der drei Winkel gedreht (Verwechslung
         des Drehwinkels);
      3. die korrekte Drehung mit genau einer versetzten Zelle.

    Eindeutigkeitsprüfung: Eine Figur, die unter dem gewürfelten Winkel auf
    sich selbst abbildet (drehsymmetrisch), wird verworfen – sonst wäre die
    Originalfigur selbst zugleich eine zweite richtige Antwort. Ebenso wird
    verworfen, wenn die gespiegelte Originalfigur zellengleich mit der
    korrekten Drehung ist – sonst wäre Ablenker 1 in Wahrheit auch richtig.
    Alle vier Endkandidaten werden zusätzlich paarweise als Zellmengen
    verglichen; jede Kollision löst einen neuen Versuch mit neuer Figur aus.
    """
    m, groessen = _spiegel_drehfigur_groessen(stufe)
    for _ in range(200):
        try:
            zellen = _zufallspolyomino(rng, m, rng.randint(*groessen))
        except ValueError:
            continue
        winkel = rng.choice((90, 180, 270))
        gedreht = _drehen(zellen, winkel)
        if gedreht == zellen:
            continue
        gespiegelt = _spiegeln(zellen)
        if gespiegelt == gedreht:
            continue
        anderer_winkel = rng.choice([w for w in (90, 180, 270) if w != winkel])
        andere_drehung = _drehen(zellen, anderer_winkel)
        fehlerhaft = _einzelne_zelle_versetzen(rng, gedreht, m)
        if fehlerhaft is None:
            continue
        kandidaten = [gedreht, gespiegelt, andere_drehung, fehlerhaft]
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
            "svg_frage": _render_grid_figur(zellen, m, farbe),
            "optionen_svg": [_render_grid_figur(o, m, farbe) for o in optionen],
            "optionen_zellen": [_als_liste(o) for o in optionen],
            "richtig": richtig,
            "winkel": winkel,
            "zellen": _als_liste(zellen),
            "stufe": stufe,
        }
    raise ValueError("konnte nach 200 Versuchen kein eindeutiges Drehfigur-Rätsel erzeugen")


def pruefe_drehfigur(aufgabe):
    """Rechnet Eindeutigkeit und Korrektheit über die Zellmengen nach."""
    try:
        zellen = _als_zellmenge(aufgabe["zellen"])
        optionen = [_als_zellmenge(o) for o in aufgabe["optionen_zellen"]]
        richtig = aufgabe["richtig"]
        winkel = aufgabe["winkel"]
    except (KeyError, TypeError, ValueError):
        return False, "Aufgabe hat kein gültiges Format"

    if winkel not in (90, 180, 270):
        return False, f"Winkel {winkel!r} ist nicht 90/180/270"
    if not (4 <= len(zellen) <= 9):
        return False, f"Figur hat {len(zellen)} Zellen, gefordert sind 4..9"
    if not _zusammenhaengend(zellen):
        return False, "Ausgangsfigur ist nicht zusammenhängend"

    erwartet = _drehen(zellen, winkel)
    if erwartet == _normalisieren(zellen):
        return False, "Figur ist unter diesem Winkel drehsymmetrisch – keine eindeutige Antwort"
    if erwartet == _spiegeln(zellen):
        return False, "gedrehte und gespiegelte Figur sind zellengleich – Spiegel-Ablenker wäre auch richtig"
    if len(optionen) != 4:
        return False, f"{len(optionen)} Optionen statt 4"
    if len({frozenset(o) for o in optionen}) != 4:
        return False, "die vier Optionen sind als Zellmengen nicht paarweise verschieden"
    if not all(_zusammenhaengend(o) for o in optionen):
        return False, "mindestens eine Option ist nicht zusammenhängend"
    if not isinstance(richtig, int) or not (0 <= richtig < 4):
        return False, f"'richtig'={richtig!r} ist kein gültiger Options-Index"

    if frozenset(optionen[richtig]) != frozenset(erwartet):
        return False, "die als richtig markierte Option ist nicht die korrekte Drehung"
    for i, o in enumerate(optionen):
        if i != richtig and frozenset(o) == frozenset(erwartet):
            return False, f"Ablenker {i} ist zellengleich mit der korrekten Drehung"
    return True, "Drehfigur-Rätsel ist eindeutig: genau eine Option ist die korrekte Drehung"


# =========================================================== wuerfelgebaeude
# Isometrische 2:1-Rautenprojektion, Blickrichtung frontal-oben-rechts:
# Bildkoordinate X hängt nur von (Spalte-Zeile) ab, Y nur von (Zeile+Spalte)
# und der Höhe. Zellen mit größerem (Zeile+Spalte) liegen näher an der
# Kamera und werden zuletzt gezeichnet (Malerprinzip) – Standardverfahren
# für isometrische Kachelraster.

ISO_TW = 60   # Kachelbreite (Rautenbreite am Boden)
ISO_TH = 30   # Kachelhöhe (Rautenhöhe am Boden), klassisches 2:1-Verhältnis
ISO_CH = 34   # sichtbarer Höhenzuwachs je gestapeltem Würfel


def _hexagon_punkte(r, c, h, tw=ISO_TW, th=ISO_TH, ch=ISO_CH):
    """Die 6 Eckpunkte der vollen Silhouette einer Säule der Höhe h an
    Rasterposition (r,c): Dachraute oben + linke/rechte Seitenfläche.
    Für h=0 entarten die oberen und unteren Punktepaare zur reinen
    Bodenraute (4 statt 6 verschiedene Punkte) – dieselbe Formel deckt also
    sowohl echte Säulen als auch leere Felder ab."""
    X = (c - r) * (tw / 2)
    Y = (r + c) * (th / 2)
    top = Y - h * ch
    return [
        (X, top - th / 2), (X + tw / 2, top), (X + tw / 2, Y),
        (X, Y + th / 2), (X - tw / 2, Y), (X - tw / 2, top),
    ]


def _top_flaeche_punkte(r, c, h, tw=ISO_TW, th=ISO_TH, ch=ISO_CH):
    """Die Dachraute (bzw. bei h=0 die Bodenraute) allein – das ist die
    Fläche, an deren Sichtbarkeit sich die Höhe des Feldes eindeutig
    ablesen lässt."""
    X = (c - r) * (tw / 2)
    Y = (r + c) * (th / 2)
    top = Y - h * ch
    return [(X, top - th / 2), (X + tw / 2, top), (X, top + th / 2), (X - tw / 2, top)]


def _punkt_in_polygon(px, py, poly):
    """Punkt-in-Polygon-Test per Strahlverfahren (funktioniert für beliebige
    einfache Polygone, hier immer konvexe Vierecke/Sechsecke)."""
    innen = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            x_schnitt = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < x_schnitt:
                innen = not innen
    return innen


def _abtastpunkte(poly):
    """Ein paar sichere Innenpunkte eines konvexen Polygons: der Schwerpunkt
    plus die Mittelpunkte zwischen Schwerpunkt und jeder Ecke. Reicht, um
    'komplett verdeckt' von 'irgendwo noch sichtbar' zu unterscheiden."""
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    punkte = [(cx, cy)]
    for x, y in poly:
        punkte.append(((x + cx) / 2, (y + cy) / 2))
    return punkte


def _saeule_sichtbar(r, c, hoehen, n):
    """True, wenn mindestens ein Abtastpunkt der Dach-/Bodenfläche von (r,c)
    von KEINER näher an der Kamera stehenden Säule (größeres Zeile+Spalte-
    Malerprinzip-Kriterium) überdeckt wird.

    Warum das reicht: Zwei Felder mit gleichem (Zeile+Spalte) überlappen sich
    auf dem Bildschirm nie (ihre Rauten sind exakt eine Kachelbreite
    auseinander), Verdeckung kann also nur von Feldern mit STRIKT größerem
    Zeile+Spalte kommen – genau die, die im Malerprinzip später gezeichnet
    werden. Ist ein Abtastpunkt frei, lässt sich an seiner Bildposition die
    tatsächliche Höhe von (r,c) ablesen (die Dachraute liegt bei einer
    anderen Höhe an einer anderen Bildstelle); ist keiner frei, könnte an
    dieser Stelle ebenso gut eine andere Höhe stehen, ohne dass sich am Bild
    etwas ändert – genau die Mehrdeutigkeit, die verboten ist.
    """
    h = hoehen[r][c]
    schwelle = r + c
    for sx, sy in _abtastpunkte(_top_flaeche_punkte(r, c, h)):
        verdeckt = False
        for rr in range(n):
            for cc in range(n):
                if rr + cc <= schwelle:
                    continue
                if _punkt_in_polygon(sx, sy, _hexagon_punkte(rr, cc, hoehen[rr][cc])):
                    verdeckt = True
                    break
            if verdeckt:
                break
        if not verdeckt:
            return True
    return False


def _alle_saeulen_sichtbar(hoehen, n):
    return all(_saeule_sichtbar(r, c, hoehen, n) for r in range(n) for c in range(n))


def _wuerfelgebaeude_groesse(stufe):
    if stufe <= 3:
        return 2
    if stufe <= 5:
        return 3
    return 4


def _boden_svg(r, c):
    X = (c - r) * (ISO_TW / 2)
    Y = (r + c) * (ISO_TH / 2)
    pts = [(X, Y - ISO_TH / 2), (X + ISO_TW / 2, Y), (X, Y + ISO_TH / 2), (X - ISO_TW / 2, Y)]
    p = " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in pts)
    return f'<polygon points="{p}" fill="none" stroke="{RASTER}" stroke-width="1"/>'


def _saeule_svg(r, c, h, farbe):
    X = (c - r) * (ISO_TW / 2)
    Y = (r + c) * (ISO_TH / 2)
    top = Y - h * ISO_CH
    tr_top = (X, top - ISO_TH / 2)
    tr_re = (X + ISO_TW / 2, top)
    tr_vo = (X, top + ISO_TH / 2)
    tr_li = (X - ISO_TW / 2, top)
    gr_re = (X + ISO_TW / 2, Y)
    gr_vo = (X, Y + ISO_TH / 2)
    gr_li = (X - ISO_TW / 2, Y)
    dach = [tr_top, tr_re, tr_vo, tr_li]
    rechts = [tr_re, tr_vo, gr_vo, gr_re]
    links = [tr_li, tr_vo, gr_vo, gr_li]
    return (_poly(links, farbe, 0.52) + _poly(rechts, farbe, 0.78) + _poly(dach, farbe, 1.0))


def _render_wuerfelgebaeude_svg(hoehen, n, farbe):
    ordnung = sorted(((r, c) for r in range(n) for c in range(n)), key=lambda rc: (rc[0] + rc[1], rc[0]))
    boden = [_boden_svg(r, c) for r in range(n) for c in range(n)]
    saeulen = [_saeule_svg(r, c, hoehen[r][c], farbe) for r, c in ordnung if hoehen[r][c] > 0]
    alle_punkte = [p for r, c in ordnung for p in _hexagon_punkte(r, c, hoehen[r][c])]
    xs = [p[0] for p in alle_punkte]
    ys = [p[1] for p in alle_punkte]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    inhalt = "".join(boden) + "".join(saeulen)
    return _svg_wrap(maxx - minx, maxy - miny, 20, inhalt, dx0=minx, dy0=miny)


def _baue_sichtbares_hoehenraster(rng, n):
    """Würfelt ein n×n-Höhenraster, das KONSTRUKTIV vollständig sichtbar ist,
    statt zufällige Raster zu würfeln und die (empirisch sehr seltenen,
    schon bei n=4 nur ~0,2 % der Fälle) vollständig sichtbaren wieder
    herauszufiltern – reines Verwerfen-und-neu-Würfeln würde den 200er-
    Deckel regelmäßig reißen.

    Stattdessen wird zeilen-/spaltenweise in Kamera-Reihenfolge gebaut (erst
    die am weitesten entfernten Felder, zuletzt die kameranächsten – dieselbe
    Reihenfolge wie beim Malerprinzip): Für jedes Feld wird eine zufällige
    Höhe 0..4 gewürfelt und dann genau so weit heruntergesetzt, bis keines
    der bereits platzierten (weiter hinten liegenden) Felder dadurch verdeckt
    wird. Das terminiert immer, weil Höhe 0 nachweislich nie etwas verdeckt
    (eine leere Bodenraute liegt vollständig unterhalb der Dachraute jedes
    weiter hinten liegenden Feldes – vgl. _saeule_sichtbar()). Am Ende hat
    jedes Feld entweder seine ursprünglich gewürfelte Höhe oder eine kleinere,
    genau ausreichend reduzierte – und jedes bereits platzierte Feld bleibt ab
    dem Moment seiner Platzierung für den Rest des Aufbaus sichtbar, weil
    spätere (nähere) Felder nur noch verkleinert, nie vergrößert werden.
    """
    hoehen = [[0] * n for _ in range(n)]
    reihenfolge = sorted(((r, c) for r in range(n) for c in range(n)),
                          key=lambda rc: (rc[0] + rc[1], rc[0]))
    for i, (r, c) in enumerate(reihenfolge):
        h = rng.randint(0, 4)
        hoehen[r][c] = h
        while h > 0 and any(not _saeule_sichtbar(rr, cc, hoehen, n) for rr, cc in reihenfolge[:i]):
            h -= 1
            hoehen[r][c] = h
    return hoehen


def erzeuge_wuerfelgebaeude(rng, stufe):
    """Baut ein n×n-Höhenraster (n je nach stufe: 2, 3 oder 4, Höhen 0..4)
    über _baue_sichtbares_hoehenraster() – das Ergebnis ist bereits
    konstruktiv vollständig sichtbar, ein Verwerfen ist dafür nicht mehr
    nötig. Nur die geforderte Mindestblockzahl (≥3) wird per Neuversuch
    sichergestellt, falls der Zufall ausnahmsweise ein zu leeres Raster
    liefert. "Nichts schwebt" muss nicht separat geprüft werden: Das
    Höhenraster IST das Datenmodell – es kennt pro Feld nur eine einzige
    Zahl (die Stapelhöhe von der Grundfläche an), ein schwebender Block wäre
    in dieser Repräsentation gar nicht ausdrückbar.
    """
    n = _wuerfelgebaeude_groesse(stufe)
    for _ in range(200):
        hoehen = _baue_sichtbares_hoehenraster(rng, n)
        gesamt = sum(sum(zeile) for zeile in hoehen)
        if gesamt < 3:
            continue
        farbe = rng.choice(PALETTE)
        return {
            "svg": _render_wuerfelgebaeude_svg(hoehen, n, farbe),
            "anzahl": gesamt,
            "hoehen": hoehen,
            "stufe": stufe,
        }
    raise ValueError(f"konnte nach 200 Versuchen kein {n}x{n}-Würfelgebäude mit ≥3 Blöcken erzeugen")


def pruefe_wuerfelgebaeude(aufgabe):
    """Prüft rechnerisch über die Höhenliste: gültige Werte, Mindestblockzahl,
    Übereinstimmung mit 'anzahl' und – als Kern der harten Anforderung –
    dass keine Säule vollständig verdeckt ist."""
    hoehen = aufgabe.get("hoehen")
    if not isinstance(hoehen, list) or not hoehen:
        return False, "keine Höhenliste vorhanden"
    n = len(hoehen)
    if any(not isinstance(zeile, list) or len(zeile) != n for zeile in hoehen):
        return False, "Höhenliste ist nicht quadratisch"
    for zeile in hoehen:
        for h in zeile:
            if not isinstance(h, int) or not (0 <= h <= 4):
                return False, f"Höhe {h!r} liegt außerhalb von 0..4"
    gesamt = sum(sum(zeile) for zeile in hoehen)
    if gesamt < 3:
        return False, f"nur {gesamt} Blöcke, mindestens 3 gefordert"
    if gesamt != aufgabe.get("anzahl"):
        return False, f"angegebene Anzahl {aufgabe.get('anzahl')!r} stimmt nicht mit den Höhen überein ({gesamt})"
    if not _alle_saeulen_sichtbar(hoehen, n):
        return False, "mindestens eine Säule ist vollständig verdeckt – Blockzahl wäre nicht eindeutig ablesbar"
    return True, "Würfelgebäude ist konstruktiv schwebefrei und jede Säule ist eindeutig ablesbar"


# ==================================================================== Demo

def _demo_seite(titel, block_html):
    # svg füllt immer genau seinen Kachel-Container (width:100%): die viewBox
    # jedes erzeugten SVGs ist ohnehin quadratisch, daher verzerrt das nie.
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{titel}</title>'
            f'<style>body{{background:#0d1420;color:#e9ecef;font-family:sans-serif;padding:20px}}'
            f'.reihe{{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}}'
            f'.kachel{{width:180px;text-align:center}}'
            f'.kachel svg{{width:100%;height:auto;display:block;background:#111a2b;'
            f'border:1px solid #26334a;border-radius:8px}}'
            f'.marke{{margin-top:4px;font-size:13px}}'
            f'h1{{font-size:18px}} .kachel.gross{{width:340px}}</style></head><body>'
            f'<h1>{titel}</h1>{block_html}</body></html>')


def _demo_kachel(svg, marke):
    return f'<div class="kachel">{svg}<div class="marke">{marke}</div></div>'


def main():
    # Ablageort der Anschauungsdateien: MC_DEMO_DIR schlaegt alles, sonst ein
    # Unterordner im Temp-Verzeichnis dieses Rechners.
    demo_dir = os.environ.get("MC_DEMO_DIR") or os.path.join(
        tempfile.gettempdir(), "mathcraft_demo", "grafik")
    os.makedirs(demo_dir, exist_ok=True)

    print("=== grafik_kern.py – Selbsttest/Demo ===\n")

    rng = random.Random(42)
    wg = erzeuge_wuerfelgebaeude(rng, stufe=6)
    ok, grund = pruefe_wuerfelgebaeude(wg)
    print(f"wuerfelgebaeude: anzahl={wg['anzahl']} stufe={wg['stufe']} "
          f"svg_len={len(wg['svg'])} pruefe_*={ok} ({grund})")
    html = _demo_seite("wuerfelgebaeude – Demo",
                        f'<div class="reihe"><div class="kachel gross">{wg["svg"]}'
                        f'<div class="marke">anzahl={wg["anzahl"]}, stufe={wg["stufe"]}</div></div></div>')
    with open(os.path.join(demo_dir, "wuerfelgebaeude.html"), "w", encoding="utf-8") as f:
        f.write(html)

    rng = random.Random(42)
    sb = erzeuge_spiegelbild(rng, stufe=4)
    ok, grund = pruefe_spiegelbild(sb)
    print(f"spiegelbild:     zellen={len(sb['zellen'])} stufe={sb['stufe']} richtig={sb['richtig']} "
          f"svg_len={len(sb['svg_frage'])} pruefe_*={ok} ({grund})")
    kacheln = "".join(
        _demo_kachel(svg, "richtig" if i == sb["richtig"] else f"Option {i}")
        for i, svg in enumerate(sb["optionen_svg"])
    )
    html = _demo_seite("spiegelbild – Demo",
                        f'<div class="reihe"><div class="kachel gross">{sb["svg_frage"]}'
                        f'<div class="marke">Frage</div></div></div><h1>Optionen</h1>'
                        f'<div class="reihe">{kacheln}</div>')
    with open(os.path.join(demo_dir, "spiegelbild.html"), "w", encoding="utf-8") as f:
        f.write(html)

    rng = random.Random(42)
    df = erzeuge_drehfigur(rng, stufe=4)
    ok, grund = pruefe_drehfigur(df)
    print(f"drehfigur:       zellen={len(df['zellen'])} stufe={df['stufe']} winkel={df['winkel']} "
          f"richtig={df['richtig']} svg_len={len(df['svg_frage'])} pruefe_*={ok} ({grund})")
    kacheln = "".join(
        _demo_kachel(svg, "richtig" if i == df["richtig"] else f"Option {i}")
        for i, svg in enumerate(df["optionen_svg"])
    )
    html = _demo_seite("drehfigur – Demo",
                        f'<div class="reihe"><div class="kachel gross">{df["svg_frage"]}'
                        f'<div class="marke">Frage (Winkel {df["winkel"]}°)</div></div></div>'
                        f'<h1>Optionen</h1><div class="reihe">{kacheln}</div>')
    with open(os.path.join(demo_dir, "drehfigur.html"), "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nAnschauungsdateien geschrieben nach {demo_dir}/")


if __name__ == "__main__":
    main()
