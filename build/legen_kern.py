# -*- coding: utf-8 -*-
"""Der deterministische Kern für den Aufgabentyp `legen` (ZIELE-V3.md, G1 und G4).

Das Kind legt Figuren (Emoji-Karten) auf Plätze und sammelt so alle
Reihenfolgen bzw. Auswahlen. Die Wahrheit steht hier, nicht in einem Text:
Die Gesamtzahl ist KEINE Rechnung aus dem Kopf eines Sprachmodells (das
verzählt sich bei Reihenfolgen mit Regeln zuverlässig), sondern das Ergebnis
einer vollständigen Aufzählung aller Anordnungen. Der Modus `alle` ist nur
bei 2…8 Anordnungen erlaubt — mehr kann ein Kind nicht sinnvoll selbst
zusammentragen, und die App kann dann jede gefundene Anordnung einzeln
gegen dieselbe Regelprüfung halten.

Zwei Dinge müssen mit der JavaScript-Prüfung in src/app.html bit-genau
übereinstimmen und stehen deshalb ausschließlich hier als Wahrheit:

  - die Regelsemantik (regel_erfuellt), und zwar so wie in ZIELE-V3.md
    beschrieben, auch dort, wo sie auf den ersten Blick ungewohnt wirkt: eine
    Regel, deren Figur gar nicht gelegt ist, gilt als erfüllt — außer
    `zusammen` ("genau dann dabei") und `dabei`;
  - die Aufzählung (anordnungen): Permutationen bei `geordnet`, Kombinationen
    sonst.

Seeds nur über zlib.crc32 von Text (kein hash(), das ist je Lauf anders),
Zufall nur über random.Random(seed): derselbe Aufruf liefert immer dieselbe
Aufgabe. Kein Sprachmodell im Pfad.
"""
import itertools
import random
import re
import zlib

# Figurenvorrat. "nom" steht klein, damit die Namen mitten im Satz ("Der Fuchs
# und die Eule …") ohne Umbauen passen; am Satzanfang wird großgeschrieben.
FIGUREN = [
    {"name": "Fuchs", "bild": "🦊", "nom": "der Fuchs", "dat": "dem Fuchs"},
    {"name": "Eule", "bild": "🦉", "nom": "die Eule", "dat": "der Eule"},
    {"name": "Golem", "bild": "🗿", "nom": "der Golem", "dat": "dem Golem"},
    {"name": "Katze", "bild": "🐱", "nom": "die Katze", "dat": "der Katze"},
    {"name": "Drache", "bild": "🐲", "nom": "der Drache", "dat": "dem Drachen"},
    {"name": "Biene", "bild": "🐝", "nom": "die Biene", "dat": "der Biene"},
]

# Regelarten je Modus (ZIELE-V3.md, "Datenformate").
REGELN_GEORDNET = ("nicht_platz", "auf_platz", "direkt_hinter", "nebeneinander",
                   "nicht_nebeneinander")
REGELN_UNGEORDNET = ("zusammen", "nicht_zusammen", "dabei", "nicht_dabei")

# Welche Felder eine Regelart trägt. "a"/"b" sind Figur-Indizes.
_FELDER = {
    "nicht_platz": ("a", "platz"), "auf_platz": ("a", "platz"),
    "direkt_hinter": ("a", "b"), "nebeneinander": ("a", "b"),
    "nicht_nebeneinander": ("a", "b"),
    "zusammen": ("a", "b"), "nicht_zusammen": ("a", "b"),
    "dabei": ("a",), "nicht_dabei": ("a",),
}

MAX_FIGUREN = len(FIGUREN)   # 6 → höchstens 720 Anordnungen zu zählen
MAX_ALLE = 8                 # Modus "alle" nur bei 2…MAX_ALLE Anordnungen


def _ganz(x):
    """True für echte ganze Zahlen (bool ist in Python auch ein int – nicht
    hier: ein `True` als Figur-Index wäre ein kaputter Kern)."""
    return isinstance(x, int) and not isinstance(x, bool)


