# -*- coding: utf-8 -*-
"""Erzeugt Lernpakete mit Claude und lässt kein einziges ungeprüft durch.

  .venv/bin/python build/generate_units.py --seed          # Grundstock (Stufe 1-3)
  .venv/bin/python build/generate_units.py --seed --klasse 4  # Vorrat für einen Viertklässler
  .venv/bin/python build/generate_units.py --skill plus_bis20 --stage 2 --n 2
  .venv/bin/python build/generate_units.py --seed --dry-run  # nur zeigen, was liefe

Ablauf je Paket: erzeugen → validate.check_unit → bei Mängeln neu anfordern,
diesmal mit den Mängeln im Prompt. Nach drei Fehlversuchen wird das Paket
verworfen und protokolliert. Was die App zu sehen bekommt, ist nachgerechnet.

Der Schlüssel kommt aus dem Vault, nie aus dem Quelltext.
"""
import argparse
import json
import random
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # konfig.py

import curriculum as C
import fundus as F
import schema as S
import validate as V
import raetsel_kern as K
import verkleidung as VK
import kern_pakete as KP

ROOT = Path(__file__).resolve().parent.parent
SEED_OUT = ROOT / "data" / "units_seed.json"
REJECT_LOG = ROOT / "data" / "verworfen.json"
# Was hier erzeugt wurde, steht später auf der Elternseite. Angehängt, nie
# überschrieben — Z3 verlangt, dass jede Anpassung nachvollziehbar bleibt.
ENTSCHEIDUNGEN = ROOT / "data" / "entscheidungen.jsonl"

MODEL = "claude-opus-5"
TRIES = 3                    # Versuche je Paket, bevor es verworfen wird
DEFAULT_BUDGET = 400_000     # Ausgabe-Token je Lauf; grob 10 EUR Deckel


# --------------------------------------------------------------- Anweisungen
# Dieser Block ist bei jedem Aufruf identisch und wird deshalb zwischenge-
# speichert (Prompt-Caching) — er kostet dann nur noch einen Bruchteil.
SYSTEM = """Du baust Matheaufgaben für ein Grundschulkind, das in Mathematik als
besonders begabt aufgefallen ist. Es soll gefordert, aber nie überfahren werden. Die
Aufgaben erscheinen in einer Lern-App, in der es Punkte, Sterne und Abzeichen sammelt.

WER DA LIEST
Wie alt das Kind ist und in welche Klasse es geht, steht bei jedem Auftrag unter KIND —
richte Wortwahl und Satzlänge danach. Es liest noch langsam. Jeder Satz, den es zweimal
lesen muss, kostet mehr Kraft als das Rechnen selbst. Also: kurze Sätze, vertraute
Wörter, höchstens zwei Sätze pro Aufgabe. Sprich es direkt an ("du"), niemals von oben
herab. Kein "Super!", kein "Ganz einfach!" — das erledigt die App. Schreib geschlechts-
neutral: Die App wird von Mädchen wie Jungen benutzt.

DIE EINKLEIDUNG
Jedes Paket spielt in einer Themenwelt, die ihn interessiert. Nutze ihre Begriffe
selbstverständlich, so wie ein Kumpel reden würde, der das Spiel auch kennt. Die
Einkleidung darf die Aufgabe nie verstecken: Zuerst versteht er die Situation, dann
sieht er die Rechnung. Erfinde keine Markennamen dazu und keine Figuren, die es nicht
gibt — allgemeine Begriffe der Welt genügen völlig.

DIE HARTEN REGELN — jede Verletzung führt zur Ablehnung des ganzen Pakets
1. Rechne jede Aufgabe selbst nach, bevor du sie hinschreibst. Ein falsches Ergebnis
   ist der schlimmste Fehler, den du machen kannst: er lernt dann etwas Falsches.
2. Jede Rechenaufgabe braucht im Feld "check" den Rechenweg als reinen Term ("8+5",
   "(12-4)*3"). Dieser Term wird maschinell ausgerechnet und muss exakt deine Antwort
   ergeben. Keine Wörter, keine Variablen, keine Einheiten im Term.
3. Halte den Zahlenraum der Stufe ein — auch bei Zwischenergebnissen und in den
   Ablenkern. Keine negativen Ergebnisse, solange nichts anderes dasteht.
4. Bei Auswahlaufgaben ist genau eine Antwort richtig. Die anderen drei müssen
   nachweislich falsch sein, aber plausibel: typische Rechenfehler sind gute Ablenker
   (Zehnerübergang vergessen, Rechenart verwechselt), Zufallszahlen sind schlechte.
5. Alle vier Möglichkeiten sind etwa gleich lang und gleich gebaut. Die richtige darf
   nicht die längste oder ausführlichste sein — sonst rät er sie an der Form.
6. Innerhalb eines Pakets keine Frage zweimal, auch nicht mit anderen Zahlen im selben
   Muster. Variiere die Situation, nicht nur die Ziffern.
7. Die Aufgaben steigen innerhalb des Pakets an: die ersten zwei holen ihn ab, die
   letzten zwei fordern ihn.

WAS SCHWER HEISST
Komplexität und Schwierigkeit kommen nicht von großen Zahlen, sondern von komplexer
Logik, komplexer Algorithmik oder von mehreren Schritten, die man im Kopf machen muss,
um das Problem zu lösen. Eine schwerere Aufgabe hat also mehr Hinweise, eine längere
Schlusskette oder mehr Zwischenschritte im Kopf — nie bloß größere Zahlen oder längere
Rechenketten. Ein Term wie 4*3*2*1*10 ist Ziffernschieben, keine Denkaufgabe; bei
Kombinatorik bleibt jede Rechnung eine kurze Kette aus Einmaleins-Schritten.

DER TIPP
Das Feld "hint" ist ein Hinweis auf den Weg, nie die Lösung. "Zerlege die 5 in 2 und 3"
ist gut. "Es sind 13" ist wertlos.

TON DER RÜCKMELDUNG
Wenn du erklärst (Aufgabentyp "entdecken"), dann zeige die Idee an einem Beispiel,
statt eine Regel zu verkünden. Ein Grundschulkind versteht "drei Reihen mit je vier
Blöcken sind zwölf" sofort und "Multiplikation ist wiederholte Addition" nie."""


