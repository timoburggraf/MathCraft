# -*- coding: utf-8 -*-
"""Erklärt eine Aufgabe an einem gleichartigen Beispiel (Z6 aus ZIELE.md).

Wenn es beim zweiten Anlauf immer noch klemmt, hilft ein Tipp aus der Konserve
oft nicht weiter — er sagt, worauf zu achten ist, aber nicht, wie es geht.
Hier rechnet stattdessen jemand eine ähnliche Aufgabe vor.

Drei Dinge sind nicht verhandelbar:

  Kein Schlüssel auf dem Kindergerät. Die App schickt nur, welches Paket und
  welche Aufgabe gemeint sind — den Rest schlägt der Dienst selbst nach und
  ruft von hier aus an. Auf dem Handy liegt nichts, was jemand abgreifen kann.

  Nicht die Lösung. Erklärt wird an einer gleichartigen Aufgabe mit anderen
  Zahlen. Wer die Antwort vorgesagt bekommt, hat nichts gelernt.

  Nachgerechnet. Das Beispiel läuft durch denselben Prüfer wie die Pakete.
  Was nicht aufgeht, wird verworfen; die App fällt dann auf den festen Tipp
  zurück. Ein Modell, das sich verrechnet, darf einem Kind nichts beibringen.

Daraus folgt eine ungewöhnliche Reihenfolge in der Leitung: Das Modell liefert
erst die Rechnung, dann die Erklärung. Nur so lässt sich das Beispiel prüfen,
bevor überhaupt etwas auf dem Bildschirm steht — und trotzdem strömt der Text
danach Wort für Wort, statt dass das Kind sechs Sekunden vor einem leeren Feld
sitzt. Angezeigt wird nachher wieder in der natürlichen Reihenfolge: erst die
Erklärung, dann das Beispiel darunter.

  .venv/bin/python tutor/erklaerer.py zahl_bis20@1 0     # von Hand ausprobieren
"""
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import curriculum as C       # noqa: E402   Alter und Klasse je Stufe
import validate as V          # noqa: E402

UNITS = ROOT / "data" / "units_seed.json"
# MC_ERK_CACHE hängt die Ablage woanders hin — der Test soll die echten
# Erklärungen weder lesen noch überschreiben.
CACHE = Path(os.environ.get("MC_ERK_CACHE") or (ROOT / "data" / "erklaerungen"))

MODEL = "claude-opus-5"
# Niedriger Effort, aber Nachdenken AN. Der erste Anlauf lief ohne — das war
# messbar schlechter: Von drei Versuchen verrechnete sich einer (12+5=18),
# einer korrigierte sich mitten im Text selbst, einer verriet die Lösung. Der
# Prüfer fing zwar alles ab, aber dann bekommt das Kind eben nichts. Mit
# Nachdenken auf niedrigem Effort kostet es etwas Zeit und liefert dafür
# etwas, das durchgeht.
EFFORT = "low"
MAX_TOKENS = 1600      # das Nachdenken zählt mit hinein

SYSTEM = """Du hilfst einem Grundschulkind bei Mathe. Wie alt es ist, steht
in der Anfrage — richte Wortwahl und Satzlänge danach.

Es ist bei einer Aufgabe nicht weitergekommen und hat um eine Erklärung
gebeten. Zeig ihm den Weg — aber an einer ANDEREN, gleichartigen Aufgabe mit
anderen Zahlen. Die vorliegende Aufgabe löst du nicht und nennst ihre Antwort
nicht.

Antworte in genau dieser Form und Reihenfolge, ohne Überschriften davor:

RECHNUNG: <Term> = <Ergebnis>
BEISPIEL: <die Beispielaufgabe, ein Satz>

<zwei bis drei kurze Sätze Erklärung>

Zur Rechnung: ein reiner Term aus Zahlen, Klammern und + - * /, ohne Wörter,
und er ergibt genau das angegebene Ergebnis. Beides in eine Zeile.

Zur Erklärung: Grundschulwortschatz, keine Fachwörter, du sprichst das Kind
mit "du" an. Sag, worauf es ankommt, und rechne das Beispiel Schritt für
Schritt vor. Keine Einleitung, kein Lob, keine Rückfrage.

Antworte ausschließlich mit dem fertigen Ergebnis. Keine Überlegungen, keine
Zwischenstände, keine verworfenen Entwürfe und keine Bemerkungen über dein
eigenes Vorgehen. Wenn dir auffällt, dass ein Ansatz nicht taugt, verwirf ihn
stillschweigend und schreib nur den brauchbaren auf.

Gib keine internen oder System-XML-Tags aus."""

