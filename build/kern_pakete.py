# -*- coding: utf-8 -*-
"""Baut die Lernpakete der neuen Denkschule-Fertigkeiten (SPEC_lektionen_v2.md §8).

Wie verkleidung.py bei Logikgitter/Folgen dreht dieses Modul das Erzeugungs-
prinzip um: Der deterministische Kern (grafik_kern.py, muster_kern.py,
raetsel_kern.py, spiel_kern.py, algo_kern.py) liefert die Wahrheit; hier
kommt nur noch die sprachliche Verkleidung dazu — rein deterministisch aus
Themenvokabular (THEMEN) zusammengesetzt, KEIN Sprachmodell. Jedes fertige
Paket läuft vor dem Schreiben durch validate.check_unit; bei einem Mangel
wird nicht geschrieben, sondern laut abgebrochen ("Kein Fehler erreicht das
Kind").

  .venv/bin/python build/kern_pakete.py --alle
  .venv/bin/python build/kern_pakete.py --alle --klasse 4
      Baut jedes fehlende Kern-Paket (Fertigkeit@Stufe und Fertigkeit@Stufe+1,
      Welt rotierend über einen laufenden Index) in data/units_seed.json.

  .venv/bin/python build/kern_pakete.py --skill geo_spiegel --stage 3 [--world weltraum]
      Baut genau ein Paket.

  .venv/bin/python build/kern_pakete.py --alle --force
      Wie --alle, ersetzt aber auch schon vorhandene Pakete.

  .venv/bin/python build/kern_pakete.py --alle --dry-run
      Zeigt nur den Bauplan, ohne zu bauen oder zu schreiben.

  .venv/bin/python build/kern_pakete.py --alle --force --nur geo_karte,must_fibo
      Beschränkt --alle auf die genannten Fertigkeiten (Komma getrennt). Die
      Welt rotiert trotzdem über den GESAMTEN Plan, damit eine Fertigkeit
      immer dieselbe Welt bekommt, egal ob alles oder nur ein Teil gebaut wird.

Seit V3 (ZIELE-V3.md) laufen auch die Geometrie-Fertigkeiten (geo_kern.py),
die Legeaufgaben (legen_kern.py), die Punktmuster von must_figur
(figur_kern.py), die reinen Zahlenfolgen (raetsel_kern.erzeuge_folge) und das
Positionsrätsel von log_reihen über diesen Pfad.

Seeds ausschließlich über zlib.crc32(f"{art}|{skill}|{stage}|{world}|{index}")
(Leitplanke §0.3) — kein hash(), kein eval(), kein LLM in diesem Pfad.
"""
import argparse
import json
import random
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum as C
import fundus as F
import validate as V
import grafik_kern as GK
import muster_kern as MK
import raetsel_kern as K
import spiel_kern as SP
import algo_kern as AK
import geo_kern as GEO
import legen_kern as LK
import figur_kern as FK
# generate_units.py importiert seinerseits kern_pakete (pfad_von/make_unit) —
# um den daraus entstehenden Ringimport nie zum Problem zu machen, wird
# generate_units hier bewusst erst innerhalb von main() geladen, nicht auf
# Modulebene (siehe dort GU.write_units/GU.notiere).

ROOT = Path(__file__).resolve().parent.parent
SEED_OUT = ROOT / "data" / "units_seed.json"


# ------------------------------------------------------------- Themenvokabular
# Je Themenwelt aus curriculum.WORLDS: ein Robotername, ein Zielobjekt, ein
# Nim-Gegenstand (Plural, ohne Artikel), ein Maschinenname, fünf Rollen
# (Nominativ + Dativ + Wortkern für Positionsrätsel) und ein Rahmensatz.
# Keine Marken, keine Spielfiguren, TABU-frei (SPEC_lektionen_v2.md §8).
THEMEN = {
    "minecraft": dict(
        roboter="der Golem", ziel="die Truhe", steine="Kristalle", stein_sg="Kristall",
        willkommen="Willkommen in der Blockwelt!",
        maschine="die Verzauberungsmaschine",
        rollen=[
            {"nom": "der Schmied", "dat": "dem Schmied", "kern": "Schmied"},
            {"nom": "die Bergarbeiterin", "dat": "der Bergarbeiterin", "kern": "Bergarbeiterin"},
            {"nom": "der Händler", "dat": "dem Händler", "kern": "Händler"},
            {"nom": "die Baumeisterin", "dat": "der Baumeisterin", "kern": "Baumeisterin"},
            {"nom": "der Entdecker", "dat": "dem Entdecker", "kern": "Entdecker"},
        ],
        rahmen="In der Blockwelt stellt sich die ganze Truppe für ein Gruppenfoto in eine Reihe.",
    ),
    "brawl": dict(
        roboter="der Kampfroboter", ziel="die Trophäe", steine="Münzen", stein_sg="Münze",
        willkommen="Willkommen in der Arena!",
        maschine="die Punktemaschine",
        rollen=[
            {"nom": "der Kämpfer", "dat": "dem Kämpfer", "kern": "Kämpfer"},
            {"nom": "die Kämpferin", "dat": "der Kämpferin", "kern": "Kämpferin"},
            {"nom": "der Schiedsrichter", "dat": "dem Schiedsrichter", "kern": "Schiedsrichter"},
            {"nom": "die Trainerin", "dat": "der Trainerin", "kern": "Trainerin"},
            {"nom": "der Fan", "dat": "dem Fan", "kern": "Fan"},
        ],
        rahmen="Vor dem nächsten Kampf stellt sich die Crew in der Arena in eine Reihe auf.",
    ),
    "clash": dict(
        roboter="der Wachroboter", ziel="das Rathaus", steine="Goldstücke", stein_sg="Goldstück",
        willkommen="Willkommen beim Burgenbau!",
        maschine="die Zaubermaschine",
        rollen=[
            {"nom": "der Baumeister", "dat": "dem Baumeister", "kern": "Baumeister"},
            {"nom": "die Burgherrin", "dat": "der Burgherrin", "kern": "Burgherrin"},
            {"nom": "der Wächter", "dat": "dem Wächter", "kern": "Wächter"},
            {"nom": "die Handwerkerin", "dat": "der Handwerkerin", "kern": "Handwerkerin"},
            {"nom": "der Bote", "dat": "dem Boten", "kern": "Bote"},
        ],
        rahmen="Vor dem Fest stellt sich die Burgmannschaft in einer Reihe auf.",
    ),
    "fussball": dict(
        roboter="der Trainingsroboter", ziel="das Tor", steine="Bälle", stein_sg="Ball",
        willkommen="Willkommen auf dem Fußballplatz!",
        maschine="die Trainingsmaschine",
        rollen=[
            {"nom": "der Torwart", "dat": "dem Torwart", "kern": "Torwart"},
            {"nom": "die Stürmerin", "dat": "der Stürmerin", "kern": "Stürmerin"},
            {"nom": "der Trainer", "dat": "dem Trainer", "kern": "Trainer"},
            {"nom": "die Kapitänin", "dat": "der Kapitänin", "kern": "Kapitänin"},
            {"nom": "der Schiedsrichter", "dat": "dem Schiedsrichter", "kern": "Schiedsrichter"},
        ],
        rahmen="Vor dem Anpfiff stellt sich die Mannschaft in einer Reihe auf.",
    ),
    "roblox": dict(
        roboter="der Bauroboter", ziel="der Ausgang", steine="Münzen", stein_sg="Münze",
        willkommen="Willkommen im Baukasten!",
        maschine="der Zahlengenerator",
        rollen=[
            {"nom": "der Baumeister", "dat": "dem Baumeister", "kern": "Baumeister"},
            {"nom": "die Spielerin", "dat": "der Spielerin", "kern": "Spielerin"},
            {"nom": "der Entwickler", "dat": "dem Entwickler", "kern": "Entwickler"},
            {"nom": "die Anführerin", "dat": "der Anführerin", "kern": "Anführerin"},
            {"nom": "der Neuling", "dat": "dem Neuling", "kern": "Neuling"},
        ],
        rahmen="Vor dem nächsten Level stellt sich die Gruppe in einer Reihe auf.",
    ),
    "pokemon": dict(
        roboter="der Sammelroboter", ziel="die Sammelkugel", steine="Bonbons", stein_sg="Bonbon",
        willkommen="Willkommen bei den Sammelmonstern!",
        maschine="die Entwicklungsmaschine",
        rollen=[
            {"nom": "der Sammler", "dat": "dem Sammler", "kern": "Sammler"},
            {"nom": "die Trainerin", "dat": "der Trainerin", "kern": "Trainerin"},
            {"nom": "der Forscher", "dat": "dem Forscher", "kern": "Forscher"},
            {"nom": "die Tauscherin", "dat": "der Tauscherin", "kern": "Tauscherin"},
            {"nom": "der Züchter", "dat": "dem Züchter", "kern": "Züchter"},
        ],
        rahmen="Vor dem Turnier stellt sich die Sammlergruppe in einer Reihe auf.",
    ),
    "weltraum": dict(
        roboter="der Rover", ziel="die Rakete", steine="Sternensteine", stein_sg="Sternenstein",
        willkommen="Willkommen im Weltraum!",
        maschine="der Bordcomputer",
        rollen=[
            {"nom": "der Astronaut", "dat": "dem Astronauten", "kern": "Astronaut"},
            {"nom": "die Pilotin", "dat": "der Pilotin", "kern": "Pilotin"},
            {"nom": "der Kapitän", "dat": "dem Kapitän", "kern": "Kapitän"},
            {"nom": "die Forscherin", "dat": "der Forscherin", "kern": "Forscherin"},
            {"nom": "der Ingenieur", "dat": "dem Ingenieur", "kern": "Ingenieur"},
        ],
        rahmen="Die Crew stellt sich vor dem Start in einer Reihe auf.",
    ),
    "dino": dict(
        roboter="der Ausgrabungsroboter", ziel="das Fossil", steine="Knochen", stein_sg="Knochen",
        willkommen="Willkommen in der Dinozeit!",
        maschine="die Zeitmaschine",
        rollen=[
            {"nom": "der Ausgräber", "dat": "dem Ausgräber", "kern": "Ausgräber"},
            {"nom": "die Forscherin", "dat": "der Forscherin", "kern": "Forscherin"},
            {"nom": "der Fährtenleser", "dat": "dem Fährtenleser", "kern": "Fährtenleser"},
            {"nom": "die Sammlerin", "dat": "der Sammlerin", "kern": "Sammlerin"},
            {"nom": "der Wächter", "dat": "dem Wächter", "kern": "Wächter"},
        ],
        rahmen="Das Grabungsteam stellt sich für ein Foto in einer Reihe auf.",
    ),
    "rennen": dict(
        roboter="der Boxenroboter", ziel="die Ziellinie", steine="Reifen", stein_sg="Reifen",
        willkommen="Willkommen an der Rennstrecke!",
        maschine="der Boxencomputer",
        rollen=[
            {"nom": "der Fahrer", "dat": "dem Fahrer", "kern": "Fahrer"},
            {"nom": "die Fahrerin", "dat": "der Fahrerin", "kern": "Fahrerin"},
            {"nom": "der Mechaniker", "dat": "dem Mechaniker", "kern": "Mechaniker"},
            {"nom": "die Chefin", "dat": "der Chefin", "kern": "Chefin"},
            {"nom": "der Streckenposten", "dat": "dem Streckenposten", "kern": "Streckenposten"},
        ],
        rahmen="Vor dem Rennen stellt sich das Team an der Startlinie in einer Reihe auf.",
    ),
    "ninja": dict(
        roboter="der Schattenroboter", ziel="die Schriftrolle", steine="Wurfsterne",
        stein_sg="Wurfstern", willkommen="Willkommen im Ninja-Training!",
        maschine="die Geheimmaschine",
        rollen=[
            {"nom": "der Ninja", "dat": "dem Ninja", "kern": "Ninja"},
            {"nom": "die Kämpferin", "dat": "der Kämpferin", "kern": "Kämpferin"},
            {"nom": "der Meister", "dat": "dem Meister", "kern": "Meister"},
            {"nom": "die Schülerin", "dat": "der Schülerin", "kern": "Schülerin"},
            {"nom": "der Wächter", "dat": "dem Wächter", "kern": "Wächter"},
        ],
        rahmen="Vor dem Training stellt sich die Gruppe in einer Reihe auf.",
    ),
}