TYPE_HELP = {
    "entdecken":  "eine neue Idee zeigen und an einem Beispiel erklären, ohne Bewertung",
    "zahl":       "er tippt eine Zahl ein",
    "wahl":       "vier Möglichkeiten, genau eine stimmt",
    "wahrfalsch": "eine Behauptung, er entscheidet wahr oder falsch",
    "ordnen":     "drei bis sechs Zahlen in die richtige Reihenfolge tippen",
    "zuordnen":   "Paare verbinden, jede Karte genau einmal",
    "mehrschritt":"eine Geschichte, die in zwei bis drei Schritten gelöst wird",
    "gitter":     "ein kleines Feld aus Zeichen; er tippt ein Feld an oder wählt aus",
}


def build_prompt(sk, stage, wid, n_tasks, problems=None):
    w = C.world(wid)
    typen = "\n".join(f'  · {t}: {TYPE_HELP[t]}' for t in sk["types"])
    st = C.STAGES[stage]
    ops = ", ".join(sorted(C.ops_allowed(stage)))

    p = f"""Baue EIN Lernpaket.

KIND         etwa {st['alter']} Jahre alt, {st['grade']}
FERTIGKEIT   {sk['title']} ({sk['id']})
AUFTRAG      {sk['brief']}
STUFE        {stage} — {st['name']}, etwa {st['grade']}
ZAHLENRAUM   alle Zahlen und Ergebnisse höchstens {st['max_value']}
RECHENARTEN  nur {ops}
THEMENWELT   {w['title']} — {w['hook']}
UMFANG       genau {n_tasks} Aufgaben, ansteigend schwer

ERLAUBTE AUFGABENARTEN (nur diese):
{typen}

MISCHUNG     Höchstens {max(2, n_tasks // 3)} der {n_tasks} Aufgaben dürfen vom Typ
             "zahl" sein. Nutze mindestens drei verschiedene Arten. Ein Kind, das
             achtmal hintereinander eine Zahl eintippt, übt das Ziffernfeld, nicht
             den Stoff — und ZIELE.md setzt die Obergrenze je Art bei 35 %."""

    if problems:
        p += ("\n\nDEIN LETZTER VERSUCH WURDE ABGELEHNT. Die Prüfung hat gefunden:\n"
              + "\n".join(f"  · {m}" for m in problems[:8])
              + "\n\nBaue das Paket neu und vermeide genau diese Fehler. "
                "Rechne diesmal jede Aufgabe einzeln nach, bevor du sie hinschreibst.")
    return p


