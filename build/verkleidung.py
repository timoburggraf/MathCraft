# -*- coding: utf-8 -*-
"""Die Verkleidungsschicht der Denkschule (ZIELE-V2.md, Abschnitt D4).

"Der deterministische Kern kommt zuerst, das Sprachmodell liefert nur die
Verkleidung." Dieses Modul setzt genau das um: Es nimmt einen fertigen Kern
aus raetsel_kern.py (Lösung, Hinweise, Zuordnungen — alles schon feststehend)
und lässt ein Sprachmodell ausschließlich Namen und Sätze drumherum bauen.
Kein Feld, das aus dem Sprachmodell kommt, ist je wahrheitstragend: Lösung,
Hinweistypen, die gefragte Stelle und die Antwortmöglichkeiten werden hier,
deterministisch über einen Seed, aus dem Kern gewählt — nie aus der Antwort
des Sprachmodells gelesen.

Das Sprachmodell selbst wird nicht fest verdrahtet: 'llm' ist ein beliebiges
Callable prompt -> Text. So bleibt dieses Modul offline testbar (siehe
validate_v2_test.py) und die Anbindung an einen echten Client (im Stil von
generate_units.py: Prompt bauen, Antwort holen, prüfen, bei Mängeln neu
anfordern) ist bewusst Sache eines späteren, aufrufenden Schritts — hier wird
nur EIN Versuch gemacht, das Retry fährt der Aufrufer.

  from raetsel_kern import erzeuge_logikgitter, erzeuge_folge
  from verkleidung import verkleide_logikgitter, verkleide_folge
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import raetsel_kern as K
import validate_v2 as V2

# Der Fixtext, mit dem jede Folgen-Frage endet — das Sprachmodell liefert nur
# die Einleitung, die eigentliche Frage ist bei jeder Folge dieselbe und
# braucht keine Einkleidung.
_FRAGE_FOLGE = "Welche Zahl kommt als Nächstes?"


# --------------------------------------------------------------- Hilfsdinge

def _themenwelt_text(themenwelt):
    """Liest Titel und Hook aus einer Themenwelt — akzeptiert sowohl ein
    Wörterbuch im Stil von curriculum.world() (title/hook) als auch einen
    einfachen String, falls der Aufrufer keine volle Themenwelt zur Hand hat.
    """
    if isinstance(themenwelt, dict):
        return themenwelt.get("title", "?"), themenwelt.get("hook", "")
    return str(themenwelt), ""


def _kat_nr(kennung):
    """Liest aus 'k1' die Zahl 1 (dasselbe Format wie raetsel_kern.py)."""
    return int(kennung[1:])


def _json_lesen(text, maengel):
    """Parst die Antwort des Sprachmodells als JSON, tolerant gegenüber
    Markdown-Codezäunen ('```json ... ```'), die manche Modelle trotz
    ausdrücklicher Anweisung noch drumherum bauen."""
    if not isinstance(text, str) or not text.strip():
        maengel.append("Antwort des Sprachmodells ist leer")
        return None
    bereinigt = text.strip()
    if bereinigt.startswith("```"):
        bereinigt = bereinigt.strip("`")
        if bereinigt.lower().startswith("json"):
            bereinigt = bereinigt[4:]
    try:
        return json.loads(bereinigt)
    except json.JSONDecodeError as e:
        maengel.append(f"Antwort ist kein gültiges JSON: {e}")
        return None


def _hoechstens_ein_satz(text):
    """Grobe Prüfung, ob ein Text aus höchstens einem Satz besteht: entfernt
    man einen einzigen abschließenden Satzzeichen-Lauf, darf kein weiteres
    '.', '!' oder '?' mehr übrig sein."""
    rest = text.strip().rstrip(".!?")
    return not any(z in rest for z in ".!?")


def _enthaelt_verneinung(satz):
    s = satz.lower()
    return "nicht" in s or "kein" in s


def _pruefe_namen_bijektion(kennungen, namen, maengel):
    """Jede Platzhalter-Kennung genau einen Namen, alle Namen einzigartig,
    keine unbekannte Kennung in der Antwort."""
    if not isinstance(namen, dict):
        maengel.append(f"Feld 'namen' fehlt oder ist kein Objekt: {namen!r}")
        return
    fehlend = [k for k in kennungen if k not in namen]
    if fehlend:
        maengel.append(f"für diese Kennungen fehlt ein Name: {fehlend}")
    ueberzaehlig = [k for k in namen if k not in kennungen]
    if ueberzaehlig:
        maengel.append(f"unbekannte Kennungen in der Antwort: {ueberzaehlig}")
    if fehlend or ueberzaehlig:
        return
    werte = [str(namen[k]).strip() for k in kennungen]
    if any(not w for w in werte):
        maengel.append("leerer Name für mindestens eine Kennung")
    elif len(set(werte)) != len(werte):
        maengel.append(f"Namen sind nicht eindeutig: {werte}")


def _pruefe_keine_kennung_uebrig(kennungen, texte, maengel):
    """Keine interne Platzhalter-Kennung (k0e0, ...) darf in einem der Texte
    stehen bleiben — die Einkleidung muss sie restlos ersetzt haben."""
    uebrig = sorted({k for k in kennungen for t in texte
                      if isinstance(t, str) and k in t})
    if uebrig:
        maengel.append(f"Platzhalter-Kennung(en) stehen noch unverkleidet im Text: {uebrig}")


# ============================================================ Logikgitter

def _logikgitter_prompt(kern, themenwelt, subjekt_kennung, ziel_kat):
    titel, hook = _themenwelt_text(themenwelt)
    kategorien = kern["kategorien"]
    kennungen_je_kategorie = "\n".join(
        f"  Kategorie {i}: {', '.join(kat)}" for i, kat in enumerate(kategorien))
    hinweise_beschreibung = "\n".join(
        f"  Hinweis {i + 1}: {h['a'][0]}e{h['a'][1]} "
        f"{'gehört' if h['typ'] == 'ist' else 'gehört NICHT'} zu {h['b'][0]}e{h['b'][1]}"
        for i, h in enumerate(kern["hinweise"]))

    return f"""Du kleidest ein fertiges Logikrätsel für ein Kind ein. Lösung, Hinweise und
