# -*- coding: utf-8 -*-
"""Prüft den deterministischen Algorithmik-Kern (algo_kern.py).

Im selben Geist wie raetsel_kern_test.py: der Kern selbst ist die einzige
Stelle, die künftig garantiert, dass eine Roboter- oder Zahlenmaschinen-
Aufgabe überhaupt lösbar, eindeutig und ihre Ablenker nachweislich falsch
sind. Deshalb wird hier NICHT einfach pruefe_roboter()/pruefe_maschine()
gegen sich selbst laufen gelassen (das würde nur zeigen, dass der Prüfer
sich selbst zustimmt) – die zentralen Garantien (kürzeste Lösung, Ein-
deutigkeit der Reparatur, Eindeutigkeit der Zahlenregel, die Simulation
selbst) werden hier mit einer UNABHÄNGIGEN Zweitimplementierung
nachgerechnet. Nur so fällt ein Fehler auf, der in Erzeuger UND Prüfer
gleichermaßen stecken würde.

  .venv/bin/python build/algo_kern_test.py
"""
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import algo_kern as A

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


# ============================================== unabhängige Zweitsimulation
# Eigens für diesen Test geschrieben, ohne irgendeine Hilfsfunktion aus
# algo_kern.py zu benutzen – nur die öffentlichen Erzeuger/Prüfer werden
# gegen DIESE Implementierung gegengerechnet.

_VEK = {"N": (-1, 0), "O": (0, 1), "S": (1, 0), "W": (0, -1)}
_LI = {"N": "W", "W": "S", "S": "O", "O": "N"}
_RE = {"N": "O", "O": "S", "S": "W", "W": "N"}
_GEGENSATZ_T = {"N": "S", "S": "N", "O": "W", "W": "O"}


def _flach_t(programm):
    ergebnis = []
    for b in (programm or []):
        if isinstance(b, dict) and "b" in b:
            for _ in range(b["x"]):
                ergebnis.extend(_flach_t(b["b"]))
        else:
            ergebnis.append(b)
    return ergebnis


def _sim_t(n, start, richtung, waende, programm):
    """Unabhängige Simulation: eigene Schleifen der Robotersteuerung, ohne
    algo_kern.simuliere() oder algo_kern.flach() aufzurufen."""
    wand = {tuple(w) for w in (waende or [])}
    r, c = start[0], start[1]
    rich = richtung
    crash = False
    for b in _flach_t(programm):
        if b == "L":
            rich = _LI[rich]
            continue
        if b == "R":
            rich = _RE[rich]
            continue
        zr = rich if b == "V" else b
        dr, dc = _VEK[zr]
        nr, nc = r + dr, c + dc
        if not (0 <= nr < n and 0 <= nc < n) or (nr, nc) in wand:
            crash = True
            break
        r, c, rich = nr, nc, zr
    return {"ende": [r, c], "richtung": rich, "crash": crash}


def _bfs_t(n, start, richtung, waende, befehlssatz):
    """Unabhängige Breitensuche über denselben Zustandsraum wie SPEC §2
    beschreibt, eigens implementiert (eigene Nachbarfunktion, eigene
    Warteschlange) statt algo_kern._bfs_zustaende() zu benutzen."""
    wand = {tuple(w) for w in (waende or [])}
    if befehlssatz == "absolut":
        start_z = (start[0], start[1])

        def nachbarn(z):
            r, c = z
            for rich in ("N", "O", "S", "W"):
                dr, dc = _VEK[rich]
                nr, nc = r + dr, c + dc
                if 0 <= nr < n and 0 <= nc < n and (nr, nc) not in wand:
                    yield (nr, nc)
    else:
        start_z = (start[0], start[1], richtung)

        def nachbarn(z):
            r, c, rich = z
            dr, dc = _VEK[rich]
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n and (nr, nc) not in wand:
                yield (nr, nc, rich)
            yield (r, c, _LI[rich])
            yield (r, c, _RE[rich])

    dist = {start_z: 0}
    q = deque([start_z])
    while q:
        z = q.popleft()
        for nz in nachbarn(z):
            if nz not in dist:
                dist[nz] = dist[z] + 1
                q.append(nz)
    return dist


def _kuerzeste_t(dist, befehlssatz, zelle):
    if befehlssatz == "absolut":
        kandidaten = [tuple(zelle)]
    else:
        kandidaten = [(zelle[0], zelle[1], rich) for rich in ("N", "O", "S", "W")]
    werte = [dist[z] for z in kandidaten if z in dist]
    return min(werte) if werte else None


def _reparatur_unabhaengig(n, start, richtung, waende, ziel, programm, palette):
    """Zählt unabhängig, wie viele Einzel-Ersetzungen von programm crashfrei
    ins Ziel führen; liefert die Liste aller Treffer (pos, befehl)."""
    treffer = []
    for p in range(len(programm)):
        for cmd in palette:
            if cmd == programm[p]:
                continue
            variante = list(programm)
            variante[p] = cmd
            s = _sim_t(n, start, richtung, waende, variante)
            if not s["crash"] and s["ende"] == ziel:
                treffer.append((p, cmd))
    return treffer


# ================================== Programmqualitäts-Regeln, unabhängig nachgerechnet
# Eigene Zweitimplementierung (ohne algo_kern._regel1_erlaubt & Co. zu
# benutzen) der vier Regeln aus der Abnahme-Nachbesserung: nie mehr als zwei
# Drehbefehle hintereinander (zwei nur als Kehrtwende), mindestens die
# Hälfte der Befehle sind Bewegungen, der letzte Befehl ist eine Bewegung,
# Schleifenkörper haben 1..3 Befehle mit mindestens einer Bewegung.