# ------------------------------------------------------------------- Hilfsdinge

def _seed(art, sid, stage, wid, index):
    """Deterministisches Seed-Schema (Leitplanke §0.3): hängt nur von Art des
    Kerns, Fertigkeit, Stufe, Welt und Aufgaben-Index ab, nie vom Versuch —
    derselbe Aufruf liefert immer byte-gleich dasselbe Paket."""
    text = f"{art}|{sid}|{stage}|{wid}|{index}"
    return zlib.crc32(text.encode("utf-8"))


def _mit_wiederholung(fn, seed, *args, versuche=5):
    """Ruft einen erzeuge_*()-Kern auf, der ein frisches random.Random(seed)
    erwartet. grafik_kern.py/muster_kern.py können nach 200 internen
    Versuchen ein ValueError werfen (seltener Kollisionsfall); dann wird hier
    mit einem leicht verschobenen Seed neu versucht, statt das ganze Paket
    scheitern zu lassen. Bleibt es dabei, wird laut weitergereicht."""
    letzter_fehler = None
    for i in range(versuche):
        try:
            return fn(random.Random(seed + i), *args)
        except ValueError as e:
            letzter_fehler = e
    raise ValueError(f"{fn.__name__} scheiterte nach {versuche} Versuchen "
                     f"(seed={seed}): {letzter_fehler}")


def _gross(s):
    """Großschreibt nur den allerersten Buchstaben – für Satzanfänge."""
    return s[0].upper() + s[1:] if s else s


def _zu(ziel_name):
    """'die Truhe' -> 'zur Truhe', 'das Rathaus'/'der Ausgang' -> 'zum
    Rathaus'/'zum Ausgang' – die Kontraktion von 'zu' + bestimmtem Artikel
    im Dativ, für Sätze wie 'Bring den Rover zur Rakete.'"""
    if ziel_name.startswith("die "):
        return "zur " + ziel_name[4:]
    if ziel_name.startswith("der ") or ziel_name.startswith("das "):
        return "zum " + ziel_name[4:]
    return "zu " + ziel_name


def _von(dat_name):
    """'von' + Dativname, mit der üblichen Verschmelzung 'von dem' -> 'vom'
    ('von der' verschmilzt im Deutschen NICHT, die bleibt unverändert):
    'dem Händler' -> 'vom Händler', 'der Trainerin' -> 'von der Trainerin'."""
    if dat_name.startswith("dem "):
        return "vom " + dat_name[4:]
    return "von " + dat_name


def _stein(wid, anzahl):
    """Singular oder Plural des Nim-Gegenstands dieser Welt, je nach Anzahl –
    'nimmt 1 Goldstück', aber 'nimmt 2 Goldstücke'."""
    themen = THEMEN[wid]
    return themen["stein_sg"] if anzahl == 1 else themen["steine"]


# ================================================================ geo_spiegel

_SPIEGEL_Q = [
    "Spiegle die Figur an der gestrichelten Linie. Welches Bild ist richtig?",
    "Wie sieht die Figur im Spiegel aus? Tippe das richtige Bild an.",
    "Klapp die Figur gedanklich an der Linie um. Welches Bild passt?",
    "Spiegle die Figur im Kopf. Welches der vier Bilder stimmt?",
    "An der gestrichelten Linie gespiegelt: Welches Bild ist richtig?",
    "Finde das Spiegelbild der Figur. Welches Bild passt genau?",
]


def _kern_stufen_spiegel_dreh(stage):
    """grafik_kern.py hat keinen eigenen Schwierigkeits-Parameter – die
    Denktiefe steigt stattdessen über die interne 'stufe' (Rastergröße/
    Figurgröße), die hier innerhalb des Pakets von Aufgabe zu Aufgabe wächst
    (SPEC_lektionen_v2.md §8, Beispiel geo_spiegel@3 -> 2,3,3,4,4,5)."""
    return [stage - 1, stage, stage, stage + 1, stage + 1, stage + 2]


def _bauer_geo_spiegel(stage, wid, index):
    seed = _seed("spiegel", "geo_spiegel", stage, wid, index)
    kern_stufe = _kern_stufen_spiegel_dreh(stage)[index]
    erz = _mit_wiederholung(GK.erzeuge_spiegelbild, seed, kern_stufe)
    kern = {"art": "spiegelbild", "zellen": erz["zellen"],
            "optionen_zellen": erz["optionen_zellen"], "richtig": erz["richtig"],
            "stufe": erz["stufe"]}
    return {"type": "bildwahl", "q": _SPIEGEL_Q[index], "svg": erz["svg_frage"],
            "optionen_svg": erz["optionen_svg"], "richtig": erz["richtig"], "kern": kern,
            "hint": "Schau dir jede Kästchenreihe einzeln an."}


# ================================================================= geo_drehen

# Zwei Formen je Winkel: Nominativ/Akkusativ ("dreh die Figur eine Viertel-
# drehung...", Akkusativ des Ausmaßes) und Dativ ("nach einer Viertel-
# drehung...", nach 'nach' steht Dativ) — je nach Schablone wird die passende
# eingesetzt (SPEC-Rückmeldung: Kasusfehler wie "nach eine Vierteldrehung").
_WINKEL_NOMAKK = {
    90: "eine Vierteldrehung nach rechts", 180: "eine halbe Drehung",
    270: "eine Vierteldrehung nach links",
}
_WINKEL_DATIV = {
    90: "einer Vierteldrehung nach rechts", 180: "einer halben Drehung",
    270: "einer Vierteldrehung nach links",
}
# Nur bei 90° zur Klarstellung angehängt – und zwar genau einmal pro Satz,
# ohne Klammer, nie verschachtelt in einer zweiten Klammer.
_UHRZEIGERSINN_ZUSATZ = ", also im Uhrzeigersinn"

