# -*- coding: utf-8 -*-
"""Ablage der Messdaten, die vom Handy kommen.

Ein Verzeichnis, eine Zeile je Ereignis. Kein Datenbankserver, kein Schema-
Migrationspfad — für ein Kind an einem Küchentisch wäre beides Ballast, und
eine Textdatei lässt sich noch in fünf Jahren mit den Augen lesen.

  data/telemetrie/<geraet>.jsonl    die Ereignisse
  data/telemetrie/<geraet>.json     Kopfdaten: bestätigte Nummer, Zählerstände,
                                     ggf. der Spielername
  data/telemetrie/wuensche.json     was die Eltern angefragt haben
  data/telemetrie/ignoriert.json    Geräte, die nicht mitzählen sollen

Zwei Eigenschaften sind hier wichtig und werden von build/sync_test.py geprüft:

  Doppelt schadet nicht. Jedes Ereignis trägt eine Nummer, die auf dem Gerät
  monoton hochzählt. Angenommen wird nur, was über der zuletzt bestätigten
  liegt. Schickt das Handy dieselbe Ladung zweimal, bleibt der Bestand gleich.

  Nur Bekanntes landet in einem Ereignis. Geschrieben wird je Ereignis
  ausschließlich, was unten in FELDER steht. Selbst wenn eine spätere Fassung
  der App aus Versehen mehr mitschickte, käme es hier nicht durch — in einem
  Ereignis (und damit in der .jsonl) hat kein Name etwas verloren, egal
  welcher.

  Eine einzige, bewusste Ausnahme (Elternwunsch vom 02.09.2026): den
  Spielernamen, den sich das Kind selbst gibt, schickt die App inzwischen als
  eigenes Feld neben den Ereignissen mit. Gesäubert und auf höchstens 18
  Zeichen gekürzt landet er einzig in den Kopfdaten (<geraet>.json) — nie in
  einem Ereignis, nie in der .jsonl. Der Avatar-Name des Würfelfuchses ist
  davon unberührt: Er ist reiner Spielspaß, bleibt strikt auf dem Gerät und
  erreicht logEvent()/syncNow() weiterhin nie.
"""
import json
import math
import os
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# MC_TELE hängt die Ablage woanders hin — der Test soll die echten Daten des
# Kindes nicht anfassen.
TELE = Path(os.environ.get("MC_TELE") or (ROOT / "data" / "telemetrie"))
WUENSCHE = TELE / "wuensche.json"
IGNORIERT = TELE / "ignoriert.json"

DEV_RE = re.compile(r"^[0-9a-f]{8,32}$")   # wird zum Dateinamen, also streng
MAX_EV = 5000                              # Ereignisse je Anfrage
MAX_TEXT = 40                              # Zeichen je Textfeld
MAX_NAME = 18                              # Zeichen für den Spielernamen — wie im Eingabefeld

# Was ein Ereignis je Art tragen darf. Alles andere wird verworfen.
FELDER = {
    "a": ("i", "t", "s", "u", "k", "g", "y", "o", "ms", "r", "h"),   # Antwort
    "n": ("i", "t", "s", "u", "k", "g", "ms"),                       # entdeckt
    "s": ("i", "t", "s", "q", "u", "n", "c", "ms", "z"),             # Sitzungsende
    "d": ("i", "t", "s", "d", "w", "u", "k", "g", "b"),              # Entscheidung
    "w": ("i", "t", "s", "z", "k", "wz"),                            # Wunsch erfüllt (Z4/A)
    "g": ("i", "t", "s", "u", "w"),                                  # Abbruchgrund (D6):
                                                                      # u Paket, w Grund 1..4 —
                                                                      # kein Freitext.
    "f": ("i", "t", "s", "u", "w"),                                  # Spaß-Signal (D6): u Paket,
                                                                      # w Bewertung 1..3 (1 nicht
                                                                      # gut, 2 ging so, 3 super) —
                                                                      # kein Freitext, höchstens
                                                                      # eins je Sitzung (App-Deckel).
}

MAX_OFFEN = 300     # so viele offene Paket-Ids je Gerät merkt sich der Dienst (D)

_lock = threading.Lock()
_cache = {"stand": None, "ereignisse": None}


# ------------------------------------------------------------------ Prüfung

