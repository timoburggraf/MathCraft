# -*- coding: utf-8 -*-
"""Der deterministische Kern für Punktmuster und Merkbild (ZIELE-V3.md, G2 und G4).

Zwei Aufgabenfamilien, beide nach dem Prinzip des Projekts "erst die Wahrheit,
dann das Bild" (wie grafik_kern.py und muster_kern.py): Ein Sprachmodell kann
weder Punkte zuverlässig zählen noch garantieren, dass unter vier Bildern
genau eines gleich dem Original ist. Hier entsteht zuerst die Konstruktion
(Punktkoordinaten), das SVG ist nur ihr Abdruck.

  1. punktmuster – Aufgabentyp `bildzahl`, kern.art "punktmuster". Das Bild
     zeigt die ersten drei Bilder einer Punktfolge mit sichtbarer Struktur
     (Streifen, L-Form, Rahmen, Quadrat, Rechteck, Dreieck); gefragt ist ein
     weit entferntes Bild ("Wie viele Punkte hat Bild 10?"). Weiterzählen
     hilft kaum, die Struktur zu erkennen sehr. Der Prüfer rechnet drei
     Wege nach: die Punkte der gezeigten Bilder aus der Konstruktion, das
     gefragte Bild aus der Konstruktion und das gefragte Bild aus der
     Formel — alle müssen zur selben Regel passen.

  2. merkbild – Aufgabentyp `bildwahl` mit "merken_ms", kern.art "merkbild".
     Ein Punktraster mit strukturierter Anordnung (Linien, Symmetrie,
     Treppe) wird kurz gezeigt und ausgeblendet; danach wählt das Kind unter
     vier Rastern das gleiche. Die Struktur hilft beim Merken — das ist der
     Sinn der Aufgabe (Käpnick: "Speichern mit Hilfe erkannter Strukturen").
     Ablenker entstehen durch Spiegeln bzw. Verschieben eines einzigen
     Punktes. Der Prüfer rechnet ohne SVG nach: genau eine Option ist
     gleich dem Original.

Alle SVGs: keine Breiten-/Höhenangabe am Wurzelelement, kein Text (Ziffern
sind aus Strichen gezeichnet), Farben nur aus grafik_kern.PALETTE, KONTUR und
RASTER. Seeds nur über zlib.crc32, Zufall nur über random.Random(seed): kein
hash(), kein eval(), kein Sprachmodell.
"""
import itertools
import random
import zlib

from grafik_kern import PALETTE, KONTUR, RASTER, _svg_wrap

LEER_FARBE = PALETTE[3]    # helles Grau für Beschriftungsstriche (PALETTE[3])
DOT_FARBEN = PALETTE[:3]   # die drei kräftigen Farben für Punkte


def _fmt(x):
    """Koordinate möglichst kompakt (ganzzahlig, wenn möglich)."""
    r = round(x, 2)
    return str(int(r)) if r == int(r) else f"{r:g}"


def _rng(*teile):
    """Zufall aus Text, nie aus hash() (das ist je Lauf anders)."""
    return random.Random(zlib.crc32("|".join(str(t) for t in teile).encode("utf-8")))


def _ganz(x):
    return isinstance(x, int) and not isinstance(x, bool)


# ================================================================ Punktmuster
# Koordinaten (x, y): x nach rechts, y nach OBEN, (0, 0) ist links unten. So
# liegt Bild n immer auf dem Boden, und wachsende Bilder wachsen sichtbar nach
# oben und rechts.

TYPEN = ("linear", "lform", "rahmen", "quadrat", "rechteck", "dreieck")


def formel(typ, param, n):
    """Punktezahl von Bild n laut Regel. Die Formel ist die Regel, die das
    Kind finden soll; die Konstruktion unten ist ihr unabhängiger Gegenpart."""
    if typ == "linear":
        return param * n                  # param Reihen mit je n Punkten
    if typ == "lform":
        return 2 * n + 1                  # Ecke + n nach oben + n nach rechts
    if typ == "rahmen":
        return 4 * n                      # Rand eines (n+1)x(n+1)-Quadrats
    if typ == "quadrat":
        return n * n
    if typ == "rechteck":
        return n * (n + 1)
    if typ == "dreieck":
        return n * (n + 1) // 2           # Treppe: n + (n-1) + … + 1
    raise ValueError(f"unbekannter Typ {typ!r}")


