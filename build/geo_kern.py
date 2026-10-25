# -*- coding: utf-8 -*-
"""Der deterministische Geometrie-Kern (ZIELE-V3.md, G3; Leitplanken ZIELE-V2.md, D2/D4).

Fünf Geometrie-Fertigkeiten für Raum & Form, Klasse 3-5 – wie grafik_kern.py
kehrt dieses Modul das Erzeugungsprinzip um: Zuerst entsteht die Wahrheit
(Höhenkarte, Würfelnetz, Kästchenfigur, Quader, Schatzkarte) als Zahlen und
Zellmengen, das SVG ist nur ihr Rendering. Jede Art hat einen Prüfer
pruefe_<art>(kern) -> (ok, grund), der die Wahrheit aus den Rohdaten des Kerns
NEU berechnet und das SVG nie ansieht. Kein Sprachmodell, kein hash, kein
eval; Zufall nur über random.Random(seed) mit Seeds aus zlib.crc32 von Text,
damit gleiche Eingabe immer die gleiche Aufgabe ergibt.

  1. ansicht     – Würfelgebäude von oben / von der linken / von der rechten Wand
                   (Rasteransichten als Antwortbilder). Jede Säule ist im Bild
                   sichtbar; die richtige Ansicht wird aus der Höhenkarte
                   nachgerechnet, genau eine Option passt.
  2. netzfalten  – Würfelnetze aus sechs Quadraten. Die Faltung wird wirklich
                   simuliert (Würfel rollt über das Netz): von den 35 freien
                   Hexominos falten genau 11. Modi: „wuerfel“ (welches Netz
                   faltet?) und „gegenueber“ (welches Zeichen liegt gegenüber?).
  3. gitterfigur – Fläche und Umfang von Kästchenfiguren (auch Treppen und
                   halbe Kästchen) sowie Rechteck-Rätsel zum Durchprobieren.
  4. quader      – Wie viele Würfel fehlen bis zum vollen Quader? Würfel stehen
                   nach Schwerkraft in Säulen, jede Säule ist sichtbar.
  5. karte       – Schatzkarte: Schritte abzählen, kürzester Weg (Breitensuche),
                   Maßstab.

Schwierigkeit ist Denktiefe, nie Zahlengröße: Die Stufe wählt größere Raster,
untypischere Netze, Umwege um Felsen – die Zahlen bleiben klein (D2). Die
Stufenhülle (z. B. „Stufe 3-4: nur oben“) gilt strikt; der Index 0..5 steigert
die Denktiefe INNERHALB dieser Hülle (größeres Raster, schwerere Ablenker).

Alle SVGs: quadratische viewBox, kein width/height, kein Text, Farben nur aus
der Palette von grafik_kern.py.
"""
import random
import zlib

import grafik_kern as GK

PALETTE = GK.PALETTE
KONTUR = GK.KONTUR
RASTER = GK.RASTER
HELL = "#e9ecef"          # Palettenfarbe für Linien, Sterne, Beschriftungsersatz

SKILLS = ("geo_ansicht", "geo_netzfalten", "geo_flaeche_umfang", "geo_quader", "geo_karte")


class _Neu(Exception):
    """Interner Abbruch: dieser Versuch taugt nichts, mit neuem Seed weiter."""


# ================================================================= Grundlagen

def _rng(skill, stage, index, seed, versuch):
    """Eigener Zufallsstrom je (Fertigkeit, Stufe, Index, Seed, Versuch) –
    Seed aus crc32 von Text, nie aus dem eingebauten Hash (der ist je Prozess anders)."""
    text = f"geo|{skill}|{stage}|{index}|{seed}|{versuch}"
    return random.Random(zlib.crc32(text.encode("utf-8")))


def _wiederhole(erzeuger, skill, stage, index, seed, versuche=500):
    """Ruft den Erzeuger mit immer neuen Zufallsströmen, bis er nicht mehr
    _Neu auslöst. Das Ergebnis hängt nur von den Eingaben ab."""
    for versuch in range(versuche):
        try:
            return erzeuger(_rng(skill, stage, index, seed, versuch), stage, index)
        except _Neu:
            continue
    raise ValueError(f"{skill}: nach {versuche} Versuchen keine Aufgabe "
                     f"(Stufe {stage}, Index {index}, Seed {seed})")


def _vorlage(liste, index):
    """Fragetext aus fester Schablone, Rotation über den Paket-Index."""
    return liste[index % len(liste)]


def _ist_int(x):
    return type(x) is int


def _mische(rng, richtig_inhalt, ablenker):
    """Setzt die richtige Option und die Ablenker in zufällige Reihenfolge;
    Rückgabe: (optionen, index_der_richtigen)."""
    alle = [richtig_inhalt] + list(ablenker)
    folge = list(range(len(alle)))
    rng.shuffle(folge)
    return [alle[i] for i in folge], folge.index(0)


# ------------------------------------------------------- Rechteck-Höhenkarten
# grafik_kern rechnet die Sichtbarkeit nur für quadratische Raster. Ansicht
# und Quader brauchen Rechtecke (Zeilen x Spalten); die Geometrie bleibt
# dieselbe, nur die Schleifengrenzen sind nicht mehr n x n.

def _saeule_sichtbar(r, c, hoehen):
    """True, wenn mindestens ein Abtastpunkt der Dach-/Bodenfläche von (r,c)
    von keiner näher an der Kamera stehenden Säule überdeckt wird (Begründung
    siehe grafik_kern._saeule_sichtbar: nur Felder mit größerem Zeile+Spalte
    können verdecken)."""
    zeilen, spalten = len(hoehen), len(hoehen[0])
    schwelle = r + c
    for sx, sy in GK._abtastpunkte(GK._top_flaeche_punkte(r, c, hoehen[r][c])):
        verdeckt = False
        for rr in range(zeilen):
            for cc in range(spalten):
                if rr + cc > schwelle and GK._punkt_in_polygon(
                        sx, sy, GK._hexagon_punkte(rr, cc, hoehen[rr][cc])):
                    verdeckt = True
                    break
            if verdeckt:
                break
        if not verdeckt:
            return True
    return False


def _alle_saeulen_sichtbar(hoehen):
    return all(_saeule_sichtbar(r, c, hoehen)
               for r in range(len(hoehen)) for c in range(len(hoehen[0])))


def _baue_sichtbar(rng, zeilen, spalten, hmax):
    """Würfelt eine zeilen x spalten Höhenkarte (0..hmax), die konstruktiv
    vollständig sichtbar ist: In Kamera-Reihenfolge (weit hinten zuerst) wird
    jede Höhe so weit gesenkt, bis keine schon gesetzte Säule verdeckt wird
    (Höhe 0 verdeckt nie etwas, die Schleife endet also immer)."""
    hoehen = [[0] * spalten for _ in range(zeilen)]
    ordnung = sorted(((r, c) for r in range(zeilen) for c in range(spalten)),
                     key=lambda rc: (rc[0] + rc[1], rc[0]))
    for i, (r, c) in enumerate(ordnung):
        h = rng.randint(0, hmax)
        hoehen[r][c] = h
        while h > 0 and any(not _saeule_sichtbar(rr, cc, hoehen) for rr, cc in ordnung[:i]):
            h -= 1
            hoehen[r][c] = h
    return hoehen


def _hoehen_gueltig(hoehen, zeilen_von, zeilen_bis, hmax):
    """Formprüfung einer Höhenkarte (für die Prüfer). Rückgabe: Grund oder None."""
    if not isinstance(hoehen, list) or not hoehen:
        return "keine Höhenkarte vorhanden"
    if not all(isinstance(z, list) for z in hoehen):
        return "Höhenkarte besteht nicht aus Zeilenlisten"
    zeilen, spalten = len(hoehen), len(hoehen[0])
    if any(len(z) != spalten for z in hoehen):
        return "Höhenkarte ist nicht rechteckig"
    if not (zeilen_von <= zeilen <= zeilen_bis and zeilen_von <= spalten <= zeilen_bis):
        return f"Höhenkarte {zeilen}x{spalten} liegt außerhalb {zeilen_von}..{zeilen_bis}"
    for z in hoehen:
        for h in z:
            if not _ist_int(h) or not (0 <= h <= hmax):
                return f"Höhe {h!r} liegt außerhalb von 0..{hmax}"
    return None


# ------------------------------------------------------------ Isometrie-Szene

def _opak(punkte, farbe, helligkeit):
    """Undurchsichtige Fläche in einer von drei Helligkeiten: erst ein deckender
    Untergrund in KONTUR-Farbe, darauf die Palettenfarbe mit fill-opacity. Bei
    grafik_kern scheinen verdeckte Würfel durch die halbtransparenten Flächen
    durch; hier würde das beim Zählen in die Irre führen."""
    pts = _punkte(punkte)
    return (f'<polygon points="{pts}" fill="{KONTUR}"/>'
            f'<polygon points="{pts}" fill="{farbe}" fill-opacity="{helligkeit}" '
            f'stroke="{KONTUR}" stroke-width="1.5" stroke-linejoin="round"/>')


def _wuerfel_svg(r, c, k, farbe):
    """Ein einzelner Würfel auf Ebene k (0 = Boden) der Säule (r,c): drei
    Flächen in den Helligkeiten 0.52 / 0.78 / 1.0 wie grafik_kern._saeule_svg."""
    tw, th, ch = GK.ISO_TW, GK.ISO_TH, GK.ISO_CH
    x = (c - r) * (tw / 2)
    y = (r + c) * (th / 2)
    grund = y - k * ch
    top = grund - ch
    dach = [(x, top - th / 2), (x + tw / 2, top), (x, top + th / 2), (x - tw / 2, top)]
    rechts = [(x + tw / 2, top), (x, top + th / 2), (x, grund + th / 2), (x + tw / 2, grund)]
    links = [(x - tw / 2, top), (x, top + th / 2), (x, grund + th / 2), (x - tw / 2, grund)]
    return _opak(links, farbe, 0.52) + _opak(rechts, farbe, 0.78) + _opak(dach, farbe, 1.0)


def _iso_ecke(r, c, z):
    """Bildpunkt einer Würfelecke; r,c dürfen halbzahlig sein (Zellrand)."""
    return ((c - r) * (GK.ISO_TW / 2), (r + c) * (GK.ISO_TH / 2) - z * GK.ISO_CH)


