# -*- coding: utf-8 -*-
"""Der Lehrplan von MathCraft: Bereiche, Fertigkeiten, Stufen.

Diese Datei ist die Wahrheit für alles andere. Der Generator sagt dem Modell
anhand dieser Angaben, was es bauen soll; der Validator prüft jede erzeugte
Aufgabe dagegen. Beide lesen dieselben Zahlen — sonst driften Anspruch und
Prüfung auseinander.

  .venv/bin/python build/curriculum.py     # Übersicht ausgeben
"""

# ------------------------------------------------------------------- Stufen
# Acht Stufen von "erste Woche der 2. Klasse" bis "Knobelaufgabe, an der auch
# Erwachsene sitzen". Der Einstieg ist bewusst leicht: Wer sich am ersten Tag
# blamiert, macht am zweiten nicht weiter. Ab Stufe 5 geht es über den
# Klassenstoff hinaus — dafür ist die App da.
STAGES = {
    1: dict(name="Erste Schritte",  max_value=20,      grade="Anfang Klasse 2"),
    2: dict(name="Sicher bis 20",   max_value=20,      grade="Klasse 2"),
    3: dict(name="Der Hunderter",   max_value=100,     grade="Klasse 2"),
    4: dict(name="Mal und Geteilt", max_value=100,     grade="Ende Klasse 2"),
    5: dict(name="Der Tausender",   max_value=1000,    grade="Klasse 3"),
    6: dict(name="Große Zahlen",    max_value=10000,   grade="Klasse 4"),
    7: dict(name="Zahlenforscher",  max_value=100000,  grade="Klasse 5/6"),
    8: dict(name="Meisterprüfung",  max_value=1000000, grade="Knobelolympiade"),
}
MAX_STAGE = max(STAGES)

# Rechenarten, die ab welcher Stufe überhaupt vorkommen dürfen. Der Validator
# lehnt alles ab, was zu früh auftaucht — ein Modell schreibt sonst gern mal
# eine Division in eine Additionsaufgabe für Stufe 1.
OP_FROM_STAGE = {"+": 1, "-": 1, "*": 3, "/": 4, "^": 7}


# ------------------------------------------------------------------ Bereiche
# Elf Bereiche = elf Welten auf der Landkarte. Die Reihenfolge ist die
# Reiseroute; die Emojis sind der Wiedererkennungswert auf der Karte.
AREAS = [
    dict(id="zahl",  emoji="🔢", title="Zahlenland",       sub="Zahlen lesen, ordnen, zerlegen"),
    dict(id="plus",  emoji="➕", title="Plus & Minus",      sub="Zusammenzählen und abziehen"),
    dict(id="mal",   emoji="✖️", title="Mal & Geteilt",     sub="Malnehmen, teilen, Reste"),
    dict(id="muster",emoji="🌀", title="Muster & Folgen",   sub="Die Regel dahinter finden"),
    dict(id="geo",   emoji="📐", title="Formen & Räume",    sub="Figuren, Symmetrie, Körper"),
    dict(id="logik", emoji="🧠", title="Knobelwelt",        sub="Denksport und Rätsel"),
    dict(id="algo",  emoji="🤖", title="Roboterwerkstatt",  sub="Befehle geben, Wege planen, Fehler finden"),
    dict(id="komb",  emoji="🎲", title="Möglichkeiten",     sub="Wie viele Wege gibt es?"),
    dict(id="groess",emoji="📏", title="Messen & Wiegen",   sub="Zeit, Geld, Länge, Gewicht"),
    dict(id="daten", emoji="📊", title="Daten & Tabellen",  sub="Diagramme lesen und deuten"),
    dict(id="geheim",emoji="🔐", title="Zahlengeheimnisse", sub="Gerade, ungerade, Teiler, Primzahlen"),
    dict(id="sach",  emoji="📖", title="Sachaufgaben",      sub="Rechnen in echten Geschichten"),
]
AREA_IDS = [a["id"] for a in AREAS]