Zuordnungen stehen bereits unumstößlich fest — du erfindest nur Namen und
Sätze drumherum, an der Wahrheit selbst änderst du nichts.

THEMENWELT   {titel} — {hook}

Kategorie 0 sind die Figuren (Personen oder Wesen). Jede weitere Kategorie
sind Dinge, die zu ihnen gehören (z. B. Tiere, Gegenstände, Farben, Orte).

PLATZHALTER, DIE JE EINEN NAMEN BRAUCHEN (kindgerecht, kurz, passend zur
Themenwelt; jede Kennung genau einen Namen, kein Name doppelt):
{kennungen_je_kategorie}

STRUKTURELLE HINWEISE — schreibe je einen deutschen Satz, der GENAU das sagt,
nicht mehr und nicht weniger, und der beide Namen wörtlich enthält. Bei einer
Verneinung ("gehört NICHT zu") muss dein Satz das Wort "nicht" oder "kein"
enthalten:
{hinweise_beschreibung}

GEFRAGTES_SUBJEKT   {subjekt_kennung}
GEFRAGTE_KATEGORIE  {ziel_kat}
FRAGE        Formuliere einen Frage-Satz, der danach fragt, welches Element
             aus Kategorie {ziel_kat} zu GEFRAGTES_SUBJEKT gehört. Nenne darin
             den Namen von GEFRAGTES_SUBJEKT wörtlich.

Schreibe außerdem eine Rahmengeschichte — höchstens EIN Satz —, die die
Themenwelt aufruft, ohne die Aufgabe vorwegzunehmen.

ANTWORT NUR ALS JSON, GENAU IN DIESER FORM (Beispiel mit erfundenen Werten):
{{
  "namen": {{"k0e0": "Anna", "k0e1": "Ben", "k1e0": "Hund", "k1e1": "Katze"}},
  "rahmen": "In der Blockwelt haben zwei Freunde je ein Lieblingstier.",
  "hinweis_saetze": ["Ben gehört der Hund.", "Anna mag keine Katze."],
  "frage_satz": "Welches Tier hat Anna?"
}}