def _qualitaet_flach_t(befehlssatz, flach_liste, ausnahme_index=None):
    """Prüft Regel 1-3 auf einer flachen Befehlsliste. ausnahme_index (nur
    reparieren) markiert den einen Befehl, der von den Regeln abweichen
    darf: die Liste wird dort in zwei unabhängig zu prüfende Teile
    zerschnitten (die Position selbst gehört zu keinem der beiden Teile)."""
    teile = [flach_liste] if ausnahme_index is None else [
        flach_liste[:ausnahme_index], flach_liste[ausnahme_index + 1:]]
    for teil in teile:
        letzter = None
        lauf = 0
        for b in teil:
            dreh = befehlssatz == "relativ" and b in ("L", "R")
            if dreh:
                if lauf == 0:
                    passt = True
                elif lauf == 1:
                    passt = (b == letzter)
                else:
                    passt = False
                if not passt:
                    return False, f"Regel 1: '{b}' darf nicht auf '{letzter}' folgen"
                lauf += 1
            else:
                if befehlssatz == "absolut" and letzter is not None and _GEGENSATZ_T.get(letzter) == b:
                    return False, f"Regel 1: Gegenrichtung '{b}' direkt nach '{letzter}'"
                lauf = 0
            letzter = b
    relevante = [i for i in range(len(flach_liste)) if i != ausnahme_index]
    if relevante:
        bewegungen = sum(1 for i in relevante if befehlssatz == "absolut" or flach_liste[i] == "V")
        mindest = -(-len(relevante) // 2)
        if bewegungen < mindest:
            return False, f"Regel 2: nur {bewegungen}/{len(relevante)} Bewegungen, nötig {mindest}"
    letzter_index = len(flach_liste) - 1
    if ausnahme_index != letzter_index:
        letzter_befehl = flach_liste[letzter_index]
        if befehlssatz != "absolut" and letzter_befehl != "V":
            return False, f"Regel 3: letzter Befehl '{letzter_befehl}' ist keine Bewegung"
    return True, None


def _qualitaet_schleifen_t(befehlssatz, programm):
    """Regel 4: jeder Schleifenkörper hat 1..3 Befehle mit mind. 1 Bewegung."""
    for b in programm or []:
        if isinstance(b, dict):
            koerper = b.get("b") or []
            if not (1 <= len(koerper) <= 3):
                return False, f"Regel 4: Schleifenkörper hat {len(koerper)} Befehle"
            bewegungen = sum(1 for x in koerper if befehlssatz == "absolut" or x == "V")
            if bewegungen < 1:
                return False, "Regel 4: Schleifenkörper ohne Bewegung"
    return True, None


# ============================================ erzeuge_befolgen (Modus "ziel", ohne Schleife)

_BEFOLGEN_TABELLE = {
    3: dict(n=4, befehlssatz="absolut", laenge=(3, 5), waende=(0, 2)),
    4: dict(n=5, befehlssatz="relativ", laenge=(4, 6), waende=(1, 3)),
}


def befolgen_serie(stufe, anzahl_seeds):
    zeile = _BEFOLGEN_TABELLE[stufe]
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        for schwierigkeit in range(6):
            geprueft += 1
            aufgabe = A.erzeuge_befolgen(stufe, seed * 97 + schwierigkeit, schwierigkeit)
            fehler = _pruefe_befolgen_aufgabe(aufgabe, zeile)
            if fehler:
                erster_fehler = erster_fehler or f"seed={seed} schwierigkeit={schwierigkeit}: {fehler}"
            else:
                bestanden += 1
    return geprueft, bestanden, erster_fehler


def _pruefe_befolgen_aufgabe(a, zeile):
    if a.get("type") != "roboter" or a.get("modus") != "ziel":
        return "type/modus falsch"
    if "ziel" in a:
        return "Feld 'ziel' darf im Modus 'ziel' nicht vorkommen"
    if a["n"] != zeile["n"] or a["befehlssatz"] != zeile["befehlssatz"]:
        return "n oder befehlssatz weicht von der Staffel-Tabelle ab"
    programm = a["programm"]
    if any(isinstance(b, dict) for b in programm):
        return "algo_befolgen darf keine Schleife enthalten"
    if not (zeile["laenge"][0] <= len(programm) <= zeile["laenge"][1]):
        return f"Programmlänge {len(programm)} außerhalb {zeile['laenge']}"
    if not (zeile["waende"][0] <= len(a["waende"]) <= zeile["waende"][1]):
        return f"Wandanzahl {len(a['waende'])} außerhalb {zeile['waende']}"
    ok_q, grund_q = _qualitaet_flach_t(a["befehlssatz"], programm)
    if not ok_q:
        return f"Programmqualität unabhängig verletzt: {grund_q}"
    sim = _sim_t(a["n"], a["start"], a["richtung"], a["waende"], programm)
    if sim["crash"]:
        return "unabhängige Simulation crasht"
    if sim["ende"] != a["loesung"]["ende"] or sim["richtung"] != a["loesung"]["richtung"]:
        return "unabhängige Simulation stimmt nicht mit loesung überein"
    if sim["ende"] == a["start"]:
        return "Ende gleich Start ist bei algo_befolgen (Stufe ≤ 5) nicht erlaubt"
    ok_check, grund = A.pruefe_roboter(a)
    if not ok_check:
        return f"pruefe_roboter lehnt eigene Aufgabe ab: {grund}"
    return None


for _stufe in (3, 4):
    _geprueft, _bestanden, _fehler = befolgen_serie(_stufe, 45)
    ok(f"{_geprueft} erzeuge_befolgen@{_stufe}: crashfrei, Ende stimmt, Größen in der Spanne",
       _geprueft == _bestanden and _geprueft >= 40, _fehler)

_a1 = A.erzeuge_befolgen(4, 2026, 3)
_a2 = A.erzeuge_befolgen(4, 2026, 3)
ok("erzeuge_befolgen: gleicher Seed liefert byte-gleiche Aufgabe", _a1 == _a2)
ok("erzeuge_befolgen: unterschiedlicher Seed liefert eine andere Aufgabe",
   A.erzeuge_befolgen(4, 2027, 3) != _a1)


# ========================================== erzeuge_finden (Modus "programm", kürzeste Lösung)

_FINDEN_TABELLE = {
    4: dict(n=5, befehlssatz="absolut", kuerzeste=(3, 5), waende=(2, 4)),
    5: dict(n=5, befehlssatz="relativ", kuerzeste=(4, 7), waende=(2, 4)),
}


def finden_serie(stufe, anzahl_seeds):
    zeile = _FINDEN_TABELLE[stufe]
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        for schwierigkeit in range(6):
            geprueft += 1
            aufgabe = A.erzeuge_finden(stufe, seed * 131 + schwierigkeit, schwierigkeit)
            fehler = _pruefe_finden_aufgabe(aufgabe, zeile)
            if fehler:
                erster_fehler = erster_fehler or f"seed={seed} schwierigkeit={schwierigkeit}: {fehler}"
            else:
                bestanden += 1
    return geprueft, bestanden, erster_fehler


def _pruefe_finden_aufgabe(a, zeile):
    if a.get("type") != "roboter" or a.get("modus") != "programm":
        return "type/modus falsch"
    if "programm" in a:
        return "Feld 'programm' darf im Modus 'programm' nicht vorkommen"
    if a["n"] != zeile["n"] or a["befehlssatz"] != zeile["befehlssatz"]:
        return "n oder befehlssatz weicht von der Staffel-Tabelle ab"
    if not (zeile["kuerzeste"][0] <= a["max_laenge"] <= zeile["kuerzeste"][1]):
        return f"max_laenge {a['max_laenge']} außerhalb {zeile['kuerzeste']}"
    if not (zeile["waende"][0] <= len(a["waende"]) <= zeile["waende"][1]):
        return f"Wandanzahl {len(a['waende'])} außerhalb {zeile['waende']}"
    beispiel = a["loesung"]["beispiel"]
    if len(beispiel) != a["max_laenge"]:
        return "loesung.beispiel hat nicht genau max_laenge Befehle"
    ok_q, grund_q = _qualitaet_flach_t(a["befehlssatz"], beispiel)
    if not ok_q:
        return f"Programmqualität von loesung.beispiel unabhängig verletzt: {grund_q}"
    sim = _sim_t(a["n"], a["start"], a["richtung"], a["waende"], beispiel)
    if sim["crash"] or sim["ende"] != a["ziel"]:
        return "loesung.beispiel erreicht das Ziel nicht crashfrei (unabhängige Simulation)"
    dist = _bfs_t(a["n"], a["start"], a["richtung"], a["waende"], a["befehlssatz"])
    kuerzeste = _kuerzeste_t(dist, a["befehlssatz"], a["ziel"])
    if kuerzeste != a["max_laenge"]:
        return f"unabhängige BFS findet kürzeste Länge {kuerzeste}, max_laenge={a['max_laenge']}"
    wand_menge = {tuple(w) for w in a["waende"]}
    if not any((a["ziel"][0] + dr, a["ziel"][1] + dc) in wand_menge for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))):
        return "keine Wand grenzt an das Ziel bzw. den kürzesten Pfad"
    ok_check, grund = A.pruefe_roboter(a)
    if not ok_check:
        return f"pruefe_roboter lehnt eigene Aufgabe ab: {grund}"
    return None


