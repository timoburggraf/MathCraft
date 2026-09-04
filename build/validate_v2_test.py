# -*- coding: utf-8 -*-
"""Prüft die drei neuen Bausteine der Denkschule: Rechenlast-Budget (D2), die
Disziplin-Tabelle (D1) und die verkleideten Logikgitter-/Folgen-Aufgaben (D4).

Im selben Geist wie validator_test.py und raetsel_kern_test.py: einwandfreie
Fälle müssen durchgehen, absichtlich kaputte müssen ausnahmslos abgelehnt
werden. Komplett offline — das Sprachmodell ist hier ein einfaches Python-
Callable, das vorbereitete JSON-Antworten liefert, kein Netzwerkzugriff.

  .venv/bin/python build/validate_v2_test.py
"""
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum as C
import disziplinen as D
import raetsel_kern as K
import validate_v2 as V2
import verkleidung as VK

RESULTS = []


def ok(name, cond, info=""):
    RESULTS.append((name, bool(cond), info))


THEMENWELT = {"title": "Blockwelt", "hook": "Blöcke, Erz, Truhen, Bauen, Craften"}


# ======================================================= Rechenlast-Budget
# Mindestens acht Fälle, wie im Auftrag verlangt: einfache Addition, zwei
# Divisionen aus der Praxis, Multiplikation, Subtraktion, Verschachtelung und
# ein unparsebarer Term.

FAELLE_KALKUEL = [
    ("8+5",              1, "kleine Addition, beide Operanden ≤ 20"),
    ("94/12",            4, "Divisor 12 liegt schon außerhalb des kleinen Einmaleins"),
    ("398/8",            4, "Divisor im Einmaleins, aber der Quotient 49,75 nicht"),
    ("42/6",             1, "Divisor UND Quotient (7) im kleinen Einmaleins"),
    ("3*4",              1, "kleines Einmaleins"),
    ("12*15",            3, "beide Faktoren über 10"),
    ("150+300",          3, "Summe über 100"),
    ("45-30",            2, "Operanden bis 100"),
    ("(3+4)*5",          2, "verschachtelt: 1 (Addition) + 1 (Multiplikation)"),
    ("(80+15)*(2+3)",    6, "verschachtelt: 2 + 1 + 3"),
]

for term, erwartet, begruendung in FAELLE_KALKUEL:
    kosten = V2.kalkuel_kosten(term)
    ok(f"kalkuel_kosten({term!r}) == {erwartet}  [{begruendung}]",
       kosten == erwartet, f"tatsächlich {kosten}")

for kaputter_term in ("8+", "acht+5", "5/0"):
    try:
        V2.kalkuel_kosten(kaputter_term)
        ok(f"kalkuel_kosten lehnt {kaputter_term!r} ab", False, "keine Ausnahme ausgelöst")
    except V2.KalkuelFehler as e:
        ok(f"kalkuel_kosten lehnt {kaputter_term!r} ab", True, str(e))

ok_flag, begr = V2.pruefe_kalkuel("8+5", budget=6)
ok("pruefe_kalkuel akzeptiert einen Term innerhalb des Budgets", ok_flag, begr)

ok_flag, begr = V2.pruefe_kalkuel("398/8", budget=1)
ok("pruefe_kalkuel lehnt einen zu teuren Term ab", not ok_flag, begr)


# ================================================================ D1-Tabelle

ALLE_SKILL_IDS = {s["id"] for s in C.SKILLS}
ZUGEORDNET = [sid for angaben in D.DISZIPLINEN.values() for sid in angaben["skills"]]
ZUGEORDNET_MENGE = set(ZUGEORDNET)
PRE_LESSON_MENGE = set(D.PRE_LESSON_SKILLS)

ok("keine Fertigkeit ist doppelt einer Disziplin zugeordnet",
   len(ZUGEORDNET) == len(ZUGEORDNET_MENGE),
   f"{len(ZUGEORDNET)} Einträge, {len(ZUGEORDNET_MENGE)} eindeutige")

ok("Disziplinen und Pre-Lesson-Fertigkeiten überschneiden sich nicht",
   ZUGEORDNET_MENGE.isdisjoint(PRE_LESSON_MENGE),
   str(ZUGEORDNET_MENGE & PRE_LESSON_MENGE))

ok("PRE_LESSON_SKILLS enthält keine doppelten Einträge",
   len(D.PRE_LESSON_SKILLS) == len(PRE_LESSON_MENGE))

ok("jede Fertigkeit aus curriculum.py ist genau einer Disziplin ODER Pre-Lesson "
   "zugeordnet — nichts fehlt, nichts ist erfunden",
   (ZUGEORDNET_MENGE | PRE_LESSON_MENGE) == ALLE_SKILL_IDS,
   f"fehlt: {ALLE_SKILL_IDS - (ZUGEORDNET_MENGE | PRE_LESSON_MENGE)}  "
   f"erfunden: {(ZUGEORDNET_MENGE | PRE_LESSON_MENGE) - ALLE_SKILL_IDS}")