_DREH_Q = [
    "Dreh die Figur im Kopf {phrase}. Welches Bild passt?",
    "Stell dir vor, du drehst die Figur {phrase}. Welches Bild ist richtig?",
    "Wie sieht die Figur nach {phrase_dat} aus? Tippe das richtige Bild an.",
    "Dreh die Figur gedanklich {phrase}. Welches der vier Bilder stimmt?",
    "Nach {phrase_dat}: Wie sieht die Figur jetzt aus? Finde das passende Bild.",
    "Dreh die Figur im Kopf {phrase}. Welches Bild ist richtig?",
]


def _bauer_geo_drehen(stage, wid, index):
    seed = _seed("dreh", "geo_drehen", stage, wid, index)
    kern_stufe = _kern_stufen_spiegel_dreh(stage)[index]
    erz = _mit_wiederholung(GK.erzeuge_drehfigur, seed, kern_stufe)
    winkel = erz["winkel"]
    zusatz = _UHRZEIGERSINN_ZUSATZ if winkel == 90 else ""
    phrase = _WINKEL_NOMAKK[winkel] + zusatz
    phrase_dat = _WINKEL_DATIV[winkel] + zusatz
    q = _DREH_Q[index].format(phrase=phrase, phrase_dat=phrase_dat)
    kern = {"art": "drehfigur", "zellen": erz["zellen"],
            "optionen_zellen": erz["optionen_zellen"], "richtig": erz["richtig"],
            "winkel": erz["winkel"], "stufe": erz["stufe"]}
    return {"type": "bildwahl", "q": q, "svg": erz["svg_frage"],
            "optionen_svg": erz["optionen_svg"], "richtig": erz["richtig"], "kern": kern,
            "hint": "Dreh die Figur in Gedanken Schritt für Schritt."}


# ================================================================ geo_wuerfel

_WUERFEL_Q = [
    "Wie viele Würfel stecken im Gebäude? Denk an die versteckten.",
    "Zähl alle Würfel im Gebäude, auch die, die du nicht siehst.",
    "Wie viele Würfel wurden für dieses Gebäude gebraucht?",
    "Wie viele Würfel sind es insgesamt? Vergiss die versteckten nicht.",
    "Zähl genau: Wie viele Würfel stecken in diesem Gebäude?",
    "Wie viele Würfel stecken in diesem Gebäude? Auch verdeckte zählen mit.",
]


def _kern_stufen_wuerfel(stage):
    """Wie _kern_stufen_spiegel_dreh, aber mit einer eigenen Staffel (SPEC
    §8, Beispiel geo_wuerfel@5 -> 4,5,5,6,6,6): grafik_kern._wuerfelgebaeude_
    groesse deckelt die Rastergröße bei n=4 (Stufe > 5), ein Sprung auf
    stage+2 brächte dort keinen Unterschied mehr."""
    return [stage - 1, stage, stage, stage + 1, stage + 1, stage + 1]


# Anzahl-Deckel je Rastergröße (SPEC-Rückmeldung: Summen bis 39 sind
# Zählgrind, kein Denken — "Schwierigkeit ist Denktiefe, nie Zahlengröße").
_WUERFEL_ANZAHL_DECKEL = {3: 20, 4: 24}


def _bauer_geo_wuerfel(stage, wid, index):
    seed = _seed("wuerfel", "geo_wuerfel", stage, wid, index)
    kern_stufe = _kern_stufen_wuerfel(stage)[index]
    erz = None
    for versuch in range(200):
        kandidat = GK.erzeuge_wuerfelgebaeude(random.Random(seed + versuch), kern_stufe)
        deckel = _WUERFEL_ANZAHL_DECKEL.get(len(kandidat["hoehen"]))
        if deckel is None or kandidat["anzahl"] <= deckel:
            erz = kandidat
            break
    if erz is None:
        raise ValueError(f"geo_wuerfel: keine Aufgabe unter dem Anzahl-Deckel gefunden "
                         f"(kern_stufe={kern_stufe}, seed={seed})")
    kern = {"art": "wuerfelgebaeude", "hoehen": erz["hoehen"], "anzahl": erz["anzahl"],
            "stufe": erz["stufe"]}
    return {"type": "bildzahl", "q": _WUERFEL_Q[index], "svg": erz["svg"], "a": erz["anzahl"],
            "kern": kern, "hint": "Zähl von hinten nach vorne, Reihe für Reihe."}


# ================================================================ must_matrix

_MATRIX_Q = [
    "Welches Bild gehört ins leere Feld?",
    "Schau dir die Reihen und Spalten an. Welches Bild passt ins leere Feld?",
    "Was fehlt im Muster? Finde das richtige Bild fürs leere Feld.",
    "Welches Bild vervollständigt das Muster?",
    "Finde die Regel im Muster. Welches Bild passt ins leere Feld?",
    "Welches der vier Bilder gehört an die leere Stelle?",
]


def _bauer_must_matrix(stage, wid, index):
    seed = _seed("matrix", "must_matrix", stage, wid, index)
    erz = _mit_wiederholung(MK.erzeuge_matrix, seed, stage, index)
    kern = {"art": "matrix", "zellen": erz["zellen"], "optionen": erz["optionen"],
            "richtig": erz["richtig"], "regeln": erz["regeln"], "stufe": erz["stufe"]}
    return {"type": "bildwahl", "q": _MATRIX_Q[index], "svg": erz["svg_frage"],
            "optionen_svg": erz["optionen_svg"], "richtig": erz["richtig"], "kern": kern,
            "hint": "Schau dir an, was sich von Zeile zu Zeile und Spalte zu Spalte ändert."}


# ============================================================== must_analogie

# Die Bilder selbst tragen keine Buchstaben (kein Text im SVG) — die Texte
# sprechen deshalb durchgehend von "das erste/zweite/dritte Bild", nie von
# "A"/"B"/"C" (SPEC-Rückmeldung).
_ANALOGIE_Q = [
    "Das erste Bild wird zum zweiten. Mach dasselbe mit dem dritten Bild: Welches kommt heraus?",
    "Finde die Umwandlung vom ersten zum zweiten Bild. Was ergibt dieselbe Umwandlung beim dritten Bild?",
    "Das erste Bild wird auf eine bestimmte Art zum zweiten. Was wird so aus dem dritten Bild?",
    "Wie wird aus dem ersten Bild das zweite? Wende denselben Trick auf das dritte Bild an.",
    "Finde die geheime Regel zwischen den ersten beiden Bildern. Was ergibt sie beim dritten Bild?",
    "Das erste Bild wird zum zweiten wie das dritte Bild zu einem vierten. Welches Bild ist das?",
]


def _bauer_must_analogie(stage, wid, index):
    seed = _seed("analogie", "must_analogie", stage, wid, index)
    erz = _mit_wiederholung(MK.erzeuge_analogie, seed, stage, index)
    kern = {"art": "analogie", "a": erz["a"], "b": erz["b"], "c": erz["c"],
            "optionen_zellen": erz["optionen_zellen"], "richtig": erz["richtig"],
            "transformation": erz["transformation"], "stufe": erz["stufe"]}
    return {"type": "bildwahl", "q": _ANALOGIE_Q[index], "svg": erz["svg_frage"],
            "optionen_svg": erz["optionen_svg"], "richtig": erz["richtig"], "kern": kern,
            "hint": "Finde zuerst heraus, was sich vom ersten zum zweiten Bild ändert."}


# =============================================================== log_position

_ORDINAL = {1: "zweiter", 2: "dritter", 3: "vierter"}


def _positionen_frage_text(frage, n, rollen):
    if frage["art"] == "position":
        p = frage["p"]
        if p == 0:
            return "Wer steht ganz links?"
        if p == n - 1:
            return "Wer steht ganz rechts?"
        return f"Wer steht an {_ORDINAL[p]} Stelle von links?"
    a_idx, seite = frage["a"], frage["seite"]
    richtung = "rechts" if seite == "rechts" else "links"
    return f"Wer steht direkt {richtung} neben {rollen[a_idx]['dat']}?"