for _stufe in (4, 5):
    _geprueft, _bestanden, _fehler = finden_serie(_stufe, 45)
    ok(f"{_geprueft} erzeuge_finden@{_stufe}: kürzeste Lösung per unabhängiger BFS bestätigt",
       _geprueft == _bestanden and _geprueft >= 40, _fehler)

_a1 = A.erzeuge_finden(5, 2026, 4)
_a2 = A.erzeuge_finden(5, 2026, 4)
ok("erzeuge_finden: gleicher Seed liefert byte-gleiche Aufgabe", _a1 == _a2)


# ========================================== erzeuge_reparieren (Modus "reparieren")

_REPARIEREN_TABELLE = {
    5: dict(n=5, laenge=(5, 7), waende=(1, 3)),
    6: dict(n=6, laenge=(7, 9), waende=(2, 4)),
}
_REPARIEREN_PALETTE = ("V", "L", "R")


def reparieren_serie(stufe, anzahl_seeds):
    zeile = _REPARIEREN_TABELLE[stufe]
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        for schwierigkeit in range(6):
            geprueft += 1
            aufgabe = A.erzeuge_reparieren(stufe, seed * 151 + schwierigkeit, schwierigkeit)
            fehler = _pruefe_reparieren_aufgabe(aufgabe, zeile)
            if fehler:
                erster_fehler = erster_fehler or f"seed={seed} schwierigkeit={schwierigkeit}: {fehler}"
            else:
                bestanden += 1
    return geprueft, bestanden, erster_fehler


