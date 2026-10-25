# -*- coding: utf-8 -*-
"""Der deterministische Rechenkern für den Denk-Check (ZIELE-V3.md, G4).

Dimension "rechnen": der Schulstoff-Anker neben den Denkdimensionen. Reine
Rechenaufgaben ohne Geschichte ("47 + 38 = ?"), damit der Check zeigt, wo das
Kind rechnerisch steht — getrennt von dem, was es denkend kann. Gerade bei
einem Kind, dessen Denken weit vor der Rechenfertigkeit liegt, ist diese
Trennung der Sinn: Eine falsche Rechenaufgabe soll nie wie eine
Denkschwäche aussehen.

Die Aufgabe entsteht aus Zahlen, nicht aus Text: erst werden die Zahlen
gewürfelt (mit den Bedingungen der Stufe), dann wird daraus `q`, `a` und der
nachrechenbare Term `check.expr` gebaut. Antwort und Term kommen aus derselben
Rechnung in Python, nie aus einem Sprachmodell.

Rechenlast-Budget (D2): ein Term kostet hier höchstens 3 elementare Schritte
(validate_v2.kalkuel_kosten), der Deckel der Disziplinen liegt bei 6. Die
Stufen steigern die Art des Rechnens (Übergang, Einmaleins, halbschriftlich),
nicht die Zahl der Schritte.

Seeds nur über zlib.crc32 von Text (kein hash()), Zufall nur über
random.Random(seed). Kein eval(): die Antwort wird als Python-Zahl gerechnet.
"""
import random
import zlib

# Die Stufen sind die Lehrplanstufen aus curriculum.STAGES (Zahlenraum und
# erlaubte Rechenarten), wie überall sonst in der App: "Stufe 4" heißt im
# Denk-Check dasselbe wie im Paket "mal_teilen@4". Darum besteht jede Aufgabe
# validate.check_task(aufgabe, stufe) bei ihrer eigenen Stufe.


def _rng(*teile):
    """Zufall aus Text, nie aus hash() (das ist je Lauf anders)."""
    return random.Random(zlib.crc32("|".join(str(t) for t in teile).encode("utf-8")))


def _zahl(n):
    """Zahl für den Fragetext: ab 10 000 mit Tausenderpunkt ("345.000"), wie
    es ein Kind in der Schule liest und wie es der Vorlese-Dienst spricht."""
    return f"{n:,}".replace(",", ".") if n >= 10000 else str(n)


def _aufgabe(links, op, rechts, ergebnis, hinweis):
    """Baut die zahl-Aufgabe. `op` ist "+", "-", "*" oder "/"; im Fragetext
    steht das Zeichen, das das Kind kennt (× bzw. :), im Term das, was der
    Validator rechnen kann."""
    zeichen = {"+": "+", "-": "-", "*": "×", "/": ":"}[op]
    return {"type": "zahl",
            "q": f"{_zahl(links)} {zeichen} {_zahl(rechts)} = ?",
            "a": ergebnis,
            "check": {"expr": f"{links} {op} {rechts}"},
            "hint": hinweis}


# ----------------------------------------------------------------- die Stufen

def _stufe2(rng):
    """Zahlenraum 20 mit Zehnerübergang (8 + 7, 15 − 8)."""
    if rng.random() < 0.5:
        a, b = rng.randint(3, 9), rng.randint(3, 9)
        while a + b <= 10:
            a, b = rng.randint(3, 9), rng.randint(3, 9)
        return _aufgabe(a, "+", b, a + b, "Erst bis zur 10, dann den Rest.")
    a, b = rng.randint(11, 18), rng.randint(3, 9)
    while a % 10 >= b:
        a, b = rng.randint(11, 18), rng.randint(3, 9)
    return _aufgabe(a, "-", b, a - b, "Erst bis zur 10 zurück, dann den Rest.")