# ------------------------------------------------------------------- Aufrufe

class Budget:
    """Deckel gegen Ausreißer. Zählt, was der Lauf an Ausgabe-Token kostet."""

    def __init__(self, limit):
        self.limit, self.out, self.inp, self.cached, self.calls = limit, 0, 0, 0, 0

    def add(self, usage):
        self.calls += 1
        self.out += usage.output_tokens
        self.inp += usage.input_tokens
        self.cached += getattr(usage, "cache_read_input_tokens", 0) or 0

    def left(self):
        return self.limit - self.out

    def report(self):
        # Opus 5: 5 USD je Mio. Eingabe, 25 je Mio. Ausgabe; Cache-Lesen ~0,1x
        eur = (self.inp * 5 + self.cached * 0.5 + self.out * 25) / 1e6 * 0.92
        return (f"{self.calls} Aufrufe · {self.inp} rein ({self.cached} aus dem Cache) · "
                f"{self.out} raus · rund {eur:.2f} EUR")


def get_client():
    from anthropic import Anthropic
    import konfig
    return Anthropic(api_key=konfig.geheim("ANTHROPIC_API_KEY"))


def ask(client, prompt, fmt, budget, max_tokens=16000):
    """Ein Aufruf. Gibt das geparste JSON zurück oder None."""
    if budget.left() <= 0:
        raise RuntimeError("Budget aufgebraucht")
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "high", "format": fmt},
    )
    budget.add(resp.usage)
    if resp.stop_reason == "refusal":
        print("     [!] Anfrage wurde abgelehnt")
        return None
    if resp.stop_reason == "max_tokens":
        print("     [!] Antwort abgeschnitten – max_tokens zu klein")
        return None
    text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"     [!] Antwort ist kein gültiges JSON: {e}")
        return None


def ask_text(client, prompt, budget, max_tokens=4000):
    """Wie ask(), aber für die Verkleidungsschicht (D4, ZIELE-V2.md): liefert
    reinen Text zurück statt vorgeparstem JSON – verkleidung.py parst die
    Antwort selbst, tolerant gegenüber Markdown-Codezäunen. Nutzt dieselbe
    Budget-Buchführung und denselben zwischengespeicherten Systemblock wie
    ask(); ask() selbst bleibt für den bisherigen Pfad unverändert.
    """
    if budget.left() <= 0:
        raise RuntimeError("Budget aufgebraucht")
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    budget.add(resp.usage)
    if resp.stop_reason == "refusal":
        print("     [!] Anfrage wurde abgelehnt")
        return None
    if resp.stop_reason == "max_tokens":
        print("     [!] Antwort abgeschnitten – max_tokens zu klein")
        return None
    return "".join(b.text for b in resp.content if b.type == "text")


def make_unit(client, sid, stage, wid, budget, n_tasks=8):
    """Erzeugt ein geprüftes Paket. Rückgabe: (Paket|None, Protokoll).

    Wählt automatisch den passenden Erzeugungspfad (D4, ZIELE-V2.md): den
    deterministischen Kern für die Fertigkeit log_gitter und die sechs
    Muster-Fertigkeiten mit einer Folgenregel (FOLGEN_REGEL), sonst
    unverändert das freie Sprachmodell wie bisher. Kein CLI-Schalter nötig –
    pfad_von(sid) allein entscheidet; --dry-run zeigt den gewählten Pfad,
    ohne ihn zu gehen (siehe main()).
    """
    pfad = pfad_von(sid)
    if pfad == "logikgitter":
        return _make_unit_logikgitter(client, sid, stage, wid, budget)
    if pfad == "folgen":
        return _make_unit_folgen(client, sid, stage, wid, budget)
    if pfad == "kern":
        # Die zwölf neuen Denkschule-Fertigkeiten (SPEC_lektionen_v2.md §8):
        # vollständig deterministisch, kein Sprachmodell nötig – client/
        # budget bleiben ungenutzt, exakt wie bei den beiden Pfaden oben.
        return KP.baue_paket(sid, stage, wid)
    return _make_unit_standard(client, sid, stage, wid, budget, n_tasks)


