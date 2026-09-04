# -*- coding: utf-8 -*-
"""Das JSON-Schema, in dem das Modell seine Lernpakete abliefern muss.

Structured Outputs erzwingen die Form schon bei der Erzeugung: fehlende Felder,
falsche Typen oder ein erfundener Aufgabentyp kommen gar nicht erst an. Das ist
die erste Verteidigungslinie — die zweite ist validate.py, die den Inhalt
nachrechnet. Die Form allein sagt nichts darüber, ob 8+5 wirklich 13 ist.

Jeder Aufgabentyp ist eine eigene Variante mit genau seinen Feldern; dadurch
kann das Modell nicht die Lösung eines Typs an einen anderen hängen.
"""

# In Structured Outputs muss jedes Objekt additionalProperties:false setzen und
# alle seine Felder in required auflisten.
def _obj(props, required=None):
    return {"type": "object", "properties": props,
            "required": required if required is not None else list(props),
            "additionalProperties": False}


_TEXT = {"type": "string"}
_NUM = {"type": "number"}
_TERM = _obj({"expr": {"type": "string",
                       "description": "Rechenweg als reiner Term, z.B. '8+5' oder '(12-4)*3'. "
                                      "Nur Zahlen, Klammern und + - * / – keine Wörter, "
                                      "keine Variablen. Muss genau die Antwort ergeben."}})

_HINT = {"type": "string", "description": "Kurzer Tipp, falls es klemmt. Ein Satz."}


# --------------------------------------------------------- die acht Varianten

_ENTDECKEN = _obj({
    "type": {"const": "entdecken"},
    "q": {"type": "string", "description": "Überschrift der neuen Idee, ein kurzer Satz."},
    "info": {"type": "string", "description": "Die Erklärung in ein bis zwei Sätzen, "
                                              "mit einem Beispiel. Kein Aufgabencharakter."},
})

_ZAHL = _obj({
    "type": {"const": "zahl"},
    "q": {"type": "string", "description": "Die Frage. Höchstens zwei Sätze."},
    "a": {"type": "number", "description": "Die richtige Zahl."},
    "check": _TERM,
    "hint": _HINT,
})

_WAHL = _obj({
    "type": {"const": "wahl"},
    "q": _TEXT,
    "opts": {"type": "array", "items": {"type": "string"},
             "description": "Vier Möglichkeiten, alle etwa gleich lang."},
    "correct": {"type": "integer", "description": "Platz der richtigen Antwort, 0 bis 3."},
    "check": _TERM,
    "hint": _HINT,
})

_WAHRFALSCH = _obj({
    "type": {"const": "wahrfalsch"},
    "q": {"type": "string", "description": "Eine Behauptung, über die entschieden wird."},
    "a": {"type": "boolean", "description": "true, wenn die Behauptung stimmt."},
    "check": _obj({
        "left": {"type": "string", "description": "linke Seite als Term, z.B. '9+4'"},
        "right": {"type": "string", "description": "rechte Seite als Term, z.B. '13'"},
    }),
    "hint": _HINT,
})

_ORDNEN = _obj({
    "type": {"const": "ordnen"},
    "q": {"type": "string", "description": "Der Auftrag, z.B. 'Ordne von klein nach groß.'"},
    "items": {"type": "array", "items": _NUM,
              "description": "Drei bis sechs Zahlen in gemischter Reihenfolge."},
    "order": {"type": "array", "items": {"type": "integer"},
              "description": "Die Plätze der Zahlen in der richtigen Reihenfolge."},
    "hint": _HINT,
})

_ZUORDNEN = _obj({
    "type": {"const": "zuordnen"},
    "q": _TEXT,
    "pairs": {"type": "array",
              "items": {"type": "array", "items": {"type": "string"}},
              "description": "Drei bis fünf Paare [links, rechts]. Jede Karte nur einmal."},
    "hint": _HINT,
})

_MEHRSCHRITT = _obj({
    "type": {"const": "mehrschritt"},
    "q": {"type": "string", "description": "Die Geschichte. Höchstens zwei Sätze."},
    "steps": {"type": "array", "items": _obj({
        "q": {"type": "string", "description": "Die Frage dieses Schritts."},
        "a": _NUM,
        "check": _TERM,
    }), "description": "Zwei bis drei Schritte, die aufeinander aufbauen."},
    "hint": _HINT,
})

