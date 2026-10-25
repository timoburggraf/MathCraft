# -*- coding: utf-8 -*-
"""Prüft den Prüfer.

Der Validator ist die einzige Stelle, die verhindert, dass ein Rechenfehler des
Sprachmodells auf dem Tablet landet. Also wird er selbst geprüft: absichtlich
kaputte Aufgaben müssen ausnahmslos abgelehnt werden — und einwandfreie
Aufgaben müssen ebenso zuverlässig durchgehen. Ein Prüfer, der alles ablehnt,
wäre genauso wertlos wie einer, der alles durchwinkt.

  .venv/bin/python build/validator_test.py
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import random
import raetsel_kern as K
import grafik_kern as GK
import muster_kern as MK
import algo_kern as AK
import geo_kern as GEO
import legen_kern as LK
import figur_kern as FK
import kern_pakete as KP
import validate as V

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


def accepts(name, task, stage=2, types=None):
    """Diese Aufgabe MUSS durchgehen."""
    problems = V.check_task(task, stage, types)
    ok(name, not problems, "; ".join(problems[:2]))


def rejects(name, task, stage=2, types=None, expect=None):
    """Diese Aufgabe MUSS abgelehnt werden."""
    problems = V.check_task(task, stage, types)
    if not problems:
        ok(name, False, "wurde durchgewinkt")
    elif expect and not any(expect.lower() in p.lower() for p in problems):
        ok(name, False, f"abgelehnt, aber aus dem falschen Grund: {problems[0]}")
    else:
        ok(name, True, problems[0][:64])


# ============================================================ gültige Aufgaben
# Erst der Gegenbeweis: der Prüfer darf nicht einfach alles ablehnen.

accepts("Rechenaufgabe geht durch",
        {"type": "zahl", "q": "Steve hat 8 Blöcke und findet 5 dazu. Wie viele hat er?",
         "a": 13, "check": {"expr": "8+5"}})

accepts("Auswahl geht durch",
        {"type": "wahl", "q": "Wie viel ist 7 plus 6?",
         "opts": ["12", "13", "14", "11"], "correct": 1, "check": {"expr": "7+6"}})

accepts("Wahr/Falsch geht durch",
        {"type": "wahrfalsch", "q": "Stimmt das: 9 plus 4 ist 13?",
         "a": True, "check": {"left": "9+4", "right": "13"}})

accepts("Ordnen geht durch",
        {"type": "ordnen", "q": "Ordne die Zahlen von klein nach groß.",
         "items": [12, 5, 19, 8], "order": [1, 3, 0, 2]})

accepts("Absteigend ordnen geht durch",
        {"type": "ordnen", "q": "Ordne von groß nach klein.",
         "items": [12, 5, 19, 8], "order": [2, 0, 3, 1]})

accepts("Zuordnen geht durch",
        {"type": "zuordnen", "q": "Was gehört zusammen?",
         "pairs": [["3 mal 2", "6"], ["4 plus 4", "8"], ["10 minus 3", "7"]]},
        stage=4)

accepts("Mehrschritt geht durch",
        {"type": "mehrschritt", "q": "Ein Trikot kostet 12 Euro, eine Hose 9 Euro.",
         "steps": [{"q": "Was kosten beide zusammen?", "a": 21, "check": {"expr": "12+9"}},
                   {"q": "Wie viel Rückgeld bei 30 Euro?", "a": 9, "check": {"expr": "30-21"}}]},
        stage=4)

accepts("Gitter mit Lösungsfeld geht durch",
        {"type": "gitter", "q": "Welches Feld ist frei?",
         "grid": [["🟩", "🟩"], ["🟩", "⬜"]], "cell": [1, 1]})

accepts("Entdecken geht durch",
        {"type": "entdecken", "q": "Malnehmen ist Zusammenzählen in Reihen.",
         "info": "3 mal 4 heißt: drei Reihen mit je vier Blöcken. Das sind 12."},
        stage=3)

accepts("Komma-Betrag im Zahlenraum geht durch",
        {"type": "zahl", "q": "Ein Eis kostet 2 Euro, eine Waffel 3 Euro. Was kostet beides?",
         "a": 5, "check": {"expr": "2+3"}})

# Diese drei sind in der Praxis aufgetreten: einwandfreie Aufgaben, die ein zu
# grober Prüfer abgelehnt hat. Fehlalarme sind genauso schädlich wie
# Durchwinken — sie werfen gute Aufgaben weg und kosten bei jedem Lauf Geld.
accepts("Antwort mit Einheit geht durch",
        {"type": "wahl", "q": "Wie viele Klötze sind es zusammen?",
         "opts": ["40 Klötze", "42 Klötze", "44 Klötze", "38 Klötze"], "correct": 1,
         "check": {"expr": "24+18"}}, stage=3)

accepts("Auslassungszeichen in einer Zahlenfolge geht durch",
        {"type": "zahl", "q": "Die Reihe geht 3, 4, 5, 6, … Welche Zahl kommt als Nächstes?",
         "a": 7, "check": {"expr": "6+1"}}, stage=1)

accepts("kurze Zahlantworten gehen durch",
        {"type": "wahl", "q": "Wie viel ist 2 plus 3?",
         "opts": ["5", "12", "14", "16"], "correct": 0, "check": {"expr": "2+3"}})


# =========================================================== falsche Rechnung
# Der Kern: Das Modell behauptet ein Ergebnis, das nicht stimmt.

rejects("falsche Lösung fällt auf",
        {"type": "zahl", "q": "Wie viel ist 8 plus 5?", "a": 14, "check": {"expr": "8+5"}},
        expect="ergibt 13")

rejects("falsche Lösung in der Auswahl fällt auf",
        {"type": "wahl", "q": "Wie viel ist 7 plus 6?",
         "opts": ["12", "14", "15", "11"], "correct": 1, "check": {"expr": "7+6"}},
        expect="ergibt 13")

rejects("falsche Lösung fällt auch mit Einheit auf",
        {"type": "wahl", "q": "Wie viele Klötze sind es zusammen?",
         "opts": ["40 Klötze", "43 Klötze", "44 Klötze", "38 Klötze"], "correct": 1,
         "check": {"expr": "24+18"}},
        stage=3, expect="ergibt 42")

rejects("zweite richtige Antwort fällt auch mit Einheit auf",
        {"type": "wahl", "q": "Wie viele Meter sind das?",
         "opts": ["42 m", "42 Meter", "44 m", "38 m"], "correct": 0,
         "check": {"expr": "24+18"}},
        stage=3, expect="ebenfalls")

rejects("Antwort ganz ohne Zahl fällt auf",
        {"type": "wahl", "q": "Wie viel ist 24 plus 18?",
         "opts": ["ganz viele", "wenige", "keine", "einige"], "correct": 0,
         "check": {"expr": "24+18"}},
        stage=3, expect="keine zahl")

rejects("zweite richtige Antwort fällt auf",
        {"type": "wahl", "q": "Wie viel ist 6 plus 6?",
         "opts": ["12", "12.0", "11", "10"], "correct": 0, "check": {"expr": "6+6"}},
        expect="ebenfalls")

rejects("falsche Behauptung bei Wahr/Falsch fällt auf",
        {"type": "wahrfalsch", "q": "Stimmt das: 9 plus 4 ist 12?",
         "a": True, "check": {"left": "9+4", "right": "12"}},
        expect="behauptung ist false")

rejects("falscher Zwischenschritt fällt auf",
        {"type": "mehrschritt", "q": "Zwei Preise.",
         "steps": [{"q": "12 plus 9?", "a": 22, "check": {"expr": "12+9"}},
                   {"q": "30 minus 21?", "a": 9, "check": {"expr": "30-21"}}]},
        stage=4, expect="schritt 1")

rejects("Aufgabe ohne nachrechenbaren Term fällt auf",
        {"type": "zahl", "q": "Wie viel ist 8 plus 5?", "a": 13},
        expect="nachrechenbar")

rejects("falsch sortierte Reihe fällt auf",
        {"type": "ordnen", "q": "Ordne von klein nach groß.",
         "items": [12, 5, 19, 8], "order": [0, 1, 2, 3]},
        expect="weder auf- noch absteigend")


# ============================================================ Stufe und Raum

rejects("zu große Zahl im Text fällt auf",
        {"type": "zahl", "q": "Ein Dorf hat 500 Bewohner, 3 ziehen weg. Wie viele bleiben?",
         "a": 497, "check": {"expr": "500-3"}},
        stage=1, expect="zahlenraum")

rejects("zu großes Ergebnis fällt auf",
        {"type": "zahl", "q": "Wie viel ist 90 plus 90?", "a": 180, "check": {"expr": "90+90"}},
        stage=3, expect="zahlenraum")

rejects("Malnehmen auf Stufe 1 fällt auf",
        {"type": "zahl", "q": "Wie viel ist 3 mal 4?", "a": 12, "check": {"expr": "3*4"}},
        stage=1, expect="noch nicht dran")

rejects("Teilen auf Stufe 3 fällt auf",
        {"type": "zahl", "q": "Wie viel ist 12 geteilt durch 4?", "a": 3,
         "check": {"expr": "12/4"}},
        stage=3, expect="noch nicht dran")

rejects("negatives Ergebnis fällt auf",
        {"type": "zahl", "q": "Wie viel ist 4 minus 9?", "a": -5, "check": {"expr": "4-9"}},
        expect="negativ")

rejects("krummes Ergebnis ohne Division fällt auf",
        {"type": "zahl", "q": "Wie viel ist 8 plus 5?", "a": 13.5,
         "check": {"expr": "8+5.5"}},
        expect="krumm")

rejects("Aufgabentyp, der nicht zur Fertigkeit passt, fällt auf",
        {"type": "zahl", "q": "Wie viel ist 2 plus 2?", "a": 4, "check": {"expr": "2+2"}},
        types=["wahl", "wahrfalsch"], expect="nicht vorgesehen")


# ================================================================= Form

rejects("doppelte Antwortmöglichkeit fällt auf",
        {"type": "wahl", "q": "Wie viel ist 7 plus 6?",
         "opts": ["13", "13", "14", "11"], "correct": 0, "check": {"expr": "7+6"}},
        expect="doppelt")

rejects("verräterisch lange richtige Antwort fällt auf",
        {"type": "wahl", "q": "Welche Aussage stimmt?",
         "opts": ["Nein", "Ja", "Alle geraden Zahlen lassen sich ohne Rest halbieren", "Nie"],
         "correct": 2},
        expect="länge")

rejects("zu wenige Antwortmöglichkeiten fallen auf",
        {"type": "wahl", "q": "Wie viel ist 7 plus 6?", "opts": ["13", "14"], "correct": 0},
        expect="3 oder 4")

rejects("Platzhalter im Text fällt auf",
        {"type": "zahl", "q": "Rechne [ZAHL] plus 5 aus.", "a": 13, "check": {"expr": "8+5"}},
        expect="platzhalter")

rejects("Formelsatz im Text fällt auf",
        {"type": "zahl", "q": "Berechne \\frac{8}{2} plus 9.", "a": 13,
         "check": {"expr": "8/2+9"}},
        stage=4, expect="platzhalter")

rejects("zu langer Fragetext fällt auf",
        {"type": "zahl", "q": "In einem Dorf " + "sehr " * 60 + "weit weg wohnt Steve. Wie alt?",
         "a": 8, "check": {"expr": "4+4"}},
        expect="zu lang")

rejects("Tabuwort fällt auf",
        {"type": "zahl", "q": "Steve tötet 3 von 8 Gegnern. Wie viele bleiben?",
         "a": 5, "check": {"expr": "8-3"}},
        expect="nichts zu suchen")

rejects("doppelte Karte beim Zuordnen fällt auf",
        {"type": "zuordnen", "q": "Was gehört zusammen?",
         "pairs": [["3 plus 3", "6"], ["2 plus 4", "6"], ["1 plus 6", "7"]]},
        expect="doppelt")

rejects("Lösungsfeld außerhalb des Gitters fällt auf",
        {"type": "gitter", "q": "Welches Feld ist frei?",
         "grid": [["🟩", "🟩"], ["🟩", "⬜"]], "cell": [5, 1]},
        expect="nicht im gitter")

rejects("Gitter ohne Lösung fällt auf",
        {"type": "gitter", "q": "Was fehlt?", "grid": [["🟩", "⬜"]]},
        expect="ohne lösung")


# ======================================================= Robustheit des Terms

rejects("Teilen durch null fällt auf",
        {"type": "zahl", "q": "Wie viel ist 8 geteilt durch 0?", "a": 0,
         "check": {"expr": "8/0"}},
        stage=4, expect="null")

rejects("Code im Term wird nicht ausgeführt",
        {"type": "zahl", "q": "Wie viel ist 8 plus 5?", "a": 13,
         "check": {"expr": "__import__('os').system('echo kaputt')"}},
        expect="nicht erlaubt")

rejects("Variable im Term fällt auf",
        {"type": "zahl", "q": "Wie viel ist x plus 5?", "a": 13, "check": {"expr": "x+5"}},
        expect="nicht erlaubt")

rejects("unlesbarer Term fällt auf",
        {"type": "zahl", "q": "Wie viel ist 8 plus 5?", "a": 13, "check": {"expr": "8 plus 5"}},
        expect="nicht lesbar")

rejects("unbekannter Aufgabentyp fällt auf", {"type": "malen", "q": "Male ein Haus."},
        expect="unbekannter aufgabentyp")


# ========================================================= Logikgitter (D4)
# validate.py delegiert die Lösbarkeit vollständig an
# validate_v2.pruefe_logikgitter_aufgabe (die wiederum raetsel_kern.pruefe_
# logikgitter befragt) – hier wird geprüft, dass diese Delegation tatsächlich
# greift und die zusätzlichen Formregeln (Platzhalter, Hinweislänge) mit
# ausgelöst werden. Der Kern kommt aus raetsel_kern.erzeuge_logikgitter, die
# Verkleidung von Hand (kein Sprachmodell nötig – deterministisch und offline,
# im selben Geist wie validate_v2_test.py).

def _kat_nr(kennung):
    return int(kennung[1:])


def _logikgitter_von_hand(seed):
    """Baut eine garantiert saubere, deterministische Logikgitter-Aufgabe:
    Kern aus raetsel_kern (immer eindeutig lösbar), Namen von Hand vergeben."""
    kern = K.erzeuge_logikgitter(2, 3, seed)
    kennungen = [el for kat in kern["kategorien"] for el in kat]
    namen = dict(zip(kennungen, ["Anna", "Ben", "Clara", "Hund", "Katze", "Vogel"]))
    hinweise = []
    for h in kern["hinweise"]:
        na = namen[h["a"][0] + "e" + str(h["a"][1])]
        nb = namen[h["b"][0] + "e" + str(h["b"][1])]
        text = f"{na} gehört zu {nb}." if h["typ"] == "ist" else f"{na} gehört nicht zu {nb}."
        hinweise.append({"typ": h["typ"], "a": [_kat_nr(h["a"][0]), h["a"][1]],
                          "b": [_kat_nr(h["b"][0]), h["b"][1]], "text": text})
    subjekt_idx = 0
    korrekt_idx = kern["loesung"]["k1"][subjekt_idx]
    zielnamen = [namen[f"k1e{j}"] for j in range(3)]
    return {
        "type": "logikgitter",
        "kategorien": [[namen[el] for el in kat] for kat in kern["kategorien"]],
        "hinweise": hinweise,
        "frage": {"a": [0, subjekt_idx], "ziel": 1},
        "frage_text": f"Welches Tier gehört zu {namen['k0e' + str(subjekt_idx)]}?",
        "loesung": kern["loesung"],
        "optionen": zielnamen,
        "richtig": korrekt_idx,
        "rahmen": "Drei Freunde haben je ein Lieblingstier.",
    }


accepts("sauberes Logikgitter geht durch", _logikgitter_von_hand(seed=1), stage=6)

_LOGIKGITTER_UNIT = {
    "skill": "log_gitter", "stage": 6, "title": "Logikgitter-Testpaket",
    "tasks": [_logikgitter_von_hand(seed=s) for s in (1, 2, 3, 4)],
}
p = V.check_unit(_LOGIKGITTER_UNIT)
ok("sauberes Logikgitter-Paket (Kern + Handverkleidung) geht durch", not p,
   "; ".join(p[:2]))

_basis = _logikgitter_von_hand(seed=5)

_zweideutig = copy.deepcopy(_basis)
_zweideutig["hinweise"] = _zweideutig["hinweise"][:-1]
rejects("zweideutiges Gitter (ein Hinweis entfernt) fällt auf", _zweideutig, stage=6,
        expect="eindeutig")

_falsch_richtig = copy.deepcopy(_basis)
_falsch_richtig["richtig"] = (_falsch_richtig["richtig"] + 1) % len(_falsch_richtig["optionen"])
rejects("falsches 'richtig'-Feld fällt auf", _falsch_richtig, stage=6, expect="richtig")

_duplikat = copy.deepcopy(_basis)
_andere = [i for i in range(len(_duplikat["optionen"])) if i != _duplikat["richtig"]]
_duplikat["optionen"][_andere[1]] = _duplikat["optionen"][_andere[0]]
rejects("Options-Duplikat im Logikgitter fällt auf", _duplikat, stage=6, expect="doppelte")

_ohne_namen = copy.deepcopy(_basis)
_ohne_namen["hinweise"][0]["text"] = "Ein Satz ohne die richtigen Namen."
rejects("Hinweistext ohne die Namen fällt auf", _ohne_namen, stage=6, expect="beide namen")

_kennung_uebrig = copy.deepcopy(_basis)
_kennung_uebrig["frage_text"] = _kennung_uebrig["frage_text"] + " (k0e0)"
rejects("Platzhalter-Kennung im Text fällt auf", _kennung_uebrig, stage=6,
        expect="platzhalter-kennung")


# ======================================================== Rechenlast-Budget (D2)
# Der Deckel greift nur innerhalb eines Pakets (check_unit), weil er wissen
# muss, ob die Fertigkeit einer der fünf Denkdisziplinen zugeordnet ist
# (disziplinen.disziplin_von) – dafür reicht eine einzelne Aufgabe nicht.
#
# Hinweis zur Termwahl: Der im Auftrag genannte Beispielterm "394/8" kostet
# nach validate_v2.kalkuel_kosten() nur 4 Rechenschritte (Teilen ist dort per
# Konstruktion auf höchstens 4 gedeckelt, siehe validate_v2._kosten_geteilt)
# und bleibt damit unter jedem der überall gleich hohen Disziplin-Budgets von
# 6 – er würde also in BEIDEN Units durchgehen, nicht nur in der Pre-Lesson-
# Unit. Um den Mechanismus trotzdem wie verlangt zu zeigen (Ablehnung in
# einer Disziplin-Unit, Durchgang in einer Pre-Lesson-Unit), wird hier ein
# Term verwendet, der die 6 tatsächlich überschreitet (Kosten 8: zwei
# Additionen über 100 plus eine Multiplikation zweistelliger Zahlen). Diese
# Abweichung vom wörtlichen Beispielterm ist im Abschlussbericht als offener
# Punkt vermerkt.
_TEUER = "(45+38)*3+58"  # = 307; kalkuel_kosten = 2(+) + 3(*) + 3(+) = 8 > 6


def _kalkuel_unit(skill, stage):
    return {
        "skill": skill, "stage": stage, "title": "Kalkül-Testpaket",
        "tasks": [{"type": "zahl", "q": f"Rechne {_TEUER} aus.", "a": 307,
                   "check": {"expr": _TEUER}}]
        + [{"type": "zahl", "q": f"Wie viel ist {n} plus 5?", "a": n + 5,
            "check": {"expr": f"{n}+5"}} for n in (3, 4, 6)],
    }


p = V.check_unit(_kalkuel_unit("must_wechsel", 5))
ok("Kalkül-Budget: teurer Term in einer Disziplin-Unit (must_wechsel) fällt auf",
   any("rechenlast-budget" in x.lower() for x in p), p[0] if p else "durchgewinkt")

p = V.check_unit(_kalkuel_unit("plus_gross", 6))
ok("Kalkül-Budget: derselbe Term in einer Pre-Lesson-Unit (plus_gross) geht durch",
   not p, "; ".join(p[:2]))


# ============================================================ Folgen-Auswahl
# Der von generate_units.py gebaute Folgen-Pfad erzeugt 'wahl'-Aufgaben mit
# Fortsetzung + drei Ablenkern; raetsel_kern.erzeuge_folge garantiert, dass
# kein Ablenker der Lösung gleicht – hier wird geprüft, dass validate.py
# einen Verstoß dagegen trotzdem zuverlässig erkennt (bestehender Mechanismus
# aus _check_options, hier in der Folgen-Form).
rejects("Folgen-Auswahl mit Ablenker gleich der Lösung fällt auf",
        {"type": "wahl", "q": "In der Arena zählt jemand Punkte. Welche Zahl kommt als Nächstes?",
         "opts": ["24", "24", "20", "28"], "correct": 0, "check": {"expr": "20+4"}},
        stage=5, expect="ebenfalls")


# =============================================== bildwahl/bildzahl/positionen
# Die vier neuen Denkschule-Typen (SPEC_lektionen_v2.md §2-§6): die Wahrheit
# kommt hier ausschließlich aus grafik_kern.py/muster_kern.py/raetsel_kern.py
# selbst — kein Umweg über kern_pakete.py nötig, genau wie bei
# _logikgitter_von_hand() oben für den bestehenden Logikgitter-Typ.

def _bildwahl_spiegel(seed=1, stufe=3):
    erz = GK.erzeuge_spiegelbild(random.Random(seed), stufe)
    kern = {"art": "spiegelbild", "zellen": erz["zellen"],
            "optionen_zellen": erz["optionen_zellen"], "richtig": erz["richtig"],
            "stufe": erz["stufe"]}
    return {"type": "bildwahl",
            "q": "Spiegle die Figur an der gestrichelten Linie. Welches Bild ist richtig?",
            "svg": erz["svg_frage"], "optionen_svg": erz["optionen_svg"],
            "richtig": erz["richtig"], "kern": kern,
            "hint": "Schau dir jede Zelle einzeln an."}


def _bildwahl_dreh(seed=2, stufe=4):
    erz = GK.erzeuge_drehfigur(random.Random(seed), stufe)
    kern = {"art": "drehfigur", "zellen": erz["zellen"],
            "optionen_zellen": erz["optionen_zellen"], "richtig": erz["richtig"],
            "winkel": erz["winkel"], "stufe": erz["stufe"]}
    return {"type": "bildwahl", "q": "Drehe die Figur im Kopf. Welches Bild ist richtig?",
            "svg": erz["svg_frage"], "optionen_svg": erz["optionen_svg"],
            "richtig": erz["richtig"], "kern": kern, "hint": "Dreh die Figur Schritt für Schritt."}


def _bildwahl_matrix(seed=3, stufe=4, schwierigkeit=1):
    erz = MK.erzeuge_matrix(random.Random(seed), stufe, schwierigkeit)
    kern = {"art": "matrix", "zellen": erz["zellen"], "optionen": erz["optionen"],
            "richtig": erz["richtig"], "regeln": erz["regeln"], "stufe": erz["stufe"]}
    return {"type": "bildwahl", "q": "Welches Bild gehört ins leere Feld?",
            "svg": erz["svg_frage"], "optionen_svg": erz["optionen_svg"],
            "richtig": erz["richtig"], "kern": kern, "hint": "Schau dir jede Zeile und Spalte an."}


def _bildwahl_analogie(seed=4, stufe=6, schwierigkeit=1):
    erz = MK.erzeuge_analogie(random.Random(seed), stufe, schwierigkeit)
    kern = {"art": "analogie", "a": erz["a"], "b": erz["b"], "c": erz["c"],
            "optionen_zellen": erz["optionen_zellen"], "richtig": erz["richtig"],
            "transformation": erz["transformation"], "stufe": erz["stufe"]}
    return {"type": "bildwahl",
            "q": "Das erste Bild wird zum zweiten. Mach dasselbe mit dem dritten: "
                 "Welches Bild kommt heraus?",
            "svg": erz["svg_frage"], "optionen_svg": erz["optionen_svg"],
            "richtig": erz["richtig"], "kern": kern, "hint": "Finde zuerst die Umwandlung."}


def _bildzahl_von_hand(seed=5, stufe=5):
    erz = GK.erzeuge_wuerfelgebaeude(random.Random(seed), stufe)
    kern = {"art": "wuerfelgebaeude", "hoehen": erz["hoehen"], "anzahl": erz["anzahl"],
            "stufe": erz["stufe"]}
    return {"type": "bildzahl", "q": "Wie viele Würfel stecken im Gebäude? Denk an die versteckten.",
            "svg": erz["svg"], "a": erz["anzahl"], "kern": kern, "hint": "Zähl Reihe für Reihe."}


accepts("bildwahl · Spiegelbild geht durch", _bildwahl_spiegel(), stage=3, types=["bildwahl"])
accepts("bildwahl · Drehfigur geht durch", _bildwahl_dreh(), stage=4, types=["bildwahl"])
accepts("bildwahl · Bildmatrix geht durch", _bildwahl_matrix(), stage=4, types=["bildwahl"])
accepts("bildwahl · Analogie geht durch", _bildwahl_analogie(), stage=6, types=["bildwahl"])
accepts("bildzahl geht durch", _bildzahl_von_hand(), stage=5, types=["bildzahl"])

_sp = _bildwahl_spiegel(seed=11)
_falsch_richtig_sp = copy.deepcopy(_sp)
_falsch_richtig_sp["kern"]["richtig"] = (_sp["richtig"] + 1) % 4
_falsch_richtig_sp["richtig"] = (_sp["richtig"] + 1) % 4
rejects("bildwahl: falsches 'richtig' fällt auf", _falsch_richtig_sp, stage=3,
        types=["bildwahl"], expect="korrekte spiegelung")

_richtig_kern_auseinander = copy.deepcopy(_sp)
_richtig_kern_auseinander["richtig"] = (_sp["richtig"] + 1) % 4
rejects("bildwahl: 'richtig' weicht vom Kern ab", _richtig_kern_auseinander, stage=3,
        types=["bildwahl"], expect="stimmt nicht mit kern.richtig")

_script = copy.deepcopy(_sp)
_script["optionen_svg"][0] = _script["optionen_svg"][0] + "<script>alert(1)</script>"
rejects("bildwahl: <script> im Options-SVG fällt auf", _script, stage=3,
        types=["bildwahl"], expect="script")

_drei_svgs = copy.deepcopy(_sp)
_drei_svgs["optionen_svg"] = _drei_svgs["optionen_svg"][:3]
rejects("bildwahl: nur 3 statt 4 Options-SVGs fällt auf", _drei_svgs, stage=3,
        types=["bildwahl"], expect="genau 4 svgs")

_kaputtes_svg = copy.deepcopy(_sp)
_kaputtes_svg["optionen_svg"][0] = "kein svg hier"
rejects("bildwahl: Options-SVG ohne '<svg' fällt auf", _kaputtes_svg, stage=3,
        types=["bildwahl"], expect="beginnt nicht")

_pn_uebrig = copy.deepcopy(_sp)
_pn_uebrig["q"] = "Vergleiche p1 mit dem Original. " + _pn_uebrig["q"]
rejects("bildwahl: liegen gebliebene Kennung 'p1' im Text fällt auf", _pn_uebrig, stage=3,
        types=["bildwahl"], expect="platzhalter-kennung")

_unbekannte_art = copy.deepcopy(_sp)
_unbekannte_art["kern"]["art"] = "zauberei"
rejects("bildwahl: unbekannte kern.art fällt auf", _unbekannte_art, stage=3,
        types=["bildwahl"], expect="unbekannte kern.art")

_df = _bildwahl_dreh(seed=12)
_falscher_winkel = copy.deepcopy(_df)
_falscher_winkel["kern"]["winkel"] = 45
rejects("bildwahl: ungültiger Drehwinkel fällt auf", _falscher_winkel, stage=4,
        types=["bildwahl"], expect="nicht 90/180/270")

_mx = _bildwahl_matrix(seed=13)
_kaputte_regel = copy.deepcopy(_mx)
_kaputte_regel["kern"]["zellen"][0] = ["kreis", "#4cc9f0", 1]
_kaputte_regel["kern"]["zellen"][1] = ["quadrat", "#f08b3e", 2]
rejects("bildwahl: Matrix mit verletzter Regel fällt auf", _kaputte_regel, stage=4,
        types=["bildwahl"])

_an = _bildwahl_analogie(seed=14)
_falsche_transformation = copy.deepcopy(_an)
_alle = ("spiegeln", "drehen90", "drehen180", "drehen270")
_falsche_transformation["kern"]["transformation"] = next(
    t for t in _alle if t != _an["kern"]["transformation"])
rejects("bildwahl: Analogie mit falscher Transformation fällt auf", _falsche_transformation,
        stage=6, types=["bildwahl"])

_bz = _bildzahl_von_hand(seed=15)
_falsche_anzahl = copy.deepcopy(_bz)
_falsche_anzahl["a"] = _bz["a"] + 1
rejects("bildzahl: a weicht von kern.anzahl ab", _falsche_anzahl, stage=5,
        types=["bildzahl"], expect="stimmt nicht mit kern.anzahl")

_hoehe_kaputt = copy.deepcopy(_bz)
_hoehe_kaputt["kern"]["hoehen"][0][0] = 9
rejects("bildzahl: Höhe außerhalb 0..4 fällt auf", _hoehe_kaputt, stage=5,
        types=["bildzahl"])

_falsche_art = copy.deepcopy(_bz)
_falsche_art["kern"]["art"] = "zauberei"
rejects("bildzahl: unbekannte kern.art fällt auf", _falsche_art, stage=5,
        types=["bildzahl"], expect="unbekannt")

# Seit V3 ist 'quader' eine gültige Art – aber nicht mit den Daten eines
# Würfelgebäudes: der Prüfer der Art lehnt ab.
_falsche_art_quader = copy.deepcopy(_bz)
_falsche_art_quader["kern"]["art"] = "quader"
rejects("bildzahl: Würfelgebäude-Daten unter kern.art 'quader' fallen auf", _falsche_art_quader,
        stage=5, types=["bildzahl"], expect="kern lehnt")

_bz_script = copy.deepcopy(_bz)
_bz_script["svg"] = _bz_script["svg"] + "<script>böse()</script>"
rejects("bildzahl: <script> im Bild fällt auf", _bz_script, stage=5,
        types=["bildzahl"], expect="script")


# --------------------------------------------------------------- positionen

def _positionen_von_hand(n, seed, schwierigkeit, namen):
    """Baut eine garantiert saubere, deterministische Positionen-Aufgabe von
    Hand — Kern aus raetsel_kern.erzeuge_positionen (immer eindeutig lösbar),
    Namen und Sätze fest vergeben (kein Sprachmodell nötig), wie
    _logikgitter_von_hand() oben."""
    kern = K.erzeuge_positionen(n, seed=seed, schwierigkeit=schwierigkeit)

    def ersetze(text):
        for i, name in enumerate(namen):
            text = text.replace(f"p{i}", name)
        return text

    hinweise = []
    for h in kern["hinweise"]:
        hh = {"typ": h["typ"], "a": int(h["a"][1:])}
        if "b" in h:
            hh["b"] = int(h["b"][1:])
        if "c" in h:
            hh["c"] = int(h["c"][1:])
        hh["text"] = ersetze(h["text"])
        hinweise.append(hh)

    loesung = [int(x[1:]) for x in kern["loesung"]]
    frage = dict(kern["frage"])
    if frage["art"] == "neben":
        frage["a"] = int(frage["a"][1:])
        pos_a = loesung.index(frage["a"])
        nachbar_pos = pos_a - 1 if frage["seite"] == "links" else pos_a + 1
        ziel_idx = loesung[nachbar_pos]
        frage_text = f"Wer steht direkt {frage['seite']} neben {namen[frage['a']]}?"
    else:
        ziel_idx = loesung[frage["p"]]
        frage_text = "Wer steht an der gefragten Stelle in der Reihe?"

    optionen = list(namen)
    random.Random(seed + 1000).shuffle(optionen)
    richtig = optionen.index(namen[ziel_idx])

    return {
        "type": "positionen",
        "rahmen": "Die Crew stellt sich für ein Erinnerungsfoto in einer Reihe auf.",
        "namen": namen, "hinweise": hinweise, "loesung": loesung, "frage": frage,
        "frage_text": frage_text, "optionen": optionen, "richtig": richtig,
        "hint": "Zeichne eine Reihe und trag jeden Hinweis ein.",
    }


_NAMEN4 = ["der Astronaut", "die Pilotin", "der Kapitän", "die Forscherin"]
_NAMEN5 = ["der Astronaut", "die Pilotin", "der Kapitän", "die Forscherin", "der Ingenieur"]

accepts("positionen (n=4, position-Frage) geht durch",
        _positionen_von_hand(4, seed=99, schwierigkeit=2, namen=_NAMEN4), stage=5,
        types=["positionen"])

# Seed 2 mit hoher Schwierigkeit erzeugt zuverlässig eine 'neben'-Frage.
_pos_neben = None
for _s in range(1, 60):
    _kandidat = _positionen_von_hand(5, seed=_s, schwierigkeit=5, namen=_NAMEN5)
    if _kandidat["frage"]["art"] == "neben":
        _pos_neben = _kandidat
        break
if _pos_neben is not None:
    accepts("positionen (n=5, neben-Frage) geht durch", _pos_neben, stage=6, types=["positionen"])

_pos = _positionen_von_hand(4, seed=99, schwierigkeit=2, namen=_NAMEN4)

_name_fehlt = copy.deepcopy(_pos)
_name_fehlt["hinweise"][0]["text"] = "Jemand steht irgendwo in der Reihe."
rejects("positionen: Name fehlt im Hinweistext fällt auf", _name_fehlt, stage=5,
        types=["positionen"], expect="enthält nicht den namen")

_nicht_eindeutig = copy.deepcopy(_pos)
_nicht_eindeutig["hinweise"] = _nicht_eindeutig["hinweise"][:-1]
rejects("positionen: ein Hinweis entfernt macht es mehrdeutig", _nicht_eindeutig, stage=5,
        types=["positionen"], expect="nicht eindeutig")

_opt_doppelt = copy.deepcopy(_pos)
_opt_doppelt["optionen"] = [_pos["namen"][0]] * 4
rejects("positionen: doppelte Option fällt auf", _opt_doppelt, stage=5,
        types=["positionen"], expect="alle namen")

_antwort_in_frage = copy.deepcopy(_pos)
_antwortname = _pos["optionen"][_pos["richtig"]]
_antwort_in_frage["frage_text"] = f"Wer steht neben {_antwortname}?"
rejects("positionen: Antwortname in der Frage fällt auf", _antwort_in_frage, stage=5,
        types=["positionen"], expect="nennt den namen der antwort")

_pn_in_hinweis = copy.deepcopy(_pos)
_pn_in_hinweis["hinweise"][0]["text"] = _pn_in_hinweis["hinweise"][0]["text"] + " (p2)"
rejects("positionen: liegen gebliebene Kennung 'p2' fällt auf", _pn_in_hinweis, stage=5,
        types=["positionen"], expect="platzhalter-kennung")

_keine_permutation = copy.deepcopy(_pos)
_keine_permutation["loesung"] = [0, 0, 1, 2]
rejects("positionen: 'loesung' ist keine Permutation", _keine_permutation, stage=5,
        types=["positionen"], expect="keine permutation")

_falsches_richtig_pos = copy.deepcopy(_pos)
_falsches_richtig_pos["richtig"] = (_pos["richtig"] + 1) % len(_pos["optionen"])
rejects("positionen: 'richtig' zeigt auf die falsche Option", _falsches_richtig_pos, stage=5,
        types=["positionen"], expect="erwartet wäre")

_option_fehlt = copy.deepcopy(_pos)
_option_fehlt["optionen"][0] = "der Klempner"
rejects("positionen: Option fehlt (kein Name aus 'namen')", _option_fehlt, stage=5,
        types=["positionen"], expect="alle namen")

_frage_p_ungueltig = copy.deepcopy(_pos)
_frage_p_ungueltig["frage"] = {"art": "position", "p": 99}
rejects("positionen: 'frage.p' außerhalb des gültigen Bereichs fällt auf",
        _frage_p_ungueltig, stage=5, types=["positionen"], expect="gültige position")

_unbekannter_typ = copy.deepcopy(_pos)
_unbekannter_typ["hinweise"][0]["typ"] = "hellsehen"
rejects("positionen: unbekannter Hinweistyp fällt auf", _unbekannter_typ, stage=5,
        types=["positionen"], expect="unbekannter hinweistyp")

_zu_lang = copy.deepcopy(_pos)
_zu_lang["hinweise"][0]["text"] = (_zu_lang["hinweise"][0]["text"].rstrip(".")
                                    + ". Und noch ein Satz. Und noch einer.")
rejects("positionen: Hinweistext länger als zwei Sätze fällt auf", _zu_lang, stage=5,
        types=["positionen"], expect="länger als zwei sätze")

_ohne_rahmen = copy.deepcopy(_pos)
_ohne_rahmen["rahmen"] = ""
rejects("positionen: fehlende Rahmengeschichte fällt auf", _ohne_rahmen, stage=5,
        types=["positionen"], expect="rahmengeschichte fehlt")

# Verneinungs-Check: Seed 0/Stufe 6 liefert zuverlässig einen nicht_neben-Hinweis
# (siehe raetsel_kern._pos_pool_nach_schwierigkeit, Schwierigkeit ≥4).
_pos_verneinung = _positionen_von_hand(5, seed=0, schwierigkeit=5, namen=_NAMEN5)
_verneinung_index = next((i for i, h in enumerate(_pos_verneinung["hinweise"])
                          if h["typ"] in ("nicht_neben", "nicht_rand")), None)
if _verneinung_index is not None:
    _ohne_verneinung = copy.deepcopy(_pos_verneinung)
    _ohne_verneinung["hinweise"][_verneinung_index]["text"] = (
        _ohne_verneinung["hinweise"][_verneinung_index]["text"]
        .replace("nicht ", " ").replace("kein ", " ").replace("keine ", " "))
    rejects("positionen: Verneinung fehlt bei nicht_neben/nicht_rand", _ohne_verneinung, stage=6,
            types=["positionen"], expect="verneinung fehlt")

# Ein ganzes Paket aus Positionen-Aufgaben durch check_unit.
_POSITIONEN_UNIT = {
    "skill": "log_position", "stage": 5, "title": "Positionsrätsel-Testpaket",
    "tasks": [_positionen_von_hand(4, seed=s, schwierigkeit=2, namen=_NAMEN4)
              for s in (21, 22, 23, 24)],
}
p = V.check_unit(_POSITIONEN_UNIT)
ok("sauberes Positionen-Paket (Kern + Handverkleidung) geht durch", not p,
   "; ".join(p[:2]))


# ---------------------------------------------------------------- roboter
# SPEC_lektionen_v2.md §2: die Wahrheit kommt ausschließlich aus
# algo_kern.pruefe_roboter() – hier wird nur geprüft, dass validate.py diese
# Delegation tatsächlich auslöst (wie bei bildwahl/bildzahl/positionen oben).

_BEFOLGEN_Q_VARIANTEN = [
    "Der Rover startet und befolgt sein Programm. Auf welchem Feld hält er an?",
    "Der Rover führt sein Programm Schritt für Schritt aus. Wo hält er am Ende?",
    "Der Rover bekommt ein Programm zum Ausführen. Welches Feld erreicht er?",
    "Der Rover folgt seinem Programm genau. Auf welchem Feld hält er an?",
]


def _roboter_befolgen(seed=1, stage=3, q_index=0):
    erz = AK.erzeuge_befolgen(stage, seed, 2)
    return dict(erz, q=_BEFOLGEN_Q_VARIANTEN[q_index % len(_BEFOLGEN_Q_VARIANTEN)],
                hint="Merk dir nach jedem Befehl, wohin der Roboter schaut.")


def _roboter_finden(seed=2, stage=4):
    erz = AK.erzeuge_finden(stage, seed, 2)
    return dict(erz, q=f"Bring den Rover mit höchstens {erz['max_laenge']} Befehlen zur Rakete.",
                hint="Zähl, wie viele Schritte du bis zum Ziel brauchst.")


def _roboter_reparieren(seed=3, stage=5):
    erz = AK.erzeuge_reparieren(stage, seed, 2)
    return dict(erz, q="Ein Befehl ist falsch. Tippe ihn an.",
                hint="Simulier das Programm Schritt für Schritt.")


def _roboter_schleife(seed=4, stage=6):
    erz = AK.erzeuge_schleife(stage, seed, 3)
    return dict(erz, q="Der Rover befolgt ein Programm mit Wiederholungen. Auf welchem Feld hält er an?",
                hint="Zähl die Wiederholungen mit, dann den Rest.")


accepts("roboter · befolgen (modus ziel) geht durch", _roboter_befolgen(), stage=3, types=["roboter"])
accepts("roboter · finden (modus programm) geht durch", _roboter_finden(), stage=4, types=["roboter"])
accepts("roboter · reparieren geht durch", _roboter_reparieren(), stage=5, types=["roboter"])
accepts("roboter · schleife geht durch", _roboter_schleife(), stage=6, types=["roboter"])

_rb = _roboter_befolgen(seed=11, stage=3)
_falsches_ende = copy.deepcopy(_rb)
_falsches_ende["loesung"]["ende"] = [
    (_rb["loesung"]["ende"][0] + 1) % _rb["n"], _rb["loesung"]["ende"][1]]
rejects("roboter: falsches loesung.ende fällt auf", _falsches_ende, stage=3, types=["roboter"],
        expect="stimmt nicht mit simuliertem ende")

_wand_auf_start = copy.deepcopy(_rb)
_wand_auf_start["waende"] = [list(_rb["start"])] + _wand_auf_start["waende"]
rejects("roboter: Wand auf dem Startfeld fällt auf", _wand_auf_start, stage=3, types=["roboter"],
        expect="start liegt auf einer wand")

_ziel_verraet = copy.deepcopy(_rb)
_ziel_verraet["ziel"] = [0, 0]
rejects("roboter: 'ziel' im modus 'ziel' verrät die Antwort und fällt auf", _ziel_verraet, stage=3,
        types=["roboter"], expect="ziel")

_rf = _roboter_finden(seed=12, stage=4)
_beispiel_crasht = copy.deepcopy(_rf)
_beispiel_crasht["loesung"]["beispiel"] = ["N"] * (_rf["max_laenge"] + 4)
rejects("roboter: loesung.beispiel crasht fällt auf", _beispiel_crasht, stage=4, types=["roboter"])

_falsche_max_laenge = copy.deepcopy(_rf)
_falsche_max_laenge["max_laenge"] = _rf["max_laenge"] + 1
rejects("roboter: max_laenge stimmt nicht mit der kürzesten Lösung überein", _falsche_max_laenge,
        stage=4, types=["roboter"])

_rr = _roboter_reparieren(seed=13, stage=5)
_zweite_reparatur = copy.deepcopy(_rr)
# Zwei Plätze auf einmal kaputt machen erhöht das Risiko einer zweiten,
# ungewollten Reparaturmöglichkeit – reicht als Negativfall, ist aber nicht
# hundertprozentig garantiert; deshalb zusätzlich der direktere Fall unten
# (die angegebene Ersetzung führt selbst nicht ins Ziel).
_falsche_ersatz = copy.deepcopy(_rr)
_falsche_ersatz["loesung"]["ersatz"] = _rr["programm"][_rr["loesung"]["index"]]
rejects("roboter: 'ersatz' ist derselbe Befehl wie zuvor (kein anderer Befehl)", _falsche_ersatz,
        stage=5, types=["roboter"])

_falscher_index = copy.deepcopy(_rr)
_falscher_index["loesung"]["index"] = len(_rr["programm"])
rejects("roboter: loesung.index liegt außerhalb des Programms", _falscher_index, stage=5,
        types=["roboter"], expect="außerhalb des programms")

_rs = _roboter_schleife(seed=14, stage=6)
_kaputte_schleife = copy.deepcopy(_rs)
for befehl in _kaputte_schleife["programm"]:
    if isinstance(befehl, dict):
        befehl["x"] = 7   # außerhalb 2..4
        break
rejects("roboter: Schleifenfaktor außerhalb 2..4 fällt auf", _kaputte_schleife, stage=6,
        types=["roboter"], expect="außerhalb 2..4")

_n_ungueltig = copy.deepcopy(_rb)
_n_ungueltig["n"] = 9
rejects("roboter: n außerhalb 4..6 fällt auf", _n_ungueltig, stage=3, types=["roboter"],
        expect="außerhalb 4..6")

_unbekannter_befehl = copy.deepcopy(_rb)
_unbekannter_befehl["programm"] = list(_rb["programm"]) + ["X"]
rejects("roboter: unbekannter Befehl im Programm fällt auf", _unbekannter_befehl, stage=3,
        types=["roboter"])

_pn_in_roboter_q = copy.deepcopy(_rb)
_pn_in_roboter_q["q"] = _pn_in_roboter_q["q"] + " (p3)"
rejects("roboter: liegen gebliebene Kennung 'p3' im Text fällt auf", _pn_in_roboter_q, stage=3,
        types=["roboter"], expect="platzhalter-kennung")

# Ein ganzes Paket aus Roboter-Aufgaben (unterschiedliche Modi/Stufen –
# check_unit prüft hier zusätzlich, dass keine zwei q-Texte kollidieren).
_ROBOTER_UNIT = {
    "skill": "algo_befolgen", "stage": 3, "title": "Roboter-Testpaket",
    "tasks": [_roboter_befolgen(seed=s, stage=3, q_index=i)
              for i, s in enumerate((31, 32, 33, 34))],
}
p = V.check_unit(_ROBOTER_UNIT)
ok("sauberes Roboter-Paket geht durch", not p, "; ".join(p[:2]))



# ======================================================= V3: legen, Geometrie, Merkbild
# (ZIELE-V3.md, G1/G3/G4). Erst der Gegenbeweis: echte Aufgaben aus den Kernen
# gehen durch; dann je eine absichtlich kaputte Fassung, die abgelehnt werden MUSS.

def _legen(skill="komb_reihen", stage=5, index=0, seed=21):
    return LK.baue_aufgabe(skill, stage, index, seed)


def _geo(skill, stage, index, seed=22):
    return GEO.baue_aufgabe(skill, stage, index, seed)


_L = _legen()
accepts("legen · Reihenfolgen mit Regeln gehen durch", _L, stage=5, types=["legen"])
accepts("legen · Modus zaehlen geht durch", _legen("komb_reihen", 5, 4), stage=5, types=["legen"])
accepts("legen · Auswahl (ungeordnet) geht durch", _legen("komb_paare", 4, 2), stage=4,
        types=["legen"])
_alle_legen = [(sk, st, i) for (sk, st) in LK.PAKETE for i in range(6)]
_legen_mangel = [f"{sk}@{st}#{i}: {m}" for sk, st, i in _alle_legen
                 for m in V.check_task(_legen(sk, st, i), st, ["legen"])]
ok(f"legen · alle {len(_alle_legen)} Paketaufgaben (komb_reihen/komb_paare, Stufe 4 und 5) gehen durch",
   not _legen_mangel, "; ".join(_legen_mangel[:2]))

_l_a = copy.deepcopy(_L)
_l_a["a"] = _L["a"] + 1
rejects("legen: falsche Gesamtzahl a fällt auf", _l_a, stage=5, types=["legen"],
        expect="stimmt nicht mit kern.anzahl")

_l_kern_anzahl = copy.deepcopy(_L)
_l_kern_anzahl["a"] = _L["a"] + 1
_l_kern_anzahl["kern"]["anzahl"] = _L["a"] + 1
rejects("legen: Kern behauptet eine falsch gezählte Anzahl", _l_kern_anzahl, stage=5,
        types=["legen"], expect="aufzählung")

_l_regel = copy.deepcopy(_L)
_l_regel["regeln"][0] = dict(_l_regel["regeln"][0])
_l_regel["regeln"][0]["a"] = (_l_regel["regeln"][0]["a"] + 1) % len(_l_regel["figuren"])
rejects("legen: Regel der Aufgabe weicht vom Kern ab", _l_regel, stage=5, types=["legen"],
        expect="weicht vom kern ab")

_l_regel_kern = copy.deepcopy(_L)
_l_regel_kern["regeln"] = []
_l_regel_kern["kern"]["regeln"] = []
rejects("legen: Regel gestrichen, Zahl bleibt – die Aufzählung widerspricht", _l_regel_kern,
        stage=5, types=["legen"], expect="aufzählung")

_l_art = copy.deepcopy(_L)
_l_art["regeln"][0]["art"] = "zauberei"
_l_art["kern"]["regeln"][0]["art"] = "zauberei"
rejects("legen: unbekannte Regelart fällt auf", _l_art, stage=5, types=["legen"],
        expect="unbekannte regelart")

_l_modus_art = copy.deepcopy(_legen("komb_paare", 5, 0))
_l_modus_art["regeln"] = [{"art": "nebeneinander", "a": 0, "b": 1}]
_l_modus_art["kern"]["regeln"] = [{"art": "nebeneinander", "a": 0, "b": 1}]
rejects("legen: Reihenfolge-Regel in einer Auswahl-Aufgabe fällt auf", _l_modus_art, stage=5,
        types=["legen"], expect="ungeordneten")

_l_index = copy.deepcopy(_L)
_l_index["regeln"][0]["a"] = 9
_l_index["kern"]["regeln"][0]["a"] = 9
rejects("legen: Regel zeigt auf eine Figur, die es nicht gibt", _l_index, stage=5,
        types=["legen"], expect="zeigt auf keine figur")

_l_modus = copy.deepcopy(_L)
_l_modus["modus"] = "sofort"
rejects("legen: unbekannter Modus fällt auf", _l_modus, stage=5, types=["legen"],
        expect="weder 'alle' noch 'zaehlen'")

_l_viele = copy.deepcopy(_legen("komb_reihen", 5, 5))     # 5 Figuren, 120 Anordnungen
_l_viele["modus"] = "alle"
rejects("legen: Modus 'alle' bei 120 Anordnungen fällt auf", _l_viele, stage=5, types=["legen"],
        expect="nur bei 2..8")

_l_figuren = copy.deepcopy(_L)
_l_figuren["figuren"] = _l_figuren["figuren"][:-1]
rejects("legen: zu wenige Figuren für den Kern fallen auf", _l_figuren, stage=5, types=["legen"],
        expect="figuren")

_l_doppelt = copy.deepcopy(_L)
_l_doppelt["figuren"][1] = dict(_l_doppelt["figuren"][0])
rejects("legen: dieselbe Figur zweimal fällt auf", _l_doppelt, stage=5, types=["legen"],
        expect="zweimal")

_l_fremd = copy.deepcopy(_L)
_l_fremd["figuren"][0] = {"name": "Drachenlord", "bild": "🐉"}
rejects("legen: Figur außerhalb des Vorrats fällt auf", _l_fremd, stage=5, types=["legen"],
        expect="vorrat")

_l_ohne_bild = copy.deepcopy(_L)
del _l_ohne_bild["figuren"][0]["bild"]
rejects("legen: Figur ohne Bild fällt auf", _l_ohne_bild, stage=5, types=["legen"],
        expect="namen und ein bild")

_l_plaetze = copy.deepcopy(_L)
_l_plaetze["plaetze"] = len(_L["figuren"]) + 1
rejects("legen: mehr Plätze als Figuren fällt auf", _l_plaetze, stage=5, types=["legen"],
        expect="plaetze")

_l_geordnet = copy.deepcopy(_L)
_l_geordnet["geordnet"] = "ja"
rejects("legen: geordnet kein Wahrheitswert fällt auf", _l_geordnet, stage=5, types=["legen"],
        expect="geordnet")

_l_ohne_kern = copy.deepcopy(_L)
del _l_ohne_kern["kern"]
rejects("legen: ohne Kern fällt auf", _l_ohne_kern, stage=5, types=["legen"], expect="kern")

_l_text = copy.deepcopy(_L)
_l_text["q"] = _L["q"] + " [TODO]"
rejects("legen: Platzhalter im Text fällt auf", _l_text, stage=5, types=["legen"],
        expect="platzhalter")

_l_typ = {"type": "zahl", "q": "Wie viele Reihenfolgen gibt es?", "a": 6, "check": {"expr": "3*2"}}
rejects("legen-Fertigkeit: eine zahl-Aufgabe ist nicht vorgesehen", _l_typ, stage=4,
        types=["legen"], expect="nicht vorgesehen")

# ---- Geometrie (geo_kern): bildwahl / bildzahl / zahl mit Kern
_A = _geo("geo_ansicht", 4, 1)
_N = _geo("geo_netzfalten", 4, 0)
_K = _geo("geo_karte", 5, 0)
_G = _geo("geo_flaeche_umfang", 4, 0)
_Q = _geo("geo_quader", 5, 0)
_KW = _geo("geo_karte", 5, 2)
_R = _geo("geo_flaeche_umfang", 4, 4)
accepts("bildwahl · Ansicht geht durch", _A, stage=4, types=["bildwahl"])
accepts("bildwahl · Würfelnetz geht durch", _N, stage=4, types=["bildwahl"])
accepts("bildwahl · Schatzkarte (Koordinaten) geht durch", _K, stage=5, types=["bildwahl"])
accepts("bildzahl · Fläche einer Kästchenfigur geht durch", _G, stage=4, types=["bildzahl"])
accepts("bildzahl · Quader geht durch", _Q, stage=5, types=["bildzahl"])
accepts("bildzahl · Schatzkarte (Weg) geht durch", _KW, stage=5, types=["bildzahl"])
accepts("zahl mit Kern · Rechteck-Rätsel (mit Papier) geht durch", _R, stage=4,
        types=["bildzahl", "zahl"])
accepts("zahl ohne Kern geht weiter durch (wie bisher)",
        {"type": "zahl", "q": "Wie viel ist 7 plus 6?", "a": 13, "check": {"expr": "7+6"}})

_a_richtig = copy.deepcopy(_A)
_a_richtig["richtig"] = (_A["richtig"] + 1) % 4
_a_richtig["kern"]["richtig"] = (_A["richtig"] + 1) % 4
rejects("bildwahl: Ansicht mit falscher richtiger Option fällt auf", _a_richtig, stage=4,
        types=["bildwahl"], expect="kern lehnt")

_a_hoehen = copy.deepcopy(_A)
_a_hoehen["kern"]["hoehen"][0][0] = 9
rejects("bildwahl: Ansicht mit kaputter Höhenkarte fällt auf", _a_hoehen, stage=4,
        types=["bildwahl"], expect="kern lehnt")

_n_richtig = copy.deepcopy(_N)
_n_richtig["richtig"] = (_N["richtig"] + 1) % 4
_n_richtig["kern"]["richtig"] = (_N["richtig"] + 1) % 4
rejects("bildwahl: Netz, das sich nicht faltet, als richtig fällt auf", _n_richtig, stage=4,
        types=["bildwahl"], expect="kern lehnt")

_k_abw = copy.deepcopy(_K)
_k_abw["richtig"] = (_K["richtig"] + 1) % 4
rejects("bildwahl: Karte, richtig weicht vom Kern ab", _k_abw, stage=5, types=["bildwahl"],
        expect="stimmt nicht mit kern.richtig")

_g_anzahl = copy.deepcopy(_G)
_g_anzahl["a"] = _G["a"] + 1
_g_anzahl["kern"]["anzahl"] = _G["a"] + 1
rejects("bildzahl: Kästchenfigur mit falsch gezählter Fläche fällt auf", _g_anzahl, stage=4,
        types=["bildzahl"], expect="kern lehnt")

_q_a = copy.deepcopy(_Q)
_q_a["a"] = _Q["a"] + 1
rejects("bildzahl: Quader, a weicht vom Kern ab", _q_a, stage=5, types=["bildzahl"],
        expect="stimmt nicht mit kern.anzahl")

_kw_anzahl = copy.deepcopy(_KW)
_kw_anzahl["a"] = _KW["a"] + 2
_kw_anzahl["kern"]["anzahl"] = _KW["a"] + 2
rejects("bildzahl: Karte mit falschem kürzestem Weg fällt auf", _kw_anzahl, stage=5,
        types=["bildzahl"], expect="kern lehnt")

_r_anzahl = copy.deepcopy(_R)
_r_anzahl["a"] = _R["a"] + 1
rejects("zahl mit Kern: a weicht vom Kern ab", _r_anzahl, stage=4, types=["zahl"],
        expect="stimmt nicht mit kern.anzahl")

_r_kern_falsch = copy.deepcopy(_R)
_r_kern_falsch["a"] = _R["a"] + 1
_r_kern_falsch["kern"]["anzahl"] = _R["a"] + 1
_r_kern_falsch["check"] = {"expr": str(_R["a"] + 1)}
rejects("zahl mit Kern: falsch durchprobiertes Rätsel fällt auf", _r_kern_falsch, stage=4,
        types=["zahl"], expect="kern lehnt")

_r_art = copy.deepcopy(_R)
_r_art["kern"]["art"] = "zauberei"
rejects("zahl mit Kern: unbekannte kern.art fällt auf", _r_art, stage=4, types=["zahl"],
        expect="unbekannte kern.art")

_r_kern_kein_objekt = copy.deepcopy(_R)
_r_kern_kein_objekt["kern"] = "oje"
rejects("zahl mit Kern: Kern kein Objekt fällt auf", _r_kern_kein_objekt, stage=4,
        types=["zahl"], expect="kein objekt")

_a_art = copy.deepcopy(_A)
_a_art["kern"]["art"] = "hexagon"
rejects("bildwahl: unbekannte V3-Art fällt auf", _a_art, stage=4, types=["bildwahl"],
        expect="unbekannte kern.art")

_q_in_bildwahl = copy.deepcopy(_Q)
_q_in_bildwahl["type"] = "bildwahl"
_q_in_bildwahl["optionen_svg"] = [_Q["svg"]] * 4
_q_in_bildwahl["richtig"] = 0
rejects("bildwahl: eine Zahl-Art (quader) gehört nicht in eine Auswahlaufgabe", _q_in_bildwahl,
        stage=5, types=["bildwahl"], expect="kein 'richtig'")

_a_in_bildzahl = copy.deepcopy(_A)
_a_in_bildzahl["type"] = "bildzahl"
_a_in_bildzahl["a"] = 3
for k in ("optionen_svg", "richtig"):
    del _a_in_bildzahl[k]
rejects("bildzahl: eine Auswahl-Art (ansicht) gehört nicht in eine Zahlaufgabe", _a_in_bildzahl,
        stage=4, types=["bildzahl"], expect="keine 'anzahl'")

# ---- Punktmuster (bildzahl) und Merkbild (bildwahl mit merken_ms)
_P = FK.baue_aufgabe("must_figur", 7, 0, 23)
_M = FK.denkcheck_merkbild(5, 24)
accepts("bildzahl · Punktmuster geht durch", _P, stage=7, types=["bildzahl"])
accepts("bildwahl · Merkbild mit merken_ms geht durch", _M, stage=5, types=["bildwahl"])

_p_a = copy.deepcopy(_P)
_p_a["a"] = _P["a"] + 1
rejects("bildzahl: Punktmuster, a weicht vom Kern ab", _p_a, stage=7, types=["bildzahl"],
        expect="stimmt nicht mit kern.anzahl")

_p_kern = copy.deepcopy(_P)
_p_kern["a"] = _P["a"] + 1
_p_kern["kern"]["anzahl"] = _P["a"] + 1
rejects("bildzahl: Punktmuster, das nicht zur Formel passt, fällt auf", _p_kern, stage=7,
        types=["bildzahl"], expect="kern lehnt")

_m_richtig = copy.deepcopy(_M)
_m_richtig["richtig"] = (_M["richtig"] + 1) % 4
_m_richtig["kern"]["richtig"] = (_M["richtig"] + 1) % 4
rejects("bildwahl: Merkbild mit falscher richtiger Option fällt auf", _m_richtig, stage=5,
        types=["bildwahl"], expect="kern lehnt")

# ---- die neuen optionalen Felder papier und merken_ms
_papier = copy.deepcopy(_R)
accepts("papier: true geht durch", dict(_papier, papier=True), stage=4, types=["zahl"])
rejects("papier: kein Wahrheitswert fällt auf", dict(_papier, papier="ja"), stage=4,
        types=["zahl"], expect="papier")
rejects("papier: 1 statt true fällt auf", dict(_papier, papier=1), stage=4, types=["zahl"],
        expect="papier")

for _ms, _name in ((500, "zu kurz"), (20000, "zu lang"), ("5000", "als Text"), (True, "als bool"),
                   (5000.5, "als Kommazahl")):
    rejects(f"merken_ms {_name} fällt auf", dict(_M, merken_ms=_ms), stage=5,
            types=["bildwahl"], expect="merken_ms")
accepts("merken_ms=1000 an einer bildwahl-Aufgabe ist als Feld gültig",
        dict(_A, merken_ms=1000), stage=4, types=["bildwahl"])
rejects("merken_ms bei bildzahl fällt auf", dict(_P, merken_ms=5000), stage=7,
        types=["bildzahl"], expect="nur bei bildwahl")
rejects("Merkbild: merken_ms weicht vom Kern ab", dict(_M, merken_ms=_M["merken_ms"] + 1000),
        stage=5, types=["bildwahl"], expect="merken_ms")

# ---- ganze V3-Pakete über check_unit (Fertigkeit, Typen, Stufe)
for _sid, _stage, _wid in (("komb_reihen", 4, "weltraum"), ("geo_karte", 5, "dino"),
                           ("must_figur", 7, "ninja"), ("log_reihen", 4, "minecraft"),
                           ("must_rueck", 3, "fussball")):
    _u, _log = KP.baue_paket(_sid, _stage, _wid)
    ok(f"V3-Paket {_sid}@{_stage} besteht check_unit", _u is not None and not V.check_unit(_u),
       "; ".join(_log[-1:]))

_u_falsch, _ = KP.baue_paket("komb_reihen", 4, "weltraum")
_u_falsch = copy.deepcopy(_u_falsch)
_u_falsch["tasks"][2] = {"type": "zahl", "q": "Wie viele Reihenfolgen gibt es?", "a": 6,
                         "check": {"expr": "3*2"}}
_p = V.check_unit(_u_falsch)
ok("komb_reihen-Paket mit einer zahl-Aufgabe fällt auf", any("nicht vorgesehen" in x for x in _p),
   _p[0] if _p else "durchgewinkt")

# ================================================================ ganze Pakete

def unit(**kw):
    base = dict(skill="plus_bis20", stage=2, title="Blöcke zählen",
                tasks=[{"type": "zahl", "q": f"Wie viel ist {n} plus 5?", "a": n + 5,
                        "check": {"expr": f"{n}+5"}} for n in (3, 4, 6, 7)])
    base.update(kw)
    return base


ok("gültiges Paket geht durch", not V.check_unit(unit()),
   "; ".join(V.check_unit(unit())[:2]))

p = V.check_unit(unit(skill="gibt_es_nicht"))
ok("unbekannte Fertigkeit fällt auf", p and "unbekannte fertigkeit" in p[0].lower(),
   p[0] if p else "durchgewinkt")

p = V.check_unit(unit(tasks=unit()["tasks"][:2]))
ok("zu kurzes Paket fällt auf", p and "aufgaben" in p[0].lower(), p[0] if p else "durchgewinkt")

doppelt = unit()["tasks"][:3] + [unit()["tasks"][0]]
p = V.check_unit(unit(tasks=doppelt))
ok("doppelte Frage im Paket fällt auf", any("zweimal" in x for x in p),
   p[0] if p else "durchgewinkt")

p = V.check_unit(unit(stage=1))
ok("Paket unter der Stufe der Fertigkeit fällt auf", any("unter der stufe" in x.lower() for x in p),
   p[0] if p else "durchgewinkt")

p = V.check_unit(unit(stage=6))
ok("Paket weit über der Stufe fällt auf", any("mehr als eine stufe" in x.lower() for x in p),
   p[0] if p else "durchgewinkt")

p = V.check_unit(unit(title="Ein wirklich außerordentlich langer Titel für ein Lernpaket"))
ok("zu langer Titel fällt auf", any("titel" in x.lower() for x in p),
   p[0] if p else "durchgewinkt")

# Ein Paket, in dem genau eine Aufgabe faul ist – der Rest ist tadellos.
faul = unit()["tasks"][:3] + [{"type": "zahl", "q": "Wie viel ist 9 plus 9?",
                               "a": 19, "check": {"expr": "9+9"}}]
p = V.check_unit(unit(tasks=faul))
ok("einzelner Rechenfehler im Paket fällt auf",
   any("aufgabe 4" in x.lower() for x in p), p[0] if p else "durchgewinkt")


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