# Ein vollständiges Kopfpaar: RECHNUNG-Zeile, direkt gefolgt von BEISPIEL-Zeile.
# Genommen wird das LETZTE im Puffer — korrigiert sich das Modell doch einmal
# selbst, fällt der verworfene Entwurf damit weg, statt beim Kind zu landen.
KOPF = re.compile(r"^RECHNUNG:(.*)\nBEISPIEL:(.*)\n", re.M | re.I)
KOPF_MAX = 1200     # so lange wird auf ein Kopfpaar gewartet, dann ist Schluss

# So viel Prosa wird zurückgehalten und geprüft, bevor das erste Wort
# hinausgeht. Genug, um ein durchgerutschtes <thinking> zu erwischen, wenig
# genug, dass es niemand merkt.
VORLAUF = 80


# --------------------------------------------------------------- Nachschlagen

_units = {"stand": None, "je_id": None}


def aufgabe(unit_id, index):
    """Die Aufgabe zu Paket und Nummer — der Dienst kennt sie selbst."""
    if not UNITS.exists():
        return None, None
    stand = (UNITS.stat().st_mtime_ns, UNITS.stat().st_size)
    if _units["stand"] != stand:
        try:
            roh = json.loads(UNITS.read_text("utf-8")).get("units", [])
        except (ValueError, OSError):
            return None, None
        _units["je_id"] = {f'{u["skill"]}@{u["stage"]}': u for u in roh}
        _units["stand"] = stand
    u = _units["je_id"].get(unit_id)
    if not u or not isinstance(index, int) or not (0 <= index < len(u["tasks"])):
        return None, None
    return u, u["tasks"][index]


# ------------------------------------------------------------------ Prüfung

def pruefe_beispiel(rechnung, ergebnis, frage, t):
    """Rechnet das Beispiel nach. Rückgabe: Liste der Beanstandungen."""
    probleme = []
    try:
        wert, _ = V.eval_term(rechnung or "")
    except V.TermError as e:
        return [f"Rechnung geht nicht auf: {e}"]

    if not isinstance(ergebnis, (int, float)) or abs(wert - ergebnis) > 1e-9:
        probleme.append(f"{rechnung} ergibt {wert}, angegeben ist {ergebnis}")

    # Gleichartig heißt: nicht dieselbe. Sonst hat er die Lösung vorgesagt.
    frage = str(frage or "").strip()
    if not frage:
        probleme.append("Beispiel ohne Frage")
    elif frage.lower() == str(t.get("q", "")).strip().lower():
        probleme.append("Beispiel ist die vorliegende Aufgabe selbst")
    eigene = t.get("a")
    if isinstance(eigene, (int, float)) and not isinstance(eigene, bool) \
            and isinstance(ergebnis, (int, float)) and abs(eigene - ergebnis) < 1e-9:
        probleme.append("Beispiel führt auf dieselbe Antwort wie die Aufgabe")
    return probleme


def pruefe_text(text):
    """Die Erklärung selbst. Nur das, was sich am Anfang schon entscheiden lässt."""
    if not isinstance(text, str) or len(text.strip()) < 15:
        return ["Erklärung fehlt oder ist zu kurz"]
    if "<" in text:
        return ["Erklärung enthält Markup"]
    return []


def _kopfzeilen(zeilen):
    """RECHNUNG- und BEISPIEL-Zeile auseinandernehmen. Rückgabe: (dict|None, Grund)."""
    rechnung = beispiel = None
    for z in zeilen:
        s = z.strip()
        if s.upper().startswith("RECHNUNG:"):
            rechnung = s.split(":", 1)[1].strip()
        elif s.upper().startswith("BEISPIEL:"):
            beispiel = s.split(":", 1)[1].strip()
    if rechnung is None or beispiel is None:
        return None, "Antwort hält sich nicht an die Form"
    if "=" not in rechnung:
        return None, "Rechnung ohne Ergebnis"
    term, _, roh = rechnung.rpartition("=")
    try:
        ergebnis = float(roh.strip().replace(",", "."))
    except ValueError:
        return None, f"Ergebnis nicht lesbar: {roh.strip()!r}"
    return ({"frage": beispiel, "rechnung": term.strip(),
             "ergebnis": int(ergebnis) if float(ergebnis).is_integer() else ergebnis},
            "")