def punkte_von(typ, param, n):
    """Die Punkte von Bild n, Stück für Stück gebaut (nicht aus der Formel)."""
    if typ == "linear":
        return sorted((x, y) for x in range(n) for y in range(param))
    if typ == "lform":
        return sorted([(0, y) for y in range(n + 1)] + [(x, 0) for x in range(1, n + 1)])
    if typ == "rahmen":
        s = n + 1
        return sorted((x, y) for x in range(s) for y in range(s)
                      if x in (0, s - 1) or y in (0, s - 1))
    if typ == "quadrat":
        return sorted((x, y) for x in range(n) for y in range(n))
    if typ == "rechteck":
        return sorted((x, y) for x in range(n + 1) for y in range(n))
    if typ == "dreieck":
        return sorted((x, y) for y in range(n) for x in range(n - y))
    raise ValueError(f"unbekannter Typ {typ!r}")


def _akzent(typ, param, n):
    """Welche Punkte von Bild n sticht die Farbe heraus? Das, was die Struktur
    verrät: bei L-Form die Ecke, sonst der Zuwachs gegenüber Bild n−1 (Spalte
    beim Streifen, Winkelstück bei Quadrat und Rechteck, Schrägzeile beim
    Dreieck). Beim Rahmen gibt es keinen Zuwachs im selben Koordinatenraum
    (der Rand wandert nach außen) — er bleibt einfarbig."""
    if typ == "lform":
        return {(0, 0)}
    if n < 2:
        return set()
    p = punkte_von(typ, param, n)
    if typ == "linear":
        return {q for q in p if q[0] == n - 1}
    if typ == "quadrat":
        return {q for q in p if q[0] == n - 1 or q[1] == n - 1}
    if typ == "rechteck":
        return {q for q in p if q[0] == n or q[1] == n - 1}
    if typ == "dreieck":
        return {q for q in p if q[0] + q[1] == n - 1}
    return set()


def _spiegeln(punkte):
    """Spiegelt ein Bild links↔rechts an seiner eigenen Breite."""
    breite = max(x for x, _ in punkte) + 1
    return sorted((breite - 1 - x, y) for x, y in punkte)


def _gezeigt(typ, param, spiegel, n):
    """Punkte von Bild n, wie sie gezeigt werden (evtl. gespiegelt)."""
    p = punkte_von(typ, param, n)
    return _spiegeln(p) if spiegel else p


# ------------------------------------------------------------- Ziffern aus Strichen
# Siebensegment-Ziffern 1..3 als Linien — kein <text>, damit das Bild in jeder
# Schrift und beim Vorlesen gleich bleibt (wie in grafik_kern/muster_kern).
_SEGMENTE = {   # a oben, b oben rechts, c unten rechts, d unten, e unten links, f oben links, g Mitte
    1: "bc", 2: "abged", 3: "abgcd",
}


def _ziffer_svg(ziffer, x0, y0, b=10, h=18):
    """Ziffer in einem b×h großen Kasten mit linker oberer Ecke (x0, y0)."""
    m = h / 2
    linien = {"a": (0, 0, b, 0), "b": (b, 0, b, m), "c": (b, m, b, h), "d": (0, h, b, h),
              "e": (0, m, 0, h), "f": (0, 0, 0, m), "g": (0, m, b, m)}
    teile = []
    for s in _SEGMENTE[ziffer]:
        xa, ya, xb, yb = linien[s]
        teile.append(f'<line x1="{_fmt(x0 + xa)}" y1="{_fmt(y0 + ya)}" x2="{_fmt(x0 + xb)}" '
                     f'y2="{_fmt(y0 + yb)}" stroke="{LEER_FARBE}" stroke-width="3" '
                     f'stroke-linecap="round"/>')
    return "".join(teile)


P_ZELLE = 26      # Rasterweite der Punktbilder
P_RADIUS = 10
P_LUECKE = 34     # Abstand zwischen den Bildern
P_RAND = 14


