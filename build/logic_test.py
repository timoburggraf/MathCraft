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

  // ------------------------------------------------ Fokus: nur eine Welt
  // Wer sich auf der Karte eine Welt vornimmt, bleibt dort, bis sie durch ist —
  // statt nach jedem Paket in eine andere Welt geschickt zu werden.
  frisch();
  S.settings.modus = "v1";
  const fw = AREAS.find(a => unitsOfArea(a.id).length >= 3);
  const inFw = u => (SKILLS.find(s => s.id === u.skill) || {}).area === fw.id;
  t("ohne Fokus gibt es keinen Umschalter", fokusUmschalter() === "");
  setzeFokus("welt", fw.id);
  const f1 = nextUnit();
  t("mit Fokus kommt ein Paket aus der gewählten Welt", inFw(f1), fw.id + " -> " + f1.skill);
  S.profile.lastUnitId = f1.id; S.units[f1.id] = {stars:1, plays:1};
  const f2 = nextUnit();
  t("auch das nächste bleibt in der Welt (keine Rotation)", inFw(f2), f2.skill);
  t("erst Ungespieltes, dann Sterne nachholen", !S.units[f2.id], f2.id);
  t("auch der Schwerer-Knopf bleibt in der Welt", !hasHarder() || inFw(nextUnit(true)));
  t("Umschalter zeigt beide Knöpfe", /Nur/.test(fokusUmschalter()) && /Alle Welten/.test(fokusUmschalter()));
  t("Kartenknopf zeigt den aktiven Fokus", /Du spielst nur hier/.test(fokusKnopf("welt", fw.id)));

  // Ein Elternwunsch aus einer anderen Welt wartet, das Protokoll sagt warum
  const fremd = DATA.units.find(u => !inFw(u));
  S.wishes = [{ziel:"skill", id:fremd.skill, art:"jetzt", t:Date.now()}];
  const fw3 = waehleUnit();
  t("Fokus schlägt den Wunsch aus einer anderen Welt", inFw(fw3.unit), fw3.unit.skill);
  t("die Abweichung steht als Grund 'fokus' im Protokoll",
    fw3.log.some(e => e.grund === "fokus" && e.u.id === fw3.unit.id), JSON.stringify(fw3.log.map(e => e.grund)));
  S.wishes = [];

  // Umschalten auf alle Welten: die Wahl bleibt gemerkt, die Rotation ist zurück
  fokusSchalten(false);
  t("ausgeschaltet bleibt die Welt gemerkt", !!S.settings.fokus && !S.settings.fokusAn);
  const f4 = nextUnit();
  t("ausgeschaltet geht es wieder in andere Welten", !inFw(f4), f4.skill);
  fokusSchalten(true);
  t("wieder eingeschaltet geht es zurück in die Welt", inFw(nextUnit()));

  // Welt komplett: dann geht es normal weiter, und das Ergebnis sagt es
  unitsOfArea(fw.id).forEach(u => { S.units[u.id] = {stars:3, plays:1}; });
  t("komplette Welt: es geht in anderen Welten weiter", !inFw(nextUnit()));
  t("komplette Welt wird gefeiert", /komplett/.test(fokusStand()) && /🏆/.test(fokusUmschalter()));

  // Denkschule: Fokus auf eine Disziplin; im anderen Modus wirkt er nicht
  frisch();
  S.settings.modus = "v2";
  const dk = Object.keys(DISZIPLINEN).find(k => unitsOfDisziplin(k).length >= 2);
  setzeFokus("disziplin", dk);
  const ids = new Set(unitsOfDisziplin(dk).map(u => u.id));
  t("Disziplin-Fokus bleibt in der Disziplin", ids.has(nextUnit().id), dk);
  S.settings.modus = "v1";
  t("Disziplin-Fokus wirkt in der Weltenkarte nicht", fokusUnits() === null);

  // Laden: Unsinn wird verworfen, gültiger Fokus überlebt
  frisch();
  localStorage.setItem(KEY, JSON.stringify({v:1, settings:{fokus:{art:"welt", id:"gibtsnicht"}, fokusAn:true}}));
  let fokusGeladen = load();
  t("unbekannte Welt wird beim Laden verworfen", !fokusGeladen.settings.fokus && !fokusGeladen.settings.fokusAn);
  localStorage.setItem(KEY, JSON.stringify({v:1, settings:{fokus:{art:"welt", id:fw.id}, fokusAn:true}}));
  fokusGeladen = load();
  t("gültiger Fokus überlebt das Laden", fokusGeladen.settings.fokus && fokusGeladen.settings.fokus.id === fw.id && fokusGeladen.settings.fokusAn);
  frisch();

  // Alte Download-Adresse (Port 8790) wird beim Laden durch die eingebaute ersetzt
  {
    const merkB = BUILD.server;
    BUILD.server = "https://192.168.0.152:8792";
    localStorage.setItem(KEY, JSON.stringify({v:1, server:"192.168.0.79:8790"}));
    t("alte 8790-Adresse wird durch die eingebaute ersetzt", load().server === BUILD.server, load().server);
    localStorage.setItem(KEY, JSON.stringify({v:1, server:"10.0.0.5:8792"}));
    t("eine selbst eingetragene sichere Adresse bleibt", load().server === "10.0.0.5:8792");
    BUILD.server = "";
    localStorage.setItem(KEY, JSON.stringify({v:1, server:"192.168.0.79:8790"}));
    t("ohne eingebaute Adresse bleibt die alte stehen", load().server === "192.168.0.79:8790");
    BUILD.server = merkB;
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


# ------------------------------------------------------------ V3: legen, Papier,
# Merkbild, Wunsch-Bremse, Boden je Disziplin (AP-4). Die Regelsemantik von
# `legen` gibt es zweimal (Python-Kern und JS in src/app.html); hier werden
# beide Seiten Fall für Fall gegeneinander gehalten.
import itertools
import legen_kern as LK


def _regel_faelle():
    """[regel, anordnung, geordnet, erwartet] — erwartet kommt allein aus dem
    Python-Kern. Je Regelart alle Parameter über 4 Figuren und 3 Plätze, dazu
    Grenzfälle (fehlende Felder, unbekannte Art, falscher Modus, kein Objekt)."""
    faelle = []
    geordnete = list(itertools.permutations(range(4), 3))
    menge = list(itertools.combinations(range(4), 2))
    for art in LK.REGELN_GEORDNET:
        felder = LK._FELDER[art]
        for a in range(4):
            for zweit in range(3 if "platz" in felder else 4):
                regel = {"art": art, "a": a}
                regel[felder[1]] = zweit
                for anf in geordnete:
                    faelle.append([regel, list(anf), True, LK.regel_erfuellt(regel, anf, True)])
    for art in LK.REGELN_UNGEORDNET:
        for a in range(4):
            for b in range(4):
                regel = {"art": art, "a": a, "b": b}
                for anf in menge:
                    faelle.append([regel, list(anf), False, LK.regel_erfuellt(regel, anf, False)])
    # Grenzfälle
    for regel, geordnet in (({"art": "dabei", "a": 0}, True),          # Art gibt es nur ungeordnet
                            ({"art": "nebeneinander", "a": 0, "b": 1}, False),
                            ({"art": "gibtsnicht", "a": 0}, True),
                            ({"a": 0}, True),
                            ({"art": "nicht_platz"}, True),            # a fehlt
                            ({"art": "direkt_hinter", "a": 0}, True),  # b fehlt
                            ({"art": "zusammen", "a": 0}, False),
                            ("keine Regel", True), (None, False), ([], True)):
        for anf in ((0, 1, 2), (2, 1, 0), (3, 1, 2)):
            faelle.append([regel, list(anf), geordnet, LK.regel_erfuellt(regel, anf, geordnet)])
    # Jede Regelart muss in den Fällen sowohl erfüllt als auch verletzt vorkommen,
    # sonst prüft der Vergleich nichts.
    for art in LK.REGELN_GEORDNET + LK.REGELN_UNGEORDNET:
        erg = {f[3] for f in faelle if isinstance(f[0], dict) and f[0].get("art") == art
               and len(f[0]) >= 2 and f[2] == (art in LK.REGELN_GEORDNET)}
        assert erg == {True, False}, f"Regelart {art} deckt nicht beide Ausgänge ab"
    return faelle


REGEL_FAELLE = _regel_faelle()


JS_V3A = r"""
async () => {
  const out = [];
  const t = (name, cond, info) => out.push({name, ok: !!cond, info: info || ""});
  const frisch = () => { S = freshState(); S.settings.modus = "v2"; save(); };
  const app = () => document.getElementById("app");
  const text = () => app().textContent.replace(/\s+/g, " ");
  const schlaf = ms => new Promise(r => setTimeout(r, ms));
  const aEv = () => S.log.ev.filter(e => e.e === "a").length;
  const starte = task => beginSession({kind:"unit", unitId:null, title:"Test", intro:"", tasks:[task]});
  const knopf = re => [...app().querySelectorAll("button")].find(b => re.test(b.textContent));

  // ------------------------------------------- legen: JS == Kern, Fall für Fall
  const alleLegen = [];
  DATA.units.forEach(u => u.tasks.forEach(x => { if(x.type === "legen") alleLegen.push({q:u.id, task:x}); }));
  const imBestand = alleLegen.length;
  DENKCHECK.aufgaben.forEach(a => { if(a.task.type === "legen") alleLegen.push({q:a.id, task:a.task}); });
  const schief = alleLegen.filter(x => {
    const n = legenAlle(x.task).length;
    return n !== x.task.a || n !== x.task.kern.anzahl;
  });
  t(`legen: JS-Aufzählung == a == kern.anzahl in allen ${alleLegen.length} Aufgaben (Bestand ${imBestand}, Denk-Check ${alleLegen.length - imBestand})`,
    imBestand >= 20 && alleLegen.length - imBestand >= 15 && schief.length === 0,
    schief.slice(0, 3).map(x => x.q).join(","));

  const faelle = __REGEL_FAELLE__;
  const falsch = faelle.filter(([r, a, g, e]) => legenRegelErfuellt(r, a, g) !== e);
  t(`legen: legenRegelErfuellt == legen_kern.regel_erfuellt in ${faelle.length} Fällen (alle neun Regelarten, Grenzfälle)`,
    faelle.length > 2000 && falsch.length === 0, JSON.stringify(falsch.slice(0, 2)));

  // ---------------------------------------------------------- qLegen: Ablauf
  const roh = (n, k, g) => {
    const o = [], cur = [];
    const rec = s0 => {
      if(cur.length === k){ o.push(cur.slice()); return; }
      for(let i = g ? 0 : s0; i < n; i++){ if(g && cur.includes(i)) continue; cur.push(i); rec(i + 1); cur.pop(); }
    };
    rec(0); return o;
  };
  const geordnetT = alleLegen.map(x => x.task).find(x => x.geordnet === true && x.modus === "alle" &&
    x.regeln.length && x.a >= 3 && x.plaetze >= 3 && roh(x.figuren.length, x.plaetze, true).some(a => !legenGueltig(x, a)));
  const mengeT = alleLegen.map(x => x.task).find(x => x.geordnet === false && x.modus === "alle" &&
    x.a >= 3 && x.regeln.length && roh(x.figuren.length, x.plaetze, false).some(a => !legenGueltig(x, a)));
  t("legen: Beispielaufgaben (geordnet und Auswahl, mit Regeln) gefunden", !!geordnetT && !!mengeT);

  const lege = arr => arr.forEach(i => app().querySelectorAll(".lg-fig")[i].click());
  const pruefen = () => knopf(/Legen/).click();
  const meldung = () => app().querySelector(".lg-msg").textContent.trim();

  frisch();
  const G = geordnetT, L = legenAlle(G);
  const ungueltig = roh(G.figuren.length, G.plaetze, true).find(a => !legenGueltig(G, a));
  starte(G);
  t("legen: Typ-Bezeichnung 'Legen' und Figurenkarten", /Legen/.test(app().querySelector(".eyebrow").textContent) &&
    app().querySelectorAll(".lg-fig").length === G.figuren.length);
  t("legen: genau so viele leere Plätze wie plaetze, geordnet mit Nummern",
    app().querySelectorAll(".lg-slot").length === G.plaetze && app().querySelector(".lg-slot").textContent.trim() === "1");
  t("legen: Tippziele mindestens 44 px (CSS)", (() => {
    const css = [...document.styleSheets].flatMap(sh => [...sh.cssRules]).map(r => r.cssText).join("\n");
    return /\.lg-fig\s*\{[^}]*min-width:\s*44px/.test(css) && /\.lg-slot\s*\{[^}]*min-width:\s*44px/.test(css);
  })());
  t("legen: ohne Fund ist 'Das sind alle!' gesperrt", knopf(/Das sind alle/).disabled);
  t("legen: Vorlesen — der Satz q wird für legen vorgelesen", SESS.spokenFor === 0);
  t("legen: kein Erklär-Knopf (OHNE_ERKLAERUNG)", OHNE_ERKLAERUNG.has("legen") && !kannErklaeren(G));

  lege(L[0]);
  t("legen: Antippen legt auf den nächsten freien Platz (der Reihe nach)",
    app().querySelectorAll(".lg-slot.set").length === G.plaetze &&
    [...app().querySelectorAll(".lg-slot.set")].map(b => b.textContent.trim()).join("") ===
      L[0].map(i => G.figuren[i].bild).join(""));
  app().querySelectorAll(".lg-slot")[0].click();
  t("legen: Antippen eines belegten Platzes nimmt die Figur zurück",
    app().querySelectorAll(".lg-slot.set").length === G.plaetze - 1 &&
    app().querySelectorAll(".lg-fig.used").length === G.plaetze - 1);
  lege([L[0][0]]);   // dieselbe Figur wieder, landet auf dem ersten freien Platz = Platz 0
  pruefen();
  t("legen: gültig und neu — 'Gefunden: 1' als Mini-Reihe, Brett wieder leer",
    /Gefunden: 1/.test(text()) && app().querySelectorAll(".lg-mini").length === 1 &&
    app().querySelectorAll(".lg-slot.set").length === 0 && /Neu/.test(meldung()), text().slice(0, 160));
  lege(L[0]); pruefen();
  t("legen: doppelt — 'Die hast du schon!', Zahl bleibt 1",
    meldung() === "Die hast du schon!" && /Gefunden: 1/.test(text()));
  knopf(/↺/).click();
  lege(ungueltig); pruefen();
  t("legen: Regelverstoß — 'Das passt nicht zu den Regeln.', nichts gesammelt",
    meldung() === "Das passt nicht zu den Regeln." && /Gefunden: 1/.test(text()));
  knopf(/↺/).click();
  const aVor = aEv();
  knopf(/Das sind alle/).click();
  t("legen: 'Das sind alle!' bei zu wenigen ist falsch, genau EIN Antwortereignis",
    SESS.answered && SESS.lastOk === false && aEv() === aVor + 1, "a-Ereignisse +" + (aEv() - aVor));
  t(`legen: Rückmeldung 'Es gibt ${G.a}. Diese fehlen noch:' mit ${G.a - 1} Mini-Reihen`,
    text().includes("Es gibt " + G.a + ".") && text().includes("Diese fehlen noch") &&
    app().querySelectorAll(".fb .lg-mini").length === G.a - 1);
  t("legen: nach der Antwort kein Brett mehr", app().querySelectorAll(".lg-fig").length === 0);

  frisch(); starte(G);
  L.forEach(a => { lege(a); pruefen(); });
  t("legen: alle gefunden — 'Gefunden: " + L.length + "'", text().includes("Gefunden: " + L.length));
  const a2 = aEv();
  knopf(/Das sind alle/).click();
  t("legen: 'Das sind alle!' mit allen gefundenen ist richtig (ein Ereignis)",
    SESS.lastOk === true && aEv() === a2 + 1 && /Genau, es gibt/.test(text()));

  // Auswahl: dieselbe Menge in anderer Reihenfolge ist doppelt
  frisch();
  const M = mengeT, ML = legenAlle(M);
  starte(M);
  t("legen: ungeordnet — Plätze ohne Nummer", app().querySelector(".lg-slot").textContent.trim() === "");
  lege(ML[0].slice().reverse()); pruefen();
  t("legen: Auswahl legen — neu", /Gefunden: 1/.test(text()));
  lege(ML[0]); pruefen();
  t("legen: gleiche Menge in anderer Reihenfolge ist doppelt", meldung() === "Die hast du schon!");

  // Modus zaehlen
  frisch();
  const Z = Object.assign({}, G, {modus:"zaehlen"});
  starte(Z);
  lege(L[0]); pruefen();
  t("legen (zählen): das Brett darf zum Ausprobieren benutzt werden und ein Ziffernfeld ist da",
    /Gefunden: 1/.test(text()) && app().querySelectorAll(".pad button").length === 12);
  const a3 = aEv();
  String(G.a).split("").forEach(ch => padKey(ch)); checkZahl();
  t("legen (zählen): Zahl == a ist richtig, ein Ereignis", SESS.lastOk === true && aEv() === a3 + 1);
  frisch(); starte(Z);
  String(G.a + 1).split("").forEach(ch => padKey(ch)); checkZahl();
  t(`legen (zählen): falsche Zahl — 'Es gibt ${G.a}.' und alle ${G.a} gültigen als Mini-Reihen`,
    SESS.lastOk === false && text().includes("Es gibt " + G.a + ".") &&
    app().querySelectorAll(".fb .lg-mini").length === G.a);
  const grosse = {type:"legen", q:"Wie viele Reihenfolgen gibt es?", figuren:G.figuren.concat(
      ["Katze","Drache","Biene"].map((n, i) => ({name:n, bild:["🐱","🐲","🐝"][i]}))).slice(0, 6),
    plaetze:6, geordnet:true, modus:"zaehlen", regeln:[], a:720, hint:"Denk an 6 mal 5 mal 4 ..."};
  t("legen: JS zählt 720 für sechs Figuren auf sechs Plätzen", legenAlle(grosse).length === 720);
  frisch(); starte(grosse);
  "5".split("").forEach(ch => padKey(ch)); checkZahl();
  t("legen (zählen, N > 24): nur die Zahl und der Tipp, keine Mini-Reihen",
    SESS.lastOk === false && text().includes("Es gibt 720.") &&
    app().querySelectorAll(".fb .lg-mini").length === 0 && text().includes("Denk an 6 mal 5"));

  // ------------------------------------------------------------------ Papier
  frisch();
  const mitPapier = DATA.units.flatMap(u => u.tasks).find(x => x.papier === true);
  const ohnePapier = DATA.units.flatMap(u => u.tasks).find(x => x.papier !== true && x.type === "zahl");
  starte(mitPapier);
  const hPapier = VIEWS.session();
  t("Papier: Streifen '📝 Papier und Stift erlaubt' erscheint bei papier:true",
    hPapier.includes("📝 Papier und Stift erlaubt"));
  t("Papier: der Streifen steht über der Frage", hPapier.indexOf("Papier und Stift") < hPapier.indexOf('class="word'));
  starte(ohnePapier);
  t("Papier: ohne papier:true kein Streifen", !VIEWS.session().includes("Papier und Stift"));

  // ------------------------------------------------------ bildzahl: jede Art
  const arten = {};
  DATA.units.forEach(u => u.tasks.forEach(x => { if(x.type === "bildzahl" && !arten[x.kern.art]) arten[x.kern.art] = x; }));
  const artNamen = Object.keys(arten);
  t("bildzahl: Bestand trägt mehrere Kern-Arten", artNamen.length >= 4, artNamen.join(","));
  let artFehler = [];
  for(const art of artNamen){
    const x = arten[art];
    frisch(); starte(x);
    const ohneFrage = app().innerHTML.split(esc(x.q)).join("");
    String(x.a).split("").forEach(ch => padKey(ch)); checkZahl();
    if(!(SESS.lastOk === true && /Richtig ist/.test(text()))) artFehler.push(art + ": nicht richtig");
    if(art !== "wuerfelgebaeude" && /Würfel/.test(ohneFrage)) artFehler.push(art + ": 'Würfel' in der Oberfläche");
  }
  t("bildzahl: jede Kern-Art lässt sich lösen, ohne Würfel-Annahme im Text", artFehler.length === 0, artFehler.join("; "));

  // ---------------------------------------------------------------- Merkbild
  frisch();
  const mk = Object.assign({}, DENKCHECK.aufgaben.find(a => a.task.merken_ms).task, {merken_ms:200});
  starte(mk);
  const t0 = Date.now();
  t("Merkbild: erst nur das Fragebild und der Fortschrittsbalken, keine Optionen",
    app().querySelectorAll(".bw-opt").length === 0 && !!app().querySelector(".merk-balken") &&
    !!app().querySelector(".bw-frage svg"));
  await schlaf(70);
  render();   // ein Neuzeichnen darf weder die Zeit verlängern noch den Balken neu starten
  t("Merkbild: nach einem Neuzeichnen läuft der Balken weiter (negativer Versatz)",
    /animation-delay:\s*-\d+ms/.test(app().querySelector(".merk-balken i").getAttribute("style")) &&
    app().querySelectorAll(".bw-opt").length === 0);
  await schlaf(330);
  const nachAblauf = Date.now() - t0;
  t("Merkbild: nach merken_ms Platzhalter 'Wie sah es aus?' und erst jetzt die Optionen",
    app().querySelectorAll(".bw-opt").length === mk.optionen_svg.length &&
    text().includes("Wie sah es aus?") && !app().querySelector(".merk-balken") &&
    !app().querySelector(".bw-frage svg"), "nach " + nachAblauf + " ms");
  chooseBild(mk.richtig);
  const evM = S.log.ev[S.log.ev.length - 1];
  const gesamt = Date.now() - t0;
  t("Merkbild: ms im Antwortereignis zählt ab Erscheinen der Optionen",
    evM.e === "a" && evM.ms < gesamt - 150 && evM.ms >= 0, `ms=${evM.ms}, seit Start ${gesamt}`);
  t("Merkbild: nach der Antwort ist das Fragebild wieder sichtbar und die Lösung markiert",
    SESS.lastOk === true && !!app().querySelector(".bw-frage svg") && !!app().querySelector(".bw-opt.right"));

  // ------------------------------------------------------------ Wunsch-Bremse
  frisch();
  const uid = DATA.units[0].id, tage = [];
  for(let k = 1; k <= 9; k++){
    vermerkeAbbruch(uid, 0);
    const x = S.units[uid];
    tage.push(x.sofort >= 3 ? Math.round((x.pausiertBis - Date.now()) / DAY) : 0);
  }
  t("Wunsch-Bremse: Pause 0,0,1,2,4,8,14,14,14 Tage ab dem 3. Sofort-Abbruch in Folge",
    JSON.stringify(tage) === "[0,0,1,2,4,8,14,14,14]", JSON.stringify(tage));
  t("Wunsch-Bremse: das Paket gilt als pausiert", istPausiert(UNITS[uid]));
  vermerkeAbbruch(uid, 4);
  t("Wunsch-Bremse: ein Lauf mit Antworten setzt den Zähler zurück", S.units[uid].sofort === 0);
  vermerkeAbbruch(uid, 0); vermerkeAbbruch(uid, 0); vermerkeAbbruch(uid, 0);
  t("Wunsch-Bremse: danach beginnt die Staffel wieder bei einem Tag",
    Math.round((S.units[uid].pausiertBis - Date.now()) / DAY) === 1);
  t("Wunsch-Bremse: sofortPauseMs 1/2/4/8/14 Tage",
    [3, 4, 5, 6, 7, 20].map(n => sofortPauseMs(n) / DAY).join() === "1,2,4,8,14,14" && sofortPauseMs(2) === 0);

  // ------------------------------------------------------ Boden je Disziplin
  frisch();
  const disz = "muster", dUnits = unitsOfDisziplin(disz);
  const hoch = dUnits[dUnits.length - 1], tief = dUnits[0];
  t("Boden: Beispieldisziplin hat Pakete auf mehreren Stufen", hoch.stage > tief.stage + 1, tief.stage + ".." + hoch.stage);
  const ohneBoden = waehleAus(false, dUnits).unit;
  t("Boden: ohne Boden kommt ein Paket nahe dem Weltniveau", ohneBoden.stage <= areaStage(skillOf(ohneBoden.skill).area) + 1,
    ohneBoden.id);
  S.profile.checkBoden = {[disz]: hoch.stage};
  t("Boden: zielStufe = max(Weltniveau, Boden)", zielStufe(hoch) === hoch.stage &&
    zielStufe(tief) === Math.max(areaStage(skillOf(tief.skill).area), hoch.stage));
  const mitBoden = waehleAus(false, dUnits).unit;
  t("Boden: waehleAus wählt ein Paket auf der Boden-Stufe", mitBoden.stage === hoch.stage, mitBoden.id);
  t("Boden: sortiere stellt das Paket der Boden-Stufe nach vorn",
    sortiere(dUnits.filter(u => u.stage === hoch.stage || u.stage === tief.stage), false)[0].stage === hoch.stage);
  t("Boden: 'Gib mir was Schwereres' orientiert sich ebenfalls am Boden",
    waehleAus(true, dUnits).unit.stage >= hoch.stage);
  const fremd = DATA.units.find(u => DISZIPLIN_VON[u.skill] && DISZIPLIN_VON[u.skill] !== disz);
  t("Boden: gilt nur für seine Disziplin", zielStufe(fremd) === areaStage(skillOf(fremd.skill).area));
  const schule = DATA.units.find(u => !DISZIPLIN_VON[u.skill]);
  t("Boden: Schulstoff ohne Disziplin kennt keinen Boden", zielStufe(schule) === areaStage(skillOf(schule.skill).area));
  S.settings.modus = "v1";
  t("Boden: im klassischen Modus (V1) wirkt er nicht", zielStufe(hoch) === areaStage(skillOf(hoch.skill).area));
  S.settings.modus = "v2";

  // Fokus (Nur hier spielen) bleibt trotz Boden in seiner Disziplin
  setzeFokus("disziplin", disz);
  const fk = waehleUnit();
  t("Boden + Fokus: 'Nur hier spielen' bleibt in der Disziplin und folgt dem Boden",
    DISZIPLIN_VON[fk.unit.skill] === disz && fk.unit.stage === hoch.stage, fk.unit.id);
  fokusSchalten(false);

  // Laden und Säubern
  const stand = JSON.parse(JSON.stringify(S));
  stand.profile.checkBoden = {muster:4, logik:99, raum:"x", gibtsnicht:3, algorithmik:0, kombinatorik:2.7};
  localStorage.setItem(KEY, JSON.stringify(stand));
  const geladen = load();
  t("Boden: laden säubert (nur bekannte Disziplinen, Stufe 1..MAX_STAGE)",
    JSON.stringify(geladen.profile.checkBoden) === JSON.stringify({muster:4, kombinatorik:2}),
    JSON.stringify(geladen.profile.checkBoden));
  stand.profile.checkBoden = "kaputt";
  localStorage.setItem(KEY, JSON.stringify(stand));
  t("Boden: ein beschädigter Eintrag wird zu {}", JSON.stringify(load().profile.checkBoden) === "{}");

  frisch();
  return out;
}
"""


JS_V3B = r"""
async () => {
  const out = [];
  const t = (name, cond, info) => out.push({name, ok: !!cond, info: info || ""});
  const frisch = () => { S = freshState(); S.settings.modus = "v2"; save(); };
  const app = () => document.getElementById("app");
  const text = () => app().textContent.replace(/\s+/g, " ");
  const J = JSON.stringify;

  // ------------------------------------------------------------ Treppenverfahren
  const stufen = (start, antworten) => {
    const folge = [];
    antworten.forEach(o => folge.push({id:"x", stufe:dcNaechsteStufe(folge, start), o:o ? 1 : 0, ms:1000}));
    return folge;
  };
  const bsp = (start, ant, soll, e, z) => {
    const f = stufen(start, ant), est = dcSchaetzung(f);
    t(`Treppe: Start ${start}, ${ant.map(o => o ? "r" : "f").join(",")} -> Stufen ${soll.join(",")}, E=${e}, z=${z}`,
      J(f.map(a => a.stufe)) === J(soll) && est.e === e && est.z === z, J(f.map(a => a.stufe)) + " E=" + est.e + " z=" + est.z);
  };
  bsp(3, [1, 1, 0, 1], [3, 5, 7, 6], 6.5, 0);
  bsp(3, [0, 1, 1, 1], [3, 2, 3, 4], 4.5, 1);
  bsp(3, [0, 0, 0, 0], [3, 2, 2, 2], 1.5, -1);
  bsp(3, [1, 1, 1, 1], [3, 5, 7, 8], 8.5, 1);
  bsp(8, [1, 1, 0, 0], [8, 8, 8, 7], 8.5, 1);
  {
    const f = stufen(2, [0, 0, 1, 0]), est = dcSchaetzung(f);
    t("Treppe: Fehler zuerst, dann richtig: danach nur +1, Stufen bleiben in 2..8",
      J(f.map(a => a.stufe)) === "[2,2,2,3]" && est.e === 2.5 && est.z === 0, J(f.map(a => a.stufe)) + " E=" + est.e);
  }
  S = freshState();
  const starts = [0, 1, 3, 4, 9].map(e => { S.profile.einstieg = e; return dcStartStufe(); });
  t("Treppe: Start = max(2, min(8, Einstieg - 1)), ohne Klasse gilt 3", J(starts) === "[2,2,2,3,8]", J(starts));

  // ----------------------------------------------------- Aufgabenbank, Auswahl
  const dims = Object.keys(DENKCHECK.dimensionen);
  t("Bank: 9 Dimensionen, je Stufe 2..8 mindestens zwei Aufgaben",
    dims.length === 9 && dims.every(d => [2, 3, 4, 5, 6, 7, 8].every(st =>
      DENKCHECK.aufgaben.filter(a => a.dim === d && a.stufe === st).length >= 2)));
  t("Bank: Runde A und B laut dimensionen[*].runde (5 + 4)",
    J(dcDimsVon("A")) === J(["strukturen", "schlussketten", "algorithmik", "darstellung", "raum"]) &&
    J(dcDimsVon("B")) === J(["umkehren", "merken", "systematik", "rechnen"]));
  t("Bank: kaepnick und boden dürfen null sein", DENKCHECK.dimensionen.darstellung.boden === null &&
    DENKCHECK.dimensionen.algorithmik.kaepnick === null);

  // ------------------------------------------------------------ die Karte
  frisch();
  go("home");
  t("Karte: Startseite zeigt '🧭 Denk-Check — finde deine Superkräfte (2 kurze Runden)'",
    text().includes("Denk-Check — finde deine Superkräfte") && text().includes("(2 kurze Runden)"));
  go("settings");
  t("Einstellungen haben einen Denk-Check-Eintrag", text().includes("Denk-Check") && /Starten/.test(text()));

  // --------------------------------------- der Lauf, Runde A, mit Unterbrechung
  frisch();
  S.profile.einstieg = 4; S.profile.xp = 40; S.profile.todayCount = 2; S.profile.streak = 3;
  const uX = DATA.units[0];
  S.skills[uX.skill] = {l:2, d:123, c:3, w:1, h:[1, 0, 1]};
  S.units[uX.id] = {stars:2, plays:1, sofort:0, pausiertBis:0, rev:""};
  save();
  const lernstand = () => J([S.skills, S.units, S.profile.xp, S.profile.todayCount, S.profile.streak,
    S.profile.lastDay, S.profile.badges, S.typLog, S.stats.correct, S.stats.packs, S.stats.bestCombo,
    S.stats.knobel, S.spassZaehler, S.plan]);
  const vorher = lernstand(), ansVor = S.stats.answers;

  const muster = {strukturen:[1, 1, 0, 1], schlussketten:[0, 1, 1, 1], algorithmik:[0, 0, 0, 0],
                  darstellung:[1, 1, 1, 1], raum:[1, 0, 1, 1]};
  const soll = [["strukturen", [3, 5, 7, 6]], ["schlussketten", [3, 2, 3, 4]], ["algorithmik", [3, 2, 2, 2]],
                ["darstellung", [3, 5, 7, 8]], ["raum", [3, 5, 4, 5]]];
  const sollFolge = soll.flatMap(([d, st]) => st.map(s => d + ":" + s));

  dcOeffnen();
  t("Ablauf: Antippen der Karte öffnet die Einleitung von Runde A", view.name === "denkcheck" &&
    view.opts.phase === "intro" && view.opts.runde === "A" && view.opts.weiter === false);
  t("Ablauf: die Einleitung ist kurz und vorlesbar (ohne Noten/Punkte)", dcIntroText("A", false).length < 400 &&
    /keine Noten/.test(dcIntroText("A", false)));
  dcLos("A");
  t("Ablauf: die erste Aufgabe ist die erste Dimension auf der Start-Stufe 3",
    SESS.kind === "denkcheck" && SESS.tasks[SESS.i].dcDim === "strukturen" && SESS.tasks[SESS.i].dcStufe === 3);
  t("Ablauf: Denk-Check-Aufgaben werden immer vorgelesen", SESS.spokenFor === 0);
  t("Ablauf: kein Übungstag, kein Tagesziel durch den Start", S.profile.todayCount === 2);

  const gesehen = [];
  let idx = 0, unterbrochen = false, zaehlerText = [];
  const antworte = () => {
    const task = SESS.tasks[SESS.i];
    gesehen.push(task.dcDim + ":" + task.dcStufe);
    zaehlerText.push(app().querySelector(".combo").textContent.trim());
    const ok = muster[task.dcDim][gesehen.filter(g => g.startsWith(task.dcDim + ":")).length - 1] === 1;
    grade(ok);
    return ok;
  };
  let neutral = true, neutralInfo = "";
  while(SESS && idx < 25){
    antworte(); idx++;
    const h = VIEWS.session();
    if(!/Weiter!/.test(h) || /class="fb|✗|✓ /.test(h) || /\bright\b|\bwrong\b/.test(h)){ neutral = false; neutralInfo = "bei Antwort " + idx; }
    if(SESS.tasks.length !== SESS.i + 1 || SESS.tasks.some(x => x.redo)){ neutral = false; neutralInfo = "Wiederholung bei " + idx; }
    if(idx === 6 && !unterbrochen){
      unterbrochen = true;
      const stehen = S.stats.answers - ansVor;
      quitSession();              // jederzeit aufhören, ohne Rückfrage
      t("Unterbrechen: ✕ beendet die Sitzung ohne Rückfrage, der Stand bleibt", SESS === null && view.name === "home" && stehen === 6);
      S = load();                 // wie nach einem App-Neustart
      const lauf = dcOffenerLauf();
      t("Unterbrechen: der offene Lauf überlebt Speichern und Laden (6 von 20)",
        !!lauf && dcZaehlung(lauf, "A").beantwortet === 6 && dcZaehlung(lauf, "A").gesamt === 20);
      t("Unterbrechen: die Karte sagt, wo es weitergeht", dcKarte().includes("Weiter bei Runde A"));
      dcOeffnen();
      t("Fortsetzen: die Einleitung sagt 'weitermachen'", view.opts.weiter === true && /weiter/i.test(dcIntroText("A", true)));
      dcLos("A");
      continue;
    }
    nextTask();
  }
  t("Ablauf: die Folge der gestellten Stufen == Treppe (20 Aufgaben, mit Unterbrechung nach 6)",
    J(gesehen) === J(sollFolge), J(gesehen));
  t("Ablauf: Fortschritt 'Runde A · 7 von 20' (gezählt wird die laufende Aufgabe)",
    zaehlerText[6] === "Runde A · 7 von 20" && zaehlerText[0] === "Runde A · 1 von 20" &&
    zaehlerText[19] === "Runde A · 20 von 20", J([zaehlerText[0], zaehlerText[6], zaehlerText[19]]));
  t("Rückmeldung: nach jeder Antwort neutral '👍 Weiter!', kein Rot/Grün, keine Wiederholung", neutral, neutralInfo);

  const lA = S.denkcheck.laeufe[0];
  t("Runde A: nach der 20. Antwort ist die Runde abgeschlossen (Zwischenstand-Ansicht)",
    SESS === null && view.name === "denkcheck" && view.opts.phase === "rundeFertig" && lA.runde.A.fertig > 0 && !lA.fertig);
  const erg = soll.map(([d]) => { const x = lA.runde.A.dims[d]; return d + " " + x.e + " " + x.z; });
  t("Runde A: Schätzung E und Vermerk z je Dimension",
    J(erg) === J(["strukturen 6.5 0", "schlussketten 4.5 1", "algorithmik 1.5 -1", "darstellung 8.5 1", "raum 5.5 1"]), J(erg));
  const cEv = S.log.ev.filter(e => e.e === "c"), aDc = S.log.ev.filter(e => e.e === "a" && e.u === "denkcheck");
  t("Ereignisse: je abgeschlossener Dimension ein 'c' (5), mit i,t,s,k,g,n,c,ms,z",
    cEv.length === 5 && cEv.every(e => ["i", "t", "s", "k", "g", "n", "c", "ms", "z"].every(f => f in e)), J(cEv[0]));
  t("Ereignisse: 'c' strukturen = g 6.5, n 4, c 3, z 0",
    cEv[0].k === "strukturen" && cEv[0].g === 6.5 && cEv[0].n === 4 && cEv[0].c === 3 && cEv[0].z === 0);
  t("Ereignisse: 'c' algorithmik z=-1, darstellung z=1", cEv[2].z === -1 && cEv[3].z === 1);
  t("Ereignisse: 20 Antworten 'a' mit u:'denkcheck', k gesetzt, g = Stufe",
    aDc.length === 20 && aDc.every(e => e.k && e.g >= 2 && e.g <= 8) && S.log.ev.filter(e => e.e === "a").length === 20);
  t("Zählung: stats.answers wächst um 20 (Abgleich mit dem Dienst), nicht todayCount",
    S.stats.answers === ansVor + 20 && S.stats.check === 20 && S.profile.todayCount === 2,
    J([ansVor, S.stats.answers, S.stats.check, S.profile.todayCount]));
  t("Lernstand unberührt: Fertigkeiten, Pakete, XP, Kombo, Abzeichen, Leitner", lernstand() === vorher);
  t("Wirkung: Boden je Disziplin = max(1, floor(E) - 1) für Dimensionen mit boden",
    J(S.profile.checkBoden) === J({muster:5, logik:3, algorithmik:1, raum:4}), J(S.profile.checkBoden));

  // Zwischenstand: Superkräfte sind nur Stärken
  const kA = dcSuperkraefte(lA).map(k => k.dim);
  t("Superkräfte (Zwischenstand): die zwei höchsten E, nie eine Dimension ohne Treffer",
    J(kA) === J(["darstellung", "strukturen"]), J(kA));
  t("Zwischenstand-Ansicht: Titel der Stärken, kein Wort über Schwächen, keine Zahlen",
    text().includes("Bilder in Zahlen") && text().includes("Muster und Strukturen") &&
    !text().includes("Befehle und Abläufe") && !text().includes("Schlussfolgern") && !/\d/.test(text()) &&
    !/schwach|Schwäche|schlecht|leider|falsch/i.test(text()) && text().includes("freut sich"), text());

  // --------------------------------------------------------------- Runde B
  dcIntro("B", false);
  t("Runde B: eigene Einleitung", view.opts.runde === "B" && /Runde B/.test(text()));
  dcLos("B");
  const musterB = {umkehren:[1, 1, 0, 1], merken:[1, 0, 1, 1], systematik:[0, 0, 0, 0], rechnen:[1, 1, 1, 1]};
  const nB = {}; let guard = 0;
  while(SESS && guard++ < 30){
    const task = SESS.tasks[SESS.i];
    nB[task.dcDim] = (nB[task.dcDim] || 0) + 1;
    grade(musterB[task.dcDim][nB[task.dcDim] - 1] === 1);
    nextTask();
  }
  const lB = S.denkcheck.laeufe[0];
  t("Runde B: 16 Antworten, Lauf fertig, Ergebnis-Ansicht",
    J(nB) === J({umkehren:4, merken:4, systematik:4, rechnen:4}) && lB.fertig > 0 &&
    view.name === "denkcheck" && view.opts.phase === "ergebnis", J(nB));
  t("Runde B: 36 Antworten insgesamt, 9 'c'-Ereignisse",
    S.stats.answers === ansVor + 36 && S.log.ev.filter(e => e.e === "c").length === 9 &&
    S.log.ev.filter(e => e.e === "a" && e.u === "denkcheck").length === 36);
  t("Lernstand bleibt auch nach Runde B unberührt", lernstand() === vorher);
  t("Wirkung: Boden für systematik -> kombinatorik gesetzt (floor(E)-1, mindestens 1)",
    S.profile.checkBoden.kombinatorik === 1 && !("umkehren" in S.profile.checkBoden));
  const kB = dcSuperkraefte(lB).map(k => k.dim).sort();
  t("Superkräfte (Ergebnis): bei Gleichstand um den zweiten Platz beide", J(kB) === J(["darstellung", "rechnen"]), J(kB));
  {
    // Überall gleich stark: höchstens drei Superkräfte, sonst sagt das Lob nichts
    const gleich = JSON.parse(JSON.stringify(lB));
    for(const r of ["A", "B"]) for(const dim of Object.keys(gleich.runde[r].dims))
      gleich.runde[r].dims[dim] = Object.assign({}, gleich.runde[r].dims[dim], {e:5, z:0});
    const kG = dcSuperkraefte(gleich);
    t("Superkräfte: bei lauter Gleichstand höchstens drei", kG.length === 3, J(kG.map(k => k.dim)));
  }
  {
    // Fund der unabhängigen Prüfung: Runden fertig, Lauf offen, aber leer —
    // das ließ „Los geht's“ mit einem TypeError abstürzen, auch nach Neuladen.
    const merk = localStorage.getItem(KEY);
    localStorage.setItem(KEY, JSON.stringify({v:1, denkcheck:{laeufe:[
      {fertig:0, runde:{A:{fertig:1}, B:{fertig:1}}}]}}));
    const sv = S, ssv = SESS, vsv = view;
    S = load();
    const l0 = S.denkcheck.laeufe[0];
    t("Widersprüchlicher Denk-Check-Stand wird beim Laden zurechtgerückt",
      l0 && !l0.fertig && !l0.runde.A.fertig && !l0.runde.B.fertig, J(l0));
    let fehler = "";
    try{ dcLos("A"); }catch(e){ fehler = String(e); }
    t("Danach startet der Denk-Check ohne Fehler", !fehler && SESS && SESS.kind === "denkcheck", fehler);
    // Auch ohne Säuberung (Stand mitten im Lauf so entstanden): keine Sackgasse
    S.denkcheck.laeufe = [{start:1, fertig:0, runde:{A:{fertig:1, dims:{}}, B:{fertig:1, dims:{}}}}];
    fehler = "";
    try{ dcLos("A"); }catch(e){ fehler = String(e); }
    t("Ein offener Lauf ohne offene Runde führt in einen neuen Lauf",
      !fehler && SESS && SESS.kind === "denkcheck" && S.denkcheck.laeufe.length === 2, fehler);
    SESS = ssv; S = sv; view = vsv; render();
    if(merk === null) localStorage.removeItem(KEY); else localStorage.setItem(KEY, merk);
  }
  t("Ergebnis-Ansicht: 'Deine Superkräfte', Emoji und lobender Satz, ohne Schwächen und Zahlen",
    text().includes("Deine Superkräfte") && text().includes("Du rechnest flink") && !/\d/.test(text()) &&
    !/schwach|Schwäche|schlecht|leider|falsch|nicht/i.test(text()) && !text().includes("Rückwärts denken"), text());

  go("home");
  t("Karte weg: ein frisch fertiger Check wird nicht mehr angeboten", dcFaellig() === false && dcKarte() === "");
  go("settings");
  t("Einstellungen: vorzeitige Wiederholung bleibt möglich", /Noch einmal machen/.test(text()));
  lB.fertig = Date.now() - 89 * DAY;
  t("Wiederholung: nach 89 Tagen noch nicht fällig", dcFaellig() === false);
  lB.fertig = Date.now() - 91 * DAY;
  go("home");
  t("Wiederholung: nach 91 Tagen erscheint die Karte wieder", dcFaellig() === true && text().includes("Denk-Check — finde"));

  // Wiederholung: unbenutzte Aufgaben zuerst
  const altIds = new Set(Object.values(lB.runde.A.dims).concat(Object.values(lB.runde.B.dims)).flatMap(d => d.folge.map(a => a.id)));
  const alteStrukt = [...altIds].filter(i => i.startsWith("strukturen-")).length;
  dcOeffnen();
  t("Wiederholung: die Einleitung beginnt von vorn (nicht 'weitermachen')", view.opts.weiter === false && view.opts.runde === "A");
  dcLos("A");
  const erstes = SESS.tasks[SESS.i];
  t("Wiederholung: ein neuer Lauf, die erste Aufgabe ist eine bisher unbenutzte",
    S.denkcheck.laeufe.length === 2 && !altIds.has(erstes.dcId) && alteStrukt >= 1, erstes.dcId);
  quitSession();

  // ------------------------------------------- Säuberung beim Laden
  frisch();
  localStorage.setItem(KEY, J({v:1, denkcheck:{laeufe:[
      "x", {runde:5},
      {start:"a", runde:{A:{dims:{strukturen:{folge:[{id:"strukturen-4-1", stufe:99, o:7, ms:-5}, {id:5}, null, "x",
          {id:"b", stufe:1}, {id:"c", stufe:4, o:1, ms:9e9}, {id:"d", stufe:4}, {id:"e", stufe:4}], e:"x", z:5},
          gibtsnicht:{folge:[]}, umkehren:{folge:[]}}}}}],
      benutzt:[1, "ok", {}, "x".repeat(99)]}}));
  const g = load(), gl = g.denkcheck.laeufe[0] || {};
  const gs = (((gl.runde || {}).A || {}).dims || {}).strukturen || {folge:[]};
  t("Laden: kaputte Läufe fallen weg, bekannte Dimension bleibt, unbekannte nicht",
    g.denkcheck.laeufe.length === 1 && !!gs.folge.length && !("gibtsnicht" in gl.runde.A.dims), J(g.denkcheck));
  t("Laden: Stufen in 2..8, o nur 0/1, ms in 0..600000, höchstens 4 Antworten, e null, z in -1/0/1",
    gs.folge.length === 4 && gs.folge.every(a => a.stufe >= 2 && a.stufe <= 8 && (a.o === 0 || a.o === 1) &&
      a.ms >= 0 && a.ms <= 600000) && gs.e === null && gs.z === 0, J(gs));
  t("Laden: benutzt enthält nur kurze Texte", J(g.denkcheck.benutzt) === J(["ok"]));
  localStorage.setItem(KEY, J({v:1, denkcheck:"kaputt"}));
  t("Laden: ein kaputter Denk-Check-Eintrag ergibt einen leeren Stand", J(load().denkcheck) === J({laeufe:[], benutzt:[]}));
  localStorage.setItem(KEY, J({v:1, denkcheck:{laeufe:Array.from({length:50}, () => ({start:1, fertig:1, runde:{A:{}, B:{}}}))}}));
  t("Laden: höchstens DC_LAEUFE_MAX Läufe", load().denkcheck.laeufe.length === DC_LAEUFE_MAX);

  // ----------------------------------- Superkräfte zeigen nie eine Schwäche
  const baue = es => {
    const lauf = {start:1, fertig:1, runde:{A:{fertig:1, dims:{}}, B:{fertig:1, dims:{}}}};
    for(const [d, [e, z]] of Object.entries(es)) lauf.runde[DENKCHECK.dimensionen[d].runde].dims[d] = {folge:[], e, z};
    return lauf;
  };
  const titel = Object.fromEntries(dims.map(d => [d, DENKCHECK.dimensionen[d].titel]));
  let rnd = 12345; const zufall = () => (rnd = (rnd * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
  let fehler = [];
  for(let n = 0; n < 150; n++){
    const es = {};
    dims.forEach(d => { if(zufall() < .8) es[d] = [Math.round((1.5 + zufall() * 7) * 2) / 2, zufall() < .3 ? -1 : (zufall() < .4 ? 1 : 0)]; });
    const lauf = baue(es), k = dcSuperkraefte(lauf);
    const ok = Object.entries(es).filter(([d, [e, z]]) => z !== -1);
    if(k.some(x => es[x.dim][1] === -1)) fehler.push("Dimension ohne Treffer als Stärke " + J(es));
    if(ok.length && !k.length) fehler.push("keine Stärke trotz Treffern " + J(es));
    if(!ok.length && k.length) fehler.push("Stärke ohne Treffer " + J(es));
    const minK = Math.min(...k.map(x => x.e)), uebrig = ok.filter(([d]) => !k.some(x => x.dim === d));
    if(uebrig.some(([d, [e]]) => e > minK)) fehler.push("höheres E nicht dabei " + J(es));
    if(k.length < Math.min(2, ok.length)) fehler.push("weniger als zwei " + J(es));
    go("denkcheck", {phase:n % 2 ? "ergebnis" : "rundeFertig", runde:"A", lauf, gesprochen:true});
    const nicht = dims.filter(d => !k.some(x => x.dim === d)).filter(d => text().includes(titel[d]));
    if(nicht.length) fehler.push("Titel einer Nicht-Stärke sichtbar: " + nicht.join() + " " + J(es));
    if(/\d|schwach|Schwäche|schlecht|leider/i.test(text())) fehler.push("Zahl oder Schwäche im Text " + J(es));
  }
  t("Superkräfte: in 150 Zufallsprofilen nie eine Schwäche, nie eine Zahl, immer die höchsten", fehler.length === 0, fehler.slice(0, 2).join(" | "));
  go("denkcheck", {phase:"ergebnis", runde:"A", gesprochen:true,
    lauf:baue({strukturen:[1.5, -1], raum:[1.5, -1], merken:[1.5, -1]})});
  t("Superkräfte: ganz ohne Treffer bleibt ein freundlicher Satz", text().includes("Du hast richtig gut mitgedacht!"));

  // Stats-Ansicht: Trefferquote ohne Denk-Check-Antworten
  frisch(); S.stats.answers = 10; S.stats.correct = 0; S.stats.check = 10;
  go("stats");
  t("Dein Stand: die Trefferquote rechnet die Denk-Check-Antworten nicht mit (Division durch 0 abgefangen)",
    !/NaN|Infinity/.test(text()));
  S.stats.answers = 20; S.stats.correct = 5; S.stats.check = 10;
  go("stats");
  t("Dein Stand: 5 richtig von 10 geübten Antworten = 50 %", /50\s*%/.test(text()), text().slice(0, 200));

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
        js3a = JS_V3A.replace("__REGEL_FAELLE__", json.dumps(REGEL_FAELLE, ensure_ascii=False))
        res += page.evaluate(js3a)
        res += page.evaluate(JS_V3B)
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