# ============================================================ Regelsemantik

def regel_erfuellt(regel, anordnung, geordnet):
    """Gilt `regel` für diese Anordnung? Semantik exakt wie ZIELE-V3.md.

    anordnung: Folge von Figur-Indizes (bei geordnet: von vorne nach hinten,
    Platz 0 = ganz vorne/links). Bei ungeordnet zählt nur, WER dabei ist.

    Eine Regel, deren Figur nicht gelegt ist, gilt als erfüllt (außer
    `zusammen` und `dabei`). Eine Regelart, die es im jeweiligen Modus nicht
    gibt, oder ein Unbekanntes gilt sicherheitshalber als NICHT erfüllt —
    dieselbe Vorsicht wie im übrigen Projekt: im Zweifel nichts durchwinken.
    """
    if not isinstance(regel, dict):
        return False
    art = regel.get("art")
    erlaubt = REGELN_GEORDNET if geordnet else REGELN_UNGEORDNET
    if art not in erlaubt:
        return False
    a, b, platz = regel.get("a"), regel.get("b"), regel.get("platz")
    pos = {figur: i for i, figur in enumerate(anordnung)}
    dabei = set(anordnung)

    if art == "nicht_platz":
        return a not in pos or pos[a] != platz
    if art == "auf_platz":
        return a not in pos or pos[a] == platz
    if art in ("direkt_hinter", "nebeneinander", "nicht_nebeneinander"):
        if a not in pos or b not in pos:
            return True
        if art == "direkt_hinter":
            return pos[a] == pos[b] + 1
        abstand = abs(pos[a] - pos[b])
        return abstand == 1 if art == "nebeneinander" else abstand != 1
    if art == "zusammen":
        return (a in dabei) == (b in dabei)
    if art == "nicht_zusammen":
        return not (a in dabei and b in dabei)
    if art == "dabei":
        return a in dabei
    return a not in dabei    # nicht_dabei


def anordnungen(n, plaetze, geordnet, regeln):
    """Alle gültigen Anordnungen, vollständig aufgezählt, in fester Reihenfolge.

    geordnet: Permutationen von `plaetze` aus n Figuren (n!/(n−k)! ohne
    Regeln); sonst Kombinationen (C(n,k)), jede als aufsteigendes Tupel.
    """
    if not (_ganz(n) and _ganz(plaetze) and 1 <= plaetze <= n):
        raise ValueError(f"unmögliche Größen: n={n!r}, plaetze={plaetze!r}")
    quelle = (itertools.permutations(range(n), plaetze) if geordnet
              else itertools.combinations(range(n), plaetze))
    return [anf for anf in quelle
            if all(regel_erfuellt(r, anf, geordnet) for r in regeln)]


def anzahl(n, plaetze, geordnet, regeln):
    """Die Gesamtzahl gültiger Anordnungen (= Länge der Aufzählung)."""
    return len(anordnungen(n, plaetze, geordnet, regeln))


# ================================================================== Sprache

def _figur_von(figur):
    """Schlägt zu einer Figur (dict mit mindestens "name") die Grammatik im
    Vorrat nach. Die Figuren in der Aufgabe tragen nur name/bild — die
    Fälle (nom/dat) kommen aus FIGUREN, damit sie nirgends doppelt stehen."""
    name = figur.get("name") if isinstance(figur, dict) else None
    for f in FIGUREN:
        if f["name"] == name:
            return f
    raise ValueError(f"unbekannte Figur {figur!r}")


def _gross(s):
    """Nur den ersten Buchstaben groß – für Satzanfänge."""
    return s[:1].upper() + s[1:]


def _akk(figur):
    """Akkusativ aus dem Vorrat: Maskulina nehmen den Dativ ohne 'dem' ('dem
    Drachen' → 'den Drachen', denn 'der Drache' ist ein schwaches Nomen),
    Feminina bleiben wie im Nominativ ('die Eule')."""
    return "den " + figur["dat"][4:] if figur["dat"].startswith("dem ") else figur["nom"]


