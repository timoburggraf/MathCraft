# -*- coding: utf-8 -*-
"""Der deterministische Algorithmik-Kern für die Denkschule (SPEC_lektionen_v2.md, §2).

Zwei Aufgabenfamilien, nach demselben Grundprinzip wie raetsel_kern.py:
der Kern entscheidet zuerst, was wahr ist, und ein Sprachmodell darf später
höchstens noch die Geschichte drumherum erzählen (die Frage "q" und den
Hinweistext "hint" – beides liefert dieses Modul bewusst NICHT).

  1. Roboter auf dem Gitter – flach() / simuliere() / erzeuge_befolgen() /
     erzeuge_finden() / erzeuge_reparieren() / erzeuge_schleife() /
     pruefe_roboter()
     Ein Roboter steht auf einem n×n-Gitter und folgt einem Programm aus
     Befehlen (absolut N/O/S/W oder relativ V/L/R, wahlweise mit
     Wiederholungen). Drei Modi: "ziel" (Programm gegeben, Endfeld
     erraten – auch mit Schleifen), "programm" (aus einer Befehlspalette
     selbst ein Programm zum Ziel bauen) und "reparieren" (den einen
     falschen Befehl in einem gegebenen Programm finden). Wie im gesamten
     Projekt gilt: der Generator würfelt einen Kandidaten und lässt ihn
     anschließend von pruefe_roboter() – demselben Prüfer, der auch fertige
     Aufgaben aus der Datenbank absichern muss – vollständig nachrechnen.
     Fällt die Prüfung durch, wird verworfen und neu gewürfelt (Deckel 500
     Versuche, danach ValueError statt eines stillen Fehlers). So kann eine
     Garantie nie auseinanderlaufen zwischen "wie erzeugt" und "wie geprüft".

  2. Zahlenmaschine – erzeuge_maschine() / pruefe_maschine()
     Eine Maschine wendet eine geheime Rechenregel (x+b, x·a, x·a+b oder,
     ab Stufe 6, (x+b)·a) auf drei Beispiel-Eingaben an; aus den drei
     Ein-/Ausgabe-Paaren soll die Regel erschlossen und auf eine neue
     Eingabe (oder – ab Stufe 6 bei hoher Schwierigkeit – rückwärts auf
     eine neue Ausgabe) angewendet werden. Eindeutigkeit wird nicht
     behauptet, sondern nachgezählt: über die GESAMTE Regelfamilie (alle
     vier Formen mit allen erlaubten Parametern, unabhängig von der
     erzeugenden Stufe – das ist die schärfere, stufenunabhängige Prüfung
     und deckt automatisch auch die Stufe-3/4/5-Fälle mit ab) darf genau
     eine Kombination zu den drei vorgegebenen Paaren passen.

Beide Familien sind reiner Standardbibliotheks-Code, vollständig seedbar
über random.Random(seed): derselbe Seed liefert byte-gleich dieselbe
Aufgabe. Kein LLM, kein eval(), kein hash(). Die Erzeuger liefern
Aufgaben OHNE Textfelder ("q"/"hint" – die kommen aus kern_pakete.py);
alle wahrheitstragenden Strukturfelder aus SPEC §2 sind aber vollständig
vorhanden, denn genau die prüft pruefe_roboter()/pruefe_maschine() nach.
"""
import random
from collections import deque


# ============================================================ Grundlagen

RICHTUNGEN = ("N", "O", "S", "W")

# Richtungsvektoren (Zeile, Spalte): Zeile 0 = oben, Spalte 0 = links.
_VEKTOR = {"N": (-1, 0), "O": (0, 1), "S": (1, 0), "W": (0, -1)}
_GEGENSATZ = {"N": "S", "S": "N", "O": "W", "W": "O"}
# 'L' dreht gegen den Uhrzeigersinn (N→W→S→O→N), 'R' im Uhrzeigersinn.
_LINKS = {"N": "W", "W": "S", "S": "O", "O": "N"}
_RECHTS = {"N": "O", "O": "S", "S": "W", "W": "N"}


def flach(programm):
    """Löst Schleifen {"x":k, "b":[...]} auf: der Körper k-mal hintereinander.

    Rekursiv, damit auch eine (laut SPEC eigentlich nicht vorgesehene)
    verschachtelte Schleife nicht zum Absturz führt, sondern einfach
    korrekt ausgerollt wird – pruefe_roboter() lehnt Verschachtelung separat
    als Strukturfehler ab, flach() selbst soll aber nie crashen.
    """
    ergebnis = []
    for befehl in (programm or []):
        if isinstance(befehl, dict) and isinstance(befehl.get("b"), list):
            for _ in range(befehl.get("x", 0) or 0):
                ergebnis.extend(flach(befehl["b"]))
        else:
            ergebnis.append(befehl)
    return ergebnis


def simuliere(n, start, richtung, waende, programm):
    """Führt ein (ggf. noch verschachteltes) Programm aus – exakt dieselbe
    Semantik wie robSchritte()/simuliereRoboter() in src/app.html:

      - 'V' bewegt in aktuelle Blickrichtung, 'L'/'R' drehen ohne zu bewegen.
      - Ein absoluter Befehl X bewegt in Richtung X und X wird neue
        Blickrichtung.
      - Zug auf eine Wand oder aus dem Gitter = Crash: die Simulation
        bricht sofort ab, die Position bleibt das letzte gültige Feld.
      - Felder dürfen mehrfach betreten werden.

    Verträgt kaputte Eingaben (unbekannter Befehl, kaputte Wandliste): so
    etwas wird als Crash gewertet statt eine Ausnahme zu werfen – simuliere()
    selbst ist keine Validierung, das übernimmt pruefe_roboter().

    Rückgabe: {"pfad":[[r,c],...] (beginnt mit start), "ende":[r,c],
    "richtung":…, "crash":bool}.
    """
    try:
        wand = {(r, c) for r, c in (waende or [])}
    except (TypeError, ValueError):
        wand = set()
    r, c = start[0], start[1]
    rich = richtung
    pfad = [[r, c]]
    crash = False
    for befehl in flach(programm):
        if befehl == "L":
            rich = _LINKS.get(rich)
            if rich is None:
                crash = True
                break
            continue
        if befehl == "R":
            rich = _RECHTS.get(rich)
            if rich is None:
                crash = True
                break
            continue
        ziel_richtung = rich if befehl == "V" else befehl
        if ziel_richtung not in _VEKTOR:
            crash = True  # unbekannter Befehl – sicherheitshalber ein Crash
            break
        dr, dc = _VEKTOR[ziel_richtung]
        neu_r, neu_c = r + dr, c + dc
        if not (0 <= neu_r < n and 0 <= neu_c < n) or (neu_r, neu_c) in wand:
            crash = True
            break
        r, c, rich = neu_r, neu_c, ziel_richtung
        pfad.append([r, c])
    return {"pfad": pfad, "ende": [r, c], "richtung": rich, "crash": crash}


def _interpoliere_stufe(bereich, schwierigkeit):
    """Bildet schwierigkeit (0..5) linear auf eine ganze Zahl zwischen dem
    unteren und dem oberen Ende von bereich=(unten, oben) ab. round() ist
    hier unkritisch: es ist eine monoton wachsende Funktion, egal wie an
    exakten .5-Stellen gerundet wird, bleibt die Staffel aufsteigend.
    """
    unten, oben = bereich
    schwierigkeit = max(0, min(5, schwierigkeit))
    return unten + round((oben - unten) * schwierigkeit / 5.0)


# ================================================== Programmqualität (Abnahme-Nachbesserung 03.09.2026)
# Rechnerisch korrekte Programme können für ein Kind trotzdem sinnlos
# aussehen: drei Drehungen hintereinander, eine Schleife, die nur dreht, ein
# Programm, das mit einer wirkungslosen Drehung endet. Die folgenden vier
# Regeln machen "sieht wie eine echte Bewegung aus" prüfbar. Sie gelten für
# jedes GEGEBENE Programm (Modus "ziel", "reparieren" – dort für das
# reparierte UND das kaputte Programm, siehe unten – sowie loesung.beispiel
# im Modus "programm") und werden sowohl beim Erzeugen (Neuwürfeln bis
# erfüllt) als auch als harte Prüfung in pruefe_roboter() durchgesetzt.
#
#   Regel 1 – nie mehr als zwei Drehbefehle (L/R) hintereinander, und zwei
#             nur als Kehrtwende (L,L oder R,R); nie L direkt nach R oder
#             umgekehrt. Bei absoluten Befehlen: nie die Gegenrichtung
#             direkt nach einer Richtung.
#   Regel 2 – mindestens die Hälfte der flachen Befehle sind Bewegungen
#             (Bewegungen ≥ aufgerundet die Hälfte der Befehle).
#   Regel 3 – der letzte flache Befehl ist eine Bewegung.
#   Regel 4 – jeder Schleifenkörper hat 1..3 Befehle mit mindestens einer
#             Bewegung; Regel 1 gilt über Schleifengrenzen hinweg im flachen
#             Programm – dafür reicht es, Regel 1 auf flach(programm)
#             anzuwenden, eine gesonderte Prüfung an den Grenzen erübrigt
#             sich dadurch.