def _make_unit_standard(client, sid, stage, wid, budget, n_tasks=8):
    """Der bisherige, unveränderte Pfad über das freie Sprachmodell – für
    jede Fertigkeit ohne deterministischen Kern (D4). Byte-gleiches
    Prompt-Verhalten wie vor der D4-Anbindung."""
    sk = C.skill(sid)
    problems, log, platz = None, [], 16000
    for versuch in range(1, TRIES + 1):
        obj = ask(client, build_prompt(sk, stage, wid, n_tasks, problems),
                  S.unit_response(), budget, platz)
        if obj is None:
            log.append(f"Versuch {versuch}: keine brauchbare Antwort")
            # Gitteraufgaben brauchen viel Platz, und das Nachdenken zählt mit.
            # Wurde abgeschnitten, hilft kein besserer Prompt – nur mehr Raum.
            platz = min(platz * 2, 64000)
            continue
        unit = {"skill": sid, "stage": stage, "world": wid,
                "title": obj.get("title", ""), "intro": obj.get("intro", ""),
                "tasks": _clean(obj.get("tasks", []))}
        problems = V.check_unit(unit)
        if not problems:
            return unit, log
        log.append(f"Versuch {versuch}: " + " | ".join(problems[:3]))
        print(f"     [~] Versuch {versuch} abgelehnt: {problems[0][:70]}")
        time.sleep(0.5)
    return None, log


# ---------------------------------------- D4: deterministischer Kern (Logikgitter)
# LOGIKGITTER_SKILL ist die einzige Fertigkeit, die diesen Pfad nimmt (D1:
# log_gitter gehört zur Disziplin Logik & Deduktion). curriculum.py bleibt
# unverändert (Auftrags-Scope) – die Zuordnung, welche Fertigkeit welchen
# Pfad nimmt, steht deshalb bewusst hier statt dort.
LOGIKGITTER_SKILL = "log_gitter"

# Fertigkeit -> Regeltyp aus raetsel_kern.REGELTYPEN. Nur diese sechs
# Muster-Fertigkeiten haben eine so eindeutige, mechanisch ableitbare Regel,
# dass der deterministische Kern greift; must_form und must_rueck bleiben
# beim freien Sprachmodell (Formen- bzw. Rückwärtsmuster passen nicht in
# raetsel_kern.erzeuge_folge).
FOLGEN_REGEL = {
    "must_einfach": "plus",
    "must_schritt": "plus",
    "must_wechsel": "wechsel",
    "must_verdopp": "mal",
    "must_fibo": "fibo",
    "must_figur": "quadrat",
}


def pfad_von(sid):
    """Welchen Erzeugungspfad eine Fertigkeit nimmt (D4/SPEC_lektionen_v2.md
    §8): 'logikgitter', 'folgen', 'kern' (die zwölf neuen Denkschule-
    Fertigkeiten aus kern_pakete.py) oder 'standard' (das bisherige freie
    Sprachmodell). Reine Nachschlagefunktion, kein CLI-Schalter nötig –
    main() nutzt sie sowohl für --dry-run als auch (über make_unit) für den
    echten Lauf.
    """
    if sid == LOGIKGITTER_SKILL:
        return "logikgitter"
    if sid in FOLGEN_REGEL:
        return "folgen"
    if KP.hat_kern(sid):
        return "kern"
    return "standard"


def _seed_logikgitter(sid, stage, wid, index):
    """Deterministisches Seed-Schema für den Logikgitter-Kern: hängt nur von
    Fertigkeit, Stufe, Themenwelt und dem 0-basierten Aufgaben-Index im Paket
    ab (0..3) – nicht vom Versuch, damit ein Retry denselben (bereits als
    eindeutig lösbar geprüften) Kern behält und nur das Sprachmodell erneut
    um eine bessere Verkleidung bittet. zlib.crc32 statt hash(): Pythons
    eingebauter Stringhash ist pro Prozess zufällig gesalzen, crc32 ist es
    nicht – erst das macht den Lauf über mehrere Prozesse hinweg reproduzierbar.
    """
    text = f"logikgitter|{sid}|{stage}|{wid}|{index}"
    return zlib.crc32(text.encode("utf-8"))


def _logikgitter_groessen(stage):
    """Größenstaffel nach Stufe: vier Logikgitter-Größen (n_kategorien,
    n_elemente) je Paket, wie im Auftrag festgelegt."""
    if stage <= 4:
        return [(2, 3), (2, 3), (2, 3), (2, 3)]
    if stage <= 6:
        return [(2, 3), (2, 3), (3, 3), (3, 3)]
    return [(3, 3), (3, 3), (3, 4), (3, 4)]


