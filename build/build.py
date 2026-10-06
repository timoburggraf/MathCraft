# -*- coding: utf-8 -*-
"""Baut die fertige, eigenständige index.html.

  .venv/bin/python build/build.py

Bindet Lernpakete, Lehrplan und Bilder direkt in die HTML ein — die Datei läuft
danach offline, ohne Server und ohne Netz.

Fehlen noch echte Illustrationen, werden schlichte Farbverläufe eingesetzt,
damit die App trotzdem vollständig spielbar und testbar ist.
"""
import base64
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum as C
import disziplinen as DZ
import validate as V

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "app.html"
DEST = ROOT / "index.html"
RAW = ROOT / "img" / "raw"
UNITS = ROOT / "data" / "units_seed.json"
# D5: die zehn Fuchs-Posen — schon fertige, freigestellte WebPs mit Alpha.
AVATAR_DIR = ROOT / "img" / "avatar_fuchs"
AVATAR_MANIFEST = AVATAR_DIR / "manifest.json"

# Breite Motive oben, quadratischere für die Weltenkarten
WIDE = {"hero", "win", "levelup"}
NEEDED = ["hero", "win", "levelup"] + C.AREA_IDS

# Farbpaare für die Platzhalter, damit sich die Welten trotzdem unterscheiden
PLACEHOLDER = {
    "hero": ("#1b2a6b", "#25d0c0"), "win": ("#2f7d4f", "#ffb238"),
    "levelup": ("#3a2a6b", "#5b8cff"),
    "zahl": ("#1b3a6b", "#4aa3ff"), "plus": ("#1b5a4b", "#25d0c0"),
    "mal": ("#5a2a5b", "#ff6ad5"), "muster": ("#4a3a7b", "#8b5cf6"),
    "geo": ("#1b4a5b", "#3ad0ff"), "logik": ("#5b3a1b", "#ffb238"),
    "komb": ("#5b1b3a", "#ff4d94"), "groess": ("#2a5b1b", "#8ad04a"),
    "daten": ("#1b2a4b", "#6a8aff"), "geheim": ("#3a1b5b", "#b45cff"),
    "sach": ("#5b4a1b", "#ffd24a"),
}


def _grad(name, w, h):
    """Schlichter Farbverlauf als Notnagel, solange Bilder fehlen."""
    from PIL import Image, ImageDraw
    a, b = PLACEHOLDER.get(name, ("#1b2a6b", "#25d0c0"))
    ca = tuple(int(a[i:i+2], 16) for i in (1, 3, 5))
    cb = tuple(int(b[i:i+2], 16) for i in (1, 3, 5))
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(ca[i] + (cb[i]-ca[i]) * t) for i in range(3)))
    return im


def encode_images():
    from PIL import Image
    out, total, fehlen = {}, 0, []
    for name in NEEDED:
        f = RAW / f"{name}.png"
        target_w, q = (1000, 72) if name in WIDE else (700, 70)
        target_h = round(target_w * (558 / 1000 if name in WIDE else 523 / 700))
        if f.exists():
            im = Image.open(f).convert("RGB")
            if im.width > target_w:
                im = im.resize((target_w, round(im.height * target_w / im.width)), Image.LANCZOS)
        else:
            fehlen.append(name)
            im = _grad(name, target_w, target_h)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=q, method=6)
        data = buf.getvalue()
        total += len(data)
        out[name] = "data:image/webp;base64," + base64.b64encode(data).decode()
    if fehlen:
        print(f"   !  {len(fehlen)} Platzhalter statt Bildern: {', '.join(fehlen)}")
    print(f"   -> {len(out)} Bilder, {total/1024/1024:.2f} MB")
    return out


def encode_avatar():
    """Bindet die Fuchs-Posen roh ein.

    Anders als encode_images() wird hier nichts neu skaliert oder erneut
    kodiert: Die WebPs unter img/avatar_fuchs/ sind schon fertig freigestellt
    (Alpha) und aufs Nötigste optimiert (zusammen ~228 KB laut Vorgabe) — ein
    erneutes Kodieren würde nur Qualität kosten, ohne etwas zu gewinnen.
    """
    if not AVATAR_MANIFEST.exists():
        print("   !  kein Fuchs-Avatar gefunden (img/avatar_fuchs/manifest.json fehlt)")
        return {}
    manifest = json.loads(AVATAR_MANIFEST.read_text("utf-8"))
    out, total = {}, 0
    for pose, info in manifest.get("posen", {}).items():
        data = (AVATAR_DIR / info["datei"]).read_bytes()
        total += len(data)
        out[pose] = "data:image/webp;base64," + base64.b64encode(data).decode()
    print(f"   -> {len(out)} Fuchs-Posen, {total/1024:.1f} KB")
    return out