def _regel1_erlaubt(befehlssatz, letzter, dreh_lauf, befehl):
    """True, wenn 'befehl' laut Regel 1 direkt auf 'letzter' folgen darf.
    dreh_lauf = Länge des noch laufenden Drehbefehl-Laufs unmittelbar VOR
    'befehl' (0, wenn der letzte Befehl eine Bewegung war oder noch keiner
    vorlag). Dieselbe Funktion trägt sowohl die inkrementellen Erzeuger (die
    einen Kandidaten verwerfen, wenn False) als auch die Kürzeste-Wege-Suche
    für erzeuge_finden (die nur erlaubte Kanten besucht)."""
    if befehlssatz == "absolut":
        return letzter is None or _GEGENSATZ.get(letzter) != befehl
    if befehl in ("L", "R"):
        if dreh_lauf == 0:
            return True
        if dreh_lauf == 1:
            return befehl == letzter  # zwei nur als Kehrtwende (L,L oder R,R)
        return False  # ein dritter Drehbefehl in Folge ist nie erlaubt
    return True  # 'V' darf immer folgen


def _regel1_naechster_lauf(befehlssatz, dreh_lauf, befehl):
    """Aktualisiert dreh_lauf, NACHDEM befehl angehängt wurde."""
    if befehlssatz == "relativ" and befehl in ("L", "R"):
        return dreh_lauf + 1
    return 0


def _regel1_ok(befehlssatz, flach_liste, ausnahme_index=None):
    """Prüft Regel 1 auf einer flachen Befehlsliste. ausnahme_index (nur bei
    reparieren gesetzt) markiert den einen Befehl, der laut Aufgabenstellung
    falsch sein darf: die Liste wird an dieser Stelle in zwei Teile
    zerschnitten (davor / danach – die Position selbst gehört zu keinem der
    beiden Teile), und JEDER Teil muss für sich genommen sauber sein.
    Regelverstöße dürfen also ausschließlich Paare oder Läufe betreffen, die
    den kaputten Befehl selbst enthalten."""
    if ausnahme_index is None:
        teile = [flach_liste]
    else:
        teile = [flach_liste[:ausnahme_index], flach_liste[ausnahme_index + 1:]]
    for teil in teile:
        letzter = None
        dreh_lauf = 0
        for befehl in teil:
            if not _regel1_erlaubt(befehlssatz, letzter, dreh_lauf, befehl):
                return False, f"'{befehl}' darf nicht direkt auf '{letzter}' folgen"
            dreh_lauf = _regel1_naechster_lauf(befehlssatz, dreh_lauf, befehl)
            letzter = befehl
    return True, None