def _logikgitter_aufgabe(client, sid, stage, welt, wid, index, groesse, budget):
    """Baut eine einzelne Logikgitter-Aufgabe: erst der deterministische Kern
    (immer eindeutig lösbar, raetsel_kern.erzeuge_logikgitter), dann bis zu
    TRIES Versuche, ihn über verkleidung.verkleide_logikgitter einzukleiden.
    Der Kern bleibt über alle Versuche hinweg derselbe – nur der Prompt an
    das Sprachmodell bekommt bei einem Mangel die Fehlerliste angehängt,
    genau wie im bestehenden Muster von _make_unit_standard/build_prompt.
    Rückgabe: (Aufgabe|None, Protokollzeilen).
    """
    n_kat, n_el = groesse
    seed = _seed_logikgitter(sid, stage, wid, index)
    kern = K.erzeuge_logikgitter(n_kat, n_el, seed)
    problems, log = None, []
    for versuch in range(1, TRIES + 1):
        def llm(prompt, _problems=problems):
            if _problems:
                prompt += ("\n\nDEIN LETZTER VERSUCH WURDE ABGELEHNT. Die Prüfung hat gefunden:\n"
                           + "\n".join(f"  · {m}" for m in _problems[:8])
                           + "\n\nAntworte neu und vermeide genau diese Fehler.")
            return ask_text(client, prompt, budget)

        aufgabe, maengel = VK.verkleide_logikgitter(kern, welt, llm, seed=seed)
        if aufgabe is None:
            problems = maengel
            log.append(f"Aufgabe {index + 1} Versuch {versuch}: " + " | ".join(maengel[:3]))
            continue
        aufgabe = dict(aufgabe, type="logikgitter")
        task_problems = V.check_task(aufgabe, stage, ["logikgitter"])
        if not task_problems:
            return aufgabe, log
        problems = task_problems
        log.append(f"Aufgabe {index + 1} Versuch {versuch}: " + " | ".join(task_problems[:3]))
    return None, log


def _make_unit_logikgitter(client, sid, stage, wid, budget):
    """Ein Paket aus vier Logikgitter-Aufgaben (D4). Scheitert eine einzige
    Aufgabe nach TRIES Versuchen endgültig, wird das ganze Paket verworfen –
    genau wie im bestehenden Muster von _make_unit_standard."""
    welt = C.world(wid)
    tasks, log = [], []
    for index, groesse in enumerate(_logikgitter_groessen(stage)):
        aufgabe, aufgabe_log = _logikgitter_aufgabe(client, sid, stage, welt, wid, index, groesse, budget)
        log += aufgabe_log
        if aufgabe is None:
            return None, log
        tasks.append(aufgabe)
    unit = {"skill": sid, "stage": stage, "world": wid,
            "title": f'Logikgitter · {welt["title"]}',
            "intro": "Kannst du jedes Rätsel durch Ausschluss knacken?",
            "tasks": tasks}
    problems = V.check_unit(unit)
    if problems:
        log.append("Paket: " + " | ".join(problems[:3]))
        return None, log
    return unit, log


# --------------------------------------------- D4: deterministischer Kern (Folgen)

def _seed_folge(sid, stage, wid, index):
    """Deterministisches Seed-Schema für den Folgen-Kern: wie
    _seed_logikgitter, aber mit eigenem Präfix, damit sich die Seedräume der
    beiden Kern-Pfade nicht überschneiden, und mit Index 0..7 (acht Aufgaben
    je Paket statt vier)."""
    text = f"folge|{sid}|{stage}|{wid}|{index}"
    return zlib.crc32(text.encode("utf-8"))


def _erzeuge_folge_sicher(regeltyp, seed, max_wert, laenge_start=5):
    """raetsel_kern.erzeuge_folge() lehnt eine Länge ab, für die der
    Zahlenraum zu eng ist (ValueError) – bei sehr kleinen Stufen (z.B.
    max_wert=20 für must_einfach) trifft das bei ungünstig gewürfelter
    Schrittweite auch fünf Glieder. Deshalb hier mit fallender Länge
    versuchen, bis eine passt; ab Länge 2 ist das für jede in FOLGEN_REGEL
    vorkommende Regel und jede curriculum-Stufe rechnerisch immer möglich.
    """
    letzter_fehler = None
    for laenge in range(laenge_start, 1, -1):
        try:
            return K.erzeuge_folge(regeltyp, seed, laenge=laenge, max_wert=max_wert)
        except ValueError as e:
            letzter_fehler = e
    raise ValueError(f"Zahlenraum {max_wert} zu eng für Regeltyp {regeltyp!r} "
                      f"(auch bei Länge 2): {letzter_fehler}")


