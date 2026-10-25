# -*- coding: utf-8 -*-
"""Prüft Z2 aus ZIELE.md: sagt die Elternseite die Wahrheit, und zwar lückenlos?

Die Schwellen für „sitzt“ und „hakt“ sind eine Setzung, keine Naturkonstante.
Genau deshalb müssen sie geprüft werden: Verschiebt sie jemand aus Versehen,
ändert sich stillschweigend, was Eltern über ihr Kind erfahren.

  .venv/bin/python build/eltern_test.py

Seit der Sicherheitsumstellung spricht der Dienst nur noch HTTPS und verlangt
Elternanmeldung (Cookie plus einmaliges CSRF-Token) bzw. signierte
Geräteanfragen. Der Test startet deshalb seinen eigenen Dienst mit
Dummy-Geheimnissen und selbstsigniertem Zertifikat auf localhost und geht
denselben Weg wie ein Browser: anmelden, Token holen, Formular abschicken. Die
Klasse HttpsDienst unten nutzen wunsch_test.py und sync_test.py ebenfalls —
an den Sicherheitsprüfungen im Dienst wird dafür nichts gelockert.

Ist die Umgebungsvariable ELTERN_BILD gesetzt, schreibt der Test am Ende ein
Bildschirmfoto der Abschnitte Denk-Check und Elternbogen dorthin.
"""
import hashlib
import hmac
import http.client
import json
import json as _json
import os
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
PORT = 8797

RESULTS = []


def add(name, ok, info=""):
    RESULTS.append((name, bool(ok), info))


def frei(port):
    s = socket.socket()
    # Wie die Dienste selbst: sonst meldet ein Socket aus dem letzten Lauf, der
    # noch in TIME-WAIT haengt, den Port faelschlich als belegt.
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


# ------------------------------------------------- HTTPS-Dienst für die Tests

# Der Dienst läuft in einem eigenen Prozess; build_app() bekommt Dummy-
# Geheimnisse über die Testkonfiguration, der Vault wird nie berührt.
_START = r"""
import os, sys
sys.path.insert(0, os.environ["MC_T_ROOT"] + "/tutor")
import server
app = server.build_app({
    "TESTING": True, "MC_STATE_HOME": os.environ["MC_T_STATE"],
    "MATHCRAFT_PARENT_PASSWORD": os.environ["MC_T_PASSWORT"],
    "MATHCRAFT_SESSION_KEY": "synthetic-session-signing-key-only-tests",
    "MATHCRAFT_DEVICE_KEY": "synthetic-device-root-key-only-tests"})
app.run(host="127.0.0.1", port=int(os.environ["MC_T_PORT"]), threaded=True,
        ssl_context=(os.environ["MC_T_CERT"], os.environ["MC_T_KEY"]))
"""


class Antwort:
    def __init__(self, status, header, body):
        self.status, self.header, self.body = status, header, body

    @property
    def text(self):
        return self.body.decode("utf-8")

    def json(self):
        return json.loads(self.body)