ok("jede Disziplin trägt ihr Kalkül-Budget aus ZIELE-V2 (6, Kombinatorik 8)",
   all(a["kalkuel_budget"] == (8 if k == "kombinatorik" else 6)
       for k, a in D.DISZIPLINEN.items()))

ok("disziplin_von() findet die Zuordnungen aus der Tabelle wieder",
   D.disziplin_von("log_gitter") == "logik"
   and D.disziplin_von("must_fibo") == "muster"
   and D.disziplin_von("komb_taube") == "kombinatorik"
   and D.disziplin_von("log_invar") == "kombinatorik"
   and D.disziplin_von("geo_netz") == "raum")

ok("disziplin_von() liefert None für Pre-Lesson-Fertigkeiten",
   D.disziplin_von("zahl_bis20") is None and D.disziplin_von("geo_umfang") is None)


# ============================================== Fake-Sprachmodell (offline)

def _saubere_logikgitter_antwort(kern):
    """Baut eine strukturell einwandfreie Antwort für einen Logikgitter-Kern:
    jede Kennung bekommt einen eindeutigen Namen, jeder Hinweissatz gibt die
    Struktur korrekt wieder. Der Frage-Satz wird erst im Fake-LLM ergänzt,
    weil erst der Prompt verrät, welches Subjekt gefragt ist."""
    kennungen = [el for kat in kern["kategorien"] for el in kat]
    namen = {k: f"Name{i}" for i, k in enumerate(kennungen)}
    hinweis_saetze = []
    for h in kern["hinweise"]:
        name_a = namen[h["a"][0] + "e" + str(h["a"][1])]
        name_b = namen[h["b"][0] + "e" + str(h["b"][1])]
        if h["typ"] == "ist":
            hinweis_saetze.append(f"{name_a} gehört zu {name_b}.")
        else:
            hinweis_saetze.append(f"{name_a} gehört nicht zu {name_b}.")
    return {"namen": namen, "rahmen": "Ein kurzer Satz zur Themenwelt.",
            "hinweis_saetze": hinweis_saetze, "frage_satz": None}


def _fake_llm_logikgitter(basisantwort):
    """Liefert ein Callable prompt -> JSON-Text. Liest die im Prompt
    genannte GEFRAGTES_SUBJEKT-Kennung aus, um einen Frage-Satz zu bauen, der
    den passenden Namen wörtlich enthält."""
    def llm(prompt):
        subjekt_kennung = re.search(r"GEFRAGTES_SUBJEKT\s+(\S+)", prompt).group(1)
        antwort = dict(basisantwort)
        antwort["frage_satz"] = f"Was hat {antwort['namen'][subjekt_kennung]}?"
        return json.dumps(antwort, ensure_ascii=False)
    return llm


# ================================================== Verkleidung: gute Fälle

KERN_GUT = K.erzeuge_logikgitter(2, 3, seed=1)
AUFGABE_GUT, MAENGEL_GUT = VK.verkleide_logikgitter(
    KERN_GUT, THEMENWELT, _fake_llm_logikgitter(_saubere_logikgitter_antwort(KERN_GUT)), seed=1)

ok("saubere Fake-LLM-Antwort liefert eine Aufgabe ohne Mängel",
   AUFGABE_GUT is not None and not MAENGEL_GUT, str(MAENGEL_GUT))

if AUFGABE_GUT is not None:
    eigenstaendig_ok, eigenstaendig_maengel = V2.pruefe_logikgitter_aufgabe(AUFGABE_GUT)
    ok("dieselbe Aufgabe besteht pruefe_logikgitter_aufgabe auch eigenständig noch einmal",
       eigenstaendig_ok, str(eigenstaendig_maengel))
else:
    # Ohne eine gute Aufgabe können die folgenden Negativtests an ihr nicht
    # aufsetzen — dann lieber laut abbrechen als stillschweigend nichts prüfen.
    raise SystemExit(f"Grundvoraussetzung gescheitert, Testlauf abgebrochen: {MAENGEL_GUT}")

KERN_FOLGE_GUT = K.erzeuge_folge("plus", seed=1, laenge=5)
AUFGABE_FOLGE_GUT, MAENGEL_FOLGE_GUT = VK.verkleide_folge(
    KERN_FOLGE_GUT, THEMENWELT, lambda prompt: json.dumps({"einleitung": "Steve zählt seine Blöcke."}))

ok("saubere Folgen-Verkleidung liefert eine Aufgabe ohne Mängel",
   AUFGABE_FOLGE_GUT is not None and not MAENGEL_FOLGE_GUT, str(MAENGEL_FOLGE_GUT))
ok("die Folgen-Aufgabe übernimmt Glieder, Fortsetzung und Ablenker unverändert aus dem Kern",
   AUFGABE_FOLGE_GUT is not None
   and AUFGABE_FOLGE_GUT["glieder"] == KERN_FOLGE_GUT["glieder"]
   and AUFGABE_FOLGE_GUT["naechstes"] == KERN_FOLGE_GUT["naechstes"]
   and AUFGABE_FOLGE_GUT["ablenker"] == KERN_FOLGE_GUT["ablenker"])


