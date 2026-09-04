# -*- coding: utf-8 -*-
"""Der deterministische Spielkern für die Denkschule (ZIELE-V2.md, Abschnitt D4).

Deckt die in D4 genannte Rätselart "Kombinatorik & Strategie" ab, konkret das
Nimm-Spiel "Der letzte Stein" (ZIELE-V2.md, D1: komb_nim):

  n Steine liegen auf einem Haufen. Zwei Spieler nehmen abwechselnd 1 bis k
  Steine weg; wer den letzten Stein nimmt, gewinnt. Das ist die klassische
  Nim-Variante mit einem einzigen Haufen und einer Ober­grenze k pro Zug.

Die Spieltheorie dahinter ist bekannt (der Spieler am Zug gewinnt sicher
genau dann, wenn n mod (k+1) ≠ 0, und der einzige sichere Zug ist dann
m = n mod (k+1)) – genau DESHALB ist sie hier zweimal unabhängig
voneinander implementiert, nicht einmal:

  * erzeuge_nim() nutzt beim Auswürfeln zwar dieselbe Modulo-Formel (das ist
    schlicht die schnellste Art, eine Gewinnstellung zu erzeugen),
  * pruefe_nim() rechnet die Gewinnstrategie aber komplett unabhängig davon
    per Rückwärtsinduktion nach: eine Tabelle gewinnt[i] für i = 0..n wird
    Stein für Stein aus gewinnt[0] = False aufgebaut, OHNE die Modulo-Formel
    zu benutzen. Ein Tippfehler in der Formel an einer der beiden Stellen
    würde dann sofort auffallen, statt sich in beide Richtungen gleich
    "richtig" zu rechnen.

Wie bei raetsel_kern.py gilt: Schwierigkeit ist Denktiefe, nie Zahlengröße
(ZIELE-V2.md, D2). Die höhere Nim-Stufe (6 statt 5) erlaubt zwar auch etwas
größere Zahlen, der eigentliche Denksprung ist aber ein anderer: mehr
mögliche Zugweiten (k=3 statt k=2) und – ab Schwierigkeit 4 – ein Gegner, der
zuerst zieht, sodass das Kind erst die neue Lage ausrechnen muss, bevor es
seinen eigenen Gewinnzug findet (ein zusätzlicher gedanklicher Zwischen-
schritt, keine größere Zahl an sich).

Reiner Standardbibliotheks-Code, vollständig seedbar über random.Random(seed):
Derselbe Seed liefert byte-gleich dieselbe Aufgabe. Kein LLM, kein eval(),
kein hash().
"""
import random


# ============================================================ Konstanten

# Stufe → (k, erlaubter Bereich für die Steinzahl n). Höhere Stufe heißt mehr
# mögliche Zugweiten (k), nicht einfach nur mehr Steine – siehe Moduldocstring.
_STUFEN = {
    5: {"k": 2, "n_bereich": range(5, 16)},   # 5..15
    6: {"k": 3, "n_bereich": range(7, 21)},   # 7..20
}


def _variante_aus_schwierigkeit(schwierigkeit):
    """Schwierigkeit 0..5 steuert die Aufgabenform, nicht die Zahlengröße:
    0-1 der reine Gewinnzug (`zug`), 2-3 der gedanklich einen Schritt
    weitere "was bleibt übrig"-Rahmen (`rest`), 4-5 zusätzlich ein Gegner-
    Vorzug, den das Kind erst verrechnen muss, bevor es seinen Zug sucht
    (`gegner`) – das ist der zusätzliche Zwischenschritt, der laut D2 echte
    Schwierigkeit ausmacht.
    """
    if schwierigkeit <= 1:
        return "zug"
    if schwierigkeit <= 3:
        return "rest"
    return "gegner"


