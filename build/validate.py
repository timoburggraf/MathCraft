# -*- coding: utf-8 -*-
"""Prüft jede erzeugte Aufgabe, bevor sie das Kind zu sehen bekommt.

Ein Sprachmodell verrechnet sich. Eine falsch als richtig markierte Aufgabe
wäre der schlimmste Fehler dieses Projekts — das Kind lernt dann Unsinn und
verliert das Vertrauen in die App. Deshalb geht hier nichts ungeprüft durch:

  1. nachgerechnet  – jede rechnerische Aufgabe liefert einen prüfbaren Term
                      mit, der ausgewertet wird und die Antwort ergeben muss
  2. Regeln         – Zahlenraum und Rechenart passen zur Stufe, genau eine
                      Antwort stimmt, die Ablenker sind nachweislich falsch
  3. Form           – Text kindgerecht und kurz, keine Platzhalter, keine
                      Antwort, die sich schon durch ihre Länge verrät

Rückgabe ist immer eine Liste von Klartext-Mängeln; leer heißt "in Ordnung".
Diese Texte gehen beim nächsten Lauf als Negativbeispiel an das Modell zurück.

  .venv/bin/python build/validate.py data/units_seed.json
"""
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum as C
import disziplinen as D
import validate_v2 as V2
import raetsel_kern as K
import grafik_kern as GK
import muster_kern as MK
import algo_kern as AK

# Ein Fragetext für einen Achtjährigen. Zwei Sätze, mehr nicht — wer drei
# Zeilen lesen muss, bevor er rechnen darf, gibt vorher auf.
MAX_Q = 220
MAX_TASKS = 12
MIN_TASKS = 4

# Platzhalter und Formelsatz, die das Modell gelegentlich stehen lässt.
# Das Auslassungszeichen gehört NICHT dazu: "3, 4, 5, …" ist die übliche und
# richtige Schreibweise einer Zahlenfolge, keine vergessene Lücke.
JUNK = re.compile(r"\[|\]|\{|\}|\\frac|\\times|\bTODO\b|\bXXX\b|\bPLATZHALTER\b", re.I)
# Zahlen im Text, inklusive Komma-Beträgen wie 3,50
NUM_IN_TEXT = re.compile(r"\d+(?:[.,]\d+)?")

# Interne Platzhalter-Kennungen aus raetsel_kern.py (z.B. "k0e0" beim
# Logikgitter, "p0".."p4" bei Positionsrätseln), die die Verkleidung restlos
# durch echte Namen ersetzen muss (D4, SPEC_lektionen_v2.md §6). Bleibt eine
# übrig, hat das Kind auf einmal einen Code statt eines Namens vor sich.
KENNUNG_UEBRIG = re.compile(r"\bk\d+e\d+\b|\bp\d+\b")

# Nichts davon in einer Aufgabe für ein Kind, auch nicht spielerisch gemeint.
# Die Endungen stehen ausgeschrieben statt als \w* – sonst gilt die harmlose
# Waffel als Waffe und eine korrekte Aufgabe wird grundlos abgelehnt.
TABU = re.compile(
    r"\b(?:tot|tote[nrs]?|töte[nt]?|getötet|stirbt|sterben|gestorben|"
    r"ermorde[tn]|erschossen|blut|waffen?|drogen?|kriege?|selbstmord|"
    r"nazis?|dumm(?:e[nrs]?)?|blöd(?:e[nrs]?)?|idiot(?:en)?)\b", re.I)


# ------------------------------------------------------- Terme nachrechnen

