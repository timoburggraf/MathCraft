# -*- coding: utf-8 -*-
"""Die fünf Denkdisziplinen der Denkschule (ZIELE-V2.md, Abschnitt D1).

Diese Datei ist reine Datenhaltung, keine Logik: Sie legt fest, welche der
inzwischen 89 Fertigkeiten aus curriculum.py zu welcher der fünf Disziplinen
gehört (Mustererkennung, Logik & Deduktion, Algorithmik, Kombinatorik &
Strategie, Raum & Form) und welche stattdessen Pre-Lesson-Material sind — reine
Rechenfertigkeiten, die dem Kind nur noch als kurzer Vorlauf vor einer
anspruchsvollen Zieldisziplin begegnen (D3), nie mehr als eigenständiges Ziel.

Die Zuordnung ist wörtlich die D1-Tabelle aus ZIELE-V2.md, ergänzt um die
zwölf neuen Denkschule-Fertigkeiten aus SPEC_lektionen_v2.md §1:

  Mustererkennung        must_*, dazu must_matrix und must_analogie (Bildmatrix
                          und Analogie sind dieselbe Regel-/Umwandlungssuche
                          wie die Zahlenfolgen, nur an Bildern statt Ziffern)
  Logik & Deduktion       log_paare, log_waage, log_reihen, log_wahrheit,
                          log_gitter, log_ruecklauf, dazu log_position (Wer
                          steht wo? ohne Zahlen — dieselbe Ausschluss-
                          Deduktion wie das Logikgitter, nur auf einer Reihe
                          statt einem Gitter)
  Kombinatorik & Strategie komb_*, dazu log_strategie und log_invar (das sind
                          Spielstrategien und Invarianten-Schlüsse, keine
                          Zuordnungsrätsel — kombinatorisches statt
                          deduktives Denken)
  Algorithmik             algo_befolgen, algo_finden, algo_reparieren,
                          algo_maschine, algo_schleife — die neuen
                          Roboter-Befehlsfolgen und die Zahlenmaschine (V2,
                          SPEC_lektionen_v2.md §1/§2)
  Raum & Form             die geo_*-Fertigkeiten, bei denen man sich eine Form
                          im Kopf vorstellen, drehen oder falten muss statt sie
                          auszumessen — geo_umfang und geo_flaeche sind
                          dagegen Rechenaufgaben (Formel anwenden) und bleiben
                          Pre-Lesson-Material; dazu die drei neuen
                          Bildaufgaben geo_spiegel, geo_drehen, geo_wuerfel

PRE_LESSON_SKILLS wird bewusst nicht von Hand abgetippt, sondern aus
curriculum.py abgeleitet ("alle übrigen"): jede Fertigkeit, die keiner
Disziplin zugeteilt ist. So bleibt die Liste automatisch vollständig, auch
wenn curriculum.py sich einmal ändert — validate_v2_test.py gleicht das
zusätzlich unabhängig ab.

  .venv/bin/python build/disziplinen.py     # Übersicht ausgeben
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum as C

DISZIPLINEN = {
    "muster": dict(
        titel="Mustererkennung",
        beschreibung="Die geheime Regel hinter Zahlen, Formen und Bildern aufspüren.",
        kalkuel_budget=6,
        skills=[
            "must_einfach", "must_schritt", "must_form", "must_rueck",
            "must_wechsel", "must_verdopp", "must_fibo", "must_figur",
            "must_matrix", "must_analogie",
        ],
    ),
    "logik": dict(
        titel="Logik & Deduktion",
        beschreibung="Aus wahren und falschen Hinweisen messerscharf die Wahrheit herausfinden.",
        kalkuel_budget=6,
        skills=[
            "log_paare", "log_waage", "log_reihen", "log_wahrheit",
            "log_gitter", "log_ruecklauf", "log_position",
        ],
    ),
    "algorithmik": dict(
        titel="Algorithmik",
        beschreibung="Einem Roboter genaue Befehle geben, seinen Weg vorhersagen und Fehler reparieren.",
        kalkuel_budget=6,
        skills=[
            "algo_befolgen", "algo_finden", "algo_reparieren",
            "algo_maschine", "algo_schleife",
        ],
    ),
    "kombinatorik": dict(
        titel="Kombinatorik & Strategie",
        beschreibung="Alle Möglichkeiten durchdenken und die beste Strategie zum Gewinnen finden.",
        # 8 statt 6: Mehrgliedrige Zählketten wie 4*3*2*1 sind hier der Denkweg
        # selbst — lauter Einmaleins-Schritte, kein Ziffern-Grind. Mit 6 wurde
        # fünfmal in Folge jedes neue komb_reihen-Paket verworfen.
        kalkuel_budget=8,
        skills=[
            "komb_paare", "komb_reihen", "komb_wege", "komb_zufall", "komb_taube",
            "log_strategie", "log_invar", "komb_nim",
        ],
    ),
    "raum": dict(
        titel="Raum & Form",
        beschreibung="Formen im Kopf drehen, spiegeln und falten, ohne sie anzufassen.",
        kalkuel_budget=6,
        skills=[
            "geo_formen", "geo_symm", "geo_zaehl", "geo_koerper", "geo_netz", "geo_koord",
            "geo_spiegel", "geo_drehen", "geo_wuerfel",
        ],
    ),
}

# Sicherheitsnetz gegen Tippfehler: Jede hier eingetragene Fertigkeit muss es
# in curriculum.py wirklich geben — sonst lieber laut scheitern als still eine
# Geisterfertigkeit mitschleppen (dieselbe Vorsicht wie im übrigen Projekt).
_ALLE_SKILL_IDS = {s["id"] for s in C.SKILLS}
for _disziplin, _angaben in DISZIPLINEN.items():
    for _sid in _angaben["skills"]:
        if _sid not in _ALLE_SKILL_IDS:
            raise ValueError(f"Disziplin {_disziplin!r} verweist auf unbekannte Fertigkeit {_sid!r}")

_ZUGEORDNETE_SKILLS = {sid for angaben in DISZIPLINEN.values() for sid in angaben["skills"]}

# Alles, was keiner Disziplin zugeteilt ist: reine Rechenfertigkeiten, die nur
# noch als kurzer Vorlauf vor einer Zieldisziplin vorkommen (D3), nie mehr als
# eigenständiges Lernziel.
PRE_LESSON_SKILLS = tuple(s["id"] for s in C.SKILLS if s["id"] not in _ZUGEORDNETE_SKILLS)


def disziplin_von(skill_id):
    """Liefert den Disziplin-Schlüssel einer Fertigkeit, oder None.

    None bedeutet: entweder ist es eine Pre-Lesson-Fertigkeit (steht in
    PRE_LESSON_SKILLS), oder skill_id ist gar keine bekannte Fertigkeit —
    diese Funktion unterscheidet die beiden Fälle bewusst nicht, das ist
    Sache des Aufrufers.
    """
    for name, angaben in DISZIPLINEN.items():
        if skill_id in angaben["skills"]:
            return name
    return None


if __name__ == "__main__":
    print(f"{len(DISZIPLINEN)} Disziplinen · {len(_ZUGEORDNETE_SKILLS)} Fertigkeiten zugeordnet · "
          f"{len(PRE_LESSON_SKILLS)} Pre-Lesson-Fertigkeiten\n")
    for name, angaben in DISZIPLINEN.items():
        print(f'  {angaben["titel"]:26s} {len(angaben["skills"]):2d} Fertigkeiten  '
              f'Budget {angaben["kalkuel_budget"]}')
        for sid in angaben["skills"]:
            print(f'      {sid}')
    print(f"\n  Pre-Lesson ({len(PRE_LESSON_SKILLS)}): " + ", ".join(PRE_LESSON_SKILLS))