# ----------------------------------------------------------- Themenwelten
# Die Einkleidung der Aufgaben. Nur Sprache, keine Logos und keine Grafiken aus
# den Spielen — die Bilder der App werden selbst erzeugt. Reine Privatnutzung.
# Der Tutor merkt sich, in welcher Welt am besten gearbeitet wird, und
# gewichtet danach; Abwechslung bleibt trotzdem Pflicht.
WORLDS = [
    dict(id="minecraft", title="Blockwelt",    hook="Blöcke, Erz, Truhen, Bauen, Craften"),
    dict(id="brawl",     title="Arena",        hook="Kämpfer, Punkte, Kisten, Trophäen"),
    dict(id="clash",     title="Burgenbau",    hook="Gold, Elixier, Truppen, Rathaus, Bauzeiten"),
    dict(id="fussball",  title="Fußball",      hook="Tore, Tabelle, Trikots, Trainingslager"),
    dict(id="roblox",    title="Baukasten",    hook="Level, Münzen, Obby, Freunde einladen"),
    dict(id="pokemon",   title="Sammelmonster",hook="Sammeln, Tauschen, Entwicklungsstufen, Bonbons"),
    dict(id="weltraum",  title="Weltraum",     hook="Raketen, Planeten, Astronauten, Countdown"),
    dict(id="dino",      title="Dinozeit",     hook="Ausgrabung, Knochen, Urzeit, Forscher"),
    dict(id="rennen",    title="Rennstrecke",  hook="Runden, Boxenstopp, Zeiten, Tuning"),
    dict(id="ninja",     title="Ninja",        hook="Parcours, Sprünge, Schriftrollen, Training"),
]
WORLD_IDS = [w["id"] for w in WORLDS]


def world(wid):
    for w in WORLDS:
        if w["id"] == wid:
            return w
    return None