def _render_punktmuster(typ, param, spiegel, farbe, akzent_farbe):
    """Bild 1, 2, 3 nebeneinander, am Boden ausgerichtet, je eine Ziffer darunter."""
    bilder = [_gezeigt(typ, param, spiegel, n) for n in (1, 2, 3)]
    hoehe = max(max(y for _, y in b) + 1 for b in bilder)
    teile, x = [], 0
    for n, b in zip((1, 2, 3), bilder):
        breite = max(px for px, _ in b) + 1
        # Akzent im Koordinatenraum der Konstruktion berechnen, dann gleich
        # mitspiegeln wie die Punkte selbst.
        ak = _akzent(typ, param, n)
        if spiegel:
            ak = {(breite - 1 - px, py) for px, py in ak}
        for px, py in b:
            cx = x + (px + 0.5) * P_ZELLE
            cy = (hoehe - 1 - py + 0.5) * P_ZELLE
            f = akzent_farbe if (px, py) in ak else farbe
            teile.append(f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{P_RADIUS}" fill="{f}" '
                         f'stroke="{KONTUR}" stroke-width="1.5"/>')
        teile.append(_ziffer_svg(n, x + breite * P_ZELLE / 2 - 5, hoehe * P_ZELLE + 14))
        x += breite * P_ZELLE + P_LUECKE
    gesamt_b = x - P_LUECKE
    gesamt_h = hoehe * P_ZELLE + 14 + 18
    w, h = gesamt_b + 2 * P_RAND, gesamt_h + 2 * P_RAND
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(w)} {_fmt(h)}">'
            f'<g transform="translate({P_RAND},{P_RAND})">{"".join(teile)}</g></svg>')


# Richtung je Stufe (Typ, mögliche Parameter, mögliche gefragte Bilder). Die
# Tiefe steigt mit der Weite des Sprungs und der Zahl der Teile der Struktur,
# nicht mit der Zahlengröße: Bild 10 beim Dreieck (55) ist schwerer als
# Bild 5 beim Streifen (15), obwohl die Zahlen ähnlich klein bleiben.
STUFEN_PUNKT = {
    2: ("linear", (2, 3), (4, 5)),
    3: ("linear", (3, 5), (5, 6)),
    4: ("lform", (0,), (6, 7, 8)),
    5: ("rahmen", (0,), (8, 10, 12)),
    6: ("quadrat", (0,), (7, 8, 9)),
    7: ("rechteck", (0,), (9, 10, 11)),
    8: ("dreieck", (0,), (10, 12, 15, 20)),
}

HINWEISE_PUNKT = {
    "linear": "Schau, wie viele Punkte in jedem Bild dazukommen.",
    "lform": "Zähl die Punkte oben, die Punkte rechts und die Ecke.",
    "rahmen": "Wie viele Punkte hat eine Seite? Und wie viele Seiten gibt es?",
    "quadrat": "Wie viele Reihen und wie viele Punkte pro Reihe?",
    "rechteck": "Zähl die Reihen und die Punkte pro Reihe. Was fällt dir auf?",
    "dreieck": "Zähl die Punkte in jeder Reihe. Wie ändert sich das von Reihe zu Reihe?",
}


def _punktmuster_aufgabe(stufe, typ, param, bild, rng):
    """Baut aus festem Typ/Parameter/Bild die fertige bildzahl-Aufgabe."""
    spiegel = rng.random() < 0.5
    farbe, akzent = rng.sample(DOT_FARBEN, 2)
    kern = {
        "art": "punktmuster", "typ": typ, "param": param, "spiegel": spiegel,
        "gezeigt": [1, 2, 3], "bild": bild, "anzahl": formel(typ, param, bild),
        "punkte": [[list(p) for p in _gezeigt(typ, param, spiegel, n)] for n in (1, 2, 3)],
        "stufe": stufe,
    }
    return {"type": "bildzahl", "q": f"Wie viele Punkte hat Bild {bild}?",
            "svg": _render_punktmuster(typ, param, spiegel, farbe, akzent),
            "a": kern["anzahl"], "kern": kern, "hint": HINWEISE_PUNKT[typ]}


