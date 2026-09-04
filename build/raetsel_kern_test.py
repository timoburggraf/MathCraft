# -*- coding: utf-8 -*-
"""Prüft den deterministischen Rätselkern (raetsel_kern.py).

Der Kern ist die einzige Stelle, die künftig garantiert, dass ein
Logikgitter überhaupt lösbar ist und eine Zahlenfolge wirklich der
angegebenen Regel folgt. Also wird er selbst geprüft, im selben Geist wie
validator_test.py den Validator prüft: absichtlich kaputte Rätsel müssen
ausnahmslos erkannt werden – und eine große Menge frisch erzeugter Rätsel
muss ausnahmslos in Ordnung sein. Ein Prüfer, der alles ablehnt, wäre genauso
wertlos wie einer, der alles durchwinkt.

  .venv/bin/python build/raetsel_kern_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import raetsel_kern as K

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


def hinweis(typ, a, b):
    """Baut einen Hinweis von Hand, im dokumentierten Format – ohne die
    internen Hilfsfunktionen von raetsel_kern.py zu benutzen. So testet
    dieser Test die öffentliche Schnittstelle, nicht die Implementierung.
    """
    return {"typ": typ, "a": list(a), "b": list(b)}


# ============================================== Logikgitter: viele Rätsel

def logikgitter_serie(n_kategorien, n_elemente, anzahl_seeds):
    """Erzeugt anzahl_seeds Logikgitter derselben Größe und prüft für jedes:
    eindeutig lösbar, die angegebene Lösung stimmt, und JEDER einzelne
    Hinweis ist notwendig (sein Entfernen macht das Rätsel mehrdeutig).

    Rückgabe: (geprüft, bestanden, erster Fehler als Text).
    """
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        raetsel = K.erzeuge_logikgitter(n_kategorien, n_elemente, seed)
        ergebnis = K.pruefe_logikgitter(raetsel["kategorien"], raetsel["hinweise"], raetsel["loesung"])
        geprueft += 1
        fehler = None
        if not (ergebnis["eindeutig"] and ergebnis["stimmt"] and ergebnis["loesungen_gezaehlt"] == 1):
            fehler = f"seed {seed}: Rätsel selbst ist nicht sauber lösbar ({ergebnis})"
        else:
            hinweise = raetsel["hinweise"]
            for i in range(len(hinweise)):
                teilmenge = hinweise[:i] + hinweise[i + 1:]
                probe = K.pruefe_logikgitter(raetsel["kategorien"], teilmenge, raetsel["loesung"])
                if probe["eindeutig"]:
                    fehler = f"seed {seed}: Hinweis {i} ({hinweise[i]['text']}) ist überflüssig"
                    break
        if fehler:
            erster_fehler = erster_fehler or fehler
        else:
            bestanden += 1
    return geprueft, bestanden, erster_fehler


GESAMT_LOGIKGITTER = 0
GESAMT_BESTANDEN_LOGIKGITTER = 0
for (n_kat, n_el, anzahl) in [(2, 3, 80), (2, 4, 60), (3, 3, 40), (3, 4, 20)]:
    geprueft, bestanden, fehler = logikgitter_serie(n_kat, n_el, anzahl)
    GESAMT_LOGIKGITTER += geprueft
    GESAMT_BESTANDEN_LOGIKGITTER += bestanden
    ok(f"{geprueft} Logikgitter ({n_kat} Kategorien × {n_el} Elemente): "
       f"eindeutig, minimal, Lösung bestätigt",
       geprueft == bestanden, fehler)

ok(f"insgesamt {GESAMT_LOGIKGITTER} Logikgitter über alle Größen und Seeds erzeugt",
   GESAMT_LOGIKGITTER >= 200 and GESAMT_BESTANDEN_LOGIKGITTER == GESAMT_LOGIKGITTER,
   f"{GESAMT_BESTANDEN_LOGIKGITTER}/{GESAMT_LOGIKGITTER} bestanden")

# Reproduzierbarkeit: derselbe Seed liefert byte-gleich dasselbe Rätsel.
gleich_a = K.erzeuge_logikgitter(3, 4, seed=2026)
gleich_b = K.erzeuge_logikgitter(3, 4, seed=2026)
ok("gleicher Seed liefert byte-gleiches Logikgitter", gleich_a == gleich_b)

verschieden = K.erzeuge_logikgitter(3, 4, seed=2027)
ok("unterschiedlicher Seed liefert ein anderes Logikgitter", gleich_a != verschieden)


# ============================================ Logikgitter: kaputte Rätsel
# Handgebaute Hinweissätze, die der Prüfer erkennen MUSS: mehrdeutig,
# unlösbar/widersprüchlich oder im Widerspruch zur angegebenen Lösung.

KAT_2x3 = [["k0e0", "k0e1", "k0e2"], ["k1e0", "k1e1", "k1e2"]]
LOESUNG_2x3 = {"k1": [1, 2, 0]}  # k0e0→k1e1, k0e1→k1e2, k0e2→k1e0 (die einzig wahre Lösung)

ist_0_1 = hinweis("ist", ["k0", 0], ["k1", 1])   # wahr
ist_1_2 = hinweis("ist", ["k0", 1], ["k1", 2])   # wahr
ist_2_0 = hinweis("ist", ["k0", 2], ["k1", 0])   # wahr, aber durch die anderen zwei bereits erzwungen

r = K.pruefe_logikgitter(KAT_2x3, [], LOESUNG_2x3)
ok("leere Hinweisliste wird als mehrdeutig erkannt",
   not r["eindeutig"] and r["loesungen_gezaehlt"] == 6, str(r))

r = K.pruefe_logikgitter(KAT_2x3, [ist_0_1], LOESUNG_2x3)
ok("ein einzelner Hinweis reicht nicht und wird als mehrdeutig erkannt",
   not r["eindeutig"] and r["loesungen_gezaehlt"] == 2, str(r))

widerspruch_gleiches_subjekt = hinweis("ist", ["k0", 0], ["k1", 2])  # k0e0 kann nicht zugleich k1e1 UND k1e2 sein
r = K.pruefe_logikgitter(KAT_2x3, [ist_0_1, widerspruch_gleiches_subjekt], LOESUNG_2x3)
ok("zwei sich widersprechende 'ist'-Hinweise machen das Rätsel unlösbar",
   r["loesungen_gezaehlt"] == 0, str(r))

nicht_0_1 = hinweis("nicht", ["k0", 0], ["k1", 1])  # widerspricht ist_0_1 direkt (dasselbe Paar)
r = K.pruefe_logikgitter(KAT_2x3, [ist_0_1, nicht_0_1], LOESUNG_2x3)
ok("'ist' und 'nicht' für dasselbe Paar widersprechen sich und machen es unlösbar",
   r["loesungen_gezaehlt"] == 0, str(r))

LOESUNG_2x3_FALSCH = {"k1": [2, 1, 0]}
r = K.pruefe_logikgitter(KAT_2x3, [ist_0_1, ist_1_2], LOESUNG_2x3_FALSCH)
ok("eindeutige, korrekte Hinweise widersprechen einer falsch angegebenen Lösung",
   r["eindeutig"] and not r["stimmt"], str(r))

nicht_1_2_falsch = hinweis("nicht", ["k0", 1], ["k1", 2])  # widerspricht ist_1_2 (dasselbe Paar)
r = K.pruefe_logikgitter(KAT_2x3, [ist_0_1, ist_1_2, nicht_1_2_falsch], LOESUNG_2x3)
ok("ein Widerspruch mitten in sonst korrekten Hinweisen macht alles unlösbar",
   r["loesungen_gezaehlt"] == 0, str(r))

referenz_kaputt = hinweis("ist", ["k0", 9], ["k1", 1])  # Subjekt 9 existiert bei n_elemente=3 nicht
r = K.pruefe_logikgitter(KAT_2x3, [ist_1_2, referenz_kaputt], LOESUNG_2x3)
ok("ein Hinweis mit Index außerhalb des Gitters macht es unlösbar statt abzustürzen",
   r["loesungen_gezaehlt"] == 0, str(r))

typ_unbekannt = {"typ": "vielleicht", "a": ["k0", 0], "b": ["k1", 1]}
r = K.pruefe_logikgitter(KAT_2x3, [ist_1_2, typ_unbekannt], LOESUNG_2x3)
ok("ein Hinweis mit unbekanntem Typ gilt sicherheitshalber als nie erfüllt und macht es unlösbar",
   r["loesungen_gezaehlt"] == 0, str(r))

# Dieselben Fehlerarten auch über eine Kategoriengrenze hinweg (k1×k2), wie
# es die typischen Verkettungen im echten Rätsel erzeugen.
KAT_3x3 = [["k0e0", "k0e1", "k0e2"], ["k1e0", "k1e1", "k1e2"], ["k2e0", "k2e1", "k2e2"]]
LOESUNG_3x3 = {"k1": [1, 2, 0], "k2": [2, 0, 1]}  # Subjekt 1 trägt k1e2 UND k2e0

k1k2_wahr = hinweis("ist", ["k1", 2], ["k2", 0])
r = K.pruefe_logikgitter(KAT_3x3, [k1k2_wahr], LOESUNG_3x3)
ok("ein einzelner k1×k2-Hinweis reicht bei drei Kategorien nicht und ist mehrdeutig",
   not r["eindeutig"], str(r))

k1k2_falsch = hinweis("ist", ["k1", 2], ["k2", 1])  # widerspricht k1k2_wahr (dasselbe a, anderes b)
r = K.pruefe_logikgitter(KAT_3x3, [k1k2_wahr, k1k2_falsch], LOESUNG_3x3)
ok("zwei widersprüchliche k1×k2-Hinweise machen ein Drei-Kategorien-Rätsel unlösbar",
   r["loesungen_gezaehlt"] == 0, str(r))


# ==================================================== Folgen: viele Regeln

def folgen_serie(regeltyp, anzahl_seeds, max_wert=1000, laenge=5):
    """Erzeugt anzahl_seeds Folgen desselben Regeltyps und prüft: die Regel
    bestätigt Glieder und Fortsetzung, kein Ablenker gleicht der Lösung, alle
    drei Ablenker sind paarweise verschieden, und der Zahlenraum-Deckel hält.

    Rückgabe: (geprüft, bestanden, erster Fehler als Text).
    """
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        f = K.erzeuge_folge(regeltyp, seed=seed, laenge=laenge, max_wert=max_wert)
        geprueft += 1
        fehler = None
        if not K.pruefe_folge(f["glieder"], f["naechstes"], f["regel"]):
            fehler = f"seed {seed}: Folge widerspricht ihrer eigenen Regel"
        elif f["naechstes"] in f["ablenker"]:
            fehler = f"seed {seed}: ein Ablenker gleicht der Lösung"
        elif len(set(f["ablenker"])) != 3:
            fehler = f"seed {seed}: Ablenker sind nicht paarweise verschieden ({f['ablenker']})"
        elif not all(0 <= wert <= max_wert for wert in f["glieder"] + [f["naechstes"]] + f["ablenker"]):
            fehler = f"seed {seed}: Zahlenraum-Deckel {max_wert} verletzt"
        if fehler:
            erster_fehler = erster_fehler or fehler
        else:
            bestanden += 1
    return geprueft, bestanden, erster_fehler


GESAMT_FOLGEN = 0
GESAMT_BESTANDEN_FOLGEN = 0
for regeltyp in K.REGELTYPEN:
    geprueft, bestanden, fehler = folgen_serie(regeltyp, anzahl_seeds=30)
    GESAMT_FOLGEN += geprueft
    GESAMT_BESTANDEN_FOLGEN += bestanden
    ok(f"{geprueft} Folgen vom Typ '{regeltyp}': Regel bestätigt, Ablenker sauber, Deckel gehalten",
       geprueft == bestanden, fehler)

ok(f"insgesamt {GESAMT_FOLGEN} Folgen über alle Regeltypen erzeugt",
   GESAMT_FOLGEN >= 100 and GESAMT_BESTANDEN_FOLGEN == GESAMT_FOLGEN,
   f"{GESAMT_BESTANDEN_FOLGEN}/{GESAMT_FOLGEN} bestanden")

# Reproduzierbarkeit auch bei den Folgen.
folge_a = K.erzeuge_folge("wechsel", seed=99, laenge=6)
folge_b = K.erzeuge_folge("wechsel", seed=99, laenge=6)
ok("gleicher Seed liefert byte-gleiche Folge", folge_a == folge_b)

folge_c = K.erzeuge_folge("wechsel", seed=100, laenge=6)
ok("unterschiedlicher Seed liefert eine andere Folge", folge_a != folge_c)

# Ein Beispiel je Regeltyp von Hand nachvollzogen, zur Absicherung, dass die
# Formeln auch wirklich das tun, was ihr Name verspricht.
beispiel = K.erzeuge_folge("plus", seed=1, laenge=4)
ok("Beispiel 'plus': jedes Glied ist das vorige plus die feste Schrittweite d",
   all(beispiel["glieder"][i] - beispiel["glieder"][i - 1] == beispiel["regel"]["d"]
       for i in range(1, len(beispiel["glieder"]))),
   str(beispiel["glieder"]))

beispiel = K.erzeuge_folge("mal", seed=1, laenge=4)
ok("Beispiel 'mal': jedes Glied ist das vorige mal dem festen Faktor q",
   all(beispiel["glieder"][i] == beispiel["glieder"][i - 1] * beispiel["regel"]["q"]
       for i in range(1, len(beispiel["glieder"]))),
   str(beispiel["glieder"]))

beispiel = K.erzeuge_folge("wachsend", seed=1, laenge=5)
ok("Beispiel 'wachsend': die Schrittweite selbst wächst um 1, 2, 3, …",
   [beispiel["glieder"][i] - beispiel["glieder"][i - 1] for i in range(1, len(beispiel["glieder"]))] == [1, 2, 3, 4],
   str(beispiel["glieder"]))

beispiel = K.erzeuge_folge("fibo", seed=1, laenge=5)
ok("Beispiel 'fibo': jedes Glied ist die Summe der zwei vorigen",
   all(beispiel["glieder"][i] == beispiel["glieder"][i - 1] + beispiel["glieder"][i - 2]
       for i in range(2, len(beispiel["glieder"]))),
   str(beispiel["glieder"]))


# =============================================== Folgen: kaputte Prüfungen

f = K.erzeuge_folge("plus", seed=7, laenge=5)
ok("pruefe_folge lehnt eine falsche Fortsetzung ab",
   not K.pruefe_folge(f["glieder"], f["naechstes"] + 1, f["regel"]))

f = K.erzeuge_folge("mal", seed=7, laenge=5)
verfaelscht = list(f["glieder"])
verfaelscht[-1] += 1
ok("pruefe_folge lehnt ein verfälschtes Glied ab",
   not K.pruefe_folge(verfaelscht, f["naechstes"], f["regel"]))

f = K.erzeuge_folge("wachsend", seed=7, laenge=5)
regel_verfaelscht = dict(f["regel"], start=f["regel"]["start"] + 1)
ok("pruefe_folge lehnt eine verfälschte Regel ab",
   not K.pruefe_folge(f["glieder"], f["naechstes"], regel_verfaelscht))

ok("pruefe_folge stürzt bei unbekanntem Regeltyp nicht ab, sondern lehnt ab",
   K.pruefe_folge([1, 2, 3], 4, {"typ": "erfunden"}) is False)

ok("pruefe_folge lehnt eine leere Gliederliste ab",
   K.pruefe_folge([], 1, {"typ": "plus", "start": 1, "d": 1}) is False)


# ============================================ Positionsrätsel: viele Rätsel

def pos_hinweis(typ, a, b=None, c=None):
    """Baut einen Positions-Hinweis von Hand, im dokumentierten Format – ohne
    die internen Hilfsfunktionen von raetsel_kern.py zu benutzen (dieselbe
    Absicht wie beim hinweis()-Helfer oben: die öffentliche Schnittstelle
    testen, nicht die Implementierung).
    """
    h = {"typ": typ, "a": a}
    if b is not None:
        h["b"] = b
    if c is not None:
        h["c"] = c
    return h


def frage_verraet_antwort(raetsel):
    """Unabhängige Gegenprobe zu erzeuge_positionen()'s eigener Garantie: Baut
    aus 'loesung' und 'frage' die erwartete Antwort nach und prüft, ob ein
    verbliebener Hinweis sie wörtlich preisgibt – ohne raetsel_kern-interne
    Hilfsfunktionen zu benutzen.
    """
    n = raetsel["n"]
    hinweise = raetsel["hinweise"]
    frage = raetsel["frage"]
    if frage["art"] == "position":
        p = frage["p"]
        if p == 0 and any(h.get("typ") == "ganz_links" for h in hinweise):
            return True
        if p == n - 1 and any(h.get("typ") == "ganz_rechts" for h in hinweise):
            return True
        if n % 2 == 1 and p == n // 2 and any(h.get("typ") == "mitte" for h in hinweise):
            return True
        return False
    if frage["art"] == "neben":
        loesung = raetsel["loesung"]
        pos = {subjekt: index for index, subjekt in enumerate(loesung)}
        a = frage["a"]
        pa = pos[a]
        nachbar = loesung[pa + 1] if frage["seite"] == "rechts" else loesung[pa - 1]
        paar = {a, nachbar}
        return any(
            h.get("typ") in ("direkt_links", "direkt_rechts") and {h.get("a"), h.get("b")} == paar
            for h in hinweise
        )
    return False


def positionen_serie(n, anzahl_seeds):
    """Erzeugt für n Subjekte anzahl_seeds Positionsrätsel – je einmal mit der
    niedrigsten (Schwierigkeit 0) und der höchsten Stufe (Schwierigkeit 5) –
    und prüft für jedes: eindeutig lösbar (per eigener Permutations-
    Enumeration in pruefe_positionen nachgerechnet), die angegebene Lösung
    stimmt, JEDER einzelne Hinweis ist notwendig (sein Entfernen macht das
    Rätsel mehrdeutig), und die Frage wird von keinem verbliebenen Hinweis
    wörtlich verraten.

    Rückgabe: (geprüft, bestanden, erster Fehler als Text).
    """
    geprueft = bestanden = 0
    erster_fehler = ""
    for seed in range(anzahl_seeds):
        for schwierigkeit in (0, 5):
            raetsel = K.erzeuge_positionen(n, seed, schwierigkeit=schwierigkeit)
            ergebnis = K.pruefe_positionen(raetsel["n"], raetsel["hinweise"], raetsel["loesung"])
            geprueft += 1
            fehler = None
            if not (ergebnis["eindeutig"] and ergebnis["stimmt"] and ergebnis["loesungen_gezaehlt"] == 1):
                fehler = (f"n={n} schwierigkeit={schwierigkeit} seed={seed}: "
                          f"Rätsel selbst ist nicht sauber lösbar ({ergebnis})")
            else:
                hinweise = raetsel["hinweise"]
                for i in range(len(hinweise)):
                    teilmenge = hinweise[:i] + hinweise[i + 1:]
                    probe = K.pruefe_positionen(raetsel["n"], teilmenge, raetsel["loesung"])
                    if probe["eindeutig"]:
                        fehler = (f"n={n} schwierigkeit={schwierigkeit} seed={seed}: "
                                  f"Hinweis {i} ({hinweise[i]['text']}) ist überflüssig")
                        break
                if not fehler and frage_verraet_antwort(raetsel):
                    fehler = (f"n={n} schwierigkeit={schwierigkeit} seed={seed}: "
                              f"Frage verrät die Antwort direkt ({raetsel['frage']})")
            if fehler:
                erster_fehler = erster_fehler or fehler
            else:
                bestanden += 1
    return geprueft, bestanden, erster_fehler


GESAMT_POSITIONEN = 0
GESAMT_BESTANDEN_POSITIONEN = 0
for n in (4, 5):
    geprueft, bestanden, fehler = positionen_serie(n, anzahl_seeds=60)
    GESAMT_POSITIONEN += geprueft
    GESAMT_BESTANDEN_POSITIONEN += bestanden
    ok(f"{geprueft} Positionsrätsel (n={n}, je 60 Seeds bei Schwierigkeit 0 & 5): "
       f"eindeutig, minimal, Lösung bestätigt, Frage nicht verraten",
       geprueft == bestanden, fehler)

ok(f"insgesamt {GESAMT_POSITIONEN} Positionsrätsel über n=4/5 und Schwierigkeit 0/5 erzeugt",
   GESAMT_POSITIONEN >= 240 and GESAMT_BESTANDEN_POSITIONEN == GESAMT_POSITIONEN,
   f"{GESAMT_BESTANDEN_POSITIONEN}/{GESAMT_POSITIONEN} bestanden")

# Reproduzierbarkeit: derselbe Seed liefert byte-gleich dasselbe Rätsel.
pos_gleich_a = K.erzeuge_positionen(5, seed=2026, schwierigkeit=3)
pos_gleich_b = K.erzeuge_positionen(5, seed=2026, schwierigkeit=3)
ok("gleicher Seed liefert byte-gleiches Positionsrätsel", pos_gleich_a == pos_gleich_b)

pos_verschieden = K.erzeuge_positionen(5, seed=2027, schwierigkeit=3)
ok("unterschiedlicher Seed liefert ein anderes Positionsrätsel", pos_gleich_a != pos_verschieden)


# ========================================== Positionsrätsel: kaputte Rätsel
# Handgebaute Hinweissätze, die der Prüfer erkennen MUSS: mehrdeutig,
# unlösbar/widersprüchlich oder im Widerspruch zur angegebenen Lösung.

LOESUNG_P3 = ["p1", "p0", "p2"]  # p1 ganz links, p0 in der Mitte, p2 ganz rechts

p1_links = pos_hinweis("ganz_links", "p1")   # wahr
p2_rechts = pos_hinweis("ganz_rechts", "p2")  # wahr

r = K.pruefe_positionen(3, [], LOESUNG_P3)
ok("leere Hinweisliste wird als mehrdeutig erkannt",
   not r["eindeutig"] and r["loesungen_gezaehlt"] == 6, str(r))

r = K.pruefe_positionen(3, [p1_links], LOESUNG_P3)
ok("ein einzelner Hinweis reicht nicht und wird als mehrdeutig erkannt",
   not r["eindeutig"] and r["loesungen_gezaehlt"] == 2, str(r))

r_voll = K.pruefe_positionen(3, [p1_links, p2_rechts], LOESUNG_P3)
ok("zwei zusammenpassende Hinweise ergeben Eindeutigkeit und bestätigen die Lösung",
   r_voll["eindeutig"] and r_voll["stimmt"] and r_voll["loesungen_gezaehlt"] == 1, str(r_voll))

r_entfernt = K.pruefe_positionen(3, [p1_links], LOESUNG_P3)  # p2_rechts entfernt
ok("entfernter Hinweis macht ein zuvor eindeutiges Rätsel mehrdeutig",
   r_voll["eindeutig"] and not r_entfernt["eindeutig"], str(r_entfernt))

widerspruch_ganz_links = pos_hinweis("ganz_links", "p0")  # p1 UND p0 können nicht beide ganz links stehen
r = K.pruefe_positionen(3, [p1_links, widerspruch_ganz_links], LOESUNG_P3)
ok("zwei sich widersprechende 'ganz_links'-Hinweise machen das Rätsel unlösbar",
   r["loesungen_gezaehlt"] == 0, str(r))

nicht_p1_links = pos_hinweis("nicht_rand", "p1")  # widerspricht p1_links direkt (p1 kann nicht zugleich Rand und nicht Rand sein)
r = K.pruefe_positionen(3, [p1_links, nicht_p1_links], LOESUNG_P3)
ok("'ganz_links' und 'nicht_rand' für dasselbe Subjekt widersprechen sich und machen es unlösbar",
   r["loesungen_gezaehlt"] == 0, str(r))

LOESUNG_P3_FALSCH = ["p2", "p0", "p1"]
r = K.pruefe_positionen(3, [p1_links, p2_rechts], LOESUNG_P3_FALSCH)
ok("eindeutige, korrekte Hinweise widersprechen einer falsch angegebenen Lösung",
   r["eindeutig"] and not r["stimmt"], str(r))

referenz_kaputt = pos_hinweis("ganz_links", "p9")  # p9 existiert bei n=3 nicht
r = K.pruefe_positionen(3, [p2_rechts, referenz_kaputt], LOESUNG_P3)
ok("ein Hinweis mit unbekannter Subjekt-Kennung macht es unlösbar statt abzustürzen",
   r["loesungen_gezaehlt"] == 0, str(r))

typ_unbekannt = {"typ": "vielleicht", "a": "p0"}
r = K.pruefe_positionen(3, [p1_links, p2_rechts, typ_unbekannt], LOESUNG_P3)
ok("ein Positions-Hinweis mit unbekanntem Typ gilt sicherheitshalber als nie erfüllt und macht es unlösbar",
   r["loesungen_gezaehlt"] == 0, str(r))

r = K.pruefe_positionen(0, [], [])
ok("pruefe_positionen mit n=0 stürzt nicht ab, sondern liefert ein sauberes Nicht-Ergebnis",
   r == {"eindeutig": False, "stimmt": False, "loesungen_gezaehlt": 0}, str(r))

# zwischen(a,b,c): beide Richtungen zählen (pos[a] muss nur zwischen pos[b]
# und pos[c] liegen, unabhängig davon, welches der beiden vorne steht).
LOESUNG_P4 = ["p0", "p1", "p2", "p3"]
zwischen_wahr = pos_hinweis("zwischen", "p1", "p3", "p0")  # p1 liegt zwischen p0 (0) und p3 (3) ✓
r = K.pruefe_positionen(4, [zwischen_wahr], LOESUNG_P4)
ok("'zwischen' ist unabhängig von der Reihenfolge der beiden Randargumente wahr",
   r["loesungen_gezaehlt"] > 0, str(r))

zwischen_falsch = pos_hinweis("zwischen", "p0", "p1", "p2")  # p0 (0) liegt nicht zwischen p1 (1) und p2 (2)
r = K.pruefe_positionen(4, [zwischen_falsch], LOESUNG_P4)
ok("ein falscher 'zwischen'-Hinweis lässt die tatsächliche Lösung durchfallen",
   not r["stimmt"], str(r))

try:
    K.erzeuge_positionen(6, seed=1)
    ok("erzeuge_positionen lehnt n=6 mit ValueError ab", False)
except ValueError:
    ok("erzeuge_positionen lehnt n=6 mit ValueError ab", True)

try:
    K.erzeuge_positionen(2, seed=1)
    ok("erzeuge_positionen lehnt n=2 mit ValueError ab", False)
except ValueError:
    ok("erzeuge_positionen lehnt n=2 mit ValueError ab", True)


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