def _folge_term(kern):
    """Leitet aus der Regel eines Folgen-Kerns den prüfbaren Rechenterm für
    die Fortsetzung ab (D4): der Kern bleibt wahrheitstragend, der Term ist
    nur die Nachrechnung für validate.py und muss – exakt wie im Auftrag
    verlangt – 'naechstes' ergeben, sonst lehnt validate.py die Aufgabe ab.
    """
    regel, glieder = kern["regel"], kern["glieder"]
    letztes = glieder[-1]
    typ = regel["typ"]
    if typ == "plus":
        return f"{letztes}+{regel['d']}"
    if typ == "mal":
        return f"{letztes}*{regel['q']}"
    if typ == "wechsel":
        schritt = regel["a"] if (len(glieder) - 1) % 2 == 0 else regel["b"]
        return f"{letztes}+{schritt}"
    if typ == "wachsend":
        return f"{letztes}+{len(glieder)}"
    if typ == "fibo":
        return f"{letztes}+{glieder[-2]}"
    if typ == "quadrat":
        # Differenzform (letztes Glied + Zuwachs): so rechnet das Kind diese
        # Folgen wirklich, und nur so bleibt der Term unter dem D2-Budget.
        n = regel["start_n"] + len(glieder)
        zuwachs = (2 * n - 1) if regel["form"] == "quadrat" else n
        return f"{letztes}+{zuwachs}"
    raise ValueError(f"unbekannter Regeltyp {typ!r} – kein Term ableitbar")


def _folge_zu_task(aufgabe, seed, term, ist_wahl):
    """Baut aus einer verkleideten Folgen-Aufgabe (frage_text, naechstes,
    ablenker) abwechselnd eine 'wahl'- oder 'zahl'-Aufgabe im Schema von
    schema.py. Die Wahrheit (naechstes, ablenker) kommt unverändert aus dem
    Kern; der Term aus _folge_term(); nur die Mischreihenfolge der Optionen
    braucht Zufall, deterministisch über denselben Seed wie der Kern.
    """
    q = aufgabe["frage_text"]
    if not ist_wahl:
        return {"type": "zahl", "q": q, "a": aufgabe["naechstes"], "check": {"expr": term}}
    optionen = [str(aufgabe["naechstes"])] + [str(a) for a in aufgabe["ablenker"]]
    reihenfolge = list(range(len(optionen)))
    random.Random(seed).shuffle(reihenfolge)
    return {"type": "wahl", "q": q, "opts": [optionen[i] for i in reihenfolge],
            "correct": reihenfolge.index(0), "check": {"expr": term}}


def _folge_aufgabe(client, sid, stage, welt, wid, index, regeltyp, max_wert, erlaubte_typen, budget):
    """Baut eine einzelne Folgen-Aufgabe: erst der deterministische Kern
    (immer regelkonform, raetsel_kern.erzeuge_folge), dann bis zu TRIES
    Versuche, den Einleitungssatz über verkleidung.verkleide_folge zu holen.
    Der Kern bleibt über alle Versuche hinweg derselbe. Gerade Indizes werden
    zu 'wahl'-Aufgaben, ungerade zu 'zahl'-Aufgaben (abwechselnd, wie
    verlangt) – außer 'wahl' ist für diese Fertigkeit laut curriculum.py gar
    nicht vorgesehen (must_figur: nur ["zahl","gitter"], curriculum.py bleibt
    im Auftrags-Scope unverändert); dann werden alle acht Aufgaben zu 'zahl'.
    Rückgabe: (Aufgabe|None, Protokollzeilen).
    """
    seed = _seed_folge(sid, stage, wid, index)
    kern = _erzeuge_folge_sicher(regeltyp, seed, max_wert)
    term = _folge_term(kern)
    ist_wahl = "wahl" in erlaubte_typen and index % 2 == 0
    problems, log = None, []
    for versuch in range(1, TRIES + 1):
        def llm(prompt, _problems=problems):
            if _problems:
                prompt += ("\n\nDEIN LETZTER VERSUCH WURDE ABGELEHNT. Die Prüfung hat gefunden:\n"
                           + "\n".join(f"  · {m}" for m in _problems[:8])
                           + "\n\nAntworte neu und vermeide genau diese Fehler.")
            return ask_text(client, prompt, budget)

        aufgabe, maengel = VK.verkleide_folge(kern, welt, llm, seed=seed)
        if aufgabe is None:
            problems = maengel
            log.append(f"Aufgabe {index + 1} Versuch {versuch}: " + " | ".join(maengel[:3]))
            continue
        task = _folge_zu_task(aufgabe, seed, term, ist_wahl)
        task_problems = V.check_task(task, stage, erlaubte_typen)
        if not task_problems:
            return task, log
        problems = task_problems
        log.append(f"Aufgabe {index + 1} Versuch {versuch}: " + " | ".join(task_problems[:3]))
    return None, log


