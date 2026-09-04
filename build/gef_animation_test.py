# -*- coding: utf-8 -*-
"""Prüft die drei neuen Verhaltensweisen des Würfelfuchs-Begleiters gegen die
gebaute index.html: den sichtbaren Spaziergang (a), die Einschlafen-Sequenz
gähnt→schläft (b) und das Aufwachen blinzelt→steht per Tipp (c).

Die echten Zeiten der Präsenz-Engine liegen bei Minuten (Streifzug) bzw. einer
Minute Ruhe vor dem Einschlafen — dafür kann ein Test nicht einfach warten.
Stattdessen werden die internen Stellschrauben in GEF_ZEIT direkt verkürzt und
GEF/gefTick() unmittelbar angestoßen (laut Auftrag ausdrücklich erlaubt).

  .venv/bin/python build/gef_animation_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testhilfe as T

APP = Path(__file__).resolve().parent.parent / "index.html"

FAELLE, GRUEN = [], 0
ALLE_FEHLER = []


def t(name, ok, extra=""):
    global GRUEN
    FAELLE.append(name)
    GRUEN += 1 if ok else 0
    print(("✅" if ok else "❌") + f" {name}" + (f"   ({extra})" if extra else ""))


def neue_seite(browser):
    """Öffnet die gebaute App bis zur Startseite — Spielername- und
    Fuchs-Taufe-Dialog stehen sonst über allem anderen (siehe smoke_test.py).

    has_touch=True: Das Gerät des Kindes ist ein Touchscreen, kein Mäuschen.
    Das ist hier kein Detail — gefWach() baut #gefroot beim Aufwecken per
    renderGef() mitten in der Interaktion neu auf, und ein simulierter
    Maus-Klick (getrennte Hit-Tests für mousedown/mouseup) feuert danach kein
    "click" mehr auf dem ausgetauschten Knoten. Ein echter Finger-Tap (ein
    zusammenhängendes touchstart/-end-Gesture) übersteht das dagegen genau
    wie auf dem echten Gerät.
    """
    fehler = []
    ctx = browser.new_context(has_touch=True)
    page = ctx.new_page()
    page.on("pageerror", lambda e: fehler.append(str(e)))
    page.emulate_media(reduced_motion="no-preference")
    T.ohne_dienst(page)
    page.goto(APP.as_uri())
    page.wait_for_timeout(400)

    page.wait_for_selector(".gef-modal", timeout=3000)
    if page.locator("#spielerNameFeld").count():
        page.click("button:has-text('Später')")
        page.wait_for_timeout(150)

    page.wait_for_selector(".gef-vorschlag", timeout=3000)
    page.locator(".gef-vorschlag").first.click()
    page.wait_for_timeout(150)

    ALLE_FEHLER.append(fehler)
    return page, fehler


def grundzustand(page, **zusatz):
    """Setzt GEF auf einen sauberen, wachen Ruhezustand ohne offenen Dialog,
    bevor ein Test gezielt einen der drei neuen Abläufe erzwingt."""
    page.evaluate("""(zusatz) => {
        GEF.schlaeft = false; GEF.pose = 'steht'; GEF.draussen = false;
        GEF.laufPhase = null; GEF.laufRichtung = 0;
        GEF.reaktion = null; GEF.reaktionBis = 0; GEF.nachfrage = null;
        GEF.wachAb = Date.now();
        Object.assign(GEF, zusatz);
    }""", zusatz)


def test_schlafsequenz(browser):
    """(1) Ruhe-Timer raffen: Pose durchläuft gaehnt -> schlaeft."""
    page, fehler = neue_seite(browser)
    grundzustand(page)
    page.evaluate("""() => {
        // Ruhe-Timer "raffen": so tun, als wäre die volle Ruhezeit schon um.
        GEF.wachAb = Date.now() - GEF_ZEIT.ruheBisSchlaf - 500;
        gefTick();
    }""")
    pose1 = page.evaluate("() => GEF.pose")
    t("Nach 60 s Ruhe gähnt er zuerst, statt sofort einzuschlafen", pose1 == "gaehnt")

    page.wait_for_timeout(2200)  # gaehntDauer 1800 ms + Puffer
    zustand = page.evaluate("() => ({schlaeft: GEF.schlaeft, pose: GEF.pose})")
    t("Danach schläft er wirklich, mit der schlaeft-Pose",
      zustand["schlaeft"] is True and zustand["pose"] == "schlaeft")

    return page, fehler


def test_aufwachen(page):
    """(2) Aufwachen per Tipp: blinzelt -> steht, Sprechblase funktioniert danach."""
    war_schlaeft = page.evaluate("() => GEF.schlaeft")
    t("Vorbedingung: der Fuchs schläft noch, bevor getippt wird", war_schlaeft is True)

    page.locator(".gef").tap(force=True)
    sofort = page.evaluate("() => ({pose: GEF.pose, schlaeft: GEF.schlaeft})")
    t("Ein Tipp weckt ihn zuerst zum Blinzeln", sofort["pose"] == "blinzelt")
    t("... und er gilt sofort als wach", sofort["schlaeft"] is False)

    hat_blase = page.locator(".gef-blase").count() == 1
    t("Die Sprechblase erscheint durch denselben Tipp", hat_blase)

    page.wait_for_timeout(700)  # wachBlinzeln 500 ms + Puffer
    danach = page.evaluate("() => GEF.pose")
    t("Nach dem Blinzeln steht er wieder", danach == "steht")

    # Regression 03.09.2026: Nach längerem Schlaf war der nächste Streifzug
    # überfällig — der frisch geweckte Fuchs lief dem Kind beim nächsten Tick
    # sofort davon. gefWach() muss die Eigenleben-Uhren neu planen.
    geplant = page.evaluate(
        "() => GEF.naechsterStreifzug - Date.now() >= GEF_ZEIT.streifzugMin - 2000")
    t("Frisch geweckt ist der nächste Streifzug wieder Minuten entfernt", geplant)

    # Ein zweiter Tipp muss die Sprechblase wie gehabt wieder schließen können.
    page.locator(".gef").tap(force=True)
    page.wait_for_timeout(100)
    geschlossen = page.locator(".gef-blase").count() == 0
    t("Ein weiterer Tipp schließt die Sprechblase wie gehabt", geschlossen)


def test_spaziergang(browser):
    """(3) Spaziergang-Start erzwingen: laeuft1/laeuft2, translateX-Transition,
    nach der (gerafften) Draussen-Phase Rückkehr bis "steht"."""
    page, fehler = neue_seite(browser)
    page.evaluate("""() => {
        // Auch die Spaziergang-Zeiten raffen — sonst dauert allein der
        // Hinweg 6-9 echte Sekunden und das Warten draußen 30-90 s.
        GEF_ZEIT.laufDauerMin = 90; GEF_ZEIT.laufDauerSpanne = 0;
        GEF_ZEIT.draussenMin = 90; GEF_ZEIT.draussenSpanne = 0;
        GEF_ZEIT.schnuppertZurueck = 90;
    }""")
    grundzustand(page, naechsterStreifzug=0)  # -> längst fällig
    page.evaluate("() => gefTick()")

    start = page.evaluate("""() => {
        const el = document.querySelector('.gef');
        return {phase: GEF.laufPhase, pose: GEF.pose,
                stil: el ? el.getAttribute('style') : null};
    }""")
    t("Der Spaziergang beginnt sichtbar mit einer Gehpose",
      start["pose"] in ("laeuft1", "laeuft2"), start["pose"])
    t("... in der Phase 'raus'", start["phase"] == "raus")
    hat_transition = bool(start["stil"]) and "translateX" in start["stil"] and "transition" in start["stil"]
    t("Der Container bekommt eine translateX-Transition", hat_transition, start["stil"])

    page.wait_for_timeout(350)  # laufDauer 90 ms + Puffer
    raus_fertig = page.evaluate("() => ({phase: GEF.laufPhase, draussen: GEF.draussen})")
    t("Am Bildschirmrand angekommen ist er unsichtbar draußen",
      raus_fertig["phase"] is None and raus_fertig["draussen"] is True)

    # Draussen-Phase ebenfalls gerafft — direkt weiterschalten statt auf den
    # nächsten 1-Sekunden-Tick der laufenden setInterval(gefTick) zu warten.
    page.wait_for_timeout(150)  # draussenMin 90 ms + Puffer
    page.evaluate("() => gefTick()")
    zurueck = page.evaluate("() => GEF.laufPhase")
    t("Nach der Draussen-Phase läuft er sichtbar zurück", zurueck == "zurueck")

    # Erst knapp über die laufDauer (90 ms) warten, um die schnuppert-Pose
    # abzupassen, bevor auch noch schnuppertZurueck (ebenfalls 90 ms) verstreicht.
    page.wait_for_timeout(150)  # laufDauer 90 ms + Puffer, < 90+90
    am_ziel = page.evaluate("() => ({phase: GEF.laufPhase, pose: GEF.pose})")
    t("Am Platz zurück schnuppert er kurz", am_ziel["pose"] == "schnuppert" and am_ziel["phase"] is None)

    page.wait_for_timeout(250)  # schnuppertZurueck 90 ms + Puffer
    ende = page.evaluate("() => ({pose: GEF.pose, draussen: GEF.draussen, laufPhase: GEF.laufPhase})")
    t("... und endet wieder in steht", ende["pose"] == "steht" and not ende["draussen"] and ende["laufPhase"] is None)

    return page, fehler


def test_kein_spaziergang_auf_session(browser):
    """(4) Auf einem Aufgaben-Screen (Session) darf kein Spaziergang starten."""
    page, fehler = neue_seite(browser)
    grundzustand(page, naechsterStreifzug=0)
    page.evaluate("() => { view.name = 'session'; gefTick(); }")
    phase = page.evaluate("() => GEF.laufPhase")
    t("Auf dem Session-Screen bleibt der Spaziergang aus", phase is None)
    page.evaluate("() => { view.name = 'home'; }")
    return page, fehler


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch()

        page1, fehler1 = test_schlafsequenz(b)
        test_aufwachen(page1)

        test_spaziergang(b)
        test_kein_spaziergang_auf_session(b)

        alle_fehler = [e for liste in ALLE_FEHLER for e in liste]
        t("(5) kein JS-Fehler in allen Fällen", not alle_fehler,
          alle_fehler[0][:160] if alle_fehler else "")

        b.close()

    print(f"\n{GRUEN}/{len(FAELLE)} bestanden")
    return 0 if GRUEN == len(FAELLE) else 1


if __name__ == "__main__":
    sys.exit(main())
