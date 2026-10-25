# -*- coding: utf-8 -*-
"""Die Aufgabenbank des Denk-Checks (ZIELE-V3.md, G4) → data/denkcheck.json.

Der Denk-Check misst neun Dimensionen (nach Käpnick) mit je 4 adaptiven
Aufgaben. Die Aufgaben kommen nicht aus einem Sprachmodell, sondern aus den
deterministischen Kernen — jede ist lösbar, eindeutig und mit nachweislich
falschen Ablenkern gebaut — und jede einzelne läuft vor dem Schreiben durch
validate.check_task bei ihrer EIGENEN Stufe. Fehlt für eine Dimension und Stufe
auch nur eine Aufgabe, bricht das Programm laut ab: ein Check mit Lücken wäre
keiner.

  .venv/bin/python build/denkcheck_bank.py

Je Dimension und Stufe 2…8 genau drei Aufgaben (id = <dim>-<stufe>-<nr>, nr 1…3),
also 9 × 7 × 3 = 189. Bei Wiederholung des Checks werden unbenutzte bevorzugt
(das entscheidet die App). Aufgaben sind neutral: keine Themenwelt, keine
Geschichten, Fragetexte so kurz wie möglich ("alles vorgelesen", möglichst
ohne Lesen).

Seeds ausschließlich über zlib.crc32 von Text — kein hash(), kein eval(), kein
Sprachmodell. Gleicher Aufruf, gleiche Datei.
"""
import json
import random
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum as C
import validate as V
import validate_v2 as V2
import algo_kern as AK
import figur_kern as FK
import grafik_kern as GK
import kern_pakete as KP
import legen_kern as LK
import muster_kern as MK
import rechen_kern as RK

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "denkcheck.json"

STUFEN = range(2, 9)       # 2…8, siehe ZIELE-V3.md (sonst käme ein starkes Kind nie oben an)
JE_STUFE = 3               # Aufgaben je Dimension und Stufe
MAX_BYTES = 1024 * 1024    # Obergrenze laut ZIELE-V3.md
VERSUCHE = 400             # Seeds, die je Aufgabe ausprobiert werden
KALKUEL_BUDGET = 6         # D2: höchstens sechs elementare Rechenschritte

# Reihenfolge = Tabelle in ZIELE-V3.md, G4. `kaepnick` ist das Merkmal aus dem
# Merkmalssystem mathematisch begabter Grundschulkinder; algorithmik ist eine
# eigene V2-Disziplin ohne Käpnick-Merkmal (null).
DIMENSIONEN = {
    "strukturen": dict(titel="Muster und Strukturen", runde="A", boden="muster",
                       kaepnick="Strukturen erkennen und nutzen"),
    "schlussketten": dict(titel="Schlussfolgern", runde="A", boden="logik",
                          kaepnick="Mit Komplexität umgehen"),
    "algorithmik": dict(titel="Befehle und Abläufe", runde="A", boden="algorithmik",
                        kaepnick=None),
    "darstellung": dict(titel="Bilder in Zahlen", runde="A", boden=None,
                        kaepnick="Wechsel der Repräsentationsebenen"),
    "raum": dict(titel="Formen im Kopf", runde="A", boden="raum",
                 kaepnick="Räumliches Vorstellungsvermögen"),
    "umkehren": dict(titel="Rückwärts denken", runde="B", boden=None,
                     kaepnick="Umkehrbarkeit von Gedankengängen"),
    "merken": dict(titel="Bilder merken", runde="B", boden=None,
                   kaepnick="Speichern mit Hilfe erkannter Strukturen"),
    "systematik": dict(titel="Alles durchprobieren", runde="B", boden="kombinatorik",
                       kaepnick="Systematisches Probieren"),
    "rechnen": dict(titel="Rechnen", runde="B", boden=None,
                    kaepnick="Schulstoff-Anker"),
}


class Neu(Exception):
    """Dieser Versuch taugt nichts (Kern lehnt ab, Form passt nicht): nächster Seed."""


def _seed(dim, stufe, nr, versuch):
    return zlib.crc32(f"denkcheck|{dim}|{stufe}|{nr}|{versuch}".encode("utf-8"))


def _welt(nr):
    """Themenwelt nur für die Rollennamen der Positionsrätsel; rotiert über nr."""
    return C.WORLD_IDS[(nr * 3) % len(C.WORLD_IDS)]


# ============================================================ die Dimensionen
# Jeder Bauer: (stufe, nr, seed) -> Aufgabe, oder Neu/ValueError für "nächster Seed".