_OPS = {
    ast.Add: ("+", lambda a, b: a + b),
    ast.Sub: ("-", lambda a, b: a - b),
    ast.Mult: ("*", lambda a, b: a * b),
    ast.Div: ("/", lambda a, b: a / b if b else None),
    ast.FloorDiv: ("/", lambda a, b: a // b if b else None),
    ast.Mod: ("/", lambda a, b: a % b if b else None),
    ast.Pow: ("^", lambda a, b: a ** b),
}


class TermError(Exception):
    pass


def eval_term(expr):
    """Wertet einen Rechenausdruck aus. Rückgabe: (Wert, benutzte Operatoren).

    Bewusst kein eval(): der Ausdruck kommt aus einem Sprachmodell. Erlaubt
    sind ausschließlich Zahlen, Klammern und die Grundrechenarten.
    """
    if not isinstance(expr, str) or not expr.strip():
        raise TermError("leerer Term")
    if len(expr) > 120:
        raise TermError("Term zu lang")
    try:
        tree = ast.parse(expr.replace("×", "*").replace("÷", "/").replace("−", "-"),
                         mode="eval")
    except SyntaxError:
        raise TermError(f"Term nicht lesbar: {expr!r}")

    ops = set()

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise TermError("nur Zahlen erlaubt")
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = walk(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            sym, fn = _OPS[type(node.op)]
            ops.add(sym)
            v = fn(walk(node.left), walk(node.right))
            if v is None:
                raise TermError("Teilen durch null")
            return v
        raise TermError(f"nicht erlaubt: {type(node).__name__}")

    return walk(tree), ops


def _near(a, b):
    """Zahlenvergleich, der 3.0 und 3 gleich behandelt und Rundung verzeiht."""
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return False


def _as_number(v):
    """Zieht die Zahl aus einer Antwortmöglichkeit.

    Antworten stehen oft mit Einheit da ("42 Klötze", "3 cm", "1,50 €") — das
    liest sich für ein Kind besser als eine nackte Zahl. Verglichen wird
    trotzdem die Zahl. Rückgabe None, wenn keine drinsteckt.
    """
    m = NUM_IN_TEXT.search(str(v).strip())
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


# ------------------------------------------------------------ Einzelprüfer

def _check_text(t, out, stage, label="Frage"):
    """Text prüfen: Länge, Platzhalter, Tabuwörter, Zahlenraum."""
    if not isinstance(t, str) or not t.strip():
        out.append(f"{label} fehlt")
        return
    if len(t) > MAX_Q:
        out.append(f"{label} zu lang ({len(t)} Zeichen, erlaubt {MAX_Q})")
    if JUNK.search(t):
        out.append(f"{label} enthält Platzhalter oder Formelsatz: {t[:60]!r}")
    if TABU.search(t):
        out.append(f"{label} enthält ein Wort, das in einer Kinderaufgabe nichts zu suchen hat")
    lim = C.max_value(stage)
    for m in NUM_IN_TEXT.findall(t):
        try:
            v = float(m.replace(",", "."))
        except ValueError:
            continue
        # Jahreszahlen und Uhrzeiten sind keine Rechengrößen
        if v > lim and not (1900 <= v <= 2100):
            out.append(f"{label}: Zahl {m} sprengt den Zahlenraum der Stufe {stage} (bis {lim})")


def _check_term(check, stage, expect, out, label="Term"):
    """Rechnet den mitgelieferten Term nach und vergleicht mit der Antwort."""
    if not isinstance(check, dict) or "expr" not in check:
        out.append(f"{label}: kein nachrechenbarer Term mitgeliefert")
        return
    try:
        value, ops = eval_term(check["expr"])
    except TermError as e:
        out.append(f"{label}: {e}")
        return

    if not _near(value, expect):
        out.append(f"{label}: {check['expr']} ergibt {value}, angegeben ist aber {expect}")

    erlaubt = C.ops_allowed(stage)
    for op in ops - erlaubt:
        out.append(f"{label}: Rechenart '{op}' ist auf Stufe {stage} noch nicht dran")

    lim = C.max_value(stage)
    if abs(value) > lim:
        out.append(f"{label}: Ergebnis {value} sprengt den Zahlenraum (bis {lim})")
    if value < 0 and stage < 6:
        out.append(f"{label}: negatives Ergebnis {value} – kennt ein Kind auf Stufe {stage} nicht")
    if value != int(value) and "/" not in ops:
        out.append(f"{label}: krummes Ergebnis {value} ohne Division")


def _check_options(opts, correct, out):
    """Auswahlaufgaben: genau eine richtig, nichts doppelt, nichts verräterisch."""
    if not isinstance(opts, list) or not 3 <= len(opts) <= 4:
        out.append("Auswahl braucht 3 oder 4 Möglichkeiten")
        return
    if not isinstance(correct, int) or not 0 <= correct < len(opts):
        out.append(f"richtige Antwort verweist auf Platz {correct}, den es nicht gibt")
        return
    norm = [str(o).strip().lower() for o in opts]
    if any(not o for o in norm):
        out.append("leere Antwortmöglichkeit")
    if len(set(norm)) != len(norm):
        out.append(f"doppelte Antwortmöglichkeit: {opts}")

    # Die richtige Antwort darf nicht die auffällig längste oder kürzeste sein –
    # sonst rät man sie an der Form, ohne die Aufgabe verstanden zu haben.
    # Bei kurzen Antworten (reine Zahlen) sagt die Länge nichts: dass 5 kürzer
    # ist als 12, verrät die Lösung nicht.
    lens = [len(str(o)) for o in opts]
    if max(lens) >= 8:
        right, others = lens[correct], [l for i, l in enumerate(lens) if i != correct]
        if right > max(others) * 1.6 or right * 1.6 < min(others):
            out.append(f"richtige Antwort fällt durch ihre Länge auf ({lens}, "
                       f"richtig ist Platz {correct})")


# ----------------------------------------------------------- je Aufgabentyp

def _v_entdecken(t, stage, out):
    _check_text(t.get("q"), out, stage)
    if not t.get("info"):
        out.append("Entdecken-Aufgabe ohne Erklärung")
    else:
        _check_text(t["info"], out, stage, "Erklärung")


def _v_zahl(t, stage, out):
    _check_text(t.get("q"), out, stage)
    a = t.get("a")
    if not isinstance(a, (int, float)) or isinstance(a, bool):
        out.append(f"Antwort ist keine Zahl: {a!r}")
        return
    _check_term(t.get("check"), stage, a, out)


def _v_wahl(t, stage, out):
    _check_text(t.get("q"), out, stage)
    opts, correct = t.get("opts"), t.get("correct")
    _check_options(opts, correct, out)
    # Rechnerische Auswahlaufgaben werden zusätzlich nachgerechnet: der Term
    # muss die als richtig markierte Option treffen – und keine andere.
    check = t.get("check")
    if isinstance(check, dict) and "expr" in check and isinstance(opts, list) \
            and isinstance(correct, int) and 0 <= correct < len(opts):
        try:
            value, ops = eval_term(check["expr"])
        except TermError as e:
            out.append(f"Term: {e}")
            return
        richtig = _as_number(opts[correct])
        if richtig is None:
            out.append(f"die richtige Antwort {opts[correct]!r} enthält keine Zahl, "
                       f"lässt sich also nicht gegen den Term {check['expr']} prüfen")
        elif not _near(value, richtig):
            out.append(f"Term {check['expr']} ergibt {value}, "
                       f"die als richtig markierte Antwort ist aber {opts[correct]!r}")
        for i, o in enumerate(opts):
            if i == correct:
                continue
            andere = _as_number(o)
            if andere is not None and _near(value, andere):
                out.append(f"Antwort {i} ({o!r}) stimmt ebenfalls – es darf nur eine richtige geben")
        for op in ops - C.ops_allowed(stage):
            out.append(f"Rechenart '{op}' ist auf Stufe {stage} noch nicht dran")


def _v_wahrfalsch(t, stage, out):
    _check_text(t.get("q"), out, stage)
    a = t.get("a")
    if not isinstance(a, bool):
        out.append(f"Wahr/Falsch braucht true oder false, nicht {a!r}")
        return
    # Behauptung der Form "12+3" == "15": beide Seiten werden gerechnet
    check = t.get("check")
    if isinstance(check, dict) and "left" in check and "right" in check:
        try:
            lv, lops = eval_term(check["left"])
            rv, rops = eval_term(check["right"])
        except TermError as e:
            out.append(f"Behauptung: {e}")
            return
        stimmt = _near(lv, rv)
        if stimmt != a:
            out.append(f"{check['left']} = {lv} und {check['right']} = {rv} → "
                       f"die Behauptung ist {stimmt}, angegeben ist {a}")
        for op in (lops | rops) - C.ops_allowed(stage):
            out.append(f"Rechenart '{op}' ist auf Stufe {stage} noch nicht dran")
    elif not check:
        out.append("Wahr/Falsch ohne nachprüfbare Behauptung")


def _v_ordnen(t, stage, out):
    _check_text(t.get("q"), out, stage)
    items, order = t.get("items"), t.get("order")
    if not isinstance(items, list) or not 3 <= len(items) <= 6:
        out.append("Ordnen braucht 3 bis 6 Dinge")
        return
    if not isinstance(order, list) or sorted(order) != list(range(len(items))):
        out.append(f"Reihenfolge {order!r} passt nicht zu {len(items)} Dingen")
        return
    if len(set(map(str, items))) != len(items):
        out.append("dieselbe Zahl steht zweimal in der Reihe")
    # Nur numerische Reihen lassen sich hart nachprüfen – die prüfen wir dann auch.
    try:
        vals = [float(str(i).replace(",", ".")) for i in items]
    except ValueError:
        out.append("Ordnen ist nur mit Zahlen zugelassen – sonst ist die Lösung nicht prüfbar")
        return
    sortiert = [i for i, _ in sorted(enumerate(vals), key=lambda p: p[1])]
    if order not in (sortiert, sortiert[::-1]):
        out.append(f"Reihenfolge {order} ist weder auf- noch absteigend richtig "
                   f"(richtig wäre {sortiert})")
    lim = C.max_value(stage)
    for v in vals:
        if v > lim:
            out.append(f"Zahl {v} sprengt den Zahlenraum (bis {lim})")


def _v_zuordnen(t, stage, out):
    _check_text(t.get("q"), out, stage)
    pairs = t.get("pairs")
    if not isinstance(pairs, list) or not 3 <= len(pairs) <= 5:
        out.append("Zuordnen braucht 3 bis 5 Paare")
        return
    links, rechts = [], []
    for p in pairs:
        if not isinstance(p, list) or len(p) != 2 or not all(str(x).strip() for x in p):
            out.append(f"kaputtes Paar: {p!r}")
            return
        links.append(str(p[0]).strip().lower())
        rechts.append(str(p[1]).strip().lower())
        _check_text(str(p[0]), out, stage, "linke Seite")
        _check_text(str(p[1]), out, stage, "rechte Seite")
    if len(set(links)) != len(links) or len(set(rechts)) != len(rechts):
        out.append("eine Karte kommt doppelt vor – die Zuordnung wäre nicht eindeutig")


def _v_mehrschritt(t, stage, out):
    _check_text(t.get("q"), out, stage)
    steps = t.get("steps")
    if not isinstance(steps, list) or not 2 <= len(steps) <= 3:
        out.append("Mehrschritt braucht 2 oder 3 Schritte")
        return
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict):
            out.append(f"Schritt {i} ist kaputt")
            continue
        _check_text(s.get("q"), out, stage, f"Schritt {i}")
        a = s.get("a")
        if not isinstance(a, (int, float)) or isinstance(a, bool):
            out.append(f"Schritt {i}: Antwort ist keine Zahl ({a!r})")
            continue
        _check_term(s.get("check"), stage, a, out, f"Schritt {i}")


def _v_gitter(t, stage, out):
    _check_text(t.get("q"), out, stage)
    grid = t.get("grid")
    if not isinstance(grid, list) or not 1 <= len(grid) <= 8:
        out.append("Gitter braucht 1 bis 8 Zeilen")
        return
    breite = None
    for r, row in enumerate(grid):
        if not isinstance(row, list) or not 1 <= len(row) <= 8:
            out.append(f"Gitterzeile {r} ist keine Reihe aus 1 bis 8 Feldern")
            return
        if breite is None:
            breite = len(row)
        elif len(row) != breite:
            out.append("Gitterzeilen sind unterschiedlich lang")
            return
        for cell in row:
            if not isinstance(cell, str) or len(cell) > 2:
                out.append(f"Gitterfeld {cell!r} ist kein kurzes Zeichen")
                return
    # Antwort ist entweder ein Feld (Zeile/Spalte) oder eine Auswahl
    if "cell" in t:
        c = t["cell"]
        if not (isinstance(c, list) and len(c) == 2
                and 0 <= c[0] < len(grid) and 0 <= c[1] < breite):
            out.append(f"Lösungsfeld {c!r} liegt nicht im Gitter")
    elif "opts" in t:
        _check_options(t.get("opts"), t.get("correct"), out)
    else:
        out.append("Gitteraufgabe ohne Lösung (weder Feld noch Auswahl)")


def _hoechstens_n_saetze(text, n):
    """Wie viele Satzenden (. ! ?) ein Text hat – großzügig gezählt, eine
    Folge von Satzzeichen ('?!') gilt als ein Satzende. Dieselbe grobe Prüfung
    wie verkleidung._hoechstens_ein_satz, hier verallgemeinert auf n Sätze."""
    return len(re.findall(r"[.!?]+", text.strip())) <= n


def _v_logikgitter(t, stage, out):
    """Logikgitter (D4): Lösbarkeit, Hinweise, Frage und Optionen prüft
    vollständig validate_v2.pruefe_logikgitter_aufgabe (delegiert an
    raetsel_kern.pruefe_logikgitter – keine zweite, potenziell abweichende
    Prüflogik). Hier kommen nur die üblichen Formregeln hinzu, die für ein
    Kind bei jedem Aufgabentyp gelten: keine Platzhalter oder Tabuwörter,
    keine liegen gebliebene interne Kennung (k0e0, ...), Hinweistexte
    höchstens zwei Sätze.
    """
    _, maengel = V2.pruefe_logikgitter_aufgabe(t)
    out.extend(maengel)

    prosa = [("Frage", t.get("frage_text")), ("Rahmengeschichte", t.get("rahmen"))]
    hinweise = t.get("hinweise") if isinstance(t.get("hinweise"), list) else []
    for i, h in enumerate(hinweise, 1):
        if isinstance(h, dict):
            prosa.append((f"Hinweis {i}", h.get("text")))
    for label, text in prosa:
        if isinstance(text, str) and text.strip():
            _check_text(text, out, stage, label)

    for i, h in enumerate(hinweise, 1):
        text = h.get("text") if isinstance(h, dict) else None
        if isinstance(text, str) and not _hoechstens_n_saetze(text, 2):
            out.append(f"Hinweis {i}: Hinweistext ist länger als zwei Sätze: {text!r}")

    alle_texte = [text for _, text in prosa if isinstance(text, str)]
    alle_texte += [o for o in (t.get("optionen") or []) if isinstance(o, str)]
    alle_texte += [n for kat in (t.get("kategorien") or []) if isinstance(kat, list)
                   for n in kat if isinstance(n, str)]
    for text in alle_texte:
        gefunden = sorted(set(KENNUNG_UEBRIG.findall(text)))
        if gefunden:
            out.append(f"Platzhalter-Kennung(en) stehen noch unverkleidet im Text: "
                       f"{gefunden} ({text!r})")


def _kennungen_pruefen(texte, out):
    """Wie der Kennungs-Scan am Ende von _v_logikgitter, als eigene kleine
    Funktion für die vier neuen Typen (SPEC_lektionen_v2.md §2-§6): keine
    liegen gebliebene interne Platzhalter-Kennung ("k0e0", "p0"..."p4") darf
    in einem sprachlichen Text stehen bleiben."""
    for text in texte:
        if not isinstance(text, str):
            continue
        gefunden = sorted(set(KENNUNG_UEBRIG.findall(text)))
        if gefunden:
            out.append(f"Platzhalter-Kennung(en) stehen noch unverkleidet im Text: "
                       f"{gefunden} ({text!r})")


def _v_svg_liste(liste, out, label):
    """Prüft eine Liste von SVG-Strings: genau 4, jedes beginnt mit '<svg',
    keines enthält '<script' (SPEC_lektionen_v2.md §3: Sicherheitsnetz gegen
    eingeschleusten Code in einem an sich vertrauenswürdigen, aber
    maschinell zusammengesetzten Feld)."""
    if not isinstance(liste, list) or len(liste) != 4:
        out.append(f"{label} braucht genau 4 SVGs, hat "
                   f"{len(liste) if isinstance(liste, list) else liste!r}")
        return
    for i, svg in enumerate(liste):
        if not isinstance(svg, str) or not svg.strip().startswith("<svg"):
            out.append(f"{label} {i}: beginnt nicht mit '<svg'")
        elif "<script" in svg:
            out.append(f"{label} {i}: enthält '<script' – das darf niemals ausgeliefert werden")


def _v_bildwahl(t, stage, out):
    """bildwahl (SPEC §3): Frage- und Optionsbilder als reines SVG, genau
    eine richtige Option; die Wahrheit selbst kommt ausschließlich aus dem
    mitgelieferten 'kern' (grafik_kern.pruefe_spiegelbild/pruefe_drehfigur
    bzw. muster_kern.pruefe_matrix/pruefe_analogie je nach kern.art) – nie
    aus dem SVG-Text, der wird hier nur auf Form und Sicherheit geprüft."""
    _check_text(t.get("q"), out, stage)
    svg = t.get("svg")
    if not isinstance(svg, str) or not svg.strip().startswith("<svg"):
        out.append("Fragebild ist kein gültiges SVG (beginnt nicht mit '<svg')")
    elif "<script" in svg:
        out.append("Fragebild enthält '<script'")
    _v_svg_liste(t.get("optionen_svg"), out, "Options-SVG")

    richtig = t.get("richtig")
    if not isinstance(richtig, int) or isinstance(richtig, bool) or not (0 <= richtig < 4):
        out.append(f"'richtig'={richtig!r} ist kein gültiger Options-Index (0..3)")

    kern = t.get("kern")
    if not isinstance(kern, dict):
        out.append("bildwahl ohne 'kern' – die Wahrheit fehlt")
        return
    art = kern.get("art")
    pruefer = {
        "spiegelbild": GK.pruefe_spiegelbild, "drehfigur": GK.pruefe_drehfigur,
        "matrix": MK.pruefe_matrix, "analogie": MK.pruefe_analogie,
    }.get(art)
    if pruefer is None:
        out.append(f"bildwahl: unbekannte kern.art {art!r}")
        return
    ok, grund = pruefer(kern)
    if not ok:
        out.append(f"Kern lehnt die Aufgabe ab: {grund}")
    if kern.get("richtig") != richtig:
        out.append(f"'richtig'={richtig!r} stimmt nicht mit kern.richtig={kern.get('richtig')!r} überein")

    _kennungen_pruefen([t.get("q")], out)


def _v_bildzahl(t, stage, out):
    """bildzahl (SPEC §4): Würfelgebäude zählen. Kein Rechenterm – der Kern
    (grafik_kern.pruefe_wuerfelgebaeude) ist die Wahrheit, wie bei bildwahl."""
    _check_text(t.get("q"), out, stage)
    svg = t.get("svg")
    if not isinstance(svg, str) or not svg.strip().startswith("<svg"):
        out.append("Bild ist kein gültiges SVG (beginnt nicht mit '<svg')")
    elif "<script" in svg:
        out.append("Bild enthält '<script'")

    a = t.get("a")
    if not isinstance(a, (int, float)) or isinstance(a, bool):
        out.append(f"Antwort ist keine Zahl: {a!r}")
        a = None

    kern = t.get("kern")
    if not isinstance(kern, dict) or kern.get("art") != "wuerfelgebaeude":
        out.append("bildzahl ohne gültigen 'kern' (kern.art muss 'wuerfelgebaeude' sein)")
        return
    ok, grund = GK.pruefe_wuerfelgebaeude(kern)
    if not ok:
        out.append(f"Kern lehnt die Aufgabe ab: {grund}")
    if a is not None and kern.get("anzahl") != a:
        out.append(f"a={a!r} stimmt nicht mit kern.anzahl={kern.get('anzahl')!r} überein")

    _kennungen_pruefen([t.get("q")], out)


# Hinweistyp -> die Felder ('a'/'b'/'c'), die auf einen Subjekt-Index zeigen.
# Dieselben elf Typen wie in raetsel_kern._pos_hinweis_erfuellt.
_POS_HINWEIS_FELDER = {
    "ganz_links": ("a",), "ganz_rechts": ("a",), "mitte": ("a",), "nicht_rand": ("a",),
    "direkt_links": ("a", "b"), "direkt_rechts": ("a", "b"),
    "links_von": ("a", "b"), "rechts_von": ("a", "b"),
    "neben": ("a", "b"), "nicht_neben": ("a", "b"),
    "zwischen": ("a", "b", "c"),
}
# Verneinungs-Hinweistypen: ihr Text muss "nicht" oder "kein" enthalten
# (SPEC_lektionen_v2.md §6) – dieselbe Regel wie bei 'nicht' im Logikgitter.
_POS_VERNEINUNG = {"nicht_neben", "nicht_rand"}

_ARTIKEL = {"der", "die", "das", "den", "dem", "des",
            "ein", "eine", "einen", "einem", "einer", "eines"}


def _wortkern(name):
    """Der Name ohne führenden Artikel ('der Astronaut' -> 'Astronaut') –
    dieses Wort muss (auch flektiert, z.B. 'Astronauten' im Dativ) in jedem
    Hinweistext auftauchen, der dieses Subjekt betrifft (SPEC §6)."""
    if not isinstance(name, str):
        return ""
    teile = name.strip().split(None, 1)
    if len(teile) == 2 and teile[0].lower() in _ARTIKEL:
        return teile[1].strip()
    return name.strip()


def _v_positionen(t, stage, out):
    """positionen (SPEC §6): Logikrätsel ohne Zahlen, in einer Reihe statt
    einem Gitter. Struktur- und Sprachprüfung hier; die Wahrheit selbst
    (eindeutig lösbar? stimmt die Lösung?) kommt ausschließlich aus
    raetsel_kern.pruefe_positionen() – dafür werden die ganzzahligen
    Subjekt-Indizes dieses App-Formats zurück auf die "pN"-Kennungen
    abgebildet, mit denen der Kern rechnet."""
    rahmen = t.get("rahmen")
    if isinstance(rahmen, str) and rahmen.strip():
        _check_text(rahmen, out, stage, "Rahmengeschichte")
    else:
        out.append("Rahmengeschichte fehlt")

    namen = t.get("namen")
    if not isinstance(namen, list) or not (3 <= len(namen) <= 5):
        out.append(f"'namen' braucht 3 bis 5 Einträge, hat "
                   f"{len(namen) if isinstance(namen, list) else namen!r}")
        return
    if len(set(namen)) != len(namen):
        out.append(f"doppelter Name in 'namen': {namen!r}")
    n = len(namen)

    hinweise = t.get("hinweise")
    if not isinstance(hinweise, list) or not hinweise:
        out.append("'hinweise' fehlt oder ist keine Liste")
        return

    kern_hinweise = []
    for i, h in enumerate(hinweise, 1):
        if not isinstance(h, dict) or "typ" not in h or "a" not in h:
            out.append(f"Hinweis {i} ist unvollständig: {h!r}")
            continue
        typ = h["typ"]
        felder = _POS_HINWEIS_FELDER.get(typ)
        if felder is None:
            out.append(f"Hinweis {i}: unbekannter Hinweistyp {typ!r}")
            continue

        indices, indices_ok = {}, True
        for feld in felder:
            idx = h.get(feld)
            if not isinstance(idx, int) or isinstance(idx, bool) or not (0 <= idx < n):
                out.append(f"Hinweis {i}: Feld {feld!r}={idx!r} ist kein gültiger Subjekt-Index")
                indices_ok = False
            else:
                indices[feld] = idx

        text = h.get("text")
        if not isinstance(text, str) or not text.strip():
            out.append(f"Hinweis {i}: Text fehlt")
        else:
            _check_text(text, out, stage, f"Hinweis {i}")
            if not _hoechstens_n_saetze(text, 2):
                out.append(f"Hinweis {i}: Hinweistext ist länger als zwei Sätze: {text!r}")
            if indices_ok:
                for feld, idx in indices.items():
                    kern_wort = _wortkern(namen[idx])
                    if not kern_wort or kern_wort not in text:
                        out.append(f"Hinweis {i}: Text {text!r} enthält nicht den Namen von "
                                   f"{namen[idx]!r} (Wortkern {kern_wort!r})")
            if typ in _POS_VERNEINUNG:
                tl = text.lower()
                if "nicht" not in tl and "kein" not in tl:
                    out.append(f"Hinweis {i}: Verneinung fehlt im Text {text!r} "
                               "(weder 'nicht' noch 'kein')")

        if indices_ok:
            kh = {"typ": typ, "a": f"p{indices['a']}"}
            if "b" in indices:
                kh["b"] = f"p{indices['b']}"
            if "c" in indices:
                kh["c"] = f"p{indices['c']}"
            kern_hinweise.append(kh)

    loesung = t.get("loesung")
    if not isinstance(loesung, list) or sorted(loesung) != list(range(n)):
        out.append(f"'loesung' {loesung!r} ist keine Permutation von 0..{n - 1}")
        return

    ergebnis = K.pruefe_positionen(n, kern_hinweise, [f"p{i}" for i in loesung])
    if not ergebnis["eindeutig"]:
        out.append(f"Rätsel ist nicht eindeutig lösbar ({ergebnis['loesungen_gezaehlt']} Lösungen passen)")
    elif not ergebnis["stimmt"]:
        out.append("die angegebene Lösung stimmt nicht mit der einzig gültigen Zuordnung überein")

    frage = t.get("frage")
    ziel_idx = None
    if not isinstance(frage, dict) or frage.get("art") not in ("position", "neben"):
        out.append(f"'frage' fehlt oder hat eine ungültige Art: {frage!r}")
    elif frage["art"] == "position":
        p = frage.get("p")
        if not isinstance(p, int) or isinstance(p, bool) or not (0 <= p < n):
            out.append(f"'frage.p'={p!r} ist keine gültige Position (0..{n - 1})")
        else:
            ziel_idx = loesung[p]
    else:  # "neben"
        a_idx, seite = frage.get("a"), frage.get("seite")
        if not isinstance(a_idx, int) or isinstance(a_idx, bool) or not (0 <= a_idx < n):
            out.append(f"'frage.a'={a_idx!r} ist kein gültiger Subjekt-Index")
        elif seite not in ("links", "rechts"):
            out.append(f"'frage.seite'={seite!r} ist weder 'links' noch 'rechts'")
        else:
            pos_a = loesung.index(a_idx)
            nachbar_pos = pos_a - 1 if seite == "links" else pos_a + 1
            if not (0 <= nachbar_pos < n):
                out.append(f"'frage': {namen[a_idx]!r} hat keinen Nachbarn auf der Seite {seite!r}")
            else:
                ziel_idx = loesung[nachbar_pos]

    optionen = t.get("optionen")
    richtig = t.get("richtig")
    if not isinstance(optionen, list) or sorted(optionen) != sorted(namen):
        out.append(f"'optionen' muss genau alle Namen enthalten (gemischt): {optionen!r}")
    elif not isinstance(richtig, int) or isinstance(richtig, bool) or not (0 <= richtig < len(optionen)):
        out.append(f"'richtig'={richtig!r} zeigt auf keine vorhandene Option")
    elif ziel_idx is not None and optionen[richtig] != namen[ziel_idx]:
        out.append(f"'richtig' zeigt auf {optionen[richtig]!r}, erwartet wäre {namen[ziel_idx]!r}")

    frage_text = t.get("frage_text")
    if not isinstance(frage_text, str) or not frage_text.strip():
        out.append("'frage_text' fehlt")
    else:
        _check_text(frage_text, out, stage, "Frage")
        if ziel_idx is not None and namen[ziel_idx] in frage_text:
            out.append(f"'frage_text' {frage_text!r} nennt den Namen der Antwort ({namen[ziel_idx]!r})")

    _kennungen_pruefen(
        [rahmen, frage_text] + [h.get("text") for h in hinweise if isinstance(h, dict)] + list(namen),
        out,
    )


def _v_roboter(t, stage, out):
    """roboter (SPEC §2): Formregeln hier (Text, keine liegen gebliebene
    Kennung); die Wahrheit selbst (Simulation, kürzeste Lösung, eindeutige
    Reparatur) kommt ausschließlich aus algo_kern.pruefe_roboter() – derselben
    Funktion, die auch algo_kern.erzeuge_* beim Erzeugen jeden Kandidaten
    nachrechnen lässt. Keine zweite, potenziell abweichende Prüflogik."""
    _check_text(t.get("q"), out, stage)
    ok, grund = AK.pruefe_roboter(t)
    if not ok:
        out.append(f"Kern lehnt die Aufgabe ab: {grund}")
    _kennungen_pruefen([t.get("q")], out)


VALIDATORS = {
    "entdecken": _v_entdecken, "zahl": _v_zahl, "wahl": _v_wahl,
    "wahrfalsch": _v_wahrfalsch, "ordnen": _v_ordnen, "zuordnen": _v_zuordnen,
    "mehrschritt": _v_mehrschritt, "gitter": _v_gitter,
    "logikgitter": _v_logikgitter,
    "bildwahl": _v_bildwahl, "bildzahl": _v_bildzahl, "positionen": _v_positionen,
    "roboter": _v_roboter,
}


# --------------------------------------------------------------- Außenseite

def check_task(task, stage, allowed_types=None):
    """Prüft eine einzelne Aufgabe. Rückgabe: Liste der Mängel (leer = gut)."""
    out = []
    if not isinstance(task, dict):
        return ["Aufgabe ist kein Objekt"]
    typ = task.get("type")
    if typ not in VALIDATORS:
        return [f"unbekannter Aufgabentyp {typ!r}"]
    # 'logikgitter' ist von curriculum.py's Typlisten bewusst ausgenommen: die
    # Fertigkeit log_gitter ist dort (unverändert, D4 betrifft nur diesen
    # Prüfer) noch mit dem alten Typ "zuordnen" eingetragen. Welche Fertigkeit
    # den deterministischen Kern nutzt, entscheidet allein generate_units.py
    # (pfad_von) – hier reicht die vollständige Delegation an validate_v2.
    if allowed_types and typ not in allowed_types and typ != "logikgitter":
        out.append(f"Aufgabentyp {typ!r} ist für diese Fertigkeit nicht vorgesehen "
                   f"(erlaubt: {', '.join(allowed_types)})")
    VALIDATORS[typ](task, stage, out)
    if task.get("hint"):
        _check_text(task["hint"], out, stage, "Tipp")
    return out


def _kalkuel_terme(task):
    """Sammelt alle prüfbaren Rechen-Terme einer Aufgabe für das
    Rechenlast-Budget (D2, ZIELE-V2.md): 'check.expr' bei zahl/wahl, beide
    Seiten der Behauptung bei wahrfalsch, je Schritt bei mehrschritt.
    Aufgabentypen ohne Rechen-Term (entdecken, ordnen, zuordnen, gitter,
    logikgitter) liefern eine leere Liste – für sie ist ein Kalkül-Budget
    sinnlos, sie werden von diesem Mechanismus einfach nicht erfasst.
    Rückgabe: Liste aus (Label, Term)."""
    if not isinstance(task, dict):
        return []
    typ, check, terme = task.get("type"), task.get("check"), []
    if typ in ("zahl", "wahl") and isinstance(check, dict) and isinstance(check.get("expr"), str):
        terme.append(("Term", check["expr"]))
    elif typ == "wahrfalsch" and isinstance(check, dict):
        for seite in ("left", "right"):
            if isinstance(check.get(seite), str):
                terme.append((f"Behauptung ({seite})", check[seite]))
    elif typ == "mehrschritt":
        for i, s in enumerate(task.get("steps") or [], 1):
            if isinstance(s, dict) and isinstance(s.get("check"), dict) \
                    and isinstance(s["check"].get("expr"), str):
                terme.append((f"Schritt {i}", s["check"]["expr"]))
    return terme


def _pruefe_kalkuel_budget(tasks, budget, out):
    """Rechenlast-Budget (D2): Jeder prüfbare Term einer Disziplin-Aufgabe
    darf höchstens 'budget' elementare Rechenschritte kosten
    (validate_v2.pruefe_kalkuel). Ein Term, der schon am eval_term()-Pfad
    scheitert (nicht lesbar, verboten), wird hier übersprungen – dafür ist
    der bestehende Fehlerpfad zuständig, er soll durch diesen zusätzlichen
    Mechanismus weder verdoppelt noch verändert werden.
    """
    for i, t in enumerate(tasks, 1):
        for label, expr in _kalkuel_terme(t):
            try:
                eval_term(expr)
            except TermError:
                continue
            kalkuel_ok, begruendung = V2.pruefe_kalkuel(expr, budget)
            if not kalkuel_ok:
                out.append(f"Aufgabe {i}: {label}: Rechenlast-Budget überschritten – {begruendung}")


def check_unit(unit):
    """Prüft ein ganzes Lernpaket. Rückgabe: Liste der Mängel (leer = gut)."""
    out = []
    if not isinstance(unit, dict):
        return ["Paket ist kein Objekt"]

    sid = unit.get("skill")
    sk = C.skill(sid) if isinstance(sid, str) else None
    if not sk:
        return [f"unbekannte Fertigkeit {sid!r}"]

    stage = unit.get("stage", sk["stage"])
    if stage not in C.STAGES:
        out.append(f"Stufe {stage!r} gibt es nicht")
        stage = sk["stage"]
    # Eine Fertigkeit darf auf ihrer eigenen Stufe oder knapp darüber geübt
    # werden, aber nicht darunter – sonst ist der Zahlenraum zu eng.
    if stage < sk["stage"]:
        out.append(f"Stufe {stage} liegt unter der Stufe {sk['stage']} dieser Fertigkeit")
    if stage > sk["stage"] + 1:
        out.append(f"Stufe {stage} liegt mehr als eine Stufe über {sk['stage']}")

    if not unit.get("title"):
        out.append("Paket ohne Titel")
    elif len(unit["title"]) > 40:
        out.append(f"Titel zu lang ({len(unit['title'])} Zeichen)")

    tasks = unit.get("tasks")
    if not isinstance(tasks, list) or not MIN_TASKS <= len(tasks) <= MAX_TASKS:
        out.append(f"Paket braucht {MIN_TASKS} bis {MAX_TASKS} Aufgaben, hat aber "
                   f"{len(tasks) if isinstance(tasks, list) else 'keine Liste'}")
        return out

    fragen = []
    for i, t in enumerate(tasks, 1):
        for m in check_task(t, stage, sk["types"]):
            out.append(f"Aufgabe {i}: {m}")
        if isinstance(t, dict) and isinstance(t.get("q"), str):
            fragen.append(t["q"].strip().lower())
    if len(set(fragen)) != len(fragen):
        out.append("dieselbe Frage kommt im Paket zweimal vor")

    # Rechenlast-Budget (D2): nur für Fertigkeiten, die einer der fünf
    # Denkdisziplinen zugeordnet sind (disziplinen.disziplin_von). Pre-Lesson-
    # und sonstige reine Rechenfertigkeiten (disziplin_von liefert None)
    # bleiben unberührt – für sie gilt kein Deckel.
    disziplin = D.disziplin_von(sid)
    if disziplin is not None:
        _pruefe_kalkuel_budget(tasks, D.DISZIPLINEN[disziplin]["kalkuel_budget"], out)

    return out


def filter_units(units, verbose=True):
    """Trennt gültige von fehlerhaften Paketen. Rückgabe: (gut, [(Paket, Mängel)])."""
    good, bad = [], []
    for u in units:
        problems = check_unit(u)
        if problems:
            bad.append((u, problems))
            if verbose:
                print(f'  [xx] {u.get("skill", "?")} · {u.get("title", "?")}')
                for p in problems[:4]:
                    print(f"        {p}")
        else:
            good.append(u)
            if verbose:
                print(f'  [ok] {u.get("skill", "?")} · {u.get("title", "?")} '
                      f'({len(u["tasks"])} Aufgaben)')
    return good, bad


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Aufruf: validate.py <units.json>")
    data = json.loads(Path(sys.argv[1]).read_text("utf-8"))
    units = data["units"] if isinstance(data, dict) else data
    good, bad = filter_units(units)
    print(f"\n{len(good)} von {len(units)} Paketen in Ordnung, {len(bad)} abgelehnt")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