def _pruefe_reparieren_aufgabe(a, zeile):
    if a.get("type") != "roboter" or a.get("modus") != "reparieren":
        return "type/modus falsch"
    if a["befehlssatz"] != "relativ" or a["n"] != zeile["n"]:
        return "n oder befehlssatz weicht von der Staffel-Tabelle ab"
    programm = a["programm"]
    if any(isinstance(b, dict) for b in programm):
        return "algo_reparieren darf keine Schleife enthalten"
    if not (zeile["laenge"][0] <= len(programm) <= zeile["laenge"][1]):
        return f"Programmlänge {len(programm)} außerhalb {zeile['laenge']}"
    if not (zeile["waende"][0] <= len(a["waende"]) <= zeile["waende"][1]):
        return f"Wandanzahl {len(a['waende'])} außerhalb {zeile['waende']}"
    base = _sim_t(a["n"], a["start"], a["richtung"], a["waende"], programm)
    if not base["crash"] and base["ende"] == a["ziel"]:
        return "das gegebene (kaputte) Programm erreicht das Ziel bereits"
    loesung = a["loesung"]
    ok_q, grund_q = _qualitaet_flach_t(a["befehlssatz"], programm, ausnahme_index=loesung["index"])
    if not ok_q:
        return f"kaputtes Programm weicht nicht nur an der Fehlerstelle von der Programmqualität ab: {grund_q}"
    korrigiert = list(programm)
    korrigiert[loesung["index"]] = loesung["ersatz"]
    ok_q2, grund_q2 = _qualitaet_flach_t(a["befehlssatz"], korrigiert)
    if not ok_q2:
        return f"repariertes Programm verletzt die Programmqualität: {grund_q2}"
    treffer = _reparatur_unabhaengig(a["n"], a["start"], a["richtung"], a["waende"], a["ziel"],
                                      programm, _REPARIEREN_PALETTE)
    if len(treffer) != 1:
        return f"unabhängig gezählt: {len(treffer)} Einzel-Ersetzungen führen ins Ziel, erwartet genau 1"
    if treffer[0] != (loesung["index"], loesung["ersatz"]):
        return "die unabhängig gefundene einzige Reparatur stimmt nicht mit loesung überein"
    ok_check, grund = A.pruefe_roboter(a)
    if not ok_check:
        return f"pruefe_roboter lehnt eigene Aufgabe ab: {grund}"
    return None


for _stufe in (5, 6):
    _geprueft, _bestanden, _fehler = reparieren_serie(_stufe, 45)
    ok(f"{_geprueft} erzeuge_reparieren@{_stufe}: Eindeutigkeit unabhängig nachgezählt",
       _geprueft == _bestanden and _geprueft >= 40, _fehler)

_a1 = A.erzeuge_reparieren(6, 2026, 2)
_a2 = A.erzeuge_reparieren(6, 2026, 2)
ok("erzeuge_reparieren: gleicher Seed liefert byte-gleiche Aufgabe", _a1 == _a2)


# ============================================= erzeuge_schleife (Modus "ziel", mit Schleife(n))

def _schleifenanzahl(programm):
    return sum(1 for b in programm if isinstance(b, dict))


def _erwartete_schleifenanzahl(stufe, schwierigkeit):
    if stufe == 6:
        return 1
    return 2 if schwierigkeit >= 3 else 1


def _erwarteter_befehlssatz(stufe, schwierigkeit):
    if stufe == 6:
        return "absolut" if schwierigkeit <= 2 else "relativ"
    return "relativ"


_SCHLEIFE_TABELLE = {
    6: dict(n=6, laenge=(6, 12), waende=(1, 3)),
    7: dict(n=6, laenge=(8, 14), waende=(2, 4)),
}


def schleife_serie(stufe, anzahl_seeds):
    zeile = _SCHLEIFE_TABELLE[stufe]
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        for schwierigkeit in range(6):
            geprueft += 1
            aufgabe = A.erzeuge_schleife(stufe, seed * 181 + schwierigkeit, schwierigkeit)
            fehler = _pruefe_schleife_aufgabe(aufgabe, zeile, stufe, schwierigkeit)
            if fehler:
                erster_fehler = erster_fehler or f"seed={seed} schwierigkeit={schwierigkeit}: {fehler}"
            else:
                bestanden += 1
    return geprueft, bestanden, erster_fehler


def _pruefe_schleife_aufgabe(a, zeile, stufe, schwierigkeit):
    if a.get("type") != "roboter" or a.get("modus") != "ziel":
        return "type/modus falsch"
    if "ziel" in a:
        return "Feld 'ziel' darf im Modus 'ziel' nicht vorkommen"
    if a["n"] != zeile["n"]:
        return "n weicht von der Staffel-Tabelle ab"
    if a["befehlssatz"] != _erwarteter_befehlssatz(stufe, schwierigkeit):
        return "befehlssatz weicht von der erwarteten Staffel-Regel ab"
    programm = a["programm"]
    anzahl = _schleifenanzahl(programm)
    if anzahl != _erwartete_schleifenanzahl(stufe, schwierigkeit):
        return f"{anzahl} Schleifen im Programm, erwartet {_erwartete_schleifenanzahl(stufe, schwierigkeit)}"
    for b in programm:
        if isinstance(b, dict):
            if not (2 <= b["x"] <= 4):
                return f"Schleifenfaktor {b['x']} außerhalb 2..4"
            if any(isinstance(bb, dict) for bb in b["b"]):
                return "verschachtelte Schleife gefunden"
    flache_liste = _flach_t(programm)
    flache_laenge = len(flache_liste)
    if not (zeile["laenge"][0] <= flache_laenge <= zeile["laenge"][1]):
        return f"flache Länge {flache_laenge} außerhalb {zeile['laenge']}"
    if not (zeile["waende"][0] <= len(a["waende"]) <= zeile["waende"][1]):
        return f"Wandanzahl {len(a['waende'])} außerhalb {zeile['waende']}"
    ok_q4, grund_q4 = _qualitaet_schleifen_t(a["befehlssatz"], programm)
    if not ok_q4:
        return f"Programmqualität (Schleifenkörper) unabhängig verletzt: {grund_q4}"
    ok_q, grund_q = _qualitaet_flach_t(a["befehlssatz"], flache_liste)
    if not ok_q:
        return f"Programmqualität unabhängig verletzt: {grund_q}"
    sim = _sim_t(a["n"], a["start"], a["richtung"], a["waende"], programm)
    if sim["crash"]:
        return "unabhängige Simulation crasht"
    if sim["ende"] != a["loesung"]["ende"] or sim["richtung"] != a["loesung"]["richtung"]:
        return "unabhängige Simulation stimmt nicht mit loesung überein"
    ok_check, grund = A.pruefe_roboter(a)
    if not ok_check:
        return f"pruefe_roboter lehnt eigene Aufgabe ab: {grund}"
    return None


