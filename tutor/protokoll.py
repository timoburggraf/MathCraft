# -*- coding: utf-8 -*-
"""Was der Tutor entschieden hat — und woran er es festgemacht hat.

Ein Programm, das dem Kind ungefragt Aufgaben zuteilt und wieder wegnimmt,
schuldet den Eltern Rechenschaft. Deshalb gilt hier eine harte Regel: Keine
Anpassung ohne Eintrag. Wer in der App eine Auswahl verändert, ruft dafür
protokolliere() auf — sonst ist die Anpassung ein Fehler, kein Merkmal.

Drei Quellen laufen hier zusammen:

  · die App          Pakete vorgezogen, zurückgestellt, übersprungen
  · der Erzeuger     neu erzeugte Pakete   (data/entscheidungen.jsonl)
  · der Prüfer       abgelehnte Pakete     (data/verworfen.json)

Herausgegeben wird nicht die Rohform, sondern je Eintrag ein deutscher Satz,
in dem die Zahlen stehen, auf denen die Entscheidung beruht.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import curriculum as C          # noqa: E402
import auswertung as A          # noqa: E402
import speicher as SP           # noqa: E402

PRIVATE_DATA = Path(os.environ.get("MC_STATE_HOME") or (Path.home() / ".local/share/mathcraft/private"))
ENTSCHEIDUNGEN = PRIVATE_DATA / "entscheidungen.jsonl"
VERWORFEN = PRIVATE_DATA / "verworfen.json"

ARTEN = {
    "vor":       "vorgezogen",
    "zurueck":   "zurückgestellt",
    "ueber":     "übersprungen",
    "neu":       "neu erzeugt",
    "abgelehnt": "vom Prüfer abgelehnt",
}

_TITEL = {s["id"]: s["title"] for s in C.SKILLS}


def titel(sid):
    return _TITEL.get(sid, sid or "?")


def _datum(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%d.%m.") if ms else "—"


def _quote(b):
    n, r = b.get("n", 0), b.get("c", 0)
    return f'{int(r)} von {int(n)} richtig ({r/n*100:.0f} %)' if n else "ohne Datengrundlage"


def _tutoreintrag(sid):
    """Der Planposten des Tutors zu einer Fertigkeit: sein eigener Begründungs-
    satz, und — falls dieser Posten selbst ein Vorlauf ist (D3, Feld "fuer") —
    die Ziel-Fertigkeit, für die er vorbereitet."""
    try:
        import lehrer as L
        p = L.lies_plan() or {}
        for e in p.get("plan") or []:
            if e.get("skill") == sid:
                return (e.get("grund") or "").strip(), (e.get("fuer") or "").strip()
    except Exception:
        pass
    return "", ""


# ------------------------------------------------------------------ Die Sätze

def satz(e):
    """Ein Eintrag als ein deutscher Satz, mit den Zahlen, auf denen er beruht."""
    d, b, t = e["art"], e.get("belege") or {}, titel(e.get("skill"))
    stufe = f' (Stufe {e["stufe"]})' if e.get("stufe") else ""
    grund = e.get("grund", "")

    if d == "ueber" and grund == "langweilig":
        stufe_txt = (f' und steht auf Leitner-Stufe {int(b["l"])}'
                     if isinstance(b.get("l"), (int, float)) else "")
        return (f'{t}{stufe} übersprungen — {_quote(b)}{stufe_txt}. Ab Leitner-Stufe '
                f'{A.LANGWEILIG_L} und {int(A.LANGWEILIG_QUOTE*100)} % gilt der Stoff als '
                f'gekonnt; noch eine Runde davon wäre Leerlauf.')
    if d == "zurueck" and grund == "zu_schwer":
        vorher = titel(b.get("vorher")) if b.get("vorher") else None
        nach = f' Zuerst kommt {vorher} dran.' if vorher else ""
        return (f'{t}{stufe} zurückgestellt — {_quote(b)}, das liegt unter der Schwelle '
                f'von {int(A.ZU_SCHWER_QUOTE*100)} %.{nach}')
    if d == "vor" and grund == "vorbedingung":
        wegen = titel(b.get("wegen")) if b.get("wegen") else "der schwerere Stoff"
        return (f'{t}{stufe} vorgezogen, weil {wegen} darauf aufbaut und dort '
                f'{_quote(b)} herauskam.')
    if d == "vor" and grund.startswith("wunsch"):
        art = {"wunsch_mehr": "du dir mehr davon gewünscht hast",
               "wunsch_jetzt": "du es nach vorn geholt hast"}.get(grund, "du es gewünscht hast")
        return f'{t}{stufe} vorgezogen, weil {art}.'
    if d == "ueber" and grund.startswith("wunsch"):
        art = {"wunsch_weniger": "du weniger davon wolltest",
               "wunsch_spaeter": "du es nach hinten gestellt hast"}.get(grund, "du es so wolltest")
        return f'{t}{stufe} übersprungen, weil {art}.'
    if d == "ueber" and grund == "typenmischung":
        return (f'{t}{stufe} übersprungen, weil zuletzt zu oft dieselbe Aufgabenart kam '
                f'({b.get("typ","?")}: {b.get("anteil",0)*100:.0f} % statt höchstens '
                f'{int(A.TYP_MAX*100)} %).')
    if d == "zurueck" and grund == "kein_vorrat":
        return (f'{t}{stufe} zurückgestellt — für diese Stufe gibt es noch kein Paket. '
                f'Der Erzeuger muss hier nachlegen.')
    if d == "neu":
        n = int(b.get("n", 1))
        return (f'{n} neue{"s" if n == 1 else ""} Paket{"" if n == 1 else "e"} für '
                f'{t}{stufe} erzeugt.')
    if grund == "tutor":
        # Der Tutor hat selbst entschieden. Sein eigener Satz steht im Plan;
        # hier wird er nachgeschlagen statt in eine Schablone gepresst — die
        # Begründung soll seine sein, nicht unsere.
        eigener, fuer = _tutoreintrag(e.get("skill"))
        wie = {"vor": "vorgezogen", "zurueck": "zurückgestellt",
               "ueber": "übersprungen"}.get(d, d)
        # D3: ist dieser Posten selbst ein Vorlauf, gehört das mit in den Satz —
        # sonst bliebe die Pre-Lesson-Kette (Ziel, Lücke, Vorlauf) unsichtbar.
        vorlauf = f' als Vorlauf für {titel(fuer)}' if fuer and fuer in _TITEL else ""
        return (f'{t}{stufe} {wie}{vorlauf} — der Tutor: „{eigener}“' if eigener
                else f'{t}{stufe} {wie}{vorlauf}, entschieden vom Tutor.')
    if d == "abgelehnt":
        versuche = int(b.get("versuche", 0))
        return (f'Ein Paket für {t}{stufe} hat der Prüfer abgelehnt — '
                f'{versuche} Versuch{"" if versuche == 1 else "e"}, keiner rechnete auf.')
    # Kein passender Satz: lieber die Rohform zeigen als die Entscheidung verschweigen.
    return f'{t}{stufe} {ARTEN.get(d, d)} ({grund or "ohne Begründung"}).'


# --------------------------------------------------------------- Die Quellen

def _aus_app():
    for e in SP.alle_ereignisse():
        if e.get("e") != "d":
            continue
        yield {"t": e.get("t", 0), "art": e.get("d", ""), "grund": e.get("w", ""),
               "skill": e.get("k", ""), "stufe": e.get("g", 0), "unit": e.get("u", ""),
               "belege": e.get("b") or {}, "quelle": "App"}


def _aus_erzeuger():
    if not ENTSCHEIDUNGEN.exists():
        return
    try:
        text = ENTSCHEIDUNGEN.read_text("utf-8")
    except OSError:
        return
    for zeile in text.splitlines():
        if not zeile.strip():
            continue
        try:
            e = json.loads(zeile)
        except ValueError:
            continue
        if isinstance(e, dict):
            yield {"t": e.get("t", 0), "art": e.get("art", ""), "grund": e.get("grund", ""),
                   "skill": e.get("skill", ""), "stufe": e.get("stufe", 0), "unit": "",
                   "belege": e.get("belege") or {}, "quelle": "Erzeuger"}


def _aus_verworfen():
    """Die Ablehnungen des Prüfers. ZIELE.md verlangt sie ausdrücklich auf der Seite.

    Die Datei kennt keinen Zeitpunkt; genommen wird ihr Änderungsdatum. Das ist
    ungenau und wird auf der Seite auch so gesagt.
    """
    if not VERWORFEN.exists():
        return
    try:
        liste = json.loads(VERWORFEN.read_text("utf-8"))
        stand = int(VERWORFEN.stat().st_mtime * 1000)
    except (ValueError, OSError):
        return
    if not isinstance(liste, list):
        return
    for e in liste:
        if not isinstance(e, dict):
            continue
        yield {"t": stand, "art": "abgelehnt", "grund": "pruefer",
               "skill": e.get("skill", ""), "stufe": e.get("stage", 0), "unit": "",
               "belege": {"versuche": len(e.get("log") or [])},
               "log": e.get("log") or [], "quelle": "Prüfer", "ungenau": True}


def eintraege(grenze=None):
    """Alle Entscheidungen, neueste zuerst."""
    alle = list(_aus_app()) + list(_aus_erzeuger()) + list(_aus_verworfen())
    alle.sort(key=lambda e: e["t"], reverse=True)
    return alle[:grenze] if grenze else alle


def zaehlung():
    """Je Art, wie oft. Für die Gegenprobe aus Z3."""
    z = {k: 0 for k in ARTEN}
    for e in eintraege():
        if e["art"] in z:
            z[e["art"]] += 1
    return z


def main():
    for e in eintraege(20):
        print(f'{_datum(e["t"])}  [{e["quelle"]:9s}] {satz(e)}')
    print("\n" + " · ".join(f"{ARTEN[k]}: {v}" for k, v in zaehlung().items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