def _positionen_hinweistext(typ, a_nom, b_dat=None, c_dat=None):
    """Satzschablonen je Hinweistyp (SPEC §6): a_nom ist die großgeschriebene
    Nominativform des Subjekts, b_dat/c_dat die Dativform der Nachbarn — im
    Deutschen stehen 'neben', 'zwischen' und 'von' mit dem Dativ."""
    if typ == "ganz_links":
        return f"{a_nom} steht ganz links."
    if typ == "ganz_rechts":
        return f"{a_nom} steht ganz rechts."
    if typ == "mitte":
        return f"{a_nom} steht genau in der Mitte."
    if typ == "nicht_rand":
        return f"{a_nom} steht nicht am Rand."
    if typ == "direkt_links":
        return f"{a_nom} steht direkt links neben {b_dat}."
    if typ == "direkt_rechts":
        return f"{a_nom} steht direkt rechts neben {b_dat}."
    if typ == "links_von":
        return f"{a_nom} steht irgendwo links {_von(b_dat)}."
    if typ == "rechts_von":
        return f"{a_nom} steht irgendwo rechts {_von(b_dat)}."
    if typ == "neben":
        return f"{a_nom} steht direkt neben {b_dat}."
    if typ == "nicht_neben":
        return f"{a_nom} steht nicht direkt neben {b_dat}."
    if typ == "zwischen":
        return f"{a_nom} steht zwischen {b_dat} und {c_dat}."
    raise ValueError(f"unbekannter Positions-Hinweistyp {typ!r}")


def _bauer_log_position(stage, wid, index):
    n = 4 if stage == 5 else 5   # SPEC §6: Stufe 5 -> n=4, Stufe 6 -> n=5
    return positionen_aufgabe("log_position", n, stage, wid, index)


def _bauer_log_reihen(stage, wid, index):
    """log_reihen (V3, ZIELE-V3.md G2): dasselbe Positionsrätsel wie
    log_position, aber mit weniger Figuren, weil die Fertigkeit eine Stufe
    früher liegt: Stufe 4 -> drei, Stufe 5 -> vier Figuren. Die Denktiefe
    steigt dazu mit dem Index (mehr und schwierigere Hinweise)."""
    n = 3 if stage == 4 else 4
    return positionen_aufgabe("log_reihen", n, stage, wid, index)


def positionen_aufgabe(sid, n, stage, wid, index):
    """Das Positionsrätsel mit n Figuren (3..5). `sid` und `index` gehen nur in
    den Seed ein; `index` ist zugleich die Schwierigkeit (0..5) des Kerns. Öffentlich,
    weil auch der Denk-Check (denkcheck_bank.py) dasselbe Rätsel braucht."""
    seed = _seed("position", sid, stage, wid, index)
    rollen = THEMEN[wid]["rollen"][:n]
    namen = [r["nom"] for r in rollen]

    kern = K.erzeuge_positionen(n, seed=seed, schwierigkeit=index)

    hinweise = []
    for h in kern["hinweise"]:
        a_idx = int(h["a"][1:])
        b_idx = int(h["b"][1:]) if "b" in h else None
        c_idx = int(h["c"][1:]) if "c" in h else None
        text = _positionen_hinweistext(
            h["typ"], _gross(rollen[a_idx]["nom"]),
            rollen[b_idx]["dat"] if b_idx is not None else None,
            rollen[c_idx]["dat"] if c_idx is not None else None,
        )
        hh = {"typ": h["typ"], "a": a_idx, "text": text}
        if b_idx is not None:
            hh["b"] = b_idx
        if c_idx is not None:
            hh["c"] = c_idx
        hinweise.append(hh)

    loesung = [int(p[1:]) for p in kern["loesung"]]
    frage = dict(kern["frage"])
    if frage["art"] == "neben":
        frage["a"] = int(frage["a"][1:])
    frage_text = _positionen_frage_text(frage, n, rollen)

    if frage["art"] == "position":
        ziel_idx = loesung[frage["p"]]
    else:
        pos_a = loesung.index(frage["a"])
        nachbar_pos = pos_a - 1 if frage["seite"] == "links" else pos_a + 1
        ziel_idx = loesung[nachbar_pos]

    # Antwortmöglichkeiten: alle Namen, deterministisch über denselben Seed
    # gemischt (SPEC §8).
    optionen = list(namen)
    random.Random(seed).shuffle(optionen)
    richtig = optionen.index(namen[ziel_idx])

    return {
        "type": "positionen", "rahmen": THEMEN[wid]["rahmen"], "namen": namen,
        "hinweise": hinweise, "loesung": loesung, "frage": frage, "frage_text": frage_text,
        "optionen": optionen, "richtig": richtig,
        "hint": "Zeichne eine Reihe und trag jeden Hinweis ein.",
    }


# ================================================================== komb_nim

_NIM_REGEL = "{n} {steine}. Ihr nehmt abwechselnd {bis}, wer zuletzt nimmt, gewinnt."

# Je zwei Formulierungen pro Variante (zug/rest/gegner kommen je zweimal pro
# Paket vor, siehe spiel_kern._variante_aus_schwierigkeit) – nötig, damit zwei
# Aufgaben mit zufällig gleicher Steinzahl trotzdem nicht wortgleich sind
# (check_unit lehnt eine im Paket zweimal vorkommende Frage ab).
_ZUG_FRAGE = [
    "Du bist dran: Wie viele {steine} nimmst du, damit du sicher gewinnst?",
    "Jetzt bist du dran: Wie viele {steine} musst du nehmen, um sicher zu gewinnen?",
]
_REST_FRAGE = [
    "Du bist dran: Wie viele {steine} lässt du liegen, wenn du sicher gewinnen willst?",
    "Jetzt bist du dran: Wie viele {steine} lässt du übrig, damit du sicher gewinnst?",
]
_GEGNER_SATZ = [
    "Der Gegner ist zuerst dran und nimmt {g} {stein_g}.",
    "Zuerst zieht der Gegner und nimmt sich {g} {stein_g}.",
]


def _bis_wort(k):
    """'1 bis k' als aufgezählte Worte statt der Floskel 'bis' (SPEC-
    Rückmeldung: 'bis 2' liest sich englisch/unklar): k=2 -> '1 oder 2',
    k=3 -> '1, 2 oder 3'."""
    zahlen = list(range(1, k + 1))
    if len(zahlen) == 1:
        return str(zahlen[0])
    return ", ".join(str(z) for z in zahlen[:-1]) + f" oder {zahlen[-1]}"


def _nim_distraktoren(rest, n, seed):
    """Drei falsche Restzahlen (SPEC §7): Zahlen aus 0..n außer 'rest', die
    naheliegenden Zahlen zuerst (plausibler als ein Zufallswurf über den
    ganzen Bereich), deterministisch gemischt."""
    pool = sorted((v for v in range(0, n + 1) if v != rest), key=lambda v: abs(v - rest))
    nah = pool[:6]
    random.Random(seed).shuffle(nah)
    return nah[:3]


def _komb_nim_erzeugen(stage, wid, index):
    """Baut den Nim-Kern für diese Position im Paket. Würfelt mit Seed-
    Versatz neu, bis die Ausgangszahl 'n' von JEDER vorherigen Aufgabe
    desselben Pakets abweicht (SPEC-Rückmeldung: komb_nim@5 hatte zweimal
    "15 Goldstücke, Gegner nimmt 1") – rekursiv, weil die vorherigen
    Aufgaben ihrerseits schon denselben Versatz durchlaufen haben können.
    Bleibt vollständig deterministisch: derselbe Aufruf liefert immer
    dasselbe Ergebnis."""
    vorherige_n = {_komb_nim_erzeugen(stage, wid, i)["n"] for i in range(index)}
    basis_seed = _seed("nim", "komb_nim", stage, wid, index)
    for versatz in range(500):
        erz = SP.erzeuge_nim(stage, basis_seed + versatz, index)
        if erz["n"] not in vorherige_n:
            return erz
    raise ValueError(f"komb_nim: keine Aufgabe mit neuer Ausgangszahl n gefunden "
                     f"(stage={stage}, wid={wid}, index={index})")


def _bauer_komb_nim(stage, wid, index):
    seed = _seed("nim", "komb_nim", stage, wid, index)   # nur für Distraktor-/Options-Mischung
    steine = THEMEN[wid]["steine"]
    erz = _komb_nim_erzeugen(stage, wid, index)
    n, k, zug, rest, variante = erz["n"], erz["k"], erz["zug"], erz["rest"], erz["variante"]
    regel = _NIM_REGEL.format(n=n, steine=steine, bis=_bis_wort(k))
    variante_index = index % 2   # jede Variante kommt genau zweimal im Paket vor

    if variante == "zug":
        q = f"{regel} " + _ZUG_FRAGE[variante_index].format(steine=steine)
        return {"type": "zahl", "q": q, "a": zug, "check": {"expr": f"{n}-{n - zug}"},
                "hint": "Denk rückwärts: Was muss am Ende übrig bleiben?"}

    if variante == "rest":
        q = f"{regel} " + _REST_FRAGE[variante_index].format(steine=steine)
        optionen = [str(rest)] + [str(d) for d in _nim_distraktoren(rest, n, seed)]
        reihenfolge = list(range(4))
        random.Random(seed + 1).shuffle(reihenfolge)
        return {"type": "wahl", "q": q, "opts": [optionen[i] for i in reihenfolge],
                "correct": reihenfolge.index(0), "check": {"expr": f"{n}-{zug}"},
                "hint": "Denk rückwärts: Was muss am Ende übrig bleiben?"}

    # variante == "gegner"
    g, n_nach = erz["gegner_nimmt"], erz["n_nach_gegner"]
    q = f"{regel} " + _GEGNER_SATZ[variante_index].format(g=g, stein_g=_stein(wid, g))
    steps = [
        {"q": f"Wie viele {steine} liegen jetzt noch da?", "a": n_nach,
         "check": {"expr": f"{n}-{g}"}},
        {"q": "Jetzt bist du dran. Wie viele nimmst du, damit du sicher gewinnst?", "a": zug,
         "check": {"expr": f"{n_nach}-{n_nach - zug}"}},
    ]
    return {"type": "mehrschritt", "q": q, "steps": steps,
            "hint": "Denk rückwärts: Was muss am Ende übrig bleiben?"}