def _kopf_suchen(puffer):
    """Das letzte vollständige Kopfpaar im Puffer. Rückgabe: (kopf, rest, grund).

    kopf ist None und rest ist None, solange noch keins da ist — dann muss der
    Aufrufer weitersammeln. Alles vor dem Kopfpaar fällt weg: Steht dort ein
    verworfener Entwurf des Modells, hat er beim Kind nichts zu suchen.
    """
    treffer = list(KOPF.finditer(puffer))
    if not treffer:
        if len(puffer) > KOPF_MAX:
            return None, "", "Antwort hält sich nicht an die Form"
        return None, None, ""
    m = treffer[-1]
    kopf, grund = _kopfzeilen(["RECHNUNG:" + m.group(1), "BEISPIEL:" + m.group(2)])
    if not kopf:
        return None, "", grund
    return kopf, puffer[m.end():].lstrip(), ""


# ------------------------------------------------------------------- Aufruf

def _client():
    from anthropic import Anthropic
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import konfig
    return Anthropic(api_key=konfig.geheim("ANTHROPIC_API_KEY"))


def _frage(u, t):
    st = C.STAGES.get(u.get("stage")) or {}
    teile = [f'Das Kind ist etwa {st.get("alter", 8)} Jahre alt ({st.get("grade", "Grundschule")}).',
             f'Bereich: {u["skill"]}, Stufe {u["stage"]}',
             f'Aufgabenart: {t.get("type")}',
             f'Die Aufgabe, an der es klemmt: {t.get("q","")}']
    if isinstance(t.get("check"), dict) and t["check"].get("expr"):
        teile.append("Ihr Rechenweg (nur zu deiner Information, nicht verraten): "
                     + t["check"]["expr"])
    if t.get("hint"):
        teile.append(f'Der feste Tipp lautet: {t["hint"]}')
    teile.append("Erkläre den Weg an einer gleichartigen Aufgabe mit anderen Zahlen.")
    # Ohne diesen Satz landet das Modell erstaunlich oft auf demselben Ergebnis
    # und verrät damit die Lösung — der Prüfer wirft es dann weg, und das Kind
    # bekommt gar nichts. Billiger, es vorher zu sagen.
    if isinstance(t.get("a"), (int, float)) and not isinstance(t.get("a"), bool):
        teile.append(f'Dein Beispiel darf NICHT auf {t["a"]} hinauslaufen — das ist '
                     f'die Antwort der vorliegenden Aufgabe. Wähl andere Zahlen.')
    return "\n".join(teile)


def _cache_pfad(unit_id, index):
    return CACHE / f'{unit_id.replace("@", "_")}_{index}.json'


def _aus_ablage(unit_id, index):
    pfad = _cache_pfad(unit_id, index)
    if not pfad.exists():
        return None
    try:
        return json.loads(pfad.read_text("utf-8"))
    except (ValueError, OSError):
        return None


def _in_ablage(unit_id, index, fertig):
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        _cache_pfad(unit_id, index).write_text(
            json.dumps(fertig, ensure_ascii=False, indent=1), "utf-8")
    except OSError:
        pass