def rev_von(tasks):
    """D6.2: kurze Fassungskennung (8 Hex-Zeichen) über den Inhalt der Aufgaben
    eines Pakets — ein Hash über deren JSON-Form. Ändert sich auch nur eine
    Aufgabe, ändert sich die rev; die App erkennt daran ein inhaltlich
    ersetztes Paket und setzt dessen Sterne zurück (siehe pruefeRevisionen()
    in src/app.html). Absichtlich nur über "tasks", nicht über das ganze
    Paket: Titel oder Einleitung zu ändern ist keine inhaltliche Ersetzung.
    """
    material = json.dumps(tasks, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:8]


def app_data():
    """Was die App vom Lehrplan wissen muss — schlank gehalten."""
    units = []
    if UNITS.exists():
        units = json.loads(UNITS.read_text("utf-8")).get("units", [])

    good, bad = V.filter_units(units, verbose=False)
    if bad:
        print(f"   !  {len(bad)} Pakete sind fehlerhaft und kommen NICHT in die App:")
        for u, problems in bad[:5]:
            print(f'      {u.get("skill","?")}: {problems[0][:80]}')

    for u in good:
        u["rev"] = rev_von(u.get("tasks") or [])

    return {
        "areas":  [{k: a[k] for k in ("id", "emoji", "title", "sub")} for a in C.AREAS],
        "skills": [{k: s[k] for k in ("id", "area", "stage", "title")} for s in C.SKILLS],
        "worlds": [{k: w[k] for k in ("id", "title")} for w in C.WORLDS],
        "stages": {str(k): v["name"] for k, v in C.STAGES.items()},
        # Klassenstufen für die Einstellung „In welche Klasse geht das Kind?“.
        # Die Zuordnung Klasse -> Einstiegsstufe steht in build/curriculum.py und
        # nur dort; die App bekommt sie fertig geliefert, damit Lehrplan und
        # Oberfläche nicht auseinanderlaufen können.
        "klassen": [{"k": k, "einstieg": v["einstieg"],
                     "name": C.STAGES[v["einstieg"]]["name"]}
                    for k, v in sorted(C.KLASSEN.items())],
        "units":  good,
    }, len(good), len(bad)


def disziplinen_data():
    """D1: die fünf Denkdisziplinen für die Denkschule-Kartenansicht — Schlüssel,
    Titel, Beschreibung und Skill-Liste je Disziplin, dazu die Liste der
    restlichen Pre-Lesson-Fertigkeiten. Analog zum Avatar-Muster (encode_avatar())
    wird hier nur eingebettet, nicht neu berechnet: build/disziplinen.py bleibt
    die einzige Quelle der Wahrheit, die App bekommt bloß ihre Daten.
    """
    return {
        "disziplinen": {
            key: {"titel": angaben["titel"], "beschreibung": angaben["beschreibung"],
                  "skills": list(angaben["skills"])}
            for key, angaben in DZ.DISZIPLINEN.items()
        },
        "preLesson": list(DZ.PRE_LESSON_SKILLS),
    }