# ================================================================= Algorithmik
# algo_befolgen, algo_finden, algo_reparieren, algo_schleife (modus "roboter",
# algo_kern.erzeuge_*) und algo_maschine (Typ "zahl"/"wahl", algo_kern.
# erzeuge_maschine). Alle Robotertexte nennen den Roboter nur als Subjekt
# (Nominativ, "{Rob}"/"{rob}") – die Themenwelt-Namen tragen keine Dativ-/
# Akkusativform, deshalb bleiben die Sätze bewusst bei "X macht/kommt/hält",
# nie bei "bring X" (das bräuchte den Akkusativ).

_BEFOLGEN_Q = [
    "{Rob} startet und befolgt sein Programm. Auf welchem Feld hält er an?",
    "{Rob} führt sein Programm aus, Schritt für Schritt. Wo hält er am Ende?",
    "{Rob} bekommt ein Programm zum Ausführen. Welches Feld erreicht er?",
    "{Rob} folgt seinem Programm genau. Auf welchem Feld hält er an?",
    "{Rob} läuft sein Programm ab. Wo steht er danach?",
    "{Rob} führt Befehl für Befehl aus. Auf welchem Feld hält er zum Schluss?",
]

_FINDEN_Q = [
    "{Rob} soll mit höchstens {n} Befehlen {zu_ziel} kommen. Baue das Programm dafür.",
    "Mit höchstens {n} Befehlen soll {rob} {zu_ziel} kommen. Bau ihm den Weg.",
    "{Rob} muss {zu_ziel} – mit höchstens {n} Befehlen. Wie geht das?",
    "Finde ein Programm mit höchstens {n} Befehlen, damit {rob} {zu_ziel} kommt.",
    "{Rob} soll {zu_ziel} kommen, mit höchstens {n} Befehlen. Baue den Weg.",
    "{Rob} soll mit höchstens {n} Befehlen sein Ziel erreichen: {zu_ziel}.",
]

# Jede Frage nennt Roboter UND Ziel (SPEC-Rückmeldung: "Ein Befehl ist
# falsch. Tippe ihn an." allein verrät nicht, worum es geht) – durchgehend
# mit "kommen zu"/"soll zu" (Dativ, über _zu() korrekt verschmolzen), nie
# mit einem direkten Objekt wie "erreiche X" (bräuchte den Akkusativ, den
# die Themenwelt-Namen nicht in eigener Form mitbringen).
_REPARIEREN_Q = [
    "{Rob} soll {zu_ziel}, aber ein Befehl ist falsch. Tippe ihn an.",
    "Ein Befehl ist falsch, deshalb kommt {rob} nicht {zu_ziel}. Finde ihn.",
    "{Rob} soll {zu_ziel} kommen, aber ein Befehl passt nicht ins Programm. Tippe ihn an.",
    "Genau ein Befehl ist falsch, sonst würde {rob} {zu_ziel} kommen. Tippe ihn an.",
    "{Rob} soll {zu_ziel}. Ein Befehl im Programm ist falsch — welcher? Tippe ihn an.",
    "Ein Befehl im Programm ist vertauscht, deshalb kommt {rob} nicht {zu_ziel}. Tippe ihn an.",
]

_SCHLEIFE_Q = [
    "{Rob} befolgt ein Programm mit Wiederholungen. Auf welchem Feld hält er an?",
    "{Rob} führt ein Programm mit Wiederholungen aus. Wo hält er am Ende?",
    "Ein Teil des Programms wiederholt sich. Wo hält {rob} an?",
    "{Rob} wiederholt einen Teil seines Programms. Auf welchem Feld hält er an?",
    "Verfolge das Programm mit den Wiederholungen. Wo hält {rob} an?",
    "{Rob} läuft sein Programm mit Wiederholungen ab. Wo steht er danach?",
]

_ROBOTER_HINT = {
    "algo_finden": "Zähl, wie viele Schritte du bis zum Ziel brauchst.",
    "algo_reparieren": "Simulier das Programm Schritt für Schritt und schau, wo es schiefgeht.",
    "algo_schleife": "Zähl die Wiederholungen mit, dann den Rest.",
}

# Bei absoluten Befehlen (N/O/S/W) ist die Blickrichtung des Roboters egal,
# bei relativen (V/L/R) muss man sie mitverfolgen — der Hint unterscheidet
# deshalb nach befehlssatz statt fest an die Stufe gekoppelt zu sein
# (SPEC-Rückmeldung).
_BEFOLGEN_HINT = {
    "absolut": "Geh das Programm Befehl für Befehl durch und zeig mit dem Finger mit.",
    "relativ": "Merk dir nach jeder Drehung, wohin der Roboter schaut.",
}


def _bauer_algo_befolgen(stage, wid, index):
    seed = _seed("roboter", "algo_befolgen", stage, wid, index)
    erz = AK.erzeuge_befolgen(stage, seed, index)
    rob = THEMEN[wid]["roboter"]
    q = _BEFOLGEN_Q[index].format(Rob=_gross(rob), rob=rob)
    return dict(erz, q=q, hint=_BEFOLGEN_HINT[erz["befehlssatz"]])


def _bauer_algo_finden(stage, wid, index):
    seed = _seed("roboter", "algo_finden", stage, wid, index)
    erz = AK.erzeuge_finden(stage, seed, index)
    rob = THEMEN[wid]["roboter"]
    zu_ziel = _zu(THEMEN[wid]["ziel"])
    q = _FINDEN_Q[index].format(Rob=_gross(rob), rob=rob, n=erz["max_laenge"], zu_ziel=zu_ziel)
    return dict(erz, q=q, hint=_ROBOTER_HINT["algo_finden"])


def _bauer_algo_reparieren(stage, wid, index):
    seed = _seed("roboter", "algo_reparieren", stage, wid, index)
    erz = AK.erzeuge_reparieren(stage, seed, index)
    rob = THEMEN[wid]["roboter"]
    zu_ziel = _zu(THEMEN[wid]["ziel"])
    q = _REPARIEREN_Q[index].format(Rob=_gross(rob), rob=rob, zu_ziel=zu_ziel)
    return dict(erz, q=q, hint=_ROBOTER_HINT["algo_reparieren"])


def _bauer_algo_schleife(stage, wid, index):
    seed = _seed("roboter", "algo_schleife", stage, wid, index)
    erz = AK.erzeuge_schleife(stage, seed, index)
    rob = THEMEN[wid]["roboter"]
    q = _SCHLEIFE_Q[index].format(Rob=_gross(rob), rob=rob)
    return dict(erz, q=q, hint=_ROBOTER_HINT["algo_schleife"])


# Zwei Formulierungen je Richtung (normal/umkehr) – reine Sicherheitsmarge
# gegen zufällig gleiche Zahlenpaare innerhalb eines Pakets, wie bei komb_nim.
_MASCHINE_Q_NORMAL = [
    "{M} macht aus {x1} die Zahl {y1}, aus {x2} die Zahl {y2} und aus {x3} die Zahl {y3}. "
    "Was kommt bei {fx} heraus?",
    "{M} verwandelt {x1} in {y1}, {x2} in {y2} und {x3} in {y3}. Was wird aus {fx}?",
]
_MASCHINE_Q_UMKEHR = [
    "{M} macht aus {x1} die Zahl {y1}, aus {x2} die Zahl {y2} und aus {x3} die Zahl {y3}. "
    "Bei welcher Zahl kommt {fy} heraus?",
    "{M} verwandelt {x1} in {y1}, {x2} in {y2} und {x3} in {y3}. Welche Zahl wurde zu {fy}?",
]