def saeubere(ev):
    """Ein Ereignis auf die erlaubten Felder eindampfen. None heißt: unbrauchbar."""
    if not isinstance(ev, dict):
        return None
    art = ev.get("e")
    erlaubt = FELDER.get(art)
    if not erlaubt:
        return None
    nr = ev.get("i")
    if isinstance(nr, bool) or not isinstance(nr, int) or nr <= 0:
        return None
    zeit = ev.get("t")
    if isinstance(zeit, bool) or not isinstance(zeit, (int, float)) or not math.isfinite(zeit):
        return None

    out = {"e": art}
    for k in erlaubt:
        if k not in ev:
            continue
        v = ev[k]
        if isinstance(v, bool):
            out[k] = int(v)
        elif isinstance(v, str):
            out[k] = v[:MAX_TEXT]
        elif isinstance(v, (int, float)):
            if not math.isfinite(v):
                continue
            out[k] = int(v) if float(v).is_integer() else round(float(v), 3)
        elif isinstance(v, dict) and k == "b":
            # Belege einer Tutor-Entscheidung: Zahlen und kurze Kennungen wie
            # die Fertigkeit, auf die sie sich bezieht. Höchstens acht Stück.
            belege = {}
            for kk, vv in list(v.items())[:8]:
                if isinstance(vv, bool):
                    belege[str(kk)[:20]] = int(vv)
                elif isinstance(vv, (int, float)) and math.isfinite(vv):
                    belege[str(kk)[:20]] = vv
                elif isinstance(vv, str):
                    belege[str(kk)[:20]] = vv[:MAX_TEXT]
            out[k] = belege
    return out


def saeubere_name(wert):
    """Den Spielernamen für die Kopfdaten säubern: nur druckbare Zeichen, kein
    Steuerzeichen, vorn/hinten getrimmt, höchstens MAX_NAME Zeichen lang.

    Alles, was kein Text ist (fehlt, ist eine Zahl, ein Objekt …), ergibt "".
    Ein leerer Rückgabewert überschreibt nie einen bereits vorhandenen Namen —
    das entscheidet schreibe(), nicht diese Funktion.
    """
    if not isinstance(wert, str):
        return ""
    ohne_steuerzeichen = "".join(c for c in wert if c.isprintable())
    return ohne_steuerzeichen.strip()[:MAX_NAME]


# -------------------------------------------------------------------- Ablage

def _pfade(dev):
    return TELE / f"{dev}.jsonl", TELE / f"{dev}.json"


def kopf(dev):
    """Kopfdaten eines Geräts: bis wohin bestätigt, wie viel angekommen ist."""
    _, meta = _pfade(dev)
    if meta.exists():
        try:
            k = json.loads(meta.read_text("utf-8"))
            if isinstance(k, dict):
                return k
        except (ValueError, OSError):
            pass
    return {"ack": 0, "ereignisse": 0, "antworten_geraet": 0, "verfallen_geraet": 0,
            "zuletzt": 0}


# ------------------------------------------------------------- Welche Geräte

def ignorierte():
    """Geräte, die nicht mitzählen sollen — Testläufe, fremde Handys.

    Ein Testlauf hinterlässt echte Dateien; sein Zählerstand fließt sonst in
    die Gegenprobe ein und lässt die Elternseite Datenverlust melden, den es
    nicht gibt. Gelöscht wird deshalb nichts: Wer ein Gerät hier einträgt,
    nimmt es aus der Auswertung, ohne die Aufzeichnung wegzuwerfen.
    """
    if not IGNORIERT.exists():
        return set()
    try:
        d = json.loads(IGNORIERT.read_text("utf-8"))
    except (ValueError, OSError):
        return set()
    if isinstance(d, dict):
        d = d.get("geraete") or []
    return {x for x in d if isinstance(x, str) and DEV_RE.match(x)}


def ignoriert_setzen(dev, ja):
    """Ein Gerät aus der Auswertung nehmen oder wieder hereinholen."""
    if not DEV_RE.match(dev or ""):
        raise ValueError("unbrauchbare Geräte-Id")
    with _lock:
        liste = ignorierte()
        liste.add(dev) if ja else liste.discard(dev)
        TELE.mkdir(parents=True, exist_ok=True)
        IGNORIERT.write_text(json.dumps({"geraete": sorted(liste)},
                                        ensure_ascii=False, indent=1), "utf-8")
        _cache["stand"] = None
        return sorted(liste)


def geraete(alle=False):
    """Die gezählten Geräte — mit alle=True auch die ausgeblendeten."""
    if not TELE.exists():
        return []
    weg = set() if alle else ignorierte()
    return sorted(p.stem for p in TELE.glob("*.jsonl") if p.stem not in weg)