def _platz_wort(platz, plaetze):
    """Platz 0 ist 'ganz vorne', der letzte 'ganz hinten', sonst zählt das
    Kind ab 1: 'auf Platz 2'. Ohne Wissen über die Platzzahl bleibt es bei
    der Zahl."""
    if platz == 0:
        return "ganz vorne"
    if plaetze is not None and platz == plaetze - 1:
        return "ganz hinten"
    return f"auf Platz {platz + 1}"


def regel_text(regel, figuren, plaetze=None):
    """Ein deutscher Satz zur Regel, z. B. 'Der Fuchs steht nie ganz vorne.'

    figuren: die Figuren der Aufgabe (Indizes der Regel zeigen hinein).
    plaetze: optional; nur damit 'ganz hinten' statt 'auf Platz 3' kommt.
    """
    art = regel.get("art")
    if art not in _FELDER:
        raise ValueError(f"unbekannte Regelart {art!r}")
    a = _figur_von(figuren[regel["a"]])
    b = _figur_von(figuren[regel["b"]]) if "b" in _FELDER[art] else None

    if art == "nicht_platz":
        wo = _platz_wort(regel["platz"], plaetze)
        satz = f"{_gross(a['nom'])} steht nie {wo}."
    elif art == "auf_platz":
        satz = f"{_gross(a['nom'])} steht {_platz_wort(regel['platz'], plaetze)}."
    elif art == "direkt_hinter":
        satz = f"{_gross(a['nom'])} steht direkt hinter {b['dat']}."
    elif art == "nebeneinander":
        satz = f"{_gross(a['nom'])} und {b['nom']} stehen nebeneinander."
    elif art == "nicht_nebeneinander":
        satz = f"{_gross(a['nom'])} und {b['nom']} stehen nie nebeneinander."
    elif art == "zusammen":
        satz = f"{_gross(a['nom'])} und {b['nom']} sind nur zusammen dabei."
    elif art == "nicht_zusammen":
        satz = f"{_gross(a['nom'])} und {b['nom']} sind nie zusammen dabei."
    elif art == "dabei":
        satz = f"{_gross(a['nom'])} ist immer dabei."
    else:   # nicht_dabei
        satz = f"{_gross(a['nom'])} ist nicht dabei."
    return satz


# ================================================================== Prüfer

def _pruefe_regel_form(regel, n, plaetze, geordnet):
    """Prüft nur die FORM einer Regel (Art passt zum Modus, Felder sind ganze
    Zahlen im richtigen Bereich). Rückgabe: Grund als Text oder None."""
    if not isinstance(regel, dict):
        return f"Regel ist kein Objekt: {regel!r}"
    art = regel.get("art")
    erlaubt = REGELN_GEORDNET if geordnet else REGELN_UNGEORDNET
    if art not in erlaubt:
        return (f"Regelart {art!r} gibt es bei "
                f"{'geordneten' if geordnet else 'ungeordneten'} Aufgaben nicht")
    felder = _FELDER[art]
    if set(regel) != {"art", *felder}:
        return f"Regel {art!r} hat die falschen Felder: {sorted(regel)}"
    for f in felder:
        w = regel[f]
        if not _ganz(w):
            return f"Regel {art!r}: Feld {f!r} ist keine ganze Zahl ({w!r})"
        grenze = plaetze if f == "platz" else n
        if not 0 <= w < grenze:
            return f"Regel {art!r}: Feld {f!r}={w} liegt außerhalb von 0..{grenze - 1}"
    if "b" in felder and regel["a"] == regel["b"]:
        return f"Regel {art!r}: a und b sind dieselbe Figur"
    return None