def _bauer_algo_maschine(stage, wid, index):
    seed = _seed("maschine", "algo_maschine", stage, wid, index)
    erz = AK.erzeuge_maschine(stage, seed, index)
    m = _gross(THEMEN[wid]["maschine"])
    (x1, y1), (x2, y2), (x3, y3) = erz["paare"]
    variante = index % 2
    hint = ("Rechne den Weg der Maschine rückwärts." if erz["umkehr"] else
            "Was macht die Maschine mit jeder Zahl? Malnehmen, dazuzählen — oder beides nacheinander?")
    if erz["umkehr"]:
        q = _MASCHINE_Q_UMKEHR[variante].format(M=m, x1=x1, y1=y1, x2=x2, y2=y2, x3=x3, y3=y3,
                                                fy=erz["frage_y"])
    else:
        q = _MASCHINE_Q_NORMAL[variante].format(M=m, x1=x1, y1=y1, x2=x2, y2=y2, x3=x3, y3=y3,
                                                 fx=erz["frage_x"])

    if index % 2 == 0:
        optionen = [str(erz["antwort"])] + [str(a) for a in erz["ablenker"]]
        reihenfolge = list(range(4))
        random.Random(seed + 1).shuffle(reihenfolge)
        return {"type": "wahl", "q": q, "opts": [optionen[i] for i in reihenfolge],
                "correct": reihenfolge.index(0), "check": {"expr": erz["term"]}, "hint": hint}
    return {"type": "zahl", "q": q, "a": erz["antwort"], "check": {"expr": erz["term"]}, "hint": hint}


# ================================================================= V3-Bauer
# Ab hier die Bauer der V3 (ZIELE-V3.md): Geometrie, Legen, Punktmuster und
# reine Zahlenfolgen. Sie tragen zusätzlich einen Wiederholungsparameter
# `versuch`: Gleicht der Fragetext einer Aufgabe zufällig dem einer anderen im
# selben Paket (check_unit lehnt das ab), würfelt baue_paket sie mit einem
# anderen, ebenfalls festen Seed neu — Versuch 0 ist immer der Grundseed.

def _mit_versuch(fn):
    """Markiert einen Bauer als wiederholbar (siehe baue_paket)."""
    fn.mit_versuch = True
    return fn


def _seed_index(index, versuch):
    """Der Index im Seed-Text: bei Versuch 0 unverändert (derselbe Aufruf
    liefert dasselbe Paket wie ohne Wiederholungslogik), sonst mit Marke."""
    return index if versuch == 0 else f"{index}#{versuch}"


def _geo_bauer(sid):
    @_mit_versuch
    def bauer(stage, wid, index, versuch=0):
        seed = _seed("geo", sid, stage, wid, _seed_index(index, versuch))
        return GEO.baue_aufgabe(sid, stage, index, seed)
    bauer.__name__ = f"_bauer_{sid}"
    return bauer


def _legen_bauer(sid):
    @_mit_versuch
    def bauer(stage, wid, index, versuch=0):
        seed = _seed("legen", sid, stage, wid, _seed_index(index, versuch))
        return LK.baue_aufgabe(sid, stage, index, seed)
    bauer.__name__ = f"_bauer_{sid}"
    return bauer


@_mit_versuch
def _bauer_must_figur(stage, wid, index, versuch=0):
    seed = _seed("figur", "must_figur", stage, wid, _seed_index(index, versuch))
    return FK.baue_aufgabe("must_figur", stage, index, seed)


# ------------------------------------------------------- reine Zahlenfolgen
# Frage ohne Geschichte (ZIELE-V3.md G2): "3, 5, 9, 17, … Welche Zahl kommt als
# Nächstes?". Glieder, Fortsetzung und Ablenker kommen aus
# raetsel_kern.erzeuge_folge, der Prüfterm aus generate_units._folge_term —
# dieselben Helfer wie der alte Folgen-Pfad, nur ohne Sprachmodell-Verkleidung.

# Fertigkeit -> (Regeltyp, kürzeste erlaubte Folge, Bedingung an die Regel).
# Die Bedingung schärft die Beschreibung der Fertigkeit nach: der Kern würfelt
# die Schrittweite von +2 bis +9, "Schritt +1 oder +2" (must_einfach) und
# "Schrittweite finden" (must_schritt) sind aber zwei verschiedene Dinge.
_FOLGEN = {
    "must_einfach": ("plus", 4, lambda regel: regel["d"] <= 3),
    "must_schritt": ("plus", 4, lambda regel: regel["d"] >= 3),
    "must_rueck": ("plus", 4, lambda regel: True),
    "must_wechsel": ("wechsel", 5, lambda regel: True),
    "must_verdopp": ("mal", 4, lambda regel: True),
    "must_fibo": ("fibo", 5, lambda regel: True),
}

# Größter Wert, der in einer Folge vorkommt (Glieder, Fortsetzung, Ablenker).
# Der Zahlenraum der Stufe wäre bei Stufe 5-6 bis 1000 bzw. 10000 und ließe den
# Kern vierstellige Startwerte würfeln ("9176, 9183, 9191, …"): das wäre
# Leselast und Rechenlast statt Denkaufgabe (Schwierigkeit ist Denktiefe, nie
# Zahlengröße, ZIELE-V2.md D2). Die Stufe bleibt die Obergrenze, wo sie kleiner
# ist (Stufe 1-2: bis 20). Nur das Verdoppeln braucht mehr Luft: bei 100 gäbe es
# nur eine Handvoll verschiedener Folgen, und die Pakete wiederholten sich.
FOLGEN_ZAHLENRAUM = 100
FOLGEN_ZAHLENRAUM_MAL = 1000

_FOLGEN_HINT = {
    "must_einfach": "Wie viel kommt von Zahl zu Zahl dazu?",
    "must_schritt": "Wie groß ist der Sprung von einer Zahl zur nächsten?",
    "must_rueck": "Um wie viel wird es von Zahl zu Zahl weniger?",
    "must_wechsel": "Die Sprünge wechseln sich ab. Welcher ist als Nächstes dran?",
    "must_verdopp": "Mit welcher Zahl wird von Glied zu Glied malgenommen?",
    "must_fibo": "Wie ergibt sich jede Zahl aus den beiden davor?",
}


def _folgen_max(sid, stage):
    raum = FOLGEN_ZAHLENRAUM_MAL if sid == "must_verdopp" else FOLGEN_ZAHLENRAUM
    return min(C.max_value(stage), raum)


def _folge_frage(glieder):
    return ", ".join(str(g) for g in glieder) + ", … Welche Zahl kommt als Nächstes?"


def _rueck_ablenker(glieder, naechstes, d, max_wert, seed):
    """Drei falsche Fortsetzungen für eine absteigende Folge: typische
    Kinderfehler zuerst (um eins daneben, Sprung vergessen, Sprung doppelt),
    nie negativ, nie die Lösung."""
    letztes = glieder[-1]
    kandidaten = [naechstes - 1, naechstes + 1, letztes, naechstes - d, letztes - 2 * d,
                  letztes + d, naechstes + 2]
    gewaehlt = []
    for k in kandidaten:
        if k != naechstes and 0 <= k <= max_wert and k not in gewaehlt:
            gewaehlt.append(k)
        if len(gewaehlt) == 3:
            break
    if len(gewaehlt) < 3:
        raise ValueError(f"zu wenige Ablenker für {glieder} -> {naechstes}")
    random.Random(seed).shuffle(gewaehlt)
    return gewaehlt


def _folge_kern(sid, stage, seed_basis, index, versuch):
    """Sucht (deterministisch, mit wachsendem Seed-Versatz) eine Folge, die
    lang genug ist und die Bedingung der Fertigkeit erfüllt. Rückgabe: der
    Kern aus raetsel_kern (für must_rueck: die VORWÄRTS-Folge mit einem Glied
    mehr, sie wird erst beim Bauen umgedreht)."""
    import generate_units as GU   # erst hier: Ringimport vermeiden (siehe Kopf)
    regeltyp, mindest, bedingung = _FOLGEN[sid]
    max_wert = _folgen_max(sid, stage)
    for versatz in range(400):
        seed = seed_basis + 7919 * versuch + versatz
        try:
            # Für must_rueck eine Stelle länger: das vorderste Glied der
            # Vorwärtsfolge ist am Ende die gesuchte Fortsetzung.
            kern = GU._erzeuge_folge_sicher(regeltyp, seed, max_wert,
                                            laenge_start=6 if sid == "must_rueck" else 5)
        except ValueError:
            continue
        laenge = len(kern["glieder"]) - (1 if sid == "must_rueck" else 0)
        if laenge >= mindest and bedingung(kern["regel"]):
            return kern
    raise ValueError(f"{sid}@{stage}: keine passende Folge gefunden")