def _kasten_svg(zeilen, spalten, hoehe):
    """Gestrichelter Umriss des vollen Quaders (alle 12 Kanten)."""
    ecken = {}
    for ri, r in enumerate((-0.5, zeilen - 0.5)):
        for ci, c in enumerate((-0.5, spalten - 0.5)):
            for zi, z in enumerate((0, hoehe)):
                ecken[(ri, ci, zi)] = _iso_ecke(r, c, z)
    linien = []
    for a in sorted(ecken):
        for b in sorted(ecken):
            if a < b and sum(1 for i in range(3) if a[i] != b[i]) == 1:
                (x1, y1), (x2, y2) = ecken[a], ecken[b]
                linien.append(f'<line x1="{GK._fmt(x1)}" y1="{GK._fmt(y1)}" x2="{GK._fmt(x2)}" '
                              f'y2="{GK._fmt(y2)}" stroke="{HELL}" stroke-width="2" '
                              f'stroke-dasharray="6,5" stroke-linecap="round" stroke-opacity="0.85"/>')
    return "".join(linien), list(ecken.values())


def _render_iso(hoehen, farbe, kasten_hoehe=None):
    """Isometrische Szene einer zeilen x spalten Höhenkarte, jeder Würfel für
    sich gezeichnet (Höhen und Zahl sind zählbar). kasten_hoehe setzt den
    gestrichelten Umriss des vollen Quaders darüber."""
    zeilen, spalten = len(hoehen), len(hoehen[0])
    ordnung = sorted(((r, c) for r in range(zeilen) for c in range(spalten)),
                     key=lambda rc: (rc[0] + rc[1], rc[0]))
    teile = [GK._boden_svg(r, c) for r, c in ordnung]
    for r, c in ordnung:
        h = hoehen[r][c]
        if h == 0:
            continue
        teile.extend(_wuerfel_svg(r, c, k, farbe) for k in range(h))
    punkte = [p for r, c in ordnung for p in GK._hexagon_punkte(r, c, hoehen[r][c])]
    if kasten_hoehe:
        kasten, ecken = _kasten_svg(zeilen, spalten, kasten_hoehe)
        teile.append(kasten)
        punkte += ecken
    xs = [p[0] for p in punkte]
    ys = [p[1] for p in punkte]
    return GK._svg_wrap(max(xs) - min(xs), max(ys) - min(ys), 20, "".join(teile),
                        dx0=min(xs), dy0=min(ys))


# ------------------------------------------------ Rasterbilder (Antwortoptionen)