def pruefe_legen(kern, aufgabe=None):
    """Prüft den Kern einer legen-Aufgabe: Rückgabe (ok, Grund).

    Die Gesamtzahl wird NEU aufgezählt und mit kern["anzahl"] verglichen. Jede
    Regel muss wirken (ohne sie ergäbe sich eine andere Zahl) — eine Regel,
    die nichts ausschließt, ist im Aufgabentext nur Rauschen und verwirrt das
    Kind. Optional kommt die ganze Aufgabe mit: dann gilt zusätzlich, dass
    der Modus `alle` nur bei 2…8 Anordnungen vorkommt und dass Figuren,
    Plätze, Regeln und Antwort zum Kern passen (der Kern selbst kennt den
    Modus nicht, ZIELE-V3.md).
    """
    if not isinstance(kern, dict) or kern.get("art") != "legen":
        return False, "kein legen-Kern (art muss 'legen' sein)"
    n, plaetze, geordnet = kern.get("n"), kern.get("plaetze"), kern.get("geordnet")
    regeln, soll = kern.get("regeln"), kern.get("anzahl")
    if not (_ganz(n) and 2 <= n <= MAX_FIGUREN):
        return False, f"n={n!r} liegt nicht in 2..{MAX_FIGUREN}"
    if not (_ganz(plaetze) and 2 <= plaetze <= n):
        return False, f"plaetze={plaetze!r} liegt nicht in 2..{n}"
    if not isinstance(geordnet, bool):
        return False, f"geordnet={geordnet!r} ist kein Wahrheitswert"
    if not geordnet and plaetze == n:
        return False, "ungeordnet mit plaetze == n ergibt nur eine Auswahl"
    if not isinstance(regeln, list) or len(regeln) > 3:
        return False, "regeln fehlt oder ist keine Liste mit höchstens 3 Regeln"
    for r in regeln:
        grund = _pruefe_regel_form(r, n, plaetze, geordnet)
        if grund:
            return False, grund
    if len({tuple(sorted(r.items())) for r in regeln}) != len(regeln):
        return False, "dieselbe Regel steht zweimal da"

    gezaehlt = anzahl(n, plaetze, geordnet, regeln)
    if gezaehlt < 1:
        return False, "die Regeln schließen alle Anordnungen aus (Anzahl 0)"
    if soll != gezaehlt or not _ganz(soll):
        return False, f"anzahl={soll!r}, die Aufzählung ergibt aber {gezaehlt}"
    for i, r in enumerate(regeln):
        ohne = regeln[:i] + regeln[i + 1:]
        if anzahl(n, plaetze, geordnet, ohne) == gezaehlt:
            return False, f"Regel {i} ({r['art']}) schließt nichts aus – überflüssig"

    if aufgabe is not None:
        return _pruefe_aufgabe_zum_kern(aufgabe, kern, gezaehlt)
    return True, f"{gezaehlt} Anordnungen, vollständig aufgezählt"


def pruefe_legen_aufgabe(aufgabe):
    """Bequem: prüft eine fertige legen-Aufgabe samt Kern und Modus."""
    if not isinstance(aufgabe, dict):
        return False, "Aufgabe ist kein Objekt"
    return pruefe_legen(aufgabe.get("kern"), aufgabe)


_PLATZHALTER = re.compile(r"[\[\]{}]|\bk\d+e\d+\b|\bp\d+\b|%s|\bNone\b|\bTODO\b")


