# -*- coding: utf-8 -*-
"""Prüft Z5 und Z3 aus ZIELE.md: weicht der Tutor richtig ab — und sagt er es?

Zwei Dinge werden hier zusammen geprüft, weil sie zusammengehören: Die App darf
von der schlichten Reihenfolge abweichen, aber jede Abweichung muss einen
Eintrag im Protokoll erzeugen. Eine Anpassung ohne Eintrag wäre kein Merkmal,
sondern ein Fehler — die Elternseite behauptete dann Vollständigkeit, die sie
nicht hat.

  .venv/bin/python build/adaptiv_test.py
"""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "index.html"

RESULTS = []


def add(name, ok, info=""):
    RESULTS.append((name, bool(ok), info))


# Ein Zustand, in dem eine Fertigkeit sicher sitzt bzw. sicher hakt. Die Zahlen
# sind mit Absicht knapp an den Schwellen aus ZIELE.md gewählt.
JS_HELFER = r"""
() => {
  window.setzeVerlauf = (id, muster, level) => {
    const x = st(id);
    x.h = muster.slice();
    x.l = level === undefined ? 5 : level;
    x.c = muster.filter(v => v).length; x.w = muster.length - x.c;
    save();
  };
  window.frisch = () => { S = freshState(); S.server = ''; save(); };
  window.entscheidungen = () => S.log.ev.filter(e => e.e === 'd');
  return true;
}
"""