# --- strukturen: Bildmatrix (2-5), Analogie (6-8). muster_kern kennt Matrix nur
# für seine Stufen 4 und 5 (zwei bzw. drei variierende Merkmale) und Analogie nur
# für 6 und 7; die Tiefe steigt hier über die Zahl der Merkmale, die
# "Lateinisches-Quadrat"-Regel (Schwierigkeit >= 3) und die schwereren
# Umwandlungen (Spiegeln, Drehung nach links).
_MATRIX_JE_STUFE = {2: (4, 0), 3: (5, 0), 4: (4, 3), 5: (5, 3)}   # (kern-stufe, schwierigkeit)
_ANALOGIE_JE_STUFE = {6: (6, 0), 7: (7, 1), 8: (7, 3)}


def _strukturen(stufe, nr, seed):
    rng = random.Random(seed)
    if stufe in _MATRIX_JE_STUFE:
        kstufe, schw = _MATRIX_JE_STUFE[stufe]
        erz = MK.erzeuge_matrix(rng, kstufe, schw)
        kern = {"art": "matrix", "zellen": erz["zellen"], "optionen": erz["optionen"],
                "richtig": erz["richtig"], "regeln": erz["regeln"], "stufe": erz["stufe"]}
        q, hint = "Welches Bild gehört ins leere Feld?", \
            "Schau, was sich von Zeile zu Zeile und Spalte zu Spalte ändert."
    else:
        kstufe, schw = _ANALOGIE_JE_STUFE[stufe]
        erz = MK.erzeuge_analogie(rng, kstufe, schw)
        kern = {"art": "analogie", "a": erz["a"], "b": erz["b"], "c": erz["c"],
                "optionen_zellen": erz["optionen_zellen"], "richtig": erz["richtig"],
                "transformation": erz["transformation"], "stufe": erz["stufe"]}
        q, hint = "Das erste Bild wird zum zweiten. Was wird aus dem dritten?", \
            "Finde zuerst heraus, was sich vom ersten zum zweiten Bild ändert."
    return {"type": "bildwahl", "q": q, "svg": erz["svg_frage"],
            "optionen_svg": erz["optionen_svg"], "richtig": erz["richtig"],
            "kern": kern, "hint": hint}


# --- schlussketten: Positionsrätsel. Die Figurenzahl (3 bis 5; raetsel_kern kennt
# nicht mehr) und die Schwierigkeit der Hinweisarten steigen mit der Stufe.
_POSITIONEN_JE_STUFE = {2: (3, 0), 3: (3, 3), 4: (4, 1), 5: (4, 4), 6: (5, 1), 7: (5, 3), 8: (5, 5)}


def _schlussketten(stufe, nr, seed):
    n, schw = _POSITIONEN_JE_STUFE[stufe]
    # Der Seed des Kerns entsteht in positionen_aufgabe aus (Name, Stufe, Welt,
    # Index) – `schw` ist dort zugleich der Index. Den Versuch tragen wir in den
    # Namen, damit jeder Versuch ein anderes Rätsel würfelt.
    versuch_marke = seed
    return KP.positionen_aufgabe(f"denkcheck-{nr}-{versuch_marke}", n, stufe, _welt(nr), schw)


# --- algorithmik: Roboter. Befehle befolgen bis Stufe 4, ab Stufe 5 selbst ein
# Programm finden. algo_kern kennt befolgen nur für Stufe 3 (absolute Befehle) und
# 4 (relative) und finden für 4 (absolut) und 5 (relativ); die Schwierigkeit
# (Länge, Wände) steigt innerhalb davon.
_BEFOLGEN_JE_STUFE = {2: (3, 0), 3: (3, 5), 4: (4, 2)}        # (kern-stufe, schwierigkeit)
_FINDEN_JE_STUFE = {5: (4, 3), 6: (5, 0), 7: (5, 3), 8: (5, 5)}


def _algorithmik(stufe, nr, seed):
    if stufe in _BEFOLGEN_JE_STUFE:
        kstufe, schw = _BEFOLGEN_JE_STUFE[stufe]
        erz = AK.erzeuge_befolgen(kstufe, seed, schw)
        return dict(erz, q="Auf welchem Feld hält der Roboter an?",
                    hint=KP._BEFOLGEN_HINT[erz["befehlssatz"]])
    kstufe, schw = _FINDEN_JE_STUFE[stufe]
    erz = AK.erzeuge_finden(kstufe, seed, schw)
    return dict(erz, q=f"Bring den Roboter mit höchstens {erz['max_laenge']} Befehlen zum Ziel.",
                hint=KP._ROBOTER_HINT["algo_finden"])


# --- darstellung: Punktmuster → Zahl (figur_kern), merken: Merkbild (figur_kern),
# systematik: legen (legen_kern), rechnen: reine Rechenaufgabe (rechen_kern).
# Die Stufen 2…8 sind in diesen Kernen schon eingebaut.