# =============================================== Verkleidung: kaputte Fälle
# Vier verschiedene Arten, wie ein Sprachmodell die Verkleidung verderben
# kann — jede MUSS als Mangel gemeldet werden, keine darf durchrutschen.

kern = K.erzeuge_logikgitter(2, 3, seed=2)
basis = _saubere_logikgitter_antwort(kern)
kennungen = list(basis["namen"].keys())
basis["namen"][kennungen[1]] = basis["namen"][kennungen[0]]  # doppelter Name
aufgabe, maengel = VK.verkleide_logikgitter(kern, THEMENWELT, _fake_llm_logikgitter(basis), seed=2)
ok("doppelter Name wird abgelehnt, nichts rutscht durch",
   aufgabe is None and any("eindeutig" in m.lower() for m in maengel), str(maengel))

kern = K.erzeuge_logikgitter(2, 3, seed=3)
basis = _saubere_logikgitter_antwort(kern)
basis["hinweis_saetze"][0] = "Ein Satz, der keinen der beiden Namen nennt."
aufgabe, maengel = VK.verkleide_logikgitter(kern, THEMENWELT, _fake_llm_logikgitter(basis), seed=3)
ok("fehlender Name im Hinweistext wird abgelehnt, nichts rutscht durch",
   aufgabe is None and any("beide Namen" in m for m in maengel), str(maengel))

kern = K.erzeuge_logikgitter(2, 3, seed=4)
basis = _saubere_logikgitter_antwort(kern)
kennungen = list(basis["namen"].keys())
basis["rahmen"] = f"Diese Geschichte handelt von {kennungen[0]}."  # Platzhalter übrig
aufgabe, maengel = VK.verkleide_logikgitter(kern, THEMENWELT, _fake_llm_logikgitter(basis), seed=4)
ok("übrig gebliebene Platzhalter-Kennung wird abgelehnt, nichts rutscht durch",
   aufgabe is None and any("Platzhalter-Kennung" in m for m in maengel), str(maengel))

kern = K.erzeuge_folge("plus", seed=6, laenge=5)
verfaelscht = list(kern["glieder"])
verfaelscht[-1] += 1
llm_kaputt = lambda prompt: json.dumps({"einleitung": "Ein Satz zur Welt.", "glieder": verfaelscht})
aufgabe, maengel = VK.verkleide_folge(kern, THEMENWELT, llm_kaputt)
ok("verändertes Zahlenmaterial bei der Folge wird abgelehnt, nichts rutscht durch",
   aufgabe is None and any("Zahlenmaterial" in m for m in maengel), str(maengel))


# ==================================== pruefe_logikgitter_aufgabe direkt geprüft
# Handgebaute Mängel an der sonst einwandfreien AUFGABE_GUT — jeder MUSS
# erkannt werden.

kaputt = copy.deepcopy(AUFGABE_GUT)
kaputt["richtig"] = (kaputt["richtig"] + 1) % len(kaputt["optionen"])
gut, maengel = V2.pruefe_logikgitter_aufgabe(kaputt)
ok("falsche 'richtig'-Option wird abgelehnt",
   not gut and any("'richtig'" in m for m in maengel), str(maengel))

kaputt = copy.deepcopy(AUFGABE_GUT)
andere_indizes = [i for i in range(len(kaputt["optionen"])) if i != kaputt["richtig"]]
kaputt["optionen"][andere_indizes[1]] = kaputt["optionen"][andere_indizes[0]]
gut, maengel = V2.pruefe_logikgitter_aufgabe(kaputt)
ok("Duplikat-Option wird abgelehnt",
   not gut and any("doppelte" in m.lower() for m in maengel), str(maengel))

kaputt = copy.deepcopy(AUFGABE_GUT)
kaputt["hinweise"][0]["text"] = "Ein Satz ohne die richtigen Namen."
gut, maengel = V2.pruefe_logikgitter_aufgabe(kaputt)
ok("Hinweistext ohne die referenzierten Namen wird abgelehnt",
   not gut and any("beide Namen" in m for m in maengel), str(maengel))

# Kompatibilität zum minimalen Format aus ZIELE-V2: fehlt 'frage.ziel', ist es
# bei genau zwei Kategorien unzweideutig die jeweils andere.
kaputt = copy.deepcopy(AUFGABE_GUT)
del kaputt["frage"]["ziel"]
gut, maengel = V2.pruefe_logikgitter_aufgabe(kaputt)
ok("fehlendes 'frage.ziel' wird bei zwei Kategorien selbst ergänzt (Format aus ZIELE-V2)",
   gut, str(maengel))


# ==================================================================== Ausgabe

def main():
    fails = [r for r in RESULTS if not r[1]]
    for name, good, info in RESULTS:
        mark = "✅" if good else "❌"
        print(f"{mark} {name}" + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