def _stufe3(rng):
    """Zahlenraum 100 mit Übergang, oder kleines Einmaleins."""
    r = rng.random()
    if r < 0.34:
        a, b = rng.randint(11, 89), rng.randint(11, 89)
        while a % 10 + b % 10 < 10 or a + b > 100:
            a, b = rng.randint(11, 89), rng.randint(11, 89)
        return _aufgabe(a, "+", b, a + b, "Geh über die nächste Zehnerzahl: erst bis dahin, dann den Rest.")
    if r < 0.67:
        a, b = rng.randint(21, 99), rng.randint(11, 89)
        while b >= a or a % 10 >= b % 10:
            a, b = rng.randint(21, 99), rng.randint(11, 89)
        return _aufgabe(a, "-", b, a - b, "Geh über die nächste Zehnerzahl: erst bis dahin, dann den Rest.")
    a, b = rng.randint(3, 9), rng.randint(3, 9)
    return _aufgabe(a, "*", b, a * b, "Denk an die Reihe des Einmaleins.")


def _stufe4(rng):
    """Zahlenraum 100: glatt geteilt (72 : 8) oder die schweren Reihen (7 × 8)."""
    if rng.random() < 0.5:
        d, q = rng.randint(3, 9), rng.randint(3, 10)
        return _aufgabe(d * q, "/", d, q, f"Welche Zahl mal {d} ergibt {d * q}?")
    a, b = rng.randint(6, 9), rng.randint(6, 9)
    return _aufgabe(a, "*", b, a * b, "Nimm eine Aufgabe, die du sicher weißt, und geh von dort aus.")


def _stufe5(rng):
    """Zahlenraum 1000: plus und minus, oder mal 10."""
    r = rng.random()
    if r < 0.4:
        a = rng.randint(101, 799)
        b = rng.randint(101, 999 - a)
        return _aufgabe(a, "+", b, a + b, "Rechne Hunderter, Zehner und Einer nacheinander.")
    if r < 0.8:
        a = rng.randint(301, 999)
        b = rng.randint(101, a - 1)
        return _aufgabe(a, "-", b, a - b, "Rechne Hunderter, Zehner und Einer nacheinander.")
    a = rng.randint(11, 99)
    return _aufgabe(a, "*", 10, a * 10, "Jede Ziffer rutscht eine Stelle nach links.")


def _stufe6(rng):
    """Halbschriftlich: zweistellig mal einstellig."""
    a, b = rng.randint(12, 99), rng.randint(3, 9)
    while a % 10 == 0:
        a = rng.randint(12, 99)
    return _aufgabe(a, "*", b, a * b, "Zerlege die große Zahl: erst die Zehner mal, dann die Einer mal.")


def _stufe7(rng):
    """Zahlenraum 100 000, plus: volle Hunderter, damit der Kopf rechnet
    und nicht nur Nullen schiebt."""
    a = rng.randint(120, 640) * 100
    b = rng.randint(120, (100000 - a) // 100 - 1) * 100
    return _aufgabe(a, "+", b, a + b, "Lass die zwei Nullen weg und rechne mit den Zahlen davor.")


def _stufe8(rng):
    """Zweistellig mal zweistellig."""
    a, b = rng.randint(12, 49), rng.randint(11, 29)
    while a % 10 == 0 or b % 10 == 0 or a == b:
        a, b = rng.randint(12, 49), rng.randint(11, 29)
    return _aufgabe(a, "*", b, a * b, "Zerlege die zweite Zahl: erst mit den Zehnern, dann mit den Einern.")


STUFEN = {2: _stufe2, 3: _stufe3, 4: _stufe4, 5: _stufe5, 6: _stufe6, 7: _stufe7, 8: _stufe8}


def denkcheck_aufgabe(stufe, seed):
    """Eine reine Rechenaufgabe der Dimension "rechnen", Stufe 2..8.

    Derselbe (stufe, seed) liefert immer dieselbe Aufgabe.
    """
    if stufe not in STUFEN:
        raise ValueError(f"stufe {stufe!r} liegt nicht in 2..8")
    return STUFEN[stufe](_rng("rechnen", stufe, seed))