def main():
    from playwright.sync_api import sync_playwright

    if not APP.exists():
        sys.exit("index.html fehlt — zuerst build/build.py laufen lassen.")

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 393, "height": 873}).new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        T.ohne_dienst(page)
        page.goto(APP.as_uri())
        page.wait_for_timeout(400)
        page.evaluate(JS_HELFER)

        # ------------------------------------------------------- Schwellen
        page.evaluate("() => frisch()")
        probe = page.evaluate("""() => {
          const id = DATA.units[0].skill;
          const raus = {};
          setzeVerlauf(id, [1,1,1,1,1,1,1,1,1,0], 4);   raus.genau  = istLangweilig(id);
          setzeVerlauf(id, [1,1,1,1,1,1,1,1,0,0], 4);   raus.knapp  = istLangweilig(id);
          setzeVerlauf(id, [1,1,1,1,1,1,1,1,1,1], 3);   raus.tief   = istLangweilig(id);
          setzeVerlauf(id, [1,1,1,1,1,1,1,1,1], 5);     raus.kurz   = istLangweilig(id);
          setzeVerlauf(id, [0,0,0,0,1,1], 2);           raus.schwer = istZuSchwer(id);
          setzeVerlauf(id, [0,0,1,1,1,1], 2);           raus.gerade = istZuSchwer(id);
          setzeVerlauf(id, [0,0,0,0,0], 2);             raus.zuwenig= istZuSchwer(id);
          return raus;
        }""")
        add("9 von 10 richtig bei Leitner-Stufe 4 gilt als zu leicht — genau 90 %",
            probe["genau"])
        add("8 von 10 reicht dafür nicht", not probe["knapp"])
        add("Leitner-Stufe 3 reicht dafür nicht", not probe["tief"])
        add("Neun Antworten reichen dafür nicht", not probe["kurz"])
        add("2 von 6 richtig gilt als zu schwer", probe["schwer"])
        add("4 von 6 richtig gilt nicht als zu schwer", not probe["gerade"])
        add("Fünf Antworten reichen für „zu schwer“ nicht", not probe["zuwenig"])

        # ------------------------------------------- Vorbedingung und Rückkehr
        vb = page.evaluate("""() => {
          frisch();
          // eine Fertigkeit mit etwas darunter in derselben Welt suchen
          const kand = DATA.units.map(u => u.skill)
            .filter((v,i,a) => a.indexOf(v) === i)
            .map(id => ({id, v: vorbedingung(id)}))
            .filter(x => x.v && DATA.units.some(u => u.skill === x.v.id));
          if(!kand.length) return {ohne: true};
          const {id, v} = kand[0];
          setzeVerlauf(id, [0,0,0,0,0,1], 1);
          const gesperrt = darfZurueck(id);
          setzeVerlauf(v.id, [1,1,1,1,1,0], 4);        // 5 von 6 = 83 %
          const offen = darfZurueck(id);
          setzeVerlauf(v.id, [1,0,1,0,1,0], 2);        // 3 von 6 = 50 %
          const wieder_zu = darfZurueck(id);
          return {ohne:false, id, vor:v.id, gesperrt, offen, wieder_zu};
        }""")
        if vb.get("ohne"):
            add("Es gibt Fertigkeiten mit einer Vorbedingung", False, "keine gefunden")
        else:
            add("Zu Schwieriges bleibt gesperrt, solange die Vorbedingung wackelt",
                not vb["gesperrt"], f'{vb["id"]} <- {vb["vor"]}')
            add("Sitzt die Vorbedingung zu 83 %, ist der Weg frei", vb["offen"])
            add("Fällt sie auf 50 %, schließt er sich wieder", not vb["wieder_zu"])

        # --------------------------- Der Plan des Tutors in seiner Reihenfolge
        # Der Tutor ordnet seinen Plan nach Wichtigkeit. Wird diese Reihenfolge
        # auf dem Gerät nach dem Abstand zum Niveau umsortiert, kommt jeder
        # Einstieg auf niedriger Stufe nie an die Reihe — genau das ist im
        # Betrieb passiert: „Die Uhr“ stand dreimal im Plan und wurde dreimal
        # von einem Stufe-4-Paket verdrängt.
        NIEDRIG, HOCH = "gr_uhr", "plus_uebergang"
        plan = page.evaluate("""([niedrig, hoch]) => {
          const stufeVon = id => (DATA.units.find(u => u.skill === id) || {}).stage;
          const aufbau = () => {
            frisch();
            // Basisniveau auf Stufe 4 heben: je zwei makellose Pakete auf 1, 2, 3
            [1,2,3].forEach(s => DATA.units
              .filter(u => u.stage === s && ![niedrig, hoch].includes(u.skill))
              .slice(0, 2).forEach(u => { S.units[u.id] = {stars:3, plays:1}; }));
            save();
          };
          const mitPlan = reihenfolge => {
            aufbau();
            S.plan = reihenfolge.map(id => ({skill:id, art:'vor', grund:'Test'}));
            save();
            return waehleUnit().unit.skill;
          };
          aufbau();
          return {basis: baseStage(),
                  stufeNiedrig: stufeVon(niedrig), stufeHoch: stufeVon(hoch),
                  ohnePlan: waehleUnit().unit.skill,
                  niedrigVorn: mitPlan([niedrig, hoch]),
                  hochVorn: mitPlan([hoch, niedrig])};
        }""", [NIEDRIG, HOCH])
        add("Der Prüfstand steht auf Stufe 4", plan["basis"] == 4,
            f'Basis {plan["basis"]}, {NIEDRIG} St{plan["stufeNiedrig"]}, '
            f'{HOCH} St{plan["stufeHoch"]}')
        add("Ohne Plan greift die Auswahl von sich aus nicht zur niedrigen Stufe",
            plan["ohnePlan"] != NIEDRIG, plan["ohnePlan"])
        add("Steht die niedrige Stufe im Plan vorn, wird sie auch gestellt",
            plan["niedrigVorn"] == NIEDRIG, f'gewählt: {plan["niedrigVorn"]}')
        add("Steht die höhere vorn, gewinnt sie",
            plan["hochVorn"] == HOCH, f'gewählt: {plan["hochVorn"]}')

        # --------------------------------- B/C: Verweigerung und Vorrangpool
        # Reproduziert die reale Lage vom 26.08.: „jetzt: komb_reihen“ wurde
        # zwölfmal vorgelegt, achtmal sofort weggetippt (n=0) — und verdeckte
        # dabei jeden anderen Planposten, weil ein Wunsch früher entweder-oder
        # den kompletten Plan ausblendete (ZIELE-V2.md, V0).
        verweigert = page.evaluate("""() => {
          frisch();
          S.plan = [{skill:'gr_uhr', art:'vor', grund:'Test'}];
          save();
          // Ein offener Kandidat, der nicht der Planposten selbst ist.
          const kandidat = DATA.units.find(u => u.skill !== 'gr_uhr' &&
            ((S.units[u.id]||{}).stars||0) < 2);
          S.wishes = [{ziel:'skill', id: kandidat.skill, art:'jetzt', t: Date.now() - 60000}];
          save();

          const w1 = waehleUnit();
          const vorAbbruch = {skill: w1.unit.skill, pausiert: istPausiert(w1.unit)};

          // Drei Sofort-Abbrüche in Folge: 0 Antworten je Paketlauf.
          for(let i = 0; i < 3; i++) vermerkeAbbruch(w1.unit.id, 0);

          const w2 = waehleUnit();
          return {gewuenscht: kandidat.skill, geplant: 'gr_uhr',
                  vorher: vorAbbruch.skill, vorherPausiert: vorAbbruch.pausiert,
                  nachherPausiert: istPausiert(w1.unit), nachher: w2.unit.skill};
        }""")
        add("Vor der Verweigerung steht der Elternwunsch vorn",
            verweigert["vorher"] == verweigert["gewuenscht"]
            and not verweigert["vorherPausiert"], verweigert["vorher"])
        add("(B) Nach drei Sofort-Abbrüchen in Folge ist das Paket pausiert",
            verweigert["nachherPausiert"])
        add("(B/C) Ein verweigerter Wunsch verdeckt den Tutorplan nicht mehr — "
            "der nächste Planposten kommt dran",
            verweigert["nachher"] == verweigert["geplant"], verweigert["nachher"])

        # ---------------------------------------- Abweichung und Protokoll
        lueckenlos = page.evaluate("""() => {
          frisch();
          const faelle = [];
          for(let runde = 0; runde < 14; runde++){
            // jede Runde eine andere Lage herstellen
            const u = nextUnit();
            if(runde % 2 === 0) setzeVerlauf(u.skill, [1,1,1,1,1,1,1,1,1,1], 5);
            else                setzeVerlauf(u.skill, [0,0,0,0,0,0], 1);
            const w = waehleUnit();
            const vorher = entscheidungen().length;
            startNext();
            SESS = null; view = {name:'home', opts:{}};
            const neu = entscheidungen().length - vorher;
            faelle.push({abgewichen: w.unit.id !== w.schlicht.id, eintraege: neu});
          }
          return faelle;
        }""")
        ohne_eintrag = [f for f in lueckenlos if f["abgewichen"] and f["eintraege"] == 0]
        eintrag_ohne = [f for f in lueckenlos if not f["abgewichen"] and f["eintraege"] > 0]
        abweichungen = sum(1 for f in lueckenlos if f["abgewichen"])
        add("Jede Abweichung erzeugt mindestens einen Eintrag",
            not ohne_eintrag, f"{len(ohne_eintrag)} ohne Eintrag von {abweichungen}")
        add("Ohne Abweichung entsteht kein Eintrag",
            not eintrag_ohne, f"{len(eintrag_ohne)} überzählige")
        add("Der Testlauf hat überhaupt Abweichungen erzeugt", abweichungen > 0,
            f"{abweichungen} von {len(lueckenlos)} Runden")

        # ------------------------------------- Begründungen tragen ihre Zahlen
        form = page.evaluate("""() => {
          const e = entscheidungen();
          return {
            n: e.length,
            arten: [...new Set(e.map(x => x.d))],
            gruende: [...new Set(e.map(x => x.w))],
            vollstaendig: e.every(x => x.d && x.w && x.k && typeof x.g === 'number'
                                    && x.b && typeof x.b === 'object'),
            mit_zahlen: e.filter(x => ['langweilig','zu_schwer'].includes(x.w))
                         .every(x => typeof x.b.n === 'number' && typeof x.b.c === 'number')
          };
        }""")
        add("Jeder Eintrag nennt Art, Grund, Fertigkeit und Stufe", form["vollstaendig"])
        add("Begründungen aus Leistungsdaten führen ihre Zahlen mit",
            form["mit_zahlen"], f'{form["n"]} Einträge')
        add("Es kommen echte Gründe vor, nicht nur „reihenfolge“",
            any(g in form["gruende"] for g in ("langweilig", "zu_schwer", "vorbedingung")),
            ", ".join(form["gruende"]))

        # ----------------------------------------------- Typenmischung wirkt
        typ = page.evaluate("""() => {
          frisch();
          for(let i = 0; i < 60; i++) S.typLog.push('zahl');
          for(let i = 0; i < 10; i++) S.typLog.push('wahl');
          save();
          const zuviel = ueberzogenerTyp();
          const gewaehlt = nextUnit();
          // Vergleich: das Paket mit dem höchsten zahl-Anteil auf gleicher Stufe
          const gleich = DATA.units.filter(u => u.stage === gewaehlt.stage);
          const schlimmster = Math.max(...gleich.map(u => typAnteilIn(u, 'zahl')));
          return {zuviel, anteil: typAnteilIn(gewaehlt, 'zahl'), schlimmster,
                  anteile: typAnteile()};
        }""")
        add("Ein überzogener Aufgabentyp wird erkannt", typ["zuviel"] == "zahl",
            f'{typ["anteile"].get("zahl", 0):.0%} zahl')
        add("Die Auswahl greift dann nicht zum schlimmsten Paket",
            typ["anteil"] <= typ["schlimmster"],
            f'gewählt {typ["anteil"]:.0%}, schlimmstes {typ["schlimmster"]:.0%}')

        # ------------------------------------------- Nichts bleibt hängen
        leer = page.evaluate("""() => {
          frisch();
          // alles als gekonnt markieren: die App muss trotzdem etwas anbieten
          DATA.units.forEach(u => setzeVerlauf(u.skill, [1,1,1,1,1,1,1,1,1,1], 5));
          const u = nextUnit();
          return !!(u && u.id);
        }""")
        add("Auch wenn alles sitzt, kommt ein Vorschlag", leer)

        add("keine JS-Fehler", not errs, errs[0][:70] if errs else "")
        b.close()

    # ------------------------------------------ Die Sätze auf der Elternseite
    tele = Path(tempfile.mkdtemp(prefix="mathcraft_adapt_"))
    os.environ["MC_TELE"] = str(tele)
    sys.path.insert(0, str(ROOT / "tutor"))
    sys.path.insert(0, str(ROOT / "build"))
    import protokoll as P

    jetzt = int(time.time() * 1000)
    beispiele = [
        {"t": jetzt, "art": "ueber", "grund": "langweilig", "skill": "zahl_bis20",
         "stufe": 2, "belege": {"n": 10, "c": 10, "l": 5}},
        {"t": jetzt, "art": "zurueck", "grund": "zu_schwer", "skill": "geo_netz",
         "stufe": 6, "belege": {"n": 6, "c": 2, "vorher": "geo_koerper"}},
        {"t": jetzt, "art": "vor", "grund": "vorbedingung", "skill": "geo_koerper",
         "stufe": 5, "belege": {"wegen": "geo_netz", "n": 6, "c": 2}},
        {"t": jetzt, "art": "neu", "grund": "vorratsluecke", "skill": "geheim_prim",
         "stufe": 7, "belege": {"n": 1}},
    ]
    for e in beispiele:
        s = P.satz(e)
        add(f'Satz für „{P.ARTEN[e["art"]]}“ nennt die Zahlen',
            all(str(v) in s for v in e["belege"].values()
                if isinstance(v, int)) and len(s) > 30, s[:78])
    add("Ein unbekannter Grund wird trotzdem gezeigt, nicht verschluckt",
        "erfunden" in P.satz({"t": jetzt, "art": "ueber", "grund": "erfunden",
                              "skill": "zahl_bis20", "stufe": 1, "belege": {}}))
    shutil.rmtree(tele, ignore_errors=True)

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, info in RESULTS:
        print(f'{"✅" if ok else "❌"} {name}' + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS)-len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
