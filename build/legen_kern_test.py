# -*- coding: utf-8 -*-
"""Prüft den deterministischen legen-Kern (legen_kern.py).

Im selben Geist wie spiel_kern_test.py: Die Gesamtzahl einer legen-Aufgabe
kommt aus einer Aufzählung im Kern. Damit ein Fehler dort nicht unbemerkt
bleibt, steht hier eine zweite, anders geschriebene Aufzählung daneben
(rekursiv statt itertools, Regeln über Listenpositionen statt über Dicts),
dazu Formeln (n!, n!/(n−k)!, C(n,k)) für den Fall ohne Regeln und von Hand
nachgerechnete Beispiele für jede Regelart.

  .venv/bin/python build/legen_kern_test.py
"""
import copy
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import legen_kern as L

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


# ============================================ zweite, unabhängige Aufzählung

def eigene_aufzaehlung(n, plaetze, geordnet, regeln):
    """Rekursiv: Plätze von vorne nach hinten füllen. Bei geordnet=False
    wird die Reihenfolge der Wahl erzwungen (aufsteigend), damit jede
    Auswahl genau einmal entsteht."""
    ergebnis = []

    def rec(bisher):
        if len(bisher) == plaetze:
            if alle_regeln(bisher):
                ergebnis.append(tuple(bisher))
            return
        for f in range(n):
            if f in bisher:
                continue
            if not geordnet and bisher and f < bisher[-1]:
                continue
            rec(bisher + [f])

    def alle_regeln(anf):
        return all(eigene_regel(r, anf) for r in regeln)

    def eigene_regel(r, anf):
        art, a, b = r["art"], r.get("a"), r.get("b")
        da = lambda x: x in anf
        if art == "dabei":
            return da(a)
        if art == "nicht_dabei":
            return not da(a)
        if art == "zusammen":
            return da(a) == da(b)
        if art == "nicht_zusammen":
            return not (da(a) and da(b))
        if art == "nicht_platz":
            return (not da(a)) or anf.index(a) != r["platz"]
        if art == "auf_platz":
            return (not da(a)) or anf.index(a) == r["platz"]
        if not (da(a) and da(b)):
            return True
        i, j = anf.index(a), anf.index(b)
        if art == "direkt_hinter":
            return i - j == 1
        if art == "nebeneinander":
            return abs(i - j) == 1
        if art == "nicht_nebeneinander":
            return abs(i - j) != 1
        raise AssertionError(art)

    rec([])
    return ergebnis


# ====================================================== Formeln ohne Regeln

fehler = []
for n in range(2, 7):
    for k in range(1, n + 1):
        if L.anzahl(n, k, True, []) != math.perm(n, k):
            fehler.append(f"geordnet n={n} k={k}")
        if L.anzahl(n, k, False, []) != math.comb(n, k):
            fehler.append(f"ungeordnet n={n} k={k}")
        if sorted(L.anordnungen(n, k, True, [])) != sorted(eigene_aufzaehlung(n, k, True, [])):
            fehler.append(f"Liste geordnet n={n} k={k}")
        if sorted(L.anordnungen(n, k, False, [])) != sorted(eigene_aufzaehlung(n, k, False, [])):
            fehler.append(f"Liste ungeordnet n={n} k={k}")
ok("ohne Regeln: n!, n!/(n-k)! und C(n,k) stimmen, auch als vollständige Listen",
   not fehler, "; ".join(fehler[:3]))

ok("ungeordnete Anordnungen sind aufsteigende Tupel",
   all(list(t) == sorted(t) for t in L.anordnungen(5, 3, False, [])))
ok("Aufzählung ist ohne Doppelte",
   len(set(L.anordnungen(5, 3, True, []))) == 60)

for schlecht in ((0, 0), (3, 4), (3, 0), (-1, 1)):
    try:
        L.anordnungen(schlecht[0], schlecht[1], True, [])
        ok(f"anordnungen{schlecht} lehnt unmögliche Größen ab", False)
    except ValueError:
        ok(f"anordnungen{schlecht} lehnt unmögliche Größen ab", True)