def erzeuge_punktmuster(stufe, seed):
    """Eine Punktmuster-Aufgabe der Stufe 2..8 (Richtung: STUFEN_PUNKT)."""
    if stufe not in STUFEN_PUNKT:
        raise ValueError(f"stufe {stufe!r} liegt nicht in 2..8")
    typ, params, bilder = STUFEN_PUNKT[stufe]
    rng = _rng("punktmuster", stufe, seed)
    return _punktmuster_aufgabe(stufe, typ, rng.choice(params), rng.choice(bilder), rng)


def pruefe_punktmuster(kern):
    """Prüft rechnerisch, ohne das SVG anzusehen: (1) die gezeigten Punkte
    sind genau die Konstruktion der Bilder 1, 2, 3 und ihre Zahl stimmt mit
    der Formel; (2) das gefragte Bild, aus der Konstruktion gebaut, hat so
    viele Punkte wie die Formel und wie `anzahl`."""
    if not isinstance(kern, dict) or kern.get("art") != "punktmuster":
        return False, "kein punktmuster-Kern (art muss 'punktmuster' sein)"
    typ, param, spiegel = kern.get("typ"), kern.get("param"), kern.get("spiegel")
    bild, soll = kern.get("bild"), kern.get("anzahl")
    if typ not in TYPEN:
        return False, f"Typ {typ!r} ist unbekannt"
    if not _ganz(param) or (param not in (2, 3, 4, 5) if typ == "linear" else param != 0):
        return False, f"param={param!r} passt nicht zum Typ {typ!r}"
    if not isinstance(spiegel, bool):
        return False, f"spiegel={spiegel!r} ist kein Wahrheitswert"
    if kern.get("gezeigt") != [1, 2, 3]:
        return False, "gezeigt muss [1, 2, 3] sein"
    if not (_ganz(bild) and 4 <= bild <= 30):
        return False, f"gefragtes Bild {bild!r} liegt nicht in 4..30"
    if not _ganz(soll):
        return False, f"anzahl={soll!r} ist keine ganze Zahl"
    gezeigt = kern.get("punkte")
    if not isinstance(gezeigt, list) or len(gezeigt) != 3:
        return False, "punkte braucht genau drei Bilder"
    for n, liste in zip((1, 2, 3), gezeigt):
        try:
            ist = [tuple(p) for p in liste]
        except TypeError:
            return False, f"Bild {n}: Punkte sind keine Koordinatenpaare"
        if any(len(p) != 2 or not all(_ganz(c) for c in p) for p in ist):
            return False, f"Bild {n}: Punkte sind keine ganzzahligen Koordinatenpaare"
        if len(set(ist)) != len(ist):
            return False, f"Bild {n}: ein Punkt steht doppelt"
        erwartet = _gezeigt(typ, param, spiegel, n)
        if set(ist) != set(erwartet):
            return False, f"Bild {n}: die Punkte sind nicht die Konstruktion von {typ}"
        if len(ist) != formel(typ, param, n):
            return False, f"Bild {n}: {len(ist)} Punkte, die Formel ergibt {formel(typ, param, n)}"
    gebaut = len(punkte_von(typ, param, bild))
    if gebaut != formel(typ, param, bild):
        return False, f"Bild {bild}: Konstruktion ({gebaut}) und Formel ({formel(typ, param, bild)}) widersprechen sich"
    if soll != gebaut:
        return False, f"anzahl={soll}, Bild {bild} hat aber {gebaut} Punkte"
    if "stufe" in kern and kern["stufe"] not in STUFEN_PUNKT:
        return False, f"stufe={kern['stufe']!r} ist ungültig"
    return True, f"Bild {bild} hat {soll} Punkte; Bilder 1-3 passen zur Regel {typ}"


# Pakete für must_figur (V3: aus dem Textpaket wird ein Bildpaket). Je Stufe
# sechs Aufgaben mit steigender Tiefe: erst eine einfache Struktur mit
# mittlerem Sprung, am Ende verschachtelte Zuwachsmuster mit weitem Sprung.
# Die gefragten Bilder sind je Paket verschieden, damit die Fragetexte nicht
# gleich lauten.
PAKET_FIGUR = {
    7: [("lform", 8), ("rahmen", 10), ("quadrat", 9),
        ("rechteck", 11), ("dreieck", 12), ("rechteck", 13)],
    8: [("lform", 17), ("quadrat", 15), ("rahmen", 25),
        ("rechteck", 16), ("dreieck", 18), ("rechteck", 20)],
}