def _darstellung(stufe, nr, seed):
    return FK.denkcheck_punktmuster(stufe, seed)


def _merken(stufe, nr, seed):
    return FK.denkcheck_merkbild(stufe, seed)


def _systematik(stufe, nr, seed):
    return LK.denkcheck_aufgabe(stufe, seed)


def _rechnen(stufe, nr, seed):
    return RK.denkcheck_aufgabe(stufe, seed)


# --- raum: Spiegelbild (2-4), Drehfigur (5-6), Würfelgebäude (7-8). Die Stufe geht
# an grafik_kern (Rastergröße); beim Würfelgebäude trägt Stufe 7 das 3x3- und
# Stufe 8 das 4x4-Raster, die Anzahl bleibt wie bei geo_wuerfel unter dem Deckel
# (Summen bis 39 wären Zählgrind, kein Denken).
_WUERFEL_JE_STUFE = {7: (5, 16), 8: (6, 24)}     # (kern-stufe, größte Würfelzahl)


def _raum(stufe, nr, seed):
    rng = random.Random(seed)
    if stufe <= 4:
        erz = GK.erzeuge_spiegelbild(rng, stufe)
        kern = {"art": "spiegelbild", "zellen": erz["zellen"],
                "optionen_zellen": erz["optionen_zellen"], "richtig": erz["richtig"],
                "stufe": erz["stufe"]}
        return {"type": "bildwahl", "q": "Welches Bild zeigt die Figur gespiegelt?",
                "svg": erz["svg_frage"], "optionen_svg": erz["optionen_svg"],
                "richtig": erz["richtig"], "kern": kern,
                "hint": "Schau dir jede Kästchenreihe einzeln an."}
    if stufe <= 6:
        erz = GK.erzeuge_drehfigur(rng, stufe)
        phrase = KP._WINKEL_NOMAKK[erz["winkel"]] + \
            (KP._UHRZEIGERSINN_ZUSATZ if erz["winkel"] == 90 else "")
        kern = {"art": "drehfigur", "zellen": erz["zellen"],
                "optionen_zellen": erz["optionen_zellen"], "richtig": erz["richtig"],
                "winkel": erz["winkel"], "stufe": erz["stufe"]}
        return {"type": "bildwahl", "q": f"Dreh die Figur im Kopf {phrase}. Welches Bild passt?",
                "svg": erz["svg_frage"], "optionen_svg": erz["optionen_svg"],
                "richtig": erz["richtig"], "kern": kern,
                "hint": "Dreh die Figur in Gedanken Schritt für Schritt."}
    kstufe, deckel = _WUERFEL_JE_STUFE[stufe]
    erz = GK.erzeuge_wuerfelgebaeude(rng, kstufe)
    if erz["anzahl"] > deckel:
        raise Neu("zu viele Würfel")
    kern = {"art": "wuerfelgebaeude", "hoehen": erz["hoehen"], "anzahl": erz["anzahl"],
            "stufe": erz["stufe"]}
    return {"type": "bildzahl", "q": "Wie viele Würfel stecken im Gebäude? Auch die versteckten.",
            "svg": erz["svg"], "a": erz["anzahl"], "kern": kern,
            "hint": "Zähl von hinten nach vorne, Reihe für Reihe."}


# --- umkehren: Zahlenmaschine rückwärts. Die Kernfunktion dreht die Frage nur auf
# ihrer Stufe 6 mit Schwierigkeit >= 3 um (Ausgabe gegeben, Eingabe gesucht);
# welche Regelform dabei herauskommt, würfelt der Kern. Die Zahl der
# Rechenschritte der Maschine steigt mit der Stufe: eine Rechenart bis Stufe 4
# (plus, dann mal; zurückgerechnet braucht mal ein Teilen, das gibt es erst ab
# Stufe 4), zwei Schritte ab Stufe 5 (erst mal dann plus, später plus dann mal).
_MASCHINE_FORM = {2: ("plus",), 3: ("plus",), 4: ("mal",), 5: ("mal_plus",),
                  6: ("plus_mal",), 7: ("mal_plus",), 8: ("plus_mal",)}


def _umkehren(stufe, nr, seed):
    erz = AK.erzeuge_maschine(6, seed, 3 + nr % 3)
    if not erz["umkehr"] or erz["regel"]["form"] not in _MASCHINE_FORM[stufe]:
        raise Neu("falsche Regelform für diese Stufe")
    (x1, y1), (x2, y2), (x3, y3) = erz["paare"]
    q = f"{x1} → {y1}, {x2} → {y2}, {x3} → {y3}. Welche Zahl wird zu {erz['frage_y']}?"
    hint = "Rechne den Weg der Maschine rückwärts."
    if nr % 2 == 0:
        optionen = [str(erz["antwort"])] + [str(a) for a in erz["ablenker"]]
        reihenfolge = list(range(4))
        random.Random(seed + 1).shuffle(reihenfolge)
        return {"type": "wahl", "q": q, "opts": [optionen[i] for i in reihenfolge],
                "correct": reihenfolge.index(0), "check": {"expr": erz["term"]}, "hint": hint}
    return {"type": "zahl", "q": q, "a": erz["antwort"], "check": {"expr": erz["term"]},
            "hint": hint}


