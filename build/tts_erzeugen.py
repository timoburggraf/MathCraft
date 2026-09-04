# -*- coding: utf-8 -*-
"""Erzeugt die vorproduzierten Vorlese-Stimmen für MathCraft (Auftrag A).

Sammelt zuerst den kompletten Vorlese-Korpus — jeden Text, den die App über
readBtn()/speak() vorlesen kann bzw. vorlesen könnte, sobald ein Aufrufer
dafür wired ist (siehe html_zu_sprechtext() unten für den einen Fall, in dem
das heute noch aussteht) — und schreibt ihn nach data/audio/korpus.json.
Danach kann es, mit einem Schlüssel für den Google-Gemini-Zugang, je fehlenden
Text und Stimme eine Aufnahme erzeugen und als Opus ablegen.

  .venv/bin/python build/tts_erzeugen.py --trocken
      Nur den Korpus schreiben, keine API-Aufrufe (Standardverhalten ohne
      GEMINI_API_KEY, und was die Tests verwenden).

  .venv/bin/python build/tts_erzeugen.py [--stimme zephyr …]
      Zusätzlich alle fehlenden Aufnahmen erzeugen (inkrementell — eine schon
      vorhandene Datei wird übersprungen). Den Schlüssel liefert konfig.py aus
      der Umgebung oder der .env; fehlt er, bleibt es beim Trockenlauf statt
      abzubrechen — der Korpus ist dann trotzdem geschrieben.

Architektur, siehe auch src/app.html:
  Audio-ID   crc32(utf8(normalisiert(text))) als 8-stelliger, führend
             genullter, vorzeichenloser Hex-String. normalisiere() MUSS
             buchstabengetreu mit der JS-Entsprechung in src/app.html
             (dort: normalisiereVorlesetext()/audioId(), siehe der
             Kommentar dort mit dem Verweis hierher) übereinstimmen.
  Ablage     data/audio/<stimme>/<id>.opus, stimme ∈ {zephyr, puck, leda}.
  Auslieferung  tutor/server.py, Route GET /audio/<stimme>/<id>.opus.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum as C

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "data" / "units_seed.json"
AUDIO_DIR = ROOT / "data" / "audio"
KORPUS = AUDIO_DIR / "korpus.json"

STIMMEN = ["zephyr", "puck", "leda"]
# Gemini erwartet den Namen groß geschrieben (prebuiltVoiceConfig.voiceName).
GEMINI_STIMMENNAMEN = {"zephyr": "Zephyr", "puck": "Puck", "leda": "Leda"}
MODELL = "gemini-2.5-flash-preview-tts"

# Der Stil-Hinweis geht nur an die API mit, ist aber NICHT Teil der Kennung —
# dieselbe Kennung entsteht unabhängig davon, ob (und mit welchem Präfix) sie
# tatsächlich erzeugt wurde. So bleibt eine spätere Anpassung des Präfixes
# folgenlos für schon vorhandene Dateien.
STIL_PRAEFIX = "Sprich warm, fröhlich und deutlich, wie ein freundlicher Begleiter für ein Kind: "

# Wie feedback() in src/app.html: eine der beiden Zeilen kommt zufällig dazu.
# Fürs Vorproduzieren genügt je Fall die erste — siehe html_zu_sprechtext()
# für den Grund, warum diese Texte heute noch nirgends tatsächlich gesprochen
# werden, aber trotzdem zum Korpus gehören (Auftrag A, Quellenliste).
LOB = ["Sitzt.", "Genau.", "Richtig.", "Stark.", "Perfekt.", "Läuft.", "Sauber."]
NOPE = ["Noch nicht ganz.", "Knapp daneben.", "Das war's nicht."]


# ------------------------------------------------------------------ Audio-ID
def normalisiere(text):
    """MUSS identisch zur JS-Fassung normalisiereVorlesetext() in src/app.html
    bleiben: trim() + jede Whitespace-Folge zu einem Leerzeichen."""
    return re.sub(r"\s+", " ", str(text).strip())


def audio_id(text):
    """MUSS identisch zur JS-Fassung audioId() in src/app.html bleiben."""
    import zlib
    norm = normalisiere(text)
    return format(zlib.crc32(norm.encode("utf-8")) & 0xFFFFFFFF, "08x")


def fmt_num(n):
    return str(n).replace(".", ",")


# Wortschatz für Roboteraufgaben (SPEC_lektionen_v2.md §2/§9). MUSS
# buchstabengetreu mit ROB_WORT/ROB_ZAHLWORT in src/app.html übereinstimmen —
# das ist dieselbe Verpflichtung wie bei normalisiere()/audio_id() oben.
ROB_WORT = {"N": "nach oben", "O": "nach rechts", "S": "nach unten", "W": "nach links",
            "V": "vor", "L": "links drehen", "R": "rechts drehen"}
ROB_ZAHLWORT = {2: "zweimal", 3: "dreimal", 4: "viermal"}


def rob_worte(programm):
    """MUSS identisch zur JS-Fassung robWorte() in src/app.html bleiben:
    Befehle als Worte, Schleifen bleiben als Gruppe erkennbar
    ("dreimal: vor, vor, rechts drehen")."""
    teile = []
    for b in (programm or []):
        if isinstance(b, dict) and isinstance(b.get("b"), list):
            zahlwort = ROB_ZAHLWORT.get(b.get("x"), f'{b.get("x")}-mal')
            teile.append(f"{zahlwort}: {rob_worte(b['b'])}")
        else:
            teile.append(ROB_WORT.get(b, ""))
    return ", ".join(teile)


def roboter_vorlesetext(t):
    """MUSS identisch zur JS-Fassung roboterVorlesetext() in src/app.html
    bleiben: q + "Das Programm: " + Befehle als Worte; im Modus "programm"
    gibt es kein vorgegebenes Programm, dort bleibt es bei q allein."""
    q = t.get("q") or ""
    if t.get("modus") == "programm":
        return q
    return f"{q} Das Programm: {rob_worte(t.get('programm'))}."


def positionen_vorlesetext(t):
    """MUSS identisch zur JS-Fassung positionenVorlesetext() in src/app.html
    bleiben: Rahmengeschichte + alle Hinweise + Frage."""
    rahmen = t.get("rahmen") or ""
    hinweise = " ".join(h.get("text", "") for h in (t.get("hinweise") or []))
    frage = t.get("frage_text") or ""
    return " ".join(x for x in (rahmen, hinweise, frage) if x)


def html_zu_sprechtext(html):
    """Wandelt die knappe HTML-Fassung eines Feedbacksatzes (<b>, <br>) in
    Sprechtext um: <br> wird zur Sprechpause (". "), alle übrigen Tags fallen
    weg.

    WICHTIG: Diese Feedbacksätze ("Sitzt. Richtig ist …") werden von der App
    heute an keiner Stelle tatsächlich per readBtn()/speak() vorgelesen — dazu
    müsste die Rückmeldung im Aufgabenbildschirm (feedback() in src/app.html)
    erst noch selbst einen Vorlesen-Knopf bekommen, was NICHT Teil dieses
    Auftrags ist (siehe die App-Änderungen dort: nur Einstellung, Ansicht,
    speak()). Der Auftrag nennt sie trotzdem ausdrücklich als Korpus-Quelle
    ("Feedbacksätze … je Aufgabe") — vermutlich, damit die Aufnahmen schon
    bereitstehen, sobald das nachgezogen wird. Diese Funktion baut deshalb
    nach, was ein künftiger Vorlesen-Knopf dort zu sprechen bekäme, ohne dass
    heute schon irgendein Aufrufer diesen Text tatsächlich an speak() gibt.
    """
    t = re.sub(r"<br\s*/?>", ". ", str(html))
    t = re.sub(r"<[^>]+>", "", t)
    return (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&#39;", "'"))


def _loesung_html(t):
    """Baut buchstabengetreu die HTML-Fassung nach, die feedback(t, loesung)
    in src/app.html für diesen Aufgabentyp bekäme (siehe dort qZahl/qWahl/
    qWahrFalsch/qOrdnen/qZuordnen/qMehrschritt/qGitter/qLogikgitter). Nur
    Rohmaterial für html_zu_sprechtext() — siehe deren Docstring."""
    typ = t.get("type")
    if typ == "zahl":
        return f"Richtig ist <b>{fmt_num(t.get('a'))}</b>."
    if typ == "wahl":
        opts, c = t.get("opts") or [], t.get("correct")
        return f"Richtig ist <b>{opts[c]}</b>." if isinstance(c, int) and 0 <= c < len(opts) else ""
    if typ == "wahrfalsch":
        return f"Die Behauptung ist <b>{'richtig' if t.get('a') else 'falsch'}</b>."
    if typ == "ordnen":
        items, order = t.get("items") or [], t.get("order") or []
        teile = [fmt_num(items[i]) for i in order if isinstance(i, int) and 0 <= i < len(items)]
        return f"Richtig ist <b>{' · '.join(teile)}</b>." if teile else ""
    if typ == "zuordnen":
        pairs = t.get("pairs") or []
        return "<br>".join(f"{a} → <b>{b}</b>" for a, b in pairs)
    if typ == "mehrschritt":
        steps = t.get("steps") or []
        return "<br>".join(f"{i+1}. {s.get('q','')} <b>{fmt_num(s.get('a'))}</b>"
                            for i, s in enumerate(steps))
    if typ == "gitter":
        if t.get("cell"):
            return "Das grüne Feld war richtig."
        opts, c = t.get("opts") or [], t.get("correct")
        return f"Richtig ist <b>{opts[c]}</b>." if isinstance(c, int) and 0 <= c < len(opts) else ""
    if typ == "logikgitter":
        optionen, r = t.get("optionen") or [], t.get("richtig")
        return f"Richtig ist <b>{optionen[r]}</b>." if isinstance(r, int) and 0 <= r < len(optionen) else ""
    if typ == "roboter":
        modus = t.get("modus")
        if modus == "ziel":
            return "Er hält auf dem grünen Feld."
        if modus == "programm":
            beispiel = (t.get("loesung") or {}).get("beispiel") or []
            return f"Ein möglicher Weg: {rob_worte(beispiel)}."
        loesung = t.get("loesung") or {}
        idx, ersatz = loesung.get("index"), loesung.get("ersatz")
        if not isinstance(idx, int) or ersatz not in ROB_WORT:
            return ""
        return f"Richtig ist Platz <b>{idx + 1}</b>: dort muss <b>{ROB_WORT[ersatz]}</b> stehen."
    if typ == "bildwahl":
        return "Das grün umrandete Bild ist richtig."
    if typ == "bildzahl":
        return f"Richtig ist <b>{fmt_num(t.get('a'))}</b>."
    if typ == "positionen":
        optionen, r = t.get("optionen") or [], t.get("richtig")
        if not isinstance(r, int) or not (0 <= r < len(optionen)):
            return ""
        namen, loesung = t.get("namen") or [], t.get("loesung") or []
        reihenfolge = " · ".join(namen[i] for i in loesung
                                  if isinstance(i, int) and 0 <= i < len(namen))
        return f"Richtig ist <b>{optionen[r]}</b>. Von links nach rechts: {reihenfolge}."
    return ""


# -------------------------------------------------------------- Der Korpus
def _lade_einheiten():
    daten = json.loads(UNITS.read_text("utf-8"))
    return daten.get("units", [])


def _statische_oberflaechentexte():
    """Feste Würfelfuchs-/Oberflächentexte OHNE jeden variablen Anteil — siehe
    die jeweiligen readBtn()-Aufrufe in src/app.html (gefNameHtml/gefTaufeHtml/
    gefNachfrageHtml/gefGrundGeben/gefBlaseHtml). Varianten von gefSpruch() mit
    einem Zähler (Serie, Rest bis Tagesziel) oder mit dem selbstgewählten
    Fuchs-/Spielernamen bleiben draußen — das sind genau die "zur Laufzeit
    dynamisch zusammengesetzten, variablen" Texte, für die der Laufzeit-
    Fallback (Systemstimme) gilt, kein vorproduzierter Clip."""
    fuchs_ohne_namen = "dein Fuchs"     # gefName()-Fallback, bevor der Fuchs getauft ist
    return [
        ("Bevor es losgeht: Wie heißt du?", "gef:name"),
        ("Hallo! Ich bin dein Würfelfuchs — ein schlauer Computer-Begleiter. "
         "Ich schaue dir beim Knobeln zu und freue mich mit dir. Wie soll ich heißen?",
         "gef:taufe"),
        ("Magst du mir kurz sagen, warum du aufgehört hast?", "gef:nachfrage"),
        ("Danke! Das merke ich mir.", "gef:dank"),
        (f"Hallo, ich bin {fuchs_ohne_namen}! "
         "Dein Tagesziel steht schon. Alles andere ist Zugabe!", "gef:gruss_ziel_erreicht"),
        (f"Hallo, ich bin {fuchs_ohne_namen}! Schön, dass du da bist!", "gef:gruss_ohne_namen"),
    ]


def sammle_korpus():
    """Alle Texte, die readBtn()/speak() in src/app.html vorlesen kann (bzw.
    laut Auftrag vorlesen könnte, siehe html_zu_sprechtext()) — dedupliziert
    über die Audio-ID. Taucht dieselbe ID mit unterschiedlichem Text auf, ist
    entweder ein echter crc32-Zusammenstoß passiert oder normalisiere() wurde
    inkonsistent verändert — beides ein harter Fehler, kein Weiterlaufen."""
    eintraege = {}   # id -> {"text":…, "quellen":[…]}

    def hinzu(text, quelle):
        text = str(text)
        if not normalisiere(text):
            return
        i = audio_id(text)
        vorhanden = eintraege.get(i)
        if vorhanden is None:
            eintraege[i] = {"text": text, "quellen": [quelle]}
            return
        if normalisiere(vorhanden["text"]) != normalisiere(text):
            raise SystemExit(
                f"crc32-Kollision bei Kennung {i}:\n  {vorhanden['text']!r}\n  {text!r}")
        if quelle not in vorhanden["quellen"]:
            vorhanden["quellen"].append(quelle)

    for u in _lade_einheiten():
        uid = f'{u.get("skill")}@{u.get("stage")}'
        for idx, t in enumerate(u.get("tasks") or []):
            typ, ort = t.get("type"), f"{uid}#{idx}"

            if typ == "logikgitter":
                # Kein "q" — Rahmengeschichte, Hinweise und Frage stattdessen
                # (siehe qLogikgitter()/logikVorlesetext() in src/app.html).
                rahmen = t.get("rahmen") or u.get("intro") or ""
                hinweise = " ".join(h.get("text", "") for h in (t.get("hinweise") or []))
                frage = t.get("frage_text") or ""
                if rahmen:
                    hinzu(rahmen, f"{ort}:rahmen")
                if hinweise:
                    hinzu(hinweise, f"{ort}:hinweise")
                if frage:
                    hinzu(frage, f"{ort}:frage_text")
                # Die automatische Gesamtvorlesung beim Erscheinen der Aufgabe
                # (mountSession() -> logikVorlesetext()) ist ein EIGENER Text.
                voll = " ".join(x for x in (rahmen, hinweise, frage) if x)
                if voll:
                    hinzu(voll, f"{ort}:logik_gesamt")
            elif typ == "positionen":
                # Wie logikgitter: kein "q" — Rahmen, Hinweise und Frage
                # stattdessen (siehe qPositionen()/positionenVorlesetext()).
                rahmen = t.get("rahmen") or u.get("intro") or ""
                hinweise = " ".join(h.get("text", "") for h in (t.get("hinweise") or []))
                frage = t.get("frage_text") or ""
                if rahmen:
                    hinzu(rahmen, f"{ort}:rahmen")
                if hinweise:
                    hinzu(hinweise, f"{ort}:hinweise")
                if frage:
                    hinzu(frage, f"{ort}:frage_text")
                # Die automatische Gesamtvorlesung beim Erscheinen der Aufgabe
                # (mountSession() -> positionenVorlesetext()) ist ein EIGENER Text.
                voll = positionen_vorlesetext(t)
                if voll:
                    hinzu(voll, f"{ort}:positionen_gesamt")
            else:
                q = t.get("q")
                if q:
                    hinzu(q, f"{ort}:q")
                if typ == "entdecken":
                    info = t.get("info")
                    if info:
                        hinzu(info, f"{ort}:info")
                if typ == "roboter":
                    # Wie bei logikgitter/positionen: die automatische
                    # Gesamtvorlesung (mountSession() -> roboterVorlesetext())
                    # ist ein EIGENER Text — bei modus "programm" identisch
                    # mit "q" (hinzu() dedupliziert das automatisch über die
                    # Audio-ID), sonst q + gesprochenes Programm.
                    vorlesetext = roboter_vorlesetext(t)
                    if vorlesetext:
                        hinzu(vorlesetext, f"{ort}:roboter_gesamt")

            # Feedbacksätze je Aufgabe — nicht für "Neu entdecken" (dort gibt
            # es keine Rückmeldung, siehe qEntdecken()). Siehe html_zu_sprech-
            # text() für den Vorbehalt, warum das heute noch kein Aufrufer
            # tatsächlich vorliest.
            if typ != "entdecken":
                loesung = _loesung_html(t)
                if loesung:
                    text = html_zu_sprechtext(loesung)
                    hinzu(f"{LOB[0]} {text}", f"{ort}:feedback_ok")
                    hinzu(f"{NOPE[0]} {text}", f"{ort}:feedback_falsch")

    # "Das hilft dir gleich bei …" (SESS.vorlaufFuer, siehe startUnit()/VIEWS.
    # session in src/app.html) — das Ziel ist ein beliebiger Lehrplan-Eintrag,
    # den der Tutor als "fuer" in seinen Plan schreibt, deshalb über den
    # gesamten (endlichen) Lehrplan statt nur über die aktuell erzeugten Pläne.
    for sk in C.SKILLS:
        hinzu(f"Das hilft dir gleich bei {sk['title']}", f"skill:{sk['id']}:vorlauf")

    for text, quelle in _statische_oberflaechentexte():
        hinzu(text, quelle)

    return [{"id": i, "text": e["text"], "quelle": "; ".join(e["quellen"])}
            for i, e in sorted(eintraege.items())]


def _schreibe_korpus(korpus):
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = KORPUS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(korpus, ensure_ascii=False, indent=1) + "\n", "utf-8")
    tmp.replace(KORPUS)          # erst fertig, dann sichtbar


# --------------------------------------------------------- Echtmodus (API)
def _pcm_zu_opus(pcm_bytes, ziel: Path):
    """PCM s16le/24kHz/mono -> Opus 32 kbit/s mono. Erst in eine Temp-Datei,
    dann umbenennen — ein Abbruch mit Strg-C darf keine halbe Datei an der
    endgültigen Stelle hinterlassen."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp_ziel = ziel.with_suffix(ziel.suffix + ".tmp")
    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as f:
        f.write(pcm_bytes)
        pcm_pfad = Path(f.name)
    try:
        subprocess.run(
            # "-f ogg" ausdrücklich: ffmpeg rät das Ausgabeformat sonst aus der
            # Dateiendung, und die heißt hier bewusst ".opus.tmp" (erst fertig,
            # dann umbenennen) — ".tmp" kennt es nicht und bricht ab.
            ["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(pcm_pfad),
             "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", str(tmp_ziel)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        tmp_ziel.replace(ziel)
    finally:
        pcm_pfad.unlink(missing_ok=True)
        if tmp_ziel.exists():
            tmp_ziel.unlink(missing_ok=True)


def _ist_behebbarer_fehler(e):
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code is None:
        # Netz-/Zeitüberschreitungsfehler der SDK tragen oft keinen Code —
        # im Zweifel wie ein 5xx behandeln und erneut versuchen.
        return True
    return code == 429 or 500 <= code < 600


def erzeuge_fehlende(stimme, korpus, schluessel):
    """Für eine Stimme jeden im Korpus noch fehlenden Clip erzeugen.
    Vorhandene Dateien werden übersprungen (inkrementell). Rückgabe: Liste
    der Fehlermeldungen zu endgültig gescheiterten Clips."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=schluessel)
    ziel_ordner = AUDIO_DIR / stimme
    ziel_ordner.mkdir(parents=True, exist_ok=True)

    fehler, neu, uebersprungen = [], 0, 0
    for eintrag in korpus:
        ziel = ziel_ordner / f"{eintrag['id']}.opus"
        if ziel.exists():
            uebersprungen += 1
            continue

        wartezeit = 10
        for versuch in range(1, 6):
            try:
                resp = client.models.generate_content(
                    model=MODELL,
                    contents=STIL_PRAEFIX + eintrag["text"],
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=GEMINI_STIMMENNAMEN[stimme]))),
                    ),
                )
                pcm = resp.candidates[0].content.parts[0].inline_data.data
                _pcm_zu_opus(pcm, ziel)
                neu += 1
                print(f"[OK] {stimme}/{eintrag['id']}.opus")
                break
            except KeyboardInterrupt:
                raise
            except Exception as e:  # noqa: BLE001 - Fehlerarten der SDK sind uns hier egal
                print(f"[!]  {stimme}/{eintrag['id']} Versuch {versuch}: "
                      f"{type(e).__name__}: {str(e)[:130]}")
                if versuch >= 5 or not _ist_behebbarer_fehler(e):
                    fehler.append(f"{stimme}/{eintrag['id']}: {e}")
                    break
                time.sleep(wartezeit)
                wartezeit *= 2
    print(f"  {stimme}: {neu} neu, {uebersprungen} schon vorhanden, {len(fehler)} gescheitert")
    return fehler


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trocken", action="store_true",
                     help="nur korpus.json schreiben, keine API-Aufrufe")
    ap.add_argument("--stimme", choices=STIMMEN, action="append",
                     help="nur diese Stimme(n) erzeugen (mehrfach angebbar; Standard: alle drei)")
    a = ap.parse_args()

    korpus = sammle_korpus()
    _schreibe_korpus(korpus)
    zeichen = sum(len(e["text"]) for e in korpus)
    print(f"Korpus: {len(korpus)} Einträge, {zeichen} Zeichen "
          f"(≈ {zeichen/15/60:.1f} Minuten Audio je Stimme bei 15 Zeichen/Sekunde)")
    print(f"-> {KORPUS}")

    if a.trocken:
        return 0
    sys.path.insert(0, str(ROOT))
    import konfig
    schluessel = konfig.wert("GEMINI_API_KEY")
    if not schluessel:
        print("Kein GEMINI_API_KEY (weder Umgebung noch .env) — "
              "bleibe im Trockenmodus.")
        return 0

    fehlerliste = []
    for stimme in (a.stimme or STIMMEN):
        fehlerliste += erzeuge_fehlende(stimme, korpus, schluessel)
    if fehlerliste:
        print(f"\n{len(fehlerliste)} Clips blieben trotz Wiederholung aus:")
        for f in fehlerliste:
            print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