def baue_aufgabe(skill, stage, index, seed):
    """Aufgabe `index` (0..5) des Pakets must_figur@stage (stage 7 oder 8)."""
    if skill != "must_figur" or stage not in PAKET_FIGUR:
        raise ValueError(f"kein figur-Paket für {skill!r}@{stage!r}")
    plan = PAKET_FIGUR[stage]
    if not (_ganz(index) and 0 <= index < len(plan)):
        raise ValueError(f"index {index!r} liegt nicht in 0..{len(plan) - 1}")
    typ, bild = plan[index]
    rng = _rng("must_figur", stage, index, seed)
    return _punktmuster_aufgabe(stage, typ, 0, bild, rng)


def denkcheck_punktmuster(stufe, seed):
    """Denk-Check, Dimension "darstellung": Punktmuster → Zahl, Stufe 2..8."""
    return erzeuge_punktmuster(stufe, seed)


# ================================================================== Merkbild
# Zellen sind (zeile, spalte) mit (0, 0) oben links — wie auf dem Bildschirm.

# Stufe -> (Rastergröße, Punktzahl). Die Tiefe steigt mit der Zahl der Teile,
# die man sich merken muss, nicht mit der Zahlengröße.
STUFEN_MERK = {2: (3, 3), 3: (3, 4), 4: (4, 5), 5: (4, 6), 6: (5, 7), 7: (5, 8), 8: (5, 10)}
MUSTER = ("symmetrie", "linien", "treppe")
_RICHTUNGEN = ((0, 1), (1, 0), (1, 1), (1, -1))    # waagerecht, senkrecht, beide Diagonalen


def merken_ms(stufe):
    """Wie lange das Original zu sehen ist: bis Stufe 4 etwas länger."""
    return 6000 if stufe <= 4 else 5000


def _in(k, z):
    return 0 <= z[0] < k and 0 <= z[1] < k


def _bilder_von(z, k):
    """Alle Spiegelungen/Drehungen einer Zellmenge, die als Ablenker oder als
    Symmetrie-Test taugen: waagerecht, senkrecht, um 180°, an der Diagonale."""
    return {
        "waagerecht": frozenset((r, k - 1 - c) for r, c in z),
        "senkrecht": frozenset((k - 1 - r, c) for r, c in z),
        "punkt": frozenset((k - 1 - r, k - 1 - c) for r, c in z),
        "diagonale": frozenset((c, r) for r, c in z),
    }


def _symmetrisch(z, k):
    z = frozenset(z)
    return any(b == z for n, b in _bilder_von(z, k).items() if n != "diagonale") \
        or _bilder_von(z, k)["diagonale"] == z


def _muster_symmetrie(rng, k, n):
    """Zellen paarweise (bzw. auf der Achse einzeln) wählen: Spiegelachse
    senkrecht, waagerecht oder Punktspiegelung. None, wenn n nicht aufgeht."""
    art = rng.choice(("waagerecht", "senkrecht", "punkt"))
    alle = [(r, c) for r in range(k) for c in range(k)]
    rng.shuffle(alle)
    z = set()
    for zelle in alle:
        if len(z) == n:
            break
        bild = {"waagerecht": (zelle[0], k - 1 - zelle[1]),
                "senkrecht": (k - 1 - zelle[0], zelle[1]),
                "punkt": (k - 1 - zelle[0], k - 1 - zelle[1])}[art]
        neu = {zelle, bild}
        if zelle in z or len(z | neu) > n:
            continue
        z |= neu
    return frozenset(z) if len(z) == n else None


def _strecken_in(z):
    """Alle geraden Strecken (Länge >= 2), die ganz in der Zellmenge liegen."""
    z = set(z)
    ergebnis = set()
    for r, c in z:
        for dr, dc in _RICHTUNGEN:
            laenge = 1
            while (r + laenge * dr, c + laenge * dc) in z:
                laenge += 1
                if laenge >= 2:
                    ergebnis.add(frozenset((r + i * dr, c + i * dc) for i in range(laenge)))
    return ergebnis