def erklaere_stream(unit_id, index, client=None, ohne_cache=False):
    """Häppchenweise, sobald etwas da ist. Erzeugt Paare (art, wert):

        ("bsp", {...})   das geprüfte Beispiel — kommt zuerst, siehe oben
        ("txt", "…")     ein Stück Erklärung
        ("fertig", {…})  Dauer und Kosten
        ("weg", "Grund") nichts Brauchbares; die App nimmt den festen Tipp

    Nach "weg" kommt nichts mehr. Vor "bsp" ist noch nichts angezeigt worden —
    darauf beruht die Zusicherung, dass ein Kind nie eine falsche Rechnung sieht.
    """
    u, t = aufgabe(unit_id, index)
    if not t:
        yield ("weg", "Aufgabe nicht gefunden")
        return

    if not ohne_cache:
        fertig = _aus_ablage(unit_id, index)
        if fertig:
            yield ("bsp", fertig["beispiel"])
            yield ("txt", fertig["erklaerung"])
            yield ("fertig", {"ms": 0, "aus_ablage": True})
            return

    try:
        client = client or _client()
    except Exception as e:
        yield ("weg", f"kein Zugang: {type(e).__name__}")
        return

    t0 = time.time()
    erste_worte = None
    kopf_durch = False
    puffer = ""          # bis der Kopf steht
    vorlauf = ""         # die ersten Zeichen Prosa, bis sie geprüft sind
    text = ""
    beispiel = None
    try:
        with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM,
                thinking={"type": "adaptive"},
                output_config={"effort": EFFORT},
                messages=[{"role": "user", "content": _frage(u, t)}]) as strom:
            for stueck in strom.text_stream:
                if not kopf_durch:
                    puffer += stueck
                    beispiel, rest, grund = _kopf_suchen(puffer)
                    if not beispiel:
                        if grund:
                            yield ("weg", grund)
                            return
                        continue                      # Kopf noch nicht vollständig
                    probleme = pruefe_beispiel(beispiel["rechnung"], beispiel["ergebnis"],
                                               beispiel["frage"], t)
                    if probleme:
                        yield ("weg", " | ".join(probleme[:2]))
                        return
                    yield ("bsp", beispiel)
                    kopf_durch = True
                    stueck = rest
                    if not stueck:
                        continue

                if vorlauf is not None:
                    vorlauf += stueck
                    if len(vorlauf) < VORLAUF:
                        continue                      # noch zurückhalten
                    if "<" in vorlauf:
                        yield ("weg", "Erklärung enthält Markup")
                        return
                    stueck, vorlauf = vorlauf, None
                    erste_worte = int((time.time() - t0) * 1000)

                text += stueck
                yield ("txt", stueck)

            # Was im Vorlauf hängengeblieben ist, wenn die Antwort kurz war
            if vorlauf is not None:
                if "<" in vorlauf:
                    yield ("weg", "Erklärung enthält Markup")
                    return
                erste_worte = int((time.time() - t0) * 1000)
                text += vorlauf
                yield ("txt", vorlauf)

            nachricht = strom.get_final_message()
    except Exception as e:
        yield ("weg", f"Aufruf gescheitert: {type(e).__name__}: {e}")
        return

    probleme = pruefe_text(text)
    if probleme or not beispiel:
        # Der Text stand schon da. Er wird nicht abgelegt, damit die nächste
        # Anfrage es noch einmal versucht — angezeigt bleibt er trotzdem.
        yield ("fertig", {"ms": int((time.time() - t0) * 1000), "aus_ablage": False,
                          "nicht_abgelegt": " | ".join(probleme) or "ohne Beispiel"})
        return

    dauer = int((time.time() - t0) * 1000)
    _in_ablage(unit_id, index, {"erklaerung": text.strip(), "beispiel": beispiel,
                                "ms": dauer, "erste_worte": erste_worte,
                                "aus_ablage": False})
    yield ("fertig", {"ms": dauer, "erste_worte": erste_worte, "aus_ablage": False,
                      "kosten": {"rein": nachricht.usage.input_tokens,
                                 "raus": nachricht.usage.output_tokens}})


def erklaere(unit_id, index, client=None, ohne_cache=False):
    """Alles auf einmal — für die Kommandozeile und die Tests."""
    text, beispiel, schluss, grund = "", None, {}, ""
    for art, wert in erklaere_stream(unit_id, index, client, ohne_cache):
        if art == "bsp":
            beispiel = wert
        elif art == "txt":
            text += wert
        elif art == "fertig":
            schluss = wert
        elif art == "weg":
            grund = wert
    if grund or not beispiel or not text.strip():
        return None, [grund or "nichts Brauchbares"]
    return (dict(schluss, erklaerung=text.strip(), beispiel=beispiel),
            [f'{schluss.get("ms", 0)} ms'])


def main():
    if len(sys.argv) < 3:
        sys.exit("Aufruf: erklaerer.py <paket-id> <aufgabennummer> [--frisch]")
    frisch = "--frisch" in sys.argv
    t0 = time.time()
    erste = None
    text, beispiel, schluss = "", None, {}
    for art, wert in erklaere_stream(sys.argv[1], int(sys.argv[2]), ohne_cache=frisch):
        if art == "weg":
            print(f"verworfen: {wert}")
            return 1
        if art == "bsp":
            beispiel = wert
        elif art == "txt":
            if erste is None:
                erste = int((time.time() - t0) * 1000)
            text += wert
            sys.stdout.write(wert)
            sys.stdout.flush()
        elif art == "fertig":
            schluss = wert
    print(f'\n\n  Beispiel: {beispiel["frage"]}')
    print(f'            {beispiel["rechnung"]} = {beispiel["ergebnis"]}')
    if schluss.get("aus_ablage"):
        print(f"\n  aus der Ablage, {erste} ms bis zum ersten Wort")
    else:
        k = schluss.get("kosten", {})
        print(f'\n  {erste} ms bis zum ersten Wort · {schluss.get("ms")} ms vollständig'
              + (f' · {k.get("rein")} rein, {k.get("raus")} raus' if k else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