_GITTER = _obj({
    "type": {"const": "gitter"},
    "q": _TEXT,
    "grid": {"type": "array",
             "items": {"type": "array", "items": {"type": "string"}},
             "description": "Bis zu 8x8 Felder, je Feld ein einzelnes Zeichen oder Emoji. "
                            "Alle Zeilen gleich lang."},
    "opts": {"type": "array", "items": {"type": "string"},
             "description": "Vier Möglichkeiten. Leer lassen, wenn ein Feld angetippt wird."},
    "correct": {"type": "integer", "description": "Platz der richtigen Antwort, sonst -1."},
    "cell": {"type": "array", "items": {"type": "integer"},
             "description": "Das zu tippende Feld als [Zeile, Spalte]. Leer, wenn es "
                            "eine Auswahl gibt."},
    "hint": _HINT,
})

# --- Logikgitter (D4, ZIELE-V2.md): der deterministische Kern aus
# raetsel_kern.py liefert die Wahrheit (Lösung, Hinweise, Zielkategorie), ein
# Sprachmodell darf nur noch Namen und Sätze drumherum bauen (verkleidung.py).
# Die Struktur ist exakt die, die validate_v2.pruefe_logikgitter_aufgabe
# erwartet. 'loesung' hat je nach Gittergröße unterschiedlich viele Schlüssel
# ('k1', 'k2', ...) — deshalb hier bewusst ein loses Objekt statt der sonst
# im Modul üblichen festen Feldliste: Dieser Typ durchläuft nie eine
# schemagesteuerte Sprachmodell-Antwort (er wird deterministisch in
# generate_units.py gebaut), das Schema dokumentiert nur die Form, in der ihn
# die App und validate.py sehen.
_LOGIKGITTER_HINWEIS = _obj({
    "typ": {"type": "string", "description": "'ist' oder 'nicht'."},
    "a": {"type": "array", "items": {"type": "integer"},
          "description": "[Kategorie-Index, Element-Index] der einen Seite des Hinweises."},
    "b": {"type": "array", "items": {"type": "integer"},
          "description": "[Kategorie-Index, Element-Index] der anderen Seite des Hinweises."},
    "text": {"type": "string", "description": "Ein deutscher Satz, der beide Namen wörtlich "
                                              "enthält; bei 'nicht' zusätzlich eine Verneinung "
                                              "('nicht' oder 'kein')."},
})

_LOGIKGITTER_FRAGE = _obj({
    "a": {"type": "array", "items": {"type": "integer"},
          "description": "[0, Element-Index] des gefragten Subjekts aus Kategorie 0."},
    "ziel": {"type": "integer", "description": "Index der gefragten Zielkategorie."},
})

_LOGIKGITTER = _obj({
    "type": {"const": "logikgitter"},
    "kategorien": {"type": "array", "items": {"type": "array", "items": {"type": "string"}},
                   "description": "Je Kategorie eine Liste von Namen; Kategorie 0 sind "
                                  "die Subjekte."},
    "hinweise": {"type": "array", "items": _LOGIKGITTER_HINWEIS,
                 "description": "Die strukturellen Hinweise, minimal und eindeutig lösbar."},
    "frage": _LOGIKGITTER_FRAGE,
    "frage_text": {"type": "string", "description": "Der Frage-Satz, nennt den Namen "
                                                     "des gefragten Subjekts."},
    "loesung": {"type": "object",
                "description": "Die vollständige Lösungsbelegung aus dem Kern: je "
                               "weiterer Kategorie ('k1', 'k2', ...) die Liste der "
                               "Elementindizes je Subjekt."},
    "optionen": {"type": "array", "items": {"type": "string"},
                 "description": "Alle Namen der Zielkategorie, gemischt."},
    "richtig": {"type": "integer", "description": "Platz der richtigen Antwort in 'optionen'."},
    "rahmen": {"type": "string", "description": "Rahmengeschichte, höchstens ein Satz."},
}, required=["type", "kategorien", "hinweise", "frage", "frage_text",
             "loesung", "optionen", "richtig"])