def _ist_linienmuster(z):
    """Besteht die Zellmenge aus höchstens drei geraden Strecken?"""
    z = frozenset(z)
    strecken = list(_strecken_in(z))
    for m in (1, 2, 3):
        for kombi in itertools.combinations(strecken, m):
            if frozenset().union(*kombi) == z:
                return True
    return False


def _muster_linien(rng, k, n):
    """Ein bis drei gerade Strecken, deren Vereinigung genau n Zellen ergibt."""
    z = set()
    for _ in range(60):
        if len(z) == n:
            break
        laenge = rng.randint(2, min(k, n))
        dr, dc = rng.choice(_RICHTUNGEN)
        r0, c0 = rng.randrange(k), rng.randrange(k)
        strecke = {(r0 + i * dr, c0 + i * dc) for i in range(laenge)}
        if not all(_in(k, s) for s in strecke) or len(z | strecke) > n or strecke <= z:
            continue
        z |= strecke
    muster = frozenset(z)
    return muster if len(muster) == n and _ist_linienmuster(muster) else None


def _treppe_hoehen(n, k):
    """Alle Spaltenhöhenfolgen h, h+1, …, h+m-1 (m >= 2) mit Summe n, die ins
    k×k-Raster passen — die klassische Treppe."""
    folgen = []
    for m in range(2, k + 1):
        for h in range(1, k + 1):
            if h + m - 1 <= k and m * h + m * (m - 1) // 2 == n:
                folgen.append([h + i for i in range(m)])
    return folgen


def _treppe_zellen(hoehen, k, rng):
    """Spalte i ist hoehen[i] hoch, unten bündig; dann zufällig gespiegelt
    und/oder an der Diagonale gekippt, an eine Rasterecke geschoben."""
    z = {(k - 1 - j, i) for i, h in enumerate(hoehen) for j in range(h)}
    if rng.random() < 0.5:
        z = {(r, k - 1 - c) for r, c in z}
    if rng.random() < 0.5:
        z = {(k - 1 - r, c) for r, c in z}
    if rng.random() < 0.5:
        z = {(c, r) for r, c in z}
    return frozenset(z)


def _ist_treppe(z):
    """Prüft nach: Liest man die Menge spaltenweise (oder nach dem Kippen
    zeilenweise), sind es benachbarte, lückenlose Spalten, deren Höhen um je
    1 wachsen (oder fallen) und die alle auf derselben Seite bündig sind."""
    z = frozenset(z)
    for lage in (z, frozenset((c, r) for r, c in z)):
        spalten = {}
        for r, c in lage:
            spalten.setdefault(c, []).append(r)
        cs = sorted(spalten)
        if len(cs) < 2 or cs != list(range(cs[0], cs[-1] + 1)):
            continue
        laeufe, lueckenlos = [], True
        for c in cs:
            rs = sorted(spalten[c])
            if rs != list(range(rs[0], rs[-1] + 1)):
                lueckenlos = False
                break
            laeufe.append((rs[0], rs[-1]))
        if not lueckenlos:
            continue
        buendig = len({u for _, u in laeufe}) == 1 or len({o for o, _ in laeufe}) == 1
        hs = [u - o + 1 for o, u in laeufe]
        stufig = (all(b - a == 1 for a, b in zip(hs, hs[1:]))
                  or all(a - b == 1 for a, b in zip(hs, hs[1:])))
        if buendig and stufig:
            return True
    return False


def _muster_treppe(rng, k, n):
    folgen = _treppe_hoehen(n, k)
    if not folgen:
        return None
    muster = _treppe_zellen(rng.choice(folgen), k, rng)
    return muster if _ist_treppe(muster) else None


_PRUEFER_MUSTER = {
    "symmetrie": lambda z, k: _symmetrisch(z, k),
    "linien": lambda z, k: _ist_linienmuster(z),
    "treppe": lambda z, k: _ist_treppe(z),
}