# ------------------------------------------------------------- Fertigkeiten
# (id, Bereich, Stufe, Titel, erlaubte Aufgabentypen, Auftrag an den Generator)
#
# Der Auftrag ist der wichtigste Teil: Er steht später fast wörtlich im Prompt.
# Je konkreter er ist, desto weniger Ausschuss produziert das Modell.
_S = [
 # ---- Zahlenland ----------------------------------------------------------
 ("zahl_bis20",     "zahl",   1, "Zahlen bis 20",          ["zahl","wahl","ordnen"],
  "Zahlen bis 20 erkennen, vergleichen und der Größe nach ordnen."),
 ("zahl_nachbar",   "zahl",   2, "Nachbarzahlen",          ["zahl","wahl"],
  "Vorgänger und Nachfolger einer Zahl bis 20 nennen."),
 ("zahl_bis100",    "zahl",   3, "Zahlen bis 100",         ["zahl","wahl","ordnen"],
  "Zahlen bis 100 lesen, vergleichen und ordnen."),
 ("zahl_stellen",   "zahl",   3, "Zehner und Einer",       ["zahl","wahl"],
  "Eine zweistellige Zahl in Zehner und Einer zerlegen (47 = 4 Zehner und 7 Einer)."),
 ("zahl_bis1000",   "zahl",   5, "Zahlen bis 1000",        ["zahl","wahl","ordnen"],
  "Dreistellige Zahlen lesen, ordnen und in Hunderter/Zehner/Einer zerlegen."),
 ("zahl_runden",    "zahl",   5, "Runden",                 ["zahl","wahl"],
  "Auf den nächsten Zehner oder Hunderter runden."),
 ("zahl_gross",     "zahl",   6, "Große Zahlen",           ["zahl","wahl","ordnen"],
  "Zahlen bis 10000 lesen, ordnen und im Stellenwert zerlegen."),
 ("zahl_roemisch",  "zahl",   7, "Römische Zahlen",        ["zahl","wahl"],
  "Römische Zahlzeichen bis 100 lesen und umwandeln."),

 # ---- Plus & Minus --------------------------------------------------------
 ("plus_bis10",     "plus",   1, "Plus bis 10",            ["zahl","wahl","wahrfalsch"],
  "Addieren und subtrahieren im Zahlenraum bis 10, ohne Übergang."),
 ("plus_bis20",     "plus",   2, "Plus bis 20",            ["zahl","wahl","wahrfalsch"],
  "Addieren und subtrahieren bis 20, auch mit Zehnerübergang (8+5, 13-6)."),
 ("plus_luecke",    "plus",   2, "Was fehlt?",             ["zahl"],
  "Die fehlende Zahl finden: 7 + ? = 15."),
 ("plus_bis100",    "plus",   3, "Plus bis 100",           ["zahl","wahl"],
  "Zweistellig plus/minus einstellig und volle Zehner bis 100."),
 ("plus_uebergang", "plus",   4, "Zehnerübergang",         ["zahl","wahl"],
  "Zweistellig plus zweistellig mit Übergang (47+38, 63-27)."),
 ("plus_bis1000",   "plus",   5, "Plus bis 1000",          ["zahl"],
  "Halbschriftlich addieren und subtrahieren im Tausenderraum."),
 ("plus_tricks",    "plus",   5, "Rechentricks",           ["zahl","wahl","wahrfalsch"],
  "Geschickt rechnen: 99 addieren als 100 minus 1, Zahlen passend zerlegen."),
 ("plus_gross",     "plus",   6, "Große Summen",           ["zahl"],
  "Vierstellige Zahlen addieren und subtrahieren."),

 # ---- Mal & Geteilt -------------------------------------------------------
 ("mal_einstieg",   "mal",    3, "Malnehmen verstehen",    ["entdecken","zahl","wahl"],
  "Malnehmen als wiederholtes Zusammenzählen begreifen (3 Reihen zu 4)."),
 ("mal_kleine",     "mal",    3, "Die kleinen Reihen",     ["zahl","wahrfalsch"],
  "Einmaleins mit 2, 5 und 10."),
 ("mal_alle",       "mal",    4, "Das ganze Einmaleins",   ["zahl","wahrfalsch"],
  "Alle Reihen des kleinen Einmaleins bis 10 mal 10."),
 ("mal_teilen",     "mal",    4, "Teilen",                 ["zahl","wahl"],
  "Durch Zahlen bis 10 teilen, Ergebnis geht glatt auf."),
 ("mal_rest",       "mal",    5, "Teilen mit Rest",        ["zahl","mehrschritt"],
  "Teilen mit Rest (17 geteilt durch 5 ist 3 Rest 2)."),
 ("mal_gross",      "mal",    5, "Großes Einmaleins",      ["zahl"],
  "Zweistellig mal einstellig (24 mal 6)."),
 ("mal_zweistell",  "mal",    6, "Mal zweistellig",        ["zahl"],
  "Zweistellig mal zweistellig."),
 ("mal_potenz",     "mal",    7, "Quadratzahlen",          ["zahl","wahl"],
  "Quadratzahlen bis 20 mal 20 und ihre Muster."),

 # ---- Muster & Folgen -----------------------------------------------------
 ("must_einfach",   "muster", 1, "Was kommt danach?",      ["zahl","wahl"],
  "Einfache Zahlenfolge fortsetzen, Schritt +1 oder +2."),
 ("must_schritt",   "muster", 2, "Schrittweite finden",    ["zahl","wahl"],
  "Folgen mit gleichbleibendem Schritt fortsetzen (3, 6, 9, ...)."),
 ("must_form",      "muster", 2, "Formenmuster",           ["gitter","wahl"],
  "Ein sich wiederholendes Muster aus Formen oder Farben fortsetzen."),
 ("must_rueck",     "muster", 3, "Rückwärts",              ["zahl","wahl"],
  "Absteigende Folgen fortsetzen (30, 25, 20, ...)."),
 ("must_wechsel",   "muster", 5, "Wechselnde Regel",       ["zahl","wahl"],
  "Folgen mit abwechselnder Regel (+2, dann mal 2)."),
 ("must_verdopp",   "muster", 5, "Verdoppeln",             ["zahl","wahl"],
  "Folgen, die sich verdoppeln oder halbieren."),
 ("must_fibo",      "muster", 7, "Zahlen bauen aufeinander",["zahl","wahl"],
  "Folgen, bei denen sich jede Zahl aus den beiden davor ergibt."),
 ("must_figur",     "muster", 7, "Figurierte Zahlen",      ["zahl","gitter"],
  "Dreieckszahlen und Quadratzahlen als wachsende Muster erkennen."),
 ("must_matrix",     "muster", 4, "Bildmatrix",             ["bildwahl"],
  "In einem 3×3-Bildmuster die Regeln erkennen und das fehlende Bild finden."),
 ("must_analogie",   "muster", 6, "Analogien",              ["bildwahl"],
  "A verhält sich zu B wie C zu ? — die Umwandlung erkennen und übertragen."),

 # ---- Formen & Räume ------------------------------------------------------
 ("geo_formen",     "geo",    1, "Formen erkennen",        ["wahl","gitter"],
  "Kreis, Dreieck, Viereck und Rechteck sicher unterscheiden."),
 ("geo_symm",       "geo",    2, "Symmetrie",              ["gitter","wahl"],
  "Spiegelachsen erkennen und eine Figur symmetrisch ergänzen."),
 ("geo_zaehl",      "geo",    3, "Ecken und Kanten",       ["zahl","wahl"],
  "Ecken, Kanten und Flächen von Figuren und Körpern zählen."),
 ("geo_umfang",     "geo",    4, "Umfang",                 ["zahl","mehrschritt"],
  "Umfang von Rechtecken und zusammengesetzten Figuren berechnen."),
 ("geo_flaeche",    "geo",    5, "Flächeninhalt",          ["zahl","gitter"],
  "Flächen in Kästchen auszählen und bei Rechtecken berechnen."),
 ("geo_koerper",    "geo",    5, "Körper",                 ["wahl","zahl"],
  "Würfel, Quader, Kugel, Zylinder und ihre Eigenschaften."),
 ("geo_netz",       "geo",    6, "Würfelnetze",            ["gitter","wahl"],
  "Erkennen, welches Netz sich zu einem Würfel falten lässt."),
 ("geo_koord",      "geo",    6, "Koordinaten",            ["gitter","zahl"],
  "Punkte in einem Gitter über Zeile und Spalte finden."),
 ("geo_spiegel",    "geo",    3, "Spiegeln im Kopf",       ["bildwahl"],
  "Eine Figur gedanklich an einer Achse spiegeln und das richtige Bild erkennen."),
 ("geo_drehen",     "geo",    4, "Drehen im Kopf",         ["bildwahl"],
  "Eine Figur gedanklich drehen und das richtige Bild erkennen."),
 ("geo_wuerfel",    "geo",    5, "Würfelgebäude",          ["bildzahl"],
  "Würfel in einem Gebäude zählen, auch die verdeckten."),

 # ---- Knobelwelt ----------------------------------------------------------
 ("log_paare",      "logik",  2, "Was passt zusammen?",    ["zuordnen","wahl"],
  "Einfache Zuordnungen nach einer erkennbaren Regel."),
 ("log_waage",      "logik",  3, "Die Waage",              ["zahl","wahl"],
  "Gleichgewichtsaufgaben: Wie viele Klötze wiegen gleich viel?"),
 ("log_reihen",     "logik",  4, "Wer steht wo?",          ["wahl","zuordnen"],
  "Aus zwei bis drei Hinweisen die richtige Reihenfolge ableiten."),
 ("log_wahrheit",   "logik",  5, "Wahr oder falsch?",      ["wahrfalsch","wahl"],
  "Aussagen über Zahlen auf ihren Wahrheitsgehalt prüfen."),
 ("log_ruecklauf",  "logik",  5, "Rückwärts denken",       ["zahl","mehrschritt"],
  "Vom Ergebnis zum Anfang zurückrechnen."),
 ("log_gitter",     "logik",  6, "Logikgitter",            ["zuordnen"],
  "Drei Angaben zu drei Personen durch Ausschluss zuordnen."),
 ("log_strategie",  "logik",  7, "Gewinnstrategie",        ["wahl","zahl"],
  "Einfache Spiele durchdenken und den sicheren Zug finden."),
 ("log_invar",      "logik",  8, "Es bleibt gleich",       ["wahl","wahrfalsch"],
  "Erkennen, was sich bei einer Aktion nie ändert, und daraus schließen."),
 ("log_position",   "logik",  5, "Wer steht wo? Ohne Zahlen", ["positionen"],
  "Aus Hinweisen ohne Zahlen die Reihenfolge von Personen herausfinden."),

 # ---- Roboterwerkstatt -----------------------------------------------------
 ("algo_befolgen",  "algo",   3, "Befehle befolgen",       ["roboter"],
  "Eine Befehlsfolge im Kopf Schritt für Schritt ausführen und das Zielfeld finden."),
 ("algo_finden",    "algo",   4, "Den Weg programmieren",  ["roboter"],
  "Aus Befehlskarten ein Programm bauen, das den Roboter um Hindernisse zum Ziel bringt."),
 ("algo_reparieren","algo",   5, "Fehler reparieren",      ["roboter"],
  "In einem Programm den einen falschen Befehl finden."),
 ("algo_maschine",  "algo",   5, "Die Zahlenmaschine",     ["zahl","wahl"],
  "Aus Ein- und Ausgabepaaren die Regel einer Maschine entdecken und anwenden."),
 ("algo_schleife",  "algo",   6, "Wiederholen",            ["roboter"],
  "Programme mit Wiederholungen lesen und ihr Ende vorhersagen."),

 # ---- Möglichkeiten -------------------------------------------------------
 ("komb_paare",     "komb",   4, "Kombinationen zählen",   ["zahl","wahl"],
  "Wie viele Paare lassen sich aus zwei kleinen Mengen bilden?"),
 ("komb_reihen",    "komb",   5, "Reihenfolgen",           ["zahl"],
  "Wie viele Reihenfolgen gibt es für drei oder vier Dinge?"),
 ("komb_wege",      "komb",   6, "Wege zählen",            ["gitter","zahl"],
  "Wege in einem kleinen Gitter zählen, nur nach rechts und unten."),
 ("komb_zufall",    "komb",   6, "Wie wahrscheinlich?",    ["wahl","wahrfalsch"],
  "Chancen vergleichen: Was ist wahrscheinlicher, was unmöglich?"),
 ("komb_taube",     "komb",   8, "Es muss zwei geben",     ["wahl","zahl"],
  "Schubfachschluss: Warum zwei Dinge zwangsläufig zusammenfallen."),
 ("komb_nim",       "komb",   5, "Der letzte Stein",       ["zahl","wahl","mehrschritt"],
  "Ein Nimm-Spiel durchdenken und den sicheren Gewinnzug finden."),

 # ---- Messen & Wiegen -----------------------------------------------------
 ("gr_uhr",         "groess", 2, "Die Uhr",                ["wahl","zuordnen","zahl"],
  "Volle und halbe Stunden auf dem Zifferblatt ablesen."),
 ("gr_uhr_min",     "groess", 4, "Minuten",                ["zahl","wahl"],
  "Uhrzeiten minutengenau lesen und Zeitspannen berechnen."),
 ("gr_geld",        "groess", 2, "Geld",                   ["zahl","wahl"],
  "Münzen und Scheine zusammenzählen, Beträge vergleichen."),
 ("gr_geld_rueck",  "groess", 4, "Rückgeld",               ["zahl","mehrschritt"],
  "Einkauf und Rückgeld in Euro und Cent berechnen."),
 ("gr_laenge",      "groess", 3, "Längen",                 ["zahl","wahl"],
  "Zentimeter und Meter, umrechnen und vergleichen."),
 ("gr_gewicht",     "groess", 5, "Gewichte",               ["zahl","wahl"],
  "Gramm und Kilogramm, umrechnen und vergleichen."),
 ("gr_liter",       "groess", 5, "Hohlmaße",               ["zahl","wahl"],
  "Milliliter und Liter, umrechnen und vergleichen."),
 ("gr_mix",         "groess", 6, "Maße umrechnen",         ["zahl","mehrschritt"],
  "Zwischen Einheiten umrechnen und dabei rechnen."),

 # ---- Daten & Tabellen ----------------------------------------------------
 ("dat_tab",        "daten",  3, "Tabellen lesen",         ["zahl","wahl"],
  "Werte aus einer kleinen Tabelle ablesen."),
 ("dat_balken",     "daten",  4, "Balkendiagramm",         ["gitter","zahl","wahl"],
  "Ein Balkendiagramm lesen und Werte vergleichen."),
 ("dat_rechnen",    "daten",  5, "Aus Daten rechnen",      ["zahl","mehrschritt"],
  "Summen und Unterschiede aus einer Tabelle berechnen."),
 ("dat_mittel",     "daten",  6, "Durchschnitt",           ["zahl"],
  "Den Durchschnitt aus wenigen Werten bestimmen."),

 # ---- Zahlengeheimnisse ---------------------------------------------------
 ("geh_gerade",     "geheim", 2, "Gerade und ungerade",    ["wahl","wahrfalsch"],
  "Gerade und ungerade Zahlen unterscheiden und ihre Regeln entdecken."),
 ("geh_verdopp",    "geheim", 3, "Doppelt und halb",       ["zahl","wahrfalsch"],
  "Verdoppeln und halbieren im Kopf."),
 ("geh_teiler",     "geheim", 5, "Teiler finden",          ["wahl","zahl"],
  "Alle Teiler einer Zahl bis 50 finden."),
 ("geh_regeln",     "geheim", 6, "Teilbarkeitsregeln",     ["wahrfalsch","wahl"],
  "Erkennen ohne zu rechnen, ob eine Zahl durch 2, 5 oder 10 teilbar ist."),
 ("geh_prim",       "geheim", 6, "Primzahlen",             ["wahl","wahrfalsch"],
  "Primzahlen als Zahlen mit genau zwei Teilern erkennen."),
 ("geh_zerleg",     "geheim", 7, "Zahlen zerlegen",        ["zahl","wahl"],
  "Eine Zahl in ein Produkt aus Primzahlen zerlegen."),
 ("geh_quersumme",  "geheim", 7, "Quersummen",             ["zahl","wahrfalsch"],
  "Quersummen bilden und für die Teilbarkeit durch 3 und 9 nutzen."),

 # ---- Sachaufgaben --------------------------------------------------------
 ("sach_eins",      "sach",   2, "Eine Rechnung",          ["zahl","wahl"],
  "Kurze Geschichte, die mit einer einzigen Rechnung gelöst wird."),
 ("sach_zwei",      "sach",   4, "Zwei Schritte",          ["mehrschritt","zahl"],
  "Geschichte, die zwei Rechenschritte nacheinander verlangt."),
 ("sach_zuviel",    "sach",   5, "Zu viele Angaben",       ["zahl","wahl"],
  "Geschichte mit einer überflüssigen Zahl — das Wichtige heraussuchen."),
 ("sach_offen",     "sach",   6, "Selbst überlegen",       ["mehrschritt"],
  "Mehrschrittige Aufgabe, bei der der Rechenweg selbst gefunden werden muss."),
 ("sach_knifflig",  "sach",   7, "Kniffliges",             ["mehrschritt","zahl"],
  "Sachaufgabe mit versteckter Bedingung oder Umkehrung."),
]

