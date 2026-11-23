# -*- coding: utf-8 -*-
"""Prüft den Tutor im Umgang mit dem Denk-Check (Elternwunsch 23.11.2026).

Kein Aufruf ans Modell: Ein nachgebauter Client liefert die Antwort. Geprüft
wird, was rundherum verlässlich sein muss — dass der Tutor das Profil zu sehen
bekommt, dass seine Check-Anforderung sauber durchkommt und ihre Zeitmarke
behält, solange sie offen ist, wann er von selbst nachdenkt und dass ein
gekoppeltes Gerät ihn nicht beliebig oft (und damit teuer) anstoßen kann.

  .venv/bin/python build/tutor_denkcheck_test.py
"""
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT / "tutor"))
import lehrer as L  # noqa: E402

TAG = 24 * 3600 * 1000


def antworten(n, t0):
    return [{"e": "a", "i": i + 1, "t": t0 + i * 1000, "u": "plus_bis100@3", "k": "plus_bis100",
             "o": 1, "ms": 4000} for i in range(n)]


def ergebnis(k, g, t, c=2):
    return {"e": "c", "t": t, "k": k, "g": g, "n": 4, "c": c, "ms": 15000, "z": 0}


class FakeClient:
    def __init__(self, antwort):
        self.antwort = antwort
        self.messages = SimpleNamespace(create=self.create)
        self.aufrufe = []

    def create(self, **kw):
        self.aufrufe.append(kw)
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(self.antwort))],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5))


def modellantwort(anfordern, bereiche=("umkehren",)):
    return {"beobachtung": "b", "eltern": "e", "erzeugen": [],
            "plan": [{"skill": "log_ruecklauf", "art": "vor", "gewicht": 1.6, "dosis": 5,
                      "wann": "frueh", "grund": "g"},
                     {"skill": "must_matrix", "art": "vor", "gewicht": 0.7, "dosis": 3,
                      "wann": "spaet", "grund": "Stärke"}],
            "denkcheck": {"anfordern": anfordern, "bereiche": list(bereiche) if anfordern else [],
                          "grund": "weil"}}


class Tutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plan_pfad = Path(self.tmp.name) / "tutorplan.json"
        self.auto_pfad = Path(self.tmp.name) / "tutor_auto.json"
        self.p1 = patch.object(L, "PLAN", self.plan_pfad)
        self.p2 = patch.object(L, "AUTO_PROTOKOLL", self.auto_pfad)
        self.p1.start(); self.p2.start()
        self.jetzt = int(time.time() * 1000)
        self.ev = antworten(20, self.jetzt - 10 * TAG) + [
            ergebnis("schlussketten", 2.5, self.jetzt - 20 * TAG, c=1),
            ergebnis("strukturen", 8.5, self.jetzt - 20 * TAG, c=4)]
        self.p3 = patch.object(L.SP, "alle_ereignisse", lambda: self.ev)
        self.p3.start()
        L._laeuft["ja"] = False

    def tearDown(self):
        patch.stopall()
        self.tmp.cleanup()

    # ------------------------------------------------------------ Säuberung
    def test_saeubere_denkcheck(self):
        p, h = L.saeubere(modellantwort(True, ("umkehren", "gibtsnicht", "umkehren")))
        self.assertEqual(p["denkcheck"]["bereiche"], ["umkehren"])
        self.assertTrue(p["denkcheck"]["anfordern"])
        self.assertTrue(any("gibtsnicht" in x for x in h))
        roh = modellantwort(True); roh["denkcheck"]["bereiche"] = ["gibtsnicht"]
        self.assertFalse(L.saeubere(roh)[0]["denkcheck"]["anfordern"], "ohne gültigen Bereich keine Anforderung")
        roh = modellantwort(False); del roh["denkcheck"]
        self.assertEqual(L.saeubere(roh)[0]["denkcheck"]["anfordern"], False)

    def test_uebungsweg_nur_bekannte_fertigkeiten(self):
        for k, liste in L.DENKCHECK_UEBEN.items():
            for s in liste:
                self.assertIn(s, L._IDS, f"{k}: {s}")
        self.assertEqual(set(L.DENKCHECK_UEBEN), set(L._dc_titel()), "Bereiche = Aufgabenbank")

    # -------------------------------------------------------------- Auszug
    def test_auszug_zeigt_profil_und_weg(self):
        a = L.denkcheck_auszug(self.ev, None)
        self.assertIn("DENK-CHECK", a)
        self.assertIn("Stufe 2.5", a)
        self.assertIn("log_ruecklauf", a)
        self.assertIn("noch nicht geprüft", a)
        self.assertIn("Letzter Check vor 20 Tagen", a)
        self.assertIn("DENK-CHECK", L.auszug())

    def test_offene_anforderung(self):
        plan = {"denkcheck": {"anfordern": True, "t": self.jetzt - TAG, "bereiche": ["umkehren", "schlussketten"],
                              "stand": L.check_stand(self.ev)}}
        self.assertIsNotNone(L.offene_anforderung(plan, self.ev))
        self.assertIn("Offen:", L.denkcheck_auszug(self.ev, plan))
        ev = self.ev + [ergebnis("umkehren", 3.5, self.jetzt)]
        self.assertIsNotNone(L.offene_anforderung(plan, ev), "schlussketten fehlt noch (das alte zählt nicht)")
        ev.append(ergebnis("schlussketten", 3.5, self.jetzt))
        self.assertIsNone(L.offene_anforderung(plan, ev))

    def test_erledigt_unabhaengig_von_der_geraeteuhr(self):
        # Geräteuhr geht zwei Tage nach: das Ergebnis kam trotzdem nach der Anforderung.
        plan = {"denkcheck": {"anfordern": True, "t": self.jetzt, "bereiche": ["umkehren"],
                              "stand": L.check_stand(self.ev)}}
        self.assertIsNone(L.offene_anforderung(plan, self.ev + [ergebnis("umkehren", 3, self.jetzt - 2 * TAG)]))
        # Geräteuhr geht vor: ein altes Ergebnis macht faellig() nicht dauerhaft wahr.
        self.ev.append(ergebnis("umkehren", 3, self.jetzt + 5 * TAG))
        L.schreib_plan({"t": self.jetzt, "grundlage": {"antworten": 20, "checks": 3}, "plan": []})
        self.assertFalse(L.faellig())

    # -------------------------------------------- Zeitmarke der Anforderung
    def test_anforderung_behaelt_zeit_solange_offen(self):
        p, _ = L.denk_nach(FakeClient(modellantwort(True)))
        t1 = p["denkcheck"]["t"]
        self.assertGreater(t1, 0)
        time.sleep(0.01)
        p2, _ = L.denk_nach(FakeClient(modellantwort(True)))
        self.assertEqual(p2["denkcheck"]["t"], t1, "offene Anforderung behält ihre Zeit")
        self.assertEqual(p2["denkcheck"]["stand"], p["denkcheck"]["stand"])
        # Erledigt (gezählt), aber mit einer Geräteuhr-Zeit außerhalb der Pause
        self.ev.append(ergebnis("umkehren", 3.5, self.jetzt - 15 * TAG))
        time.sleep(0.01)
        p3, _ = L.denk_nach(FakeClient(modellantwort(True)))
        self.assertGreater(p3["denkcheck"]["t"], t1, "nach Erledigung gilt eine neue Zeit")
        p4, _ = L.denk_nach(FakeClient(modellantwort(False)))
        self.assertNotIn("t", p4["denkcheck"])
        self.assertEqual(json.loads(self.plan_pfad.read_text("utf-8"))["denkcheck"]["anfordern"], False)

    def test_pause_nach_einem_check(self):
        self.ev.append(ergebnis("merken", 8.5, self.jetzt - 3 * TAG))
        p, log = L.denk_nach(FakeClient(modellantwort(True)))
        self.assertFalse(p["denkcheck"]["anfordern"])
        self.assertTrue(any("zurückgestellt" in x for x in log))

    def test_prompt_traegt_schema_und_auszug(self):
        c = FakeClient(modellantwort(False))
        L.denk_nach(c)
        kw = c.aufrufe[0]
        self.assertIn("denkcheck", kw["output_config"]["format"]["schema"]["required"])
        self.assertIn("DENK-CHECK", kw["messages"][0]["content"])
        self.assertIn("Denk-Check", kw["system"])

    # ------------------------------------------------------------ fällig?
    def test_faellig(self):
        L.schreib_plan({"t": self.jetzt - 30 * 3600 * 1000, "grundlage": {"antworten": 20, "checks": 2}, "plan": []})
        self.assertFalse(L.faellig(), "alter Plan ohne neue Antwort: kein Lauf")
        self.ev.append(antworten(1, self.jetzt)[0] | {"i": 99})
        self.assertTrue(L.faellig(), "alter Plan mit neuer Antwort")
        self.ev.pop()
        L.schreib_plan({"t": self.jetzt - 3600 * 1000, "grundlage": {"antworten": 20, "checks": 2}, "plan": []})
        self.assertFalse(L.faellig())
        self.ev.append(ergebnis("umkehren", 3.5, self.jetzt))
        self.assertTrue(L.faellig(), "neues Check-Ergebnis seit dem Plan")

    # ------------------------------------------------------ Kostenbremse
    def test_auto_deckel(self):
        t = self.jetzt
        self.assertEqual([L._auto_frei(t + i) for i in range(5)], [True, True, True, False, False])
        self.assertTrue(L._auto_frei(t + TAG + 10), "nach 24 Stunden wieder frei")
        self.auto_pfad.write_text("kaputt", "utf-8")
        self.assertTrue(L._auto_frei(t), "kaputtes Protokoll stellt den Tutor nicht ab")

    def test_elternknopf_waehrend_eines_laufs(self):
        L._laeuft["ja"] = True
        p, log = L.denk_nach(FakeClient(modellantwort(False)))
        self.assertIsNone(p)
        self.assertIn("schon", log[0])
        L._laeuft["ja"] = False
        self.assertIsNotNone(L.denk_nach(FakeClient(modellantwort(False)))[0])
        self.assertFalse(L._laeuft["ja"], "nach dem Lauf wieder frei")

    def test_gleichzeitige_anstoesse(self):
        # Acht Übertragungen gleichzeitig: genau ein bezahlter Lauf.
        sperre, gestartet = threading.Event(), []

        def langsam(*a, **k):
            gestartet.append(1); sperre.wait(2); return None, ["x"]

        start = threading.Barrier(8)
        def anstoss():
            start.wait(); L.vielleicht_nachdenken()
        with patch.object(L, "_denk_nach", langsam):
            fs = [threading.Thread(target=anstoss) for _ in range(8)]
            [f.start() for f in fs]; [f.join() for f in fs]
            sperre.set()
            for _ in range(100):
                if not L._laeuft["ja"]:
                    break
                time.sleep(0.01)
        self.assertEqual(len(gestartet), 1)
        self.assertEqual(len(json.loads(self.auto_pfad.read_text("utf-8"))), 1)

    def test_elternseite_zeigt_anforderung(self):
        import eltern as E
        L.schreib_plan({"t": self.jetzt, "datum": "x", "grundlage": {"antworten": 20}, "plan": [],
                        "denkcheck": {"anfordern": True, "t": self.jetzt, "bereiche": ["umkehren"],
                                      "grund": "Wirkt das Üben?", "stand": L.check_stand(self.ev)}})
        html = E._tutor({"fertigkeiten": []})
        self.assertIn("Denk-Check angefordert", html)
        self.assertIn("Wirkt das Üben?", html)
        self.assertIn("gemacht ist er noch nicht", html)
        self.ev.append(ergebnis("umkehren", 3, self.jetzt))
        self.assertIn("Erledigt", E._tutor({"fertigkeiten": []}))
        L.schreib_plan({"t": self.jetzt, "datum": "x", "grundlage": {"antworten": 20}, "plan": [],
                        "denkcheck": {"anfordern": False, "bereiche": [], "grund": "zu früh"}})
        self.assertIn("Diesmal keiner: zu früh", E._tutor({"fertigkeiten": []}))

    def test_kein_doppelter_lauf(self):
        sperre = threading.Event()
        gestartet = []

        def langsam(*a, **k):
            gestartet.append(1)
            sperre.wait(2)
            return None, ["x"]

        with patch.object(L, "faellig", lambda: not L._laeuft["ja"]), patch.object(L, "_denk_nach", langsam):
            self.assertTrue(L.vielleicht_nachdenken())
            self.assertFalse(L.vielleicht_nachdenken(), "zweiter Anstoß, während der erste läuft")
            sperre.set()
            for _ in range(100):
                if not L._laeuft["ja"]:
                    break
                time.sleep(0.01)
        self.assertEqual(len(gestartet), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
