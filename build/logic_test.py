# -*- coding: utf-8 -*-
"""Prüft die Lernlogik der fertigen index.html direkt im Browser-Kontext.

  .venv/bin/python build/logic_test.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum as C
import raetsel_kern as K
import testhilfe as T
import validate_v2 as V2
import validate as V
import kern_pakete as KP

APP = Path(__file__).resolve().parent.parent / "index.html"


def _logikgitter_fixture(n_kategorien, n_elemente, seed, subjekt_namen, ziel_namen_je_kategorie,
                          subjekt_idx, ziel_kat, rahmen, frage_vorlage, skill):
    """Baut eine fertig 'verkleidete' Logikgitter-Aufgabe von Hand — ohne jedes
    Sprachmodell (D4/D1, Testdaten laut ZIELE-V2.md).

    raetsel_kern.erzeuge_logikgitter() liefert den deterministischen Kern samt
    seinen deutschen Fallback-Hinweissätzen (Platzhalter wie 'k0e0'). Diese
    Funktion ersetzt die Platzhalter durch fest von Hand vergebene Namen —
    eine reine 1:1-Textersetzung, genau wie es die Einkleidung tun würde, nur
    ohne den Umweg über ein Sprachmodell. Anschließend wird das Ergebnis durch
    denselben Prüfer gejagt, der auch echte Pakete abnimmt
    (validate_v2.pruefe_logikgitter_aufgabe) — ein Fixture, das den eigenen
    Prüfer nicht besteht, taugt nichts als Testgrundlage.
    """
    kern = K.erzeuge_logikgitter(n_kategorien, n_elemente, seed)

    namen = {f"k0e{i}": n for i, n in enumerate(subjekt_namen)}
    for kat, liste in ziel_namen_je_kategorie.items():
        for i, n in enumerate(liste):
            namen[f"k{kat}e{i}"] = n

    def ersetze(text):
        for platzhalter, name in namen.items():
            text = text.replace(platzhalter, name)
        return text

    kategorien = [[namen[f"k{kat}e{i}"] for i in range(len(kern["kategorien"][kat]))]
                  for kat in range(len(kern["kategorien"]))]
    hinweise = [{"typ": h["typ"], "a": [int(h["a"][0][1:]), h["a"][1]],
                 "b": [int(h["b"][0][1:]), h["b"][1]], "text": ersetze(h["text"])}
                for h in kern["hinweise"]]

    subjekt_name = subjekt_namen[subjekt_idx]
    korrekt_idx = kern["loesung"][f"k{ziel_kat}"][subjekt_idx]
    optionen = list(ziel_namen_je_kategorie[ziel_kat])

    aufgabe = {
        "type": "logikgitter",
        "skill": skill,
        "kategorien": kategorien,
        "hinweise": hinweise,
        "frage": {"a": [0, subjekt_idx], "ziel": ziel_kat},
        "frage_text": frage_vorlage.format(name=subjekt_name),
        "loesung": kern["loesung"],
        "optionen": optionen,
        "richtig": korrekt_idx,
        "rahmen": rahmen,
    }
    ok, maengel = V2.pruefe_logikgitter_aufgabe(aufgabe)
    assert ok, f"Logikgitter-Testfixture (seed={seed}) ist ungültig: {maengel}"
    return aufgabe


# Zwei feste Fixtures, wie in ZIELE-V2.md gefordert: unterschiedliche Größe,
# unterschiedliche Themenwelt, beide deterministisch (feste Seeds) und beide
# ohne jeden LLM-Aufruf verkleidet (siehe _logikgitter_fixture()).
FIX_LOGIK_1 = _logikgitter_fixture(
    n_kategorien=2, n_elemente=3, seed=101,
    subjekt_namen=["Mia", "Ben", "Lea"],
    ziel_namen_je_kategorie={1: ["Hund", "Katze", "Vogel"]},
    subjekt_idx=0, ziel_kat=1,
    rahmen="In der Blockwelt haben drei Freunde je ein Lieblingstier.",
    frage_vorlage="Welches Tier mag {name} am liebsten?",
    skill="log_gitter",
)
FIX_LOGIK_2 = _logikgitter_fixture(
    n_kategorien=3, n_elemente=4, seed=202,
    subjekt_namen=["Finn", "Nora", "Timo", "Ida"],
    ziel_namen_je_kategorie={1: ["Rot", "Blau", "Grün", "Gelb"],
                             2: ["Schwert", "Bogen", "Schild", "Zauberstab"]},
    subjekt_idx=2, ziel_kat=2,
    rahmen="Vier Ritter rüsten sich für das Turnier in der Burgenbau-Welt aus.",
    frage_vorlage="Welche Waffe trägt {name}?",
    skill="log_gitter",
)


# --------------------------- D1/SPEC_lektionen_v2.md §2/§3/§4/§6: die vier
# neuen Denkschule-Typen — je eine fertige Aufgabe direkt aus kern_pakete.py
# (dieselbe deterministische Erzeugung wie in data/units_seed.json, kein
# Sprachmodell).
def _kern_fixture(skill, art, stage=None, index=0, wid="weltraum"):
    """Baut EINE Aufgabe über den kern_pakete-Bauer für 'skill' und lässt sie
    denselben Prüfer durchlaufen, der auch echte Pakete abnimmt
    (validate.check_task) — ein Fixture, das den eigenen Prüfer nicht
    besteht, taugt nichts."""
    sk = C.skill(skill)
    stage = stage if stage is not None else sk["stage"]
    bauer = KP.KERN_SKILLS[skill]
    aufgabe = dict(bauer(stage, wid, index), skill=skill)
    maengel = V.check_task(aufgabe, stage, [art])
    assert not maengel, f"Kern-Testfixture {skill!r} ist ungültig: {maengel}"
    return aufgabe


FIX_BILDWAHL = _kern_fixture("geo_spiegel", "bildwahl")
FIX_BILDZAHL = _kern_fixture("geo_wuerfel", "bildzahl")
FIX_POSITIONEN = _kern_fixture("log_position", "positionen")

# ------------------------------------------- D1/SPEC_lektionen_v2.md §2: die
# drei Roboter-Modi (algo_kern.py, zuletzt fertig geworden). FIX_ROBOTER_*
# sind je EINE Aufgabe für "ziel"/"programm"/"reparieren"; ROBOTER_LISTE ist
# eine große, über alle vier Zeilen der beiden "modus ziel"-Staffeln
# (algo_befolgen Stufe 3/4, algo_schleife Stufe 6/7) gemischte Menge für den
# JS/Python-Abgleich von simuliereRoboter() — jede Aufgabe trägt bereits ihr
# geprüftes loesung.ende aus dem Kern.
FIX_ROBOTER_ZIEL = _kern_fixture("algo_befolgen", "roboter")
FIX_ROBOTER_PROGRAMM = _kern_fixture("algo_finden", "roboter")
FIX_ROBOTER_REPARIEREN = _kern_fixture("algo_reparieren", "roboter")


def _roboter_ziel_liste():
    aufgaben = []
    for wid in ("weltraum", "minecraft", "dino"):
        for stufe in (3, 4):
            for index in range(6):
                aufgaben.append(_kern_fixture("algo_befolgen", "roboter", stage=stufe,
                                               index=index, wid=wid))
        for stufe in (6, 7):
            for index in range(6):
                aufgaben.append(_kern_fixture("algo_schleife", "roboter", stage=stufe,
                                               index=index, wid=wid))
    return aufgaben


ROBOTER_LISTE = _roboter_ziel_liste()
assert len(ROBOTER_LISTE) >= 30, f"nur {len(ROBOTER_LISTE)} Roboter-Testaufgaben, gefordert sind >= 30"

JS = r"""
() => {
  const out = [];
  const t = (name, cond, info) => out.push({name, ok: !!cond, info: info || ""});
  const frisch = () => { S = freshState(); save(); };

  // ------------------------------------------------------------ Zahlvergleich
  t("3 und 3.0 sind gleich",        numEq("3", 3));
  t("Komma und Punkt sind gleich",  numEq("3,5", 3.5));
  t("3 und 4 sind verschieden",     !numEq("3", 4));
  t("Leereingabe zählt nicht",      !numEq("", 3));

  // -------------------------------------------------------------- Leitner
  frisch();
  const sk = SKILLS.find(s => DATA.units.some(u => u.skill === s.id)) || SKILLS[0];
  const x = st(sk.id);
  t("neue Fertigkeit startet bei 0", x.l === 0);

  // Richtig beantworten hebt den Level, falsch senkt ihn – aber nie unter 0
  x.l = 0;
  for(let i = 0; i < 7; i++){ x.l = Math.min(MAX_L, x.l + 1); }
  t("Level steigt nicht über das Maximum", x.l === MAX_L, "l=" + x.l);
  for(let i = 0; i < 9; i++){ x.l = Math.max(0, x.l - 1); }
  t("Level fällt nicht unter null", x.l === 0);

  t("Leitner-Abstände steigen",
    INTERVALS.every((v,i) => i === 0 || v >= INTERVALS[i-1]), JSON.stringify(INTERVALS));
  t("Abstand passt zum Level", INTERVALS[3] === 3 && INTERVALS[5] === 21);

  // ------------------------------------------------------- Bewertung live
  frisch();
  const unit = DATA.units[0];
  startUnit(unit.id);
  const erste = SESS.tasks[0];
  const xpVor = S.profile.xp, tagVor = S.profile.todayCount;
  grade(true);
  t("richtige Antwort bringt XP", S.profile.xp > xpVor, `${xpVor} -> ${S.profile.xp}`);
  t("richtige Antwort zählt zum Tagesziel",
    erste.type === "entdecken" || S.profile.todayCount === tagVor + 1);
  t("Fertigkeit steigt nach richtiger Antwort",
    erste.type === "entdecken" || stRead(erste.skill).l > 0);
  t("Wiederholung ist eingeplant", stRead(erste.skill).d > 0);

  // Falsche Antwort hängt die Aufgabe hinten an
  nextTask();
  const vorher = SESS.tasks.length;
  const lvVor = stRead(SESS.tasks[SESS.i].skill).l;
  grade(false);
  t("falsche Aufgabe kommt nochmal", SESS.tasks.length === vorher + 1);
  t("letzte Aufgabe ist als Wiederholung markiert", SESS.tasks[SESS.tasks.length-1].redo === true);
  t("falsche Antwort senkt den Level", stRead(SESS.tasks[SESS.i].skill).l <= lvVor);

  // Eine Wiederholung darf den Level nicht wieder anheben
  const t2 = SESS.tasks[SESS.tasks.length-1];
  const lv2 = stRead(t2.skill).l;
  SESS.i = SESS.tasks.length - 1; SESS.answered = false;
  grade(true);
  t("Wiederholung hebt den Level nicht", stRead(t2.skill).l === lv2, "l=" + stRead(t2.skill).l);

  // ------------------------------------------------------------- Sterne
  const sterne = (right, asked) => {
    const pct = asked ? right/asked : 1;
    return pct >= .9 ? 3 : pct >= .72 ? 2 : 1;
  };
  t("10 von 10 gibt 3 Sterne", sterne(10,10) === 3);
  t("8 von 10 gibt 2 Sterne",  sterne(8,10) === 2);
  t("5 von 10 gibt 1 Stern",   sterne(5,10) === 1);

  // Ein ganzes Paket sauber durchspielen
  frisch();
  startUnit(unit.id);
  let schutz = 0;
  while(SESS && schutz++ < 100){ grade(true); nextTask(); }
  t("Paket endet von selbst", !SESS, "nach " + schutz + " Aufgaben");
  t("Paket ist als gespielt vermerkt", !!S.units[unit.id]);
  t("Fehlerfreies Paket gibt 3 Sterne", (S.units[unit.id]||{}).stars === 3);
  t("Paketzähler steht auf 1", S.stats.packs === 1);

  // ------------------------------------------------------ Wegweiser & Vorrat
  frisch();
  const n1 = nextUnit();
  t("nächstes Paket ist bestimmbar", !!n1 && !!UNITS[n1.id]);
  S.units[n1.id] = {stars:3, plays:1};
  t("erledigtes Paket wird übersprungen", nextUnit().id !== n1.id || DATA.units.length === 1);

  frisch();
  t("ohne Fortschritt ist nichts fällig", dueSkills().length === 0);
  const anyId = DATA.units[0].skill;
  S.skills[anyId] = {l:2, d:Date.now() - 1000, c:1, w:0};
  t("fällige Fertigkeit wird gefunden", dueSkills().includes(anyId));
  S.skills[anyId].d = Date.now() + 9e8;
  t("noch nicht fällige wird nicht gefunden", !dueSkills().includes(anyId));

  // -------------------------------------------------- Schwierigkeit passt sich an
  frisch();
  t("ohne Fortschritt startet er auf Stufe 1", baseStage() === 1);

  // Zwei fehlerfrei gelöste Pakete einer Stufe heben das Grundniveau –
  // dann fängt er auch in unbekannten Welten nicht mehr bei eins an.
  const s1 = DATA.units.filter(u => u.stage === 1);
  if(s1.length >= 2){
    S.units[s1[0].id] = {stars:3, plays:1};
    t("ein perfektes Paket hebt das Niveau noch nicht", baseStage() === 1);
    S.units[s1[1].id] = {stars:3, plays:1};
    t("zwei perfekte Pakete heben das Grundniveau", baseStage() === 2, "base=" + baseStage());
  }

  frisch();
  // Wer nur mittelmäßig abschneidet, bleibt auf seiner Stufe
  s1.slice(0,2).forEach(u => { S.units[u.id] = {stars:2, plays:1}; });
  t("zwei mittelmäßige Pakete heben nichts", baseStage() === 1, "base=" + baseStage());

  frisch();
  // Das Weltniveau steigt für sich, wenn in dieser Welt etwas sofort saß
  const w = AREAS.find(a => unitsOfArea(a.id).length >= 2);
  if(w){
    const us = unitsOfArea(w.id);
    S.units[us[0].id] = {stars:3, plays:1};
    t("perfektes Paket hebt das Niveau seiner Welt",
      areaStage(w.id) === us[0].stage + 1, w.id + " -> " + areaStage(w.id));
    const andere = AREAS.find(a => a.id !== w.id && unitsOfArea(a.id).length);
    t("andere Welten bleiben davon unberührt", areaStage(andere.id) === 1);
  }

  frisch();
  // Das nächste Paket muss dem Niveau folgen, nicht der Reihenfolge
  s1.slice(0,2).forEach(u => { S.units[u.id] = {stars:3, plays:1}; });
  const nach = nextUnit();
  t("nach dem Aufstieg kommt kein Stufe-1-Paket mehr",
    !nach || nach.stage >= 2 || !DATA.units.some(u => u.stage >= 2),
    "vorgeschlagen: Stufe " + (nach ? nach.stage : "?"));

  // Abwechslung: zweimal hintereinander dieselbe Welt soll die Ausnahme sein
  frisch();
  const erst = nextUnit();
  S.profile.lastUnitId = erst.id;
  S.units[erst.id] = {stars:1, plays:1};
  const zweit = nextUnit();
  const gebiet = u => (SKILLS.find(s => s.id === u.skill) || {}).area;
  t("das nächste Paket kommt aus einer anderen Welt",
    gebiet(zweit) !== gebiet(erst) || AREAS.filter(a => unitsOfArea(a.id).length).length < 2,
    gebiet(erst) + " -> " + gebiet(zweit));

  // Der Schwerer-Knopf muss wirklich schwerer sein
  frisch();
  if(DATA.units.some(u => u.stage >= 2)){
    t("es gibt etwas Schwereres", hasHarder());
    const hart = nextUnit(true), normal = nextUnit();
    t("der Schwerer-Knopf führt höher", hart.stage > normal.stage || hart.id !== normal.id,
      normal.stage + " -> " + hart.stage);
  }

  // Nie über die höchste Stufe hinaus
  frisch();
  DATA.units.forEach(u => { S.units[u.id] = {stars:3, plays:1}; });
  t("das Niveau bleibt im Rahmen", baseStage() <= MAX_STAGE, "base=" + baseStage());
  t("auch bei allem gemeistert kommt ein Vorschlag", !!nextUnit());

  // ------------------------------------------------------------- Abzeichen
  frisch();
  S.stats.packs = 1; checkBadges();
  t("erstes Abzeichen wird vergeben", S.profile.badges.includes("first"));
  frisch();
  S.stats.correct = 100; checkBadges();
  t("Abzeichen für 100 richtige", S.profile.badges.includes("a100"));
  frisch();
  t("ohne Leistung kein Abzeichen", (checkBadges(), S.profile.badges.length === 0));

  // --------------------------------------------------------------- Speicher
  frisch();
  S.profile.xp = 123; save();
  const roh = JSON.parse(localStorage.getItem(KEY));
  t("Speicherstand ist lesbar", roh && roh.profile.xp === 123);

  localStorage.setItem(KEY, "{kaputt");
  t("kaputter Speicher wirft die App nicht um", load().profile.xp === 0);
  localStorage.setItem(KEY, JSON.stringify({v:1, profile:{xp:"viel"}, skills:{unbekannt:{l:9}}}));
  const geladen = load();
  t("unsinnige XP werden verworfen", geladen.profile.xp === 0);
  t("unbekannte Fertigkeit wird verworfen", !geladen.skills.unbekannt);
  localStorage.removeItem(KEY);

  // ---------------------------------------------------------- Datenqualität
  const alleTasks = DATA.units.flatMap(u => u.tasks);
  t("jedes Paket kennt seine Fertigkeit",
    DATA.units.every(u => SKILLS.some(s => s.id === u.skill)));
  t("jede Fertigkeit gehört zu einer Welt",
    SKILLS.every(s => AREAS.some(a => a.id === s.area)));
  t("kein Paket ist leer", DATA.units.every(u => u.tasks.length >= 4));
  t("jede Aufgabe hat eine bekannte Art",
    alleTasks.every(x => !!RENDER[x.type]),
    [...new Set(alleTasks.map(x=>x.type))].join(","));
  t("jede Aufgabe hat eine Frage",
    alleTasks.every(x => ((x.q || x.frage_text || "")).trim().length > 0));
  t("Auswahlaufgaben haben eine gültige Lösung",
    alleTasks.filter(x => x.type === "wahl")
      .every(x => x.opts && x.correct >= 0 && x.correct < x.opts.length));
  t("Ordnen-Aufgaben haben eine vollständige Reihenfolge",
    alleTasks.filter(x => x.type === "ordnen")
      .every(x => x.order && x.order.length === x.items.length));
  t("Level-Titel reichen für alle Stufen", TITLES.length === 10);

  // ----------------------------------------------------- D5/D7: Würfelfuchs
  // Ein bekannter Bildschirm, unabhängig davon, wo die vorigen Tests den
  // Router stehen gelassen haben — begleiterSchirm() braucht view.name.
  view.name = "home";

  // ------------------------------------------------ D7: Modus-/Begleiter-Schalter
  frisch();
  t("Voreinstellung nach dem Update ist Denkschule (V2)", S.settings.modus === "v2");
  t("Der Begleiter ist standardmäßig eingeschaltet", S.settings.begleiter === true);
  S.settings.modus = "v1";
  t("Im klassischen Modus (V1) ist der Begleiter nicht aktiv", !begleiterAktiv());
  S.settings.modus = "v2"; S.settings.begleiter = false;
  t("Ausgeschalteter Begleiter bleibt auch in V2 unsichtbar", !begleiterAktiv());
  S.settings.begleiter = true;
  t("V2 mit eingeschaltetem Begleiter ist aktiv", begleiterAktiv());

  S.units[unit.id] = {stars:2, plays:3, sofort:0, pausiertBis:0};
  S.skills[unit.skill] = {l:3, d:Date.now()+1000, c:5, w:1, h:[1,0,1]};
  const standVorUmschalten = JSON.stringify({u:S.units, s:S.skills});
  S.settings.modus = "v1"; save();
  S.settings.modus = "v2"; save();
  t("Umschalten zwischen V1 und V2 verändert den Lernstand nicht",
    JSON.stringify({u:S.units, s:S.skills}) === standVorUmschalten);

  // --------------------------------------------------------------- D5: Taufe
  frisch();
  GEF.taufeSpaeter = false; GEF.nachfrage = null;
  t("Vor der Taufe ist der Namensdialog fällig", gefTaufeOffen());
  t("Ungetauft heißt er im Text 'dein Fuchs'", gefName() === "dein Fuchs");
  gefTaufe("Keks");
  t("Nach der Taufe ist er getauft und trägt seinen Namen",
    S.avatar.getauft === true && S.avatar.name === "Keks" && gefName() === "Keks");
  t("Nach der Taufe erscheint der Dialog nicht noch einmal", !gefTaufeOffen());

  frisch();
  t("Ohne 'Später' ist der Dialog wieder fällig", gefTaufeOffen());
  gefTaufeSpaeter();
  t("Nach 'Später' bleibt der Dialog in dieser Sitzung zu", !gefTaufeOffen());
  t("Aber die Taufe selbst gilt nicht als erledigt", S.avatar.getauft === false);
  GEF.taufeSpaeter = false;

  // ------------------------------------------------------ D6: Abbruch-Nachfrage
  frisch();
  S.settings.modus = "v2"; S.settings.begleiter = true;
  GEF.nachfrage = null;
  nachAbbruchFragen(unit.id, true);
  t("Ein Anlass löst die erste Nachfrage des Tages aus", GEF.nachfrage !== null);
  t("Der Tag wird vermerkt", S.avatar.letzteNachfrageTag === String(today()));
  t("Die Folge wird vermerkt", S.avatar.nachfrageWarZuletzt === true);

  GEF.nachfrage = null;
  nachAbbruchFragen(unit.id, true);
  t("Am selben Tag folgt keine zweite Nachfrage (Tagesdeckel)", GEF.nachfrage === null);
  t("Zwei Anlässe in Folge lösen nur einmal aus (nie zweimal hintereinander)",
    S.avatar.nachfrageWarZuletzt === false);

  GEF.nachfrage = null;
  nachAbbruchFragen(unit.id, true);
  t("Der Tagesdeckel gilt unabhängig von der Folge weiter", GEF.nachfrage === null);

  S.avatar.letzteNachfrageTag = "2000-01-01";   // ein anderer Tag simuliert
  S.avatar.nachfrageWarZuletzt = true;          // aber zuletzt war schon eine Nachfrage
  GEF.nachfrage = null;
  nachAbbruchFragen(unit.id, true);
  t("Nie zwei Mal in Folge, auch an einem neuen Tag nicht", GEF.nachfrage === null);

  S.avatar.letzteNachfrageTag = "2000-01-01";
  nachAbbruchFragen(unit.id, false);            // eine Sitzung ganz ohne Anlass
  t("Eine Sitzung ohne Nachfrage setzt die Folge zurück", S.avatar.nachfrageWarZuletzt === false);
  GEF.nachfrage = null;
  nachAbbruchFragen(unit.id, true);
  t("Danach darf an einem neuen Tag wieder gefragt werden", GEF.nachfrage !== null);

  S.settings.begleiter = false;
  GEF.nachfrage = null;
  nachAbbruchFragen(unit.id, true);
  t("Ohne Begleiter fragt der Fuchs nie nach", GEF.nachfrage === null);
  S.settings.begleiter = true;

  // Immer wegtippbar, ohne jede Bewertung
  GEF.nachfrage = {unitId: unit.id};
  const logVorSchliessen = S.log.ev.length;
  gefNachfrageSchliessen();
  t("'Sag ich nicht' schließt ohne ein Ereignis zu erzeugen",
    GEF.nachfrage === null && S.log.ev.length === logVorSchliessen);

  GEF.nachfrage = {unitId: unit.id};
  gefGrundGeben(3);
  const grundEvent = S.log.ev[S.log.ev.length - 1];
  t("Eine Grund-Antwort erzeugt genau ein 'g'-Ereignis mit Paket und Zahl 1–4",
    grundEvent.e === "g" && grundEvent.u === unit.id && grundEvent.w === 3);
  t("Danach ist die Nachfrage geschlossen", GEF.nachfrage === null);

  // ----------------------------------------------- Z1: kein Freitext im Sync
  frisch();
  S.avatar.name = "Alex"; S.avatar.getauft = true; save();
  GEF.nachfrage = {unitId: unit.id};
  gefGrundGeben(4);
  const syncNutzlast = JSON.stringify(S.log.ev);
  t("Der Avatar-Name taucht in keinem Ereignis der Sync-Nutzlast auf",
    !syncNutzlast.includes("Alex"));

  // ------------------------------------------------- D1/D4: Logikgitter-Typ
  // Zwei von Hand eingekleidete Fixtures (siehe _logikgitter_fixture() in
  // diesem Python-Skript) — deterministisch, ohne jeden LLM-Aufruf.
  frisch();
  const fix1 = __FIX_LOGIK_1__, fix2 = __FIX_LOGIK_2__;
  beginSession({kind:"unit", unitId:null, title:"Test", intro:"", tasks:[fix1, fix2]});

  const html1 = RENDER.logikgitter(curTask());
  t("Logikgitter zeigt alle Hinweise", fix1.hinweise.every(h => html1.includes(esc(h.text))));
  t("Logikgitter zeigt die Frage", html1.includes(esc(fix1.frage_text)));
  t("Logikgitter zeigt alle Antwortmöglichkeiten", fix1.optionen.every(o => html1.includes(esc(o))));

  // Denkhilfe: rein lokale Notiz, schaltet zyklisch leer -> ✓ -> ✗ -> leer
  t("Denkhilfe startet leer", Object.keys(SESS.denk || {}).length === 0);
  const zelle = "0_1_0";
  tapDenkzelle(zelle);
  t("Erstes Antippen der Denkhilfe setzt ✓", SESS.denk[zelle] === 1);
  tapDenkzelle(zelle);
  t("Zweites Antippen der Denkhilfe setzt ✗", SESS.denk[zelle] === 2);
  tapDenkzelle(zelle);
  t("Drittes Antippen leert die Denkhilfe wieder", SESS.denk[zelle] === 0);
  t("Denkhilfe ist zunächst eingeklappt", SESS.denkOffen === false);
  toggleDenkhilfe();
  t("Denkhilfe lässt sich aufklappen", SESS.denkOffen === true);

  // Vorlesen deckt Rahmengeschichte, Hinweise und Frage ab
  const vorlesetext1 = logikVorlesetext(fix1);
  t("Vorlesetext enthält die Rahmengeschichte", vorlesetext1.includes(fix1.rahmen));
  t("Vorlesetext enthält alle Hinweise", fix1.hinweise.every(h => vorlesetext1.includes(h.text)));
  t("Vorlesetext enthält die Frage", vorlesetext1.includes(fix1.frage_text));

  // Richtige Option wird richtig gewertet
  chooseLogik(fix1.richtig);
  t("Richtige Antwort wird als richtig gewertet", SESS.answered && SESS.lastOk === true);

  // Falsche Option wird falsch gewertet — zweites Fixture, frischer Task
  nextTask();
  t("Ein neuer Task setzt die Denkhilfe zurück",
    SESS.denkOffen === false && Object.keys(SESS.denk || {}).length === 0);
  const falscheOpt = fix2.optionen.findIndex((_, i) => i !== fix2.richtig);
  chooseLogik(falscheOpt);
  t("Falsche Antwort wird als falsch gewertet", SESS.answered && SESS.lastOk === false);

  // --------------------------------- D1: bildwahl/bildzahl/positionen (SPEC
  // §3/§4/§6) — je eine fertige Aufgabe direkt aus kern_pakete.py (Python,
  // __FIX_…__ als JSON eingesetzt). Roboter folgt separat (algo_kern.py).
  frisch();
  const fixBw = __FIX_BILDWAHL__, fixBz = __FIX_BILDZAHL__, fixPos = __FIX_POSITIONEN__;
  beginSession({kind:"unit", unitId:null, title:"Test", intro:"", tasks:[fixBw, fixBz, fixPos]});

  const htmlBw = RENDER.bildwahl(curTask());
  t("bildwahl zeigt das Fragebild und alle vier Optionsbilder",
    htmlBw.includes(fixBw.svg) && fixBw.optionen_svg.every(svg => htmlBw.includes(svg)));
  chooseBild(fixBw.richtig);
  t("bildwahl: richtige Antwort wird als richtig gewertet", SESS.answered && SESS.lastOk === true);

  nextTask();
  const htmlBz = RENDER.bildzahl(curTask());
  t("bildzahl zeigt das Bild", htmlBz.includes(fixBz.svg));
  const falscheZahl = fixBz.a + 1;
  SESS.typed = String(falscheZahl);
  checkZahl();
  t("bildzahl: falsche Antwort wird als falsch gewertet", SESS.answered && SESS.lastOk === false);

  nextTask();
  const htmlPos = RENDER.positionen(curTask());
  t("positionen zeigt Rahmen, alle Hinweise und die Frage",
    htmlPos.includes(esc(fixPos.rahmen))
    && fixPos.hinweise.every(h => htmlPos.includes(esc(h.text)))
    && htmlPos.includes(esc(fixPos.frage_text)));
  t("positionen zeigt alle Antwortmöglichkeiten",
    fixPos.optionen.every(o => htmlPos.includes(esc(o))));
  const vorlesetextPos = positionenVorlesetext(fixPos);
  t("positionen-Vorlesetext enthält Rahmen, Hinweise und Frage",
    vorlesetextPos.includes(fixPos.rahmen)
    && fixPos.hinweise.every(h => vorlesetextPos.includes(h.text))
    && vorlesetextPos.includes(fixPos.frage_text));
  choosePosition(fixPos.richtig);
  t("positionen: richtige Antwort wird als richtig gewertet", SESS.answered && SESS.lastOk === true);

  // ------------------------------------------------- D1: roboter (SPEC §2)
  // ROBOTER_LISTE: JS/Python-Abgleich über >= 30 gemischte Aufgaben – die
  // Simulation ist reine Wahrheit, sie MUSS mit dem Python-Kern übereinstimmen.
  const robListe = __ROBOTER_LISTE__;
  t(`simuliereRoboter stimmt für alle ${robListe.length} Roboter-Testaufgaben mit der `
    + `Python-Lösung überein (Ende + kein Crash)`,
    robListe.length >= 30 && robListe.every(x => {
      const erg = simuliereRoboter(x, x.programm);
      return !erg.crash && erg.ende[0] === x.loesung.ende[0] && erg.ende[1] === x.loesung.ende[1];
    }), `n=${robListe.length}`);

  frisch();
  const fixRobZiel = __FIX_ROBOTER_ZIEL__, fixRobProg = __FIX_ROBOTER_PROGRAMM__,
        fixRobRep = __FIX_ROBOTER_REPARIEREN__;
  beginSession({kind:"unit", unitId:null, title:"Test", intro:"",
                tasks:[fixRobZiel, fixRobProg, fixRobRep]});

  const htmlRobZiel = RENDER.roboter(curTask());
  t("roboter (modus ziel) zeigt das Programm als Symbole", htmlRobZiel.includes("rob-prog"));
  t("roboter (modus ziel) zeigt das Gitter", htmlRobZiel.includes("rob-grid"));
  const ergZiel = simuliereRoboter(fixRobZiel, fixRobZiel.programm);
  t("roboterVorlesetext (modus ziel) enthält q und das gesprochene Programm",
    roboterVorlesetext(fixRobZiel).startsWith(fixRobZiel.q)
    && roboterVorlesetext(fixRobZiel).includes("Das Programm:"));
  pickRoboterZelle(ergZiel.ende[0], ergZiel.ende[1]);
  t("roboter (modus ziel): das richtige Feld wird richtig gewertet",
    SESS.answered && SESS.lastOk === true);

  nextTask();
  const htmlRobProg = RENDER.roboter(curTask());
  t("roboter (modus programm) zeigt die Befehlspalette", htmlRobProg.includes("rob-palette"));
  t("roboterVorlesetext (modus programm) ist nur die Frage", roboterVorlesetext(fixRobProg) === fixRobProg.q);
  const beispielErg = simuliereRoboter(fixRobProg, fixRobProg.loesung.beispiel);
  t("loesung.beispiel (modus programm) erreicht crashfrei das Ziel",
    !beispielErg.crash && beispielErg.ende[0] === fixRobProg.ziel[0]
    && beispielErg.ende[1] === fixRobProg.ziel[1]
    && fixRobProg.loesung.beispiel.length <= fixRobProg.max_laenge);
  SESS.prog = fixRobProg.loesung.beispiel.slice();
  startRoboterProgramm();
  t("roboter (modus programm): das eigene (Kern-)Programm wird richtig gewertet",
    SESS.answered && SESS.lastOk === true);

  nextTask();
  const htmlRobRep = RENDER.roboter(curTask());
  t("roboter (modus reparieren) zeigt die antippbaren Befehls-Chips", htmlRobRep.includes("rob-chip"));
  tapBefehl(fixRobRep.loesung.index);
  t("roboter (modus reparieren): der richtige Platz wird richtig gewertet",
    SESS.answered && SESS.lastOk === true);

  frisch();
  beginSession({kind:"unit", unitId:null, title:"Test", intro:"", tasks:[fixRobRep]});
  const falscherPlatz = (fixRobRep.loesung.index + 1) % fixRobRep.programm.length;
  tapBefehl(falscherPlatz);
  t("roboter (modus reparieren): ein falscher Platz wird falsch gewertet",
    SESS.answered && SESS.lastOk === false);

  // -------------------------------------------------- D1: Denkschule-Karte
  frisch();
  S.settings.modus = "v2";
  go("map");
  const appText1 = () => document.getElementById("app").textContent;
  const diszTitel = Object.values(DISZIPLINEN).map(d => d.titel);
  t("Denkschule-Karte zeigt alle 5 Disziplinen",
    diszTitel.length === 5 && diszTitel.every(titel => appText1().includes(titel)));

  // Der Platzhaltersatz ist reine UI-Logik (disziplinKarte() in src/app.html)
  // für den Fall, dass eine Disziplin noch kein Paket hat. Seit den zwölf
  // neuen Denkschule-Fertigkeiten (SPEC_lektionen_v2.md) hat jede der fünf
  // Disziplinen mindestens ein Paket — die leere Fläche wird deshalb hier
  // künstlich nachgestellt (Pakete der Disziplin "algorithmik" ausgeblendet),
  // statt sich auf zufällig leere Produktivdaten zu verlassen.
  const einheitenVorPlatzhalter = DATA.units;
  DATA.units = DATA.units.filter(u => !DISZIPLINEN.algorithmik.skills.includes(u.skill));
  go("map");
  t("Eine leere Disziplin zeigt den Platzhaltersatz statt einer leeren Fläche",
    appText1().includes("Hier schlummert noch was"));
  DATA.units = einheitenVorPlatzhalter;
  go("map");

  view.opts.trainingOffen = true; render();
  const preSkillSet = new Set(PRE_LESSON_SKILLS);
  const resteWelten = AREAS.filter(a => unitsOfArea(a.id).some(u => preSkillSet.has(u.skill)));
  t("'Schulstoff & Training' enthält alle übrigen Welten",
    resteWelten.length > 0 && resteWelten.every(a => appText1().includes(a.title)));

  S.settings.modus = "v1";
  go("map");
  const v1Karten = document.querySelectorAll(".uc").length;
  const erwarteteV1 = AREAS.filter(a => unitsOfArea(a.id).length > 0).length;
  t("Modus V1 zeigt weiterhin die klassische Weltenkarte",
    v1Karten === erwarteteV1 && !document.getElementById("app").textContent.includes("Schulstoff"),
    `${v1Karten} von ${erwarteteV1} Welten`);

  // --------------------------------------------------------- D6: Motivation
  // Spaß-Signal: höchstens 1× je Sitzung, zusätzlich höchstens jedes zweite
  // Paketende (abwechselnd) — genau ein "f"-Ereignis, kein Freitext.
  frisch();
  SPASS.gezeigtSitzung = false;   // Laufzeit-Marke, siehe GEF — überlebt frisch() nicht von selbst
  {
    const u = DATA.units[0];
    const spieleDurch = () => {
      startUnit(u.id);
      let schutz = 0;
      while(SESS && schutz++ < 100){ grade(true); nextTask(); }
    };

    spieleDurch();                       // 1. Paketende: spassZaehler 0 -> 1 (ungerade)
    t("Nach dem ersten vollständig gespielten Paket erscheint das Spaß-Signal",
      view.opts.res.spassFragen === true);
    t("Vor einer Antwort ist noch keine vermerkt", !view.opts.res.spassAntwort);

    const vorEv = S.log.ev.length;
    gibSpassFeedback(3);
    const letztes = S.log.ev[S.log.ev.length - 1];
    t("Eine Antwort erzeugt genau ein 'f'-Ereignis mit Paket und Zahl 1–3",
      S.log.ev.length === vorEv + 1 && letztes.e === "f" && letztes.u === u.id
      && letztes.w === 3);
    t("Danach steht die Antwort im Ergebnis", view.opts.res.spassAntwort === 3);
    const nochmal = S.log.ev.length;
    gibSpassFeedback(1);
    t("Ein zweiter Tipp auf dasselbe Ergebnis erzeugt kein zweites Ereignis",
      S.log.ev.length === nochmal);

    spieleDurch();                       // 2. Paketende: 1 -> 2 (gerade) — Abwechslung sagt nein
    t("Beim zweiten Paketende erscheint es nicht noch einmal",
      view.opts.res.spassFragen === false);

    spieleDurch();                       // 3. Paketende: 2 -> 3 (ungerade) — Abwechslung sagt ja,
                                          // aber der Sitzungs-Deckel (SPASS) hat schon einmal gezeigt
    t("Der Sitzungs-Deckel blockiert ein drittes Mal, auch wenn die Abwechslung 'ja' sagen würde",
      view.opts.res.spassFragen === false, "spassZaehler=" + S.spassZaehler);
  }

  // rev-Reset (D6.2): ein inhaltlich ersetztes Paket verliert nur seine Sterne.
  frisch();
  {
    const u = DATA.units[0];
    startUnit(u.id);
    let schutz = 0;
    while(SESS && schutz++ < 100){ grade(true); nextTask(); }
    const sterneVorher = S.units[u.id].stars, playsVorher = S.units[u.id].plays;
    const gedaechtnisVorher = JSON.stringify(S.skills[u.skill]);
    t("Nach dem Spielen ist die aktuelle Fassung (rev) vermerkt", !!S.units[u.id].rev);

    const echteRev = u.rev;
    u.rev = "deadbeef";                  // simuliert einen Neu-Bau mit anderem Inhalt
    pruefeRevisionen();
    t("Eine geänderte rev setzt die Paket-Sterne zurück", S.units[u.id].stars === 0,
      sterneVorher + " -> " + S.units[u.id].stars);
    t("plays bleibt dabei unberührt", S.units[u.id].plays === playsVorher);
    t("pausiertBis/sofort bleiben Feldnamen des Pakets, unberührt",
      "sofort" in S.units[u.id] && "pausiertBis" in S.units[u.id]);
    t("Das Fertigkeiten-Gedächtnis bleibt unberührt",
      JSON.stringify(S.skills[u.skill]) === gedaechtnisVorher);
    t("Die neue rev ist jetzt vermerkt", S.units[u.id].rev === "deadbeef");
    u.rev = echteRev;

    // Erstmaliges Auftauchen einer rev (noch keine gespeichert) setzt nichts
    // zurück, sondern merkt sie nur — sonst verlöre jedes Paket beim
    // allerersten Bau mit dieser Funktion scheinbar seinen Fortschritt.
    S.units[u.id] = {stars:2, plays:3, sofort:0, pausiertBis:0, rev:""};
    pruefeRevisionen();
    t("Erstmaliges Merken einer rev setzt die Sterne NICHT zurück",
      S.units[u.id].stars === 2);
    t("Die rev wird dabei trotzdem gemerkt", S.units[u.id].rev === u.rev);
  }

  // Pre-Lesson-Kette (D3): sichtbare Zeile bei einem "fuer"-Posten.
  frisch();
  {
    const u = DATA.units[0];
    const ziel = SKILLS.find(s => s.id !== u.skill);
    S.plan = [{skill:u.skill, art:"vor", fuer:ziel.id, grund:"x"}];
    startUnit(u.id);
    t("Ein 'fuer'-Posten setzt den Vorlauf-Titel der Sitzung",
      SESS.vorlaufFuer === ziel.title);
    const html = VIEWS.session();
    t("Die Sitzung zeigt die Vorlauf-Zeile mit dem Titel der Ziel-Fertigkeit",
      html.includes("Das hilft dir gleich bei") && html.includes(esc(ziel.title)));

    S.plan = [{skill:u.skill, art:"vor", grund:"x"}];   // ohne "fuer"
    startUnit(u.id);
    t("Ohne 'fuer' bleibt die Vorlauf-Zeile aus",
      !SESS.vorlaufFuer && !VIEWS.session().includes("Das hilft dir gleich bei"));
  }

  frisch();
  return out;
}
"""


def main():
    from playwright.sync_api import sync_playwright

    # Die zwei von Hand eingekleideten Fixtures als JS-Objektliteral einsetzen —
    # per einfachem Textersatz statt f-string, damit die vielen geschweiften
    # Klammern des restlichen JS-Codes nicht mit Format-Platzhaltern kollidieren.
    js = JS.replace("__FIX_LOGIK_1__", json.dumps(FIX_LOGIK_1, ensure_ascii=False))
    js = js.replace("__FIX_LOGIK_2__", json.dumps(FIX_LOGIK_2, ensure_ascii=False))
    js = js.replace("__FIX_BILDWAHL__", json.dumps(FIX_BILDWAHL, ensure_ascii=False))
    js = js.replace("__FIX_BILDZAHL__", json.dumps(FIX_BILDZAHL, ensure_ascii=False))
    js = js.replace("__FIX_POSITIONEN__", json.dumps(FIX_POSITIONEN, ensure_ascii=False))
    js = js.replace("__FIX_ROBOTER_ZIEL__", json.dumps(FIX_ROBOTER_ZIEL, ensure_ascii=False))
    js = js.replace("__FIX_ROBOTER_PROGRAMM__", json.dumps(FIX_ROBOTER_PROGRAMM, ensure_ascii=False))
    js = js.replace("__FIX_ROBOTER_REPARIEREN__", json.dumps(FIX_ROBOTER_REPARIEREN, ensure_ascii=False))
    js = js.replace("__ROBOTER_LISTE__", json.dumps(ROBOTER_LISTE, ensure_ascii=False))

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        T.ohne_dienst(page)
        page.goto(APP.as_uri())
        page.wait_for_timeout(500)
        res = page.evaluate(js)
        b.close()

    fails = [r for r in res if not r["ok"]]
    for r in res:
        mark = "✅" if r["ok"] else "❌"
        info = f"   ({r['info']})" if r["info"] else ""
        print(f"{mark} {r['name']}{info}")
    if errs:
        print("\nJS-Fehler:", *errs, sep="\n  ")
    print(f"\n{len(res)-len(fails)}/{len(res)} bestanden")
    return 1 if fails or errs else 0


if __name__ == "__main__":
    sys.exit(main())