def _pruefe_aufgabe_zum_kern(aufgabe, kern, gezaehlt):
    """Der Teil von pruefe_legen, der die ganze Aufgabe braucht."""
    if aufgabe.get("type") != "legen":
        return False, f"type={aufgabe.get('type')!r}, erwartet 'legen'"
    modus = aufgabe.get("modus")
    if modus not in ("alle", "zaehlen"):
        return False, f"modus={modus!r} ist weder 'alle' noch 'zaehlen'"
    if modus == "alle" and not 2 <= gezaehlt <= MAX_ALLE:
        return False, (f"Modus 'alle' nur bei 2..{MAX_ALLE} Anordnungen, "
                       f"hier sind es {gezaehlt}")
    if aufgabe.get("a") != gezaehlt:
        return False, f"a={aufgabe.get('a')!r}, die Aufzählung ergibt {gezaehlt}"
    for feld in ("plaetze", "geordnet", "regeln"):
        if aufgabe.get(feld) != kern.get(feld):
            return False, f"Feld {feld!r} der Aufgabe weicht vom Kern ab"
    figuren = aufgabe.get("figuren")
    if not isinstance(figuren, list) or len(figuren) != kern["n"]:
        return False, "figuren fehlt oder hat nicht n Einträge"
    namen = []
    for f in figuren:
        if not isinstance(f, dict) or set(f) != {"name", "bild"}:
            return False, f"Figur {f!r} darf nur name und bild tragen"
        vorrat = [v for v in FIGUREN if v["name"] == f["name"] and v["bild"] == f["bild"]]
        if not vorrat:
            return False, f"Figur {f!r} gibt es im Vorrat nicht"
        namen.append(f["name"])
    if len(set(namen)) != len(namen):
        return False, "dieselbe Figur kommt zweimal vor"
    q = aufgabe.get("q")
    if not isinstance(q, str) or not q.strip():
        return False, "q fehlt"
    if _PLATZHALTER.search(q) or _PLATZHALTER.search(str(aufgabe.get("hint", ""))):
        return False, "Text enthält einen Platzhalter"
    return True, f"{gezaehlt} Anordnungen, Modus {modus}, vollständig aufgezählt"


# ============================================================ Aufgaben bauen
# Ein "Plan" beschreibt die Gestalt einer Aufgabe, nicht ihre Einzelheiten:
# Modus, Größen, Regelarten und welche Gesamtzahl herauskommen soll. Welche
# Figuren, welche Plätze und welche Figur-Paare in den Regeln stehen, würfelt
# der Seed aus — und zwar so lange, bis die AUFZÄHLUNG die gewünschte Zahl
# liefert. Die Zahl wird also nie vorausgesetzt, sondern nachgezählt.

_GEORDNET_ARTEN = REGELN_GEORDNET


def _plan(modus, n, plaetze, geordnet, regeln=(), soll=None, bereich=None):
    return {"modus": modus, "n": n, "plaetze": plaetze, "geordnet": geordnet,
            "regeln": [tuple(r) if isinstance(r, (tuple, list)) else (r,) for r in regeln],
            "soll": soll, "bereich": bereich}


# Denktiefe steigt mit dem Index: erst Systematik an kleinen Fällen, dann
# Regeln, dann das bloße Zählen ohne Probierbrett-Hilfe durch Wiederholung.
PAKETE = {
    ("komb_reihen", 4): [
        _plan("alle", 2, 2, True, soll=2),
        _plan("alle", 3, 3, True, soll=6),
        _plan("alle", 3, 3, True, ["nicht_platz"], soll=4),
        _plan("alle", 3, 3, True, ["direkt_hinter"], soll=2),
        _plan("zaehlen", 3, 2, True, soll=6),
        _plan("zaehlen", 4, 4, True, soll=24),
    ],
    ("komb_reihen", 5): [
        _plan("alle", 4, 4, True, [_GEORDNET_ARTEN, _GEORDNET_ARTEN], bereich=(2, 8)),
        _plan("alle", 4, 2, True, [("nicht_platz", "auf_platz"), ("nicht_platz", "auf_platz")],
              bereich=(2, 8)),
        _plan("zaehlen", 4, 4, True, ["nicht_platz"], soll=18),
        _plan("zaehlen", 4, 4, True, ["nebeneinander"], soll=12),
        _plan("zaehlen", 4, 4, True, ["nicht_nebeneinander"], soll=12),
        _plan("zaehlen", 5, 5, True, soll=120),
    ],
    ("komb_paare", 4): [
        _plan("alle", 3, 2, False, soll=3),
        _plan("alle", 4, 2, False, soll=6),
        _plan("alle", 4, 2, False, ["nicht_zusammen"], soll=5),
        _plan("alle", 4, 3, False, soll=4),
        _plan("zaehlen", 5, 2, False, soll=10),
        _plan("zaehlen", 6, 2, False, soll=15),
    ],
    ("komb_paare", 5): [
        _plan("alle", 5, 3, False, ["nicht_zusammen"], soll=7),
        _plan("alle", 5, 2, False, ["dabei"], soll=4),
        _plan("zaehlen", 5, 3, False, soll=10),
        _plan("zaehlen", 6, 2, False, ["nicht_zusammen"], soll=14),
        _plan("zaehlen", 6, 3, False, soll=20),
        _plan("zaehlen", 6, 3, False, ["zusammen"]),
    ],
}

