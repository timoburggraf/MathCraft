# -*- coding: utf-8 -*-
"""Der deterministische Rätselkern für die Denkschule (ZIELE-V2.md, Abschnitt D4).

Ein Sprachmodell verrechnet sich nicht nur bei Termen — bei Logikrätseln ist es
noch unzuverlässiger: unlösbare, mehrdeutige oder in sich widersprüchliche
Rätsel sind bei Sprachmodellen die Regel, nicht die Ausnahme. Deshalb wird das
Erzeugungsprinzip hier umgedreht: Der deterministische Kern kommt zuerst und
legt Lösung, Hinweise und Ablenker fest. Ein Sprachmodell darf später nur noch
die Geschichte drumherum erzählen (die Platzhalter wie "k0e0" durch "der
Busfahrer" ersetzen) — an der Wahrheit selbst rührt es nicht.

Dieses Modul deckt drei der vier in D4 genannten Rätselarten ab:

  1. Logikgitter   – erzeuge_logikgitter() / pruefe_logikgitter()
     Zuordnungsrätsel vom Typ "Der Täter trägt eine Sonnenbrille". Die Lösung
     wird ausgewürfelt, wahre Hinweise werden daraus abgeleitet und so lange
     ausgedünnt, wie das Rätsel eindeutig lösbar bleibt. Geprüft wird durch
     vollständige Enumeration aller Zuordnungen — bei den zugelassenen Größen
     (höchstens 3 Kategorien × 4 Elemente, also höchstens (4!)² = 576 Fälle)
     ist das in Millisekunden erledigt.

  2. Zahlenfolgen  – erzeuge_folge() / pruefe_folge()
     Die Regel steht als Formel fest, bevor die Glieder berechnet werden —
     nicht umgekehrt. Derselbe Regel-Ausdruck erzeugt beim Erzeugen und beim
     Prüfen exakt dieselben Zahlen, ein Sprachmodell ist an keiner Stelle
     beteiligt.

  3. Positionsrätsel – erzeuge_positionen() / pruefe_positionen()
     Subjekte stehen in einer Reihe; Hinweise sprechen ausschließlich über
     ihre Position zueinander ("steht direkt links neben", "steht zwischen"),
     nie über eine Zahl. Auch hier wird zuerst die Lösung gewürfelt, daraus
     werden alle wahren Hinweise abgeleitet und mit derselben Greedy-
     Ausdünnung wie beim Logikgitter reduziert. Eindeutigkeit wird durch
     Enumeration aller n! Reihenfolgen bestätigt (n ≤ 5, also höchstens 120
     Fälle) — auch hier wird nicht deduktiv geprüft, sondern ausprobiert.

Alle drei sind reiner Standardbibliotheks-Code und vollständig seedbar:
Derselbe Seed liefert byte-gleich dasselbe Rätsel. Dieses Modul hat noch
keine Anbindung an das übrige Projekt (kein Import von curriculum.py,
validate.py oder Ähnlichem) — das ist bewusst ein späterer Schritt.
"""
import itertools
import math
import random


# ============================================================== Logikgitter

def _kategorie_nummer(bezeichner):
    """Liest aus 'k1' die Zahl 1. Liefert -1 für alles, was keine gültige
    Kategoriebezeichnung ist – ein kaputter Hinweis soll das Programm nicht
    zum Absturz bringen, sondern als das erkannt werden, was er ist: falsch.
    """
    if isinstance(bezeichner, str) and bezeichner.startswith("k") and bezeichner[1:].isdigit():
        return int(bezeichner[1:])
    return -1


def _hinweistext(typ, a, b):
    """Ein deterministischer deutscher Fallback-Satz, falls (noch) kein
    Sprachmodell eine Geschichte um den Hinweis gebaut hat. Er benutzt bewusst
    dieselben Platzhalter-Kennungen wie 'kategorien' – die Einkleidung ersetzt
    sie später 1:1 durch "der Busfahrer", "die Sonnenbrille" und so weiter.
    """
    bez_a = f"{a[0]}e{a[1]}"
    bez_b = f"{b[0]}e{b[1]}"
    if typ == "ist":
        return f"{bez_a} gehört zu {bez_b}."
    return f"{bez_a} gehört nicht zu {bez_b}."


def _hinweis(typ, kategorie_a, index_a, kategorie_b, index_b):
    """Baut einen strukturierten Hinweis samt Fallback-Satz zusammen."""
    a = [f"k{kategorie_a}", index_a]
    b = [f"k{kategorie_b}", index_b]
    return {"typ": typ, "a": a, "b": b, "text": _hinweistext(typ, a, b)}