def _folgen_bauer(sid):
    @_mit_versuch
    def bauer(stage, wid, index, versuch=0):
        import generate_units as GU
        seed = _seed("folge", sid, stage, wid, index)
        kern = _folge_kern(sid, stage, seed, index, versuch)
        max_wert = _folgen_max(sid, stage)
        if sid == "must_rueck":
            vorwaerts = kern["glieder"]
            if not K.pruefe_folge(vorwaerts, kern["naechstes"], kern["regel"]):
                raise ValueError(f"{sid}: Kern prüft die eigene Folge nicht")
            d = kern["regel"]["d"]
            glieder = vorwaerts[:0:-1]          # absteigend, ohne das vorderste Glied
            naechstes = vorwaerts[0]
            term = f"{glieder[-1]}-{d}"
            ablenker = _rueck_ablenker(glieder, naechstes, d, max_wert, seed + versuch)
        else:
            glieder, naechstes = kern["glieder"], kern["naechstes"]
            term = GU._folge_term(kern)
            ablenker = kern["ablenker"]
        q = _folge_frage(glieder)
        hint = _FOLGEN_HINT[sid]
        if index % 2 == 0:       # abwechselnd wahl und zahl, wie bisher
            optionen = [str(naechstes)] + [str(a) for a in ablenker]
            reihenfolge = list(range(len(optionen)))
            random.Random(seed + 1).shuffle(reihenfolge)
            return {"type": "wahl", "q": q, "opts": [optionen[i] for i in reihenfolge],
                    "correct": reihenfolge.index(0), "check": {"expr": term}, "hint": hint}
        return {"type": "zahl", "q": q, "a": naechstes, "check": {"expr": term}, "hint": hint}
    bauer.__name__ = f"_bauer_{sid}"
    return bauer


# --------------------------------------------------------- Titel und Einstieg

_TITEL = {
    "geo_spiegel": "Spiegeln im Kopf", "geo_drehen": "Drehen im Kopf",
    "geo_wuerfel": "Würfelgebäude", "must_matrix": "Bildmatrix",
    "must_analogie": "Analogien", "log_position": "Wer steht wo?",
    "komb_nim": "Der letzte Stein",
    "algo_befolgen": "Befehle befolgen", "algo_finden": "Weg programmieren",
    "algo_reparieren": "Fehler reparieren", "algo_maschine": "Zahlenmaschine",
    "algo_schleife": "Wiederholen",
    # V3 (ZIELE-V3.md)
    "geo_ansicht": "Von allen Seiten", "geo_netzfalten": "Netze falten",
    "geo_flaeche_umfang": "Fläche und Umfang", "geo_quader": "Quader füllen",
    "geo_karte": "Schatzkarte",
    "komb_reihen": "Reihenfolgen legen", "komb_paare": "Paare und Auswahlen",
    "must_figur": "Punktmuster", "log_reihen": "Wer steht wo?",
    "must_einfach": "Was kommt danach?", "must_schritt": "Schrittweite finden",
    "must_rueck": "Rückwärts zählen", "must_wechsel": "Wechselnde Regel",
    "must_verdopp": "Verdoppeln", "must_fibo": "Zahlen bauen Zahlen",
}

# {willkommen} kommt aus THEMEN[wid]["willkommen"] – ein je Welt von Hand
# grammatisch korrekt formulierter Satz ("Willkommen in der Blockwelt!",
# "Willkommen beim Burgenbau!", ...), NICHT die mechanische Floskel
# "Willkommen in {welt}!" (SPEC-Rückmeldung: "Willkommen in Baukasten!" ist
# falsches Deutsch, jede Welt braucht ihre eigene Präposition/ihren Kasus).
_INTRO = {
    "geo_spiegel": "{willkommen} Hier spiegelst du Figuren im Kopf.",
    "geo_drehen": "{willkommen} Hier drehst du Figuren im Kopf.",
    "geo_wuerfel": "{willkommen} Zähl Würfel, auch die versteckten.",
    "must_matrix": "{willkommen} Finde die Regel im Bildmuster.",
    "must_analogie": "{willkommen} Finde die geheime Umwandlung.",
    "log_position": "{willkommen} Finde heraus, wer wo steht.",
    "komb_nim": "{willkommen} Denk dir eine Gewinnstrategie aus.",
    "algo_befolgen": "{willkommen} Befolge das Programm des Roboters.",
    "algo_finden": "{willkommen} Programmier den Roboter zum Ziel.",
    "algo_reparieren": "{willkommen} Finde den einen falschen Befehl.",
    "algo_maschine": "{willkommen} Knack die Regel der Maschine.",
    "algo_schleife": "{willkommen} Lies Programme mit Wiederholungen.",
    # V3 (ZIELE-V3.md)
    "geo_ansicht": "{willkommen} Sieh das Gebäude von oben, vorne und rechts.",
    "geo_netzfalten": "{willkommen} Falte Netze im Kopf zu Würfeln.",
    "geo_flaeche_umfang": "{willkommen} Miss Fläche und Umfang. Papier ist erlaubt.",
    "geo_quader": "{willkommen} Finde heraus, was zum vollen Quader fehlt.",
    "geo_karte": "{willkommen} Finde den Schatz auf der Karte. Papier ist erlaubt.",
    "komb_reihen": "{willkommen} Lege alle Reihenfolgen und finde keine doppelt.",
    "komb_paare": "{willkommen} Lege alle Paare und Auswahlen und zähle sie.",
    "must_figur": "{willkommen} Erkenne, wie die Punktbilder wachsen.",
    "log_reihen": "{willkommen} Finde heraus, wer wo in der Reihe steht.",
    "must_einfach": "{willkommen} Setze die Zahlenreihe fort.",
    "must_schritt": "{willkommen} Finde den Sprung in der Zahlenreihe.",
    "must_rueck": "{willkommen} Zähle in der Zahlenreihe rückwärts.",
    "must_wechsel": "{willkommen} Die Sprünge in der Reihe wechseln sich ab.",
    "must_verdopp": "{willkommen} Die Zahlen wachsen immer schneller.",
    "must_fibo": "{willkommen} Jede Zahl entsteht aus den beiden davor.",
}


# ------------------------------------------------------------------ Paketbau

KERN_SKILLS = {
    "geo_spiegel": _bauer_geo_spiegel,
    "geo_drehen": _bauer_geo_drehen,
    "geo_wuerfel": _bauer_geo_wuerfel,
    "must_matrix": _bauer_must_matrix,
    "must_analogie": _bauer_must_analogie,
    "log_position": _bauer_log_position,
    "komb_nim": _bauer_komb_nim,
    "algo_befolgen": _bauer_algo_befolgen,
    "algo_finden": _bauer_algo_finden,
    "algo_reparieren": _bauer_algo_reparieren,
    "algo_maschine": _bauer_algo_maschine,
    "algo_schleife": _bauer_algo_schleife,
    # V3 (ZIELE-V3.md). Die Reihenfolge steht fest: _alle_pakete_plan() lässt
    # die Welt über den Plan rotieren, neue Einträge gehören ans Ende, damit
    # die Welten schon gebauter Pakete nicht verrutschen.
    "geo_ansicht": _geo_bauer("geo_ansicht"),
    "geo_netzfalten": _geo_bauer("geo_netzfalten"),
    "geo_flaeche_umfang": _geo_bauer("geo_flaeche_umfang"),
    "geo_quader": _geo_bauer("geo_quader"),
    "geo_karte": _geo_bauer("geo_karte"),
    "komb_reihen": _legen_bauer("komb_reihen"),
    "komb_paare": _legen_bauer("komb_paare"),
    "must_figur": _bauer_must_figur,
    "log_reihen": _bauer_log_reihen,
    "must_einfach": _folgen_bauer("must_einfach"),
    "must_schritt": _folgen_bauer("must_schritt"),
    "must_rueck": _folgen_bauer("must_rueck"),
    "must_wechsel": _folgen_bauer("must_wechsel"),
    "must_verdopp": _folgen_bauer("must_verdopp"),
    "must_fibo": _folgen_bauer("must_fibo"),
}

# Die V3-Fertigkeiten, die neu gebaut oder auf den Kern umgestellt wurden
# (bei den umgestellten liegt eine alte Fassung im Bestand: --force + Fundus).
V3_SKILLS = ("geo_ansicht", "geo_netzfalten", "geo_flaeche_umfang", "geo_quader", "geo_karte",
             "komb_reihen", "komb_paare", "must_figur", "log_reihen",
             "must_einfach", "must_schritt", "must_rueck", "must_wechsel", "must_verdopp",
             "must_fibo")


def hat_kern(sid):
    """True, wenn diese Fertigkeit über diesen deterministischen Pfad läuft
    (generate_units.pfad_von() fragt genau das ab)."""
    return sid in KERN_SKILLS


VERSUCHE = 12   # höchstens so viele Seeds pro Aufgabe, wenn die Frage schon vorkommt


def _frage_von(task):
    """Der Fragetext, wie check_unit ihn vergleicht (None bei Typen ohne q)."""
    q = task.get("q") if isinstance(task, dict) else None
    return q.strip().lower() if isinstance(q, str) else None