for _stufe in (6, 7):
    _geprueft, _bestanden, _fehler = schleife_serie(_stufe, 45)
    ok(f"{_geprueft} erzeuge_schleife@{_stufe}: Schleifenanzahl/-form, flache Länge, Simulation stimmen",
       _geprueft == _bestanden and _geprueft >= 40, _fehler)

_a1 = A.erzeuge_schleife(7, 2026, 4)
_a2 = A.erzeuge_schleife(7, 2026, 4)
ok("erzeuge_schleife: gleicher Seed liefert byte-gleiche Aufgabe", _a1 == _a2)


# ============================================= pruefe_roboter: absichtlich kaputte Aufgaben
# pruefe_roboter() MUSS jede dieser Aufgaben ablehnen – handgebaut, nicht aus
# einem Erzeuger, damit die Prüfung wirklich unabhängig von den Erzeugern ist.

_ZIEL_BASIS = {
    "type": "roboter", "modus": "ziel", "n": 4,
    "start": [0, 0], "richtung": "O", "waende": [],
    "befehlssatz": "absolut", "programm": ["O", "O"],
    "loesung": {"ende": [0, 2], "richtung": "O"},
}
ok_check, _ = A.pruefe_roboter(_ZIEL_BASIS)
ok("Referenz-Aufgabe (Basis der kaputten Fälle) ist selbst gültig", ok_check)

_PROGRAMM_BASIS = {
    "type": "roboter", "modus": "programm", "n": 4,
    "start": [0, 0], "richtung": "O", "waende": [], "ziel": [0, 2],
    "befehlssatz": "absolut", "max_laenge": 2,
    "loesung": {"beispiel": ["O", "O"]},
}
ok_check, _ = A.pruefe_roboter(_PROGRAMM_BASIS)
ok("Referenz-Aufgabe (programm-Modus) ist selbst gültig", ok_check)

_REPARIEREN_BASIS = {
    "type": "roboter", "modus": "reparieren", "n": 4,
    "start": [0, 0], "richtung": "O", "waende": [], "ziel": [0, 2],
    "befehlssatz": "absolut", "programm": ["O", "N"],
    "loesung": {"index": 1, "ersatz": "O"},
}
ok_check, _ = A.pruefe_roboter(_REPARIEREN_BASIS)
ok("Referenz-Aufgabe (reparieren-Modus) ist selbst gültig", ok_check)


def _mutiere(basis, **aenderungen):
    kopie = dict(basis)
    kopie.update(aenderungen)
    return kopie


_KAPUTTE_FAELLE = []


def kaputt(name, aufgabe):
    _KAPUTTE_FAELLE.append((name, aufgabe))


kaputt("falsches Ende in loesung (ziel-Modus)",
       _mutiere(_ZIEL_BASIS, loesung={"ende": [0, 3], "richtung": "O"}))
kaputt("Wand auf dem Startfeld",
       _mutiere(_ZIEL_BASIS, waende=[[0, 0]]))
kaputt("ziel-Feld ist im Modus 'ziel' vorhanden (verrät die Antwort)",
       _mutiere(_ZIEL_BASIS, ziel=[0, 2]))
kaputt("Programm im Modus 'ziel' crasht (Wand mitten im Pfad)",
       _mutiere(_ZIEL_BASIS, waende=[[0, 1]]))
kaputt("unbekannter Befehl im Programm",
       _mutiere(_ZIEL_BASIS, programm=["O", "X"]))
kaputt("verschachtelte Schleife (Schleife im Schleifenkörper)",
       _mutiere(_ZIEL_BASIS, programm=[{"x": 2, "b": [{"x": 2, "b": ["O"]}]}],
                loesung={"ende": [0, 4], "richtung": "O"}))
kaputt("Schleifenfaktor außerhalb 2..4",
       _mutiere(_ZIEL_BASIS, programm=[{"x": 5, "b": ["O"]}],
                loesung={"ende": [0, 5], "richtung": "O"}))
kaputt("leerer Schleifenkörper",
       _mutiere(_ZIEL_BASIS, programm=[{"x": 2, "b": []}],
                loesung={"ende": [0, 0], "richtung": "O"}))
kaputt("drei Schleifen auf oberster Ebene (erlaubt sind höchstens zwei)",
       _mutiere(_ZIEL_BASIS, n=6, start=[0, 0],
                programm=[{"x": 2, "b": ["O"]}, {"x": 2, "b": ["O"]}, {"x": 2, "b": ["N"]}],
                loesung={"ende": [0, 4], "richtung": "O"}))
kaputt("max_laenge kommt im Modus 'ziel' nicht vor",
       _mutiere(_ZIEL_BASIS, max_laenge=2))