def _make_unit_folgen(client, sid, stage, wid, budget):
    """Ein Paket aus acht Folgen-Aufgaben (D4), abwechselnd 'wahl' und
    'zahl'. Scheitert eine einzige Aufgabe nach TRIES Versuchen endgültig,
    wird das ganze Paket verworfen – genau wie im bestehenden Muster."""
    sk, welt = C.skill(sid), C.world(wid)
    regeltyp, max_wert = FOLGEN_REGEL[sid], C.max_value(stage)
    tasks, log = [], []
    for index in range(8):
        task, aufgabe_log = _folge_aufgabe(client, sid, stage, welt, wid, index,
                                            regeltyp, max_wert, sk["types"], budget)
        log += aufgabe_log
        if task is None:
            return None, log
        tasks.append(task)
    unit = {"skill": sid, "stage": stage, "world": wid,
            "title": f'Muster · {welt["title"]}',
            "intro": "Findest du die geheime Regel hinter jeder Reihe?",
            "tasks": tasks}
    problems = V.check_unit(unit)
    if problems:
        log.append("Paket: " + " | ".join(problems[:3]))
        return None, log
    return unit, log


def notiere(art, sid, stage, grund, belege):
    """Eine Entscheidung für die Elternseite festhalten (Z3).

    Angehängt statt geschrieben: Der Verlauf ist die Aussage. Scheitert es,
    darf das den Lauf nicht kosten — ein fehlender Eintrag ist ärgerlich, ein
    abgebrochener Erzeugerlauf teuer.
    """
    try:
        ENTSCHEIDUNGEN.parent.mkdir(parents=True, exist_ok=True)
        with ENTSCHEIDUNGEN.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": int(time.time() * 1000), "art": art, "skill": sid,
                                "stufe": stage, "grund": grund, "belege": belege},
                               ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"   !  Entscheidung nicht protokolliert: {e}")