# Der Geometrie-Kern kennt für manche Fragen nur drei Schablonen, die über den
# Paket-Index rotieren (geo_kern._vorlage): Aufgabe 0 und 3 lauten dann
# wortgleich, obwohl die Bilder verschieden sind. check_unit lehnt zwei gleiche
# Fragen im Paket aber ab, und ein anderer Seed ändert an der Schablone nichts.
# Deshalb bekommt die zweite (dritte, …) Aufgabe einen kurzen Vorspann; der
# Kern bleibt unberührt, die Wahrheit steht nicht im Fragetext.
_VORSPANN = ["Noch eins: ", "Und jetzt: ", "Nächstes Bild: ", "Weiter geht's: ", "Probier das: ",
             "Zum Schluss: "]


def _fragen_unterscheiden(tasks):
    """Macht wortgleiche Fragen im Paket unterscheidbar (siehe oben).
    Die erste Aufgabe mit einem Fragetext behält ihn unverändert."""
    gesehen, neu = set(), []
    for task in tasks:
        q = task.get("q") if isinstance(task, dict) else None
        if isinstance(q, str) and q.strip().lower() in gesehen:
            for vorspann in _VORSPANN:
                if (vorspann + q).strip().lower() not in gesehen:
                    task = dict(task, q=vorspann + q)
                    break
        if isinstance(task, dict) and isinstance(task.get("q"), str):
            gesehen.add(task["q"].strip().lower())
        neu.append(task)
    return neu


def baue_paket(sid, stage, wid):
    """Baut ein vollständiges, geprüftes 6-Aufgaben-Paket. Rückgabe:
    (unit|None, log) — dieselbe Form wie generate_units._make_unit_
    logikgitter()/_make_unit_folgen(), damit generate_units.make_unit() sie
    unverändert weiterreichen kann. Bei einem Mangel wird NICHTS
    zurückgegeben (unit=None) statt eine fehlerhafte Aufgabe scheinbar
    'irgendwie' auszuliefern — der Aufrufer entscheidet, wie laut er das
    meldet (die CLI unten bricht sofort ab)."""
    bauer = KERN_SKILLS.get(sid)
    if bauer is None:
        return None, [f"{sid!r} hat keinen Kern-Bauer (siehe KERN_SKILLS)"]

    welt = C.world(wid)
    if welt is None:
        return None, [f"unbekannte Themenwelt {wid!r}"]

    try:
        tasks, fragen = [], set()
        for index in range(6):
            task = bauer(stage, wid, index)
            # Zwei Aufgaben mit demselben Fragetext lehnt check_unit ab. Wo der
            # Bauer wiederholbar ist, wird die doppelte Aufgabe mit einem anderen
            # (festen) Seed neu gewürfelt, statt das ganze Paket zu verwerfen.
            if getattr(bauer, "mit_versuch", False):
                for versuch in range(1, VERSUCHE):
                    if _frage_von(task) not in fragen:
                        break
                    task = bauer(stage, wid, index, versuch=versuch)
            fragen.add(_frage_von(task))
            tasks.append(task)
        tasks = _fragen_unterscheiden(tasks)
    except (ValueError, KeyError) as e:
        return None, [f"{sid}@{stage}·{wid}: Kern konnte keine gültige Aufgabe erzeugen: {e}"]

    unit = {
        "skill": sid, "stage": stage, "world": wid,
        "title": f"{_TITEL[sid]} · {welt['title']}"[:40],
        "intro": _INTRO[sid].format(willkommen=THEMEN[wid]["willkommen"]),
        "tasks": tasks,
    }
    problems = V.check_unit(unit)
    if problems:
        return None, [f"{sid}@{stage}·{wid}: " + " | ".join(problems[:5])]
    return unit, [f"{sid}@{stage}·{wid}: ok ({len(tasks)} Aufgaben)"]


def _alle_pakete_plan():
    """Plant alle Kern-Pakete (jede Fertigkeit auf ihrer Stufe und Stufe+1),
    Welt rotierend über einen laufenden Index über ALLE Pakete hinweg (SPEC
    §8) – nicht neu beginnend bei jeder Fertigkeit, sonst bekämen alle
    Fertigkeiten immer dieselbe erste Welt."""
    plan, i = [], 0
    for sid in KERN_SKILLS:
        sk = C.skill(sid)
        for stage in (sk["stage"], sk["stage"] + 1):
            plan.append((sid, stage, C.WORLD_IDS[i % len(C.WORLD_IDS)]))
            i += 1
    return plan


# ------------------------------------------------------------------------ CLI

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alle", action="store_true", help="jedes fehlende Kern-Paket bauen")
    ap.add_argument("--skill", help="nur diese Fertigkeit")
    ap.add_argument("--stage", type=int, help="Stufe (Standard: die eigene Stufe der Fertigkeit)")
    ap.add_argument("--world", help="Themenwelt (Standard bei --skill: erste Welt)")
    ap.add_argument("--klasse", type=int,
                    help="mit --alle nur die Stufen bauen, die diese Schulklasse braucht "
                         "(siehe KLASSEN in curriculum.py)")
    ap.add_argument("--force", action="store_true",
                    help="auch schon vorhandene Pakete ersetzen; die alte Fassung "
                         "wandert dabei in den Fundus, sie geht nicht verloren")
    ap.add_argument("--dry-run", action="store_true", help="nur den Bauplan zeigen")
    ap.add_argument("--nur", help="mit --alle nur diese Fertigkeiten (Komma getrennt); "
                                  "die Welt rotiert trotzdem über den ganzen Plan")
    a = ap.parse_args()

    # Ein Tippfehler in --world lief bisher bis in ein 'NoneType'-Problem
    # mitten im Bauplan. Lieber hier abbrechen, mit der Liste dabei.
    if a.world and C.world(a.world) is None:
        raise SystemExit(f"unbekannte Themenwelt: {a.world!r}\n"
                         f"gültig sind: {', '.join(C.WORLD_IDS)}")

    if a.alle:
        plan = _alle_pakete_plan()
        if a.nur:
            nur = {x.strip() for x in a.nur.split(",") if x.strip()}
            unbekannt = sorted(nur - set(KERN_SKILLS))
            if unbekannt:
                raise SystemExit(f"--nur: keine Kern-Fertigkeit: {', '.join(unbekannt)}")
            plan = [e for e in plan if e[0] in nur]
        if a.klasse:
            band = set(C.klasse_band(a.klasse))
            plan = [e for e in plan if e[1] in band]
            print(f"Klasse {a.klasse}: Stufen {','.join(map(str, sorted(band)))} "
                  f"— {len(plan)} von {len(_alle_pakete_plan())} Kern-Paketen")
    elif a.skill:
        if not hat_kern(a.skill):
            raise SystemExit(f"{a.skill!r} ist keine Kern-Fertigkeit (siehe KERN_SKILLS in "
                             "kern_pakete.py)")
        sk = C.skill(a.skill)
        if sk is None:
            raise SystemExit(f"unbekannte Fertigkeit: {a.skill}")
        stage = a.stage if a.stage is not None else sk["stage"]
        wid = a.world or C.WORLD_IDS[0]
        plan = [(a.skill, stage, wid)]
    else:
        raise SystemExit("--alle oder --skill angeben")

    print(f"{len(plan)} Kern-Pakete geplant")
    if a.dry_run:
        for sid, stage, wid in plan:
            print(f'   {sid:16s} Stufe {stage}  {C.world(wid)["title"]:12s}')
        return 0

    # Erst hier, innerhalb von main(): kern_pakete.py bleibt so auch ohne
    # generate_units.py vollständig importierbar (siehe Modul-Docstring).
    import generate_units as GU

    have = {}
    if SEED_OUT.exists():
        have = {u["skill"] + "@" + str(u["stage"]): u
                for u in json.loads(SEED_OUT.read_text("utf-8")).get("units", [])}

    gebaut = 0
    for sid, stage, wid in plan:
        key = f"{sid}@{stage}"
        if key in have and a.force:
            ab = F.lege_paket_ab(have[key])
            if ab:
                print(f"   [ar] alte Fassung im Fundus: {ab.relative_to(ROOT)}")
        if key in have and not a.force:
            print(f"[=] {key} vorhanden")
            continue
        print(f'[..] {key} · {C.world(wid)["title"]}')
        unit, log = baue_paket(sid, stage, wid)
        if unit is None:
            # Kein Fehler erreicht das Kind: nicht schreiben, sondern laut
            # abbrechen (Leitplanke §0.1) – ein deterministischer Kern, der
            # scheitert, ist ein Programmierfehler, kein Anlass zum Retry.
            raise SystemExit(f"[xx] {key} verworfen: " + (log[-1] if log else "unbekannter Fehler"))
        have[key] = unit
        GU.notiere("neu", sid, stage, "vorratsluecke",
                   {"n": 1, "aufgaben": len(unit["tasks"]), "welt": wid})
        GU.write_units(SEED_OUT, list(have.values()))
        gebaut += 1
        print(f'     [ok] {unit["title"]} ({len(unit["tasks"])} Aufgaben)')

    print(f"\n{gebaut} Pakete gebaut, {len(have)} insgesamt in {SEED_OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