kaputt("n außerhalb 4..6",
       _mutiere(_ZIEL_BASIS, n=8))
kaputt("start außerhalb des Gitters",
       _mutiere(_ZIEL_BASIS, start=[9, 9]))
kaputt("unbekannte Blickrichtung",
       _mutiere(_ZIEL_BASIS, richtung="NO"))
kaputt("unbekannter befehlssatz",
       _mutiere(_ZIEL_BASIS, befehlssatz="diagonal"))

kaputt("programm-Feld ist im Modus 'programm' vorhanden (Kind soll es selbst bauen)",
       _mutiere(_PROGRAMM_BASIS, programm=["O", "O"]))
kaputt("ziel liegt auf einer Wand (programm-Modus)",
       _mutiere(_PROGRAMM_BASIS, waende=[[0, 2]]))
kaputt("max_laenge zu groß (programm-Modus)",
       _mutiere(_PROGRAMM_BASIS, max_laenge=4, loesung={"beispiel": ["O", "S", "O", "N"]}))
kaputt("max_laenge zu klein (loesung.beispiel passt nicht mehr zur Länge)",
       _mutiere(_PROGRAMM_BASIS, max_laenge=1))
kaputt("loesung.beispiel crasht (programm-Modus)",
       _mutiere(_PROGRAMM_BASIS, waende=[[0, 1]]))
kaputt("loesung.beispiel erreicht ein falsches Feld (programm-Modus)",
       _mutiere(_PROGRAMM_BASIS, loesung={"beispiel": ["O", "N"]}))

kaputt("Schleife im Modus 'reparieren' (dort nur flache Befehle erlaubt)",
       _mutiere(_REPARIEREN_BASIS, programm=[{"x": 2, "b": ["O"]}, "N"]))
kaputt("kaputtes Programm erreicht das Ziel bereits selbst",
       _mutiere(_REPARIEREN_BASIS, programm=["O", "O"]))
kaputt("loesung.ersatz ist derselbe wie der vorhandene Befehl",
       _mutiere(_REPARIEREN_BASIS, loesung={"index": 1, "ersatz": "N"}))
kaputt("loesung.index liegt außerhalb des Programms",
       _mutiere(_REPARIEREN_BASIS, loesung={"index": 9, "ersatz": "O"}))
kaputt("angegebene Reparatur führt selbst nicht ins Ziel",
       _mutiere(_REPARIEREN_BASIS, loesung={"index": 0, "ersatz": "N"}))
kaputt("zweite gültige Reparatur existiert (Eindeutigkeit verletzt)", {
    "type": "roboter", "modus": "reparieren", "n": 4,
    "start": [0, 0], "richtung": "N", "waende": [], "ziel": [2, 0],
    "befehlssatz": "relativ", "programm": ["R", "L", "V", "V"],
    "loesung": {"index": 0, "ersatz": "L"},
    # Der Fehler lässt sich nicht eindeutig verorten: sowohl (0,'L') als auch
    # (1,'R') reparieren ["R","L","V","V"] qualitätskonform bis ans Ziel.
})

# ------------------------------------ Programmqualitäts-Regeln (Abnahme-Nachbesserung)
# Eine eigene, relative Basisaufgabe (Regel 1 betrifft bei "absolut" nur die
# Gegenrichtung, für die Dreh-Lauflängen-Fälle wird "relativ" gebraucht).
_ZIEL_BASIS_RELATIV = {
    "type": "roboter", "modus": "ziel", "n": 4,
    "start": [0, 0], "richtung": "S", "waende": [],
    "befehlssatz": "relativ", "programm": ["V", "V"],
    "loesung": {"ende": [2, 0], "richtung": "S"},
}
ok_check, _ = A.pruefe_roboter(_ZIEL_BASIS_RELATIV)
ok("Referenz-Aufgabe (relativ, Basis der Qualitäts-Fälle) ist selbst gültig", ok_check)

kaputt("Regel 1: drei Drehbefehle hintereinander (R,R,R)",
       _mutiere(_ZIEL_BASIS_RELATIV, programm=["V", "R", "R", "R", "V"]))
kaputt("Regel 3: letzter Befehl ist eine Drehung statt einer Bewegung",
       _mutiere(_ZIEL_BASIS_RELATIV, programm=["V", "V", "R"]))
kaputt("Regel 4: Schleifenkörper ohne jede Bewegung",
       _mutiere(_ZIEL_BASIS_RELATIV, programm=[{"x": 2, "b": ["L", "L"]}]))
kaputt("Regel 2: Programm mit nur einer Bewegung unter fünf Befehlen",
       _mutiere(_ZIEL_BASIS_RELATIV, programm=["L", "L", "V", "R", "R"]))

for _name, _aufgabe in _KAPUTTE_FAELLE:
    _ergebnis, _grund = A.pruefe_roboter(_aufgabe)
    ok(f"pruefe_roboter lehnt ab: {_name}", _ergebnis is False, _grund if _ergebnis else "")

ok(f"mindestens 10 absichtlich kaputte Roboter-Fälle wurden getestet", len(_KAPUTTE_FAELLE) >= 10,
   str(len(_KAPUTTE_FAELLE)))

# pruefe_roboter darf auch an völlig wirren Eingaben nicht abstürzen.
for _wirr in (None, {}, {"type": "roboter"}, {"type": "anders", "modus": "ziel"}, "kaputt", 42, []):
    try:
        _ergebnis, _grund = A.pruefe_roboter(_wirr)
        ok(f"pruefe_roboter stürzt nicht ab bei wirrer Eingabe {_wirr!r}", _ergebnis is False)
    except Exception as e:
        ok(f"pruefe_roboter stürzt nicht ab bei wirrer Eingabe {_wirr!r}", False, repr(e))