def _hinweis_erfuellt(hinweis, subjekt_von):
    """Prüft einen einzelnen Hinweis gegen eine konkrete Zuordnung.

    subjekt_von(kategorie, index) beantwortet: "Zu welchem Subjekt (= Element
    aus Kategorie 0) gehört dieses Element in dieser konkreten Zuordnung?".
    Ein unbekannter Hinweistyp gilt sicherheitshalber als nicht erfüllt –
    dieselbe Vorsicht wie im übrigen Projekt: im Zweifel nichts durchwinken.
    """
    kat_a, idx_a = hinweis["a"]
    kat_b, idx_b = hinweis["b"]
    gleiches_subjekt = subjekt_von(kat_a, idx_a) == subjekt_von(kat_b, idx_b)
    typ = hinweis.get("typ")
    if typ == "ist":
        return gleiches_subjekt
    if typ == "nicht":
        return not gleiches_subjekt
    return False


def pruefe_logikgitter(kategorien, hinweise, loesung):
    """Prüft ein Logikgitter durch vollständige Enumeration aller Zuordnungen.

    Es wird nicht deduziert, sondern stumpf ausprobiert: Für jede weitere
    Kategorie (alles außer Kategorie 0, den Subjekten) wird jede mögliche
    Permutation durchgespielt und gegen alle Hinweise gehalten. Bei den
    zugelassenen Größen (höchstens 3 Kategorien × 4 Elemente) sind das
    höchstens (4!)² = 576 Fälle – zu wenig, um eine Heuristik zu rechtfertigen,
    die sich selbst wieder irren könnte.

    Rückgabe (dict):
      eindeutig          – genau eine Zuordnung erfüllt alle Hinweise
      stimmt              – diese eine Zuordnung ist die angegebene Lösung
      loesungen_gezaehlt – wie viele Zuordnungen tatsächlich passen
    """
    n_elemente = len(kategorien[0]) if kategorien else 0
    weitere_kategorien = list(range(1, len(kategorien)))

    gezaehlt = 0
    gefundene_zuordnung = None
    for kombination in itertools.product(itertools.permutations(range(n_elemente)),
                                          repeat=len(weitere_kategorien)):
        zuordnung = {f"k{kat}": list(perm) for kat, perm in zip(weitere_kategorien, kombination)}

        # Für jede Kategorie das Gegenstück zu 'zuordnung': zu welchem Subjekt
        # gehört Element idx? (Kategorie 0 sind die Subjekte selbst.)
        subjekt_tabellen = {0: list(range(n_elemente))}
        for kat, perm in zip(weitere_kategorien, kombination):
            invertiert = [-1] * n_elemente
            for subjekt, element in enumerate(perm):
                invertiert[element] = subjekt
            subjekt_tabellen[kat] = invertiert

        def subjekt_von(kategorie_schluessel, index, tabellen=subjekt_tabellen):
            tabelle = tabellen.get(_kategorie_nummer(kategorie_schluessel))
            if tabelle is None or not 0 <= index < len(tabelle):
                return None  # kaputte Referenz – passt garantiert zu keinem echten Subjekt
            return tabelle[index]

        if all(_hinweis_erfuellt(h, subjekt_von) for h in hinweise):
            gezaehlt += 1
            gefundene_zuordnung = zuordnung

    eindeutig = gezaehlt == 1
    stimmt = eindeutig and gefundene_zuordnung == loesung
    return {"eindeutig": eindeutig, "stimmt": stimmt, "loesungen_gezaehlt": gezaehlt}