SKILLS = [dict(id=i, area=a, stage=s, title=t, types=ty, brief=b) for i, a, s, t, ty, b in _S]

# Alle vorkommenden Aufgabentypen. Die App kennt genau diese zwölf (die
# ursprünglichen acht plus die vier neuen Denkschule-Typen der Roboterwerkstatt/
# Raum & Form/Logik: roboter, bildwahl, bildzahl, positionen).
TASK_TYPES = ["entdecken", "zahl", "wahl", "wahrfalsch", "ordnen",
              "zuordnen", "mehrschritt", "gitter",
              "roboter", "bildwahl", "bildzahl", "positionen"]


# ------------------------------------------------------------- Nachschlagen

def skill(sid):
    for s in SKILLS:
        if s["id"] == sid:
            return s
    return None


def area(aid):
    for a in AREAS:
        if a["id"] == aid:
            return a
    return None


def skills_of_area(aid):
    return [s for s in SKILLS if s["area"] == aid]


def skills_up_to(stage):
    """Alles, was auf dieser Stufe schon geübt werden darf."""
    return [s for s in SKILLS if s["stage"] <= stage]


def max_value(stage):
    """Größte Zahl, die auf dieser Stufe vorkommen darf.

    Der Validator prüft jede Zahl in Aufgabe und Antwort dagegen. Etwas Luft
    ist eingebaut: Geldbeträge in Cent und Gewichte in Gramm sprengen sonst
    den Rahmen, ohne dass die Aufgabe zu schwer wäre.
    """
    return STAGES[stage]["max_value"]


def ops_allowed(stage):
    return {op for op, from_stage in OP_FROM_STAGE.items() if from_stage <= stage}


def stage_of(sid):
    s = skill(sid)
    return s["stage"] if s else None


if __name__ == "__main__":
    print(f"{len(AREAS)} Bereiche · {len(SKILLS)} Fertigkeiten · {MAX_STAGE} Stufen\n")
    for a in AREAS:
        ss = skills_of_area(a["id"])
        stufen = sorted({s["stage"] for s in ss})
        print(f'  {a["emoji"]} {a["title"]:20s} {len(ss):2d} Fertigkeiten  Stufen {stufen}')
    print("\nje Stufe:")
    for st in sorted(STAGES):
        n = len([s for s in SKILLS if s["stage"] == st])
        info = STAGES[st]
        print(f'  {st}  {info["name"]:16s} bis {info["max_value"]:>7d}  '
              f'{n:2d} neu   ({info["grade"]})')