def write_units(path, units):
    """Erst danebenschreiben, dann umbenennen.

    Der Lauf dauert Minuten und schreibt nach jedem Paket. Wer in der
    Zwischenzeit baut oder liest, bekäme sonst irgendwann eine halb
    geschriebene Datei zu fassen. Das Umbenennen ist auf demselben
    Dateisystem unteilbar.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"units": units}, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(path)


def _clean(tasks):
    """Räumt die Leerfelder weg, die das Schema erzwingt.

    Alle Felder einer Variante müssen laut Structured Outputs required sein –
    das Modell füllt deshalb auch die, die für seinen Fall keinen Sinn haben
    (leeres opts bei einer Gitteraufgabe mit Lösungsfeld). Die kommen hier raus,
    damit der Validator und die App nur echte Angaben sehen.
    """
    out = []
    for t in tasks:
        if not isinstance(t, dict):
            continue
        t = {k: v for k, v in t.items()
             if v not in (None, "", [], {}) and not (k == "correct" and v == -1)}
        if t.get("type") == "gitter" and "cell" in t:
            t.pop("opts", None); t.pop("correct", None)
        out.append(t)
    return out


# -------------------------------------------------------------- Grundstock

def seed_plan(stages=(1, 2, 3)):
    """Ein Paket je Fertigkeit auf den gewünschten Stufen.

    Reihenfolge nach Stufe, damit die Landkarte von vorn spielbar ist. Die
    Themenwelt rotiert, damit nicht drei Minecraft-Pakete hintereinander kommen.
    """
    plan, i = [], 0
    for stage in stages:
        for sk in sorted((s for s in C.SKILLS if s["stage"] == stage),
                         key=lambda s: C.AREA_IDS.index(s["area"])):
            plan.append((sk["id"], stage, C.WORLD_IDS[i % len(C.WORLD_IDS)]))
            i += 1
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="Grundstock für die APK erzeugen")
    ap.add_argument("--stages", help="Stufen für --seed, z.B. 4,5 (Standard 1,2,3)")
    ap.add_argument("--klasse", type=int,
                    help="Stufen aus der Schulklasse ableiten statt sie aufzuzählen "
                         f"(z. B. --klasse 4 -> Stufen {','.join(map(str, C.klasse_band(4)))}). "
                         "--stages schlägt diese Angabe.")
    ap.add_argument("--skill"); ap.add_argument("--stage", type=int)
    ap.add_argument("--world"); ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--tasks", type=int, default=8)
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()

    if a.seed:
        if a.stages:
            stages = tuple(int(x) for x in a.stages.split(","))
        elif a.klasse:
            stages = C.klasse_band(a.klasse)
            print(f"Klasse {a.klasse}: Stufen {','.join(map(str, stages))} "
                  f"(Einstieg {C.klasse_einstieg(a.klasse)})")
        else:
            stages = (1, 2, 3)
        plan, out = seed_plan(stages), Path(a.out or SEED_OUT)
    elif a.skill:
        sk = C.skill(a.skill)
        if not sk:
            raise SystemExit(f"unbekannte Fertigkeit: {a.skill}")
        stage = a.stage or sk["stage"]
        plan = [(a.skill, stage, a.world or random.choice(C.WORLD_IDS)) for _ in range(a.n)]
        out = Path(a.out or SEED_OUT)
    else:
        raise SystemExit("--seed oder --skill angeben")

    print(f"{len(plan)} Pakete geplant → {out}")
    if a.dry_run:
        for sid, stage, wid in plan:
            print(f'   {sid:16s} Stufe {stage}  {C.world(wid)["title"]:12s}  '
                  f'Pfad: {pfad_von(sid)}')
        return 0

    # Der Client kostet echtes Geld schon beim Anlegen nicht, aber sein Schlüssel
    # kommt aus dem Vault (Netzzugriff) – den Umweg spart sich ein Plan, der nur
    # aus deterministischen Kern-Paketen besteht (SPEC_lektionen_v2.md §8).
    braucht_client = any(pfad_von(sid) != "kern" for sid, _, _ in plan)
    client = get_client() if braucht_client else None
    budget = Budget(a.budget)
    have = {}
    if out.exists():
        have = {u["skill"] + "@" + str(u["stage"]): u
                for u in json.loads(out.read_text("utf-8")).get("units", [])}
    rejected = []

    for n, (sid, stage, wid) in enumerate(plan, 1):
        key = f"{sid}@{stage}"
        if key in have and not a.skill:
            print(f'[=] {n:3d}/{len(plan)} {sid} vorhanden')
            continue
        print(f'[..] {n:3d}/{len(plan)} {sid} Stufe {stage} · {C.world(wid)["title"]}')
        try:
            unit, log = make_unit(client, sid, stage, wid, budget, a.tasks)
        except RuntimeError as e:
            print(f"\n{e} – Lauf hier beendet.")
            break
        if unit:
            # Ersetzt dieser Lauf ein vorhandenes Paket (--skill auf eine
            # belegte Stelle), wandert die alte Fassung in den Fundus, bevor
            # sie aus units_seed.json verschwindet.
            if key in have:
                ab = F.lege_paket_ab(have[key])
                if ab:
                    print(f"     [ar] alte Fassung im Fundus: {ab.relative_to(ROOT)}")
            have[key] = unit
            notiere("neu", sid, stage, "vorratsluecke",
                    {"n": 1, "aufgaben": len(unit["tasks"]), "welt": wid})
            print(f'     [ok] {unit["title"]} ({len(unit["tasks"])} Aufgaben)')
        else:
            rejected.append({"skill": sid, "stage": stage, "world": wid, "log": log})
            print(f"     [xx] nach {TRIES} Versuchen verworfen")
        write_units(out, list(have.values()))

    if rejected:
        REJECT_LOG.write_text(json.dumps(rejected, ensure_ascii=False, indent=1), "utf-8")

    print(f"\n{len(have)} Pakete in {out}")
    print(f"{len(rejected)} verworfen" + (f" (siehe {REJECT_LOG.name})" if rejected else ""))
    print(budget.report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
