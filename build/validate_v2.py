# -*- coding: utf-8 -*-
"""Prüft die zwei neuen Bausteine der Denkschule: Rechenlast-Budget (D2) und
verkleidete Logikgitter-Aufgaben (D4).

Zwei unabhängige Prüfer stecken hier drin:

  1. kalkuel_kosten()/pruefe_kalkuel()  – zählt gewichtete elementare
     Rechenschritte an einem Term, ohne ihn per eval() auszuführen. Das ist
     dieselbe Vorsicht wie in validate.py (der Term kommt letztlich aus einem
     Sprachmodell): erlaubt sind ausschließlich Zahlen, Klammern und die vier
     Grundrechenarten.

  2. pruefe_logikgitter_aufgabe()  – prüft die VERKLEIDETE Aufgabenstruktur,
     die build/verkleidung.py aus einem raetsel_kern-Kern und Sprachmodell-
     Namen zusammenbaut. Die eigentliche Lösbarkeit wird dafür an
     raetsel_kern.pruefe_logikgitter() delegiert (kein zweiter, potenziell
     abweichender Lösungsweg) — hier kommt nur dazu, was erst nach der
     Verkleidung prüfbar ist: Namen, Hinweistexte, Frage, Optionen.

  .venv/bin/python build/validate_v2_test.py
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import raetsel_kern as K


class KalkuelFehler(Exception):
    """Ein Term ist nicht lesbar oder verwendet etwas, das hier nicht erlaubt ist."""


# ======================================================= Rechenlast-Budget

def _kosten_plus_minus(links, rechts):
    """Addition/Subtraktion: Kosten steigen mit der Größe der Operanden —
    8+5 im Kopf ist etwas anderes als 4821+3790."""
    hoechstwert = max(abs(links), abs(rechts))
    if hoechstwert <= 20:
        return 1
    if hoechstwert <= 100:
        return 2
    return 3


def _kosten_mal(links, rechts):
    """Kleines Einmaleins (beide Faktoren höchstens 10) ist auswendig
    abrufbar und kostet 1 Schritt; alles darüber muss gerechnet werden."""
    if abs(links) <= 10 and abs(rechts) <= 10:
        return 1
    return 3


def _kosten_geteilt(divisor, quotient):
    """Teilen kostet nur dann wenig, wenn sowohl der Divisor als auch das
    Ergebnis im kleinen Einmaleins liegen und glatt aufgeht — 42/6 kann man
    aus dem 6er-Einmaleins ablesen, 398/8 nicht."""
    glatt = quotient == int(quotient)
    if abs(divisor) <= 10 and glatt and abs(quotient) <= 10:
        return 1
    return 4


def _wert_und_kosten(knoten):
    """Wertet einen Syntaxbaum-Knoten aus UND zählt dabei die Kalkül-Kosten.

    Rückgabe (Wert, Kosten). Der Wert wird nur gebraucht, um die Kosten der
    umgebenden Operation zu bestimmen (Klammern selbst kosten nichts, ihr
    Ergebnis bestimmt aber, wie teuer der nächste Rechenschritt ist) — kein
    eval(): erlaubt sind ausschließlich Zahlen, Vorzeichen und die vier
    Grundrechenarten +, -, *, /.
    """
    if isinstance(knoten, ast.Expression):
        return _wert_und_kosten(knoten.body)

    if isinstance(knoten, ast.Constant):
        if isinstance(knoten.value, bool) or not isinstance(knoten.value, (int, float)):
            raise KalkuelFehler(f"nur Zahlen sind erlaubt, nicht {knoten.value!r}")
        return knoten.value, 0

    if isinstance(knoten, ast.UnaryOp) and isinstance(knoten.op, (ast.UAdd, ast.USub)):
        wert, kosten = _wert_und_kosten(knoten.operand)
        return (wert if isinstance(knoten.op, ast.UAdd) else -wert), kosten

    if isinstance(knoten, ast.BinOp):
        links_wert, links_kosten = _wert_und_kosten(knoten.left)
        rechts_wert, rechts_kosten = _wert_und_kosten(knoten.right)
        kinder_kosten = links_kosten + rechts_kosten

        if isinstance(knoten.op, ast.Add):
            return links_wert + rechts_wert, kinder_kosten + _kosten_plus_minus(links_wert, rechts_wert)
        if isinstance(knoten.op, ast.Sub):
            return links_wert - rechts_wert, kinder_kosten + _kosten_plus_minus(links_wert, rechts_wert)
        if isinstance(knoten.op, ast.Mult):
            return links_wert * rechts_wert, kinder_kosten + _kosten_mal(links_wert, rechts_wert)
        if isinstance(knoten.op, ast.Div):
            if rechts_wert == 0:
                raise KalkuelFehler("Division durch null")
            quotient = links_wert / rechts_wert
            return quotient, kinder_kosten + _kosten_geteilt(rechts_wert, quotient)
        raise KalkuelFehler(f"Rechenart nicht erlaubt: {type(knoten.op).__name__}")

    raise KalkuelFehler(f"nicht erlaubter Ausdruck: {type(knoten).__name__}")


def kalkuel_kosten(term):
    """Zählt die gewichteten elementaren Rechenschritte eines Terms (D2).

    term ist ein reiner Rechenausdruck als Zeichenkette ("8+5", "(12-4)*3").
    Kein eval(): der Term kommt letztlich aus einem Sprachmodell, geparst wird
    ausschließlich über den eingeschränkten Python-Syntaxbaum, genau wie in
    validate.eval_term(). Ist der Term nicht lesbar oder enthält er etwas
    anderes als Zahlen, Klammern und die vier Grundrechenarten, wird eine
    KalkuelFehler-Ausnahme mit einer deutschen Meldung ausgelöst.
    """
    if not isinstance(term, str) or not term.strip():
        raise KalkuelFehler("leerer Term")
    if len(term) > 120:
        raise KalkuelFehler("Term zu lang")
    bereinigt = term.replace("×", "*").replace("÷", "/").replace("−", "-")
    try:
        baum = ast.parse(bereinigt, mode="eval")
    except SyntaxError:
        raise KalkuelFehler(f"Term nicht lesbar: {term!r}")
    _, kosten = _wert_und_kosten(baum)
    return kosten


def pruefe_kalkuel(term, budget):
    """Prüft einen Term gegen ein Rechenlast-Budget (D2: Disziplin-Aufgaben
    höchstens 6 elementare Schritte). Rückgabe: (ok, Begründung als Klartext).
    """
    try:
        kosten = kalkuel_kosten(term)
    except KalkuelFehler as e:
        return False, str(e)
    if kosten <= budget:
        return True, f"{kosten} von {budget} erlaubten Rechenschritten verbraucht"
    return False, f"{kosten} Rechenschritte überschreiten das Budget von {budget}"


# =================================================== Verkleidete Logikgitter

def _slot_gueltig(slot, kategorien):
    """Prüft, ob [Kategorie-Index, Element-Index] wirklich ins Gitter zeigt."""
    if not isinstance(slot, (list, tuple)) or len(slot) != 2:
        return False
    kat, idx = slot
    if not isinstance(kat, int) or isinstance(kat, bool) or not isinstance(idx, int) or isinstance(idx, bool):
        return False
    return 0 <= kat < len(kategorien) and 0 <= idx < len(kategorien[kat])


def pruefe_logikgitter_aufgabe(aufgabe):
    """Prüft eine fertig verkleidete Logikgitter-Aufgabe (Format siehe
    verkleidung.verkleide_logikgitter). Rückgabe: (ok, Liste der Mängel).

    Die eigentliche Lösbarkeit (eindeutig? stimmt die Lösung?) übernimmt
    raetsel_kern.pruefe_logikgitter() — hier kommt nur hinzu, was erst nach
    der sprachlichen Verkleidung prüfbar ist.
    """
    maengel = []
    if not isinstance(aufgabe, dict):
        return False, ["Aufgabe ist kein Objekt"]

    kategorien = aufgabe.get("kategorien")
    if not isinstance(kategorien, list) or not kategorien or not all(isinstance(k, list) and k for k in kategorien):
        return False, ["'kategorien' fehlt oder ist keine Liste nichtleerer Listen"]

    # Namen innerhalb jeder Kategorie einzigartig und nicht leer.
    for i, kat in enumerate(kategorien):
        namen = [str(n).strip() for n in kat]
        if any(not n for n in namen):
            maengel.append(f"Kategorie {i} enthält einen leeren Namen: {kat!r}")
        if len(set(namen)) != len(namen):
            maengel.append(f"Kategorie {i} hat doppelte Namen: {kat!r}")

    n_kategorien = len(kategorien)

    hinweise = aufgabe.get("hinweise")
    if not isinstance(hinweise, list) or not hinweise:
        return False, maengel + ["'hinweise' fehlt oder ist keine Liste"]

    kern_hinweise = []
    for i, h in enumerate(hinweise):
        if not isinstance(h, dict) or "a" not in h or "b" not in h or "typ" not in h:
            maengel.append(f"Hinweis {i} ist unvollständig: {h!r}")
            continue
        a, b = h["a"], h["b"]
        if not _slot_gueltig(a, kategorien) or not _slot_gueltig(b, kategorien):
            maengel.append(f"Hinweis {i}: Index außerhalb des Gitters (a={a!r}, b={b!r})")
            continue
        text = h.get("text") or ""
        name_a, name_b = kategorien[a[0]][a[1]], kategorien[b[0]][b[1]]
        if name_a not in text or name_b not in text:
            maengel.append(f"Hinweis {i}: Text {text!r} enthält nicht beide Namen "
                            f"({name_a!r}, {name_b!r})")
        if h["typ"] == "nicht":
            tl = text.lower()
            if "nicht" not in tl and "kein" not in tl:
                maengel.append(f"Hinweis {i}: Verneinung fehlt im Text {text!r} "
                                "(weder 'nicht' noch 'kein')")
        # Für raetsel_kern.pruefe_logikgitter() zurück ins interne kN-Format.
        kern_hinweise.append({"typ": h["typ"], "a": [f"k{a[0]}", a[1]], "b": [f"k{b[0]}", b[1]]})

    loesung = aufgabe.get("loesung")
    if not isinstance(loesung, dict):
        maengel.append("'loesung' fehlt oder ist kein Objekt")
    else:
        ergebnis = K.pruefe_logikgitter(kategorien, kern_hinweise, loesung)
        if not ergebnis["eindeutig"]:
            maengel.append(f"Rätsel ist nicht eindeutig lösbar "
                            f"({ergebnis['loesungen_gezaehlt']} Lösungen passen)")
        elif not ergebnis["stimmt"]:
            maengel.append("die angegebene Lösung stimmt nicht mit der einzig "
                            "gültigen Zuordnung überein")

    frage = aufgabe.get("frage")
    if not isinstance(frage, dict) or "a" not in frage:
        return False, maengel + ["'frage' fehlt oder ist unvollständig"]

    a = frage["a"]
    if not _slot_gueltig(a, kategorien):
        return False, maengel + [f"'frage.a' zeigt auf ein Feld außerhalb des Gitters: {a!r}"]

    subjekt_kat, subjekt_idx = a
    ziel = frage.get("ziel")
    # Fehlt 'ziel' (das minimale Format aus ZIELE-V2 kennt dieses Feld nicht),
    # ist es bei genau zwei Kategorien unzweideutig: die jeweils andere.
    if ziel is None and n_kategorien == 2:
        ziel = 1 if subjekt_kat == 0 else 0
    if ziel is None or not isinstance(ziel, int) or isinstance(ziel, bool) \
            or not (0 <= ziel < n_kategorien) or ziel == subjekt_kat:
        maengel.append(f"'frage.ziel' fehlt oder ist ungültig: {frage.get('ziel')!r}")
        return False, maengel
    if subjekt_kat != 0:
        maengel.append("'frage.a' muss auf ein Subjekt aus Kategorie 0 zeigen "
                        "(so ist die Lösung im Kern gespeichert)")
        return False, maengel

    if isinstance(loesung, dict):
        schluessel = f"k{ziel}"
        zuordnung = loesung.get(schluessel)
        if not isinstance(zuordnung, list) or not 0 <= subjekt_idx < len(zuordnung):
            maengel.append(f"Lösung enthält keine Zuordnung für {schluessel!r}")
        else:
            korrekt_idx = zuordnung[subjekt_idx]
            if not 0 <= korrekt_idx < len(kategorien[ziel]):
                maengel.append(f"Lösung zeigt für {schluessel!r} auf einen Index "
                                f"außerhalb der Kategorie: {korrekt_idx}")
            else:
                korrekt_name = kategorien[ziel][korrekt_idx]
                subjekt_name = kategorien[0][subjekt_idx]

                optionen = aufgabe.get("optionen")
                richtig = aufgabe.get("richtig")
                if not isinstance(optionen, list) or not optionen:
                    maengel.append("'optionen' fehlt oder ist leer")
                else:
                    if len(set(optionen)) != len(optionen):
                        maengel.append(f"doppelte Antwortmöglichkeit: {optionen!r}")
                    if not isinstance(richtig, int) or isinstance(richtig, bool) \
                            or not 0 <= richtig < len(optionen):
                        maengel.append(f"'richtig' zeigt auf keine vorhandene Option: {richtig!r}")
                    elif optionen[richtig] != korrekt_name:
                        maengel.append(f"'richtig' zeigt auf {optionen[richtig]!r}, "
                                        f"die Lösung ist aber {korrekt_name!r}")
                    for j, opt in enumerate(optionen):
                        if j == richtig:
                            continue
                        if opt not in kategorien[ziel]:
                            maengel.append(f"Option {opt!r} kommt in Kategorie {ziel} gar nicht vor")
                        elif opt == korrekt_name:
                            maengel.append(f"Option {opt!r} ist ebenfalls die Lösung – "
                                            "es darf nur eine richtige geben")

                frage_text = aufgabe.get("frage_text") or ""
                if subjekt_name not in frage_text:
                    maengel.append(f"'frage_text' {frage_text!r} nennt nicht den Namen "
                                    f"des gefragten Subjekts ({subjekt_name!r})")

    return not maengel, maengel