# Denk-Check, Dimension "systematik": Stufe 2..8, adaptiv gezogen. Stufe 5
# hat zwei Gestalten (alle Paare aus 4 oder zaehlen 4), der Seed wählt.
DENKCHECK = {
    2: [_plan("alle", 2, 2, True, soll=2)],
    3: [_plan("alle", 3, 3, True, soll=6)],
    4: [_plan("alle", 3, 3, True, [("nicht_platz", "auf_platz", "direkt_hinter")],
              bereich=(2, 4))],
    5: [_plan("alle", 4, 2, False, soll=6),
        _plan("zaehlen", 4, 4, True, soll=24)],
    6: [_plan("zaehlen", 4, 4, True, [("nicht_platz", "direkt_hinter", "nebeneinander",
                                        "nicht_nebeneinander")])],
    7: [_plan("zaehlen", 5, 5, True, ["direkt_hinter"])],
    8: [_plan("zaehlen", 5, 5, True, ["nicht_nebeneinander"])],
}


def _ziehe_regel(rng, art, n, plaetze):
    """Würfelt die Einzelheiten einer Regelart aus."""
    felder = _FELDER[art]
    r = {"art": art}
    if "b" in felder:
        r["a"], r["b"] = rng.sample(range(n), 2)
    else:
        r["a"] = rng.randrange(n)
    if "platz" in felder:
        r["platz"] = 0 if rng.random() < 0.5 else rng.randrange(plaetze)
    return r


def _passt(plan, regeln):
    """Hat die Zählung das gewünschte Ergebnis, und wirkt jede Regel?"""
    n, p, g = plan["n"], plan["plaetze"], plan["geordnet"]
    ist = anzahl(n, p, g, regeln)
    if ist < 1:
        return None
    if plan["soll"] is not None and ist != plan["soll"]:
        return None
    if plan["bereich"] is not None and not plan["bereich"][0] <= ist <= plan["bereich"][1]:
        return None
    if plan["modus"] == "alle" and not 2 <= ist <= MAX_ALLE:
        return None
    if len({tuple(sorted(r.items())) for r in regeln}) != len(regeln):
        return None
    for i in range(len(regeln)):
        if anzahl(n, p, g, regeln[:i] + regeln[i + 1:]) == ist:
            return None   # Regel schließt nichts aus
    return ist


_WORT = {2: "Paare", 3: "Dreier", 4: "Vierer"}


def _frage(plan, figuren, regeln):
    """Der Fragetext: kurz, mit Anzahl der Figuren (sonst wären die ersten
    Aufgaben eines Pakets textgleich), danach je Regel ein Satz."""
    n, p, g = plan["n"], plan["plaetze"], plan["geordnet"]
    if g:
        was = "Reihenfolgen"
        mit = f"mit {n} Figuren" if p == n else f"mit {p} von {n} Figuren"
    else:
        was = _WORT[p]
        mit = f"aus {n} Figuren"
    if plan["modus"] == "alle":
        ziel = f"Lege alle {was} {mit}."
    else:
        ziel = f"Wie viele {was} gibt es {mit}?"
    saetze = [regel_text(r, figuren, p) for r in regeln]
    return " ".join([ziel] + saetze)


