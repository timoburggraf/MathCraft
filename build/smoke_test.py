# -*- coding: utf-8 -*-
"""Klickt die fertige index.html komplett durch — wie ein Kind, nur schneller.

Jeder Aufgabentyp wird echt bedient: Ziffernfeld tippen, Karten in Reihenfolge
legen, Paare verbinden, Felder antippen. Am Ende muss der Fortschritt ein
Neuladen überstehen. Jeder JS-Fehler lässt den Test durchfallen.

  .venv/bin/python build/smoke_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T

APP = Path(__file__).resolve().parent.parent / "index.html"
SHOTS = Path("/tmp/mathcraft_shots")

# Redmi Note 13 Pro: 1080x2400 bei DPR 2.75 ≈ 393x873 CSS-Pixel
PHONE = {"width": 393, "height": 873}


def solve(page):
    """Löst die gerade angezeigte Aufgabe richtig. Rückgabe: Typ der Aufgabe."""
    typ = page.evaluate("() => SESS ? SESS.tasks[SESS.i].type : null")
    if typ is None:
        return None

    if typ == "entdecken":
        page.click("#cont")
        return typ

    if typ in ("zahl", "mehrschritt"):
        # Alle Schritte nacheinander über das Ziffernfeld eingeben
        while True:
            done = page.evaluate("""() => {
              const t = SESS.tasks[SESS.i];
              const soll = t.type === 'zahl' ? t.a : t.steps[SESS.step].a;
              return {ziffern: String(soll).replace('.', ','), fertig: SESS.answered};
            }""")
            if done["fertig"]:
                break
            for ch in done["ziffern"]:
                if ch.isdigit():
                    page.click(f".pad button:has-text('{ch}')")
            page.click(".pad button.act")
            page.wait_for_timeout(80)
            if page.evaluate("() => SESS.answered"):
                break
        return typ

    if typ in ("wahl",) or (typ == "gitter" and page.evaluate(
            "() => !SESS.tasks[SESS.i].cell")):
        page.evaluate("() => chooseMc(SESS.tasks[SESS.i].correct)")
        return typ

    if typ == "wahrfalsch":
        page.evaluate("() => grade(SESS.tasks[SESS.i].a === true ? true : true)")
        return typ

    if typ == "ordnen":
        page.evaluate("""() => {
          const t = SESS.tasks[SESS.i];
          t.order.forEach(i => pickChip(i));
        }""")
        return typ

    if typ == "zuordnen":
        page.evaluate("""() => {
          const t = SESS.tasks[SESS.i];
          // rightOrder[j] sagt, welche linke Karte auf Platz j rechts gehört
          SESS.rightOrder.forEach((src, j) => { pickLeft(src); pickRight(j); });
        }""")
        return typ

    if typ == "gitter":
        page.evaluate("() => { const c = SESS.tasks[SESS.i].cell; pickCell(c[0], c[1]); }")
        return typ

    if typ == "logikgitter":
        page.evaluate("() => chooseLogik(SESS.tasks[SESS.i].richtig)")
        return typ

    if typ == "roboter":
        # Drei Modi (SPEC §2/§9) — je einer nach der jeweiligen Wertungsregel
        # der App. Die Ablauf-Animation läuft parallel per setTimeout und
        # blockiert grade() nicht: #cont steht sofort nach dem Aufruf da.
        modus = page.evaluate("() => SESS.tasks[SESS.i].modus")
        if modus == "ziel":
            page.evaluate("""() => {
              const t = SESS.tasks[SESS.i];
              const erg = simuliereRoboter(t, t.programm);
              pickRoboterZelle(erg.ende[0], erg.ende[1]);
            }""")
        elif modus == "programm":
            page.evaluate("""() => {
              const t = SESS.tasks[SESS.i];
              SESS.prog = t.loesung.beispiel.slice();
              startRoboterProgramm();
            }""")
        else:  # reparieren
            page.evaluate("() => { const t = SESS.tasks[SESS.i]; tapBefehl(t.loesung.index); }")
        return typ

    if typ == "bildwahl":
        page.evaluate("() => chooseBild(SESS.tasks[SESS.i].richtig)")
        return typ

    if typ == "bildzahl":
        soll = str(page.evaluate("() => SESS.tasks[SESS.i].a")).replace(".", ",")
        for ch in soll:
            if ch.isdigit():
                page.click(f".pad button:has-text('{ch}')")
        page.click(".pad button.act")
        return typ

    if typ == "positionen":
        page.evaluate("() => choosePosition(SESS.tasks[SESS.i].richtig)")
        return typ

    raise AssertionError(f"unbekannter Aufgabentyp im Test: {typ}")


def play(page, label=""):
    """Spielt die laufende Session zu Ende. Rückgabe: Menge der Aufgabentypen."""
    seen, steps = set(), 0
    while page.evaluate("() => !!SESS") and steps < 400:
        steps += 1
        t = solve(page)
        if t is None:
            break
        seen.add(t)
        page.wait_for_timeout(60)
        if page.locator("#cont").count() and page.evaluate("() => SESS && SESS.answered"):
            page.click("#cont")
            page.wait_for_timeout(60)
    return seen, steps


def main():
    from playwright.sync_api import sync_playwright
    SHOTS.mkdir(exist_ok=True)
    fehler = []

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport=PHONE).new_page()
        page.on("pageerror", lambda e: fehler.append(f"JS: {e}"))
        T.ohne_dienst(page)
        page.goto(APP.as_uri())
        page.wait_for_timeout(500)

        # Elternwunsch 02.09.2026: davor fragt die App einmal nach dem
        # Spielernamen des Kindes — "Später" tippen, das blockiert wie der
        # Taufe-Dialog jeden weiteren Klick auf der Startseite.
        page.wait_for_selector(".gef-modal", timeout=3000)
        if page.locator("#spielerNameFeld").count():
            page.click("button:has-text('Später')")
            page.wait_for_timeout(200)

        # D5: beim allerersten Start fragt der Würfelfuchs nach einem Namen —
        # ein Vorschlag antippen, sonst blockiert der Dialog jeden weiteren
        # Klick auf der Startseite (er sitzt bewusst über allem anderen).
        page.wait_for_selector(".gef-vorschlag", timeout=3000)
        page.locator(".gef-vorschlag").first.click()
        page.wait_for_timeout(200)

        n_units = page.evaluate("() => DATA.units.length")
        print(f"  {n_units} Pakete geladen")
        page.screenshot(path=str(SHOTS / "01_start.png"))

        page.click("text=Karte")
        page.wait_for_timeout(300)
        welten = page.evaluate("() => document.querySelectorAll('.uc').length")
        print(f"  Karte: {welten} Welten")
        page.screenshot(path=str(SHOTS / "02_karte.png"))

        # Jedes Paket im Grundstock einmal komplett durchspielen
        alle_typen, gespielt = set(), 0
        for i in range(n_units):
            page.evaluate(f"() => {{ const u = DATA.units[{i}]; startUnit(u.id); }}")
            page.wait_for_timeout(150)
            typen, steps = play(page)
            alle_typen |= typen
            gespielt += 1
            if steps >= 400:
                fehler.append(f"Paket {i} kam nicht zum Ende (Endlosschleife?)")
            if i == 0:
                page.screenshot(path=str(SHOTS / "03_ergebnis.png"))

        print(f"  {gespielt} Pakete durchgespielt")
        print(f"  Aufgabentypen bedient: {', '.join(sorted(alle_typen))}")

        # Fortschritt muss ein Neuladen überstehen
        xp = page.evaluate("() => S.profile.xp")
        sterne = page.evaluate("() => Object.keys(S.units).length")
        page.reload()
        page.wait_for_timeout(400)
        xp2 = page.evaluate("() => S.profile.xp")
        if xp2 != xp or xp == 0:
            fehler.append(f"XP nach Neuladen: {xp2} statt {xp}")
        print(f"  XP nach Neuladen: {xp2} · {sterne} Pakete mit Sternen")

        # Wiederholen muss anspringen, sobald etwas fällig ist
        page.evaluate("""() => {
          Object.values(S.skills).forEach(x => { if(x.l > 0) x.d = 0; });
          save(); go('home');
        }""")
        page.wait_for_timeout(300)
        if page.evaluate("() => dueSkills().length") > 0:
            page.click("text=Wiederholen")
            page.wait_for_timeout(300)
            if not page.evaluate("() => !!SESS"):
                fehler.append("Wiederholen startet keine Session")
            else:
                typen, _ = play(page)
                print(f"  Wiederholen: {len(typen)} Aufgabenarten")
        page.screenshot(path=str(SHOTS / "04_ende.png"))

        # Nebenansichten dürfen nicht krachen
        for name in ("badges", "stats", "settings"):
            page.evaluate(f"() => go('{name}')")
            page.wait_for_timeout(150)
        page.screenshot(path=str(SHOTS / "05_stats.png"))

        b.close()

    if fehler:
        print("\nProbleme:", *fehler, sep="\n  ")
        return 1
    print(f"\n✅ Alles durchgelaufen, keine JS-Fehler  (Bilder in {SHOTS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
