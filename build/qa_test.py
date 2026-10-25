# -*- coding: utf-8 -*-
"""Prüft die gebaute App auf Herz und Nieren: Passform, Fairness, Rechenrichtigkeit.

Anders als der Durchklick-Test prüft dieser hier jeden Aufgabentyp einzeln und
auf jedem Bildschirmformat — auch die, die im aktuellen Grundstock zufällig
nicht vorkommen. Dafür werden Beispielaufgaben eingespeist.

  .venv/bin/python build/qa_test.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T
import validate as V

APP = Path(__file__).resolve().parent.parent / "index.html"

RESULTS = []


def add(group, name, ok, info=""):
    RESULTS.append((group, name, bool(ok), info))


# Ein Beispiel je Aufgabentyp — bewusst mit langen Texten und vielen Optionen,
# damit die Passform im ungünstigsten Fall geprüft wird.
BEISPIELE = {
 "entdecken": {"type":"entdecken", "skill":"mal_einstieg",
   "q":"Malnehmen ist Zusammenzählen in Reihen, nur schneller aufgeschrieben.",
   "info":"Drei Reihen mit je vier Blöcken sind zwölf Blöcke. Man schreibt das als 3 mal 4."},
 "zahl": {"type":"zahl", "skill":"plus_bis20",
   "q":"In deiner Truhe liegen 18 Blöcke und du legst noch einmal 15 Blöcke dazu.",
   "a":33, "check":{"expr":"18+15"}, "hint":"Fülle erst bis zum nächsten Zehner auf."},
 "wahl": {"type":"wahl", "skill":"plus_bis20",
   "q":"Du baust eine lange Mauer aus 48 Blöcken und setzt 27 weitere obendrauf.",
   "opts":["65 Blöcke","75 Blöcke","85 Blöcke","55 Blöcke"], "correct":1,
   "hint":"Rechne erst die Zehner, dann die Einer."},
 "wahrfalsch": {"type":"wahrfalsch", "skill":"geh_gerade",
   "q":"Ein Mitspieler behauptet: Wenn man zwei ungerade Zahlen zusammenzählt, ist das Ergebnis immer gerade.",
   "a":True, "hint":"Probiere es mit 3 und 5."},
 "ordnen": {"type":"ordnen", "skill":"zahl_bis100",
   "q":"Ordne die gefundenen Erzmengen von der kleinsten bis zur größten Zahl.",
   "items":[47,12,93,68,25,81], "order":[1,4,0,3,5,2]},
 "zuordnen": {"type":"zuordnen", "skill":"log_paare",
   "q":"Welche Rechnung gehört zu welchem Ergebnis?",
   "pairs":[["12 plus 9","21"],["30 minus 8","22"],["5 mal 5","25"],["36 geteilt durch 3","12"]]},
 "mehrschritt": {"type":"mehrschritt", "skill":"sach_zwei",
   "q":"Du kaufst drei Trikots für je 14 Euro und bezahlst mit einem Fünfzigeuroschein.",
   "steps":[{"q":"Was kosten die drei Trikots zusammen?","a":42,"check":{"expr":"3*14"}},
            {"q":"Wie viel Rückgeld bekommst du?","a":8,"check":{"expr":"50-42"}}]},
 "gitter_feld": {"type":"gitter", "skill":"geo_symm",
   "q":"Welches Feld musst du färben, damit das Muster spiegelsymmetrisch wird?",
   "grid":[["🟦","🟦","⬜","🟦"],["🟦","⬜","⬜","🟦"],["⬜","🟦","🟦","⬜"],["🟦","🟦","🟦","🟦"]],
   "cell":[1,2]},
 "gitter_wahl": {"type":"gitter", "skill":"must_form",
   "q":"Wie geht das Muster in der letzten Zeile weiter?",
   "grid":[["🔺","🟦","🔺","🟦"],["🟦","🔺","🟦","🔺"],["🔺","🟦","🔺","🟦"]],
   "opts":["🟦 dann 🔺","🔺 dann 🟦","🟦 dann 🟦","🔺 dann 🔺"], "correct":1},

 # ---- Roboter (D2 algo): alle drei Modi. roboter_ziel hat bewusst n=6 und
 # eine Schleife (SPEC §9-Auflage) — von Hand nachgerechnet:
 # Start (5,0) Blick N, flach V,R,V,R,V,R (dreimal "vor, rechts drehen"):
 # V->(4,0) N; R->Blick O; V->(4,1) O; R->Blick S; V->(5,1) S; R->Blick W.
 # Ende (5,1), Blick W, keine Wand auf dem Weg berührt.
 "roboter_ziel": {"type":"roboter", "modus":"ziel", "skill":"algo_schleife",
   "q":"Der Rover befolgt sein Programm. Auf welchem Feld hält er am Ende?",
   "n":6, "start":[5,0], "richtung":"N", "waende":[[0,5],[3,3]],
   "befehlssatz":"relativ", "programm":[{"x":3,"b":["V","R"]}],
   "loesung":{"ende":[5,1],"richtung":"W"},
   "hint":"Merk dir nach jedem Drehbefehl, wohin der Rover schaut."},
 # roboter_programm: absolute Befehle, Handrechnung N,N,N,O,O von (4,0) nach
 # (1,2) meidet die Wand bei (2,2) und ist mit 5 Befehlen die kürzeste Lösung
 # (Manhattan-Abstand |4-1|+|0-2|=5, ein direkter Weg existiert also).
 "roboter_programm": {"type":"roboter", "modus":"programm", "skill":"algo_finden",
   "q":"Bring den Rover mit höchstens fünf Befehlen zur Rakete, ohne gegen die Wand zu fahren.",
   "n":5, "start":[4,0], "richtung":"N", "waende":[[2,2]], "ziel":[1,2],
   "befehlssatz":"absolut", "max_laenge":5,
   "loesung":{"beispiel":["N","N","N","O","O"]},
   "hint":"Zähl zuerst, wie oft du nach oben musst, dann wie oft nach rechts."},
 # roboter_reparieren: gegeben ["R","V","V"] ab (2,2) Blick O landet über
 # R(Blick S),V(3,2),V(4,2) bei (4,2) statt beim Ziel (0,2) — falsches Ende,
 # kein Crash. Ersetzt man Platz 0 durch "L" (Blick N), führt L,V,V über
 # (1,2),(0,2) genau zum Ziel.
 "roboter_reparieren": {"type":"roboter", "modus":"reparieren", "skill":"algo_reparieren",
   "q":"Der Rover soll zur Rakete, bleibt aber falsch stehen. Genau ein Befehl ist falsch — tippe ihn an.",
   "n":5, "start":[2,2], "richtung":"O", "waende":[[4,0]], "ziel":[0,2],
   "befehlssatz":"relativ", "programm":["R","V","V"],
   "loesung":{"index":0,"ersatz":"L"},
   "hint":"Merk dir bei jedem Drehbefehl, wohin der Rover danach schaut."},

 # ---- Bildwahl (Raum & Form): vier echte, kleine SVG-Rechtecke statt Emoji —
 # damit die Passform mit echten Bildern statt Platzhaltertext geprüft wird.
 "bildwahl": {"type":"bildwahl", "skill":"geo_spiegel",
   "q":"Spiegle die Figur an der gestrichelten Linie. Welches Bild ist richtig?",
   "svg":('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
          '<rect x="8" y="8" width="34" height="34" fill="#3ad0ff"/>'
          '<rect x="58" y="58" width="34" height="34" fill="#ffb238"/></svg>'),
   "optionen_svg":[
     ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
      '<rect x="8" y="8" width="34" height="34" fill="#ffb238"/>'
      '<rect x="58" y="58" width="34" height="34" fill="#3ad0ff"/></svg>'),
     ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
      '<rect x="8" y="58" width="34" height="34" fill="#3ad0ff"/>'
      '<rect x="58" y="8" width="34" height="34" fill="#3ad0ff"/></svg>'),
     ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
      '<rect x="58" y="8" width="34" height="34" fill="#ffb238"/>'
      '<rect x="8" y="58" width="34" height="34" fill="#3ad0ff"/></svg>'),
     ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
      '<rect x="30" y="30" width="34" height="34" fill="#ff5a68"/></svg>'),
   ], "richtig":2,
   "hint":"Was oben links steht, landet nach dem Spiegeln unten rechts."},

 # ---- Bildzahl (Würfelgebäude): svg + a, kein Rechenterm.
 "bildzahl": {"type":"bildzahl", "skill":"geo_wuerfel",
   "q":"Wie viele Würfel stecken im Gebäude? Denk an die versteckten.",
   "svg":('<svg viewBox="0 0 120 100" xmlns="http://www.w3.org/2000/svg">'
          '<rect x="5" y="60" width="30" height="30" fill="#8b5cf6"/>'
          '<rect x="40" y="60" width="30" height="30" fill="#8b5cf6"/>'
          '<rect x="75" y="60" width="30" height="30" fill="#8b5cf6"/>'
          '<rect x="5" y="25" width="30" height="30" fill="#8b5cf6"/>'
          '<rect x="40" y="25" width="30" height="30" fill="#8b5cf6"/>'
          '<rect x="75" y="25" width="30" height="30" fill="#8b5cf6"/>'
          '<rect x="40" y="-10" width="30" height="30" fill="#8b5cf6"/></svg>'),
   "a":7, "hint":"Zähl auch die Würfel mit, die von anderen verdeckt werden."},

 # ---- Positionen (Logik ohne Zahlen): 5 Namen, 5 Hinweise, bewusst lange
 # Texte für die Passform. Lösung von Hand geprüft:
 # loesung[p] = Person an Position p (0 = ganz links):
 # 0 Ingenieurin, 1 Funkerin, 2 Astronautin, 3 Kapitän, 4 Pilot.
 # (1) Ingenieurin ganz links -> pos 0 ✓  (2) Astronautin Mitte -> pos 2 ✓
 # (3) Funkerin direkt links neben Astronautin -> pos1 = pos2-1 ✓
 # (4) Kapitän direkt neben Astronautin -> |pos3-pos2|=1 ✓
 # (5) Astronautin zwischen Funkerin und Kapitän -> pos2 liegt zwischen 1 und 3 ✓
 # Übrig bleibt Pilot auf dem letzten freien Platz, ganz rechts (Position 4).
 "positionen": {"type":"positionen", "skill":"log_position",
   "rahmen":"Auf der Forschungsstation warten fünf Mitglieder der Mannschaft "
     "nebeneinander auf das Startsignal, aber du weißt noch nicht, in welcher "
     "Reihenfolge sie wirklich stehen.",
   "namen":["die Astronautin","der Pilot","die Ingenieurin","der Kapitän","die Funkerin"],
   "hinweise":[
     {"typ":"ganz_links","a":2,
      "text":"Die Ingenieurin steht ganz links in der Reihe, direkt neben dem Eingang zur Schleuse."},
     {"typ":"mitte","a":0,
      "text":"Die Astronautin steht genau in der Mitte der ganzen Reihe."},
     {"typ":"direkt_links","a":4,"b":0,
      "text":"Die Funkerin steht direkt links neben der Astronautin."},
     {"typ":"neben","a":3,"b":0,
      "text":"Der Kapitän steht direkt neben der Astronautin."},
     {"typ":"zwischen","a":0,"b":4,"c":3,
      "text":"Die Astronautin steht zwischen der Funkerin und dem Kapitän."},
   ],
   "loesung":[2,4,0,3,1],
   "frage":{"art":"position","p":4},
   "frage_text":"Wer steht ganz rechts in der Reihe, wenn du von links nach rechts zählst?",
   "optionen":["die Ingenieurin","der Kapitän","der Pilot","die Funkerin","die Astronautin"],
   "richtig":2,
   "hint":"Trag die festen Hinweise zuerst in die Denkhilfe-Tabelle ein."},

 # ---- Legen (V3/G1). legen_alle: 4 Figuren, geordnet, zwei Regeln — von Hand:
 # Drache ganz hinten (auf_platz 3), Biene nie auf Platz 2 (nicht_platz 2):
 # Die drei anderen verteilen sich auf Platz 0..2 (6 Wege), die Biene darf nicht
 # auf Platz 2 -> 4 Anordnungen. legen_zaehlen: 4 Figuren auf 3 Plätzen ohne
 # Regel = 4*3*2 = 24 Anordnungen, genau die Grenze, bis zu der die App bei einer
 # falschen Zahl alle als Mini-Reihen zeigt (längste Rückmeldung).
 # legen_sechs: sechs Figuren, sechs Plätze — das breiteste Brett, 720 Wege.
 "legen_alle": {"type":"legen", "skill":"komb_reihen", "modus":"alle", "geordnet":True,
   "q":"Lege alle Reihenfolgen mit 4 Figuren. Der Drache steht ganz hinten. Die Biene steht nie auf Platz 2.",
   "figuren":[{"name":"Fuchs","bild":"🦊"},{"name":"Eule","bild":"🦉"},{"name":"Biene","bild":"🐝"},{"name":"Drache","bild":"🐲"}],
   "plaetze":4, "regeln":[{"art":"auf_platz","a":3,"platz":3},{"art":"nicht_platz","a":2,"platz":2}], "a":4,
   "hint":"Fang mit dem Fuchs vorne an und probier alles dahinter."},
 "legen_zaehlen": {"type":"legen", "skill":"komb_reihen", "modus":"zaehlen", "geordnet":True,
   "q":"Wie viele Reihenfolgen gibt es, wenn drei von vier Figuren auf drei Plätze kommen?",
   "figuren":[{"name":"Fuchs","bild":"🦊"},{"name":"Eule","bild":"🦉"},{"name":"Katze","bild":"🐱"},{"name":"Drache","bild":"🐲"}],
   "plaetze":3, "regeln":[], "a":24,
   "hint":"Vier Möglichkeiten für vorne, dann drei, dann zwei."},
 "legen_sechs": {"type":"legen", "skill":"komb_reihen", "modus":"zaehlen", "geordnet":True,
   "q":"Wie viele Reihenfolgen gibt es für alle sechs Figuren?",
   "figuren":[{"name":"Fuchs","bild":"🦊"},{"name":"Eule","bild":"🦉"},{"name":"Golem","bild":"🗿"},
              {"name":"Katze","bild":"🐱"},{"name":"Drache","bild":"🐲"},{"name":"Biene","bild":"🐝"}],
   "plaetze":6, "regeln":[], "a":720, "hint":"Sechs mal fünf mal vier mal drei mal zwei mal eins."},

 # ---- Papier-Streifen über der Frage (V3/G3)
 "papier": {"type":"bildzahl", "skill":"geo_quader", "papier":True,
   "q":"Wie viele Würfel fehlen noch bis zum vollen Quader? Skizziere die Schichten auf Papier.",
   "svg":('<svg viewBox="0 0 120 100" xmlns="http://www.w3.org/2000/svg">'
          '<rect x="5" y="60" width="30" height="30" fill="#8b5cf6"/>'
          '<rect x="40" y="60" width="30" height="30" fill="#8b5cf6"/>'
          '<rect x="5" y="25" width="30" height="30" fill="#8b5cf6"/></svg>'),
   "a":9, "hint":"Zähl Schicht für Schicht."},

 # ---- Merkbild (V3/G4): Fragebild zeigen, dann ausblenden, erst dann die Optionen
 "merkbild": {"type":"bildwahl", "skill":"geo_spiegel", "merken_ms":600,
   "q":"Merk dir das Bild. Welches Bild war das?",
   "svg":('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
          '<circle cx="30" cy="30" r="14" fill="#ffb238"/><circle cx="70" cy="70" r="14" fill="#3ad0ff"/></svg>'),
   "optionen_svg":[
     ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
      '<circle cx="30" cy="30" r="14" fill="#ffb238"/><circle cx="70" cy="70" r="14" fill="#3ad0ff"/></svg>'),
     ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
      '<circle cx="70" cy="30" r="14" fill="#ffb238"/><circle cx="30" cy="70" r="14" fill="#3ad0ff"/></svg>'),
     ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
      '<circle cx="30" cy="30" r="14" fill="#3ad0ff"/><circle cx="70" cy="70" r="14" fill="#ffb238"/></svg>'),
     ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
      '<circle cx="50" cy="50" r="14" fill="#ff5a68"/></svg>')],
   "richtig":0, "hint":"Achte auf Farben und Plätze."},
}

SIZES = [("320x568", 320, 568), ("360x640", 360, 640), ("393x873 Redmi", 393, 873),
         ("412x915", 412, 915), ("800x1280 Tablet", 800, 1280), ("915x412 quer", 915, 412)]


def zeige(page, task):
    """Speist eine Beispielaufgabe ein und zeigt sie an."""
    page.evaluate("""t => {
      beginSession({kind:'unit', unitId:null, title:'Test', intro:'', tasks:[t]});
    }""", task)
    page.wait_for_timeout(150)


def beantworte(page, key):
    """Beantwortet die eingespeiste Aufgabe richtig, damit die Rückmeldung erscheint."""
    t = BEISPIELE[key]
    typ = t["type"]
    if typ == "entdecken":
        page.evaluate("() => grade(true)")
    elif typ == "zahl":
        page.evaluate("() => { SESS.typed = String(SESS.tasks[0].a); checkZahl(); }")
    elif typ == "wahl":
        page.evaluate("() => chooseMc(SESS.tasks[0].correct)")
    elif typ == "wahrfalsch":
        page.evaluate("() => grade(true)")
    elif typ == "ordnen":
        page.evaluate("() => SESS.tasks[0].order.forEach(i => pickChip(i))")
    elif typ == "zuordnen":
        page.evaluate("() => SESS.rightOrder.forEach((src,j) => { pickLeft(src); pickRight(j); })")
    elif typ == "mehrschritt":
        page.evaluate("""() => {
          const st = SESS.tasks[0].steps;
          for(let k = 0; k < st.length && SESS && !SESS.answered; k++){
            SESS.typed = String(st[SESS.step].a); checkStep();
          }}""")
    elif typ == "gitter":
        if "cell" in t:
            page.evaluate("() => { const c = SESS.tasks[0].cell; pickCell(c[0], c[1]); }")
        else:
            page.evaluate("() => chooseMc(SESS.tasks[0].correct)")
    elif typ == "roboter":
        # Alle drei Modi, je nach der Wertungsregel der App (SPEC §2/§9). Die
        # Ablauf-Animation läuft parallel per setTimeout und blockiert grade()
        # nicht — #cont steht sofort nach dem Aufruf da.
        if t["modus"] == "ziel":
            page.evaluate("""() => {
              const tt = SESS.tasks[0];
              const erg = simuliereRoboter(tt, tt.programm);
              pickRoboterZelle(erg.ende[0], erg.ende[1]);
            }""")
        elif t["modus"] == "programm":
            page.evaluate("""() => {
              SESS.prog = SESS.tasks[0].loesung.beispiel.slice();
              startRoboterProgramm();
            }""")
        else:  # reparieren
            page.evaluate("() => tapBefehl(SESS.tasks[0].loesung.index)")
    elif typ == "bildwahl":
        if t.get("merken_ms"):
            page.wait_for_timeout(t["merken_ms"] + 150)   # erst dann gibt es Optionen
        page.evaluate("() => chooseBild(SESS.tasks[0].richtig)")
    elif typ == "legen":
        # Bewusst FALSCH beantworten: die Rückmeldung mit der Liste der fehlenden
        # bzw. aller gültigen Anordnungen ist die längste Ansicht des Typs.
        if t["modus"] == "alle":
            page.evaluate("""() => {
              const L = legenAlle(SESS.tasks[0]);
              L[0].forEach(i => document.querySelectorAll('.lg-fig')[i].click());
              legenPruefen(); legenFertig();
            }""")
        else:
            page.evaluate("() => { SESS.typed = '5'; checkZahl(); }")
    elif typ == "bildzahl":
        page.evaluate("() => { SESS.typed = String(SESS.tasks[0].a); checkZahl(); }")
    elif typ == "positionen":
        page.evaluate("() => choosePosition(SESS.tasks[0].richtig)")
    page.wait_for_timeout(200)


def passt_brett(page):
    """Legen vor der Antwort: Brett, Knöpfe und Fundliste ohne Scrollen sichtbar,
    nichts ragt seitlich heraus?"""
    return page.evaluate("""() => {
      const vb = innerWidth, vh = innerHeight;
      const teile = [...document.querySelectorAll('.lg-fig, .lg-slot, #app button')]
        .filter(e => e.getBoundingClientRect().width > 0);
      const seitlich = teile.filter(e => { const r = e.getBoundingClientRect();
        return r.left < -1 || r.right > vb + 1; }).length;
      const knoepfe = [...document.querySelectorAll('#app button')].filter(
        b => /Legen|Das sind alle/.test(b.textContent));
      const unten = Math.max(0, ...knoepfe.map(b => b.getBoundingClientRect().bottom));
      const fig = [...document.querySelectorAll('.lg-fig')].map(e => e.getBoundingClientRect());
      return {seitlich, unten: unten <= vh + 2, figuren: fig.length,
              breit: Math.round(Math.min(...fig.map(r => r.width))),
              hoch: Math.round(Math.min(...fig.map(r => r.height)))};
    }""")


def passt(page):
    """Weiter-Knopf erreichbar und Rückmeldung sichtbar, ohne zu scrollen?"""
    return page.evaluate("""() => {
      const c = document.getElementById('cont');
      const f = document.querySelector('.fb, .info');
      const body = document.body.scrollHeight <= innerHeight + 4;
      return {cont: !c || c.getBoundingClientRect().bottom <= innerHeight + 2,
              fb: !f || f.getBoundingClientRect().top >= -2,
              body};
    }""")


def main():
    from playwright.sync_api import sync_playwright

    # ---------------------------------------------------- Rechnerische Prüfung
    html = APP.read_text("utf-8")
    start = html.index("const DATA = ") + len("const DATA = ")
    ende = html.index(";\n", start)
    data = json.loads(html[start:ende])

    units = data["units"]
    good, bad = V.filter_units(units, verbose=False)
    add("Aufgaben", "jede Aufgabe in der App ist nachgerechnet", not bad,
        f"{len(bad)} fehlerhaft" if bad else f"{len(units)} Pakete geprüft")
    for u, probleme in bad[:3]:
        add("Aufgaben", f'   {u.get("skill")}: {probleme[0][:70]}', False)

    n_tasks = sum(len(u["tasks"]) for u in units)
    add("Aufgaben", "genug Stoff für den Anfang", n_tasks >= 100, f"{n_tasks} Aufgaben")

    typen = {t["type"] for u in units for t in u["tasks"]}
    add("Aufgaben", "mehrere Aufgabenarten im Grundstock", len(typen) >= 4,
        ", ".join(sorted(typen)))

    stufen = {u["stage"] for u in units}
    add("Aufgaben", "Grundstock beginnt bei Stufe 1", 1 in stufen, f"Stufen {sorted(stufen)}")

    welten = {u.get("world") for u in units}
    add("Aufgaben", "mehrere Themenwelten vertreten", len(welten) >= 5, f"{len(welten)} Welten")

    # Kein Paket darf eine Fertigkeit über seiner Stufe verlangen
    add("Aufgaben", "jedes Paket passt zu seiner Fertigkeit",
        all(not V.check_unit(u) for u in good))

    # -------------------------------------------------------------- Passform
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for label, w, h in SIZES:
            page = b.new_context(viewport={"width": w, "height": h}).new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            T.ohne_dienst(page)
            page.goto(APP.as_uri())
            page.wait_for_timeout(400)

            eng = []
            for key, task in BEISPIELE.items():
                zeige(page, task)
                beantworte(page, key)
                r = passt(page)
                if not (r["cont"] and r["fb"]):
                    eng.append(key)
            add("Passt aufs Display", f"{label}: Rückmeldung und Weiter ohne Scrollen",
                not eng, ", ".join(eng) or f"alle {len(BEISPIELE)} Ansichten")

            # V3: das Legen-Brett VOR der Antwort (Figuren, Plätze, Knöpfe, Fundliste)
            # und die beiden Ansichten mit Zeitablauf; dazu Papier-Streifen und
            # die Denk-Check-Ansichten.
            brett_fehler = []
            for key in ("legen_alle", "legen_zaehlen", "legen_sechs"):
                zeige(page, BEISPIELE[key])
                if key == "legen_alle":      # zwei gefundene, dazu ein halb belegtes Brett
                    page.evaluate("""() => { const L = legenAlle(SESS.tasks[0]);
                      [L[0], L[1]].forEach(a => { a.forEach(i => document.querySelectorAll('.lg-fig')[i].click());
                        legenPruefen(); });
                      L[2].slice(0, 2).forEach(i => document.querySelectorAll('.lg-fig')[i].click()); }""")
                else:                        # Ausprobieren: eine gültige Anordnung gefunden
                    page.evaluate("""() => { const t = SESS.tasks[0];
                      for(let i = 0; i < t.plaetze; i++) document.querySelectorAll('.lg-fig')[i].click();
                      legenPruefen(); }""")
                page.wait_for_timeout(400)     # die Skalierung läuft 0,18 s nach
                r = passt_brett(page)
                if r["seitlich"] or not r["unten"]:
                    brett_fehler.append(f'{key}: seitlich {r["seitlich"]}, unten sichtbar {r["unten"]}')
            add("Passt aufs Display", f"{label}: Legen-Brett (Figuren, Plätze, Knöpfe, Fundliste) sichtbar",
                not brett_fehler, "; ".join(brett_fehler) or "3 Bretter")

            zeige(page, BEISPIELE["papier"])
            pap = page.evaluate("""() => { const e = document.querySelector('.papier');
              if(!e) return null; const r = e.getBoundingClientRect();
              return {oben: r.top >= -1, breit: r.right <= innerWidth + 1, links: r.left >= -1,
                      text: e.textContent.trim()}; }""")
            add("Passt aufs Display", f"{label}: Papier-Streifen vollständig sichtbar",
                bool(pap) and pap["oben"] and pap["breit"] and pap["links"]
                and pap["text"] == "📝 Papier und Stift erlaubt", str(pap))

            zeige(page, BEISPIELE["merkbild"])
            vorher = page.evaluate("""() => ({optionen: document.querySelectorAll('.bw-opt').length,
              bild: !!document.querySelector('.bw-frage svg'), balken: !!document.querySelector('.merk-balken'),
              breit: document.documentElement.scrollWidth <= innerWidth + 1})""")
            page.wait_for_timeout(BEISPIELE["merkbild"]["merken_ms"] + 500)
            nachher = page.evaluate("""() => { const g = [...document.querySelectorAll('.bw-opt')]
                .map(e => e.getBoundingClientRect());
              return {optionen: g.length, platzhalter: !!document.querySelector('.merk-weg'),
                      unten: Math.max(0, ...g.map(r => r.bottom)) <= innerHeight + 2,
                      breit: document.documentElement.scrollWidth <= innerWidth + 1}; }""")
            add("Passt aufs Display", f"{label}: Merkbild vorher (nur Bild + Balken) und nachher (Platzhalter + Optionen)",
                vorher["optionen"] == 0 and vorher["bild"] and vorher["balken"] and vorher["breit"]
                and nachher["optionen"] == 4 and nachher["platzhalter"] and nachher["breit"]
                # Die Optionen stehen im Hochformat ohne Scrollen da. Im Querformat
                # (412 px hoch) sprengt jedes 2x2-Bildraster die Höhe, auch das der
                # bisherigen Bildwahl; dort gilt nur: nichts ragt seitlich heraus.
                and (nachher["unten"] or w > h),
                f"{vorher} {nachher}")

            # Denk-Check: Karte auf der Startseite, Einleitung, Aufgabe, Zwischenstand
            # und Ergebnis. Nichts darf seitlich herausragen; Knöpfe bleiben groß genug.
            dc_fehler = []
            for ansicht in ("home", "intro", "aufgabe", "antwort", "zwischen", "ergebnis"):
                page.evaluate("""(a) => {
                  SESS = null; S = freshState(); S.profile.name = 'Alex'; S.profile.einstieg = 4;
                  S.avatar.getauft = true; S.avatar.name = 'Kiko'; save();
                  const lauf = () => S.denkcheck.laeufe[S.denkcheck.laeufe.length - 1];
                  const durch = (r, m) => { dcLos(r); const n = {};
                    while(SESS){ const t = SESS.tasks[SESS.i]; n[t.dcDim] = (n[t.dcDim] || 0) + 1;
                      grade((m[t.dcDim] || [1, 1, 1, 1])[n[t.dcDim] - 1] === 1); nextTask(); } };
                  if(a === 'home') go('home');
                  else if(a === 'intro') dcIntro('A', false);
                  else if(a === 'aufgabe') dcLos('A');
                  else if(a === 'antwort'){ dcLos('A'); grade(true); }
                  else if(a === 'zwischen') durch('A', {algorithmik: [0, 0, 0, 0], raum: [1, 0, 1, 1]});
                  else { durch('A', {raum: [1, 0, 1, 1]}); dcIntro('B', false);
                         durch('B', {systematik: [1, 1, 0, 1]}); }
                }""", ansicht)
                page.wait_for_timeout(250)
                r = page.evaluate("""() => { const vb = innerWidth;
                  const teile = [...document.querySelectorAll('#app button, #app .card, #app .dc-kraft')]
                    .filter(e => e.getBoundingClientRect().width > 0);
                  const seitlich = teile.filter(e => { const r = e.getBoundingClientRect();
                    return r.left < -1 || r.right > vb + 1; }).length;
                  const klein = [...document.querySelectorAll('#app button')].filter(
                    b => !b.disabled && b.getBoundingClientRect().height < 43.5 && !b.classList.contains('rob-chip'))
                    .map(b => b.textContent.trim().slice(0, 12));
                  return {seitlich, klein, horizontal: document.documentElement.scrollWidth > vb + 1}; }""")
                # Zu kleine Knöpfe zählen nur außerhalb der Sitzung: dort schrumpft
                # fitScreen() den Inhalt auf kleinen Displays absichtlich.
                if r["seitlich"] or r["horizontal"] or (r["klein"] and ansicht in ("home", "intro", "zwischen", "ergebnis")):
                    dc_fehler.append(f'{ansicht}: seitlich {r["seitlich"]}, waagerecht scrollbar {r["horizontal"]}, zu klein {r["klein"]}')
            add("Passt aufs Display", f"{label}: Denk-Check (Karte, Einleitung, Aufgabe, Antwort, Zwischenstand, Ergebnis)",
                not dc_fehler, "; ".join(dc_fehler) or "6 Ansichten")
            if errs:
                add("Passt aufs Display", f"{label}: keine JS-Fehler", False, errs[0][:70])
            page.close()

        # ------------------------------------------------------ Bedienbarkeit
        page = b.new_context(viewport={"width": 393, "height": 873}).new_page()
        T.ohne_dienst(page)
        page.goto(APP.as_uri()); page.wait_for_timeout(400)

        # Tippziele müssen für Kinderfinger groß genug sein (Richtwert 44 px)
        zeige(page, BEISPIELE["zahl"])
        klein = page.evaluate("""() => {
          const r = [...document.querySelectorAll('.pad button')].map(b => b.getBoundingClientRect());
          return r.filter(x => x.height < 44 || x.width < 44).length;
        }""")
        add("Bedienbarkeit", "Zifferntasten sind groß genug", klein == 0, f"{klein} zu klein")

        zeige(page, BEISPIELE["wahl"])
        klein = page.evaluate("""() => [...document.querySelectorAll('.opt')]
          .filter(b => b.getBoundingClientRect().height < 44).length""")
        add("Bedienbarkeit", "Antwortknöpfe sind groß genug", klein == 0, f"{klein} zu klein")

        # Eine falsche Eingabe darf nicht zum Weiterkommen führen
        zeige(page, BEISPIELE["zahl"])
        page.evaluate("() => { SESS.typed = '999'; checkZahl(); }")
        add("Bedienbarkeit", "falsche Zahl wird als falsch gewertet",
            page.evaluate("() => SESS.answered && !SESS.lastOk"))

        # Leere Eingabe darf gar nichts auslösen
        zeige(page, BEISPIELE["zahl"])
        page.evaluate("() => { SESS.typed = ''; checkZahl(); }")
        add("Bedienbarkeit", "leere Eingabe wird ignoriert",
            page.evaluate("() => !SESS.answered"))

        # Ordnen: falsche Reihenfolge muss auffallen
        zeige(page, BEISPIELE["ordnen"])
        page.evaluate("""() => {
          const t = SESS.tasks[0];
          const falsch = t.order.slice().reverse();
          falsch.forEach(i => pickChip(i));
        }""")
        add("Bedienbarkeit", "falsche Reihenfolge wird als falsch gewertet",
            page.evaluate("() => SESS.answered && !SESS.lastOk"))

        # Vorlesen darf nie krachen, auch ohne Sprachausgabe
        page.evaluate("() => speak('Test ohne Stimme')")
        add("Bedienbarkeit", "Vorlesen wirft keinen Fehler", True)

        # Zuordnen: keine Karte darf neben ihrem Partner liegen, sonst ist die
        # Aufgabe ohne Rechnen lösbar. 40 Ziehungen, jede muss verschoben sein.
        treffer = page.evaluate("""() => {
          let schlecht = 0;
          for(let n = 0; n < 40; n++){
            SESS = null;
            beginSession({kind:'unit', unitId:null, title:'T', intro:'', tasks:[{
              type:'zuordnen', skill:'log_paare', q:'Was passt zusammen?',
              pairs:[['a','1'],['b','2'],['c','3']]}]});
            qZuordnen(SESS.tasks[0]);
            if(SESS.rightOrder.some((src, j) => src === j)) schlecht++;
          }
          return schlecht;
        }""")
        add("Bedienbarkeit", "Zuordnen ist nie durch bloßes Danebenlegen lösbar",
            treffer == 0, f"{treffer} von 40 Ziehungen unverschoben")

        page.close()
        b.close()

    # ---------------------------------------------------------------- Ausgabe
    gruppen = {}
    for g, name, ok, info in RESULTS:
        gruppen.setdefault(g, []).append((name, ok, info))
    fails = [r for r in RESULTS if not r[2]]
    for g, items in gruppen.items():
        print(f"\n── {g} " + "─" * max(0, 58 - len(g)))
        for name, ok, info in items:
            print(f'  {"✅" if ok else "❌"} {name}' + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS)-len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
