# -*- coding: utf-8 -*-
"""Rechnet die Ereignisse vom Handy in Aussagen um, die Eltern etwas sagen.

Alle Schwellen stehen hier oben und nirgendwo sonst. Sie stammen aus ZIELE.md;
wer sie ändert, ändert damit auch, was auf der Elternseite als "sitzt" gilt —
deshalb werden sie dort im Klartext neben jede Zahl geschrieben. Eine Kennzahl,
deren Definition man erst suchen muss, ist keine.

  .venv/bin/python tutor/auswertung.py     # kurzer Überblick auf der Kommandozeile
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import curriculum as C           # noqa: E402
import disziplinen as DZ         # noqa: E402
import speicher as SP            # noqa: E402

# ------------------------------------------------------- Schwellen aus ZIELE.md
SITZT_N, SITZT_QUOTE = 10, 0.90          # Z2: ab hier gilt eine Fertigkeit als sicher
HAKT_N, HAKT_QUOTE = 6, 0.50             # Z2: ab hier hakt sie
HAKT_SERIE = 3                           # Z2: oder drei Fehlversuche hintereinander
LANGWEILIG_QUOTE, LANGWEILIG_N, LANGWEILIG_L = 0.90, 10, 4   # Z5
ZU_SCHWER_QUOTE, ZU_SCHWER_N = 0.40, 6      # Z5
BAND_UNTEN, BAND_OBEN = 0.70, 0.85          # Z5: das Zielband
KURZE_SITZUNG = 5                           # Z5: darunter gilt sie als abgebrochen
TYP_MAX = 0.35                              # Z5: kein Aufgabentyp darüber
WOCHEN = 8                                  # Z2: so weit reicht der Verlauf zurück

ZUSTAND_TEXT = {
    "sitzt":      "sitzt",
    "hakt":       "hakt",
    "arbeit":     "in Arbeit",
    "unberuehrt": "noch nicht geübt",
}

DEFINITION = {
    "sitzt":  f"mindestens {SITZT_N} Antworten und mindestens {int(SITZT_QUOTE*100)} % davon richtig",
    "hakt":   f"mindestens {HAKT_N} Antworten und höchstens {int(HAKT_QUOTE*100)} % richtig, "
              f"oder {HAKT_SERIE} Fehlversuche hintereinander",
    "arbeit": "schon geübt, aber noch keine der beiden Schwellen erreicht",
    "unberuehrt": "noch keine einzige Antwort",
}

# D6: Nordstern ist die Motivation, nicht mehr nur die Trefferquote.
NULLNULL_FENSTER = 25       # ZIELE-V2.md: Anteil der 0/0-Sitzungen unter den letzten 25
WOCHEN_MOTIVATION = 4       # so weit reicht der Wochenmengen-Trend im Tutor-Auszug zurück

GRUND_TEXT = {1: "zu lange gedauert", 2: "zu langweilig", 3: "zu schwer",
              4: "wollte etwas anderes machen"}
SPASS_TEXT = {1: "nicht gut", 2: "ging so", 3: "super"}


def _quote(richtig, n):
    return (richtig / n) if n else 0.0


def _wochenstart(ms):
    d = datetime.fromtimestamp(ms / 1000).date()
    return d - timedelta(days=d.weekday())


# ------------------------------------------------------------------ Fertigkeiten

def fertigkeiten(ereignisse=None):
    """Jede der Fertigkeiten des Lehrplans mit ihrem Zustand — ohne Lücken.

    Auch was nie gespielt wurde, kommt vor. Eine Fertigkeit, die auf der Seite
    fehlt, wäre ein blinder Fleck, und blinde Flecken sind der Grund, warum es
    diese Seite gibt.
    """
    ev = alle_antworten(ereignisse)
    je = {}
    for e in ev:
        k = e.get("k")
        if not k:
            continue
        d = je.setdefault(k, {"n": 0, "richtig": 0, "letzte": 0, "folge": []})
        d["n"] += 1
        d["richtig"] += 1 if e.get("o") else 0
        d["letzte"] = max(d["letzte"], e.get("t", 0))
        d["folge"].append(1 if e.get("o") else 0)

    out = []
    for s in C.SKILLS:
        d = je.get(s["id"], {"n": 0, "richtig": 0, "letzte": 0, "folge": []})
        n, richtig = d["n"], d["richtig"]
        letzte3 = d["folge"][-HAKT_SERIE:]
        serie_aus = len(letzte3) == HAKT_SERIE and not any(letzte3)

        # Reihenfolge mit Absicht: Wer insgesamt gut dasteht, zuletzt aber
        # dreimal danebenlag, braucht Aufmerksamkeit — nicht ein Lob.
        if n == 0:
            zustand = "unberuehrt"
        elif (n >= HAKT_N and _quote(richtig, n) <= HAKT_QUOTE) or serie_aus:
            zustand = "hakt"
        elif n >= SITZT_N and _quote(richtig, n) >= SITZT_QUOTE:
            zustand = "sitzt"
        else:
            zustand = "arbeit"

        out.append({
            "id": s["id"], "titel": s["title"], "bereich": s["area"], "stufe": s["stage"],
            "n": n, "richtig": richtig, "quote": _quote(richtig, n),
            "letzte": d["letzte"], "serie_aus": serie_aus, "zustand": zustand,
        })
    return out


def alle_antworten(ereignisse=None):
    ev = SP.alle_ereignisse() if ereignisse is None else ereignisse
    return [e for e in ev if e.get("e") == "a"]


def bereiche(fert=None):
    """Je Welt zusammengefasst, in der Reihenfolge des Lehrplans."""
    fert = fert if fert is not None else fertigkeiten()
    je = {a["id"]: {"id": a["id"], "titel": a["title"], "emoji": a["emoji"],
                    "n": 0, "richtig": 0, "sitzt": 0, "hakt": 0,
                    "arbeit": 0, "unberuehrt": 0, "fertigkeiten": 0}
          for a in C.AREAS}
    for f in fert:
        b = je.get(f["bereich"])
        if not b:
            continue
        b["n"] += f["n"]
        b["richtig"] += f["richtig"]
        b[f["zustand"]] += 1
        b["fertigkeiten"] += 1
    for b in je.values():
        b["quote"] = _quote(b["richtig"], b["n"])
    return [je[a["id"]] for a in C.AREAS]


# ----------------------------------------------------------------- Verlauf

def verlauf(wochen=WOCHEN, ereignisse=None):
    """Trefferquote je Bereich über die letzten Wochen, Woche für Woche."""
    ev = alle_antworten(ereignisse)
    bereich_von = {s["id"]: s["area"] for s in C.SKILLS}

    heute = date.today()
    start = heute - timedelta(days=heute.weekday()) - timedelta(weeks=wochen - 1)
    labels = [start + timedelta(weeks=i) for i in range(wochen)]
    leer = {w: {"n": 0, "richtig": 0} for w in labels}

    je = {a["id"]: {w: dict(v) for w, v in leer.items()} for a in C.AREAS}
    gesamt = {w: dict(v) for w, v in leer.items()}
    for e in ev:
        w = _wochenstart(e.get("t", 0))
        if w not in leer:
            continue
        aid = bereich_von.get(e.get("k"))
        ziele = [gesamt] + ([je[aid]] if aid in je else [])
        for z in ziele:
            z[w]["n"] += 1
            z[w]["richtig"] += 1 if e.get("o") else 0

    def reihe(d):
        return [{"woche": w.isoformat(), "n": d[w]["n"], "richtig": d[w]["richtig"],
                 "quote": _quote(d[w]["richtig"], d[w]["n"])} for w in labels]

    return {"wochen": [w.isoformat() for w in labels], "gesamt": reihe(gesamt),
            "bereiche": {a["id"]: reihe(je[a["id"]]) for a in C.AREAS}}


# ------------------------------------------------------------------ Sitzungen

def sitzungen(ereignisse=None):
    ev = SP.alle_ereignisse() if ereignisse is None else ereignisse
    out = []
    for e in ev:
        if e.get("e") != "s":
            continue
        n, c = e.get("n", 0) or 0, e.get("c", 0) or 0
        out.append({"t": e.get("t", 0), "n": n, "richtig": c, "quote": _quote(c, n),
                    "abgebrochen": bool(e.get("z")), "anlass": e.get("q", ""),
                    "ms": e.get("ms", 0)})
    return out


def nordstern(ereignisse=None):
    """Der Kernwert aus Z5: Wie oft lag eine Sitzung im Zielband?

    Zu leicht ist genauso ein Fehler wie zu schwer. Zwischen 70 und 85 Prozent
    richtig ist die Zone, in der ein Kind arbeitet statt sich zu langweilen
    oder aufzugeben. Sitzungen mit zu wenigen Antworten zählen nicht mit —
    aus drei Aufgaben lässt sich keine Quote ablesen.
    """
    s = [x for x in sitzungen(ereignisse) if x["n"] >= KURZE_SITZUNG]
    alle = sitzungen(ereignisse)
    im_band = [x for x in s if BAND_UNTEN <= x["quote"] <= BAND_OBEN]
    kurz = [x for x in alle if x["n"] < KURZE_SITZUNG]
    return {
        "sitzungen": len(alle), "gewertet": len(s), "im_band": len(im_band),
        "anteil": (len(im_band) / len(s)) if s else 0.0,
        "zu_leicht": sum(1 for x in s if x["quote"] > BAND_OBEN),
        "zu_schwer": sum(1 for x in s if x["quote"] < BAND_UNTEN),
        "kurz": len(kurz),
        "anteil_kurz": (len(kurz) / len(alle)) if alle else 0.0,
    }


def typenmischung(ereignisse=None):
    ev = alle_antworten(ereignisse)
    je = {}
    for e in ev:
        je[e.get("y", "?")] = je.get(e.get("y", "?"), 0) + 1
    n = sum(je.values())
    return sorted(({"typ": t, "n": v, "anteil": v / n if n else 0.0}
                   for t, v in je.items()), key=lambda x: -x["n"])


def vorratsdeckung():
    """Fertigkeiten, für die es kein einziges Paket gibt — Z5 verlangt hier null."""
    import json
    datei = ROOT / "data" / "units_seed.json"
    vorhanden = set()
    if datei.exists():
        try:
            for u in json.loads(datei.read_text("utf-8")).get("units", []):
                vorhanden.add(u.get("skill"))
        except (ValueError, OSError):
            pass
    fehlend = [s for s in C.SKILLS if s["id"] not in vorhanden]
    return {"gesamt": len(C.SKILLS), "unversorgt": len(fehlend),
            "liste": [{"id": s["id"], "titel": s["title"], "stufe": s["stage"],
                       "bereich": s["area"]} for s in fehlend]}


def aktuelle_stufe(ereignisse=None):
    """Auf welcher Stufe das Kind gerade wirklich steht.

    Genommen wird die höchste Stufe, auf der es mindestens HAKT_N Antworten
    gegeben hat und dabei nicht unter die Hakt-Schwelle gefallen ist. Was er
    einmal probiert und sofort verrissen hat, zählt also nicht als „erreicht“.
    """
    ev = alle_antworten(ereignisse)
    je = {}
    for e in ev:
        g = int(e.get("g") or 0)
        if not g:
            continue
        d = je.setdefault(g, [0, 0])
        d[0] += 1
        d[1] += 1 if e.get("o") else 0
    erreicht = [g for g, (n, r) in je.items() if n >= HAKT_N and _quote(r, n) > HAKT_QUOTE]
    return max(erreicht) if erreicht else 1


def wunsch_wirkung(w, ereignisse=None):
    """Was seit einem Wunsch tatsächlich geübt wurde — in Zahlen, nicht in Worten."""
    ev = alle_antworten(ereignisse)
    bereich_von = {s["id"]: s["area"] for s in C.SKILLS}
    seit = w.get("t", 0)
    treffer = [e for e in ev if e.get("t", 0) >= seit and (
        e.get("k") == w.get("id") if w.get("ziel") == "skill"
        else bereich_von.get(e.get("k")) == w.get("id"))]
    richtig = sum(1 for e in treffer if e.get("o"))
    return {"n": len(treffer), "richtig": richtig, "quote": _quote(richtig, len(treffer)),
            "seit": seit}


def uebungstage(ereignisse=None):
    """An wie vielen verschiedenen Tagen überhaupt geübt wurde.

    Der Unterschied zwischen 160 Aufgaben an einem Tag und 160 über vier Wochen
    ist der Unterschied zwischen einer Momentaufnahme und einem Verlauf. Wer das
    nicht danebenschreibt, lässt die Seite mehr behaupten, als sie weiß.
    """
    return sorted({datetime.fromtimestamp(e.get("t", 0) / 1000).strftime("%Y-%m-%d")
                   for e in alle_antworten(ereignisse) if e.get("t")})


def _skill_von_unit():
    """Paket-Id ("skill@stufe") -> Fertigkeit — die Umkehrung dessen, was ein
    Paket über sich selbst weiß. Ein "f"- oder "g"-Ereignis trägt nur die
    Paket-Id (u), keine Fertigkeit — wer wissen will, zu welcher Denkdisziplin
    ein Spaß-Signal oder ein Abbruchgrund gehört, braucht diese Abbildung.
    """
    je = {}
    datei = ROOT / "data" / "units_seed.json"
    if datei.exists():
        try:
            import json
            for u in json.loads(datei.read_text("utf-8")).get("units", []):
                sk, stufe = u.get("skill"), u.get("stage")
                if sk and stufe is not None:
                    je[f"{sk}@{stufe}"] = sk
        except (ValueError, OSError):
            pass
    return je


def wochenmenge(wochen=WOCHEN_MOTIVATION, ereignisse=None):
    """D6a: Antworten je Woche für die letzten `wochen` Wochen, insgesamt —
    der Wochenmengen-Trend, den ZIELE-V2.md als Nordstern-Größe nennt."""
    v = verlauf(wochen=wochen, ereignisse=ereignisse)
    return v["gesamt"]


def sofort_abbrueche_anteil(ereignisse=None, n=NULLNULL_FENSTER):
    """D6b: Anteil der 0/0-Sitzungen (Paket geöffnet, sofort weggetippt, keine
    einzige Antwort) an den letzten `n` Sitzungen."""
    s = sitzungen(ereignisse)[-n:]
    nullnull = sum(1 for x in s if x["n"] == 0 and x["richtig"] == 0)
    return {"anzahl": nullnull, "von": len(s), "anteil": (nullnull / len(s)) if s else 0.0}


def sofort_abbrueche_je_paket(ereignisse=None, seit=0):
    """D6c: je Paket-Id die Zahl der Sofort-Abbrüche (0 Antworten) seit `seit`
    — meist der Zeitpunkt des letzten Tutorplans. Ohne das sieht der Tutor
    nur, dass ein Paket weiterhin ungeübt ist, nicht, dass es dreimal
    geöffnet und sofort wieder verlassen wurde."""
    ev = SP.alle_ereignisse() if ereignisse is None else ereignisse
    je = {}
    for e in ev:
        if e.get("e") != "s" or (e.get("t") or 0) < seit or int(e.get("n") or 0) != 0:
            continue
        u = e.get("u")
        if u:
            je[u] = je.get(u, 0) + 1
    return je


def abbruchgruende(ereignisse=None, n=20):
    """D6d: die zuletzt genannten Abbruchgründe aus "g"-Ereignissen im
    Klartext, mit Paket-Id und Zeitpunkt — neueste zuerst."""
    ev = SP.alle_ereignisse() if ereignisse is None else ereignisse
    out = []
    for e in ev:
        if e.get("e") != "g":
            continue
        grund = int(e.get("w") or 0)
        out.append({"t": e.get("t", 0), "unit": e.get("u", ""),
                    "grund": grund, "text": GRUND_TEXT.get(grund, "unbekannt")})
    out.sort(key=lambda x: -x["t"])
    return out[:n]


def spass_verteilung(ereignisse=None):
    """D6e: Verteilung der Spaß-Signale ("f"-Ereignisse), gesamt und je
    Denkdisziplin (Zuordnung über disziplinen.disziplin_von, anhand der
    Fertigkeit des jeweiligen Pakets)."""
    ev = SP.alle_ereignisse() if ereignisse is None else ereignisse
    skill_von_unit = _skill_von_unit()
    gesamt = {1: 0, 2: 0, 3: 0}
    je_disziplin = {}
    for e in ev:
        if e.get("e") != "f":
            continue
        w = int(e.get("w") or 0)
        if w not in gesamt:
            continue
        gesamt[w] += 1
        sk = skill_von_unit.get(e.get("u") or "")
        dz = DZ.disziplin_von(sk) if sk else None
        if dz:
            je_disziplin.setdefault(dz, {1: 0, 2: 0, 3: 0})
            je_disziplin[dz][w] += 1
    return {"gesamt": gesamt, "n": sum(gesamt.values()), "je_disziplin": je_disziplin}


def disziplinen_uebersicht(ereignisse=None):
    """Elternseite/D6: Antworten und Trefferquote je Denkdisziplin, aus den
    Fertigkeiten aggregiert (disziplinen.disziplin_von)."""
    fert = fertigkeiten(ereignisse)
    je = {key: {"n": 0, "richtig": 0} for key in DZ.DISZIPLINEN}
    for f in fert:
        dz = DZ.disziplin_von(f["id"])
        if dz:
            je[dz]["n"] += f["n"]
            je[dz]["richtig"] += f["richtig"]
    out = []
    for key, angaben in DZ.DISZIPLINEN.items():
        n, r = je[key]["n"], je[key]["richtig"]
        out.append({"id": key, "titel": angaben["titel"], "n": n, "richtig": r,
                    "quote": _quote(r, n)})
    return out


def motivationslage(ereignisse=None, seit_plan=0):
    """D6: alles, was der Tutor über die Motivation des Kindes braucht, kompakt
    aus den vorhandenen Ereignissen berechnet (ZIELE-V2.md, Abschnitt D6) —
    Wochenmenge, 0/0-Sitzungen, Sofort-Abbrüche je Paket seit dem letzten
    Plan, Abbruchgründe im Klartext, Spaß-Signale gesamt und je Disziplin.
    """
    ev = SP.alle_ereignisse() if ereignisse is None else ereignisse
    return {
        "wochenmenge": wochenmenge(WOCHEN_MOTIVATION, ev),
        "nullnull": sofort_abbrueche_anteil(ev),
        "abbrueche_je_paket": sofort_abbrueche_je_paket(ev, seit_plan),
        "abbruchgruende": abbruchgruende(ev),
        "spass": spass_verteilung(ev),
    }


def ueberblick(ereignisse=None):
    """Alles, was die Elternseite braucht, in einem Rutsch.

    ereignisse=None wertet wie bisher alle mitzählenden Geräte gemeinsam aus.
    Wird eine Liste übergeben — die Elternseite tut das mit
    speicher.ereignisse_von(dev) für die spielerspezifische Ansicht
    (Elternwunsch 03.09.2026) —, gilt nur sie. Vorrat, Zählstand und
    Gerätetabelle bleiben davon unberührt: Sie werden hier unten weiterhin
    ohne ereignisse-Parameter erhoben, weil sie geräteübergreifend gelten.
    """
    ev = SP.alle_ereignisse() if ereignisse is None else ereignisse
    ant = alle_antworten(ev)
    fert = fertigkeiten(ev)
    return {
        "ereignisse": len(ev),
        "antworten": len(ant),
        "richtig": sum(1 for e in ant if e.get("o")),
        "quote": _quote(sum(1 for e in ant if e.get("o")), len(ant)),
        "von": min((e.get("t", 0) for e in ev), default=0),
        "bis": max((e.get("t", 0) for e in ev), default=0),
        "tage": uebungstage(ev),
        "stufe": aktuelle_stufe(ev),
        "fertigkeiten": fert,
        "bereiche": bereiche(fert),
        "verlauf": verlauf(WOCHEN, ev),
        "nordstern": nordstern(ev),
        "sitzungen": sitzungen(ev),
        "typen": typenmischung(ev),
        "vorrat": vorratsdeckung(),
        "zaehlstand": SP.zaehlstand(),
        "geraete": SP.geraetestand(),
        "motivation": motivationslage(ev),
        "disziplinen": disziplinen_uebersicht(ev),
    }


def main():
    u = ueberblick()
    print(f'{u["antworten"]} Antworten, {u["quote"]*100:.0f} % richtig, '
          f'{u["ereignisse"]} Ereignisse')
    z = {k: 0 for k in ZUSTAND_TEXT}
    for f in u["fertigkeiten"]:
        z[f["zustand"]] += 1
    print("  " + " · ".join(f'{ZUSTAND_TEXT[k]}: {v}' for k, v in z.items()))
    n = u["nordstern"]
    print(f'  Zielband: {n["im_band"]}/{n["gewertet"]} Sitzungen ({n["anteil"]*100:.0f} %), '
          f'{n["kurz"]} abgebrochen')
    print(f'  Vorrat: {u["vorrat"]["unversorgt"]} von {u["vorrat"]["gesamt"]} '
          f'Fertigkeiten ohne Paket')
    return 0


if __name__ == "__main__":
    sys.exit(main())