# =================================================================== Zahlenmaschine
# Eigene, von algo_kern._werte_regel/_regelfamilie_iter unabhängige Zweit-
# implementierung: Regel auswerten (kein eval), Term bauen, Regelfamilie
# vollständig durchzählen.

def _werte_regel_t(form, a, b, x):
    if form == "plus":
        return x + b
    if form == "mal":
        return x * a
    if form == "mal_plus":
        return x * a + b
    if form == "plus_mal":
        return (x + b) * a
    raise ValueError(f"unbekannte Form {form!r}")


def _regelfamilie_t():
    for b in range(1, 10):
        yield ("plus", None, b)
    for a in range(2, 6):
        yield ("mal", a, None)
    for a in (2, 3):
        for b in range(1, 6):
            yield ("mal_plus", a, b)
    for a in (2, 3):
        for b in range(1, 5):
            yield ("plus_mal", a, b)


def _term_vorwaerts_t(form, a, b, x):
    if form == "plus":
        return f"{x}+{b}"
    if form == "mal":
        return f"{x}*{a}"
    if form == "mal_plus":
        return f"{x}*{a}+{b}"
    if form == "plus_mal":
        return f"({x}+{b})*{a}"
    raise ValueError


def _term_umkehr_t(form, a, b, y):
    if form == "plus":
        return f"{y}-{b}"
    if form == "mal":
        return f"{y}/{a}"
    if form == "mal_plus":
        return f"({y}-{b})/{a}"
    if form == "plus_mal":
        return f"{y}/{a}-{b}"
    raise ValueError


def _pruefe_maschine_aufgabe(m, stufe, schwierigkeit):
    regel = m["regel"]
    form, a, b = regel["form"], regel["a"], regel["b"]
    if stufe == 5 and form == "plus_mal":
        return "Form 'plus_mal' darf erst ab Stufe 6 vorkommen"
    erwartetes_umkehr = stufe == 6 and schwierigkeit >= 3
    if m["umkehr"] != erwartetes_umkehr:
        return f"umkehr={m['umkehr']}, erwartet {erwartetes_umkehr} (Stufe {stufe}, Schwierigkeit {schwierigkeit})"

    paare = m["paare"]
    if len(paare) != 3:
        return "paare hat nicht genau 3 Einträge"
    for x, y in paare:
        if not (1 <= x <= 12):
            return f"x={x} außerhalb 1..12"
        if y > 60:
            return f"y={y} über 60"
        if _werte_regel_t(form, a, b, x) != y:
            return f"Paar [{x},{y}] passt nicht zur angegebenen Regel (unabhängig ausgewertet)"

    treffer = [kandidat for kandidat in _regelfamilie_t()
               if all(_werte_regel_t(*kandidat, x) == y for x, y in paare)]
    if len(treffer) != 1:
        return f"unabhängig gezählt: {len(treffer)} Regeln passen zu den drei Paaren, erwartet genau 1"
    if treffer[0] != (form, a, b):
        return "die unabhängig gefundene eindeutige Regel stimmt nicht mit regel überein"

    antwort = m["antwort"]
    if not m["umkehr"]:
        frage_x = m["frage_x"]
        if not (1 <= frage_x <= 12):
            return f"frage_x={frage_x} außerhalb 1..12"
        erwartete_antwort = _werte_regel_t(form, a, b, frage_x)
        if erwartete_antwort > 60:
            return "antwort liegt über 60"
        if antwort != erwartete_antwort:
            return "antwort stimmt nicht mit der unabhängig ausgewerteten Regel überein"
        erwarteter_term = _term_vorwaerts_t(form, a, b, frage_x)
        if m["term"] != erwarteter_term:
            return f"term={m['term']!r} != unabhängig gebaut {erwarteter_term!r}"
        if frage_x in [p[0] for p in paare]:
            return "frage_x taucht schon unter den drei Beispiel-Eingaben auf"
    else:
        frage_y = m["frage_y"]
        if frage_y > 60:
            return "frage_y liegt über 60"
        if not (1 <= antwort <= 12):
            return f"antwort={antwort} außerhalb 1..12"
        if _werte_regel_t(form, a, b, antwort) != frage_y:
            return "antwort löst frage_y nicht unter der unabhängig ausgewerteten Regel"
        erwarteter_term = _term_umkehr_t(form, a, b, frage_y)
        if m["term"] != erwarteter_term:
            return f"term={m['term']!r} != unabhängig gebaut {erwarteter_term!r}"

    ablenker = m["ablenker"]
    if len(ablenker) != 3:
        return "ablenker hat nicht genau 3 Einträge"
    if antwort in ablenker:
        return "ein Ablenker ist gleich der Antwort"
    if len(set(ablenker)) != 3:
        return "die Ablenker sind nicht paarweise verschieden"

    ok_check, grund = A.pruefe_maschine(m)
    if not ok_check:
        return f"pruefe_maschine lehnt eigene Aufgabe ab: {grund}"
    return None


def maschine_serie(stufe, anzahl_seeds):
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        for schwierigkeit in range(6):
            geprueft += 1
            m = A.erzeuge_maschine(stufe, seed * 223 + schwierigkeit, schwierigkeit)
            fehler = _pruefe_maschine_aufgabe(m, stufe, schwierigkeit)
            if fehler:
                erster_fehler = erster_fehler or f"seed={seed} schwierigkeit={schwierigkeit}: {fehler}"
            else:
                bestanden += 1
    return geprueft, bestanden, erster_fehler