def erzeuge_nim(stufe, seed, schwierigkeit):
    """Erzeugt eine Nim-Aufgabe: das Kind steht vor n Steinen (direkt oder
    nach einem Gegner-Vorzug) und muss den einzigen sicheren Gewinnzug finden.

    stufe ∈ {5, 6} legt k fest (Stufe 5: k=2, Steine 5..15; Stufe 6: k=3,
    Steine 7..20). schwierigkeit 0..5 wählt die Variante (siehe
    _variante_aus_schwierigkeit). seed macht die Ziehung reproduzierbar.

    Garantie, die pruefe_nim() unabhängig nachrechnet: Die Stellung, in der
    das Kind tatsächlich zieht (n bei 'zug'/'rest', n-g bei 'gegner'), ist
    IMMER eine Gewinnstellung – ein Kind, das den Kern richtig durchdenkt,
    kann also nie in eine unlösbare Lage geraten.

    Ergebnis-Struktur (dict):
      n            – Steinzahl zu Beginn (vor einem eventuellen Gegnerzug)
      k            – höchste erlaubte Zugweite
      zug          – der einzige sichere Gewinnzug des Kindes
      rest         – wie viele Steine nach diesem Zug übrig bleiben
      variante     – "zug" | "rest" | "gegner"
      gegner_nimmt – wie viele Steine der Gegner zuerst nimmt, sonst None
      stufe        – die übergebene Stufe (zur Rückverfolgung)
    Bei variante "gegner" zusätzlich:
      n_nach_gegner – n - gegner_nimmt; die Stellung, vor der das Kind
                      tatsächlich steht (darauf beziehen sich zug und rest)
    """
    if stufe not in _STUFEN:
        raise ValueError(f"stufe muss 5 oder 6 sein, nicht {stufe!r}")

    rng = random.Random(seed)
    k = _STUFEN[stufe]["k"]
    n_bereich = _STUFEN[stufe]["n_bereich"]
    variante = _variante_aus_schwierigkeit(schwierigkeit)

    if variante in ("zug", "rest"):
        # Nur Steinzahlen, bei denen das Kind tatsächlich am Zug eine
        # Gewinnstellung vorfindet (n mod (k+1) ≠ 0), kommen infrage.
        kandidaten = [n for n in n_bereich if n % (k + 1) != 0]
        n = rng.choice(kandidaten)
        m = n % (k + 1)
        return {
            "n": n,
            "k": k,
            "zug": m,
            "rest": n - m,
            "variante": variante,
            "gegner_nimmt": None,
            "stufe": stufe,
        }

    # variante == "gegner": der Gegner nimmt zuerst g ∈ 1..k Steine; die
    # Lage, in der das Kind zieht, ist n' = n - g, und NUR sie muss eine
    # Gewinnstellung sein (die Ausgangslage n selbst darf beliebig sein –
    # der Gegner zieht ja nicht zwingend "richtig").
    kandidaten = [
        (n, g)
        for n in n_bereich
        for g in range(1, k + 1)
        if (n - g) >= 1 and (n - g) % (k + 1) != 0
    ]
    n, g = rng.choice(kandidaten)
    n_nach_gegner = n - g
    m = n_nach_gegner % (k + 1)
    return {
        "n": n,
        "k": k,
        "zug": m,
        "rest": n_nach_gegner - m,
        "variante": "gegner",
        "gegner_nimmt": g,
        "n_nach_gegner": n_nach_gegner,
        "stufe": stufe,
    }


def _gewinntabelle(n_kind, k):
    """Baut die Gewinn-/Verlusttabelle per Rückwärtsinduktion, Stein für
    Stein von unten nach oben – das ist absichtlich NICHT die Modulo-Formel
    n mod (k+1) ≠ 0 (siehe Moduldocstring): gewinnt[0] = False (wer bei 0
    Steinen am Zug ist, hat schon verloren – der andere hat den letzten
    Stein genommen); gewinnt[i] ist True, sobald irgendein erlaubter Zug
    1..min(k, i) den Gegner in eine Stellung mit gewinnt[...] == False
    zwingt.
    """
    gewinnt = [False] * (n_kind + 1)
    for i in range(1, n_kind + 1):
        gewinnt[i] = any(not gewinnt[i - m] for m in range(1, min(k, i) + 1))
    return gewinnt