def _original(rng, k, n):
    """Würfelt ein strukturiertes Original mit genau n Punkten auf k×k.
    Rückgabe (Zellmenge, Musterart). Die Reihenfolge der Musterarten ist
    zufällig; es gibt immer mindestens die Symmetrie als Ausweg."""
    arten = list(MUSTER)
    for _ in range(100):
        rng.shuffle(arten)
        for art in arten:
            z = {"symmetrie": _muster_symmetrie, "linien": _muster_linien,
                 "treppe": _muster_treppe}[art](rng, k, n)
            if z is not None and len(z) == n:
                return z, art
    raise ValueError(f"kein strukturiertes Merkbild für k={k}, n={n} gefunden")


def _verschoben(rng, k, z):
    """Ein Punkt wandert auf eine freie Zelle in seiner Nähe (höchstens zwei
    Felder weit) — der feinste Unterschied, den die Aufgabe verlangt."""
    zellen = sorted(z)
    for _ in range(40):
        weg = rng.choice(zellen)
        nahe = [(weg[0] + dr, weg[1] + dc) for dr in range(-2, 3) for dc in range(-2, 3)
                if (dr or dc) and _in(k, (weg[0] + dr, weg[1] + dc))
                and (weg[0] + dr, weg[1] + dc) not in z]
        if nahe:
            return frozenset((z - {weg}) | {rng.choice(nahe)})
    return None


def _ablenker(rng, k, z, stufe):
    """Drei verschiedene Raster, alle mit gleich vielen Punkten wie das
    Original (sonst verriete schon das Zählen die Antwort). Bis Stufe 4 darf
    eines gespiegelt sein (grobe Unterschiede), danach nur noch ein
    verschobener Punkt."""
    ergebnis = []
    if stufe <= 4:
        spiegel = [b for b in _bilder_von(z, k).values() if b != z]
        rng.shuffle(spiegel)
        ergebnis += spiegel[:1]
    for _ in range(200):
        if len(ergebnis) == 3:
            break
        v = _verschoben(rng, k, z)
        if v is not None and v != z and v not in ergebnis:
            ergebnis.append(v)
    return ergebnis if len(ergebnis) == 3 else None


# ---------------------------------------------------------------- Rendern
M_ZELLE = 44
M_RAND = M_ZELLE // 2


def _render_raster(k, zellen, farbe):
    """Ein k×k-Raster mit Punkten (immer gleich gezeichnet, damit Original und
    Optionen sich nur im Inhalt unterscheiden)."""
    teile = []
    for i in range(k + 1):
        teile.append(f'<line x1="0" y1="{i * M_ZELLE}" x2="{k * M_ZELLE}" y2="{i * M_ZELLE}" '
                     f'stroke="{RASTER}" stroke-width="1"/>')
        teile.append(f'<line x1="{i * M_ZELLE}" y1="0" x2="{i * M_ZELLE}" y2="{k * M_ZELLE}" '
                     f'stroke="{RASTER}" stroke-width="1"/>')
    for r, c in sorted(zellen):
        teile.append(f'<circle cx="{_fmt((c + 0.5) * M_ZELLE)}" cy="{_fmt((r + 0.5) * M_ZELLE)}" '
                     f'r="{_fmt(M_ZELLE * 0.34)}" fill="{farbe}" stroke="{KONTUR}" stroke-width="2"/>')
    return _svg_wrap(k * M_ZELLE, k * M_ZELLE, M_RAND, "".join(teile))