def _render_raster(raster, farbe, unit=34):
    """Rechteckiges 0/1-Raster: Rasterlinien plus gefüllte Felder."""
    zeilen, spalten = len(raster), len(raster[0])
    teile = []
    for i in range(zeilen + 1):
        teile.append(f'<line x1="0" y1="{i * unit}" x2="{spalten * unit}" y2="{i * unit}" '
                     f'stroke="{RASTER}" stroke-width="1"/>')
    for j in range(spalten + 1):
        teile.append(f'<line x1="{j * unit}" y1="0" x2="{j * unit}" y2="{zeilen * unit}" '
                     f'stroke="{RASTER}" stroke-width="1"/>')
    for r in range(zeilen):
        for c in range(spalten):
            if raster[r][c]:
                teile.append(f'<rect x="{c * unit}" y="{r * unit}" width="{unit}" height="{unit}" '
                             f'fill="{farbe}" stroke="{KONTUR}" stroke-width="2"/>')
    return GK._svg_wrap(spalten * unit, zeilen * unit, unit // 2, "".join(teile))


# ================================================================ 1. ansicht
# Konvention (im Fragetext genannt): Im isometrischen Bild sieht man zwei
# Wände. „vorne“ ist die LINKE sichtbare Wand (man schaut entlang der Zeilen,
# die Spalten laufen von links nach rechts), „rechts“ ist die RECHTE sichtbare
# Wand (die nahe Ecke liegt links, also laufen die Zeilen von der letzten zur
# ersten). „oben“ ist der Grundriss mit der linken Wand unten und der rechten
# Wand rechts: Zeile r läuft von oben nach unten, Spalte c von links nach rechts.

RICHTUNGEN = ("oben", "vorne", "rechts")


def _profil_raster(profil, hmax):
    """Wandansicht als Raster: hmax Zeilen (oben zuerst), Säulen wachsen vom Boden."""
    return [[1 if p > hmax - 1 - i else 0 for p in profil] for i in range(hmax)]


def _profil_von_raster(raster):
    return [sum(raster[i][c] for i in range(len(raster))) for c in range(len(raster[0]))]


def ansicht_raster(hoehen, richtung, hmax):
    """Die Wahrheit der Aufgabe: Ansicht der Höhenkarte als 0/1-Raster."""
    zeilen, spalten = len(hoehen), len(hoehen[0])
    if richtung == "oben":
        return [[1 if hoehen[r][c] > 0 else 0 for c in range(spalten)] for r in range(zeilen)]
    if richtung == "vorne":
        return _profil_raster([max(hoehen[r][c] for r in range(zeilen))
                               for c in range(spalten)], hmax)
    if richtung == "rechts":
        return _profil_raster([max(hoehen[r]) for r in reversed(range(zeilen))], hmax)
    raise ValueError(f"unbekannte Richtung {richtung!r}")


def _spiegel_h(raster):
    return [list(reversed(z)) for z in raster]


def _spiegel_v(raster):
    return [list(z) for z in reversed(raster)]


def _ansicht_masse(stage, index):
    """(Zeilen, Spalten, größte Höhe). Stufe 3-4: 2x2 bzw. 3x3, Höhe 2;
    Stufe 5: 3x3, Höhe 3; Stufe 6-8: 4x3 bis 4x4, Höhe 4."""
    if stage <= 4:
        klein = (stage == 3 and index < 3) or (stage == 4 and index < 1)
        n = 2 if klein else 3
        return n, n, 2
    if stage == 5:
        return 3, 3, 3
    plan = {6: [(3, 4), (4, 3), (4, 3), (4, 4), (4, 4), (4, 4)],
            7: [(4, 3), (4, 4), (4, 4), (4, 4), (4, 4), (4, 4)],
            8: [(4, 4)] * 6}[stage]
    return plan[index][0], plan[index][1], 4


def _ansicht_richtung(stage, index):
    if stage <= 4:
        return "oben"
    if stage == 5:
        return ("vorne", "rechts")[index % 2]
    return RICHTUNGEN[(index + stage) % 3]


_ANSICHT_Q = {
    "oben": ["Wie sieht das Gebäude von oben aus? Die linke Wand ist unten.",
             "Du schaust von oben auf das Gebäude. Die linke Wand ist unten.",
             "Welches Bild zeigt das Gebäude von oben? Die linke Wand ist unten."],
    "vorne": ["Du schaust auf die linke Wand. Welches Bild zeigt sie?",
              "Wie sieht das Gebäude von vorne aus? Schau auf die linke Wand.",
              "Welches Bild zeigt die linke Wand des Gebäudes?"],
    "rechts": ["Du schaust auf die rechte Wand. Welches Bild zeigt sie?",
               "Wie sieht das Gebäude von rechts aus? Schau auf die rechte Wand.",
               "Welches Bild zeigt die rechte Wand des Gebäudes?"],
}
_ANSICHT_HINT = {
    "oben": "Welche Felder sind besetzt, wenn du von oben schaust?",
    "vorne": "Such für jede Säule an der Wand die höchste Stelle.",
    "rechts": "Such für jede Säule an der Wand die höchste Stelle.",
}


def _zellfehler(rng, raster, richtung, hmax):
    """Ablenker „eine Stelle verändert“: ein Feld kippen (oben) bzw. eine
    Säule der Wandansicht um eins höher oder niedriger."""
    if richtung == "oben":
        r = rng.randrange(len(raster))
        c = rng.randrange(len(raster[0]))
        neu = [list(z) for z in raster]
        neu[r][c] = 1 - neu[r][c]
        return neu
    profil = _profil_von_raster(raster)
    c = rng.randrange(len(profil))
    profil[c] += rng.choice((-1, 1))
    if not (0 <= profil[c] <= hmax):
        return raster
    return _profil_raster(profil, hmax)


def _ansicht_ablenker(rng, hoehen, richtung, hmax, richtig):
    """Drei verschiedene falsche Ansichten: aus anderer Richtung, gespiegelt,
    eine Stelle verändert (und bei Bedarf weitere Stellenfehler)."""
    kandidaten = []
    if richtung == "oben":
        kandidaten += [_dreh180(richtig), _spiegel_h(richtig), _spiegel_v(richtig)]
    else:
        andere = ansicht_raster(hoehen, "rechts" if richtung == "vorne" else "vorne", hmax)
        if len(andere[0]) == len(richtig[0]):
            kandidaten.append(andere)
        kandidaten.append(_spiegel_h(richtig))
        if len(andere[0]) == len(richtig[0]):
            kandidaten.append(_spiegel_h(andere))
    kandidaten.append(_zellfehler(rng, richtig, richtung, hmax))
    gewaehlt = []
    for k in kandidaten:
        if k != richtig and k not in gewaehlt and len(gewaehlt) < 3:
            gewaehlt.append(k)
    for _ in range(60):
        if len(gewaehlt) >= 3:
            break
        k = _zellfehler(rng, richtig, richtung, hmax)
        if k != richtig and k not in gewaehlt:
            gewaehlt.append(k)
    if len(gewaehlt) < 3:
        raise _Neu()
    return gewaehlt


def _dreh180(raster):
    return _spiegel_v(_spiegel_h(raster))


def _erzeuge_ansicht(rng, stage, index):
    zeilen, spalten, hmax = _ansicht_masse(stage, index)
    richtung = _ansicht_richtung(stage, index)
    hoehen = _baue_sichtbar(rng, zeilen, spalten, hmax)
    belegt = sum(1 for z in hoehen for h in z if h > 0)
    if sum(map(sum, hoehen)) < 3 or belegt < 2 or belegt == zeilen * spalten and richtung == "oben":
        raise _Neu()
    richtig = ansicht_raster(hoehen, richtung, hmax)
    if richtig == _spiegel_h(richtig):          # symmetrisch: Spiegel-Ablenker wäre auch richtig
        raise _Neu()
    ablenker = _ansicht_ablenker(rng, hoehen, richtung, hmax, richtig)
    optionen, idx = _mische(rng, richtig, ablenker)
    farbe = rng.choice(PALETTE)
    kern = {"art": "ansicht", "hoehen": hoehen, "richtung": richtung, "hmax": hmax,
            "optionen": optionen, "richtig": idx, "stufe": stage}
    return {"type": "bildwahl", "q": _vorlage(_ANSICHT_Q[richtung], index),
            "svg": _render_iso(hoehen, farbe),
            "optionen_svg": [_render_raster(o, farbe) for o in optionen],
            "richtig": idx, "kern": kern, "hint": _ANSICHT_HINT[richtung]}, kern


def _raster_gueltig(raster, zeilen, spalten):
    return (isinstance(raster, list) and len(raster) == zeilen
            and all(isinstance(z, list) and len(z) == spalten
                    and all(_ist_int(x) and x in (0, 1) for x in z) for z in raster))


def pruefe_ansicht(kern):
    """Rechnet die Ansicht aus der Höhenkarte nach, verlangt dass jede Säule
    sichtbar ist und genau eine Option mit der Rechnung übereinstimmt."""
    try:
        hoehen, richtung, hmax = kern["hoehen"], kern["richtung"], kern["hmax"]
        optionen, richtig = kern["optionen"], kern["richtig"]
    except (KeyError, TypeError):
        return False, "Kern hat kein gültiges Format"
    grund = _hoehen_gueltig(hoehen, 2, 4, 4)
    if grund:
        return False, grund
    if richtung not in RICHTUNGEN:
        return False, f"Richtung {richtung!r} unbekannt"
    if not _ist_int(hmax) or not (1 <= hmax <= 4) or hmax < max(max(z) for z in hoehen):
        return False, f"hmax {hmax!r} passt nicht zur Höhenkarte"
    if sum(map(sum, hoehen)) < 3:
        return False, "weniger als 3 Würfel im Gebäude"
    if not _alle_saeulen_sichtbar(hoehen):
        return False, "mindestens eine Säule ist im Bild nicht sichtbar – Höhe nicht eindeutig ablesbar"
    erwartet = ansicht_raster(hoehen, richtung, hmax)
    zeilen, spalten = len(erwartet), len(erwartet[0])
    if not isinstance(optionen, list) or len(optionen) != 4:
        return False, "es müssen genau 4 Optionen da sein"
    if not all(_raster_gueltig(o, zeilen, spalten) for o in optionen):
        return False, f"eine Option ist kein {zeilen}x{spalten}-Raster aus 0/1"
    if len({tuple(map(tuple, o)) for o in optionen}) != 4:
        return False, "die vier Optionen sind nicht paarweise verschieden"
    if not _ist_int(richtig) or not (0 <= richtig < 4):
        return False, f"'richtig'={richtig!r} ist kein gültiger Options-Index"
    passend = [i for i, o in enumerate(optionen) if o == erwartet]
    if passend != [richtig]:
        return False, f"nachgerechnete Ansicht passt zu Optionen {passend}, markiert ist {richtig}"
    return True, "Ansicht stimmt: genau eine Option zeigt die nachgerechnete Ansicht"


# ============================================================= 2. netzfalten
# Ein Würfelnetz ist ein Hexomino (sechs Quadrate, kantenverbunden). Ob es sich
# zum Würfel faltet, wird nicht nach Muster, sondern durch Abrollen berechnet:
# Ein Würfel steht auf dem Startquadrat und rollt über die Nachbarquadrate; die
# Fläche, die dabei jeweils den Boden berührt, gehört zu diesem Quadrat. Das
# Netz faltet genau dann, wenn alle sechs Würfelflächen genau einmal drankommen.
# (Ein 2x2-Block kann nie falten: vier Flächen an einer Würfelecke gibt es nicht.)

_ACHT = (lambda r, c: (r, c), lambda r, c: (r, -c), lambda r, c: (-r, c), lambda r, c: (-r, -c),
         lambda r, c: (c, r), lambda r, c: (c, -r), lambda r, c: (-c, r), lambda r, c: (-c, -r))
_NACHBAR_ZIEL = (((0, 1), "ost"), ((0, -1), "west"), ((-1, 0), "nord"), ((1, 0), "sued"))
GEGENUEBER = {0: 1, 1: 0, 2: 3, 3: 2, 4: 5, 5: 4}     # Würfelflächen: unten/oben, N/S, O/W


def _norm(zellen):
    mr = min(r for r, c in zellen)
    mc = min(c for r, c in zellen)
    return tuple(sorted((r - mr, c - mc) for r, c in zellen))


def _acht_lagen(zellen):
    return [_norm([f(r, c) for r, c in zellen]) for f in _ACHT]


def _kanonisch(zellen):
    """Eine Form, egal wie gedreht oder gespiegelt (kleinste der 8 Lagen)."""
    return min(_acht_lagen(zellen))


_HEXOMINOS = []


def alle_hexominos():
    """Alle 35 freien Hexominos als kanonische, sortierte Zelltupel."""
    if not _HEXOMINOS:
        formen = {((0, 0),)}
        for _ in range(5):
            neu = set()
            for form in formen:
                for r, c in form:
                    for (dr, dc), _n in _NACHBAR_ZIEL:
                        z = (r + dr, c + dc)
                        if z not in form:
                            neu.add(_norm(list(form) + [z]))
            formen = neu
        _HEXOMINOS.extend(sorted({_kanonisch(f) for f in formen}))
    return list(_HEXOMINOS)


def _rolle(zustand, richtung):
    """Würfel rollt eine Zelle weiter. Zustand = (unten, oben, nord, süd, ost, west),
    jeweils die Nummer der Würfelfläche an dieser Stelle."""
    u, o, n, s, e, w = zustand
    if richtung == "ost":
        return (e, w, n, s, o, u)
    if richtung == "west":
        return (w, e, n, s, u, o)
    if richtung == "nord":
        return (n, s, o, u, e, w)
    return (s, n, u, o, e, w)


def _hat_2x2(zellen):
    return any({(r, c), (r + 1, c), (r, c + 1), (r + 1, c + 1)} <= zellen for r, c in zellen)


def falte_netz(zellen):
    """Rollt einen Würfel über das Netz. Rückgabe {zelle: würfelfläche} oder
    None, wenn das Netz kein Würfelnetz ist."""
    zellen = {tuple(z) for z in zellen}
    if len(zellen) != 6 or not GK._zusammenhaengend(zellen) or _hat_2x2(zellen):
        return None
    start = min(zellen)
    zustand = {start: (0, 1, 2, 3, 4, 5)}
    flaeche = {start: 0}
    stapel = [start]
    while stapel:
        z = stapel.pop()
        for (dr, dc), name in _NACHBAR_ZIEL:
            nb = (z[0] + dr, z[1] + dc)
            if nb in zellen and nb not in zustand:
                zustand[nb] = _rolle(zustand[z], name)
                flaeche[nb] = zustand[nb][0]
                stapel.append(nb)
    return flaeche if len(set(flaeche.values())) == 6 else None


def _max_linie(zellen):
    z = set(zellen)
    best = 1
    for r, c in z:
        for dr, dc in ((0, 1), (1, 0)):
            if (r - dr, c - dc) in z:
                continue
            n = 0
            while (r + n * dr, c + n * dc) in z:
                n += 1
            best = max(best, n)
    return best


def _leicht_ungueltig(form):
    """Offensichtlich kein Netz: 2x2-Block oder fünf Quadrate in einer Reihe."""
    return _hat_2x2(set(form)) or _max_linie(form) >= 5


def _netz_versetzt(rng, netz):
    """Ungültige Nachbarn eines gültigen Netzes: ein Quadrat wird woanders
    angeklebt. Sehen dem Original zum Verwechseln ähnlich."""
    netz = set(netz)
    kandidaten = set()
    for x in sorted(netz):
        rest = netz - {x}
        if not GK._zusammenhaengend(rest):
            continue
        for r, c in sorted(rest):
            for (dr, dc), _n in _NACHBAR_ZIEL:
                z = (r + dr, c + dc)
                if z not in rest and z != x:
                    form = _kanonisch(list(rest | {z}))
                    if falte_netz(form) is None:
                        kandidaten.add(form)
    kandidaten.discard(_kanonisch(list(netz)))
    return sorted(kandidaten)


def _netz_plan(stage, index):
    """(Modus, Ablenker-Härte, Netzart) je Stufe und Index."""
    if stage <= 4:
        return "wuerfel", ("leicht" if stage == 3 or index < 3 else "gemischt"), None
    if stage == 5:
        return ("wuerfel", "schwer", None) if index < 3 else ("gegenueber", None, "typisch")
    if stage == 6:
        if index < 2:
            return "wuerfel", "schwer", None
        return "gegenueber", None, ("untypisch" if index == 5 else "typisch")
    return "gegenueber", None, ("typisch" if stage == 7 and index < 2 else "untypisch")


# ------------------------------------------------------------ Zeichen und Netze

ZEICHEN = ("kreis", "dreieck", "quadrat", "stern", "raute", "kreuz")
_ZEICHEN_DATIV = {"kreis": "vom Kreis", "dreieck": "vom Dreieck", "quadrat": "vom Quadrat",
                  "stern": "vom Stern", "raute": "von der Raute", "kreuz": "vom Kreuz"}
_ZEICHEN_FARBE = {"kreis": PALETTE[0], "dreieck": PALETTE[1], "quadrat": PALETTE[2],
                  "stern": PALETTE[3], "raute": PALETTE[0], "kreuz": PALETTE[2]}


def _punkte(liste):
    return " ".join(f"{GK._fmt(x)},{GK._fmt(y)}" for x, y in liste)


def _zeichen_svg(name, cx, cy, u):
    """Einfache Form in einer Zelle der Kantenlänge u, Mittelpunkt (cx,cy)."""
    f, k = _ZEICHEN_FARBE[name], f'stroke="{KONTUR}" stroke-width="2"'
    a = u * 0.30
    if name == "kreis":
        return f'<circle cx="{GK._fmt(cx)}" cy="{GK._fmt(cy)}" r="{GK._fmt(a)}" fill="{f}" {k}/>'
    if name == "dreieck":
        pts = [(cx, cy - a), (cx + a * 1.1, cy + a * 0.85), (cx - a * 1.1, cy + a * 0.85)]
    elif name == "quadrat":
        pts = [(cx - a * 0.85, cy - a * 0.85), (cx + a * 0.85, cy - a * 0.85),
               (cx + a * 0.85, cy + a * 0.85), (cx - a * 0.85, cy + a * 0.85)]
    elif name == "raute":
        pts = [(cx, cy - a * 1.2), (cx + a * 0.9, cy), (cx, cy + a * 1.2), (cx - a * 0.9, cy)]
    elif name == "kreuz":
        d, e = a * 0.38, a * 1.1
        pts = [(cx - d, cy - e), (cx + d, cy - e), (cx + d, cy - d), (cx + e, cy - d),
               (cx + e, cy + d), (cx + d, cy + d), (cx + d, cy + e), (cx - d, cy + e),
               (cx - d, cy + d), (cx - e, cy + d), (cx - e, cy - d), (cx - d, cy - d)]
    else:   # stern: fünf Spitzen
        import math
        pts = []
        for i in range(10):
            w = -math.pi / 2 + i * math.pi / 5
            rad = a * 1.25 if i % 2 == 0 else a * 0.55
            pts.append((cx + rad * math.cos(w), cy + rad * math.sin(w)))
    return f'<polygon points="{_punkte(pts)}" fill="{f}" {k}/>'


def _render_zeichen(name, u=64):
    """Antwortbild: ein einzelnes Zeichen auf hellem Feld."""
    feld = (f'<rect x="0" y="0" width="{u}" height="{u}" fill="{HELL}" fill-opacity="0.14" '
            f'stroke="{KONTUR}" stroke-width="2"/>')
    return GK._svg_wrap(u, u, u // 4, feld + _zeichen_svg(name, u / 2, u / 2, u))


def _render_netz(zellen, farbe, zeichen=None, unit=32):
    """Netz als Quadrate; mit zeichen = {zelle: name} sitzt in jedem ein Zeichen."""
    teile = []
    for r, c in sorted(zellen):
        if zeichen is None:
            teile.append(f'<rect x="{c * unit}" y="{r * unit}" width="{unit}" height="{unit}" '
                         f'fill="{farbe}" stroke="{KONTUR}" stroke-width="2"/>')
        else:
            teile.append(f'<rect x="{c * unit}" y="{r * unit}" width="{unit}" height="{unit}" '
                         f'fill="{HELL}" fill-opacity="0.14" stroke="{KONTUR}" stroke-width="2"/>')
            teile.append(_zeichen_svg(zeichen[(r, c)], c * unit + unit / 2, r * unit + unit / 2, unit))
    hoehe = max(r for r, c in zellen) + 1
    breite = max(c for r, c in zellen) + 1
    return GK._svg_wrap(breite * unit, hoehe * unit, unit // 2, "".join(teile))


def _wuerfelbild(farbe):
    """Fragebild für „Welches Netz?“: ein Würfel in Isometrie."""
    return _render_iso([[1]], farbe)


# --------------------------------------------------------------- Erzeuger/Prüfer

_NETZ_Q_WUERFEL = ["Welches Netz lässt sich zu einem Würfel falten?",
                   "Aus welchem Netz kannst du einen Würfel falten?",
                   "Nur eins der Netze faltet sich zum Würfel. Welches?"]
_NETZ_Q_GEGEN = ["Was liegt gegenüber {dativ}? Falte das Netz im Kopf.",
                 "Das Netz wird zum Würfel. Was liegt gegenüber {dativ}?",
                 "Falte im Kopf: Welches Zeichen liegt gegenüber {dativ}?"]


def _lage_zufall(rng, form):
    """Zufällig gedrehte/gespiegelte Zeichenlage, damit nicht alle Netze gleich liegen."""
    return rng.choice(_acht_lagen(form))


def _netz_wuerfel(rng, haerte, stage, index):
    alle = alle_hexominos()
    gueltig = [f for f in alle if falte_netz(f)]
    ungueltig = [f for f in alle if not falte_netz(f)]
    richtig = rng.choice(gueltig)
    leicht = [f for f in ungueltig if _leicht_ungueltig(f)]
    aehnlich = _netz_versetzt(rng, richtig)
    schwer = [f for f in aehnlich if not _leicht_ungueltig(f)]
    schwer_rest = [f for f in ungueltig if not _leicht_ungueltig(f) and f not in schwer]
    if haerte == "leicht":
        reihen = [rng.sample(leicht, len(leicht))]
    elif haerte == "gemischt":
        reihen = [rng.sample(leicht, 2), rng.sample(schwer or schwer_rest, 1)]
    else:
        reihen = [rng.sample(schwer, len(schwer)), rng.sample(schwer_rest, len(schwer_rest)),
                  rng.sample(leicht, len(leicht))]
    gewaehlt = []
    for reihe in reihen:
        for f in reihe:
            if f not in gewaehlt and len(gewaehlt) < 3:
                gewaehlt.append(f)
    if len(gewaehlt) < 3:
        raise _Neu()
    lagen = [_lage_zufall(rng, f) for f in [richtig] + gewaehlt]
    optionen, idx = _mische(rng, lagen[0], lagen[1:])
    farbe = rng.choice(PALETTE)
    kern = {"art": "netzfalten", "modus": "wuerfel",
            "optionen": [[list(z) for z in o] for o in optionen], "richtig": idx, "stufe": stage}
    return {"type": "bildwahl", "q": _vorlage(_NETZ_Q_WUERFEL, index), "svg": _wuerfelbild(farbe),
            "optionen_svg": [_render_netz(o, farbe) for o in optionen], "richtig": idx,
            "kern": kern, "hint": "Stell dir vor, du klappst die Quadrate nacheinander hoch."}, kern


def _netz_gegenueber(rng, art, stage, index):
    gueltig = [f for f in alle_hexominos() if falte_netz(f)]
    pool = [f for f in gueltig if (_max_linie(f) == 4) == (art == "typisch")]
    form = _lage_zufall(rng, rng.choice(pool))
    zellen = sorted(form)
    namen = list(ZEICHEN)
    rng.shuffle(namen)
    zeichen = dict(zip(zellen, namen))
    flaeche = falte_netz(zellen)
    gefragt = rng.choice(ZEICHEN)
    zelle_g = next(z for z, n in zeichen.items() if n == gefragt)
    gegen = next(n for z, n in zeichen.items() if flaeche[z] == GEGENUEBER[flaeche[zelle_g]])
    # Beliebte Fehlgriffe zuerst: die Zeichen, die im Netz direkt neben dem gefragten liegen.
    nachbarn = [zeichen[(zelle_g[0] + dr, zelle_g[1] + dc)] for (dr, dc), _n in _NACHBAR_ZIEL
                if (zelle_g[0] + dr, zelle_g[1] + dc) in zeichen]
    rest = [n for n in ZEICHEN if n not in (gefragt, gegen) and n not in nachbarn]
    rng.shuffle(nachbarn)
    rng.shuffle(rest)
    ablenker = (nachbarn + rest)[:3]
    optionen, idx = _mische(rng, gegen, ablenker)
    farbe = rng.choice(PALETTE)
    kern = {"art": "netzfalten", "modus": "gegenueber", "netz": [list(z) for z in zellen],
            "zeichen": [zeichen[z] for z in zellen], "gefragt": gefragt,
            "optionen": optionen, "richtig": idx, "stufe": stage}
    return {"type": "bildwahl", "q": _vorlage(_NETZ_Q_GEGEN, index).format(dativ=_ZEICHEN_DATIV[gefragt]),
            "svg": _render_netz(zellen, farbe, zeichen),
            "optionen_svg": [_render_zeichen(n) for n in optionen], "richtig": idx,
            "kern": kern, "hint": "Zwei Quadrate nebeneinander im Netz liegen am Würfel nie gegenüber."}, kern


def _erzeuge_netz(rng, stage, index):
    modus, haerte, art = _netz_plan(stage, index)
    if modus == "wuerfel":
        return _netz_wuerfel(rng, haerte, stage, index)
    return _netz_gegenueber(rng, art, stage, index)


def _netz_zellen(netz):
    """Liste von [r,c] -> Menge von Tupeln, oder None bei Formfehler."""
    try:
        zellen = {(int(z[0]), int(z[1])) for z in netz}
    except (TypeError, ValueError, IndexError):
        return None
    return zellen if len(zellen) == 6 else None


def pruefe_netzfalten(kern):
    """Faltet jedes Netz durch Abrollen nach. wuerfel: genau eine Option faltet
    und ist die markierte, alle Formen verschieden. gegenueber: Netz faltet,
    Zeichen verschieden, die markierte Option ist das nachgerechnete Gegenüber."""
    try:
        modus, optionen, richtig = kern["modus"], kern["optionen"], kern["richtig"]
    except (KeyError, TypeError):
        return False, "Kern hat kein gültiges Format"
    if not isinstance(optionen, list) or len(optionen) != 4:
        return False, "es müssen genau 4 Optionen da sein"
    if not _ist_int(richtig) or not (0 <= richtig < 4):
        return False, f"'richtig'={richtig!r} ist kein gültiger Options-Index"
    if modus == "wuerfel":
        formen = [_netz_zellen(o) for o in optionen]
        if any(f is None for f in formen):
            return False, "eine Option ist kein Netz aus 6 verschiedenen Quadraten"
        if len({_kanonisch(f) for f in formen}) != 4:
            return False, "zwei Optionen sind dieselbe Form (nur gedreht oder gespiegelt)"
        faltend = [i for i, f in enumerate(formen) if falte_netz(f)]
        if faltend != [richtig]:
            return False, f"es falten die Optionen {faltend}, markiert ist {richtig}"
        return True, "genau ein Netz faltet sich zum Würfel, und es ist das markierte"
    if modus == "gegenueber":
        try:
            netz, zeichen, gefragt = kern["netz"], kern["zeichen"], kern["gefragt"]
        except KeyError:
            return False, "Kern hat kein gültiges Format"
        zellen = _netz_zellen(netz)
        if zellen is None or not isinstance(zeichen, list) or len(zeichen) != 6:
            return False, "Netz oder Zeichenliste ist ungültig"
        flaeche = falte_netz(zellen)
        if flaeche is None:
            return False, "das Netz faltet sich nicht zum Würfel"
        if sorted(zeichen) != sorted(ZEICHEN):
            return False, "die sechs Zeichen sind nicht alle verschieden oder unbekannt"
        zuordnung = {(int(z[0]), int(z[1])): n for z, n in zip(netz, zeichen)}
        if gefragt not in ZEICHEN:
            return False, f"gefragtes Zeichen {gefragt!r} unbekannt"
        zelle_g = next(z for z, n in zuordnung.items() if n == gefragt)
        gegen = next(n for z, n in zuordnung.items() if flaeche[z] == GEGENUEBER[flaeche[zelle_g]])
        if any(n not in ZEICHEN for n in optionen) or len(set(optionen)) != 4:
            return False, "die Optionen sind keine 4 verschiedenen Zeichen"
        if gefragt in optionen:
            return False, "das gefragte Zeichen selbst steht unter den Optionen"
        if optionen[richtig] != gegen:
            return False, f"gegenüber liegt {gegen!r}, markiert ist {optionen[richtig]!r}"
        return True, "das markierte Zeichen liegt nachgerechnet gegenüber"
    return False, f"Modus {modus!r} unbekannt"


# ========================================================== 3. gitterfigur
# Eine Kästchenfigur besteht aus ganzen Kästchen und (ab Stufe 6) halben, also
# Dreiecken, deren Katheten auf Kästchenseiten liegen. Zur Löcherprüfung wird
# jedes Kästchen in vier Teildreiecke (N, O, S, W) zerlegt: Ein ganzes Kästchen
# besetzt alle vier, ein halbes zwei benachbarte. So fällt auch ein Hohlraum
# auf, den ein halbes Kästchen zuschnürt.

ECKEN = ("ol", "or", "ul", "ur")       # Ecke mit dem rechten Winkel des halben Kästchens
_ECKE_DREIECKE = {"ol": ("N", "W"), "or": ("N", "E"), "ul": ("S", "W"), "ur": ("S", "E")}
_ECKE_KATHETEN = {"ol": ((-1, 0), (0, -1)), "or": ((-1, 0), (0, 1)),
                  "ul": ((1, 0), (0, -1)), "ur": ((1, 0), (0, 1))}
_IM_KAESTCHEN = {"N": ("E", "W"), "E": ("N", "S"), "S": ("E", "W"), "W": ("N", "S")}
_UEBER_RAND = {"N": (-1, 0, "S"), "S": (1, 0, "N"), "E": (0, 1, "W"), "W": (0, -1, "E")}


def _belegte_dreiecke(zellen, halbe):
    belegt = {(r, c, s) for r, c in zellen for s in "NESW"}
    for (r, c), ecke in halbe:
        belegt |= {(r, c, s) for s in _ECKE_DREIECKE[ecke]}
    return belegt


def _dreieck_nachbarn(t):
    r, c, s = t
    yield from ((r, c, s2) for s2 in _IM_KAESTCHEN[s])
    dr, dc, s2 = _UEBER_RAND[s]
    yield (r + dr, c + dc, s2)


def _figur_pruefen(zellen, halbe):
    """Grund, warum die Figur unzulässig ist, oder None. zellen: Menge von
    (r,c); halbe: Liste von ((r,c), ecke)."""
    if not (3 <= len(zellen) <= 16):
        return f"{len(zellen)} ganze Kästchen, erlaubt sind 3..16"
    if len(halbe) % 2 or len(halbe) > 4:
        return "die Zahl der halben Kästchen muss gerade und höchstens 4 sein"
    ort = [z for z, _e in halbe]
    if len(set(ort)) != len(ort) or any(z in zellen for z in ort):
        return "ein halbes Kästchen liegt doppelt oder auf einem ganzen"
    for (r, c), ecke in halbe:
        if ecke not in ECKEN:
            return f"Ecke {ecke!r} unbekannt"
        if not any((r + dr, c + dc) in zellen for dr, dc in _ECKE_KATHETEN[ecke]):
            return "ein halbes Kästchen liegt mit keiner Kathete an einem ganzen"
    belegt = _belegte_dreiecke(zellen, halbe)
    start = next(iter(sorted(belegt)))
    gesehen, stapel = {start}, [start]
    while stapel:
        for n in _dreieck_nachbarn(stapel.pop()):
            if n in belegt and n not in gesehen:
                gesehen.add(n)
                stapel.append(n)
    if gesehen != belegt:
        return "die Figur hängt nicht zusammen"
    alle = list(zellen) + ort
    r0, r1 = min(r for r, c in alle) - 1, max(r for r, c in alle) + 1
    c0, c1 = min(c for r, c in alle) - 1, max(c for r, c in alle) + 1
    aussen = {(r0, c0, "N")}
    stapel = [(r0, c0, "N")]
    while stapel:
        for n in _dreieck_nachbarn(stapel.pop()):
            if r0 <= n[0] <= r1 and c0 <= n[1] <= c1 and n not in belegt and n not in aussen:
                aussen.add(n)
                stapel.append(n)
    leer = {(r, c, s) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) for s in "NESW"} - belegt
    if leer != aussen:
        return "die Figur hat ein Loch"
    return None


def figur_flaeche(zellen, halbe):
    return len(zellen) + len(halbe) // 2


def figur_umfang(zellen):
    return sum(1 for r, c in zellen for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
               if (r + dr, c + dc) not in zellen)


def _bbox_umfang(zellen):
    return 2 * (max(r for r, c in zellen) - min(r for r, c in zellen)
                + max(c for r, c in zellen) - min(c for r, c in zellen) + 2)


def _render_gitterfigur(zellen, halbe, farbe, unit=34):
    alle = list(zellen) + [z for z, _e in halbe]
    zeilen = max(r for r, c in alle) + 3        # ein Kästchen Rand rundherum
    spalten = max(c for r, c in alle) + 3
    teile = []
    for i in range(zeilen + 1):
        teile.append(f'<line x1="0" y1="{i * unit}" x2="{spalten * unit}" y2="{i * unit}" '
                     f'stroke="{RASTER}" stroke-width="1"/>')
    for j in range(spalten + 1):
        teile.append(f'<line x1="{j * unit}" y1="0" x2="{j * unit}" y2="{zeilen * unit}" '
                     f'stroke="{RASTER}" stroke-width="1"/>')
    for r, c in sorted(zellen):
        teile.append(f'<rect x="{(c + 1) * unit}" y="{(r + 1) * unit}" width="{unit}" height="{unit}" '
                     f'fill="{farbe}" stroke="{KONTUR}" stroke-width="2"/>')
    for (r, c), ecke in sorted(halbe):
        x0, y0, x1, y1 = (c + 1) * unit, (r + 1) * unit, (c + 2) * unit, (r + 2) * unit
        pts = {"ol": [(x0, y0), (x1, y0), (x0, y1)], "or": [(x1, y0), (x0, y0), (x1, y1)],
               "ul": [(x0, y1), (x0, y0), (x1, y1)], "ur": [(x1, y1), (x1, y0), (x0, y1)]}[ecke]
        teile.append(GK._poly(pts, farbe, 1.0, KONTUR, 2))
    return GK._svg_wrap(spalten * unit, zeilen * unit, unit // 2, "".join(teile))


def _gitter_plan(stage, index):
    """(Frage, Variante, (min, max) ganze Kästchen) für Index 0..3.
    Variante: poly | treppe | halbe."""
    gross = {3: (5, 7), 4: (6, 8), 5: (7, 9), 6: (8, 10), 7: (9, 12), 8: (9, 12)}[stage]
    gross2 = (gross[0] + 2, gross[1] + 2) if stage <= 5 else gross
    if index == 0:
        return "flaeche", "poly", gross
    if index == 1:
        return "umfang", "poly", gross
    if index == 2:
        if stage >= 6:
            return "flaeche", "halbe", (gross[0] - 2, gross[1] - 2)
        return "flaeche", "poly", gross2
    if stage >= 5:
        return "umfang", "treppe", gross2
    return "umfang", "poly", gross2


def _treppe(rng, stage):
    """Treppenfigur: Spaltenhöhen fallen von links nach rechts, mindestens
    zwei Stufen. Ihr Umfang ist der des umschließenden Rechtecks."""
    breite = rng.randint(3, 4 if stage <= 5 else 5)
    hoch = rng.randint(3, 4 if stage <= 5 else 5)
    hoehen = [hoch]
    for _ in range(breite - 1):
        hoehen.append(max(1, hoehen[-1] - rng.choice((0, 1, 1, 2))))
    if len(set(hoehen)) < 3:
        raise _Neu()
    zellen = {(hoch - 1 - k, c) for c, h in enumerate(hoehen) for k in range(h)}
    return set(_lage_zufall(rng, sorted(zellen)))


def _halbe_dazu(rng, zellen, anzahl):
    """Setzt `anzahl` halbe Kästchen so an die Figur, dass jedes mit einer
    Kathete an einem ganzen liegt."""
    halbe = []
    for _ in range(anzahl):
        kandidaten = []
        belegt = set(zellen) | {z for z, _e in halbe}
        for r, c in sorted(zellen):
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                z = (r + dr, c + dc)
                if z in belegt:
                    continue
                for ecke in ECKEN:
                    if any((z[0] + a, z[1] + b) in zellen for a, b in _ECKE_KATHETEN[ecke]):
                        kandidaten.append((z, ecke))
        if not kandidaten:
            raise _Neu()
        halbe.append(rng.choice(sorted(set(kandidaten))))
    return halbe


def _verschiebe_figur(zellen, halbe):
    alle = list(zellen) + [z for z, _e in halbe]
    r0, c0 = min(r for r, c in alle), min(c for r, c in alle)
    return ({(r - r0, c - c0) for r, c in zellen},
            [((r - r0, c - c0), e) for (r, c), e in halbe])


_GITTER_Q = {
    "flaeche": ["Wie groß ist die Fläche? Zähl die Kästchen.",
                "Wie viele Kästchen bedeckt die Figur? Zähl sie.",
                "Wie groß ist die Fläche der Figur? Zähl die Kästchen."],
    "flaeche_halbe": ["Wie groß ist die Fläche? Zwei halbe Kästchen sind ein ganzes."],
    "umfang": ["Wie lang ist der Umfang? Zähl die Kästchenseiten.",
               "Wie lang ist der Rand der Figur? Zähl die Kästchenseiten.",
               "Wie lang ist der Umfang der Figur? Zähl die Kästchenseiten."],
}
_GITTER_HINT = {
    "flaeche": "Zähl Reihe für Reihe.",
    "flaeche_halbe": "Zwei halbe Kästchen ergeben zusammen ein ganzes.",
    "umfang": "Geh am Rand entlang und zähl jede Kästchenseite.",
    "treppe": "Schau dir das Rechteck an, in das die Treppe genau hineinpasst.",
}


def _erzeuge_gitterfigur(rng, stage, index):
    frage, variante, (lo, hi) = _gitter_plan(stage, index)
    n = rng.randint(lo, hi)
    halbe = []
    if variante == "treppe":
        zellen = _treppe(rng, stage)
    else:
        m = 5 if n <= 9 else (6 if n <= 12 else 7)
        try:
            zellen = set(GK._zufallspolyomino(rng, m, n))
        except ValueError:
            raise _Neu()
        if variante == "halbe":
            halbe = _halbe_dazu(rng, zellen, rng.choice((2, 2, 4) if stage >= 7 else (2,)))
    if variante == "poly" and frage == "umfang" and figur_umfang(zellen) == _bbox_umfang(zellen):
        raise _Neu()       # eine Treppe/ein Rechteck wäre der Denktrick, nicht das Zählen
    zellen, halbe = _verschiebe_figur(zellen, halbe)
    if _figur_pruefen(zellen, halbe) is not None:
        raise _Neu()
    if frage == "umfang" and variante == "treppe" and figur_umfang(zellen) != _bbox_umfang(zellen):
        raise _Neu()
    anzahl = figur_flaeche(zellen, halbe) if frage == "flaeche" else figur_umfang(zellen)
    farbe = rng.choice(PALETTE)
    kern = {"art": "gitterfigur", "modus": "figur", "frage": frage,
            "zellen": [list(z) for z in sorted(zellen)],
            "halbe": [[list(z), e] for z, e in sorted(halbe)], "anzahl": anzahl, "stufe": stage}
    qkey = "flaeche_halbe" if halbe else frage
    hkey = "treppe" if variante == "treppe" else qkey
    return {"type": "bildzahl", "q": _vorlage(_GITTER_Q[qkey], index),
            "svg": _render_gitterfigur(zellen, halbe, farbe), "a": anzahl, "kern": kern,
            "hint": _GITTER_HINT[hkey]}, kern


# ---------------------------------------------------- Rechteck-Rätsel (zahl, 📝)

def _rechtecke_mit_flaeche(f):
    return [(a, f // a) for a in range(1, int(f ** 0.5) + 1) if f % a == 0]


def _rechtecke_mit_umfang(u):
    return [(a, u // 2 - a) for a in range(1, u // 4 + 1)]


def raetsel_loesung(typ, zahl):
    """Antwort und Rechenterm des Rechteck-Rätsels – durch Durchprobieren
    aller Rechtecke aus ganzen Kästchen."""
    if typ == "rechtecke_flaeche":
        n = len(_rechtecke_mit_flaeche(zahl))
        return n, str(n)
    if typ == "rechtecke_umfang":
        n = len(_rechtecke_mit_umfang(zahl))
        return n, str(n)
    if typ == "max_flaeche":
        a, b = max(_rechtecke_mit_umfang(zahl), key=lambda p: p[0] * p[1])
        return a * b, f"{a}*{b}"
    if typ == "min_umfang":
        a, b = min(_rechtecke_mit_flaeche(zahl), key=lambda p: p[0] + p[1])
        return 2 * (a + b), f"2*({a}+{b})"
    raise ValueError(f"unbekannte Rätselart {typ!r}")


_RAETSEL_Q = {
    "rechtecke_flaeche": "Fläche {z}: Wie viele verschiedene Rechtecke aus ganzen Kästchen gibt es? "
                         "Gedrehte zählen einmal.",
    "rechtecke_umfang": "Umfang {z}: Wie viele verschiedene Rechtecke aus ganzen Kästchen gibt es? "
                        "Gedrehte zählen einmal.",
    "max_flaeche": "Rechteck aus ganzen Kästchen, Umfang {z}. Wie groß ist die Fläche höchstens?",
    "min_umfang": "Rechteck aus ganzen Kästchen, Fläche {z}. Wie klein ist der Umfang mindestens?",
}
_RAETSEL_HINT = {
    "rechtecke_flaeche": "Probier alle Längen durch: 1 mal …, 2 mal …, und so weiter.",
    "rechtecke_umfang": "Zwei Seiten zusammen sind der halbe Umfang. Probier alle Paare.",
    "max_flaeche": "Zwei Seiten zusammen sind der halbe Umfang. Probier Paare und rechne die Fläche.",
    "min_umfang": "Finde alle Rechtecke mit dieser Fläche und rechne bei jedem den Umfang.",
}
_RAETSEL_FLAECHEN = {3: (8, 12, 16, 18), 4: (12, 16, 18, 20, 24), 5: (18, 20, 24, 30),
                     6: (24, 30, 36), 7: (24, 30, 36), 8: (24, 30, 36)}
_RAETSEL_UMFAENGE = {3: (10, 12, 14), 4: (12, 14, 16), 5: (14, 16, 18), 6: (16, 18, 20),
                     7: (18, 20, 22), 8: (20, 22, 24)}


def _erzeuge_raetsel(rng, stage, index):
    if index == 4:
        typ = rng.choice(("rechtecke_flaeche", "rechtecke_umfang"))
    else:
        typ = rng.choice(("max_flaeche", "min_umfang"))
    zahl = rng.choice(_RAETSEL_FLAECHEN[stage] if typ in ("rechtecke_flaeche", "min_umfang")
                      else _RAETSEL_UMFAENGE[stage])
    antwort, term = raetsel_loesung(typ, zahl)
    kern = {"art": "gitterfigur", "modus": "raetsel", "typ": typ, "zahl": zahl,
            "anzahl": antwort, "stufe": stage}
    return {"type": "zahl", "q": _RAETSEL_Q[typ].format(z=zahl), "a": antwort,
            "check": {"expr": term}, "hint": _RAETSEL_HINT[typ], "papier": True}, kern


def pruefe_gitterfigur(kern):
    """Figur: Fläche/Umfang aus den Zellen nachzählen (und Löcher, Zusammenhang,
    halbe Kästchen prüfen). Rätsel: alle Rechtecke noch einmal durchprobieren."""
    try:
        modus, anzahl = kern["modus"], kern["anzahl"]
    except (KeyError, TypeError):
        return False, "Kern hat kein gültiges Format"
    if not _ist_int(anzahl):
        return False, f"anzahl {anzahl!r} ist keine ganze Zahl"
    if modus == "raetsel":
        typ, zahl = kern.get("typ"), kern.get("zahl")
        if typ not in _RAETSEL_Q or not _ist_int(zahl):
            return False, "Rätselart oder Zahl ungültig"
        if not (2 <= zahl <= 36) or (typ in ("rechtecke_umfang", "max_flaeche")
                                      and (zahl % 2 or zahl < 6 or zahl > 30)):
            return False, f"Zahl {zahl} liegt außerhalb des erlaubten Bereichs"
        if typ in ("rechtecke_flaeche", "min_umfang") and zahl < 4:
            return False, "Fläche zu klein für ein Rätsel"
        erwartet, _term = raetsel_loesung(typ, zahl)
        if anzahl != erwartet:
            return False, f"durchprobiert ergibt sich {erwartet}, angegeben ist {anzahl}"
        return True, "Rätsel stimmt: alle Rechtecke durchprobiert"
    if modus != "figur":
        return False, f"Modus {modus!r} unbekannt"
    try:
        frage = kern["frage"]
        zellen = {(int(r), int(c)) for r, c in kern["zellen"]}
        halbe = [((int(z[0]), int(z[1])), e) for z, e in kern["halbe"]]
    except (KeyError, TypeError, ValueError, IndexError):
        return False, "Kern hat kein gültiges Zellenformat"
    if len(zellen) != len(kern["zellen"]):
        return False, "ein Kästchen kommt doppelt vor"
    grund = _figur_pruefen(zellen, halbe)
    if grund:
        return False, grund
    if frage == "flaeche":
        erwartet = figur_flaeche(zellen, halbe)
    elif frage == "umfang":
        if halbe:
            return False, "Umfang mit halben Kästchen ist nicht ganzzahlig abzählbar"
        erwartet = figur_umfang(zellen)
    else:
        return False, f"Frage {frage!r} unbekannt"
    if anzahl != erwartet:
        return False, f"nachgezählt ergibt sich {erwartet}, angegeben ist {anzahl}"
    return True, f"{frage} nachgezählt: {erwartet}"


# ================================================================ 4. quader
# Länge L läuft nach rechts (Spalten), Breite B in die Tiefe (Zeilen), Höhe H
# nach oben. Die Würfel stehen als Säulen vom Boden (Schwerkraft); jede Säule
# ist im Bild sichtbar, also lässt sich die Zahl der vorhandenen Würfel
# eindeutig zählen. Gesucht: L·B·H minus vorhandene.

def _quader_masse(stage, index):
    """(Länge, Breite, Höhe) – wächst mit Stufe und Index bis 4x3x3."""
    plan = {3: [(2, 2, 2)] * 3 + [(3, 2, 2)] * 3,
            4: [(2, 2, 2)] + [(3, 2, 2)] * 3 + [(3, 3, 2)] * 2,
            5: [(3, 2, 2)] + [(3, 3, 2)] * 3 + [(3, 3, 3)] * 2,
            6: [(3, 3, 2)] + [(3, 3, 3)] * 2 + [(4, 3, 2)] * 2 + [(4, 3, 3)],
            7: [(3, 3, 3)] + [(4, 3, 2)] + [(4, 3, 3)] * 4,
            8: [(4, 3, 2)] + [(4, 3, 3)] * 5}[stage]
    return plan[index]


_QUADER_Q = ["Wie viele Würfel fehlen noch bis zum vollen Quader?",
             "Der gestrichelte Quader soll ganz voll werden. Wie viele Würfel fehlen?",
             "Wie viele Würfel musst du noch dazulegen, bis der Quader voll ist?"]


def _erzeuge_quader(rng, stage, index):
    laenge, breite, hoehe = _quader_masse(stage, index)
    hoehen = _baue_sichtbar(rng, breite, laenge, hoehe)
    da = sum(map(sum, hoehen))
    fehlt = laenge * breite * hoehe - da
    if da < 2 or fehlt < 2:
        raise _Neu()
    farbe = rng.choice(PALETTE)
    kern = {"art": "quader", "laenge": laenge, "breite": breite, "hoehe": hoehe,
            "hoehen": hoehen, "anzahl": fehlt, "stufe": stage}
    return {"type": "bildzahl", "q": _vorlage(_QUADER_Q, index),
            "svg": _render_iso(hoehen, farbe, kasten_hoehe=hoehe), "a": fehlt,
            "kern": kern, "hint": "Rechne: Wie viele Würfel passen in den ganzen Quader? "
                                  "Zieh ab, wie viele schon da sind."}, kern


def pruefe_quader(kern):
    """Zählt die vorhandenen Würfel aus den Säulenhöhen, rechnet L·B·H − da
    nach und verlangt, dass jede Säule im Bild sichtbar ist."""
    try:
        laenge, breite, hoehe = kern["laenge"], kern["breite"], kern["hoehe"]
        hoehen, anzahl = kern["hoehen"], kern["anzahl"]
    except (KeyError, TypeError):
        return False, "Kern hat kein gültiges Format"
    if not all(_ist_int(x) for x in (laenge, breite, hoehe, anzahl)):
        return False, "Maße und Anzahl müssen ganze Zahlen sein"
    if not (2 <= laenge <= 4 and 2 <= breite <= 4 and 2 <= hoehe <= 3) or laenge * breite * hoehe > 36:
        return False, f"Quader {laenge}x{breite}x{hoehe} liegt außerhalb des erlaubten Bereichs"
    grund = _hoehen_gueltig(hoehen, 2, 4, hoehe)
    if grund:
        return False, grund
    if len(hoehen) != breite or len(hoehen[0]) != laenge:
        return False, f"Höhenkarte {len(hoehen)}x{len(hoehen[0])} passt nicht zu Breite {breite} x Länge {laenge}"
    da = sum(map(sum, hoehen))
    if da < 1:
        return False, "kein einziger Würfel im Quader"
    if not _alle_saeulen_sichtbar(hoehen):
        return False, "mindestens eine Säule ist im Bild nicht sichtbar – Würfel nicht eindeutig zählbar"
    fehlt = laenge * breite * hoehe - da
    if fehlt < 1:
        return False, "der Quader ist schon voll – es fehlt nichts"
    if anzahl != fehlt:
        return False, f"nachgerechnet fehlen {fehlt} Würfel, angegeben ist {anzahl}"
    return True, f"{laenge}*{breite}*{hoehe} - {da} = {fehlt}"


# ================================================================== 5. karte
# Karte N x N (Zeile r von oben, Spalte c von links). Zeichen sind einfache
# SVG-Formen; ein Anker gibt es genau einmal (Startpunkt).

KARTE_ZEICHEN = ("anker", "palme", "felsen", "schatz", "muschel", "flagge")
_RICHTUNG = {"rechts": (0, 1), "links": (0, -1), "oben": (-1, 0), "unten": (1, 0)}


def _karte_symbol(name, x, y, u):
    """Zeichen in der Karten-Zelle mit linker oberer Ecke (x,y), Kantenlänge u."""
    def p(fx, fy):
        return f"{GK._fmt(x + fx * u)},{GK._fmt(y + fy * u)}"
    k = f'stroke="{KONTUR}" stroke-width="1.5" stroke-linejoin="round"'
    if name == "anker":
        s = f'stroke="{HELL}" stroke-width="3" stroke-linecap="round" fill="none"'
        return (f'<circle cx="{GK._fmt(x + .5 * u)}" cy="{GK._fmt(y + .2 * u)}" r="{GK._fmt(.09 * u)}" {s}/>'
                f'<path d="M{p(.5, .29)} L{p(.5, .8)} M{p(.33, .4)} L{p(.67, .4)} '
                f'M{p(.2, .6)} Q{p(.5, 1.0)} {p(.8, .6)}" {s}/>')
    if name == "palme":
        stamm = f'<polygon points="{p(.45, .85)} {p(.55, .85)} {p(.58, .45)} {p(.48, .45)}" fill="{PALETTE[1]}" {k}/>'
        blatt = "".join(
            f'<ellipse cx="{GK._fmt(x + .53 * u + dx * u)}" cy="{GK._fmt(y + .36 * u + dy * u)}" '
            f'rx="{GK._fmt(.2 * u)}" ry="{GK._fmt(.075 * u)}" fill="{PALETTE[2]}" {k} '
            f'transform="rotate({w} {GK._fmt(x + .53 * u + dx * u)} {GK._fmt(y + .36 * u + dy * u)})"/>'
            for dx, dy, w in ((-.14, .0, -25), (.14, .0, 25), (0, -.09, 0), (-.1, .08, 30), (.1, .08, -30)))
        return stamm + blatt
    if name == "felsen":
        return (f'<polygon points="{p(.16, .8)} {p(.1, .55)} {p(.3, .3)} {p(.55, .24)} '
                f'{p(.82, .42)} {p(.9, .8)}" fill="{HELL}" fill-opacity="0.6" {k}/>')
    if name == "schatz":
        return (f'<rect x="{GK._fmt(x + .2 * u)}" y="{GK._fmt(y + .46 * u)}" width="{GK._fmt(.6 * u)}" '
                f'height="{GK._fmt(.32 * u)}" fill="{PALETTE[1]}" {k}/>'
                f'<path d="M{p(.2, .46)} Q{p(.5, .12)} {p(.8, .46)} Z" fill="{PALETTE[1]}" fill-opacity="0.75" {k}/>'
                f'<rect x="{GK._fmt(x + .45 * u)}" y="{GK._fmt(y + .5 * u)}" width="{GK._fmt(.1 * u)}" '
                f'height="{GK._fmt(.14 * u)}" fill="{HELL}" {k}/>')
    if name == "muschel":
        pts = [(.5, .82), (.14, .5), (.26, .3), (.5, .22), (.74, .3), (.86, .5)]
        fach = " ".join(p(a, b) for a, b in pts)
        rippen = "".join(f'<line x1="{GK._fmt(x + .5 * u)}" y1="{GK._fmt(y + .82 * u)}" '
                         f'x2="{GK._fmt(x + a * u)}" y2="{GK._fmt(y + b * u)}" stroke="{KONTUR}" '
                         f'stroke-width="1.2"/>' for a, b in pts[1:-1])
        return f'<polygon points="{fach}" fill="{PALETTE[0]}" {k}/>' + rippen
    return (f'<line x1="{GK._fmt(x + .35 * u)}" y1="{GK._fmt(y + .85 * u)}" x2="{GK._fmt(x + .35 * u)}" '
            f'y2="{GK._fmt(y + .18 * u)}" stroke="{HELL}" stroke-width="3" stroke-linecap="round"/>'
            f'<polygon points="{p(.35, .2)} {p(.82, .38)} {p(.35, .56)}" fill="{PALETTE[1]}" {k}/>')


def _render_karte(n, symbole, unit=44):
    """symbole: {(r,c): name}. Rasterkarte ohne Beschriftung."""
    teile = [f'<rect x="0" y="0" width="{n * unit}" height="{n * unit}" fill="{HELL}" '
             f'fill-opacity="0.07" stroke="{HELL}" stroke-width="2"/>']
    for i in range(1, n):
        teile.append(f'<line x1="0" y1="{i * unit}" x2="{n * unit}" y2="{i * unit}" '
                     f'stroke="{RASTER}" stroke-width="1"/>')
        teile.append(f'<line x1="{i * unit}" y1="0" x2="{i * unit}" y2="{n * unit}" '
                     f'stroke="{RASTER}" stroke-width="1"/>')
    for (r, c), name in sorted(symbole.items()):
        teile.append(_karte_symbol(name, c * unit, r * unit, unit))
    return GK._svg_wrap(n * unit, n * unit, unit // 2, "".join(teile))


def _render_karte_zeichen(name, u=64):
    feld = (f'<rect x="0" y="0" width="{u}" height="{u}" fill="{HELL}" fill-opacity="0.07" '
            f'stroke="{HELL}" stroke-width="2"/>')
    return GK._svg_wrap(u, u, u // 4, feld + _karte_symbol(name, 0, 0, u))


def _karte_groesse(stage):
    return {3: 5, 4: 5, 5: 6, 6: 7, 7: 8, 8: 8}[stage]


def _karte_modus(stage, index):
    if stage < 5:
        return "schritte" if index < 3 else "weg"
    return ("schritte", "schritte", "weg", "weg", "massstab", "massstab")[index]


def kuerzester_weg(n, felsen, start, ziel):
    """Breitensuche, nur waagrecht/senkrecht, Felsen sperren. Länge in
    Schritten oder None, wenn das Ziel unerreichbar ist."""
    felsen = set(map(tuple, felsen))
    dist = {tuple(start): 0}
    schlange = [tuple(start)]
    for z in schlange:
        if z == tuple(ziel):
            return dist[z]
        for dr, dc in _RICHTUNG.values():
            nb = (z[0] + dr, z[1] + dc)
            if 0 <= nb[0] < n and 0 <= nb[1] < n and nb not in felsen and nb not in dist:
                dist[nb] = dist[z] + 1
                schlange.append(nb)
    return None


_SCHRITTE_KURZ = {"rechts": "rechts", "links": "links", "oben": "hoch", "unten": "runter"}


def _schritte_text(schritte):
    if len(schritte) == 2:
        (r1, n1), (r2, n2) = schritte
        return f"Vom Anker {n1} nach {r1} und {n2} nach {r2}. Was liegt dort?"
    teile = ", ".join(f"{n} {_SCHRITTE_KURZ[r]}" for r, n in schritte)
    return f"Vom Anker: {teile}. Was liegt dort?"


def _gehe(start, schritte):
    """Folge der Eckpunkte des Weges (Start eingeschlossen)."""
    pos = [tuple(start)]
    for richtung, laenge in schritte:
        dr, dc = _RICHTUNG[richtung]
        pos.append((pos[-1][0] + dr * laenge, pos[-1][1] + dc * laenge))
    return pos


def _karte_schritte(rng, stage, index):
    n = _karte_groesse(stage)
    anzahl = min(4, {3: 2, 4: 2, 5: 2, 6: 3, 7: 3, 8: 4}[stage] + (1 if index >= 3 and stage >= 4 else 0))
    anker = (rng.randrange(n), rng.randrange(n))
    achse = rng.randrange(2)
    schritte, pos = [], anker
    for _ in range(anzahl):
        if achse == 0:
            mgl = [("rechts", k) for k in range(1, n - pos[1])] + [("links", k) for k in range(1, pos[1] + 1)]
        else:
            mgl = [("unten", k) for k in range(1, n - pos[0])] + [("oben", k) for k in range(1, pos[0] + 1)]
        if not mgl:
            raise _Neu()
        richtung, laenge = rng.choice(mgl)
        schritte.append((richtung, laenge))
        pos = _gehe(pos, [(richtung, laenge)])[-1]
        achse = 1 - achse
    ziel = pos
    if ziel == anker or any(p == anker for p in _gehe(anker, schritte)[1:]):
        raise _Neu()
    # Typische Fehlgriffe: letzten Schritt weglassen / umkehren, links-rechts bzw. oben-unten
    # vertauscht, Schritte der beiden Achsen vertauscht, um ein Feld daneben.
    umgekehrt = {"rechts": "links", "links": "rechts", "oben": "unten", "unten": "oben"}
    fehlerwege = [schritte[:-1], schritte[:-1] + [(umgekehrt[schritte[-1][0]], schritte[-1][1])],
                  [(umgekehrt[r] if r in ("oben", "unten") else r, k) for r, k in schritte],
                  [(umgekehrt[r] if r in ("rechts", "links") else r, k) for r, k in schritte]]
    fehlerzellen = []
    for weg in fehlerwege:
        z = _gehe(anker, weg)[-1]
        if 0 <= z[0] < n and 0 <= z[1] < n and z not in (anker, ziel) and z not in fehlerzellen:
            fehlerzellen.append(z)
    daneben = [(ziel[0] + dr, ziel[1] + dc) for dr, dc in _RICHTUNG.values()]
    rng.shuffle(daneben)
    for z in daneben:
        if 0 <= z[0] < n and 0 <= z[1] < n and z not in (anker,) and z != ziel and z not in fehlerzellen:
            fehlerzellen.append(z)
    rng.shuffle(fehlerzellen)
    fehlerzellen = fehlerzellen[:3]
    ziel_name = rng.choice(KARTE_ZEICHEN[1:])
    andere = [t for t in KARTE_ZEICHEN[1:] if t != ziel_name]
    rng.shuffle(andere)
    symbole = {anker: "anker", ziel: ziel_name}
    for z, t in zip(fehlerzellen, andere):
        symbole[z] = t
    ablenker = [symbole[z] for z in fehlerzellen] + [t for t in andere if t not in symbole.values()]
    ablenker = ablenker[:3]
    if len(ablenker) < 3:
        raise _Neu()
    for r in range(n):
        for c in range(n):
            if (r, c) not in symbole and rng.random() < 0.28:
                symbole[(r, c)] = rng.choice(KARTE_ZEICHEN[1:])
    optionen, idx = _mische(rng, ziel_name, ablenker)
    kern = {"art": "karte", "modus": "schritte", "n": n, "anker": list(anker),
            "zeichen": [[r, c, name] for (r, c), name in sorted(symbole.items())],
            "schritte": [[r, k] for r, k in schritte], "optionen": optionen,
            "richtig": idx, "stufe": stage}
    return {"type": "bildwahl", "q": _schritte_text(schritte), "svg": _render_karte(n, symbole),
            "optionen_svg": [_render_karte_zeichen(o) for o in optionen], "richtig": idx,
            "kern": kern, "hint": "Geh Schritt für Schritt mit dem Finger über die Karte."}, kern


_WEG_Q = ["Wie viele Schritte sind es vom Anker zum Schatz? Nicht schräg, Felsen umgehen.",
          "Kürzester Weg vom Anker zum Schatz: Wie viele Schritte? Nicht schräg, nicht über Felsen."]
_MASSSTAB_Q = "Kürzester Weg ohne Felsen, nicht schräg. 1 Kästchen = {m} m. Wie viele Meter?"


def _karte_weg(rng, stage, index, modus):
    n = _karte_groesse(stage)
    felsenzahl = {3: 3, 4: 4, 5: 5, 6: 7, 7: 9, 8: 11}[stage] + index // 2
    zellen = [(r, c) for r in range(n) for c in range(n)]
    anker, schatz = rng.sample(zellen, 2)
    manh = abs(anker[0] - schatz[0]) + abs(anker[1] - schatz[1])
    if manh < max(4, n - 1):
        raise _Neu()
    frei = [z for z in zellen if z not in (anker, schatz)]
    felsen = sorted(rng.sample(frei, felsenzahl))
    weg = kuerzester_weg(n, felsen, anker, schatz)
    if weg is None or weg > (12 if modus == "massstab" else 16):
        raise _Neu()
    if stage >= 5 and weg == manh:
        raise _Neu()                   # ab Stufe 5 braucht es einen echten Umweg
    symbole = {anker: "anker", schatz: "schatz"}
    symbole.update({f: "felsen" for f in felsen})
    kern = {"art": "karte", "modus": modus, "n": n, "anker": list(anker), "schatz": list(schatz),
            "felsen": [list(f) for f in felsen], "anzahl": weg, "stufe": stage}
    if modus == "massstab":
        meter = rng.choice({5: (10,), 6: (10, 20), 7: (10, 20, 5), 8: (10, 20, 5)}[stage])
        kern["meter"] = meter
        kern["anzahl"] = weg * meter
        q, hint = _MASSSTAB_Q.format(m=meter), "Zähl erst die Kästchen, dann rechne mal so viele Meter."
    else:
        q, hint = _vorlage(_WEG_Q, index), "Zähl die Schritte um die Felsen herum."
    aufgabe = {"type": "bildzahl", "q": q, "svg": _render_karte(n, symbole), "a": kern["anzahl"],
               "kern": kern, "hint": hint}
    if modus == "massstab":
        aufgabe["papier"] = True
    return aufgabe, kern


def _erzeuge_karte(rng, stage, index):
    modus = _karte_modus(stage, index)
    if modus == "schritte":
        return _karte_schritte(rng, stage, index)
    return _karte_weg(rng, stage, index, modus)


def _zelle(z, n):
    try:
        r, c = z
    except (TypeError, ValueError):
        return None
    return (r, c) if _ist_int(r) and _ist_int(c) and 0 <= r < n and 0 <= c < n else None


def pruefe_karte(kern):
    """schritte: geht die Schritte von Anker aus nach und liest das Zeichen am
    Ziel ab. weg/massstab: Breitensuche um die Felsen, ggf. mal Maßstab."""
    try:
        modus, n = kern["modus"], kern["n"]
        anker = kern["anker"]
    except (KeyError, TypeError):
        return False, "Kern hat kein gültiges Format"
    if not _ist_int(n) or not (5 <= n <= 8):
        return False, f"Kartengröße {n!r} liegt außerhalb von 5..8"
    anker = _zelle(anker, n)
    if anker is None:
        return False, "Anker liegt nicht auf der Karte"
    if modus == "schritte":
        try:
            zeichen, schritte, optionen, richtig = (kern["zeichen"], kern["schritte"],
                                                    kern["optionen"], kern["richtig"])
        except KeyError:
            return False, "Kern hat kein gültiges Format"
        symbole = {}
        for eintrag in zeichen:
            try:
                r, c, name = eintrag
            except (TypeError, ValueError):
                return False, "Zeicheneintrag ist kein [Zeile, Spalte, Name]"
            z = _zelle((r, c), n)
            if z is None or name not in KARTE_ZEICHEN or z in symbole:
                return False, "Zeichen liegt außerhalb, doppelt auf einem Feld oder ist unbekannt"
            symbole[z] = name
        if [z for z, nm in symbole.items() if nm == "anker"] != [anker]:
            return False, "es muss genau einen Anker geben, und zwar am Startfeld"
        if not isinstance(schritte, list) or not (2 <= len(schritte) <= 4):
            return False, "2 bis 4 Schritte erwartet"
        pos = anker
        for s in schritte:
            try:
                richtung, laenge = s
            except (TypeError, ValueError):
                return False, "Schritt ist kein [Richtung, Länge]"
            if richtung not in _RICHTUNG or not _ist_int(laenge) or not (1 <= laenge <= n - 1):
                return False, f"Schritt {s!r} ist ungültig"
            pos = (pos[0] + _RICHTUNG[richtung][0] * laenge, pos[1] + _RICHTUNG[richtung][1] * laenge)
            if _zelle(pos, n) is None:
                return False, "der Weg führt von der Karte hinunter"
        if pos == anker:
            return False, "der Weg endet wieder beim Anker"
        if pos not in symbole:
            return False, "am Zielfeld liegt nichts"
        if not isinstance(optionen, list) or len(optionen) != 4 or len(set(optionen)) != 4 \
                or any(o not in KARTE_ZEICHEN for o in optionen):
            return False, "die Optionen sind keine 4 verschiedenen Zeichen"
        if not _ist_int(richtig) or not (0 <= richtig < 4):
            return False, f"'richtig'={richtig!r} ist kein gültiger Options-Index"
        if optionen[richtig] != symbole[pos]:
            return False, f"am Ziel liegt {symbole[pos]!r}, markiert ist {optionen[richtig]!r}"
        return True, f"Ziel nachgegangen: dort liegt {symbole[pos]}"
    if modus in ("weg", "massstab"):
        try:
            schatz, felsen, anzahl = _zelle(kern["schatz"], n), kern["felsen"], kern["anzahl"]
        except KeyError:
            return False, "Kern hat kein gültiges Format"
        felsenzellen = [_zelle(f, n) for f in felsen] if isinstance(felsen, list) else [None]
        if schatz is None or None in felsenzellen:
            return False, "Schatz oder Fels liegt nicht auf der Karte"
        if len(set(felsenzellen)) != len(felsenzellen) or anker == schatz \
                or anker in felsenzellen or schatz in felsenzellen:
            return False, "Felder überschneiden sich (Anker, Schatz, Felsen)"
        weg = kuerzester_weg(n, felsenzellen, anker, schatz)
        if weg is None:
            return False, "der Schatz ist nicht erreichbar"
        if modus == "massstab":
            meter = kern.get("meter")
            if not _ist_int(meter) or meter < 1:
                return False, "Maßstab fehlt"
            weg *= meter
        if anzahl != weg:
            return False, f"nachgerechnet ergibt sich {weg}, angegeben ist {anzahl}"
        return True, f"kürzester Weg nachgerechnet: {weg}"
    return False, f"Modus {modus!r} unbekannt"


# ======================================================== öffentliche Fabrik

_ERZEUGER = {"geo_ansicht": _erzeuge_ansicht, "geo_netzfalten": _erzeuge_netz,
             "geo_quader": _erzeuge_quader, "geo_karte": _erzeuge_karte}


def _baue(skill, stage, index, seed):
    """Wie baue_aufgabe, liefert aber zusätzlich den Kern (auch für die
    zahl-Rätsel, die in der Aufgabe selbst keinen Kern tragen)."""
    if skill not in SKILLS:
        raise ValueError(f"unbekannte Fertigkeit {skill!r}")
    if not (_ist_int(stage) and 3 <= stage <= 8):
        raise ValueError(f"Stufe {stage!r} außerhalb 3..8")
    if not (_ist_int(index) and 0 <= index <= 5):
        raise ValueError(f"Index {index!r} außerhalb 0..5")
    if skill == "geo_flaeche_umfang":
        erz = _erzeuge_gitterfigur if index < 4 else _erzeuge_raetsel
    else:
        erz = _ERZEUGER[skill]
    return _wiederhole(erz, skill, stage, index, seed)


def baue_aufgabe(skill, stage, index, seed):
    """Fertige Aufgabe im Schema (bildwahl | bildzahl | zahl). index 0..5 ist
    die Position im 6er-Paket, die Denktiefe steigt mit dem Index. Gleiche
    Eingabe, gleiche Aufgabe.

    Auch die zahl-Rätsel (geo_flaeche_umfang, Index 4–5) tragen ihren Kern in
    der Aufgabe: check.expr allein ist dort nur die Zahl selbst und beweist
    nichts — erst pruefe_gitterfigur rechnet das Durchprobieren nach, und dafür
    muss validate.py den Kern sehen."""
    aufgabe, kern = _baue(skill, stage, index, seed)
    if aufgabe.get("type") == "zahl" and "kern" not in aufgabe and kern:
        aufgabe = dict(aufgabe, kern=kern)
    return aufgabe


PRUEFER = {"ansicht": pruefe_ansicht, "netzfalten": pruefe_netzfalten,
           "gitterfigur": pruefe_gitterfigur, "quader": pruefe_quader, "karte": pruefe_karte}