def schreibe(dev, ereignisse, stats, jetzt, name=""):
    """Neue Ereignisse anhängen. Gibt (ack, angenommen) zurück.

    Angenommen wird nur, was über der zuletzt bestätigten Nummer liegt. Damit
    ist ein zweiter Versuch mit derselben Ladung folgenlos.

    name ist der Spielername (Elternwunsch 02.09.2026) — ein Sync-Metadatum,
    kein Ereignisfeld. Er wird gesäubert und landet ausschließlich in den
    Kopfdaten. Ein leerer (oder unbrauchbarer) Name lässt einen dort bereits
    hinterlegten unangetastet.
    """
    if not DEV_RE.match(dev or ""):
        raise ValueError("unbrauchbare Geräte-Id")

    with _lock:
        TELE.mkdir(parents=True, exist_ok=True)
        log, meta = _pfade(dev)
        k = kopf(dev)
        ack = int(k.get("ack", 0))

        frisch = []
        for roh in ereignisse[:MAX_EV]:
            ev = saeubere(roh)
            if ev and ev["i"] > ack:
                frisch.append(ev)
        frisch.sort(key=lambda e: e["i"])

        if frisch:
            with log.open("a", encoding="utf-8") as f:
                for ev in frisch:
                    f.write(json.dumps(ev, ensure_ascii=False, separators=(",", ":")) + "\n")
            ack = frisch[-1]["i"]
            k["ereignisse"] = int(k.get("ereignisse", 0)) + len(frisch)

        k["ack"] = ack
        k["zuletzt"] = jetzt
        name_sauber = saeubere_name(name)
        if name_sauber:
            k["name"] = name_sauber
        if isinstance(stats, dict):
            # Was das Gerät selbst gezählt hat — der Gegenprobe zuliebe.
            for hier, dort in (("antworten_geraet", "answers"), ("verfallen_geraet", "lost")):
                v = stats.get(dort)
                if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
                    k[hier] = int(v)
            # D: der letzte gemeldete Offen-Stand (Unit-Ids mit stars<2) — nur
            # so weiß die Elternseite, ob ein Planposten "nicht stellbar" ist.
            offen = stats.get("offen")
            if isinstance(offen, list):
                k["offen"] = [x[:60] for x in offen if isinstance(x, str)][:MAX_OFFEN]
        meta.write_text(json.dumps(k, ensure_ascii=False, indent=1), "utf-8")
        _cache["stand"] = None

    # A: Ereignisse vom Typ "w" bestätigen einen erfüllten "jetzt"-Wunsch.
    # Außerhalb der Sperre, denn wunsch_erfuellen() sperrt selbst — _lock ist
    # nicht wiedereintrittsfest.
    # Ausgeblendete Geräte erfüllen dabei nichts: Ein Testlauf, der das
    # gewünschte Paket durchspielt, hakte sonst den für das Kind gedachten
    # Wunsch ab (so geschehen am 03.09.2026 durch den Emulator) — es zählt ja
    # auch sonst nicht mit.
    if dev not in ignorierte():
        for ev in frisch:
            if ev.get("e") == "w":
                wunsch_erfuellen(ev.get("z"), ev.get("k"), ev.get("wz"), jetzt)
    return ack, len(frisch)


def alle_ereignisse():
    """Alle Ereignisse aller gezählten Geräte, nach Zeit sortiert.

    Jedes Ereignis trägt sein Gerät in "dev" — daran hängt die Aufschlüsselung
    auf der Elternseite. Ausgeblendete Geräte kommen hier gar nicht erst vor.

    Gecacht über den Stand der Dateien; die Elternseite ruft das bei jedem
    Aufruf, und für 90 Tage Daten soll sie unter einer Sekunde bleiben.
    """
    if not TELE.exists():
        return []
    weg = ignorierte()
    stand = (tuple(sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size)
                          for p in TELE.glob("*.jsonl"))), tuple(sorted(weg)))
    if _cache["stand"] == stand:
        return _cache["ereignisse"]

    out = []
    for dev in geraete():
        out.extend(ereignisse_von(dev))
    out.sort(key=lambda e: (e.get("t", 0), e.get("i", 0)))
    _cache["stand"] = stand
    _cache["ereignisse"] = out
    return out


def ereignisse_von(dev):
    """Die Ereignisse eines einzelnen Geräts, auch eines ausgeblendeten."""
    out = []
    try:
        text = (TELE / f"{dev}.jsonl").read_text("utf-8")
    except OSError:
        return out
    for zeile in text.splitlines():
        if not zeile.strip():
            continue
        try:
            ev = json.loads(zeile)
        except ValueError:
            continue              # eine kaputte Zeile kostet ein Ereignis, nicht die Seite
        if isinstance(ev, dict):
            ev["dev"] = dev
            out.append(ev)
    return out


def zaehlstand():
    """Was die Geräte gezählt haben gegen das, was hier liegt — für Z1."""
    hier_a = sum(1 for e in alle_ereignisse() if e.get("e") == "a")
    dort_a = sum(int(kopf(d).get("antworten_geraet", 0)) for d in geraete())
    return {"antworten_hier": hier_a, "antworten_geraete": dort_a,
            "abweichung": hier_a - dort_a,
            "verfallen": sum(int(kopf(d).get("verfallen_geraet", 0)) for d in geraete()),
            "geraete": len(geraete())}