def erzeuge_logikgitter(n_kategorien, n_elemente, seed):
    """Erzeugt ein Logikgitter-Rätsel mit garantiert eindeutiger, minimaler
    Hinweismenge. n_kategorien ∈ {2, 3}, n_elemente ∈ {3, 4}.

    Ablauf in drei Schritten, wie in ZIELE-V2.md/D4 gefordert:

      (a) eine zufällige Lösungsbelegung auswürfeln – jedem Subjekt (Element
          aus Kategorie 0) wird je ein Element jeder weiteren Kategorie fest
          zugeordnet (eine Permutation pro Kategorie);
      (b) daraus ALLE wahren Hinweise ableiten, für jedes Kategorienpaar und
          jedes Element, sowohl "ist"- als auch "nicht"-Hinweise;
      (c) die Hinweismenge in zufälliger Reihenfolge ausdünnen: jeder Hinweis
          fliegt raus, sofern das Rätsel danach noch immer genau eine Lösung
          hat – sonst bleibt er drin.

    Schritt (c) garantiert nebenbei die Minimalität: Ein Hinweis, der zu einem
    Zeitpunkt nicht entfernbar war, bleibt es auch für jede kleinere Teilmenge
    der bis dahin verbliebenen Hinweise – weniger Hinweise können ein Rätsel
    nie eindeutiger machen, nur mehrdeutiger oder gleich eindeutig. Damit ist
    das Endergebnis automatisch minimal, ohne das eigens nachzuprüfen.

    Ergebnis-Struktur (dict): kategorien, loesung, hinweise, groesse, seed.
    """
    if n_kategorien not in (2, 3):
        raise ValueError(f"n_kategorien muss 2 oder 3 sein, nicht {n_kategorien!r}")
    if n_elemente not in (3, 4):
        raise ValueError(f"n_elemente muss 3 oder 4 sein, nicht {n_elemente!r}")

    rng = random.Random(seed)
    kategorien = [[f"k{kat}e{el}" for el in range(n_elemente)] for kat in range(n_kategorien)]

    # (a) Lösungsbelegung: loesung["k1"][s] ist der Elementindex, den Subjekt s
    # in Kategorie k1 zugewiesen bekommt – eine Permutation je weiterer Kategorie.
    loesung = {}
    for kat in range(1, n_kategorien):
        permutation = list(range(n_elemente))
        rng.shuffle(permutation)
        loesung[f"k{kat}"] = permutation

    def element_des_subjekts(kategorie, subjekt):
        return subjekt if kategorie == 0 else loesung[f"k{kategorie}"][subjekt]

    # (b) Wahre Hinweise für jedes Kategorienpaar (auch k1×k2 – das ergibt die
    # typischen Verkettungen): der Treffer je Subjekt ("ist") sowie alle
    # Fehltreffer ("nicht").
    pool = []
    for kat_a in range(n_kategorien):
        for kat_b in range(kat_a + 1, n_kategorien):
            for subjekt in range(n_elemente):
                idx_a = element_des_subjekts(kat_a, subjekt)
                idx_b = element_des_subjekts(kat_b, subjekt)
                pool.append(_hinweis("ist", kat_a, idx_a, kat_b, idx_b))
                for anderes_subjekt in range(n_elemente):
                    if anderes_subjekt == subjekt:
                        continue
                    idx_b_falsch = element_des_subjekts(kat_b, anderes_subjekt)
                    pool.append(_hinweis("nicht", kat_a, idx_a, kat_b, idx_b_falsch))

    # (c) Greedy-Reduktion in zufälliger, aber fester Reihenfolge.
    reihenfolge = list(pool)
    rng.shuffle(reihenfolge)
    hinweise = list(pool)
    for kandidat in reihenfolge:
        probeweise = [h for h in hinweise if h is not kandidat]
        if pruefe_logikgitter(kategorien, probeweise, loesung)["eindeutig"]:
            hinweise = probeweise

    return {
        "kategorien": kategorien,
        "loesung": loesung,
        "hinweise": hinweise,
        "groesse": {"kategorien": n_kategorien, "elemente": n_elemente},
        "seed": seed,
    }


# ================================================================== Folgen