Die Liste "hinweis_saetze" braucht genau {len(kern['hinweise'])} Einträge, in
genau der oben angegebenen Reihenfolge. Keine der Kennungen (k0e0, k1e2, ...)
darf in deiner Antwort als Text auftauchen — ersetze sie überall durch die
echten Namen."""


def verkleide_logikgitter(kern, themenwelt, llm, seed=0):
    """Kleidet einen Logikgitter-Kern (raetsel_kern.erzeuge_logikgitter) mit
    Namen und Sätzen aus 'llm' ein. Rückgabe: (aufgabe, maengel).

    aufgabe ist None, sobald maengel nicht leer ist — bei Mängeln fährt der
    Aufrufer den Retry (im Stil von generate_units.py: Mängel in den nächsten
    Prompt zurückspielen). Lösung, Hinweistypen, die gefragte Stelle und die
    Antwortmöglichkeiten kommen ausschließlich aus dem Kern bzw. aus dem
    übergebenen Seed — niemals aus der Antwort des Sprachmodells.
    """
    maengel = []
    kategorien_kern = kern["kategorien"]
    kennungen = [el for kat in kategorien_kern for el in kat]
    n_kategorien, n_elemente = len(kategorien_kern), len(kategorien_kern[0])

    # (1) Die gefragte Stelle steht schon fest, BEVOR das Sprachmodell überhaupt
    # gefragt wird — nur so kann der Frage-Satz das richtige Subjekt nennen.
    # Ausgeschlossen sind Stellen, deren Antwort ein 'ist'-Hinweis wörtlich
    # verrät: Wer die Frage durch Ablesen beantworten kann, denkt nicht.
    rng = random.Random(seed)
    direkt = set()
    for h in kern["hinweise"]:
        if h["typ"] != "ist":
            continue
        for eine, andere in ((h["a"], h["b"]), (h["b"], h["a"])):
            if eine[0] == "k0" and andere[0] != "k0":
                z = int(andere[0][1:])
                if kern["loesung"][f"k{z}"][eine[1]] == andere[1]:
                    direkt.add((eine[1], z))
    paare = [(s, z) for s in range(n_elemente) for z in range(1, n_kategorien)
             if (s, z) not in direkt]
    if not paare:   # zur Sicherheit — bei minimalen Hinweismengen praktisch nie
        paare = [(s, z) for s in range(n_elemente) for z in range(1, n_kategorien)]
    subjekt_idx, ziel_kat = rng.choice(paare)
    subjekt_kennung = f"k0e{subjekt_idx}"

    text = llm(_logikgitter_prompt(kern, themenwelt, subjekt_kennung, ziel_kat))
    antwort = _json_lesen(text, maengel)
    if antwort is None:
        return None, maengel

    namen = antwort.get("namen")
    _pruefe_namen_bijektion(kennungen, namen, maengel)
    if maengel:
        return None, maengel

    hinweis_saetze = antwort.get("hinweis_saetze")
    rahmen = antwort.get("rahmen")
    frage_satz = antwort.get("frage_satz")

    _pruefe_keine_kennung_uebrig(
        kennungen,
        [rahmen, frage_satz] + (hinweis_saetze if isinstance(hinweis_saetze, list) else []),
        maengel,
    )

    if not isinstance(hinweis_saetze, list) or len(hinweis_saetze) != len(kern["hinweise"]):
        maengel.append(f"erwartet {len(kern['hinweise'])} Hinweissätze in einer Liste, "
                        f"bekommen: {hinweis_saetze!r}")
        return None, maengel

    hinweise_out = []
    for h, satz in zip(kern["hinweise"], hinweis_saetze):
        kat_a, idx_a = _kat_nr(h["a"][0]), h["a"][1]
        kat_b, idx_b = _kat_nr(h["b"][0]), h["b"][1]
        name_a, name_b = namen[h["a"][0] + "e" + str(idx_a)], namen[h["b"][0] + "e" + str(idx_b)]
        if not isinstance(satz, str) or not satz.strip():
            maengel.append(f"Hinweissatz für {name_a}/{name_b} fehlt oder ist leer")
        else:
            if name_a not in satz or name_b not in satz:
                maengel.append(f"Hinweissatz {satz!r} enthält nicht beide Namen "
                                f"({name_a!r}, {name_b!r})")
            if h["typ"] == "nicht" and not _enthaelt_verneinung(satz):
                maengel.append(f"Hinweissatz {satz!r} verneint nicht sichtbar "
                                "(weder 'nicht' noch 'kein')")
        hinweise_out.append({"typ": h["typ"], "a": [kat_a, idx_a], "b": [kat_b, idx_b], "text": satz})

    if not isinstance(rahmen, str) or not rahmen.strip():
        maengel.append("Rahmengeschichte fehlt oder ist leer")
    elif not _hoechstens_ein_satz(rahmen):
        maengel.append(f"Rahmengeschichte ist länger als ein Satz: {rahmen!r}")

    subjekt_name = namen[subjekt_kennung]
    if not isinstance(frage_satz, str) or not frage_satz.strip():
        maengel.append("Frage-Satz fehlt oder ist leer")
    elif subjekt_name not in frage_satz:
        maengel.append(f"Frage-Satz {frage_satz!r} nennt nicht den Namen des "
                        f"gefragten Subjekts ({subjekt_name!r})")

    if maengel:
        return None, maengel

    # (2) Die Antwortmöglichkeiten: Lösung plus alle übrigen Elemente der
    # Zielkategorie, deterministisch mit demselben Seed durchmischt.
    korrekt_idx = kern["loesung"][f"k{ziel_kat}"][subjekt_idx]
    zielnamen = [namen[f"k{ziel_kat}e{j}"] for j in range(n_elemente)]
    reihenfolge = list(range(n_elemente))
    rng.shuffle(reihenfolge)
    optionen = [zielnamen[j] for j in reihenfolge]
    richtig = reihenfolge.index(korrekt_idx)

    aufgabe = {
        "kategorien": [[namen[el] for el in kat] for kat in kategorien_kern],
        "hinweise": hinweise_out,
        "frage": {"a": [0, subjekt_idx], "ziel": ziel_kat},
        "frage_text": frage_satz,
        "loesung": kern["loesung"],
        "optionen": optionen,
        "richtig": richtig,
        "rahmen": rahmen,
    }

    # Letzte Instanz: derselbe Prüfer, der auch später jede Aufgabe abnimmt.
    # Eine doppelte, potenziell abweichende Prüflogik wäre selbst ein Risiko.
    ok, aufgabe_maengel = V2.pruefe_logikgitter_aufgabe(aufgabe)
    if not ok:
        return None, aufgabe_maengel
    return aufgabe, []


# ================================================================== Folgen

def _folge_prompt(kern, themenwelt):
    titel, hook = _themenwelt_text(themenwelt)
    glieder_text = ", ".join(str(g) for g in kern["glieder"])
    return f"""Du schreibst nur die Rahmengeschichte zu einer fertigen Zahlenfolge. An den