class HttpsDienst:
    """Ein lokal gestarteter HTTPS-Dienst mit Eltern-Anmeldung und Geräte-Signatur.

    Nur 127.0.0.1, nur Dummy-Geheimnisse (pro Lauf neu), selbstsigniertes
    Zertifikat — das Zertifikat wird absichtlich nicht geprüft, denn es gibt
    nichts, wogegen zu prüfen wäre. Der Zustand (Sitzungen, Geräte) liegt in
    einem eigenen Wegwerf-Ordner; die Telemetrie in `tele`.
    """

    def __init__(self, port, tele, plan=None):
        self.port, self.tele = port, Path(tele)
        self.arbeit = Path(tempfile.mkdtemp(prefix="mathcraft_https_"))
        self.zustand = self.arbeit / "zustand"
        self.zustand.mkdir(mode=0o700)
        self.passwort = secrets.token_urlsafe(24)
        self.plan = plan or (self.arbeit / "tutorplan.json")
        self.cookies = {}
        self.prozess = None
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE

    @property
    def basis(self):
        return f"https://127.0.0.1:{self.port}"

    def start(self):
        cert, key = self.arbeit / "cert.pem", self.arbeit / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt",
                        "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", str(key),
                        "-out", str(cert), "-days", "1", "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        env = dict(os.environ, MC_TELE=str(self.tele), MC_PLAN=str(self.plan),
                   MC_T_ROOT=str(ROOT), MC_T_STATE=str(self.zustand),
                   MC_T_PASSWORT=self.passwort, MC_T_PORT=str(self.port),
                   MC_T_CERT=str(cert), MC_T_KEY=str(key))
        self.prozess = subprocess.Popen([sys.executable, "-c", _START], env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                if self.anfrage("GET", "/health").status == 200:
                    return True
            except OSError:
                time.sleep(.2)
        return False

    def stop(self):
        if self.prozess:
            self.prozess.terminate()
            try:
                self.prozess.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.prozess.kill()
        shutil.rmtree(self.arbeit, ignore_errors=True)

    # ------------------------------------------------------------- Anfragen
    def anfrage(self, methode, pfad, body=None, header=None, cookies=True):
        """Eine Anfrage ohne Umleitung zu folgen (ob der Dienst umleitet, ist
        selbst Prüfgegenstand). Cookies werden wie im Browser mitgeführt."""
        h = dict(header or {})
        if cookies and self.cookies:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        c = http.client.HTTPSConnection("127.0.0.1", self.port, context=self._ctx, timeout=30)
        try:
            c.request(methode, pfad, body=body, headers=h)
            r = c.getresponse()
            daten = r.read()
            for roh in r.headers.get_all("Set-Cookie") or []:
                sc = SimpleCookie()
                sc.load(roh)
                for k, m in sc.items():
                    if m.value:
                        self.cookies[k] = m.value
                    else:
                        self.cookies.pop(k, None)
            return Antwort(r.status, r.headers, daten)
        finally:
            c.close()

    def get(self, pfad):
        return self.anfrage("GET", pfad)

    def anmelden(self):
        """Elternanmeldung wie im Browser: Formular holen, Token und Passwort abschicken."""
        seite = self.get("/login").text
        token = re.search(r'name="csrf" value="([^"]+)"', seite).group(1)
        a = self.anfrage("POST", "/login", urlencode({"csrf": token, "password": self.passwort}),
                         {"Content-Type": "application/x-www-form-urlencoded"})
        return a.status == 303

    def csrf(self):
        """Das einmalige Token der Sitzung — steht in jedem Formular der Elternseite."""
        return re.search(r'name="csrf" value="([^"]+)"', self.get("/eltern").text).group(1)

    def formular(self, pfad, felder):
        """Ein Elternformular abschicken, mit frischem Token (jedes gilt nur einmal).
        felder: dict oder Liste von Paaren."""
        paare = list(felder.items()) if isinstance(felder, dict) else list(felder)
        paare.append(("csrf", self.csrf()))
        return self.anfrage("POST", pfad, urlencode(paare),
                            {"Content-Type": "application/x-www-form-urlencoded"})

    # --------------------------------------------------------------- Geräte
    def koppeln(self, dev):
        """Gerät über den Elternweg freigeben (Code, dann /pair) -> Geräteschlüssel."""
        a = self.formular("/device/pair-code", {"dev": dev})
        code = re.search(r"<strong>([A-Z2-7]+)</strong>", a.text).group(1)
        r = self.anfrage("POST", "/pair", json.dumps({"dev": dev, "code": code}),
                         {"Content-Type": "application/json"}, cookies=False)
        return r.json()["key"]

    def signiert(self, dev, key, pfad, nutzlast):
        """Eine signierte Geräteanfrage, so wie die App sie schickt."""
        roh = json.dumps(nutzlast, separators=(",", ":")).encode("utf-8")
        stempel, nonce = str(int(time.time())), secrets.token_hex(16)
        kanon = "\n".join(("POST", pfad, stempel, nonce, hashlib.sha256(roh).hexdigest()))
        sig = hmac.new(key.encode(), kanon.encode(), hashlib.sha256).hexdigest()
        return self.anfrage("POST", pfad, roh,
                            {"Content-Type": "application/json", "X-MC-Device": dev,
                             "X-MC-Time": stempel, "X-MC-Nonce": nonce, "X-MC-Signature": sig},
                            cookies=False)


def antwort(nr, skill, stufe, ok, t, typ="zahl"):
    return {"i": nr, "t": t, "s": "abcd1234", "e": "a", "u": f"{skill}@{stufe}",
            "k": skill, "g": stufe, "y": typ, "o": 1 if ok else 0,
            "ms": 5000, "r": 0, "h": 0}


def _wirft(f):
    """True, wenn der Aufruf mit ValueError abgewiesen wird."""
    try:
        f()
    except ValueError:
        return True
    return False


def _bildschirmfoto(dienst, pfad, ziel):
    """Die Abschnitte Denk-Check und Elternbogen als Bild (Breite 1000 px) —
    mit der Anmeldung des Tests, über denselben HTTPS-Dienst."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": 1000, "height": 900}, ignore_https_errors=True)
        ctx.add_cookies([{"name": n, "value": v, "url": dienst.basis, "secure": True}
                         for n, v in dienst.cookies.items()])
        seite = ctx.new_page()
        seite.goto(dienst.basis + pfad)
        box = seite.evaluate("""() => {
          const oben = document.getElementById('denkcheck').getBoundingClientRect().top + scrollY;
          const karten = document.getElementById('elternbogen').parentElement
            ? [...document.querySelectorAll('#elternbogen ~ .card')] : [];
          const unten = karten.slice(0, 2).pop().getBoundingClientRect().bottom + scrollY;
          return {oben, unten};
        }""")
        Path(ziel).parent.mkdir(parents=True, exist_ok=True)
        seite.screenshot(path=str(ziel), full_page=True,
                         clip={"x": 0, "y": max(0, box["oben"] - 12), "width": 1000,
                               "height": box["unten"] - box["oben"] + 24})
        b.close()


def main():
    tele = Path(tempfile.mkdtemp(prefix="mathcraft_eltern_"))
    os.environ["MC_TELE"] = str(tele)
    sys.path.insert(0, str(ROOT / "tutor"))
    sys.path.insert(0, str(ROOT / "build"))
    import auswertung as A
    import curriculum as C
    import eltern as E

    jetzt = int(time.time() * 1000)
    tag = 86400000

    # ------------------------------------------------- Schwellen für sich
    ids = [s["id"] for s in C.SKILLS]
    s_sitzt, s_hakt, s_arbeit, s_serie, s_knapp = ids[0], ids[1], ids[2], ids[3], ids[4]
    ev, nr = [], 1

    def reihe(skill, muster, ab):
        nonlocal nr
        for k, ok in enumerate(muster):
            ev.append(antwort(nr, skill, 1, ok, jetzt - (ab - k) * 3600000))
            nr += 1

    reihe(s_sitzt,  [1] * 9 + [0], 40)               # 10 Antworten, 90 % richtig
    reihe(s_hakt,   [1, 0, 0, 1, 0, 0], 30)          # 6 Antworten, 33 % richtig
    reihe(s_arbeit, [1, 1, 0], 20)                   # zu wenige für beide Schwellen
    reihe(s_serie,  [1] * 17 + [0, 0, 0], 15)        # 85 % richtig, aber dreimal daneben
    reihe(s_knapp,  [1] * 9, 10)                     # 100 %, aber nur 9 Antworten

    fert = {f["id"]: f for f in A.fertigkeiten(ev)}
    add("10 Antworten mit 90 % gelten als „sitzt“",
        fert[s_sitzt]["zustand"] == "sitzt", fert[s_sitzt]["zustand"])
    add("6 Antworten mit 33 % gelten als „hakt“",
        fert[s_hakt]["zustand"] == "hakt", fert[s_hakt]["zustand"])
    add("Wenige Antworten gelten als „in Arbeit“",
        fert[s_arbeit]["zustand"] == "arbeit", fert[s_arbeit]["zustand"])
    add("Drei Fehlversuche in Folge schlagen die gute Gesamtquote",
        fert[s_serie]["zustand"] == "hakt",
        f'{fert[s_serie]["zustand"]}, Quote {fert[s_serie]["quote"]:.0%}')
    add("Eine Antwort zu wenig reicht nicht für „sitzt“",
        fert[s_knapp]["zustand"] == "arbeit",
        f'{fert[s_knapp]["n"]} Antworten, {fert[s_knapp]["zustand"]}')
    add("Ungeübtes heißt „noch nicht geübt“, nicht 0 %",
        fert[ids[-1]]["zustand"] == "unberuehrt")

    add("Jede Fertigkeit des Lehrplans kommt genau einmal vor",
        len(fert) == len(C.SKILLS) == len(A.fertigkeiten(ev)),
        f"{len(fert)} von {len(C.SKILLS)}")

    # -------------------------------------------------------------- Verlauf
    v = A.verlauf(ereignisse=ev)
    add(f"Der Verlauf umfasst {A.WOCHEN} Wochen", len(v["wochen"]) == A.WOCHEN)
    add("Jede Welt hat eine Reihe im Verlauf",
        all(len(v["bereiche"][a["id"]]) == A.WOCHEN for a in C.AREAS))
    add("Wochen ohne Aufgaben sind 0 und nicht leer",
        all(w["n"] >= 0 and "quote" in w for w in v["gesamt"]))

    # ------------------------------------------------------------ Nordstern
    sess = [
        {"i": 900, "t": jetzt, "s": "z1", "e": "s", "q": "unit", "n": 10, "c": 8, "ms": 1, "z": 0},
        {"i": 901, "t": jetzt, "s": "z2", "e": "s", "q": "unit", "n": 10, "c": 10, "ms": 1, "z": 0},
        {"i": 902, "t": jetzt, "s": "z3", "e": "s", "q": "unit", "n": 10, "c": 4, "ms": 1, "z": 0},
        {"i": 903, "t": jetzt, "s": "z4", "e": "s", "q": "unit", "n": 3, "c": 3, "ms": 1, "z": 1},
    ]
    n = A.nordstern(ev + sess)
    add("Zielband zählt nur die gewerteten Sitzungen",
        n["gewertet"] == 3 and n["im_band"] == 1, f'{n["im_band"]}/{n["gewertet"]}')
    add("Zu leicht und zu schwer werden getrennt gezählt",
        n["zu_leicht"] == 1 and n["zu_schwer"] == 1)
    add("Kurze Sitzungen zählen als Abbruch",
        n["kurz"] == 1 and abs(n["anteil_kurz"] - .25) < 1e-9, f'{n["anteil_kurz"]:.2f}')

    # ------------------------------------------------------ Die Seite selbst
    if not frei(PORT):
        sys.exit(f"Port {PORT} ist belegt")

    # 90 Tage Daten, damit die Ladezeit unter realistischer Last gemessen wird
    viele, nr2 = [], 1
    for t in range(90):
        for k in range(30):
            viele.append(antwort(nr2, ids[t % len(ids)], 1 + t % 6,
                                 (nr2 % 4) != 0, jetzt - t * tag + k * 60000))
            nr2 += 1
    import speicher as SP
    # Spielername (Elternwunsch 02.09.2026): dieses Gerät trägt einen Namen,
    # damit die Gerätetabelle ihn statt der nackten Kennung zeigen kann.
    SP.schreibe("00aa11bb22cc33dd", viele, {"answers": len(viele), "lost": 0}, jetzt,
                name="Alex")

    # ---------------------------------------------- D6: Motivations-Ereignisse
    # Abbruchgründe ("g") und Spaß-Signale ("f") für den neuen Abschnitt
    # "Wie es ihm damit geht" — dasselbe Paket wie oben (s_hakt@1), damit sich
    # der Fertigkeitstitel im Fließtext wiederfindet.
    mot_unit = f"{s_hakt}@1"
    titel_hakt = next(s["title"] for s in C.SKILLS if s["id"] == s_hakt)
    mot_ev = [
        {"i": 1, "t": jetzt - 2*3600000, "s": "mot1", "e": "g", "u": mot_unit, "w": 3},  # zu schwer
        {"i": 2, "t": jetzt - 1*3600000, "s": "mot1", "e": "g", "u": mot_unit, "w": 2},  # zu langweilig
        {"i": 3, "t": jetzt - 50*60000, "s": "mot1", "e": "f", "u": mot_unit, "w": 3},
        {"i": 4, "t": jetzt - 40*60000, "s": "mot1", "e": "f", "u": mot_unit, "w": 3},
        {"i": 5, "t": jetzt - 30*60000, "s": "mot1", "e": "f", "u": mot_unit, "w": 2},
        {"i": 6, "t": jetzt - 20*60000, "s": "mot1", "e": "f", "u": mot_unit, "w": 1},
        # zwei 0/0-Sitzungen: Paket geöffnet, sofort ohne Antwort wieder verlassen
        {"i": 7, "t": jetzt - 15*60000, "s": "mot2", "e": "s", "q": "unit",
         "u": mot_unit, "n": 0, "c": 0, "ms": 400, "z": 1},
        {"i": 8, "t": jetzt - 10*60000, "s": "mot3", "e": "s", "q": "unit",
         "u": mot_unit, "n": 0, "c": 0, "ms": 400, "z": 1},
    ]
    SP.schreibe("22bb33cc44dd55ee", mot_ev, {"answers": 0}, jetzt)
    # Dieses zweite Gerät dient gleich zweifach: als Spieler mit eigenen,
    # vom ersten Gerät klar unterscheidbaren Ereignissen (keine einzige Antwort, dafür
    # die Motivations-Ereignisse) für die Spieler-Auswahl (Elternwunsch
    # 03.09.2026), und — als ignoriertes Gerät — für die Testgerät-Kennzeichnung.
    SP.ignoriert_setzen("22bb33cc44dd55ee", True)

    dienst = HttpsDienst(PORT, tele)
    try:
        if not dienst.start():
            sys.exit("HTTPS-Dienst startet nicht")
        add("Die Elternanmeldung klappt mit dem Test-Passwort", dienst.anmelden())

        t0 = time.time()
        seite = dienst.get("/eltern").text
        dauer = time.time() - t0
        add("Die Seite lädt bei 90 Tagen Daten unter 1 Sekunde", dauer < 1.0,
            f"{dauer*1000:.0f} ms für {len(viele)} Antworten")

        # --------------------------------------- Spieler-Auswahl (Elternwunsch 03.09.2026)
        # Zwei Geräte mit klar unterscheidbaren Ereignissen: Alex (00aa11bb…,
        # 2700 Antworten, keine Motivations-Ereignisse) gegen das zweite,
        # ignorierte Gerät (22bb33cc…, keine einzige Antwort, dafür die
        # Motivations-Ereignisse von oben).
        kind_kpi = f'>{len(viele)}</b>'
        seite_b = dienst.get("/eltern?spieler=22bb33cc44dd55ee").text
        seite_a = dienst.get("/eltern?spieler=00aa11bb22cc33dd").text
        r_unbekannt = dienst.get("/eltern?spieler=nichtvorhanden999")
        status_unbekannt, seite_unbekannt = r_unbekannt.status, r_unbekannt.text

        add("(1) Die Auswahl erscheint und listet Geräte mit Namen bzw. Kennung",
            '<select name="spieler"' in seite and 'Alex</option>' in seite
            and '22bb33cc… · Testgerät</option>' in seite)
        add("(2) ?spieler=B zeigt Bs Zahlen und nicht die von A",
            kind_kpi not in seite_b and "0/0-Sitzungen" in seite_b
            and kind_kpi in seite_a and "0/0-Sitzungen" not in seite_a)
        add("(3) Ohne Parameter gewinnt das zählende Gerät mit den meisten Antworten",
            kind_kpi in seite and seite_a == seite)
        add("(4) Ein Testgerät ist wählbar und als solches gekennzeichnet",
            '22bb33cc… · Testgerät</option>' in seite
            and "Testgerät ausgeblendet" in seite_b)
        add("(5) Ein ungültiger spieler-Parameter fällt still auf die Voreinstellung zurück",
            status_unbekannt == 200 and kind_kpi in seite_unbekannt)

        add("Alle Fertigkeiten stehen auf der Seite",
            all(s["title"] in seite for s in C.SKILLS),
            next((s["title"] for s in C.SKILLS if s["title"] not in seite), ""))
        # Weltnamen wie „Plus & Minus“ stehen im HTML als &amp; — richtig so
        add("Jede Welt hat einen Abschnitt",
            all(E.esc(a["title"]) in seite for a in C.AREAS),
            next((a["title"] for a in C.AREAS if E.esc(a["title"]) not in seite), ""))
        for z, text in A.ZUSTAND_TEXT.items():
            add(f'Der Zustand „{text}“ wird benannt', text in seite)
        add("Die Definition von „sitzt“ steht dabei", A.DEFINITION["sitzt"] in seite)
        add("Die Definition von „hakt“ steht dabei", A.DEFINITION["hakt"] in seite)
        add("Das Zielband wird erklärt", "70 bis 85 % richtig" in seite)
        add("Die Vorratslücke wird beziffert",
            "Fertigkeiten ohne ein einziges Paket" in seite)
        add("Die Seite verweist auf ihre eigenen Schwellen", "ZIELE.md" in seite)
        add("Ein Gerät mit Spielername wird namentlich angezeigt",
            "Alex (00aa11bb…)" in seite)

        # ------------------------------------------- D6: "Wie es ihm damit geht"
        add("Der neue Abschnitt 'Wie es ihm damit geht' erscheint",
            "Wie es ihm damit geht" in seite)
        add("Er steht nach 'Kurz gesagt'",
            seite.find("Kurz gesagt") < seite.find("Wie es ihm damit geht"))
        add("Die Wochenmenge wird in ganzen Sätzen genannt",
            "Aufgaben je Woche gerechnet" in seite)
        # Alex’ Gerät (die Standardansicht) hat selbst keine Motivations-Ereignisse
        # — die liegen auf dem zweiten Gerät, geprüft über dessen eigene Ansicht
        # (?spieler=…), denn seit dem spielerspezifischen Umbau (03.09.2026)
        # wertet jede Ansicht nur noch ihr gewähltes Gerät aus.
        add("Die Sofort-Abbrüche (0/0-Sitzungen) werden genannt",
            "0/0-Sitzungen" in seite_b)
        add("Die Abbruchgründe erscheinen im Klartext dessen, was angetippt wurde",
            "zu schwer" in seite_b and "zu langweilig" in seite_b
            and titel_hakt in seite_b)
        add("Die Spaß-Verteilung wird genannt",
            "super" in seite_b and "ging so" in seite_b and "nicht gut" in seite_b)
        add("Die Denkschule-Tabelle mit Antworten und Trefferquote je Disziplin erscheint",
            "Die Denkschule" in seite)

        # ----------------------------- V3/G4: Denk-Check und Elternbogen (live)
        # Ein eigenes Gerät mit Denk-Check-Ergebnissen. Es kommt erst jetzt
        # dazu, damit die Spieler-Auswahl oben unberührt bleibt.
        dc_dev, dc_t = "dc00dc00dc00dc00", jetzt - 3600000
        dc_ev = [
            {"i": 1, "t": jetzt - 100 * tag, "s": "chk0", "e": "c", "k": "strukturen",
             "g": 4, "n": 4, "c": 2, "ms": 9000, "z": 0},          # früherer Check
            {"i": 2, "t": dc_t, "s": "chk1", "e": "c", "k": "strukturen",
             "g": 5.5, "n": 4, "c": 3, "ms": 7400, "z": 0},
            {"i": 3, "t": dc_t, "s": "chk1", "e": "c", "k": "schlussketten",
             "g": 8.5, "n": 4, "c": 4, "ms": 9000, "z": 1},       # Decke nicht erreicht
            {"i": 4, "t": dc_t, "s": "chk1", "e": "c", "k": "raum",
             "g": 1.5, "n": 4, "c": 1, "ms": 12000, "z": -1},     # unter dem Start
        ]
        # zehn Fehlversuche im Denk-Check: dürfen keiner Fertigkeit etwas antun
        for q in range(10):
            dc_ev.append({"i": 10 + q, "t": dc_t - 60000 * (10 - q), "s": "chk1", "e": "a",
                          "u": "denkcheck", "k": ids[0], "g": 6, "y": "bildwahl", "o": 0,
                          "ms": 6000, "r": 0, "h": 0})
        SP.schreibe(dc_dev, dc_ev, {"answers": 10}, jetzt)
        ev_dc = SP.ereignisse_von(dc_dev)

        def titel_der(k):
            try:
                d = _json.loads((ROOT / "data" / "denkcheck.json").read_text("utf-8"))
                return d["dimensionen"][k]["titel"]
            except (OSError, ValueError, KeyError, TypeError):
                return k            # ohne Aufgabenbank steht der Schlüssel da

        seite_dc = dienst.get(f"/eltern?spieler={dc_dev}").text
        nach = lambda a, b: a in seite_dc and b in seite_dc and seite_dc.find(a) < seite_dc.find(b)
        add("(G4) Der Abschnitt Denk-Check steht mit Anker nach dem Fazit",
            nach("Kurz gesagt", '<h2 id="denkcheck">Denk-Check</h2>'))
        add("(G4) Jede Dimension mit Ergebnis trägt ihren Titel",
            all(E.esc(titel_der(k)) in seite_dc for k in ("strukturen", "schlussketten", "raum")),
            ", ".join(titel_der(k) for k in ("strukturen", "schlussketten", "raum")))
        s5, s6 = C.STAGES[5]["name"], C.STAGES[6]["name"]
        add("(G4) Die Stufe steht mit Namen aus dem Lehrplan, eine halbe Stufe als „zwischen“",
            f"Stufe 5,5 — zwischen „{E.esc(s5)}“ und „{E.esc(s6)}“" in seite_dc
            and f"Stufe 8,5 — {C.STAGES[8]['name']}" in seite_dc)
        add("(G4) Der Balken hat die Skala 1–8", "Skala von 1 bis 8" in seite_dc
            and 'style="width:68.8%"' in seite_dc)
        add("(G4) „c von n richtig“ und die Median-Sekunden stehen da",
            "3 von 4 richtig" in seite_dc and "Median 7,4 s" in seite_dc)
        add("(G4) Die Vermerke „Decke nicht erreicht“ und „unter dem Start“ erscheinen",
            "Decke nicht erreicht" in seite_dc and "unter dem Start" in seite_dc)
        add("(G4) Raumvorstellung trägt den Zusatz zum Interessenwert",
            "(Interessenwert — trennt laut Forschung kaum)" in seite_dc)
        dc_datum = E.datum(dc_t)
        add("(G4) Das Datum des Ergebnisses steht da", dc_datum in seite_dc, dc_datum)
        ab = datetime.fromtimestamp(dc_t / 1000) + timedelta(days=90)
        add("(G4) Der nächste Check wird ab letztem Check + 90 Tage vorgeschlagen",
            f"Nächster Check sinnvoll ab {ab.strftime('%d.%m.%Y')}." in seite_dc,
            ab.strftime("%d.%m.%Y"))
        add("(G4) Der frühere Check steht im Verlauf", "früher: 4 (" in seite_dc)
        hinweis = ("Der Denk-Check ist kein IQ-Test und vergleicht nicht mit anderen Kindern. "
                   "Er zeigt, wo dein Kind im Verhältnis zu sich selbst stark ist, und legt die "
                   "Startstufen fest. Aussagekräftig wird das Bild erst zusammen mit dem, was "
                   "beim normalen Spielen über Wochen herauskommt.")
        add("(G4) Der Hinweis „kein IQ-Test“ steht wörtlich darunter", hinweis in seite_dc)
        ohne = ("Noch kein Denk-Check gemacht — das Kind startet ihn in der App auf der "
                "Startseite.")
        add("(G4) Ohne Ergebnis: ein Satz statt leerer Tabelle, der Hinweis bleibt, kein Termin",
            ohne in seite_a and hinweis in seite_a and "Nächster Check" not in seite_a
            and ohne not in seite_dc)

        # Die zehn Fehlversuche haben der Statistik nichts getan
        kontrolle = [dict(e, u=f'{ids[0]}@6') if e.get("u") == "denkcheck" else e for e in ev_dc]
        add("(G4) Denk-Check-Antworten zählen in keiner Fertigkeiten-Statistik mit",
            all(f["n"] == 0 for f in A.fertigkeiten(ev_dc))
            and A.alle_antworten(ev_dc) == [] and A.typenmischung(ev_dc) == []
            and A.uebungstage(ev_dc) == [] and A.aktuelle_stufe(ev_dc) == 1
            and A.ueberblick(ev_dc)["antworten"] == 0)
        add("(G4) … und das nicht, weil der Test nichts sähe: ohne die Marke zählen sie",
            next(f for f in A.fertigkeiten(kontrolle) if f["id"] == ids[0])["n"] == 10
            and A.ueberblick(kontrolle)["antworten"] == 10)
        add("(G4) Die Seite des Geräts meldet 0 gerechnete Aufgaben",
            "hat 0 Aufgaben gerechnet" in seite_dc)

        p = A.denkcheck_profil(ev_dc)
        st = p["dimensionen"].get("strukturen", {})
        add("(G4) denkcheck_profil: jüngstes Ergebnis je Dimension samt Verlauf",
            set(p["dimensionen"]) == {"strukturen", "schlussketten", "raum"}
            and st.get("schaetzung") == 5.5 and (st.get("n"), st.get("c"), st.get("ms"), st.get("z"))
            == (4, 3, 7400, 0) and [v["schaetzung"] for v in st.get("verlauf", [])] == [4]
            and p["dimensionen"]["raum"]["z"] == -1 and p["dimensionen"]["schlussketten"]["z"] == 1,
            str(st)[:80])
        add("(G4) denkcheck_profil: Datum des letzten Checks; pro Gerät, ohne Ergebnis leer",
            p["letzter"] == dc_t and p["letzter_datum"] == datetime.fromtimestamp(dc_t / 1000).date().isoformat()
            and A.denkcheck_profil(SP.ereignisse_von("00aa11bb22cc33dd"))["dimensionen"] == {}
            and A.denkcheck_profil([])["letzter"] == 0)

        # Die Ablage lässt von einem "c"-Ereignis nur zu, was dazugehört
        roh = {"e": "c", "i": 1, "t": 1, "s": "x", "k": "raum", "g": 5.5, "n": 4, "c": 2,
               "ms": 100, "z": 1, "name": "Alex", "u": "denkcheck"}
        sa = SP.saeubere(roh)
        add("(G4) Ereignis „c“: Kommazahl bleibt, fremde Felder fallen weg",
            sa == {"e": "c", "i": 1, "t": 1, "s": "x", "k": "raum", "g": 5.5, "n": 4, "c": 2,
                   "ms": 100, "z": 1})
        add("(G4) Ereignis „c“: z außerhalb von −1/0/1 wird verworfen",
            "z" not in SP.saeubere(dict(roh, z=2)) and SP.saeubere(dict(roh, z=-1))["z"] == -1)

        # ---------------------------------------------------- Elternbogen
        werte_1 = {k: (i % 4) + 1 for i, k in enumerate(SP.BOGEN_SCHLUESSEL)}
        r = dienst.formular("/elternbogen", {"dev": dc_dev, **{k: str(v) for k, v in werte_1.items()}})
        bogen_datei = tele / "elternbogen.json"
        gespeichert = _json.loads(bogen_datei.read_text("utf-8")) if bogen_datei.exists() else []
        add("(G4) Elternbogen: Speichern antwortet 303 zurück zum gewählten Kind",
            r.status == 303 and r.header.get("Location") == f"/eltern?spieler={dc_dev}#elternbogen",
            f'{r.status} {r.header.get("Location")}')
        add("(G4) Elternbogen: elternbogen.json trägt t, dev und die neun Werte",
            len(gespeichert) == 1 and gespeichert[0]["dev"] == dc_dev
            and gespeichert[0]["werte"] == werte_1 and abs(gespeichert[0]["t"] - jetzt) < 60000,
            str(gespeichert)[:60])
        seite_bogen = dienst.get(f"/eltern?spieler={dc_dev}").text
        add("(G4) Elternbogen: letzter Bogen mit Datum und allen neun Aussagen",
            'id="elternbogen"' in seite_bogen
            and f"Letzter Bogen vom {E.datum(gespeichert[0]['t'])}" in seite_bogen
            and all(E.esc(t) in seite_bogen for _, t in SP.ELTERNBOGEN))
        add("(G4) Elternbogen: das Formular ist mit den letzten Werten vorausgefüllt",
            all(f'name="{k}" value="{v}" required checked' in seite_bogen for k, v in werte_1.items())
            and seite_bogen.count(" checked") == 9)
        add("(G4) Elternbogen: das Formular trägt Gerät und CSRF-Token",
            re.search(r'<form method="post" action="/elternbogen"><input type="hidden" '
                      r'name="csrf" value="[^"]+">\s*<input type="hidden" name="dev" '
                      + f'value="{dc_dev}">', seite_bogen) is not None)
        add("(G4) Elternbogen: ein anderes Gerät hat keinen Bogen",
            "Noch kein Bogen ausgefüllt." in dienst.get("/eltern?spieler=00aa11bb22cc33dd").text)

        voll = {k: str(v) for k, v in werte_1.items()}
        schlecht = {
            "Wert 5": dict(voll, knobeln="5"),
            "Wert 0": dict(voll, knobeln="0"),
            "Wert kein Zahl": dict(voll, ideen="abc"),
            "Wert 3,5": dict(voll, ideen="3.5"),
            "Wert mit Zeilenumbruch": dict(voll, ideen="3\n"),
            "ein Schlüssel fehlt": {k: v for k, v in voll.items() if k != "merken"},
            "ein Schlüssel zu viel": dict(voll, extra="1"),
            "falsches Gerät": dict(voll, dev="../../etc/passwd"),
        }
        for was, felder in schlecht.items():
            felder = dict({"dev": dc_dev}, **felder)
            rr = dienst.formular("/elternbogen", felder)
            add(f"(G4) Elternbogen: ungültig ({was}) → 400", rr.status == 400, str(rr.status))
        rr = dienst.formular("/elternbogen", list({"dev": dc_dev, **voll}.items()) + [("knobeln", "2")])
        add("(G4) Elternbogen: ein Wert doppelt → 400", rr.status == 400, str(rr.status))
        add("(G4) Elternbogen: nach all dem Ungültigen liegt weiter genau ein Bogen",
            len(_json.loads(bogen_datei.read_text("utf-8"))) == 1)

        werte_2 = {k: 4 - (i % 4) for i, k in enumerate(SP.BOGEN_SCHLUESSEL)}
        dienst.formular("/elternbogen", {"dev": dc_dev, **{k: str(v) for k, v in werte_2.items()}})
        seite_bogen2 = dienst.get(f"/eltern?spieler={dc_dev}").text
        add("(G4) Elternbogen: ein zweiter Bogen ersetzt die Anzeige, der erste bleibt im Verlauf",
            all(f'name="{k}" value="{v}" required checked' in seite_bogen2 for k, v in werte_2.items())
            and [b["werte"] for b in SP.elternbogen_lesen(dc_dev)] == [werte_1, werte_2])
        for q in range(55):
            SP.elternbogen_speichern("ba5eba11ba5eba11", werte_1, jetzt + q)
        add("(G4) Elternbogen: höchstens 50 je Gerät, andere Geräte bleiben unberührt",
            len(SP.elternbogen_lesen("ba5eba11ba5eba11")) == 50
            and SP.elternbogen_lesen("ba5eba11ba5eba11")[0]["t"] == jetzt + 5
            and len(SP.elternbogen_lesen(dc_dev)) == 2)
        add("(G4) Elternbogen: unbrauchbare Werte und Geräte wirft die Ablage selbst ab",
            _wirft(lambda: SP.elternbogen_speichern("../x", werte_1, 1))
            and _wirft(lambda: SP.elternbogen_speichern(dc_dev, dict(werte_1, knobeln=True), 1))
            and _wirft(lambda: SP.elternbogen_speichern(dc_dev, dict(werte_1, knobeln=7), 1))
            and _wirft(lambda: SP.elternbogen_speichern(dc_dev, {"knobeln": 1}, 1)))

        bild = os.environ.get("ELTERN_BILD")
        if bild:
            _bildschirmfoto(dienst, f"/eltern?spieler={dc_dev}", bild)

        # Leerer Zustand darf nicht nach 0 % aussehen
        leer = Path(tempfile.mkdtemp(prefix="mathcraft_leer_"))
        alt = SP.TELE
        SP.TELE = leer
        SP._cache["stand"] = None
        A.SP.TELE = leer
        # lehrer.py wird hier zum ersten Mal in diesem Prozess importiert
        # (durch _tutor()) und läse sonst den echten Tutorplan des Projekts
        # ein — mit seinen eigenen, ganz realen Prozentzahlen im Text.
        os.environ["MC_PLAN"] = str(leer / "tutorplan.json")
        s_leer = E.seite()
        add("Ohne Daten steht das da, statt überall 0 %",
            "Noch sind keine Daten angekommen" in s_leer and "0 %" not in s_leer)

        # D6: auch im Leerzustand erscheint der Abschnitt — ehrlich, ohne
        # leere Tabelle oder falsche Null.
        add("'Wie es ihm damit geht' erscheint auch ohne jede Daten",
            "Wie es ihm damit geht" in s_leer)
        add("Zur Wochenmenge steht ein ehrlicher Satz statt einer Zahl",
            "Zur Wochenmenge liegen noch keine Angaben vor." in s_leer)
        add("Zu Sofort-Abbrüchen steht ein ehrlicher Satz",
            "Zu Sofort-Abbrüchen liegen noch keine Angaben vor." in s_leer)
        add("Zu Abbruchgründen steht ein ehrlicher Satz",
            "Abbruchgründe hat er noch keine genannt." in s_leer)
        add("Zum Spaß-Signal steht ein ehrlicher Satz",
            "Zum Spaß-Signal liegen noch keine Angaben vor." in s_leer)
        add("Die Denkschule-Tabelle bleibt im Leerzustand keine leere Tabelle,"
            " sondern ein ehrlicher Satz",
            "Zur Denkschule liegen noch keine Angaben vor." in s_leer and "<table>" not in
            s_leer[s_leer.find("Die Denkschule"):s_leer.find("Die Denkschule")+600])

        # --------------------------------------------- D: Status je Planposten
        # V0/ZIELE-V2.md: die Elternseite muss je Planposten sagen, ob er
        # gestellt wurde, verweigert wird, noch nicht dran war oder gar nicht
        # mehr stellbar ist — sonst bleibt unsichtbar, dass ein Plan wirkungslos
        # verpufft (genau das ist dem Plan vom 26.08. passiert).
        units_roh = _json.loads((ROOT / "data" / "units_seed.json").read_text("utf-8"))["units"]
        je_fertigkeit = {}
        for un in units_roh:
            je_fertigkeit.setdefault(un["skill"], []).append(f'{un["skill"]}@{un["stage"]}')
        unversorgt = [s["id"] for s in A.vorratsdeckung()["liste"]]
        kandidaten = [i for i in ids if i in je_fertigkeit]
        sk_gestellt, sk_verweigert, sk_dran = kandidaten[0], kandidaten[1], kandidaten[2]
        sk_keins = unversorgt[0] if unversorgt else kandidaten[3]

        planzeit = jetzt - 5 * 3600000
        d_tele = Path(tempfile.mkdtemp(prefix="mathcraft_status_"))
        SP.TELE = d_tele
        SP._cache["stand"] = None
        A.SP.TELE = d_tele

        d_ev, nr3 = [], 1
        d_ev.append(antwort(nr3, sk_gestellt, 1, True, planzeit + 60000)); nr3 += 1
        unit_verweigert = je_fertigkeit[sk_verweigert][0]
        for k in range(2):
            d_ev.append({"i": nr3, "t": planzeit + 60000 * (k + 1), "s": "d3v1x", "e": "s",
                         "q": "unit", "u": unit_verweigert, "n": 0, "c": 0, "ms": 500, "z": 1})
            nr3 += 1
        offen_ids = je_fertigkeit.get(sk_dran, []) + je_fertigkeit.get(sk_verweigert, [])
        SP.schreibe("ff001122334455aa", d_ev, {"answers": len(d_ev), "offen": offen_ids}, jetzt)

        # dieselbe Datei, auf die MC_PLAN weiter oben schon isoliert wurde
        (leer / "tutorplan.json").write_text(_json.dumps({
            "t": planzeit, "datum": "01.09.2026 00:00",
            "beobachtung": "Testbeobachtung.", "eltern": "Testabsatz.",
            "plan": [
                {"skill": sk_gestellt, "art": "vor", "grund": "Testgrund"},
                {"skill": sk_verweigert, "art": "vor", "grund": "Testgrund"},
                {"skill": sk_dran, "art": "vor", "grund": "Testgrund"},
                {"skill": sk_keins, "art": "vor", "grund": "Testgrund"},
            ],
            "erzeugen": [], "grundlage": {"antworten": 10, "ereignisse": 10},
            "kosten": {}, "hinweise": [],
        }, ensure_ascii=False), "utf-8")

        # dieselben Wünsche-Zustände, dieselben Sofort-Abbrüche
        SP.wunsch_setzen("skill", sk_gestellt, "jetzt", planzeit)
        SP.wunsch_erfuellen("skill", sk_gestellt, planzeit, jetzt)
        SP.wunsch_setzen("skill", sk_verweigert, "jetzt", planzeit)
        SP.wunsch_setzen("skill", sk_dran, "jetzt", planzeit)

        seite_status = E.seite()
        add("(D) Ein gestellter Planposten wird als solcher erkannt",
            "seit diesem Plan: gestellt" in seite_status)
        add("(D) Eine Verweigerung wird erkannt",
            "seit diesem Plan: verweigert" in seite_status)
        add("(D) Ein noch nicht gestellter Planposten wird erkannt",
            "seit diesem Plan: noch nicht dran" in seite_status)
        add("(D) Ein nicht stellbarer Planposten wird erkannt",
            "nicht stellbar — kein offenes Paket" in seite_status)
        add("(D) Ein erfüllter Wunsch zeigt sein Erfüllungsdatum",
            "erfüllt am " in seite_status)
        add("(D) Ein verweigerter Wunsch wird als solcher erkannt",
            "wird verweigert (" in seite_status and "weggetippt" in seite_status)
        add("(D) Ein wirkender Wunsch wird als solcher erkannt",
            "wirkt</span>" in seite_status)


        # --------------------------------------------------- G5: Wunsch-Bremse
        # Zwei Sofort-Abbrüche genügen für „verweigert“, aber noch nicht für den
        # Hinweis auf der Elternseite; ab dem dritten kommt er, neben dem ✕.
        add("(G5) Bei zwei Sofort-Abbrüchen noch kein Hinweis zum Zurücknehmen",
            "🛑" not in seite_status)
        SP.schreibe("ff001122334455aa",
                    [{"i": nr3, "t": planzeit + 60000 * 3, "s": "d3v1x", "e": "s", "q": "unit",
                      "u": unit_verweigert, "n": 0, "c": 0, "ms": 500, "z": 1}],
                    {"answers": len(d_ev)}, jetzt)
        seite_bremse = E.seite()
        text_bremse = ("🛑 Seit deinem Wunsch 3-mal sofort weggetippt. Die App pausiert das "
                       "Paket inzwischen immer länger. Vielleicht den Wunsch zurücknehmen?")
        add("(G5) Ab drei Sofort-Abbrüchen seit dem Wunsch steht der Hinweis da",
            text_bremse in seite_bremse)
        if text_bremse in seite_bremse:
            ab_i = seite_bremse.index(text_bremse)
            zeile = seite_bremse[seite_bremse.rfind("<tr>", 0, ab_i):seite_bremse.find("</tr>", ab_i)]
            add("(G5) … in der Zeile des Wunsches, dort wo auch das Zurücknehmen steht",
                'value="weg"' in zeile and E.esc(next(
                    s["title"] for s in C.SKILLS if s["id"] == sk_verweigert)) in zeile)
        add("(G5) Der Hinweis erscheint nur einmal (nicht bei den übrigen Wünschen)",
            seite_bremse.count("🛑") == 1)
        SP.wunsch_setzen("skill", sk_verweigert, "weniger", planzeit)
        add("(G5) Bei „weniger davon“ rät die Seite nicht zum Zurücknehmen",
            "🛑" not in E.seite())
        SP.wunsch_setzen("skill", sk_verweigert, "jetzt", planzeit)
        SP.wunsch_setzen("skill", sk_verweigert, "jetzt", jetzt)   # Wunsch von heute: davor liegt nichts
        add("(G5) Gezählt wird erst ab dem Zeitpunkt des Wunsches", "🛑" not in E.seite())
        SP.wunsch_setzen("skill", sk_verweigert, "jetzt", planzeit)

        # Eine Antwort aus dem Denk-Check ist kein „gestellt“
        SP.schreibe("ff001122334455aa",
                    [{"i": nr3 + 1, "t": planzeit + 90000, "s": "chk9", "e": "a", "u": "denkcheck",
                      "k": sk_dran, "g": 5, "y": "bildwahl", "o": 1, "ms": 4000, "r": 0, "h": 0}],
                    {"answers": len(d_ev)}, jetzt)
        add("(D) Eine Antwort aus dem Denk-Check macht den Planposten nicht zu „gestellt“",
            "seit diesem Plan: noch nicht dran" in E.seite())

        SP.wunsch_loeschen("skill", sk_gestellt)
        SP.wunsch_loeschen("skill", sk_verweigert)
        SP.wunsch_loeschen("skill", sk_dran)
        shutil.rmtree(d_tele, ignore_errors=True)

        SP.TELE = alt
        SP._cache["stand"] = None
        shutil.rmtree(leer, ignore_errors=True)
    finally:
        dienst.stop()
        shutil.rmtree(tele, ignore_errors=True)

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, info in RESULTS:
        print(f'{"✅" if ok else "❌"} {name}' + (f"   ({info})" if info else ""))
    print(f"\n{len(RESULTS)-len(fails)}/{len(RESULTS)} bestanden")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