BAUER = {
    "strukturen": _strukturen, "schlussketten": _schlussketten,
    "algorithmik": _algorithmik, "darstellung": _darstellung, "raum": _raum,
    "umkehren": _umkehren, "merken": _merken, "systematik": _systematik,
    "rechnen": _rechnen,
}


# ============================================================ Bank zusammenbauen

def _inhalt(task):
    """Der Vergleichsschlüssel zweier Aufgaben: der ganze Inhalt, nicht nur die Frage."""
    return json.dumps(task, ensure_ascii=False, sort_keys=True)


def _rechenlast(task):
    """D2: höchstens KALKUEL_BUDGET elementare Rechenschritte je Term. Leere Liste = in Ordnung."""
    maengel = []
    for label, expr in V._kalkuel_terme(task):
        try:
            V.eval_term(expr)
        except V.TermError:
            continue
        ok, grund = V2.pruefe_kalkuel(expr, KALKUEL_BUDGET)
        if not ok:
            maengel.append(f"{label}: {grund}")
    return maengel


def baue_aufgabe(dim, stufe, nr, gesehen):
    """Die Aufgabe `nr` (1…3) der Dimension `dim` auf `stufe`: der erste Seed, dessen
    Aufgabe der Kern bestätigt, die validate.check_task bei dieser Stufe besteht, im
    Rechenlast-Budget bleibt und sich von den schon gewählten unterscheidet.
    Rückgabe: (Aufgabe, Zahl der verworfenen Versuche). Gibt es keinen, bricht es ab."""
    bauer = BAUER[dim]
    letzter = "kein Versuch"
    for versuch in range(VERSUCHE):
        seed = _seed(dim, stufe, nr, versuch)
        try:
            task = bauer(stufe, nr, seed)
        except (Neu, ValueError, KeyError) as e:
            letzter = f"{type(e).__name__}: {e}"
            continue
        maengel = V.check_task(task, stufe) + _rechenlast(task)
        if maengel:
            letzter = "; ".join(maengel[:2])
            continue
        if _inhalt(task) in gesehen:
            letzter = "Aufgabe gleicht einer schon gewählten"
            continue
        return task, versuch
    raise SystemExit(f"[xx] {dim}-{stufe}-{nr}: nach {VERSUCHE} Seeds keine gültige Aufgabe "
                     f"(zuletzt: {letzter})")


def baue_bank():
    """Alle 9 x 7 x 3 Aufgaben. Rückgabe: das Dokument für data/denkcheck.json."""
    aufgaben, verworfen = [], 0
    for dim in DIMENSIONEN:
        for stufe in STUFEN:
            gesehen = set()
            for nr in range(1, JE_STUFE + 1):
                task, v = baue_aufgabe(dim, stufe, nr, gesehen)
                gesehen.add(_inhalt(task))
                verworfen += v
                aufgaben.append({"id": f"{dim}-{stufe}-{nr}", "dim": dim, "stufe": stufe,
                                 "task": task})
    return {"version": 1, "dimensionen": DIMENSIONEN, "aufgaben": aufgaben}, verworfen


def main():
    bank, verworfen = baue_bank()
    text = json.dumps(bank, ensure_ascii=False, separators=(",", ":"))
    groesse = len(text.encode("utf-8"))
    soll = len(DIMENSIONEN) * len(STUFEN) * JE_STUFE
    if len(bank["aufgaben"]) != soll:
        raise SystemExit(f"[xx] {len(bank['aufgaben'])} Aufgaben statt {soll}")
    if groesse > MAX_BYTES:
        raise SystemExit(f"[xx] data/denkcheck.json wäre {groesse / 1024:.0f} KB und überschreitet "
                         f"die Grenze von {MAX_BYTES // 1024} KB")
    tmp = OUT.with_suffix(".json.tmp")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(text + "\n", "utf-8")
    tmp.replace(OUT)       # erst fertig, dann sichtbar
    print(f"{len(bank['aufgaben'])} Aufgaben ({len(DIMENSIONEN)} Dimensionen x {len(STUFEN)} Stufen "
          f"x {JE_STUFE}), {groesse / 1024:.0f} KB, {verworfen} Seeds verworfen")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