Zahlen selbst änderst du nichts — sie stehen schon fest und werden maschinell
nachgerechnet.

THEMENWELT   {titel} — {hook}
FOLGE        {glieder_text}, ? (nur zu deiner Orientierung — nicht wiederholen)

Schreibe GENAU einen Einleitungssatz, der die Themenwelt aufruft und zur Folge
passt, ohne eine der Zahlen zu nennen oder zu verändern.

ANTWORT NUR ALS JSON, GENAU IN DIESER FORM:
{{"einleitung": "In der Arena zählt Steve seine Punkte nach jeder Runde."}}"""


def _pruefe_zahlenmaterial_unveraendert(kern, antwort, maengel):
    """Sicherheitsnetz gegen ein Sprachmodell, das versucht, wahrheitstragende
    Felder mitzuliefern: Glieder, Fortsetzung, Ablenker und Regel kommen
    ausschließlich aus dem Kern. Liefert die Antwort eines dieser Felder
    trotzdem mit UND weicht es vom Kern ab, ist das ein Mangel, kein stiller
    Fall für 'wird eh ignoriert'."""
    for feld in ("glieder", "naechstes", "ablenker", "regel"):
        if feld in antwort and antwort[feld] != kern[feld]:
            maengel.append(f"Antwort verändert das Zahlenmaterial im Feld {feld!r} "
                            f"(Kern: {kern[feld]!r}, Antwort: {antwort[feld]!r}) — "
                            "Zahlen kommen ausschließlich aus dem Kern")


def verkleide_folge(kern, themenwelt, llm, seed=0):
    """Kleidet einen Folgen-Kern (raetsel_kern.erzeuge_folge) mit einem
    Einleitungssatz aus 'llm' ein. Rückgabe: (aufgabe, maengel).

    Glieder, Fortsetzung und Ablenker kommen unverändert aus dem Kern; das
    Sprachmodell liefert ausschließlich den Einleitungssatz. seed wird hier
    nur der Vollständigkeit halber entgegengenommen (Signatur-Gleichklang mit
    verkleide_logikgitter) — diese Funktion trifft selbst keine Zufallswahl.
    """
    maengel = []
    text = llm(_folge_prompt(kern, themenwelt))
    antwort = _json_lesen(text, maengel)
    if antwort is None:
        return None, maengel

    _pruefe_zahlenmaterial_unveraendert(kern, antwort, maengel)
    if maengel:
        return None, maengel

    einleitung = antwort.get("einleitung")
    if not isinstance(einleitung, str) or not einleitung.strip():
        maengel.append("Einleitungssatz fehlt oder ist leer")
        return None, maengel
    if not _hoechstens_ein_satz(einleitung):
        maengel.append(f"Einleitung ist länger als ein Satz: {einleitung!r}")
        return None, maengel

    if not K.pruefe_folge(kern["glieder"], kern["naechstes"], kern["regel"]):
        maengel.append("der Kern selbst ist nicht in sich konsistent (pruefe_folge lehnt ab) — "
                        "das darf nie passieren und liegt nicht am Sprachmodell")
        return None, maengel

    aufgabe = {
        "frage_text": f"{einleitung.strip()} {_FRAGE_FOLGE}",
        "glieder": list(kern["glieder"]),
        "naechstes": kern["naechstes"],
        "ablenker": list(kern["ablenker"]),
    }
    return aufgabe, []