def pruefe_nim(a):
    """Prüft eine Nim-Aufgabe unabhängig per Rückwärtsinduktion (siehe
    _gewinntabelle) – nicht per Modulo-Formel, siehe Moduldocstring.

    Verträgt kaputte Eingaben ohne Absturz: liefert dann (False, Grund)
    statt eine Exception zu werfen.

    Rückgabe: (ok, grund) – ok ist genau dann True, wenn
      * k eine sinnvolle Zugweite ist (k ≥ 1),
      * die Stellung, vor der das Kind steht, überhaupt eine Gewinnstellung
        ist,
      * 'zug' unter allen erlaubten Zügen 1..min(k, n_kind) der EINZIGE
        Gewinnzug ist (kein anderer Zug schickt den Gegner ebenfalls in eine
        Verluststellung),
      * 'rest' korrekt aus n_kind - zug berechnet ist und selbst eine
        Verluststellung für den Gegner ist.
    Bei 'gegner' wird zusätzlich geprüft, dass gegner_nimmt ∈ 1..k liegt und
    n_nach_gegner tatsächlich n - gegner_nimmt ist.
    """
    if not isinstance(a, dict):
        return False, "Eingabe ist kein dict"

    k = a.get("k")
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        return False, f"k außerhalb des gültigen Bereichs (muss ≥ 1 sein): {k!r}"

    variante = a.get("variante")
    if variante == "gegner":
        n_start = a.get("n")
        g = a.get("gegner_nimmt")
        n_kind = a.get("n_nach_gegner")
        if not isinstance(n_start, int) or isinstance(n_start, bool):
            return False, f"'n' kaputt: {n_start!r}"
        if not isinstance(g, int) or isinstance(g, bool) or not (1 <= g <= k):
            return False, f"'gegner_nimmt' außerhalb 1..{k}: {g!r}"
        if not isinstance(n_kind, int) or isinstance(n_kind, bool):
            return False, f"'n_nach_gegner' kaputt: {n_kind!r}"
        if n_kind != n_start - g:
            return False, f"'n_nach_gegner' ({n_kind}) passt nicht zu n ({n_start}) - gegner_nimmt ({g})"
    elif variante in ("zug", "rest"):
        n_kind = a.get("n")
        if not isinstance(n_kind, int) or isinstance(n_kind, bool):
            return False, f"'n' kaputt: {n_kind!r}"
    else:
        return False, f"unbekannte Variante: {variante!r}"

    if n_kind < 1:
        return False, f"keine Steine mehr übrig, wenn das Kind ziehen soll: n={n_kind}"

    zug = a.get("zug")
    rest = a.get("rest")
    if not isinstance(zug, int) or isinstance(zug, bool):
        return False, f"'zug' kaputt: {zug!r}"
    if not isinstance(rest, int) or isinstance(rest, bool):
        return False, f"'rest' kaputt: {rest!r}"
    if not (1 <= zug <= min(k, n_kind)):
        return False, f"'zug' außerhalb 1..{min(k, n_kind)}: {zug}"
    if rest != n_kind - zug:
        return False, f"'rest' passt nicht zu n und zug: erwartet {n_kind - zug}, bekommen {rest}"

    gewinnt = _gewinntabelle(n_kind, k)

    if not gewinnt[n_kind]:
        return False, f"Stellung mit {n_kind} Steinen ist selbst schon eine Verluststellung"

    gewinnzuege = [m for m in range(1, min(k, n_kind) + 1) if not gewinnt[n_kind - m]]
    if gewinnzuege != [zug]:
        return False, f"'{zug}' ist nicht der einzige Gewinnzug (per Rückwärtsinduktion gefunden: {gewinnzuege})"

    if gewinnt[rest]:
        return False, f"'rest'={rest} ist selbst noch eine Gewinnstellung für den Gegner, keine Verluststellung"

    return True, "ok"