# --- Roboter, Bildwahl, Bildzahl, Positionen (SPEC_lektionen_v2.md §2/§3/§4/§6):
# vier weitere deterministische Kern-Typen, im selben Stil wie 'logikgitter'
# oben: lose Objekte für 'kern'/'loesung'/'programm' statt der sonst im Modul
# üblichen festen Feldliste, weil diese Typen NIE eine schemagesteuerte
# Sprachmodell-Antwort durchlaufen (sie entstehen deterministisch in
# kern_pakete.py aus algo_kern.py/grafik_kern.py/muster_kern.py/raetsel_kern.py)
# — das Schema hier dokumentiert nur die Form, in der die App und validate.py
# sie sehen. Deshalb stehen sie in TASK, aber ausdrücklich NICHT in TASK_LLM.
_ROBOTER = _obj({
    "type": {"const": "roboter"},
    "modus": {"type": "string", "description": "'ziel', 'programm' oder 'reparieren'."},
    "q": {"type": "string", "description": "Die Aufgabenstellung. Höchstens zwei Sätze."},
    "n": {"type": "integer", "description": "Gittergröße n×n, 4..6."},
    "start": {"type": "array", "items": {"type": "integer"},
              "description": "[Zeile, Spalte] des Startfelds."},
    "richtung": {"type": "string", "description": "Startblickrichtung: 'N','O','S','W'."},
    "waende": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}},
               "description": "Liste von Wandfeldern [Zeile, Spalte]."},
    "ziel": {"type": "array", "items": {"type": "integer"},
             "description": "[Zeile, Spalte] des Zielfelds. Fehlt bewusst bei modus 'ziel' "
                            "(würde die Antwort verraten)."},
    "befehlssatz": {"type": "string", "description": "'absolut' (N/O/S/W) oder 'relativ' (V/L/R)."},
    "programm": {"type": "array",
                 "description": "Die Befehlsfolge (bei 'ziel'/'reparieren'); Einträge sind "
                                "entweder ein Befehlsbuchstabe oder eine Schleife "
                                "{'x':k,'b':[…]}."},
    "max_laenge": {"type": "integer", "description": "Nur bei 'programm': Länge der kürzesten "
                                                      "Lösung."},
    "loesung": {"type": "object", "description": "Kern-Wahrheit, je nach Modus: 'ziel' -> "
                                                 "{'ende','richtung'}; 'reparieren' -> "
                                                 "{'index','ersatz'}; 'programm' -> {'beispiel'}."},
    "hint": _HINT,
}, required=["type", "modus", "q", "n", "start", "richtung", "waende", "hint"])

_BILDWAHL = _obj({
    "type": {"const": "bildwahl"},
    "q": {"type": "string", "description": "Die Aufgabenstellung. Höchstens zwei Sätze."},
    "svg": {"type": "string", "description": "Das Fragebild als SVG-Text."},
    "optionen_svg": {"type": "array", "items": {"type": "string"},
                      "description": "Genau vier Options-SVGs."},
    "richtig": {"type": "integer", "description": "Platz der richtigen Option, 0..3."},
    "kern": {"type": "object", "description": "Die wahrheitstragenden Felder aus grafik_kern.py "
                                              "bzw. muster_kern.py (art, zellen, optionen_zellen, "
                                              "richtig, stufe, ggf. winkel/regeln/…)."},
    "hint": _HINT,
})

_BILDZAHL = _obj({
    "type": {"const": "bildzahl"},
    "q": {"type": "string", "description": "Die Aufgabenstellung. Höchstens zwei Sätze."},
    "svg": {"type": "string", "description": "Das Fragebild als SVG-Text."},
    "a": {"type": "number", "description": "Die richtige Anzahl."},
    "kern": {"type": "object", "description": "{'art':'wuerfelgebaeude','hoehen':[[…]],"
                                              "'anzahl':…, 'stufe':…} aus grafik_kern.py."},
    "hint": _HINT,
})

_POSITIONEN_HINWEIS = _obj({
    "typ": {"type": "string", "description": "Hinweistyp, z.B. 'direkt_links', 'neben', "
                                             "'ganz_links', 'zwischen', ..."},
    "a": {"type": "integer", "description": "Subjekt-Index (0-basiert) der Hauptperson."},
    "b": {"type": "integer", "description": "Subjekt-Index der zweiten Person (falls nötig)."},
    "c": {"type": "integer", "description": "Subjekt-Index der dritten Person (nur 'zwischen')."},
    "text": {"type": "string", "description": "Ein deutscher Satz, der den/die Namen wörtlich "
                                              "enthält; bei einer Verneinung zusätzlich "
                                              "'nicht' oder 'kein'."},
}, required=["typ", "a", "text"])