def geraetestand():
    """Je Gerät eine Zeile — für den Technikteil der Elternseite.

    Auch die ausgeblendeten stehen hier, sonst wüsste niemand mehr, dass es sie
    gibt, und die Zahl der Antworten auf der Seite bliebe unerklärt.
    """
    out = []
    weg = ignorierte()
    for dev in geraete(alle=True):
        ev = ereignisse_von(dev)
        k = kopf(dev)
        antworten = [e for e in ev if e.get("e") == "a"]
        out.append({
            "dev": dev,
            "name": str(k.get("name") or ""),
            "gezaehlt": dev not in weg,
            "antworten": len(antworten),
            "gemeldet": int(k.get("antworten_geraet", 0)),
            "ereignisse": len(ev),
            "erste": ev[0].get("t", 0) if ev else 0,
            "zuletzt": int(k.get("zuletzt", 0)),
        })
    return sorted(out, key=lambda g: (-g["antworten"], g["dev"]))


def offene_pakete():
    """D: Unit-Ids, die laut dem zuletzt gemeldeten Gerätestand noch offen sind
    (stars<2) — vereinigt über alle mitzählenden Geräte. Daran erkennt die
    Elternseite, ob es zu einer Fertigkeit überhaupt noch etwas zu stellen
    gibt, oder ob sie "nicht stellbar" ist, weil alle Pakete schon zweimal
    saßen.
    """
    out = set()
    for dev in geraete():
        offen = kopf(dev).get("offen")
        if isinstance(offen, list):
            out.update(x for x in offen if isinstance(x, str))
    return out


# ------------------------------------------------------------------ Wünsche

def wuensche_lesen():
    if not WUENSCHE.exists():
        return []
    try:
        w = json.loads(WUENSCHE.read_text("utf-8"))
        return w if isinstance(w, list) else []
    except (ValueError, OSError):
        return []


def wuensche_schreiben(liste):
    with _lock:
        TELE.mkdir(parents=True, exist_ok=True)
        WUENSCHE.write_text(json.dumps(liste, ensure_ascii=False, indent=1), "utf-8")


ARTEN = ("mehr", "weniger", "jetzt", "spaeter")
MAX_WUENSCHE = 20


def wunsch_setzen(ziel, kennung, art, jetzt, titel=""):
    """Einen Wunsch ablegen. Ein zweiter zum selben Ziel ersetzt den ersten.

    Ein Wunsch ohne Zeitpunkt wäre wertlos — an ihm hängt die Aussage, was
    seither passiert ist. Deshalb bekommt jeder einen.
    """
    if ziel not in ("skill", "bereich") or art not in ARTEN or not kennung:
        raise ValueError("unbrauchbarer Wunsch")
    liste = [w for w in wuensche_lesen()
             if not (w.get("ziel") == ziel and w.get("id") == kennung)]
    liste.append({"ziel": ziel, "id": kennung, "art": art, "t": jetzt, "titel": titel})
    liste = liste[-MAX_WUENSCHE:]
    wuensche_schreiben(liste)
    return liste


def wunsch_loeschen(ziel, kennung):
    liste = [w for w in wuensche_lesen()
             if not (w.get("ziel") == ziel and w.get("id") == kennung)]
    wuensche_schreiben(liste)
    return liste


def wunsch_erfuellen(ziel, kennung, wunsch_zeit, jetzt):
    """A: Ein "jetzt"-Wunsch gilt als erfüllt, sobald das Gerät ein "w"-Ereignis
    dazu meldet — ein Paket der gewünschten Fertigkeit wurde vollständig
    gespielt. Der Zeitstempel identifiziert den genauen Wunsch: Wurde er
    inzwischen durch einen neuen ersetzt oder zurückgenommen, passiert nichts.
    Doppelte Ereignisse sind folgenlos, weil hier nur noch einmal derselbe
    Status gesetzt wird.
    """
    with _lock:
        liste = wuensche_lesen()
        geaendert = False
        for w in liste:
            if (w.get("ziel") == ziel and w.get("id") == kennung
                    and w.get("t") == wunsch_zeit and w.get("art") == "jetzt"
                    and w.get("status") != "erfuellt"):
                w["status"] = "erfuellt"
                w["erfuellt_am"] = jetzt
                geaendert = True
        if geaendert:
            TELE.mkdir(parents=True, exist_ok=True)
            WUENSCHE.write_text(json.dumps(liste, ensure_ascii=False, indent=1), "utf-8")