def _regel2_ok(befehlssatz, flach_liste, ausnahme_index=None):
    """Regel 2 (Bewegungen ≥ aufgerundet die halbe Länge), ausgewertet OHNE
    die Ausnahme-Position (weder im Zähler noch im Nenner): der eine kaputte
    Befehl darf selbst dafür verantwortlich sein, dass die reine Zahl knapp
    nicht reicht, aber der ÜBRIGE Teil des Programms muss die Regel für sich
    genommen weiterhin erfüllen."""
    relevante = [i for i in range(len(flach_liste)) if i != ausnahme_index]
    if not relevante:
        return True, None
    bewegungen = sum(1 for i in relevante if befehlssatz == "absolut" or flach_liste[i] == "V")
    mindest = -(-len(relevante) // 2)  # Aufrunden ohne math.ceil
    if bewegungen < mindest:
        return False, f"nur {bewegungen} von {len(relevante)} Befehlen sind Bewegungen, nötig sind mindestens {mindest}"
    return True, None


def _regel3_ok(befehlssatz, flach_liste, ausnahme_index=None):
    """Regel 3 (letzter Befehl ist eine Bewegung) – entfällt, wenn genau die
    letzte Position der kaputte Befehl ist."""
    letzter_index = len(flach_liste) - 1
    if ausnahme_index == letzter_index:
        return True, None
    letzter = flach_liste[letzter_index]
    if befehlssatz != "absolut" and letzter != "V":
        return False, f"letzter Befehl '{letzter}' ist keine Bewegung"
    return True, None


def _regel4_ok(befehlssatz, programm):
    """Regel 4 (nur im Modus "ziel" relevant, wo Schleifen vorkommen dürfen):
    jeder Schleifenkörper hat 1..3 Befehle mit mindestens einer Bewegung."""
    for befehl in programm or []:
        if isinstance(befehl, dict):
            koerper = befehl.get("b") or []
            if not (1 <= len(koerper) <= 3):
                return False, f"Schleifenkörper hat {len(koerper)} Befehle, erlaubt sind 1..3"
            bewegungen = sum(1 for b in koerper if befehlssatz == "absolut" or b == "V")
            if bewegungen < 1:
                return False, "Schleifenkörper enthält keine Bewegung"
    return True, None


def _pruefe_qualitaet(befehlssatz, programm, ausnahme_index=None, schleifen_erlaubt=False):
    """Prüft die Regeln 1-4 (Programmqualität) zusammen. 'programm' darf bei
    schleifen_erlaubt=True noch verschachtelt sein (Modus "ziel"); sonst wird
    eine bereits flache Liste erwartet (reparieren, loesung.beispiel).
    ausnahme_index bezieht sich immer auf die FLACHE Darstellung – bei
    reparieren/beispiel ist "programm" ohnehin schon flach, der Index
    entspricht also direkt dem im rohen Programm. Rückgabe: (True, None)
    oder (False, Grund)."""
    if schleifen_erlaubt:
        ok4, grund4 = _regel4_ok(befehlssatz, programm)
        if not ok4:
            return False, f"Regel 4 (Schleifenkörper): {grund4}"
        flach_liste = flach(programm)
    else:
        flach_liste = list(programm or [])
    if not flach_liste:
        return False, "Programm ist leer"
    ok1, grund1 = _regel1_ok(befehlssatz, flach_liste, ausnahme_index)
    if not ok1:
        return False, f"Regel 1 (Drehbefehle/Gegenrichtung): {grund1}"
    ok2, grund2 = _regel2_ok(befehlssatz, flach_liste, ausnahme_index)
    if not ok2:
        return False, f"Regel 2 (mindestens halb Bewegungen): {grund2}"
    ok3, grund3 = _regel3_ok(befehlssatz, flach_liste, ausnahme_index)
    if not ok3:
        return False, f"Regel 3 (letzter Befehl ist Bewegung): {grund3}"
    return True, None


# ================================================================== Modus "ziel": Befehle befolgen

def _baue_flache_folge(rng, n, start, richtung, befehlssatz, laenge):
    """Würfelt eine flache Befehlsfolge der gewünschten Länge, die garantiert
    crashfrei im n×n-Gitter bleibt (Wände kommen erst danach dazu und werden
    abseits des so entstandenen Pfads platziert) und alle Programmqualitäts-
    Regeln erfüllt: Regel 1 wird bei jedem Kandidaten inkrementell erzwungen,
    'V' wird bei "relativ" bevorzugt gewürfelt (hilft Regel 2), und der
    LETZTE Befehl wird bei "relativ" auf 'V' erzwungen (Regel 3 – bei
    "absolut" ist ohnehin jeder Befehl eine Bewegung, Regel 2 und 3 sind dort
    automatisch erfüllt).

    Liefert (befehle, pfad, end_richtung) oder None, wenn das mit den bisher
    gezogenen Zufallszahlen nicht in vertretbar vielen Versuchen klappt; der
    Aufrufer würfelt dann Start/Richtung neu statt hier endlos zu kreisen.
    """
    ist_relativ = befehlssatz == "relativ"
    palette = ["V", "L", "R"] if ist_relativ else ["N", "O", "S", "W"]
    gewichte = (3, 1, 1) if ist_relativ else None
    r, c, rich = start[0], start[1], richtung
    befehle = []
    pfad = [[r, c]]
    dreh_lauf = 0
    letzter = None
    versuche = 0
    grenze = laenge * 80 + 80
    while len(befehle) < laenge:
        versuche += 1
        if versuche > grenze:
            return None
        letzter_schritt = ist_relativ and len(befehle) == laenge - 1
        if letzter_schritt:
            b = "V"  # Regel 3: der letzte Befehl muss eine Bewegung sein
        elif ist_relativ:
            b = rng.choices(palette, weights=gewichte, k=1)[0]
        else:
            b = rng.choice(palette)
        if not _regel1_erlaubt(befehlssatz, letzter, dreh_lauf, b):
            if letzter_schritt:
                return None  # 'V' ist von Regel 1 nie verboten – nur sicherheitshalber
            continue
        if b in ("L", "R"):
            rich = _LINKS[rich] if b == "L" else _RECHTS[rich]
            dreh_lauf = _regel1_naechster_lauf(befehlssatz, dreh_lauf, b)
            letzter = b
            befehle.append(b)
            continue
        ziel_richtung = rich if b == "V" else b
        dr, dc = _VEKTOR[ziel_richtung]
        neu_r, neu_c = r + dr, c + dc
        if not (0 <= neu_r < n and 0 <= neu_c < n):
            if letzter_schritt:
                return None  # der erzwungene letzte 'V' ist hier blockiert
            continue
        r, c, rich = neu_r, neu_c, ziel_richtung
        dreh_lauf = _regel1_naechster_lauf(befehlssatz, dreh_lauf, b)
        letzter = b
        befehle.append(b)
        pfad.append([r, c])

    # Regel 1 ist bereits inkrementell garantiert, Regel 3 durch den
    # erzwungenen letzten Befehl (bzw. automatisch bei "absolut") – nur
    # Regel 2 (Bewegungs-Quote) ist eine globale Eigenschaft und wird hier
    # am fertigen Ergebnis geprüft.
    ok2, _ = _regel2_ok(befehlssatz, befehle)
    if not ok2:
        return None
    return befehle, pfad, rich


# Denktiefe-Staffel für erzeuge_befolgen (SPEC §2, Tabelle "algo_befolgen").
_BEFOLGEN_STAFFEL = {
    3: dict(n=4, befehlssatz="absolut", laenge=(3, 5), waende=(0, 2)),
    4: dict(n=5, befehlssatz="relativ", laenge=(4, 6), waende=(1, 3)),
}


def erzeuge_befolgen(stufe, seed, schwierigkeit):
    """Modus "ziel" ohne Schleife (Fertigkeit algo_befolgen, Stufe 3 oder 4):
    ein fertiges Programm ausführen und das Feld finden, auf dem der Roboter
    hält. Ende ≠ Start ist hier Pflicht (Stufe ≤ 5) – sonst wäre "0 Schritte
    gehen" eine gültige, aber witzlose Lösung.
    """
    zeile = _BEFOLGEN_STAFFEL.get(stufe)
    if zeile is None:
        raise ValueError(f"erzeuge_befolgen: unbekannte Stufe {stufe!r} (erwartet 3 oder 4)")
    n, befehlssatz = zeile["n"], zeile["befehlssatz"]
    ziel_laenge = _interpoliere_stufe(zeile["laenge"], schwierigkeit)
    ziel_waende = _interpoliere_stufe(zeile["waende"], schwierigkeit)

    rng = random.Random(seed)
    for _ in range(500):
        start = [rng.randrange(n), rng.randrange(n)]
        richtung = rng.choice(RICHTUNGEN)
        ergebnis = _baue_flache_folge(rng, n, start, richtung, befehlssatz, ziel_laenge)
        if ergebnis is None:
            continue
        befehle, pfad, end_richtung = ergebnis
        ende = pfad[-1]
        if ende == start:
            continue
        pfad_zellen = {(p[0], p[1]) for p in pfad}
        freie_zellen = [(zr, zc) for zr in range(n) for zc in range(n) if (zr, zc) not in pfad_zellen]
        if len(freie_zellen) < ziel_waende:
            continue
        rng.shuffle(freie_zellen)
        waende = [list(z) for z in freie_zellen[:ziel_waende]]

        aufgabe = {
            "type": "roboter", "modus": "ziel", "n": n,
            "start": start, "richtung": richtung, "waende": waende,
            "befehlssatz": befehlssatz, "programm": befehle,
            "loesung": {"ende": ende, "richtung": end_richtung},
        }
        ok, _ = pruefe_roboter(aufgabe)
        if ok:
            return aufgabe
    raise ValueError(f"erzeuge_befolgen: kein gültiges Rätsel nach 500 Versuchen (Stufe {stufe}, seed {seed})")


# ============================================================ Modus "programm": den Weg programmieren

def _nachbarn(n, wand, befehlssatz, zustand):
    """Gemeinsame Nachbarfunktion für alle Zustandsraum-Suchen (Vorwärts-BFS
    für die kürzeste Distanz, Rückwärts-BFS und Backtracking für die
    qualitätsbewusste Pfadsuche): liefert (neuer_zustand, benutzter_befehl)
    für jeden gültigen Zug aus zustand."""
    if befehlssatz == "absolut":
        r, c = zustand
        for rich in RICHTUNGEN:
            dr, dc = _VEKTOR[rich]
            nr, nc = r + dr, c + dc
            if 0 <= nr < n and 0 <= nc < n and (nr, nc) not in wand:
                yield (nr, nc), rich
    else:
        r, c, rich = zustand
        dr, dc = _VEKTOR[rich]
        nr, nc = r + dr, c + dc
        if 0 <= nr < n and 0 <= nc < n and (nr, nc) not in wand:
            yield (nr, nc, rich), "V"
        yield (r, c, _LINKS[rich]), "L"
        yield (r, c, _RECHTS[rich]), "R"


def _bfs_zustaende(n, start, richtung, waende, befehlssatz):
    """Breitensuche über den Zustandsraum: bei "absolut" ist ein Zustand ein
    Feld, bei "relativ" ist es (Feld, Blickrichtung) – jeder Befehl (auch
    Drehen) kostet genau 1, SPEC §2. Liefert (distanz, herkunft,
    start_zustand); herkunft[z] = (vorgänger_zustand, benutzter_befehl) für
    die Rekonstruktion einer kürzesten Befehlsfolge.
    """
    wand = {(r, c) for r, c in (waende or [])}
    start_zustand = (start[0], start[1]) if befehlssatz == "absolut" else (start[0], start[1], richtung)

    distanz = {start_zustand: 0}
    herkunft = {}
    warteschlange = deque([start_zustand])
    while warteschlange:
        z = warteschlange.popleft()
        for nz, befehl in _nachbarn(n, wand, befehlssatz, z):
            if nz not in distanz:
                distanz[nz] = distanz[z] + 1
                herkunft[nz] = (z, befehl)
                warteschlange.append(nz)
    return distanz, herkunft, start_zustand


def _kuerzeste_distanz_zu_zelle(distanz, befehlssatz, zelle):
    """Kürzeste Distanz zu einer Gitterzelle: bei "relativ" das Minimum über
    alle vier möglichen Blickrichtungen am Ziel. None, wenn unerreichbar.
    """
    if befehlssatz == "absolut":
        kandidaten = [(zelle[0], zelle[1])]
    else:
        kandidaten = [(zelle[0], zelle[1], rich) for rich in RICHTUNGEN]
    werte = [distanz[z] for z in kandidaten if z in distanz]
    return min(werte) if werte else None


def _dist_zum_ziel_states(n, wand, befehlssatz, dist_von_start, ziel_zustaende):
    """Rückwärts-BFS: Distanz von JEDEM erreichbaren Zustand BIS zu einem der
    ziel_zustaende, im ORIGINALEN gerichteten Zustandsgraphen. Technik: Kanten
    umkehren und von den Zielzuständen aus suchen – das liefert in einem
    Durchgang die Distanz-zum-Ziel für alle Zustände, ohne für jeden
    Startkandidaten eine eigene Vorwärtssuche zu brauchen."""
    rueckwaerts = {}
    for z in dist_von_start:
        for nz, _b in _nachbarn(n, wand, befehlssatz, z):
            rueckwaerts.setdefault(nz, []).append(z)
    dist = {}
    warteschlange = deque()
    for zz in ziel_zustaende:
        if zz in dist_von_start and zz not in dist:
            dist[zz] = 0
            warteschlange.append(zz)
    while warteschlange:
        z = warteschlange.popleft()
        for vz in rueckwaerts.get(z, []):
            if vz not in dist:
                dist[vz] = dist[z] + 1
                warteschlange.append(vz)
    return dist


def _kuerzeste_qualitaetsbefehle_zu_zelle(n, waende, befehlssatz, start_zustand, dist_von_start,
                                           ziel, max_laenge, rng):
    """Sucht unter ALLEN kürzesten Lösungen (Länge genau max_laenge) zur
    Zielzelle eine, die zusätzlich Regel 1 und 2 erfüllt. Regel 3 ist bei
    JEDER kürzesten Lösung automatisch erfüllt: der distanzminimale
    Zielzustand kann nie über eine Drehung erreicht worden sein – sonst wäre
    schon sein Vorgänger (dieselbe Zelle, andere Blickrichtung) ein
    Zielzustand mit kleinerer Distanz gewesen, und genau der wäre gewählt
    worden. Backtracking über den Kürzeste-Wege-DAG (nur Kanten, die auf
    irgendeinem kürzesten Weg liegen): bei "absolut" ist ohnehin JEDE
    kürzeste Lösung automatisch regelkonform (zwei Gegenrichtungen
    hintereinander wären nie kürzeste, denn beide zusammen strichen ergäben
    einen um 2 kürzeren Weg), die Suche findet dort also sofort einen
    Treffer. None, wenn keine kürzeste Lösung dieser exakten Länge alle
    Regeln erfüllt (der Aufrufer probiert dann ein anderes Gitter).
    """
    wand = {(r, c) for r, c in waende}
    if befehlssatz == "absolut":
        ziel_zustaende = {(ziel[0], ziel[1])}
    else:
        ziel_zustaende = {(ziel[0], ziel[1], rich) for rich in RICHTUNGEN}
    ziel_zustaende = {z for z in ziel_zustaende if z in dist_von_start}
    if not ziel_zustaende:
        return None
    dist_zum_ziel = _dist_zum_ziel_states(n, wand, befehlssatz, dist_von_start, ziel_zustaende)
    if dist_zum_ziel.get(start_zustand) != max_laenge:
        return None

    mindest_bewegungen = -(-max_laenge // 2)  # Regel 2, Aufrunden ohne math.ceil
    pfad = []

    def dfs(z, dreh_lauf, letzter, bewegungen):
        if dist_von_start[z] == max_laenge:
            if z in ziel_zustaende and bewegungen >= mindest_bewegungen:
                return list(pfad)
            return None
        kandidaten = []
        for nz, befehl in _nachbarn(n, wand, befehlssatz, z):
            if dist_von_start.get(nz) != dist_von_start[z] + 1:
                continue  # nicht auf einem kürzesten Weg vom Start aus
            if dist_zum_ziel.get(nz) != dist_zum_ziel.get(z, -1) - 1:
                continue  # führt von dort aus nicht mehr auf kürzestem Weg zum Ziel
            if not _regel1_erlaubt(befehlssatz, letzter, dreh_lauf, befehl):
                continue
            kandidaten.append((nz, befehl))
        rng.shuffle(kandidaten)
        for nz, befehl in kandidaten:
            neuer_lauf = _regel1_naechster_lauf(befehlssatz, dreh_lauf, befehl)
            ist_bewegung = befehlssatz == "absolut" or befehl == "V"
            pfad.append(befehl)
            ergebnis = dfs(nz, neuer_lauf, befehl, bewegungen + (1 if ist_bewegung else 0))
            if ergebnis is not None:
                return ergebnis
            pfad.pop()
        return None

    return dfs(start_zustand, 0, None, 0)


# Denktiefe-Staffel für erzeuge_finden (SPEC §2, Tabelle "algo_finden").
_FINDEN_STAFFEL = {
    4: dict(n=5, befehlssatz="absolut", kuerzeste=(3, 5), waende=(2, 4)),
    5: dict(n=5, befehlssatz="relativ", kuerzeste=(4, 7), waende=(2, 4)),
}


def erzeuge_finden(stufe, seed, schwierigkeit):
    """Modus "programm" (Fertigkeit algo_finden, Stufe 4 oder 5): das Kind
    baut selbst ein Programm zum Ziel. max_laenge = Länge der per BFS
    bestimmten kürzesten Lösung; mindestens eine Wand grenzt an diesen
    kürzesten Pfad an, sonst wäre das Hindernis wirkungslos.
    """
    zeile = _FINDEN_STAFFEL.get(stufe)
    if zeile is None:
        raise ValueError(f"erzeuge_finden: unbekannte Stufe {stufe!r} (erwartet 4 oder 5)")
    n, befehlssatz = zeile["n"], zeile["befehlssatz"]
    ziel_kuerzeste = _interpoliere_stufe(zeile["kuerzeste"], schwierigkeit)
    ziel_waende = _interpoliere_stufe(zeile["waende"], schwierigkeit)

    rng = random.Random(seed)
    alle_zellen = [(r, c) for r in range(n) for c in range(n)]
    for _ in range(500):
        start = [rng.randrange(n), rng.randrange(n)]
        richtung = rng.choice(RICHTUNGEN)
        start_t = (start[0], start[1])
        kandidaten_waende = [z for z in alle_zellen if z != start_t]
        if len(kandidaten_waende) < ziel_waende:
            continue
        rng.shuffle(kandidaten_waende)
        waende_zellen = kandidaten_waende[:ziel_waende]
        waende = [list(z) for z in waende_zellen]
        wand_menge = set(waende_zellen)

        distanz, _herkunft, start_zustand = _bfs_zustaende(n, start, richtung, waende, befehlssatz)

        ziel_kandidaten = []
        for (r, c) in alle_zellen:
            if (r, c) == start_t or (r, c) in wand_menge:
                continue
            d = _kuerzeste_distanz_zu_zelle(distanz, befehlssatz, (r, c))
            if d != ziel_kuerzeste:
                continue
            grenzt_an_wand = any(
                (r + dr, c + dc) in wand_menge for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
            )
            if grenzt_an_wand:
                ziel_kandidaten.append((r, c))
        if not ziel_kandidaten:
            continue
        ziel = list(rng.choice(ziel_kandidaten))
        beispiel = _kuerzeste_qualitaetsbefehle_zu_zelle(
            n, waende, befehlssatz, start_zustand, distanz, ziel, ziel_kuerzeste, rng)
        if beispiel is None:
            continue

        aufgabe = {
            "type": "roboter", "modus": "programm", "n": n,
            "start": start, "richtung": richtung, "waende": waende, "ziel": ziel,
            "befehlssatz": befehlssatz, "max_laenge": len(beispiel),
            "loesung": {"beispiel": beispiel},
        }
        ok, _ = pruefe_roboter(aufgabe)
        if ok:
            return aufgabe
    raise ValueError(f"erzeuge_finden: kein gültiges Rätsel nach 500 Versuchen (Stufe {stufe}, seed {seed})")


# =========================================================== Modus "reparieren": Fehler finden

# Denktiefe-Staffel für erzeuge_reparieren (SPEC §2, Tabelle "algo_reparieren").
_REPARIEREN_STAFFEL = {
    5: dict(n=5, laenge=(5, 7), waende=(1, 3)),
    6: dict(n=6, laenge=(7, 9), waende=(2, 4)),
}
_REPARIEREN_PALETTE = ("V", "L", "R")


def erzeuge_reparieren(stufe, seed, schwierigkeit):
    """Modus "reparieren" (Fertigkeit algo_reparieren, Stufe 5 oder 6, immer
    relativ – SPEC-Tabelle): baut ein korrektes, crashfreies Programm P zum
    Ziel, ersetzt genau einen Befehl und sichert per vollständiger
    Enumeration aller Einzel-Ersetzungen ab, dass GENAU diese eine Stelle
    das kaputte Programm repariert – keine andere Ersetzung führt zufällig
    ebenfalls ins Ziel, und das kaputte Programm selbst erreicht es nicht.
    """
    zeile = _REPARIEREN_STAFFEL.get(stufe)
    if zeile is None:
        raise ValueError(f"erzeuge_reparieren: unbekannte Stufe {stufe!r} (erwartet 5 oder 6)")
    n = zeile["n"]
    ziel_laenge = _interpoliere_stufe(zeile["laenge"], schwierigkeit)
    ziel_waende = _interpoliere_stufe(zeile["waende"], schwierigkeit)
    befehlssatz = "relativ"

    rng = random.Random(seed)
    for _ in range(500):
        start = [rng.randrange(n), rng.randrange(n)]
        richtung = rng.choice(RICHTUNGEN)
        ergebnis = _baue_flache_folge(rng, n, start, richtung, befehlssatz, ziel_laenge)
        if ergebnis is None:
            continue
        korrekt, pfad, _end_richtung = ergebnis
        ziel = pfad[-1]
        if ziel == start:
            continue
        ok_qual, _ = _pruefe_qualitaet(befehlssatz, korrekt, ausnahme_index=None, schleifen_erlaubt=False)
        if not ok_qual:
            continue  # _baue_flache_folge garantiert das eigentlich schon – sicherheitshalber trotzdem geprüft
        pfad_zellen = {(p[0], p[1]) for p in pfad}
        freie_zellen = [(r, c) for r in range(n) for c in range(n) if (r, c) not in pfad_zellen]
        if len(freie_zellen) < ziel_waende:
            continue
        rng.shuffle(freie_zellen)
        waende = [list(z) for z in freie_zellen[:ziel_waende]]

        positionen = list(range(len(korrekt)))
        rng.shuffle(positionen)
        for i in positionen:
            ersatz_kandidaten = [x for x in _REPARIEREN_PALETTE if x != korrekt[i]]
            rng.shuffle(ersatz_kandidaten)
            for ersatz in ersatz_kandidaten:
                kaputt = list(korrekt)
                kaputt[i] = ersatz
                ok_qual, _ = _pruefe_qualitaet(befehlssatz, kaputt, ausnahme_index=i, schleifen_erlaubt=False)
                if not ok_qual:
                    continue  # der kaputte Befehl darf NUR an Position i von den Regeln abweichen
                probe = simuliere(n, start, richtung, waende, kaputt)
                if not probe["crash"] and probe["ende"] == ziel:
                    continue  # kaputtes Programm darf das Ziel nicht erreichen

                treffer = []
                for p in range(len(kaputt)):
                    for cmd in _REPARIEREN_PALETTE:
                        if cmd == kaputt[p]:
                            continue
                        variante = list(kaputt)
                        variante[p] = cmd
                        s = simuliere(n, start, richtung, waende, variante)
                        if not s["crash"] and s["ende"] == ziel:
                            treffer.append((p, cmd))
                            if len(treffer) > 1:
                                break
                    if len(treffer) > 1:
                        break
                if len(treffer) != 1 or treffer[0] != (i, korrekt[i]):
                    continue

                aufgabe = {
                    "type": "roboter", "modus": "reparieren", "n": n,
                    "start": start, "richtung": richtung, "waende": waende, "ziel": ziel,
                    "befehlssatz": befehlssatz, "programm": kaputt,
                    "loesung": {"index": i, "ersatz": korrekt[i]},
                }
                ok, _ = pruefe_roboter(aufgabe)
                if ok:
                    return aufgabe
    raise ValueError(f"erzeuge_reparieren: kein gültiges Rätsel nach 500 Versuchen (Stufe {stufe}, seed {seed})")


# =========================================================== Modus "ziel" mit Schleife(n)

class _Bauer:
    """Führt ein Programm schrittweise "live" aus, während es erst noch
    entsteht – mit Schnappschuss/Wiederherstellen, damit ein Schleifenkörper,
    dessen spätere Wiederholungen aus dem Gitter laufen würden, verworfen und
    neu gewürfelt werden kann, ohne die bis dahin gebaute Vorgeschichte zu
    verlieren. Trägt Regel 1 (Drehbefehl-Lauflänge) fortlaufend mit, auch
    über Schleifen-Wiederholungen und Segmentgrenzen hinweg – dieselbe
    Zustandsmaschine wie in _baue_flache_folge.
    """

    def __init__(self, n, start, richtung):
        self.n = n
        self.r, self.c = start[0], start[1]
        self.rich = richtung
        self.pfad = [[self.r, self.c]]
        self.letzter = None
        self.dreh_lauf = 0

    def schnappschuss(self):
        return (self.r, self.c, self.rich, len(self.pfad), self.letzter, self.dreh_lauf)

    def wiederherstellen(self, snap):
        self.r, self.c, self.rich, pfad_laenge, self.letzter, self.dreh_lauf = snap
        del self.pfad[pfad_laenge:]

    def schritt(self, b, befehlssatz):
        """Versucht EINEN Befehl auszuführen. Bei Regel-1-Verstoß oder
        Rand-Crash wird NICHTS verändert – False heißt also immer
        "unverändert, bitte etwas anderes versuchen"."""
        if not _regel1_erlaubt(befehlssatz, self.letzter, self.dreh_lauf, b):
            return False
        if b in ("L", "R"):
            self.rich = _LINKS[self.rich] if b == "L" else _RECHTS[self.rich]
            self.dreh_lauf = _regel1_naechster_lauf(befehlssatz, self.dreh_lauf, b)
            self.letzter = b
            return True
        ziel_richtung = self.rich if b == "V" else b
        dr, dc = _VEKTOR[ziel_richtung]
        neu_r, neu_c = self.r + dr, self.c + dc
        if not (0 <= neu_r < self.n and 0 <= neu_c < self.n):
            return False
        self.r, self.c, self.rich = neu_r, neu_c, ziel_richtung
        self.dreh_lauf = _regel1_naechster_lauf(befehlssatz, self.dreh_lauf, b)
        self.letzter = b
        self.pfad.append([self.r, self.c])
        return True


def _baue_segment(bauer, palette, befehlssatz, laenge, rng, muss_enden_mit_bewegung=False):
    """Baut LIVE (also direkt auf bauer wirkend) ein flaches Segment der
    gewünschten Länge; 'V' wird bei "relativ" bevorzugt gewürfelt (Regel 2),
    und – falls dieses Segment das LETZTE Stück des gesamten Programms wird
    (muss_enden_mit_bewegung) – der letzte Befehl auf 'V' erzwungen
    (Regel 3). Ein einzelner erfolgloser Zug verändert bauer nicht (siehe
    _Bauer.schritt) und wird einfach neu gewürfelt."""
    ist_relativ = befehlssatz == "relativ"
    gewichte = (3, 1, 1) if ist_relativ else None
    befehle = []
    versuche = 0
    grenze = laenge * 80 + 80
    while len(befehle) < laenge:
        versuche += 1
        if versuche > grenze:
            return None
        letzter_schritt = muss_enden_mit_bewegung and ist_relativ and len(befehle) == laenge - 1
        if letzter_schritt:
            b = "V"
        elif ist_relativ:
            b = rng.choices(palette, weights=gewichte, k=1)[0]
        else:
            b = rng.choice(palette)
        if bauer.schritt(b, befehlssatz):
            befehle.append(b)
        elif letzter_schritt:
            return None
    return befehle


def _baue_schleife(bauer, palette, befehlssatz, k, koerper_laenge, rng, max_versuche=200,
                    koerper_muss_enden_mit_bewegung=False):
    """Baut einen Schleifenkörper der Länge koerper_laenge (Regel 4: 1..3
    Befehle mit mindestens einer Bewegung) und prüft sofort, ob er sich
    k-mal hintereinander crashfrei ausführen lässt (die erste Ausführung
    entsteht beim Bauen selbst, k-1 weitere werden als Wiederholung
    desselben Befehlssatzes probiert – Regel 1 gilt dabei automatisch auch
    über die Wiederholungsgrenzen hinweg, weil _Bauer den laufenden
    Drehbefehl-Lauf durchgängig mitführt). Klappt eine Wiederholung nicht
    (Rand erreicht) oder verletzt der Körper Regel 4, wird bauer auf den
    Stand vor dieser Schleife zurückgesetzt und ein neuer Körper versucht."""
    for _ in range(max_versuche):
        snap = bauer.schnappschuss()
        koerper = _baue_segment(bauer, palette, befehlssatz, koerper_laenge, rng,
                                 muss_enden_mit_bewegung=koerper_muss_enden_mit_bewegung)
        if koerper is None:
            bauer.wiederherstellen(snap)
            continue
        bewegungen = sum(1 for b in koerper if befehlssatz == "absolut" or b == "V")
        if bewegungen < 1:
            bauer.wiederherstellen(snap)
            continue
        erfolgreich = True
        for _wiederholung in range(k - 1):
            for b in koerper:
                if not bauer.schritt(b, befehlssatz):
                    erfolgreich = False
                    break
            if not erfolgreich:
                break
        if erfolgreich:
            return koerper
        bauer.wiederherstellen(snap)
    return None


def _plane_schleifen(rng, ziel_laenge, anzahl_schleifen):
    """Sucht eine Zerlegung von ziel_laenge in (optionalen) Vor-/Zwischen-/
    Nachlauf aus flachen Befehlen plus anzahl_schleifen Schleifen mit
    k ∈ {2,3,4} und Körperlänge 1..3 (Regel 4), deren Gesamtlänge nach dem
    Ausrollen exakt ziel_laenge ergibt. Liefert (vorlauf, nachlauf,
    zwischenlauf, [(k, koerper_laenge), ...]) oder None."""
    kombinationen = []
    for vorlauf in range(0, 4):
        for nachlauf in range(0, 4):
            zwischenlaeufe = range(0, 4) if anzahl_schleifen == 2 else [0]
            for zwischenlauf in zwischenlaeufe:
                rest = ziel_laenge - vorlauf - nachlauf - zwischenlauf
                if anzahl_schleifen == 1:
                    for k in (2, 3, 4):
                        if rest >= k and rest % k == 0:
                            koerper_laenge = rest // k
                            if 1 <= koerper_laenge <= 3:  # Regel 4: höchstens 3 Befehle je Körper
                                kombinationen.append((vorlauf, nachlauf, zwischenlauf, [(k, koerper_laenge)]))
                else:
                    for k1 in (2, 3, 4):
                        for k2 in (2, 3, 4):
                            for b1 in range(1, min(rest, 3) + 1):  # Regel 4: höchstens 3 Befehle je Körper
                                verbleibt = rest - k1 * b1
                                if verbleibt <= 0:
                                    continue
                                if verbleibt % k2 == 0:
                                    b2 = verbleibt // k2
                                    if 1 <= b2 <= 3:
                                        kombinationen.append(
                                            (vorlauf, nachlauf, zwischenlauf, [(k1, b1), (k2, b2)])
                                        )
    if not kombinationen:
        return None
    return rng.choice(kombinationen)


def _versuch_schleifenaufgabe(rng, n, befehlssatz, ziel_laenge, ziel_waende, anzahl_schleifen):
    """Ein einzelner Erzeugungsversuch für erzeuge_schleife(): Start/Richtung
    würfeln, Plan für vorlauf/nachlauf/zwischenlauf/Schleifen suchen, live
    ausführen, Wände abseits des entstandenen Pfads platzieren. Liefert eine
    fertige (noch ungeprüfte) Aufgabe oder None."""
    start = [rng.randrange(n), rng.randrange(n)]
    richtung = rng.choice(RICHTUNGEN)
    plan = _plane_schleifen(rng, ziel_laenge, anzahl_schleifen)
    if plan is None:
        return None
    vorlauf, nachlauf, zwischenlauf, schleifen_plan = plan

    palette = ["N", "O", "S", "W"] if befehlssatz == "absolut" else ["V", "L", "R"]
    bauer = _Bauer(n, start, richtung)
    programm = []

    if vorlauf > 0:
        seg = _baue_segment(bauer, palette, befehlssatz, vorlauf, rng)
        if seg is None:
            return None
        programm.extend(seg)

    for idx, (k, koerper_laenge) in enumerate(schleifen_plan):
        # Regel 3 (letzter flacher Befehl ist eine Bewegung) betrifft nur das
        # Segment, das TATSÄCHLICH als Letztes im Programm steht: bei
        # nachlauf > 0 ist das der Nachlauf, sonst der Körper der letzten
        # Schleife (er wird wiederholt, sein letzter Befehl ist also auch
        # der letzte Befehl des gesamten Programms).
        ist_letzte_schleife = idx == len(schleifen_plan) - 1
        koerper_ist_letztes_segment = ist_letzte_schleife and nachlauf == 0
        koerper = _baue_schleife(bauer, palette, befehlssatz, k, koerper_laenge, rng,
                                  koerper_muss_enden_mit_bewegung=koerper_ist_letztes_segment)
        if koerper is None:
            return None
        programm.append({"x": k, "b": koerper})
        if idx < len(schleifen_plan) - 1 and zwischenlauf > 0:
            seg = _baue_segment(bauer, palette, befehlssatz, zwischenlauf, rng)
            if seg is None:
                return None
            programm.extend(seg)

    if nachlauf > 0:
        seg = _baue_segment(bauer, palette, befehlssatz, nachlauf, rng, muss_enden_mit_bewegung=True)
        if seg is None:
            return None
        programm.extend(seg)

    # Regel 1 ist über den ganzen Bauvorgang inkrementell garantiert, Regel 3
    # durch die erzwungenen letzten Befehle oben – nur Regel 2 (die
    # Bewegungs-Quote ÜBER DAS GESAMTE Programm, nicht je Segment) ist eine
    # globale Eigenschaft und wird hier am fertigen, verschachtelten
    # Programm geprüft (schleifen_erlaubt=True löst dafür intern flach()
    # auf).
    ok_qual, _ = _pruefe_qualitaet(befehlssatz, programm, ausnahme_index=None, schleifen_erlaubt=True)
    if not ok_qual:
        return None

    ende = [bauer.r, bauer.c]
    end_richtung = bauer.rich
    pfad_zellen = {(p[0], p[1]) for p in bauer.pfad}
    freie_zellen = [(r, c) for r in range(n) for c in range(n) if (r, c) not in pfad_zellen]
    if len(freie_zellen) < ziel_waende:
        return None
    rng.shuffle(freie_zellen)
    waende = [list(z) for z in freie_zellen[:ziel_waende]]

    return {
        "type": "roboter", "modus": "ziel", "n": n,
        "start": start, "richtung": richtung, "waende": waende,
        "befehlssatz": befehlssatz, "programm": programm,
        "loesung": {"ende": ende, "richtung": end_richtung},
    }


# Denktiefe-Staffel für erzeuge_schleife (SPEC §2, Tabelle "algo_schleife").
# Stufe 6: Index 0-2 absolut, 3-5 relativ, genau 1 Schleife.
# Stufe 7: relativ, 1 Schleife (Schwierigkeit 0-2) oder 2 Schleifen nacheinander (≥3).
def erzeuge_schleife(stufe, seed, schwierigkeit):
    """Modus "ziel" MIT Schleife(n) (Fertigkeit algo_schleife, Stufe 6 oder 7):
    ein Programm mit Wiederholung lesen und das Endfeld vorhersagen. Anders
    als bei algo_befolgen ist "Ende = Start" hier nicht verboten (eine
    Schleife, die exakt zum Ausgangsfeld zurückführt, ist eine legitime,
    sogar besonders lehrreiche Aufgabe) – pruefe_roboter() erkennt an der
    Anwesenheit einer Schleife im Programm, dass diese Ausnahme gilt.
    """
    if stufe == 6:
        n = 6
        befehlssatz = "absolut" if schwierigkeit <= 2 else "relativ"
        laenge_bereich, waende_bereich = (6, 12), (1, 3)
        anzahl_schleifen = 1
    elif stufe == 7:
        n = 6
        befehlssatz = "relativ"
        laenge_bereich, waende_bereich = (8, 14), (2, 4)
        anzahl_schleifen = 2 if schwierigkeit >= 3 else 1
    else:
        raise ValueError(f"erzeuge_schleife: unbekannte Stufe {stufe!r} (erwartet 6 oder 7)")

    ziel_laenge = _interpoliere_stufe(laenge_bereich, schwierigkeit)
    ziel_waende = _interpoliere_stufe(waende_bereich, schwierigkeit)

    rng = random.Random(seed)
    for _ in range(500):
        aufgabe = _versuch_schleifenaufgabe(rng, n, befehlssatz, ziel_laenge, ziel_waende, anzahl_schleifen)
        if aufgabe is None:
            continue
        ok, _ = pruefe_roboter(aufgabe)
        if ok:
            return aufgabe
    raise ValueError(f"erzeuge_schleife: kein gültiges Rätsel nach 500 Versuchen (Stufe {stufe}, seed {seed})")


# =================================================================== Prüfer

def _ist_feld(wert, n):
    """True, wenn wert ein [r, c] mit 0 ≤ r,c < n ist (n selbst geprüft)."""
    if not isinstance(wert, (list, tuple)) or len(wert) != 2:
        return False
    r, c = wert
    return isinstance(r, int) and isinstance(c, int) and 0 <= r < n and 0 <= c < n


def _pruefe_flaches_programm_struktur(programm, palette):
    """Prüft ein Programm, das laut SPEC KEINE Schleifen enthalten darf
    (reparieren, loesung.beispiel): Liste aus Strings der erlaubten Palette,
    sonst wird der Grund als String zurückgegeben (None = alles ok)."""
    if not isinstance(programm, list) or not programm:
        return "Programm ist keine (nichtleere) Liste"
    for befehl in programm:
        if befehl not in palette:
            return f"unbekannter oder unpassender Befehl {befehl!r}"
    return None


def _pruefe_ziel_programm_struktur(programm, palette):
    """Prüft ein Programm im Modus "ziel": flache Befehle der Palette oder
    Schleifen {"x":k,"b":[...]} mit k ∈ 2..4 und nichtleerem, NICHT
    verschachteltem Körper; höchstens zwei Schleifen auf oberster Ebene.
    Liefert (schleifenanzahl, grund) – grund ist None, wenn alles passt."""
    if not isinstance(programm, list) or not programm:
        return 0, "Programm ist keine (nichtleere) Liste"
    anzahl_schleifen = 0
    for befehl in programm:
        if isinstance(befehl, dict):
            anzahl_schleifen += 1
            k = befehl.get("x")
            koerper = befehl.get("b")
            if not isinstance(k, int) or not (2 <= k <= 4):
                return anzahl_schleifen, f"Schleifenfaktor {k!r} außerhalb 2..4"
            if not isinstance(koerper, list) or not koerper:
                return anzahl_schleifen, "Schleifenkörper ist keine (nichtleere) Liste"
            for b in koerper:
                if isinstance(b, dict):
                    return anzahl_schleifen, "verschachtelte Schleife ist nicht erlaubt"
                if b not in palette:
                    return anzahl_schleifen, f"unbekannter Befehl {b!r} im Schleifenkörper"
        elif befehl not in palette:
            return anzahl_schleifen, f"unbekannter Befehl {befehl!r}"
    if anzahl_schleifen > 2:
        return anzahl_schleifen, f"{anzahl_schleifen} Schleifen auf oberster Ebene, erlaubt sind höchstens 2"
    return anzahl_schleifen, None


def pruefe_roboter(aufgabe):
    """Rechnet ALLE Garantien aus SPEC §2 für eine Roboter-Aufgabe nach.
    Verträgt beliebig kaputte Eingaben – liefert immer (bool, grund) statt
    abzustürzen, damit ein fehlerhafter Datensatz nie das Kind erreicht,
    sondern hier hängen bleibt.
    """
    try:
        if not isinstance(aufgabe, dict):
            return False, "Aufgabe ist kein dict"
        if aufgabe.get("type") != "roboter":
            return False, f"type ist {aufgabe.get('type')!r}, erwartet 'roboter'"

        modus = aufgabe.get("modus")
        if modus not in ("ziel", "programm", "reparieren"):
            return False, f"unbekannter modus {modus!r}"

        n = aufgabe.get("n")
        if not isinstance(n, int) or not (4 <= n <= 6):
            return False, f"n={n!r} außerhalb 4..6"

        start = aufgabe.get("start")
        if not _ist_feld(start, n):
            return False, f"start={start!r} ist kein gültiges Feld"

        richtung = aufgabe.get("richtung")
        if richtung not in RICHTUNGEN:
            return False, f"richtung={richtung!r} unbekannt"

        waende = aufgabe.get("waende")
        if not isinstance(waende, list):
            return False, "waende ist keine Liste"
        for w in waende:
            if not _ist_feld(w, n):
                return False, f"Wand {w!r} ist kein gültiges Feld"
        wand_menge = {(w[0], w[1]) for w in waende}
        if (start[0], start[1]) in wand_menge:
            return False, "start liegt auf einer Wand"

        befehlssatz = aufgabe.get("befehlssatz")
        if befehlssatz not in ("absolut", "relativ"):
            return False, f"befehlssatz={befehlssatz!r} unbekannt"
        palette = ["N", "O", "S", "W"] if befehlssatz == "absolut" else ["V", "L", "R"]

        if "max_laenge" in aufgabe and modus != "programm":
            return False, "max_laenge ist nur im modus 'programm' erlaubt"

        # ---------------------------------------------------------- modus "ziel"
        if modus == "ziel":
            if "ziel" in aufgabe:
                return False, "im modus 'ziel' darf das Feld 'ziel' nicht vorkommen (verrät die Antwort)"
            programm = aufgabe.get("programm")
            anzahl_schleifen, grund = _pruefe_ziel_programm_struktur(programm, palette)
            if grund:
                return False, grund
            ok_qual, grund_qual = _pruefe_qualitaet(befehlssatz, programm, ausnahme_index=None, schleifen_erlaubt=True)
            if not ok_qual:
                return False, grund_qual
            ergebnis = simuliere(n, start, richtung, waende, programm)
            if ergebnis["crash"]:
                return False, "Programm crasht"
            loesung = aufgabe.get("loesung")
            if not isinstance(loesung, dict):
                return False, "loesung fehlt oder ist kein dict"
            if loesung.get("ende") != ergebnis["ende"]:
                return False, f"loesung.ende={loesung.get('ende')!r} stimmt nicht mit simuliertem Ende {ergebnis['ende']!r} überein"
            if loesung.get("richtung") != ergebnis["richtung"]:
                return False, "loesung.richtung stimmt nicht mit der simulierten Blickrichtung überein"
            # Ende ≠ Start ist nur bei Stufe ≤ 5 Pflicht; ein Programm ohne
            # Schleife stammt strukturell immer aus algo_befolgen (Stufe 3/4,
            # beide ≤ 5) – ein Programm MIT Schleife immer aus algo_schleife
            # (Stufe 6/7, beide > 5), wo diese Einschränkung laut SPEC entfällt.
            if anzahl_schleifen == 0 and ergebnis["ende"] == start:
                return False, "Ende gleich Start ist ohne Schleife (Stufe ≤ 5) nicht erlaubt"
            return True, "ok"

        # -------------------------------------------------------- modus "programm"
        if modus == "programm":
            if "programm" in aufgabe:
                return False, "im modus 'programm' darf das Feld 'programm' nicht vorkommen (das Kind baut es selbst)"
            ziel = aufgabe.get("ziel")
            if not _ist_feld(ziel, n):
                return False, f"ziel={ziel!r} ist kein gültiges Feld"
            if (ziel[0], ziel[1]) in wand_menge:
                return False, "ziel liegt auf einer Wand"
            if ziel == start:
                return False, "ziel ist gleich start"
            max_laenge = aufgabe.get("max_laenge")
            if not isinstance(max_laenge, int) or max_laenge < 1:
                return False, f"max_laenge={max_laenge!r} ist keine positive ganze Zahl"
            loesung = aufgabe.get("loesung")
            if not isinstance(loesung, dict):
                return False, "loesung fehlt oder ist kein dict"
            beispiel = loesung.get("beispiel")
            grund = _pruefe_flaches_programm_struktur(beispiel, palette)
            if grund:
                return False, f"loesung.beispiel: {grund}"
            if len(beispiel) != max_laenge:
                return False, f"loesung.beispiel hat Länge {len(beispiel)}, max_laenge={max_laenge}"
            ok_qual, grund_qual = _pruefe_qualitaet(befehlssatz, beispiel, ausnahme_index=None, schleifen_erlaubt=False)
            if not ok_qual:
                return False, f"loesung.beispiel: {grund_qual}"
            ergebnis = simuliere(n, start, richtung, waende, beispiel)
            if ergebnis["crash"] or ergebnis["ende"] != ziel:
                return False, "loesung.beispiel erreicht das Ziel nicht crashfrei"
            distanz, _herkunft, _start_zustand = _bfs_zustaende(n, start, richtung, waende, befehlssatz)
            kuerzeste = _kuerzeste_distanz_zu_zelle(distanz, befehlssatz, ziel)
            if kuerzeste is None:
                return False, "ziel ist laut eigener BFS gar nicht erreichbar"
            if kuerzeste != max_laenge:
                return False, f"kürzeste Lösung hat laut BFS Länge {kuerzeste}, max_laenge={max_laenge}"
            return True, "ok"

        # ------------------------------------------------------- modus "reparieren"
        if modus == "reparieren":
            ziel = aufgabe.get("ziel")
            if not _ist_feld(ziel, n):
                return False, f"ziel={ziel!r} ist kein gültiges Feld"
            if (ziel[0], ziel[1]) in wand_menge:
                return False, "ziel liegt auf einer Wand"
            if ziel == start:
                return False, "ziel ist gleich start"
            programm = aufgabe.get("programm")
            grund = _pruefe_flaches_programm_struktur(programm, palette)
            if grund:
                return False, grund
            probe = simuliere(n, start, richtung, waende, programm)
            if not probe["crash"] and probe["ende"] == ziel:
                return False, "das gegebene (kaputte) Programm erreicht das Ziel bereits – nichts zu reparieren"

            loesung = aufgabe.get("loesung")
            if not isinstance(loesung, dict):
                return False, "loesung fehlt oder ist kein dict"
            index = loesung.get("index")
            ersatz = loesung.get("ersatz")
            if not isinstance(index, int) or not (0 <= index < len(programm)):
                return False, f"loesung.index={index!r} außerhalb des Programms"
            if ersatz not in palette or ersatz == programm[index]:
                return False, f"loesung.ersatz={ersatz!r} ist kein anderer gültiger Befehl"

            # Programmqualität: das kaputte Programm darf NUR an Position
            # 'index' von den Regeln abweichen (siehe _pruefe_qualitaet),
            # das reparierte Programm muss sie vollständig erfüllen.
            ok_qual, grund_qual = _pruefe_qualitaet(befehlssatz, programm, ausnahme_index=index, schleifen_erlaubt=False)
            if not ok_qual:
                return False, f"kaputtes Programm weicht nicht nur an der einen Stelle von der Programmqualität ab: {grund_qual}"

            korrigiert = list(programm)
            korrigiert[index] = ersatz
            ok_qual2, grund_qual2 = _pruefe_qualitaet(befehlssatz, korrigiert, ausnahme_index=None, schleifen_erlaubt=False)
            if not ok_qual2:
                return False, f"repariertes Programm verletzt die Programmqualität: {grund_qual2}"
            probe_fix = simuliere(n, start, richtung, waende, korrigiert)
            if probe_fix["crash"] or probe_fix["ende"] != ziel:
                return False, "die angegebene Reparatur führt nicht crashfrei ins Ziel"

            treffer = []
            for p in range(len(programm)):
                for cmd in palette:
                    if cmd == programm[p]:
                        continue
                    variante = list(programm)
                    variante[p] = cmd
                    s = simuliere(n, start, richtung, waende, variante)
                    if not s["crash"] and s["ende"] == ziel:
                        treffer.append((p, cmd))
            if len(treffer) != 1:
                return False, f"{len(treffer)} Einzel-Ersetzungen führen ins Ziel, erwartet genau 1"
            if treffer[0] != (index, ersatz):
                return False, "die eindeutige Reparatur ist nicht (index, ersatz) aus loesung"
            return True, "ok"

        return False, f"unbekannter modus {modus!r}"
    except Exception as e:  # eine kaputte Aufgabe soll hier hängen bleiben, nie crashen
        return False, f"Ausnahme beim Prüfen: {e!r}"


# =========================================================== Zahlenmaschine (SPEC §2)

def _werte_regel(form, a, b, x):
    """Wendet eine Regel der Zahlenmaschine auf x an – reine Arithmetik,
    kein eval(). Dieselbe Funktion wird beim Erzeugen UND beim Prüfen
    benutzt, damit "Regel angewendet" niemals auseinanderlaufen kann."""
    if form == "plus":
        return x + b
    if form == "mal":
        return x * a
    if form == "mal_plus":
        return x * a + b
    if form == "plus_mal":
        return (x + b) * a
    raise ValueError(f"_werte_regel: unbekannte Form {form!r}")


def _baue_term(form, a, b, x=None, y=None, umkehr=False):
    """Baut den Rechenterm für Vorwärts- ("6*2+1") oder Umkehrfragen
    ("(13-1)/2") – rein textuell aus Regel+Frage, ohne jede Berechnung."""
    if not umkehr:
        if form == "plus":
            return f"{x}+{b}"
        if form == "mal":
            return f"{x}*{a}"
        if form == "mal_plus":
            return f"{x}*{a}+{b}"
        if form == "plus_mal":
            return f"({x}+{b})*{a}"
    else:
        if form == "plus":
            return f"{y}-{b}"
        if form == "mal":
            return f"{y}/{a}"
        if form == "mal_plus":
            return f"({y}-{b})/{a}"
        if form == "plus_mal":
            return f"{y}/{a}-{b}"
    raise ValueError(f"_baue_term: unbekannte Form {form!r}")


# Erlaubte Parameterbereiche je Form (SPEC §2). "plus_mal" gibt es erst ab
# Stufe 6 als GEHEIME Regel, zählt aber – gerade weil es die naheliegendste
# Verwechslung mit "mal_plus" ist – IMMER zur Eindeutigkeitsprüfung dazu.
_MASCHINE_BEREICHE = {
    "plus": {"a": (None,), "b": tuple(range(1, 10))},
    "mal": {"a": tuple(range(2, 6)), "b": (None,)},
    "mal_plus": {"a": (2, 3), "b": tuple(range(1, 6))},
    "plus_mal": {"a": (2, 3), "b": tuple(range(1, 5))},
}


def _regelfamilie_iter():
    """Zählt die GESAMTE Regelfamilie vollständig durch – alle vier Formen
    mit allen erlaubten Parametern, unabhängig von der erzeugenden Stufe."""
    for form, bereiche in _MASCHINE_BEREICHE.items():
        for a in bereiche["a"]:
            for b in bereiche["b"]:
                yield form, a, b


def _baue_ablenker(form, a, b, antwort, basis_x=None, basis_y=None, umkehr=False):
    """Baut drei plausible, aber nachweislich falsche Zahlen: Ergebnisse
    naheliegender falscher Regeln (nur x·a, nur x+b, vertauschte Reihenfolge
    von "mal_plus" und "plus_mal"), ergänzt um ±1 – SPEC §2. Rein
    deterministisch (keine eigene Zufallsziehung nötig), damit derselbe
    Aufruf immer dieselben Ablenker liefert."""
    kandidaten = []
    if not umkehr:
        x = basis_x
        if form == "plus":
            kandidaten += [x, x + 2 * b]
        elif form == "mal":
            kandidaten += [x, x * (a + 1)]
        elif form == "mal_plus":
            kandidaten += [x * a, x + b, (x + b) * a]
        elif form == "plus_mal":
            kandidaten += [x * a, x + b, x * a + b]
    else:
        y = basis_y
        if form == "plus":
            kandidaten += [y, y - 2 * b]
        elif form == "mal":
            kandidaten += [y, y // max(a - 1, 1)]
        elif form == "mal_plus":
            kandidaten += [y // a, y - b]
        elif form == "plus_mal":
            kandidaten += [y // a, y - b]

    erweitert = list(kandidaten)
    for k in kandidaten:
        erweitert.append(k + 1)
        erweitert.append(k - 1)
    erweitert.append(antwort + 1)
    erweitert.append(antwort - 1)

    ergebnis = []
    for k in erweitert:
        if k == antwort or k < 0 or k in ergebnis:
            continue
        ergebnis.append(k)
        if len(ergebnis) == 3:
            return ergebnis

    # seltener Randfall: noch nicht genug Kandidaten – deterministisch auffüllen
    versatz = 2
    while len(ergebnis) < 3:
        kandidat = antwort + versatz
        if kandidat != antwort and kandidat >= 0 and kandidat not in ergebnis:
            ergebnis.append(kandidat)
        versatz = -versatz + (1 if versatz > 0 else -1)
    return ergebnis


# Denktiefe-Staffel für erzeuge_maschine: die Fertigkeit algo_maschine liegt
# auf Stufe 5, das zweite Paket (wie bei jeder Fertigkeit) auf Stufe+1 = 6.
_MASCHINE_FORMEN_JE_STUFE = {
    5: ("plus", "mal", "mal_plus"),
    6: ("plus", "mal", "mal_plus", "plus_mal"),
}


def erzeuge_maschine(stufe, seed, schwierigkeit):
    """Zahlenmaschine (Fertigkeit algo_maschine, Stufe 5 oder 6): eine
    geheime Regel wird auf drei Beispiel-Eingaben angewendet; ab Stufe 6
    kommt die Form "plus_mal" dazu, und bei Schwierigkeit ≥ 3 wird die
    Frage umgedreht (Ausgabe gegeben, Eingabe gesucht). Eindeutigkeit wird
    über die GESAMTE Regelfamilie geprüft (siehe _regelfamilie_iter), nicht
    nur über die an dieser Stufe erlaubten Formen – das ist strenger und
    schließt automatisch auch "könnte das nicht auch plus_mal sein?" aus.
    """
    formen = _MASCHINE_FORMEN_JE_STUFE.get(stufe)
    if formen is None:
        raise ValueError(f"erzeuge_maschine: unbekannte Stufe {stufe!r} (erwartet 5 oder 6)")
    umkehr = stufe == 6 and schwierigkeit >= 3

    rng = random.Random(seed)
    for _ in range(500):
        form = rng.choice(formen)
        a = rng.choice(_MASCHINE_BEREICHE[form]["a"])
        b = rng.choice(_MASCHINE_BEREICHE[form]["b"])

        moegliche_x = [x for x in range(1, 13) if _werte_regel(form, a, b, x) <= 60]
        if len(moegliche_x) < 4:  # 3 für die Paare, mindestens 1 für die Frage
            continue
        rng.shuffle(moegliche_x)
        beispiel_x = moegliche_x[:3]
        paare = [[x, _werte_regel(form, a, b, x)] for x in beispiel_x]
        rest_x = moegliche_x[3:]
        if not rest_x:
            continue
        frage_x_kandidat = rng.choice(rest_x)

        m = {"regel": {"form": form, "a": a, "b": b}, "paare": paare, "umkehr": umkehr}
        if not umkehr:
            antwort = _werte_regel(form, a, b, frage_x_kandidat)
            m["frage_x"] = frage_x_kandidat
            m["antwort"] = antwort
            m["term"] = _baue_term(form, a, b, x=frage_x_kandidat, umkehr=False)
            m["ablenker"] = _baue_ablenker(form, a, b, antwort, basis_x=frage_x_kandidat, umkehr=False)
        else:
            antwort_x = frage_x_kandidat
            frage_y = _werte_regel(form, a, b, antwort_x)
            m["frage_y"] = frage_y
            m["antwort"] = antwort_x
            m["term"] = _baue_term(form, a, b, y=frage_y, umkehr=True)
            m["ablenker"] = _baue_ablenker(form, a, b, antwort_x, basis_y=frage_y, umkehr=True)

        ok, _ = pruefe_maschine(m)
        if ok:
            return m
    raise ValueError(f"erzeuge_maschine: kein gültiges Rätsel nach 500 Versuchen (Stufe {stufe}, seed {seed})")


def pruefe_maschine(m):
    """Rechnet ALLE Garantien der Zahlenmaschine nach: die drei Paare passen
    zu genau einem Mitglied der gesamten Regelfamilie (vollständige
    Enumeration, kein eval), der Term wird aus Regel+Frage neu gebaut und
    stringgleich verglichen, alle Ausgaben bleiben ≤ 60, die Ablenker sind
    drei von der Antwort verschiedene, paarweise verschiedene ganze Zahlen.
    Verträgt kaputte Eingaben, stürzt nie ab.
    """
    try:
        if not isinstance(m, dict):
            return False, "Maschine ist kein dict"

        regel = m.get("regel")
        if not isinstance(regel, dict):
            return False, "regel fehlt oder ist kein dict"
        form = regel.get("form")
        a, b = regel.get("a"), regel.get("b")
        bereiche = _MASCHINE_BEREICHE.get(form)
        if bereiche is None:
            return False, f"regel.form={form!r} unbekannt"
        if a not in bereiche["a"]:
            return False, f"regel.a={a!r} außerhalb des erlaubten Bereichs für Form {form!r}"
        if b not in bereiche["b"]:
            return False, f"regel.b={b!r} außerhalb des erlaubten Bereichs für Form {form!r}"

        paare = m.get("paare")
        if not isinstance(paare, list) or len(paare) != 3:
            return False, "paare muss eine Liste von genau 3 Einträgen sein"
        x_werte = []
        for paar in paare:
            if not isinstance(paar, (list, tuple)) or len(paar) != 2:
                return False, f"Paar {paar!r} ist kein [x, y]"
            x, y = paar
            if not isinstance(x, int) or not (1 <= x <= 12):
                return False, f"x={x!r} außerhalb 1..12"
            if not isinstance(y, int) or y > 60:
                return False, f"y={y!r} ist keine ganze Zahl ≤ 60"
            if _werte_regel(form, a, b, x) != y:
                return False, f"Paar [{x},{y}] passt nicht zur angegebenen Regel"
            x_werte.append(x)
        if len(set(x_werte)) != 3:
            return False, "die drei Paare haben nicht drei verschiedene Eingaben x"

        treffer = []
        for f2, a2, b2 in _regelfamilie_iter():
            passt = True
            for x, y in paare:
                if _werte_regel(f2, a2, b2, x) != y:
                    passt = False
                    break
            if passt:
                treffer.append((f2, a2, b2))
        if len(treffer) != 1:
            return False, f"die drei Paare passen zu {len(treffer)} Regeln der Gesamtfamilie, erwartet genau 1"
        if treffer[0] != (form, a, b):
            return False, "die angegebene Regel ist nicht die eindeutig passende"

        umkehr = m.get("umkehr")
        if umkehr not in (True, False):
            return False, f"umkehr={umkehr!r} ist kein bool"
        antwort = m.get("antwort")

        if not umkehr:
            if "frage_y" in m:
                return False, "ohne umkehr darf frage_y nicht vorkommen"
            frage_x = m.get("frage_x")
            if not isinstance(frage_x, int) or not (1 <= frage_x <= 12):
                return False, f"frage_x={frage_x!r} außerhalb 1..12"
            erwartete_antwort = _werte_regel(form, a, b, frage_x)
            if not isinstance(antwort, int) or antwort != erwartete_antwort:
                return False, f"antwort={antwort!r} stimmt nicht mit der Regel überein"
            if antwort > 60:
                return False, "antwort liegt über 60"
            erwarteter_term = _baue_term(form, a, b, x=frage_x, umkehr=False)
            if m.get("term") != erwarteter_term:
                return False, f"term={m.get('term')!r} stimmt nicht mit der neu gebauten Fassung {erwarteter_term!r} überein"
        else:
            if "frage_x" in m:
                return False, "bei umkehr darf frage_x nicht vorkommen"
            frage_y = m.get("frage_y")
            if not isinstance(frage_y, int) or frage_y > 60:
                return False, f"frage_y={frage_y!r} ist keine ganze Zahl ≤ 60"
            if not isinstance(antwort, int) or not (1 <= antwort <= 12):
                return False, f"antwort={antwort!r} außerhalb 1..12"
            if _werte_regel(form, a, b, antwort) != frage_y:
                return False, "antwort löst frage_y nicht unter der angegebenen Regel"
            erwarteter_term = _baue_term(form, a, b, y=frage_y, umkehr=True)
            if m.get("term") != erwarteter_term:
                return False, f"term={m.get('term')!r} stimmt nicht mit der neu gebauten Fassung {erwarteter_term!r} überein"

        ablenker = m.get("ablenker")
        if not isinstance(ablenker, list) or len(ablenker) != 3:
            return False, "ablenker muss eine Liste von genau 3 Einträgen sein"
        for wert in ablenker:
            if not isinstance(wert, int):
                return False, f"Ablenker {wert!r} ist keine ganze Zahl"
            if wert == antwort:
                return False, f"Ablenker {wert!r} ist gleich der Antwort"
        if len(set(ablenker)) != 3:
            return False, "die drei Ablenker sind nicht paarweise verschieden"

        return True, "ok"
    except Exception as e:  # eine kaputte Maschine soll hier hängen bleiben, nie crashen
        return False, f"Ausnahme beim Prüfen: {e!r}"