_POSITIONEN_FRAGE = _obj({
    "art": {"type": "string", "description": "'position' oder 'neben'."},
    "p": {"type": "integer", "description": "Nur bei 'position': die gefragte Stelle, 0-basiert."},
    "a": {"type": "integer", "description": "Nur bei 'neben': Subjekt-Index."},
    "seite": {"type": "string", "description": "Nur bei 'neben': 'links' oder 'rechts'."},
}, required=["art"])

_POSITIONEN = _obj({
    "type": {"const": "positionen"},
    "rahmen": {"type": "string", "description": "Rahmengeschichte, höchstens ein Satz."},
    "namen": {"type": "array", "items": {"type": "string"},
              "description": "Nominativ mit Artikel je Subjekt, Index = Subjekt-Kennung."},
    "hinweise": {"type": "array", "items": _POSITIONEN_HINWEIS,
                 "description": "Die strukturellen Hinweise, minimal und eindeutig lösbar, "
                                "komplett ohne Zahlen im Text."},
    "loesung": {"type": "array", "items": {"type": "integer"},
                "description": "loesung[p] = Subjekt-Index an Position p (0 = ganz links)."},
    "frage": _POSITIONEN_FRAGE,
    "frage_text": {"type": "string", "description": "Der Frage-Satz. Nennt nicht den Namen der "
                                                     "Antwort."},
    "optionen": {"type": "array", "items": {"type": "string"},
                 "description": "Alle Namen, gemischt."},
    "richtig": {"type": "integer", "description": "Platz der richtigen Antwort in 'optionen'."},
    "hint": _HINT,
}, required=["type", "rahmen", "namen", "hinweise", "loesung", "frage", "frage_text",
             "optionen", "richtig", "hint"])

TASK = {"anyOf": [_ENTDECKEN, _ZAHL, _WAHL, _WAHRFALSCH,
                  _ORDNEN, _ZUORDNEN, _MEHRSCHRITT, _GITTER, _LOGIKGITTER,
                  _ROBOTER, _BILDWAHL, _BILDZAHL, _POSITIONEN]}

# Was ein Sprachmodell abliefern darf: alles außer 'logikgitter'. Der Typ
# entsteht ausschließlich deterministisch aus dem Kern (generate_units.py);
# stünde er im Antwortformat, könnte das Modell die Wahrheit selbst erfinden —
# und die API lehnt das lose 'loesung'-Objekt ohnehin ab.
TASK_LLM = {"anyOf": [_ENTDECKEN, _ZAHL, _WAHL, _WAHRFALSCH,
                      _ORDNEN, _ZUORDNEN, _MEHRSCHRITT, _GITTER]}

UNIT = _obj({
    "title": {"type": "string", "description": "Titel des Pakets, höchstens 4 Wörter, "
                                               "passend zur Themenwelt."},
    "intro": {"type": "string", "description": "Ein Satz, der das Kind in die Welt holt."},
    "tasks": {"type": "array", "items": TASK_LLM,
              "description": "Die Aufgaben, in aufsteigender Schwierigkeit."},
})

# Was der Tutor zusätzlich zur Einschätzung liefert (Stufe 2 des Projekts).
ASSESSMENT = _obj({
    "area": {"type": "string", "description": "Kennung des Bereichs."},
    "koennen": {"type": "integer", "description": "0 bis 100, wie sicher er darin ist."},
    "interesse": {"type": "integer", "description": "0 bis 100, wie gern er es macht."},
    "grund": {"type": "string", "description": "Woran du das festmachst. Ein Satz, "
                                               "mit Bezug auf konkrete Zahlen."},
})


def unit_response():
    """Antwortformat für einen einzelnen Generator-Aufruf."""
    return {"type": "json_schema", "schema": UNIT}


def tutor_response():
    """Antwortformat für den Tutor-Lauf: Einschätzung plus mehrere Pakete."""
    return {"type": "json_schema", "schema": _obj({
        "assessment": {"type": "array", "items": ASSESSMENT},
        "message": {"type": "string",
                    "description": "Ein Satz an das Kind, was als Nächstes kommt und warum."},
        "units": {"type": "array", "items": _obj({
            "skill": {"type": "string", "description": "Kennung der Fertigkeit."},
            "stage": {"type": "integer"},
            "world": {"type": "string", "description": "Kennung der Themenwelt."},
            "title": {"type": "string"},
            "intro": {"type": "string"},
            "tasks": {"type": "array", "items": TASK_LLM},
        })},
    })}