def _werte_regel_aus(regel, laenge):
    """Berechnet Glieder und Fortsetzung einer Zahlenfolge rein aus der Regel.

    Das ist der eigentliche Kern hinter erzeuge_folge() UND pruefe_folge():
    Egal wer die Regel liefert – der Generator beim Erzeugen, ein Prüfer beim
    Nachrechnen –, es kommt garantiert dieselbe Folge heraus. Kein Zufall
    fließt hier ein, nur die in der Regel gespeicherten Parameter.
    """
    typ = regel.get("typ") if isinstance(regel, dict) else None

    if typ == "plus":
        start, d = regel["start"], regel["d"]
        glieder = [start + i * d for i in range(laenge)]
        naechstes = start + laenge * d

    elif typ == "mal":
        start, q = regel["start"], regel["q"]
        glieder = [start * q ** i for i in range(laenge)]
        naechstes = start * q ** laenge

    elif typ == "wechsel":
        start, a, b = regel["start"], regel["a"], regel["b"]
        glieder = [start]
        for i in range(1, laenge):
            glieder.append(glieder[-1] + (a if (i - 1) % 2 == 0 else b))
        naechstes = glieder[-1] + (a if (laenge - 1) % 2 == 0 else b)

    elif typ == "wachsend":
        start = regel["start"]
        glieder = [start + i * (i + 1) // 2 for i in range(laenge)]
        naechstes = start + laenge * (laenge + 1) // 2

    elif typ == "fibo":
        start0, start1 = regel["start"]
        vorlauf = [start0, start1]
        while len(vorlauf) < laenge + 1:
            vorlauf.append(vorlauf[-1] + vorlauf[-2])
        glieder = vorlauf[:laenge]
        naechstes = vorlauf[laenge]

    elif typ == "quadrat":
        start_n, form = regel["start_n"], regel["form"]
        if form == "quadrat":
            glieder = [(start_n + i) ** 2 for i in range(laenge)]
            naechstes = (start_n + laenge) ** 2
        elif form == "dreieck":
            glieder = [(start_n + i) * (start_n + i + 1) // 2 for i in range(laenge)]
            naechstes = (start_n + laenge) * (start_n + laenge + 1) // 2
        else:
            raise ValueError(f"unbekannte Form {form!r} für Regeltyp 'quadrat'")

    else:
        raise ValueError(f"unbekannter Regeltyp {typ!r}")

    return glieder, naechstes


def _drei_ablenker(rng, korrekt, kandidaten, max_wert):
    """Wählt aus den (regeltypischen) Kandidaten drei aus, die von der
    Lösung und voneinander verschieden sind und in den Zahlenraum passen.
    Reichen die Kandidaten nicht, wird deterministisch mit kleinen
    Verschiebungen aufgefüllt.
    """
    gewaehlt = []
    for kandidat in kandidaten:
        if len(gewaehlt) >= 3:
            break
        if kandidat != korrekt and 0 <= kandidat <= max_wert and kandidat not in gewaehlt:
            gewaehlt.append(kandidat)

    versuch = 1
    while len(gewaehlt) < 3:
        vorschlag = korrekt + rng.choice((-1, 1)) * versuch
        versuch += 1
        if vorschlag != korrekt and 0 <= vorschlag <= max_wert and vorschlag not in gewaehlt:
            gewaehlt.append(vorschlag)

    rng.shuffle(gewaehlt)
    return gewaehlt


def _ablenker_erzeugen(regeltyp, rng, glieder, naechstes, regel, max_wert):
    """Baut drei plausible, aber nachweislich falsche Fortsetzungen.

    Weil die Regel genau eine richtige Fortsetzung festlegt, ist jeder Wert
    ungleich 'naechstes' automatisch ein Regelverstoß – pruefe_folge() lehnt
    ihn ab. Die Kandidaten sind trotzdem keine reinen Zufallszahlen, sondern
    typische Kinderfehler (off-by-one, falsche naheliegende Regel), damit das
    Rätsel fair und nicht durch offensichtlichen Unsinn lösbar bleibt.
    """
    letztes = glieder[-1]
    vorletztes = glieder[-2] if len(glieder) > 1 else letztes
    kandidaten = [naechstes - 1, naechstes + 1, letztes]

    if regeltyp == "plus":
        d = regel["d"]
        kandidaten += [letztes + d + 1, letztes + d - 1, letztes + 2 * d]
    elif regeltyp == "mal":
        q = regel["q"]
        # typischer Fehler: die Folge additiv statt multiplikativ fortsetzen
        kandidaten += [letztes + (letztes - vorletztes), letztes * (q - 1), letztes + q]
    elif regeltyp == "wechsel":
        a, b = regel["a"], regel["b"]
        falsche_schrittweite = a if (naechstes - letztes) == b else b
        kandidaten += [letztes + falsche_schrittweite]
    elif regeltyp == "wachsend":
        # typischer Fehler: den letzten Schritt wiederholen statt ihn zu erhöhen
        kandidaten += [letztes + (letztes - vorletztes)]
    elif regeltyp == "fibo":
        kandidaten += [letztes * 2, letztes + vorletztes - 1]
    elif regeltyp == "quadrat":
        kandidaten += [letztes + (letztes - vorletztes) * 2]

    return _drei_ablenker(rng, naechstes, kandidaten, max_wert)


REGELTYPEN = ("plus", "mal", "wechsel", "wachsend", "fibo", "quadrat")


def _regel_erzeugen(regeltyp, rng, laenge, max_wert):
    """Würfelt die Parameter einer Regel so aus, dass Glieder UND Fortsetzung
    garantiert innerhalb des Zahlenraum-Deckels max_wert bleiben.
    """
    if regeltyp == "plus":
        d = rng.randint(2, 9)
        obergrenze = max_wert - laenge * d
        if obergrenze < 1:
            raise ValueError("Zahlenraum zu eng für eine Plus-Folge dieser Länge")
        return {"typ": "plus", "start": rng.randint(1, obergrenze), "d": d}

    if regeltyp == "mal":
        q = rng.choice((2, 3))
        obergrenze = max_wert // (q ** laenge)
        if obergrenze < 1:
            raise ValueError("Zahlenraum zu eng für eine Mal-Folge dieser Länge")
        return {"typ": "mal", "start": rng.randint(1, obergrenze), "q": q}

    if regeltyp == "wechsel":
        a, b = rng.sample(range(2, 10), 2)
        gesamtzuwachs = sum(a if i % 2 == 0 else b for i in range(laenge))
        obergrenze = max_wert - gesamtzuwachs
        if obergrenze < 1:
            raise ValueError("Zahlenraum zu eng für eine Wechsel-Folge dieser Länge")
        return {"typ": "wechsel", "start": rng.randint(1, obergrenze), "a": a, "b": b}

    if regeltyp == "wachsend":
        gesamtzuwachs = laenge * (laenge + 1) // 2
        obergrenze = max_wert - gesamtzuwachs
        if obergrenze < 1:
            raise ValueError("Zahlenraum zu eng für eine wachsende Folge dieser Länge")
        return {"typ": "wachsend", "start": rng.randint(1, obergrenze)}

    if regeltyp == "fibo":
        start0, start1 = rng.randint(1, 5), rng.randint(1, 5)
        while True:
            _, naechstes = _werte_regel_aus({"typ": "fibo", "start": [start0, start1]}, laenge)
            if naechstes <= max_wert or (start0 == 1 and start1 == 1):
                break
            start0, start1 = max(1, start0 - 1), max(1, start1 - 1)
        if naechstes > max_wert:
            raise ValueError("Zahlenraum zu eng für eine Fibonacci-Folge dieser Länge")
        return {"typ": "fibo", "start": [start0, start1]}

    if regeltyp == "quadrat":
        form = rng.choice(("quadrat", "dreieck"))
        if form == "quadrat":
            max_n = math.isqrt(max_wert) - laenge
        else:
            # Dreieckszahl T_n = n(n+1)/2 <= max_wert  →  n <= (√(8·max_wert+1) − 1) / 2
            max_n = (math.isqrt(8 * max_wert + 1) - 1) // 2 - laenge
        if max_n < 1:
            raise ValueError("Zahlenraum zu eng für eine Quadrat-/Dreieckszahlenfolge dieser Länge")
        return {"typ": "quadrat", "start_n": rng.randint(1, max_n), "form": form}

    raise ValueError(f"unbekannter Regeltyp {regeltyp!r}")


def erzeuge_folge(regeltyp, seed, laenge=5, max_wert=1000):
    """Erzeugt eine Zahlenfolge samt Fortsetzung und drei Ablenkern.

    regeltyp ist eine von REGELTYPEN: 'plus' (+d), 'mal' (×q, q ∈ {2, 3}),
    'wechsel' (abwechselnd +a, +b), 'wachsend' (+1, +2, +3, …), 'fibo' (jedes
    Glied die Summe der zwei Vorgänger) oder 'quadrat' (Quadratzahlen bzw.
    figurierte Dreieckszahlen – welche der beiden Formen es wird, entscheidet
    der Zufall). max_wert ist der Zahlenraum-Deckel: Glieder, Fortsetzung und
    alle Ablenker bleiben garantiert darunter.

    Ergebnis-Struktur (dict): glieder, naechstes, regel, ablenker, max_wert,
    seed.
    """
    if regeltyp not in REGELTYPEN:
        raise ValueError(f"unbekannter Regeltyp {regeltyp!r}, erlaubt sind {REGELTYPEN}")

    rng = random.Random(seed)
    regel = _regel_erzeugen(regeltyp, rng, laenge, max_wert)
    glieder, naechstes = _werte_regel_aus(regel, laenge)
    ablenker = _ablenker_erzeugen(regeltyp, rng, glieder, naechstes, regel, max_wert)

    return {
        "glieder": glieder,
        "naechstes": naechstes,
        "regel": regel,
        "ablenker": ablenker,
        "max_wert": max_wert,
        "seed": seed,
    }


def pruefe_folge(glieder, naechstes, regel):
    """Rechnet die Regel unabhängig nach und bestätigt Glieder und Fortsetzung.

    Es fließt keine der beim Erzeugen benutzten Zufallszahlen hier ein – nur
    die in 'regel' gespeicherten Parameter werden erneut ausgewertet
    (_werte_regel_aus ist derselbe Code, den auch erzeuge_folge() benutzt).
    Stimmt etwas nicht überein oder ist die Regel kaputt, liefert die Funktion
    False statt abzustürzen.
    """
    if not isinstance(glieder, list) or not glieder:
        return False
    try:
        erwartete_glieder, erwartetes_naechstes = _werte_regel_aus(regel, len(glieder))
    except (KeyError, TypeError, ValueError):
        return False
    return erwartete_glieder == list(glieder) and erwartetes_naechstes == naechstes


# ============================================================ Positionsrätsel

def _pos_hinweistext(typ, a, b=None, c=None):
    """Ein deterministischer deutscher Fallback-Satz mit den Kennungen
    "p0".."p{n-1}" – genau wie bei _hinweistext() für das Logikgitter ist das
    nur der Platzhalter, den die spätere Einkleidung 1:1 durch "der
    Astronaut" & Co. ersetzt. Bewusst ohne jede Positionsnummer: das Rätsel
    ist "komplett ohne Zahlen" (ZIELE-V2.md/D1).
    """
    if typ == "ganz_links":
        return f"{a} steht ganz links."
    if typ == "ganz_rechts":
        return f"{a} steht ganz rechts."
    if typ == "mitte":
        return f"{a} steht genau in der Mitte."
    if typ == "nicht_rand":
        return f"{a} steht weder ganz links noch ganz rechts."
    if typ == "direkt_links":
        return f"{a} steht direkt links neben {b}."
    if typ == "direkt_rechts":
        return f"{a} steht direkt rechts neben {b}."
    if typ == "links_von":
        return f"{a} steht irgendwo links von {b}."
    if typ == "rechts_von":
        return f"{a} steht irgendwo rechts von {b}."
    if typ == "neben":
        return f"{a} steht direkt neben {b}."
    if typ == "nicht_neben":
        return f"{a} steht nicht direkt neben {b}."
    if typ == "zwischen":
        return f"{a} steht zwischen {b} und {c}."
    return f"(unbekannter Hinweistyp {typ!r})"


def _pos_hinweis(typ, a, b=None, c=None):
    """Baut einen strukturierten Positions-Hinweis samt Fallback-Satz. 'a',
    'b', 'c' sind Subjekt-Kennungen ("p0" …) – anders als beim Logikgitter
    braucht es hier keine [Kategorie, Index]-Paare, weil es nur eine Sorte
    Subjekt gibt (die Personen selbst, nicht ihre Merkmale).
    """
    h = {"typ": typ, "a": a}
    if b is not None:
        h["b"] = b
    if c is not None:
        h["c"] = c
    h["text"] = _pos_hinweistext(typ, a, b, c)
    return h


def _pos_hinweis_erfuellt(hinweis, positionen, n):
    """Prüft einen einzelnen Positions-Hinweis gegen eine konkrete Reihenfolge.

    'positionen' bildet Subjekt-Kennung auf Positionsindex ab (dict). Eine
    unbekannte Kennung (kaputter Index, Tippfehler, Zahl statt "pX") liefert
    None und macht den Hinweis – wie beim Logikgitter – sicherheitshalber
    nicht erfüllt, statt abzustürzen. Ein unbekannter Hinweistyp fällt am
    Ende durch dieselbe Vorsicht: im Zweifel nichts durchwinken.
    """
    typ = hinweis.get("typ") if isinstance(hinweis, dict) else None
    pa = positionen.get(hinweis.get("a")) if isinstance(hinweis, dict) else None
    if pa is None:
        return False

    if typ == "ganz_links":
        return pa == 0
    if typ == "ganz_rechts":
        return pa == n - 1
    if typ == "mitte":
        return n % 2 == 1 and pa == n // 2
    if typ == "nicht_rand":
        return 0 < pa < n - 1

    if typ in ("direkt_links", "direkt_rechts", "links_von", "rechts_von", "neben", "nicht_neben"):
        pb = positionen.get(hinweis.get("b"))
        if pb is None:
            return False
        if typ == "direkt_links":
            return pa == pb - 1
        if typ == "direkt_rechts":
            return pa == pb + 1
        if typ == "links_von":
            return pa < pb
        if typ == "rechts_von":
            return pa > pb
        if typ == "neben":
            return abs(pa - pb) == 1
        if typ == "nicht_neben":
            return abs(pa - pb) > 1

    if typ == "zwischen":
        pb = positionen.get(hinweis.get("b"))
        pc = positionen.get(hinweis.get("c"))
        if pb is None or pc is None:
            return False
        untere, obere = min(pb, pc), max(pb, pc)
        return untere < pa < obere

    return False


def pruefe_positionen(n, hinweise, loesung):
    """Prüft ein Positionsrätsel durch vollständige Enumeration aller n!
    Reihenfolgen – wie pruefe_logikgitter() wird nicht dedaktiv hergeleitet,
    sondern stumpf ausprobiert. Bei n ≤ 5 sind das höchstens 120 Fälle.

    Rückgabe (dict):
      eindeutig          – genau eine Reihenfolge erfüllt alle Hinweise
      stimmt              – diese eine Reihenfolge ist die angegebene Lösung
      loesungen_gezaehlt – wie viele Reihenfolgen tatsächlich passen
    """
    if not isinstance(n, int) or n < 1:
        return {"eindeutig": False, "stimmt": False, "loesungen_gezaehlt": 0}

    subjekte = [f"p{i}" for i in range(n)]
    gezaehlt = 0
    gefundene_reihenfolge = None
    for permutation in itertools.permutations(subjekte):
        positionen = {subjekt: index for index, subjekt in enumerate(permutation)}
        if all(_pos_hinweis_erfuellt(h, positionen, n) for h in hinweise):
            gezaehlt += 1
            gefundene_reihenfolge = list(permutation)

    eindeutig = gezaehlt == 1
    stimmt = False
    if eindeutig:
        # list(loesung) statt direktem Vergleich: eine kaputte Lösung (z. B.
        # None oder eine Zahl statt einer Liste) soll False liefern, nicht
        # das Programm zum Absturz bringen.
        try:
            stimmt = gefundene_reihenfolge == list(loesung)
        except TypeError:
            stimmt = False
    return {"eindeutig": eindeutig, "stimmt": stimmt, "loesungen_gezaehlt": gezaehlt}


# Hinweistypen, die eine Position (fast) wörtlich verraten – Grundlage für
# die Schwierigkeits-Filterung UND für die "Frage verrät die Antwort nicht"-
# Garantie weiter unten.
_POS_RAND_LOCKER = ("ganz_links", "ganz_rechts", "mitte")
_POS_RAND_STRENG = _POS_RAND_LOCKER + ("direkt_links", "direkt_rechts")


def _pos_pool_wahrer_hinweise(subjekte, positionen, n):
    """Leitet aus einer konkreten Reihenfolge ALLE wahren Hinweise ab – jede
    Instanz jedes Typs, auch wenn zwei Instanzen dieselbe Tatsache aus
    verschiedenen Typen heraus beschreiben (z. B. direkt_links(a,b) und
    direkt_rechts(b,a) sind dieselbe Nachbarschaft, nur anders erzählt).
    Genau wie in erzeuge_logikgitter() ist das gewollt: Schritt (c) dünnt
    diesen Überschuss aus, bis nur noch das Nötige übrig bleibt.
    """
    pool = []
    for a in subjekte:
        pa = positionen[a]
        if pa == 0:
            pool.append(_pos_hinweis("ganz_links", a))
        if pa == n - 1:
            pool.append(_pos_hinweis("ganz_rechts", a))
        if n % 2 == 1 and pa == n // 2:
            pool.append(_pos_hinweis("mitte", a))
        if 0 < pa < n - 1:
            pool.append(_pos_hinweis("nicht_rand", a))

    for a, b in itertools.permutations(subjekte, 2):
        pa, pb = positionen[a], positionen[b]
        if pa == pb - 1:
            pool.append(_pos_hinweis("direkt_links", a, b))
        if pa == pb + 1:
            pool.append(_pos_hinweis("direkt_rechts", a, b))
        if pa < pb:
            pool.append(_pos_hinweis("links_von", a, b))
        if pa > pb:
            pool.append(_pos_hinweis("rechts_von", a, b))
        if abs(pa - pb) == 1:
            pool.append(_pos_hinweis("neben", a, b))
        if abs(pa - pb) > 1:
            pool.append(_pos_hinweis("nicht_neben", a, b))

    for a in subjekte:
        andere = [s for s in subjekte if s != a]
        for b, c in itertools.combinations(andere, 2):
            pa, pb, pc = positionen[a], positionen[b], positionen[c]
            untere, obere = min(pb, pc), max(pb, pc)
            if untere < pa < obere:
                pool.append(_pos_hinweis("zwischen", a, b, c))

    return pool


def _pos_pool_nach_schwierigkeit(pool, schwierigkeit, n, loesung, rng):
    """Filtert den vollen Hinweis-Pool NACH Denktiefe – das ist die eine
    Hälfte der Grunddefinition "Schwierigkeit ist Denktiefe, nie
    Zahlengröße" (ZIELE-V2.md/D2): mehr Schwierigkeit heißt nicht mehr oder
    größere Zahlen, sondern indirektere Hinweise.

      Schwierigkeit ≤ 1: alle Typen erlaubt, keine Einschränkung.
      Schwierigkeit 2–3: von "ganz_links"/"ganz_rechts"/"mitte" darf
        höchstens EINER im Pool landen – die anderen sind zu direkt.
      Schwierigkeit ≥ 4: "ganz_links"/"ganz_rechts"/"mitte"/"direkt_links"/
        "direkt_rechts" fliegen komplett raus. Ausnahme (Sicherheitsnetz):
        Reicht die verbleibende, "indirekte" Menge (links_von/rechts_von
        decken für jedes Paar ohnehin eine Richtung ab und legen dadurch
        schon die komplette Reihenfolge fest – das Sicherheitsnetz greift
        also nur in seltenen Rand­fällen) ausnahmsweise nicht für
        Eindeutigkeit, werden so wenige der strengen Typen wie nötig aus dem
        vollen Pool nachgelegt, einer nach dem anderen in zufälliger,
        seedfester Reihenfolge, bis es reicht.
    """
    if schwierigkeit <= 1:
        return list(pool)

    if schwierigkeit <= 3:
        rand = [h for h in pool if h["typ"] in _POS_RAND_LOCKER]
        rest = [h for h in pool if h["typ"] not in _POS_RAND_LOCKER]
        if rand:
            rand = [rng.choice(rand)]
        return rest + rand

    pool_erlaubt = [h for h in pool if h["typ"] not in _POS_RAND_STRENG]
    if not pruefe_positionen(n, pool_erlaubt, loesung)["eindeutig"]:
        rand_kandidaten = [h for h in pool if h["typ"] in _POS_RAND_STRENG]
        rng.shuffle(rand_kandidaten)
        for kandidat in rand_kandidaten:
            pool_erlaubt.append(kandidat)
            if pruefe_positionen(n, pool_erlaubt, loesung)["eindeutig"]:
                break
    return pool_erlaubt


def _pos_frage_kandidaten(n, loesung, hinweise):
    """Listet alle Frage-Kandidaten auf, die von KEINEM verbliebenen Hinweis
    wörtlich verraten werden.

    "position p" scheidet aus, wenn ein "ganz_links"-Hinweis existiert und
    p == 0 ist (analog "ganz_rechts" bei p == n-1, "mitte" bei p == n//2).
    "neben a, Seite" scheidet aus, wenn ein "direkt_links"- oder
    "direkt_rechts"-Hinweis GENAU dieses Nachbarpaar nennt – unabhängig
    davon, in welcher der beiden Typ-Richtungen er das tut (direkt_links(a,b)
    und direkt_rechts(b,a) beschreiben dieselbe Nachbarschaft).

    Mindestens ein "position"-Kandidat bleibt immer übrig: "ganz_links",
    "ganz_rechts" und "mitte" betreffen ausschließlich die Positionen 0,
    n-1 bzw. n//2 – bei n ≥ 4 bleiben also mindestens n-2 Positionen
    unberührt, und bei n = 3 kann "mitte" nachweislich nie zusätzlich zu
    BEIDEN Rand-Hinweisen im minimalen Hinweissatz überleben (sind
    "ganz_links" und "ganz_rechts" beide vorhanden, legen sie die Reihenfolge
    bereits vollständig fest, wodurch "mitte" beim Ausdünnen immer entfernbar
    wird) – es bleibt also immer mindestens eine der drei Positionen frei.
    """
    kandidaten = []
    verraet_links = any(h.get("typ") == "ganz_links" for h in hinweise)
    verraet_rechts = any(h.get("typ") == "ganz_rechts" for h in hinweise)
    verraet_mitte = any(h.get("typ") == "mitte" for h in hinweise)
    for p in range(n):
        if p == 0 and verraet_links:
            continue
        if p == n - 1 and verraet_rechts:
            continue
        if n % 2 == 1 and p == n // 2 and verraet_mitte:
            continue
        kandidaten.append({"art": "position", "p": p})

    positionen = {subjekt: index for index, subjekt in enumerate(loesung)}
    verratene_paare = set()
    for h in hinweise:
        if h.get("typ") in ("direkt_links", "direkt_rechts"):
            verratene_paare.add(frozenset({h.get("a"), h.get("b")}))

    for a in loesung:
        pa = positionen[a]
        if pa < n - 1:
            nachbar = loesung[pa + 1]
            if frozenset({a, nachbar}) not in verratene_paare:
                kandidaten.append({"art": "neben", "a": a, "seite": "rechts"})
        if pa > 0:
            nachbar = loesung[pa - 1]
            if frozenset({a, nachbar}) not in verratene_paare:
                kandidaten.append({"art": "neben", "a": a, "seite": "links"})

    return kandidaten


def erzeuge_positionen(n, seed, schwierigkeit=3):
    """Erzeugt ein Positionsrätsel mit garantiert eindeutiger, minimaler
    Hinweismenge und einer Frage, die kein einzelner Hinweis wörtlich
    verrät. n ∈ {3, 4, 5} Subjekte ("p0" … "p{n-1}") stehen in einer Reihe,
    Position 0 = ganz links.

    Ablauf wie erzeuge_logikgitter(), auf eine Reihe statt ein Gitter
    übertragen:

      (a) eine zufällige Reihenfolge auswürfeln – die spätere Lösung;
      (b) daraus ALLE wahren Hinweise ableiten (_pos_pool_wahrer_hinweise);
      (c) den Pool nach Denktiefe filtern (_pos_pool_nach_schwierigkeit) –
          das steuert, WELCHE Hinweisarten überhaupt zur Wahl stehen;
      (d) den gefilterten Pool in zufälliger, seedfester Reihenfolge greedy
          ausdünnen: jeder Hinweis fliegt raus, sofern das Rätsel danach
          noch immer genau eine Lösung hat (Eindeutigkeit per Enumeration
          aller n! Reihenfolgen, pruefe_positionen()) – das garantiert
          nebenbei Minimalität, aus demselben Grund wie beim Logikgitter:
          weniger Hinweise können ein Rätsel nie eindeutiger machen;
      (e) eine Frage auswählen, die von keinem verbliebenen Hinweis
          verraten wird (_pos_frage_kandidaten()).

    Ergebnis-Struktur (dict): n, loesung, hinweise, frage, seed.
    """
    if n not in (3, 4, 5):
        raise ValueError(f"n muss 3, 4 oder 5 sein, nicht {n!r}")

    rng = random.Random(seed)
    subjekte = [f"p{i}" for i in range(n)]

    # (a) Lösung: eine zufällige Reihenfolge der Subjekte.
    loesung = list(subjekte)
    rng.shuffle(loesung)
    positionen = {subjekt: index for index, subjekt in enumerate(loesung)}

    # (b) + (c) Pool aller wahren Hinweise, gefiltert nach Denktiefe.
    pool = _pos_pool_wahrer_hinweise(subjekte, positionen, n)
    pool_erlaubt = _pos_pool_nach_schwierigkeit(pool, schwierigkeit, n, loesung, rng)

    # (d) Greedy-Ausdünnung – identisches Prinzip wie in erzeuge_logikgitter().
    reihenfolge = list(pool_erlaubt)
    rng.shuffle(reihenfolge)
    hinweise = list(pool_erlaubt)
    for kandidat in reihenfolge:
        probeweise = [h for h in hinweise if h is not kandidat]
        if pruefe_positionen(n, probeweise, loesung)["eindeutig"]:
            hinweise = probeweise

    # (e) Frage deterministisch wählen, ohne dass ein verbliebener Hinweis
    # sie verrät (siehe Beweisskizze in _pos_frage_kandidaten()).
    kandidaten = _pos_frage_kandidaten(n, loesung, hinweise)
    if not kandidaten:
        # Nach der Herleitung in _pos_frage_kandidaten() kann das nicht
        # passieren – lieber laut scheitern als still eine verratene Frage
        # ausliefern ("Kein Fehler erreicht das Kind").
        raise RuntimeError(
            "keine unverratene Frage gefunden – widerspricht der Konstruktionsgarantie"
        )
    frage = rng.choice(kandidaten)

    return {
        "n": n,
        "loesung": loesung,
        "hinweise": hinweise,
        "frage": frage,
        "seed": seed,
    }