def _hinweis(plan, figuren, regeln):
    """Ein Tipp zum Vorgehen (Systematik), nie die Lösung."""
    f0 = _figur_von(figuren[0])
    p, g, modus = plan["plaetze"], plan["geordnet"], plan["modus"]
    if g:
        if modus == "alle" and not regeln:
            return f"Fang mit {f0['dat']} vorne an und probier alles dahinter."
        if modus == "alle":
            return (f"Leg der Reihe nach: erst {f0['nom']} vorne, dann die anderen. "
                    "Prüf jede Reihe gegen die Regel.")
        if regeln:
            return "Probier es auf dem Brett aus und prüf jede Reihe gegen die Regel."
        if plan["n"] >= 4:
            return f"Leg erst die Reihen mit {f0['dat']} vorne. Mit den anderen geht es genauso."
        return f"Fang mit {f0['dat']} vorne an: Wie viele Reihen gibt es dann?"
    wort = _WORT[p]
    if modus == "alle":
        return f"Such zuerst alle {wort} mit {f0['dat']}. Dann die ohne {_akk(f0)}."
    return f"Such erst alle {wort} mit {f0['dat']}, dann alle ohne {_akk(f0)}."


def _aufgabe_aus_plan(plan, rng, name):
    """Würfelt Figuren und Regeldetails, bis die Zählung zum Plan passt."""
    n, p, g = plan["n"], plan["plaetze"], plan["geordnet"]
    for _ in range(2000):
        figuren = [{"name": f["name"], "bild": f["bild"]} for f in rng.sample(FIGUREN, n)]
        regeln = [_ziehe_regel(rng, rng.choice(arten), n, p) for arten in plan["regeln"]]
        gezaehlt = _passt(plan, regeln)
        if gezaehlt is None:
            continue
        kern = {"art": "legen", "n": n, "plaetze": p, "geordnet": g,
                "regeln": [dict(r) for r in regeln], "anzahl": gezaehlt}
        aufgabe = {"type": "legen", "q": _frage(plan, figuren, regeln),
                   "figuren": figuren, "plaetze": p, "geordnet": g,
                   "modus": plan["modus"], "regeln": regeln, "a": gezaehlt,
                   "kern": kern, "hint": _hinweis(plan, figuren, regeln)}
        ok, grund = pruefe_legen(kern, aufgabe)
        if not ok:   # Selbstprüfung: lieber laut scheitern als Falsches ausliefern
            raise RuntimeError(f"{name}: selbst erzeugte Aufgabe fällt durch: {grund}")
        return aufgabe
    raise ValueError(f"{name}: keine passende Aufgabe nach 2000 Versuchen gefunden")


def _rng(*teile):
    """Zufall aus Text, nie aus hash() (das ist je Lauf anders)."""
    return random.Random(zlib.crc32("|".join(str(t) for t in teile).encode("utf-8")))


def baue_aufgabe(skill, stage, index, seed):
    """Die Aufgabe `index` (0..5) des Pakets skill@stage.

    skill ∈ {"komb_reihen", "komb_paare"}, stage ∈ {4, 5}. Derselbe Aufruf
    liefert immer dieselbe Aufgabe.
    """
    plaene = PAKETE.get((skill, stage))
    if plaene is None:
        raise ValueError(f"kein legen-Paket für {skill!r}@{stage!r}")
    if not (_ganz(index) and 0 <= index < len(plaene)):
        raise ValueError(f"index {index!r} liegt nicht in 0..{len(plaene) - 1}")
    rng = _rng("legen", skill, stage, index, seed)
    return _aufgabe_aus_plan(plaene[index], rng, f"{skill}@{stage}#{index}")


def denkcheck_aufgabe(stufe, seed):
    """Eine Denk-Check-Aufgabe der Dimension "systematik", Stufe 2..8."""
    plaene = DENKCHECK.get(stufe)
    if plaene is None:
        raise ValueError(f"stufe {stufe!r} liegt nicht in 2..8")
    rng = _rng("legen-denkcheck", stufe, seed)
    plan = rng.choice(plaene)
    return _aufgabe_aus_plan(plan, rng, f"denkcheck systematik @{stufe}")
