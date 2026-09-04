# -*- coding: utf-8 -*-
"""Prüft die Klassenstufe und den Fundus.

  .venv/bin/python build/klassen_test.py

Zwei Dinge, die beide schiefgehen können, ohne dass es jemand merkt:

  · Die Klassenstufe setzt einen BODEN, keine Decke. Wird daraus versehentlich
    eine Decke, sitzt ein schnelles Kind auf seiner Einstiegsstufe fest und
    niemand sieht es — die App würde ja weiter Aufgaben zeigen.
  · Der Fundus soll nichts vernichten. Ein Fehler hier fällt erst auf, wenn
    jemand eine alte Fassung sucht, die es dann nicht mehr gibt.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum as C
import fundus as F
import generate_units as GU
import kern_pakete as KP
import testhilfe as T

APP = Path(__file__).resolve().parent.parent / "index.html"

ERGEBNIS = []


def add(name, ok, info=""):
    ERGEBNIS.append({"name": name, "ok": bool(ok), "info": str(info)})


# ============================================================ Lehrplan-Seite

def pruefe_curriculum():
    add("Jede Klasse hat einen Einstieg innerhalb der Stufen",
        all(1 <= v["einstieg"] <= C.MAX_STAGE for v in C.KLASSEN.values()))

    add("Der Einstieg steigt mit der Klasse, ohne je zu fallen",
        all(C.KLASSEN[a]["einstieg"] <= C.KLASSEN[b]["einstieg"]
            for a, b in zip(sorted(C.KLASSEN), sorted(C.KLASSEN)[1:])))

    add("Der Einstieg liegt unter dem, was der Lehrplan der Klasse verlangt",
        # Sonst wäre der Anfang kein Anfang, sondern ein Sprung ins kalte Wasser.
        C.klasse_einstieg(4) < 6 and C.klasse_einstieg(3) < 5,
        f"Klasse 3 -> {C.klasse_einstieg(3)}, Klasse 4 -> {C.klasse_einstieg(4)}")

    add("Der Einstieg einer Klasse liegt in ihrem eigenen Vorratsband",
        all(v["einstieg"] in v["band"] for v in C.KLASSEN.values()))

    add("Jedes Vorratsband bleibt innerhalb der Stufen",
        all(all(1 <= s <= C.MAX_STAGE for s in v["band"]) for v in C.KLASSEN.values()))

    add("Eine Klasse unterhalb des Bereichs wird gekappt, nicht geraten",
        C.klasse_einstieg(1) == C.KLASSEN[min(C.KLASSEN)]["einstieg"]
        and C.klasse_band(0) == C.KLASSEN[min(C.KLASSEN)]["band"])

    add("Eine Klasse oberhalb des Bereichs wird gekappt, nicht geraten",
        C.klasse_einstieg(9) == C.KLASSEN[max(C.KLASSEN)]["einstieg"]
        and C.klasse_band(13) == C.KLASSEN[max(C.KLASSEN)]["band"])


def pruefe_baupläne():
    band = C.klasse_band(4)
    plan = GU.seed_plan(band)
    add("Der Grundstock einer Klasse enthält nur Stufen aus ihrem Band",
        plan and all(stufe in band for _, stufe, _ in plan),
        f"{len(plan)} Pakete, Stufen {sorted({s for _, s, _ in plan})}")

    add("Der Grundstock einer Klasse ist nicht leer",
        len(plan) >= 10, f"{len(plan)} Pakete")

    alle = KP._alle_pakete_plan()
    gefiltert = [e for e in alle if e[1] in band]
    add("Der Kern-Bauplan lässt sich auf ein Klassenband einschränken",
        0 < len(gefiltert) < len(alle), f"{len(gefiltert)} von {len(alle)}")

    # Zwei verschiedene Klassen dürfen nicht denselben Plan ergeben — sonst
    # wäre die ganze Unterscheidung wirkungslos.
    add("Zwei Klassen ergeben verschiedene Grundstöcke",
        GU.seed_plan(C.klasse_band(2)) != GU.seed_plan(C.klasse_band(4)))


# ================================================================== Fundus

def pruefe_fundus():
    tmp = Path(tempfile.mkdtemp(prefix="mathcraft_fundus_test_"))
    alt_f, alt_p, alt_b = F.FUNDUS, F.PAKETE, F.BILDER
    F.FUNDUS, F.PAKETE, F.BILDER = tmp, tmp / "pakete", tmp / "bilder"
    try:
        paket = {"skill": "plus_bis20", "stage": 2, "title": "Erste Fassung",
                 "tasks": [{"type": "rechnen", "q": "3+4", "a": 7}]}

        ab1 = F.lege_paket_ab(paket)
        add("Ein ersetztes Paket landet im Fundus", ab1 is not None and ab1.exists())
        add("Es liegt unter Fertigkeit und Stufe",
            ab1 and ab1.parent.name == "plus_bis20@2", ab1 and ab1.parent.name)
        add("Der abgelegte Inhalt ist der ursprüngliche",
            ab1 and json.loads(ab1.read_text("utf-8")) == paket)

        # Der Kern der Sache: zweimal ablegen darf nichts überschreiben, auch
        # nicht innerhalb derselben Sekunde.
        zweite = dict(paket, title="Zweite Fassung")
        ab2 = F.lege_paket_ab(zweite)
        add("Zweimal ablegen überschreibt die erste Fassung nicht",
            ab1 and ab2 and ab1 != ab2 and ab1.exists() and ab2.exists(),
            f"{ab1 and ab1.name} / {ab2 and ab2.name}")
        add("Beide Fassungen sind unterscheidbar erhalten",
            json.loads(ab1.read_text("utf-8"))["title"] == "Erste Fassung"
            and json.loads(ab2.read_text("utf-8"))["title"] == "Zweite Fassung")

        # Dateien: kopieren, nicht verschieben. Scheitert die Neuerzeugung,
        # muss das Original noch an seinem Platz stehen.
        quelle = tmp / "hero.png"
        quelle.write_bytes(b"\x89PNG-Platzhalter")
        abd = F.lege_datei_ab(quelle, "bilder")
        add("Ein überschriebenes Bild landet im Fundus", abd is not None and abd.exists())
        add("Das Original bleibt liegen — abgelegt wird eine Kopie", quelle.exists())
        add("Die Kopie ist inhaltsgleich", abd and abd.read_bytes() == quelle.read_bytes())
        add("Sie liegt unter dem Namen des Bildes",
            abd and abd.parent.name == "hero", abd and abd.parent.name)

        add("Eine nicht vorhandene Datei abzulegen ist kein Fehler",
            F.lege_datei_ab(tmp / "gibtesnicht.png", "bilder") is None)
        add("Etwas, das kein Paket ist, abzulegen ist kein Fehler",
            F.lege_paket_ab(None) is None and F.lege_paket_ab({"stage": 1}) is None)

        p, b, g = F.bestand()
        add("Der Bestand zählt, was abgelegt wurde", p == 2 and b == 1 and g > 0,
            f"{p} Pakete, {b} Bilder, {g} Bytes")
    finally:
        F.FUNDUS, F.PAKETE, F.BILDER = alt_f, alt_p, alt_b
        shutil.rmtree(tmp, ignore_errors=True)


# ================================================================ Die App

JS = r"""
() => {
  const R = [];
  const add = (name, ok, info) => R.push({name, ok: !!ok, info: info === undefined ? "" : String(info)});

  const frisch = () => { S = freshState(); save(); };

  // ---------------------------------------------------- ohne jede Angabe
  frisch();
  add("Ohne Klassenangabe geht es bei Stufe 1 los",
      baseStage() === 1, baseStage());

  // ---------------------------------------------------------- Boden setzen
  setzeKlasse(4);
  const e4 = KLASSEN.find(x => x.k === 4);
  add("Klasse 4 setzt die Einstiegsstufe aus dem Lehrplan",
      S.profile.einstieg === e4.einstieg && S.profile.klasse === 4,
      S.profile.einstieg + "/" + e4.einstieg);
  add("Der Boden wirkt sofort auf die Grundstufe",
      baseStage() === e4.einstieg, baseStage());
  add("Auch jede Welt startet mindestens auf dem Boden",
      AREAS.every(a => areaStage(a.id) >= e4.einstieg),
      AREAS.map(a => areaStage(a.id)).join(","));

  // ------------------------------------------- ein Boden, keine Decke
  // Zwei fehlerfrei gelöste Pakete einer Stufe über dem Einstieg müssen
  // weiterhin aufsteigen lassen. Ginge das verloren, säße ein schnelles
  // Kind auf seiner Einstiegsstufe fest.
  const hoch = Object.values(UNITS).filter(u => u.stage === MAX_STAGE_ROH - 1).slice(0, 2);
  if(hoch.length === 2){
    hoch.forEach(u => { S.units[u.id] = {stars: 3, plays: 1, sofort: 1, rev: u.rev}; });
    save();
    add("Über dem Boden zählt weiterhin nur, was das Kind zeigt",
        baseStage() === MAX_STAGE_ROH, baseStage() + " statt " + MAX_STAGE_ROH);
  } else {
    add("Über dem Boden zählt weiterhin nur, was das Kind zeigt", false,
        "keine zwei Pakete auf Stufe " + (MAX_STAGE_ROH - 1) + " im Vorrat");
  }

  // ------------------------------------------------ zurückstellen
  frisch();
  setzeKlasse(4);
  S.units["__probe__"] = {stars: 2, plays: 3, sofort: 1};
  const vorher = JSON.stringify(S.units);
  setzeKlasse(0);
  add("Zurück auf „keine Angabe“ senkt den Boden wieder",
      S.profile.klasse === 0 && S.profile.einstieg === 0 && baseStage() === 1,
      baseStage());
  add("Das Umstellen lässt den Lernstand unangetastet",
      JSON.stringify(S.units) === vorher);

  // ------------------------------------------------ unbekannte Klasse
  frisch();
  setzeKlasse(99);
  add("Eine Klasse, die es nicht gibt, setzt keinen Boden",
      S.profile.klasse === 0 && S.profile.einstieg === 0 && baseStage() === 1);

  // ------------------------------------------------ alter Lernstand
  // Ein Stand von vor dieser Einstellung darf sich nicht anders verhalten
  // als bisher — sonst springt ein Kind nach einem Update plötzlich woanders hin.
  const alt = {v: 1, server: "", profile: {name: "Alex", xp: 120, goal: 15,
              badges: [], lastUnitId: ""}, skills: {}, units: {}};
  localStorage.setItem("mathcraft_v1", JSON.stringify(alt));
  S = load();
  add("Ein Lernstand ohne die Einstellung verhält sich wie bisher",
      S.profile.einstieg === 0 && S.profile.klasse === 0 && baseStage() === 1,
      S.profile.einstieg + "/" + baseStage());
  add("Dabei bleibt alles Übrige des alten Standes erhalten",
      S.profile.name === "Alex" && S.profile.xp === 120);

  // ------------------------------------------------ Unsinn im Speicher
  const wild = {v: 1, server: "", profile: {einstieg: 999, klasse: -5, badges: []},
                skills: {}, units: {}};
  localStorage.setItem("mathcraft_v1", JSON.stringify(wild));
  S = load();
  add("Ein zu hoher gespeicherter Einstieg wird auf die höchste Stufe gekappt",
      S.profile.einstieg === MAX_STAGE_ROH, S.profile.einstieg);
  add("Eine negative gespeicherte Klasse wird auf 0 gekappt",
      S.profile.klasse === 0, S.profile.klasse);

  // ------------------------------------------------ Liste und Lehrplan
  add("Die Klassenliste kommt aus dem Lehrplan und ist nicht leer",
      KLASSEN.length > 0, KLASSEN.length);
  add("Jeder Eintrag nennt eine Stufe, die es gibt",
      KLASSEN.every(e => STAGES[e.einstieg]));
  add("Jeder Eintrag trägt den Namen genau dieser Stufe",
      KLASSEN.every(e => e.name === STAGES[e.einstieg]));

  frisch();
  return R;
}
"""


def pruefe_app():
    from playwright.sync_api import sync_playwright
    if not APP.exists():
        add("index.html vorhanden", False, "zuerst build/build.py laufen lassen")
        return
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        T.ohne_dienst(page)
        page.goto(APP.as_uri())
        page.wait_for_timeout(400)
        ERGEBNIS.extend(page.evaluate(JS))
        b.close()
    for e in errs:
        add("Kein JS-Fehler beim Prüfen", False, e)


def main():
    pruefe_curriculum()
    pruefe_baupläne()
    pruefe_fundus()
    pruefe_app()

    fails = [r for r in ERGEBNIS if not r["ok"]]
    for r in ERGEBNIS:
        info = f"   ({r['info']})" if r["info"] else ""
        print(f"{'✅' if r['ok'] else '❌'} {r['name']}{info}")
    print(f"\n{len(ERGEBNIS)-len(fails)}/{len(ERGEBNIS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
