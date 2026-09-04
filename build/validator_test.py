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
_falsche_art["kern"]["art"] = "quader"
rejects("bildzahl: falsche kern.art fällt auf", _falsche_art, stage=5,
        types=["bildzahl"], expect="wuerfelgebaeude")

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