# ================================== jede Regelart an von Hand gerechneten Fällen
# Figuren 0,1,2. Hand-Rechnung steht jeweils im Kommentar.

def R(art, a=None, b=None, platz=None):
    r = {"art": art}
    for k, v in (("a", a), ("b", b), ("platz", platz)):
        if v is not None:
            r[k] = v
    return r


FAELLE = [
    # (Name, n, plaetze, geordnet, regeln, erwartete Liste)
    ("nicht_platz: 0 nie ganz vorne", 3, 3, True, [R("nicht_platz", 0, platz=0)],
     [(1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]),
    ("auf_platz: 0 ganz vorne", 3, 3, True, [R("auf_platz", 0, platz=0)],
     [(0, 1, 2), (0, 2, 1)]),
    ("direkt_hinter: 1 direkt hinter 0", 3, 3, True, [R("direkt_hinter", 1, 0)],
     [(0, 1, 2), (2, 0, 1)]),
    ("nebeneinander: 0 und 1", 3, 3, True, [R("nebeneinander", 0, 1)],
     [(0, 1, 2), (1, 0, 2), (2, 0, 1), (2, 1, 0)]),
    ("nicht_nebeneinander: 0 und 1", 3, 3, True, [R("nicht_nebeneinander", 0, 1)],
     [(0, 2, 1), (1, 2, 0)]),
    ("zwei Regeln zusammen", 3, 3, True,
     [R("nicht_platz", 0, platz=0), R("direkt_hinter", 1, 0)], [(2, 0, 1)]),
    # Figur nicht gelegt -> Regel gilt als erfüllt (3 Figuren auf 2 Plätzen):
    ("auf_platz mit fehlender Figur gilt als erfüllt", 3, 2, True, [R("auf_platz", 0, platz=0)],
     [(0, 1), (0, 2), (1, 2), (2, 1)]),
    ("nicht_platz mit fehlender Figur gilt als erfüllt", 3, 2, True,
     [R("nicht_platz", 0, platz=0)], [(1, 0), (1, 2), (2, 0), (2, 1)]),
    ("direkt_hinter ohne beide gelegt: nur (0,1) verletzt", 4, 2, True,
     [R("direkt_hinter", 0, 1)], None),   # 12 - 1 = 11, siehe unten
    ("zusammen: 0 und 1 gemeinsam oder beide nicht", 4, 2, False, [R("zusammen", 0, 1)],
     [(0, 1), (2, 3)]),
    ("nicht_zusammen: 0 und 1 nie beide", 4, 2, False, [R("nicht_zusammen", 0, 1)],
     [(0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]),
    ("dabei: 0 muss dabei sein", 4, 2, False, [R("dabei", 0)], [(0, 1), (0, 2), (0, 3)]),
    ("nicht_dabei: 0 darf nicht dabei sein", 4, 2, False, [R("nicht_dabei", 0)],
     [(1, 2), (1, 3), (2, 3)]),
    ("zusammen bei Dreiern aus 6 (Rechnung: 4 mit beiden + 4 ohne beide = 8)", 6, 3, False,
     [R("zusammen", 0, 1)], None),
]
for name, n, p, g, regeln, erwartet in FAELLE:
    ist = L.anordnungen(n, p, g, regeln)
    if erwartet is None:
        soll = {"direkt_hinter ohne beide gelegt: nur (0,1) verletzt": 11}.get(name, 8)
        ok(f"Regel von Hand: {name}", len(ist) == soll, f"{len(ist)} statt {soll}")
    else:
        ok(f"Regel von Hand: {name}", sorted(ist) == sorted(erwartet), str(ist))
    ok(f"   und gleiche Liste wie die zweite Aufzählung ({name})",
       sorted(ist) == sorted(eigene_aufzaehlung(n, p, g, regeln)))

# Einzelprüfung regel_erfuellt, auch außerhalb der Aufzählung
ok("regel_erfuellt: unbekannte Regelart gilt als nicht erfüllt",
   not L.regel_erfuellt(R("fliegt"), (0, 1), True))
ok("regel_erfuellt: geordnete Regelart bei ungeordnet gilt als nicht erfüllt",
   not L.regel_erfuellt(R("nicht_platz", 0, platz=0), (0, 1), False))
ok("regel_erfuellt: ungeordnete Regelart bei geordnet gilt als nicht erfüllt",
   not L.regel_erfuellt(R("dabei", 0), (0, 1), True))
ok("regel_erfuellt: kein dict stürzt nicht ab", not L.regel_erfuellt("x", (0, 1), True))


# ===================================================================== Sätze

FIG = [{"name": "Fuchs", "bild": "🦊"}, {"name": "Eule", "bild": "🦉"},
       {"name": "Golem", "bild": "🗿"}, {"name": "Drache", "bild": "🐲"}]
TEXTE = [
    (R("nicht_platz", 0, platz=0), 3, "Der Fuchs steht nie ganz vorne."),
    (R("nicht_platz", 1, platz=2), 3, "Die Eule steht nie ganz hinten."),
    (R("nicht_platz", 2, platz=1), 4, "Der Golem steht nie auf Platz 2."),
    (R("auf_platz", 1, platz=0), 3, "Die Eule steht ganz vorne."),
    (R("direkt_hinter", 1, 0), 3, "Die Eule steht direkt hinter dem Fuchs."),
    (R("direkt_hinter", 0, 3), 4, "Der Fuchs steht direkt hinter dem Drachen."),
    (R("nebeneinander", 0, 1), 3, "Der Fuchs und die Eule stehen nebeneinander."),
    (R("nicht_nebeneinander", 2, 1), 3, "Der Golem und die Eule stehen nie nebeneinander."),
    (R("zusammen", 0, 1), 3, "Der Fuchs und die Eule sind nur zusammen dabei."),
    (R("nicht_zusammen", 3, 2), 4, "Der Drache und der Golem sind nie zusammen dabei."),
    (R("dabei", 1), 3, "Die Eule ist immer dabei."),
    (R("nicht_dabei", 3), 4, "Der Drache ist nicht dabei."),
]
for regel, plaetze, satz in TEXTE:
    ok(f"regel_text {regel['art']}: {satz}", L.regel_text(regel, FIG, plaetze) == satz,
       L.regel_text(regel, FIG, plaetze))
ok("regel_text ohne Platzzahl nennt 'auf Platz 3' statt 'ganz hinten'",
   L.regel_text(R("nicht_platz", 1, platz=2), FIG) == "Die Eule steht nie auf Platz 3.")
try:
    L.regel_text({"art": "fliegt", "a": 0}, FIG)
    ok("regel_text lehnt unbekannte Regelart ab", False)
except ValueError:
    ok("regel_text lehnt unbekannte Regelart ab", True)

# ================================================== Pakete und Denk-Check

PLATZHALTER = re.compile(r"[\[\]{}]|\bk\d+e\d+\b|\bp\d+\b|%s|\bNone\b|\bTODO\b")
FORMEL_AUSGABE = re.compile(r"(?:^|[^\w])(?:True|False)\b")


def gute_aufgabe(a, wo):
    """Alle Anforderungen an eine fertige Aufgabe; Rückgabe: Mangel oder None."""
    ok_kern, grund = L.pruefe_legen_aufgabe(a)
    if not ok_kern:
        return f"{wo}: pruefe_legen lehnt ab ({grund})"
    ok_kern, grund = L.pruefe_legen(a["kern"])
    if not ok_kern:
        return f"{wo}: pruefe_legen(kern) lehnt ab ({grund})"
    n = a["kern"]["n"]
    ist = len(eigene_aufzaehlung(n, a["plaetze"], a["geordnet"], a["regeln"]))
    if ist != a["a"] or ist != a["kern"]["anzahl"]:
        return f"{wo}: zweite Aufzählung ergibt {ist}, a={a['a']}"
    if a["modus"] == "alle" and not 2 <= a["a"] <= 8:
        return f"{wo}: Modus alle bei {a['a']} Anordnungen"
    if set(a) != {"type", "q", "figuren", "plaetze", "geordnet", "modus", "regeln",
                  "a", "kern", "hint"}:
        return f"{wo}: Felder {sorted(a)}"
    if any(set(f) != {"name", "bild"} for f in a["figuren"]):
        return f"{wo}: Figuren tragen mehr als name/bild"
    for feld in ("q", "hint"):
        if PLATZHALTER.search(a[feld]) or not a[feld].strip():
            return f"{wo}: {feld} leer oder mit Platzhalter: {a[feld]!r}"
    ziel = re.split(r"(?<=[.?])\s", a["q"])[0]
    if len(ziel.split()) > 12:
        return f"{wo}: Ziel hat mehr als 12 Wörter: {ziel!r}"
    if json.loads(json.dumps(a, ensure_ascii=False)) != a:
        return f"{wo}: nicht JSON-fest"
    return None


# Sollwerte aus dem Auftrag (wo dort eine feste Zahl steht)
SOLL = {
    ("komb_reihen", 4): [2, 6, 4, 2, 6, 24],
    ("komb_reihen", 5): [None, None, 18, 12, 12, 120],
    ("komb_paare", 4): [3, 6, 5, 4, 10, 15],
    ("komb_paare", 5): [7, 4, 10, 14, 20, 8],
}
MODI = {
    ("komb_reihen", 4): ["alle"] * 4 + ["zaehlen"] * 2,
    ("komb_reihen", 5): ["alle"] * 2 + ["zaehlen"] * 4,
    ("komb_paare", 4): ["alle"] * 4 + ["zaehlen"] * 2,
    ("komb_paare", 5): ["alle"] * 2 + ["zaehlen"] * 4,
}
maengel, anzahl_aufgaben = [], 0
for (skill, stage), soll in SOLL.items():
    for seed in range(5):
        fragen = []
        for i in range(6):
            a = L.baue_aufgabe(skill, stage, i, seed)
            anzahl_aufgaben += 1
            m = gute_aufgabe(a, f"{skill}@{stage} #{i} seed={seed}")
            if m:
                maengel.append(m)
                continue
            if soll[i] is not None and a["a"] != soll[i]:
                maengel.append(f"{skill}@{stage} #{i}: a={a['a']}, Auftrag nennt {soll[i]}")
            if a["modus"] != MODI[(skill, stage)][i]:
                maengel.append(f"{skill}@{stage} #{i}: Modus {a['modus']}")
            if a["geordnet"] != (skill == "komb_reihen"):
                maengel.append(f"{skill}@{stage} #{i}: geordnet falsch")
            fragen.append(a["q"].lower())
        if len(set(fragen)) != 6:
            maengel.append(f"{skill}@{stage} seed={seed}: Fragetexte im Paket nicht verschieden")
ok(f"{anzahl_aufgaben} Paketaufgaben (4 Pakete x 6 x 5 Seeds): geprüft, Sollwerte, Modus, Texte",
   not maengel, "; ".join(maengel[:3]))

ok("Paket komb_reihen@5 #0 und #1: 2..8 Anordnungen",
   all(2 <= L.baue_aufgabe("komb_reihen", 5, i, s)["a"] <= 8 for i in (0, 1) for s in range(10)))
ok("komb_reihen@5 #1 hat 4 Figuren auf 2 Plätzen",
   (lambda a: a["plaetze"] == 2 and len(a["figuren"]) == 4)(L.baue_aufgabe("komb_reihen", 5, 1, 0)))
ok("komb_paare@5 #5 (zusammen) ist ungeordnet mit Regel zusammen",
   L.baue_aufgabe("komb_paare", 5, 5, 0)["regeln"][0]["art"] == "zusammen")

ok("Determinismus: gleicher Aufruf, gleiche Aufgabe",
   all(L.baue_aufgabe(sk, st, i, 7) == L.baue_aufgabe(sk, st, i, 7)
       for (sk, st) in SOLL for i in range(6)))
ok("andere Seeds liefern andere Aufgaben (Figuren oder Regeln)",
   len({json.dumps(L.baue_aufgabe("komb_reihen", 5, 0, s), sort_keys=True)
        for s in range(12)}) >= 6)
ok("Figurenwahl hängt vom Seed ab (alle 6 Figuren kommen vor)",
   len({f["name"] for s in range(20) for f in L.baue_aufgabe("komb_paare", 4, 5, s)["figuren"]}) == 6)

for ung in (("komb_reihen", 3, 0), ("quatsch", 4, 0), ("komb_reihen", 4, 6), ("komb_reihen", 4, -1)):
    try:
        L.baue_aufgabe(ung[0], ung[1], ung[2], 0)
        ok(f"baue_aufgabe{ung} lehnt Unmögliches ab", False)
    except ValueError:
        ok(f"baue_aufgabe{ung} lehnt Unmögliches ab", True)

# Denk-Check
dc_maengel, dc_n = [], 0
for stufe in range(2, 9):
    gesehen = set()
    for seed in range(12):
        a = L.denkcheck_aufgabe(stufe, seed)
        dc_n += 1
        m = gute_aufgabe(a, f"denkcheck stufe={stufe} seed={seed}")
        if m:
            dc_maengel.append(m)
        gesehen.add(json.dumps(a, sort_keys=True))
        if a != L.denkcheck_aufgabe(stufe, seed):
            dc_maengel.append(f"stufe={stufe} seed={seed}: nicht deterministisch")
    if len(gesehen) < 3:
        dc_maengel.append(f"stufe={stufe}: nur {len(gesehen)} verschiedene Aufgaben in 12 Seeds")
ok(f"{dc_n} Denk-Check-Aufgaben (Stufe 2..8 x 12 Seeds): geprüft, deterministisch, verschieden",
   not dc_maengel, "; ".join(dc_maengel[:3]))

ok("Denk-Check wird mit der Stufe schwerer (Anzahl-Spanne und Regeln)",
   L.denkcheck_aufgabe(2, 0)["a"] == 2 and L.denkcheck_aufgabe(3, 0)["a"] == 6
   and len(L.denkcheck_aufgabe(4, 0)["regeln"]) == 1
   and L.denkcheck_aufgabe(7, 0)["a"] == 24 and L.denkcheck_aufgabe(8, 0)["a"] == 72
   and L.denkcheck_aufgabe(7, 0)["regeln"][0]["art"] == "direkt_hinter"
   and L.denkcheck_aufgabe(8, 0)["regeln"][0]["art"] == "nicht_nebeneinander")
for s in (1, 9):
    try:
        L.denkcheck_aufgabe(s, 0)
        ok(f"denkcheck_aufgabe({s}) lehnt Stufe ab", False)
    except ValueError:
        ok(f"denkcheck_aufgabe({s}) lehnt Stufe ab", True)


# ===================================================== manipulierte Kerne
# Ausgangspunkt: die von Hand nachgerechnete Aufgabe "3 Figuren, 0 nie vorne" = 4.

def basis():
    return L.baue_aufgabe("komb_reihen", 4, 2, 3)


def kern_ablehnen(name, aendere, mit_aufgabe=False):
    a = copy.deepcopy(basis())
    aendere(a)
    # Aufgabe und Kern gleich ändern, wo es um die Regeln geht, damit der
    # Mangel wirklich im Kern liegt und nicht nur in der Abweichung
    ok_kern, grund = (L.pruefe_legen(a["kern"], a) if mit_aufgabe else L.pruefe_legen(a["kern"]))
    ok(f"abgelehnt: {name}", not ok_kern, grund)


ok("Ausgangsaufgabe für die Negativfälle ist in Ordnung",
   L.pruefe_legen_aufgabe(basis())[0], str(L.pruefe_legen_aufgabe(basis())))
kern_ablehnen("falsche Anzahl", lambda a: a["kern"].update(anzahl=5))
kern_ablehnen("Anzahl 0", lambda a: a["kern"].update(anzahl=0))
kern_ablehnen("Anzahl als Text", lambda a: a["kern"].update(anzahl="4"))
kern_ablehnen("Anzahl als Wahrheitswert", lambda a: a["kern"].update(anzahl=True))
kern_ablehnen("falsche art", lambda a: a["kern"].update(art="reihen"))
kern_ablehnen("n zu groß", lambda a: a["kern"].update(n=7))
kern_ablehnen("n = 1", lambda a: a["kern"].update(n=1))
kern_ablehnen("plaetze > n", lambda a: a["kern"].update(plaetze=4))
kern_ablehnen("plaetze = 1", lambda a: a["kern"].update(plaetze=1))
kern_ablehnen("geordnet als Zahl", lambda a: a["kern"].update(geordnet=1))
kern_ablehnen("ungeordnet mit plaetze == n", lambda a: a["kern"].update(geordnet=False))
kern_ablehnen("Regel mit Platz außerhalb", lambda a: a["kern"]["regeln"][0].update(platz=3))
kern_ablehnen("Regel mit Figur außerhalb", lambda a: a["kern"]["regeln"][0].update(a=3))
kern_ablehnen("Regel mit negativer Figur", lambda a: a["kern"]["regeln"][0].update(a=-1))
kern_ablehnen("Regel mit Figur als Text", lambda a: a["kern"]["regeln"][0].update(a="0"))
kern_ablehnen("Regelart des anderen Modus", lambda a: a["kern"]["regeln"][0].update(art="dabei"))
kern_ablehnen("Regelart unbekannt", lambda a: a["kern"]["regeln"][0].update(art="fliegt"))
kern_ablehnen("Regel mit fremdem Feld", lambda a: a["kern"]["regeln"][0].update(b=1))
kern_ablehnen("Regeln keine Liste", lambda a: a["kern"].update(regeln="nein"))
kern_ablehnen("zu viele Regeln", lambda a: a["kern"].update(
    regeln=[R("nicht_platz", 0, platz=0), R("nicht_platz", 1, platz=1),
            R("nicht_platz", 2, platz=2), R("nicht_platz", 0, platz=1)]))
kern_ablehnen("dieselbe Regel zweimal", lambda a: a["kern"].update(
    regeln=[R("nicht_platz", 0, platz=0), R("nicht_platz", 0, platz=0)], anzahl=4))
kern_ablehnen("überflüssige Regel (schließt nichts aus)", lambda a: a["kern"].update(
    regeln=[R("auf_platz", 0, platz=0), R("auf_platz", 0, platz=0)]))
kern_ablehnen("a == b in Zwei-Figuren-Regel",
              lambda a: a["kern"].update(regeln=[R("nebeneinander", 1, 1)], anzahl=6))
kern_ablehnen("Regeln schließen alles aus", lambda a: a["kern"].update(
    regeln=[R("auf_platz", 0, platz=0), R("auf_platz", 0, platz=1)], anzahl=0))

ok("abgelehnt: Kern ist kein dict", not L.pruefe_legen("legen")[0])
ok("abgelehnt: Kern ist None", not L.pruefe_legen(None)[0])
ok("abgelehnt: leerer Kern", not L.pruefe_legen({})[0])
ok("abgelehnt: Aufgabe ist kein dict", not L.pruefe_legen_aufgabe("x")[0])

# Mängel, die erst mit der ganzen Aufgabe auffallen
kern_ablehnen("Modus alle bei 24 Anordnungen", lambda a: (
    a.update(modus="alle", a=24, regeln=[]), a["kern"].update(regeln=[], anzahl=24),
    a.update(figuren=a["figuren"] + [{"name": "Biene", "bild": "🐝"}]),
    a["kern"].update(n=4, plaetze=4), a.update(plaetze=4)), mit_aufgabe=True)
kern_ablehnen("Modus alle bei genau einer Anordnung", lambda a: (
    a["kern"].update(regeln=[R("nicht_platz", 0, platz=0), R("direkt_hinter", 1, 0)], anzahl=1),
    a.update(regeln=[R("nicht_platz", 0, platz=0), R("direkt_hinter", 1, 0)], a=1)),
    mit_aufgabe=True)
kern_ablehnen("Modus unbekannt", lambda a: a.update(modus="raten"), mit_aufgabe=True)
kern_ablehnen("a weicht von der Zählung ab", lambda a: a.update(a=5), mit_aufgabe=True)
kern_ablehnen("type falsch", lambda a: a.update(type="zahl"), mit_aufgabe=True)
kern_ablehnen("Figurenzahl falsch", lambda a: a["figuren"].pop(), mit_aufgabe=True)
kern_ablehnen("Figur doppelt", lambda a: a["figuren"].__setitem__(1, dict(a["figuren"][0])),
              mit_aufgabe=True)
kern_ablehnen("Figur unbekannt", lambda a: a["figuren"].__setitem__(
    0, {"name": "Hase", "bild": "🐰"}), mit_aufgabe=True)
kern_ablehnen("Figur trägt mehr als name/bild", lambda a: a["figuren"][0].update(nom="der Fuchs"),
              mit_aufgabe=True)
kern_ablehnen("Platzhalter im Text", lambda a: a.update(q="Lege alle {was}."), mit_aufgabe=True)
kern_ablehnen("Platzhalter p0 im Hinweis", lambda a: a.update(hint="Fang mit p0 an."),
              mit_aufgabe=True)
kern_ablehnen("Regeln der Aufgabe weichen vom Kern ab", lambda a: a.update(regeln=[]),
              mit_aufgabe=True)

# Modus alle bei 9 Anordnungen: Grenze genau prüfen
kern9 = {"art": "legen", "n": 4, "plaetze": 2, "geordnet": True,
         "regeln": [R("nicht_platz", 0, platz=0)], "anzahl": 9}
a9 = {"type": "legen", "q": "Lege alle Reihenfolgen mit 2 von 4 Figuren.",
      "figuren": [{"name": "Fuchs", "bild": "🦊"}, {"name": "Eule", "bild": "🦉"},
                  {"name": "Golem", "bild": "🗿"}, {"name": "Katze", "bild": "🐱"}],
      "plaetze": 2, "geordnet": True, "modus": "alle", "regeln": kern9["regeln"],
      "a": 9, "kern": kern9, "hint": "Fang vorne an."}
ok("Grenze: Modus alle bei 9 Anordnungen wird abgelehnt", not L.pruefe_legen(kern9, a9)[0],
   L.pruefe_legen(kern9, a9)[1])
ok("Grenze: derselbe Kern im Modus zaehlen ist in Ordnung",
   L.pruefe_legen(kern9, dict(a9, modus="zaehlen"))[0], L.pruefe_legen(kern9, dict(a9, modus="zaehlen"))[1])

# ======================================== validate.py kennt `legen` noch nicht
# Erwartet (AP-3 trägt es nach): einzige Meldung ist der unbekannte Typ. Der
# Text wird trotzdem schon jetzt gegen die Textregeln gehalten.
try:
    import validate as V
    fremd, text_maengel = [], []
    for (skill, stage) in SOLL:
        for i in range(6):
            a = L.baue_aufgabe(skill, stage, i, 1)
            m = V.check_task(a, stage)
            fremd += [x for x in m if "unbekannter Aufgabentyp" not in x]
            out = []
            V._check_text(a["q"], out, stage)
            V._check_text(a["hint"], out, stage, "Tipp")
            text_maengel += out
    ok("validate.py: Texte aller Paketaufgaben bestehen die Textregeln "
       "(Meldung 'unbekannter Aufgabentyp' ist erwartet und ausgefiltert)",
       not fremd and not text_maengel, "; ".join((fremd + text_maengel)[:3]))
except ImportError as e:
    ok("validate.py importierbar", False, str(e))


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