def erzeuge_merkbild(stufe, seed):
    """Eine Merkbild-Aufgabe der Stufe 2..8: das Fragebild ist das Original
    (die App blendet es nach `merken_ms` aus), dann wählt das Kind unter vier
    Rastern das gleiche."""
    if stufe not in STUFEN_MERK:
        raise ValueError(f"stufe {stufe!r} liegt nicht in 2..8")
    k, n = STUFEN_MERK[stufe]
    rng = _rng("merkbild", stufe, seed)
    for _ in range(100):
        original, art = _original(rng, k, n)
        abl = _ablenker(rng, k, original, stufe)
        if abl is None:
            continue
        optionen = [original] + abl
        reihenfolge = list(range(4))
        rng.shuffle(reihenfolge)
        optionen = [optionen[i] for i in reihenfolge]
        richtig = reihenfolge.index(0)
        farbe = rng.choice(DOT_FARBEN)
        kern = {
            "art": "merkbild", "raster": k, "muster": art,
            "original": [list(z) for z in sorted(original)],
            "optionen": [[list(z) for z in sorted(o)] for o in optionen],
            "richtig": richtig, "stufe": stufe, "merken_ms": merken_ms(stufe),
        }
        return {"type": "bildwahl", "q": "Merk dir das Bild. Welches Bild war das?",
                "svg": _render_raster(k, original, farbe),
                "optionen_svg": [_render_raster(k, o, farbe) for o in optionen],
                "richtig": richtig, "merken_ms": merken_ms(stufe), "kern": kern,
                "hint": "Achte auf Linien, Treppen und Spiegelungen."}
    raise ValueError(f"kein Merkbild für Stufe {stufe} nach 100 Versuchen")


def _zellen_von(liste, k):
    """Liste von [zeile, spalte] -> frozenset, mit Prüfung. Wirft ValueError."""
    zellen = [tuple(z) for z in liste]
    if any(len(z) != 2 or not all(_ganz(c) for c in z) or not _in(k, z) for z in zellen):
        raise ValueError("Zellen sind keine Paare innerhalb des Rasters")
    if len(set(zellen)) != len(zellen):
        raise ValueError("eine Zelle steht doppelt")
    return frozenset(zellen)


def pruefe_merkbild(kern):
    """Rechnet ohne SVG nach: genau eine Option ist gleich dem Original, alle
    Optionen sind verschieden und haben gleich viele Punkte, und das Original
    hat die Struktur, die es zu haben behauptet."""
    if not isinstance(kern, dict) or kern.get("art") != "merkbild":
        return False, "kein merkbild-Kern (art muss 'merkbild' sein)"
    k, richtig = kern.get("raster"), kern.get("richtig")
    if not (_ganz(k) and 3 <= k <= 5):
        return False, f"raster={k!r} liegt nicht in 3..5"
    try:
        original = _zellen_von(kern.get("original"), k)
        optionen = [_zellen_von(o, k) for o in kern.get("optionen")]
    except (TypeError, ValueError) as e:
        return False, f"Zellen unbrauchbar: {e}"
    if len(optionen) != 4:
        return False, f"{len(optionen)} Optionen statt 4"
    if len(set(optionen)) != 4:
        return False, "die vier Optionen sind nicht paarweise verschieden"
    if not (_ganz(richtig) and 0 <= richtig < 4):
        return False, f"richtig={richtig!r} ist kein Options-Index (0..3)"
    gleiche = [i for i, o in enumerate(optionen) if o == original]
    if gleiche != [richtig]:
        return False, f"Optionen gleich dem Original: {gleiche}, als richtig angegeben: {richtig}"
    if any(len(o) != len(original) for o in optionen):
        return False, "eine Option hat eine andere Punktzahl als das Original"
    if not 3 <= len(original) <= 10:
        return False, f"{len(original)} Punkte liegen nicht in 3..10"
    muster = kern.get("muster")
    if muster not in _PRUEFER_MUSTER:
        return False, f"Muster {muster!r} ist unbekannt"
    if not _PRUEFER_MUSTER[muster](original, k):
        return False, f"das Original hat die Struktur {muster!r} gar nicht"
    stufe = kern.get("stufe")
    if stufe is not None:
        if stufe not in STUFEN_MERK or STUFEN_MERK[stufe] != (k, len(original)):
            return False, f"Raster {k}x{k} mit {len(original)} Punkten passt nicht zu Stufe {stufe!r}"
        if kern.get("merken_ms") != merken_ms(stufe):
            return False, f"merken_ms={kern.get('merken_ms')!r} passt nicht zu Stufe {stufe}"
    return True, "genau eine Option ist gleich dem Original"


def denkcheck_merkbild(stufe, seed):
    """Denk-Check, Dimension "merken": Merkbild, Stufe 2..8."""
    return erzeuge_merkbild(stufe, seed)


PRUEFER = {"punktmuster": pruefe_punktmuster, "merkbild": pruefe_merkbild}