for _stufe in (5, 6):
    _geprueft, _bestanden, _fehler = maschine_serie(_stufe, 45)
    ok(f"{_geprueft} erzeuge_maschine@{_stufe}: Eindeutigkeit unabhängig durchgezählt, Term neu gebaut",
       _geprueft == _bestanden and _geprueft >= 40, _fehler)

_m1 = A.erzeuge_maschine(6, 2026, 4)
_m2 = A.erzeuge_maschine(6, 2026, 4)
ok("erzeuge_maschine: gleicher Seed liefert byte-gleiche Aufgabe", _m1 == _m2)
ok("erzeuge_maschine: unterschiedlicher Seed liefert eine andere Aufgabe",
   A.erzeuge_maschine(6, 2027, 4) != _m1)


# =================================================== pruefe_maschine: absichtlich kaputte Fälle

_MASCHINE_BASIS = {
    "regel": {"form": "plus", "a": None, "b": 3},
    "paare": [[1, 4], [2, 5], [3, 6]],
    "umkehr": False, "frage_x": 5, "antwort": 8, "term": "5+3",
    "ablenker": [5, 9, 11],
}
ok_check, _ = A.pruefe_maschine(_MASCHINE_BASIS)
ok("Referenz-Maschine (Basis der kaputten Fälle) ist selbst gültig", ok_check)

_MASCHINE_UMKEHR_BASIS = {
    "regel": {"form": "mal_plus", "a": 2, "b": 1},
    "paare": [[2, 5], [3, 7], [4, 9]],
    "umkehr": True, "frage_y": 13, "antwort": 6, "term": "(13-1)/2",
    "ablenker": [13, 7, 8],
}
ok_check, _ = A.pruefe_maschine(_MASCHINE_UMKEHR_BASIS)
ok("Referenz-Maschine (umkehr) stimmt mit dem SPEC-Beispiel '(13-1)/2' überein und ist gültig", ok_check)


def _mutiere_m(basis, **aenderungen):
    kopie = {k: (dict(v) if isinstance(v, dict) else v) for k, v in basis.items()}
    kopie.update(aenderungen)
    return kopie


_KAPUTTE_MASCHINEN = []


def kaputt_m(name, maschine):
    _KAPUTTE_MASCHINEN.append((name, maschine))


kaputt_m("Paar widerspricht der angegebenen Regel",
          _mutiere_m(_MASCHINE_BASIS, paare=[[1, 4], [2, 5], [3, 99]]))
kaputt_m("unbekannte Regelform",
          _mutiere_m(_MASCHINE_BASIS, regel={"form": "minus", "a": None, "b": 3}))
kaputt_m("Parameter a außerhalb des erlaubten Bereichs",
          _mutiere_m(_MASCHINE_BASIS, regel={"form": "mal", "a": 99, "b": None},
                     paare=[[1, 99], [2, 198], [3, 297]]))
kaputt_m("mehrdeutig: drei Paare passen zu zwei Regeln (mal_plus 2,2 und plus_mal 2,1)",
          {"regel": {"form": "mal_plus", "a": 2, "b": 2}, "paare": [[1, 4], [2, 6], [3, 8]],
           "umkehr": False, "frage_x": 5, "antwort": 12, "term": "5*2+2", "ablenker": [10, 7, 13]})
kaputt_m("term stimmt nicht mit Regel/Frage überein",
          _mutiere_m(_MASCHINE_BASIS, term="5+4"))
kaputt_m("antwort stimmt nicht mit der Regel überein",
          _mutiere_m(_MASCHINE_BASIS, antwort=9))
kaputt_m("ein Ablenker ist gleich der Antwort",
          _mutiere_m(_MASCHINE_BASIS, ablenker=[8, 9, 11]))
kaputt_m("Ablenker sind nicht paarweise verschieden",
          _mutiere_m(_MASCHINE_BASIS, ablenker=[5, 5, 11]))
kaputt_m("frage_y ist vorhanden, obwohl umkehr=false",
          _mutiere_m(_MASCHINE_BASIS, frage_y=8))
kaputt_m("frage_x ist vorhanden, obwohl umkehr=true",
          _mutiere_m(_MASCHINE_UMKEHR_BASIS, frage_x=5))
kaputt_m("Ausgabe eines Paars liegt über 60",
          _mutiere_m(_MASCHINE_BASIS, regel={"form": "plus", "a": None, "b": 9},
                     paare=[[1, 10], [2, 11], [55, 64]]))
kaputt_m("frage_x liegt außerhalb 1..12",
          _mutiere_m(_MASCHINE_BASIS, frage_x=20, antwort=23, term="20+3"))
kaputt_m("nur 2 statt 3 Paare",
          _mutiere_m(_MASCHINE_BASIS, paare=[[1, 4], [2, 5]]))

for _name, _maschine in _KAPUTTE_MASCHINEN:
    _ergebnis, _grund = A.pruefe_maschine(_maschine)
    ok(f"pruefe_maschine lehnt ab: {_name}", _ergebnis is False, _grund if _ergebnis else "")

ok("mindestens 10 absichtlich kaputte Zahlenmaschinen wurden getestet", len(_KAPUTTE_MASCHINEN) >= 10,
   str(len(_KAPUTTE_MASCHINEN)))

for _wirr in (None, {}, {"regel": {}}, "kaputt", 42, []):
    try:
        _ergebnis, _grund = A.pruefe_maschine(_wirr)
        ok(f"pruefe_maschine stürzt nicht ab bei wirrer Eingabe {_wirr!r}", _ergebnis is False)
    except Exception as e:
        ok(f"pruefe_maschine stürzt nicht ab bei wirrer Eingabe {_wirr!r}", False, repr(e))


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