def lan_ip():
    """Adresse, unter der das Handy diesen Rechner im WLAN erreicht.

    Wird als Voreinstellung für den Update-Dienst eingebaut, damit niemand sie
    von Hand abtippen muss. In den Einstellungen bleibt sie änderbar.
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.1.1", 1))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


def build_info():
    """Fassung aus dem Android-Projekt plus voreingestellte Serveradresse."""
    code, name = 0, "Entwicklung"
    gradle = ROOT / "android" / "app" / "build.gradle"
    if gradle.exists():
        t = gradle.read_text("utf-8")
        m = re.search(r"versionCode\s+(\d+)", t)
        n = re.search(r'versionName\s+"([^"]+)"', t)
        # Beim Bauen wird der Code gleich hochgezählt; die APK, die daraus
        # entsteht, traegt also genau diese Nummer.
        if m:
            code = int(m.group(1))
        if n:
            name = n.group(1)
    # MC_SERVER aus Umgebung oder .env schlaegt die selbst erkannte Adresse;
    # ohne beides bleibt das Feld leer und die App fragt in den Einstellungen.
    sys.path.insert(0, str(ROOT))
    import konfig
    server = konfig.wert("MC_SERVER") or (f"https://{lan_ip()}:8792" if lan_ip() else "")
    if server:
        from urllib.parse import urlsplit, urlunsplit
        endpoint = urlsplit(server if "://" in server else "https://" + server)
        port = 8792 if endpoint.port == 8790 else endpoint.port
        server = urlunsplit(("https", endpoint.hostname + (f":{port}" if port else ""), "", "", ""))
    return {"code": code, "name": name, "server": server}


def pruefe_webview_zugang():
    """Prüft sichere Android-Herkunft, Klartextsperre und den öffentlichen CA-Anker.

    Private Funktionen benötigen verifiziertes HTTPS. Datei-Browser-Tests
    bilden Androids Netzrichtlinie nicht ab; deshalb wird sie beim Build geprüft.
    """
    cfg = ROOT / "capacitor.config.json"
    if not cfg.exists():
        return
    try:
        c = json.loads(cfg.read_text("utf-8"))
    except ValueError as e:
        raise SystemExit(f"capacitor.config.json ist nicht lesbar: {e}")

    schema = (c.get("server") or {}).get("androidScheme", "https")   # Capacitors Vorgabe
    gemischt = (c.get("android") or {}).get("allowMixedContent", False)
    if schema != "https" or gemischt:
        raise SystemExit(
            "MathCraft verwendet HTTPS. Die bestehende Android-Herkunft https://localhost "
            "muss erhalten und allowMixedContent muss ausgeschaltet bleiben.")
    manifest = (ROOT / "android/app/src/main/AndroidManifest.xml").read_text()
    if 'android:networkSecurityConfig="@xml/network_security_config"' not in manifest or 'android:usesCleartextTraffic="false"' not in manifest:
        raise SystemExit("Androids begrenzter CA-Trust und Klartextsperre fehlen.")
    cert = ROOT / "android/app/src/main/res/raw/mathcraft_local_ca.crt"
    if not cert.is_file() or "BEGIN CERTIFICATE" not in cert.read_text():
        raise SystemExit("Der öffentliche MathCraft-CA-Trust muss vor dem Android-Bau vorliegen.")


def main():
    pruefe_webview_zugang()
    data, n_good, n_bad = app_data()
    n_tasks = sum(len(u["tasks"]) for u in data["units"])
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    info = build_info()

    print("Bilder:")
    images = json.dumps(encode_images(), separators=(",", ":"))

    print("Fuchs-Avatar:")
    avatar = json.dumps(encode_avatar(), separators=(",", ":"))

    disziplinen = json.dumps(disziplinen_data(), ensure_ascii=False, separators=(",", ":"))
    print(f"Denkdisziplinen:\n   -> {len(DZ.DISZIPLINEN)} Disziplinen, "
          f"{len(DZ.PRE_LESSON_SKILLS)} Pre-Lesson-Fertigkeiten, {len(disziplinen)/1024:.1f} KB")

    html = SRC.read_text("utf-8")
    for marker, value in (("/*__DATA__*/null", payload), ("/*__IMG__*/{}", images),
                          ("/*__AVATAR__*/{}", avatar),
                          ("/*__DISZIPLINEN__*/{disziplinen:{}, preLesson:[]}", disziplinen),
                          ("/*__BUILD__*/{code:0, name:\"Entwicklung\", server:\"\"}",
                           json.dumps(info, ensure_ascii=False))):
        if marker not in html:
            raise SystemExit(f"Platzhalter fehlt in app.html: {marker}")
        html = html.replace(marker, value, 1)

    DEST.write_text(html, "utf-8")
    print(f"\n{DEST}")
    print(f"  {n_good} Pakete · {n_tasks} Aufgaben · {len(C.AREAS)} Welten · "
          f"{DEST.stat().st_size/1024/1024:.2f} MB"
          + (f"  ({n_bad} fehlerhafte Pakete ausgelassen)" if n_bad else ""))
    print(f"  Fassung {info['name']} (Nr. {info['code']})"
          + (f" · Update-Dienst {info['server']}" if info["server"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
