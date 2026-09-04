# -*- coding: utf-8 -*-
"""Der Fundus — nichts Erzeugtes wird vernichtet, nur abgelegt.

Jedes Aufgabenpaket, jedes Bild und jede Tonspur hat Rechenzeit, Geld und oft
mehrere Anläufe gekostet. Wenn etwas ersetzt wird, ist die alte Fassung
deswegen nicht wertlos: Sie kann besser gewesen sein als die neue, sie kann zu
einem anderen Kind passen, und sie ist der einzige Beleg dafür, was ein Kind
damals tatsächlich vor sich hatte.

Deshalb überschreibt in diesem Projekt nichts etwas Erzeugtes, ohne die
Vorgängerfassung vorher hierher zu legen:

    fundus/pakete/<fertigkeit>@<stufe>/<zeitstempel>.json
    fundus/bilder/<name>/<zeitstempel>.png

Die Vorlesestimmen brauchen keinen Eintrag: ihr Dateiname ist der crc32 des
gesprochenen Textes (data/audio/<stimme>/<id>.opus). Ein geänderter Text
bekommt damit einen neuen Namen, statt den alten zu überschreiben — die
Sammlung ist von sich aus ein Fundus und verliert nie eine Aufnahme.

Zurückholen geht von Hand: Die Datei aus dem Fundus in data/units_seed.json
bzw. img/raw/ zurückkopieren. Absichtlich kein Automatismus — wer eine alte
Fassung zurückholt, soll sie vorher angesehen haben.
"""
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNDUS = ROOT / "fundus"
PAKETE = FUNDUS / "pakete"
BILDER = FUNDUS / "bilder"


def _stempel():
    """Sortierbar und ohne Zeichen, die einem Dateisystem wehtun."""
    return time.strftime("%Y%m%d-%H%M%S")


def lege_paket_ab(unit):
    """Ein Aufgabenpaket ablegen, bevor es ersetzt wird.

    Rückgabe: der Ablageort, oder None, wenn nichts abzulegen war. Ein Fehler
    beim Ablegen darf den Lauf nicht abbrechen — lieber ein Paket weniger im
    Fundus als ein abgebrochener Erzeugungslauf, der Geld gekostet hat.
    """
    if not isinstance(unit, dict) or not unit.get("skill"):
        return None
    ordner = PAKETE / f'{unit["skill"]}@{unit.get("stage", 0)}'
    try:
        ordner.mkdir(parents=True, exist_ok=True)
        ziel = ordner / f"{_stempel()}.json"
        # Gleiche Sekunde, gleiche Fertigkeit: durchnummerieren statt überschreiben.
        n = 2
        while ziel.exists():
            ziel = ordner / f"{_stempel()}-{n}.json"
            n += 1
        ziel.write_text(json.dumps(unit, ensure_ascii=False, indent=1), "utf-8")
        return ziel
    except OSError as e:
        print(f"   !  Fundus: {unit.get('skill')} nicht abgelegt ({e})")
        return None


def lege_datei_ab(pfad, sparte="bilder"):
    """Eine Datei ablegen, bevor sie überschrieben wird (Bilder, Beliebiges).

    Kopiert statt zu verschieben: Scheitert die Neuerzeugung danach, steht das
    Original noch an seinem Platz. Rückgabe wie oben.
    """
    pfad = Path(pfad)
    if not pfad.exists():
        return None
    ordner = (FUNDUS / sparte / pfad.stem)
    try:
        ordner.mkdir(parents=True, exist_ok=True)
        ziel = ordner / f"{_stempel()}{pfad.suffix}"
        n = 2
        while ziel.exists():
            ziel = ordner / f"{_stempel()}-{n}{pfad.suffix}"
            n += 1
        shutil.copy2(pfad, ziel)
        return ziel
    except OSError as e:
        print(f"   !  Fundus: {pfad.name} nicht abgelegt ({e})")
        return None


def bestand():
    """Was im Fundus liegt — (Pakete, Bilder, Bytes)."""
    pakete = len(list(PAKETE.rglob("*.json"))) if PAKETE.exists() else 0
    bilder = len([p for p in BILDER.rglob("*") if p.is_file()]) if BILDER.exists() else 0
    groesse = sum(p.stat().st_size for p in FUNDUS.rglob("*") if p.is_file()) \
        if FUNDUS.exists() else 0
    return pakete, bilder, groesse


if __name__ == "__main__":
    p, b, g = bestand()
    print(f"Fundus: {FUNDUS}")
    print(f"  {p} abgelegte Paketfassungen")
    print(f"  {b} abgelegte Bildfassungen")
    print(f"  {g/1024/1024:.1f} MB")
    print("\nDie Vorlesestimmen liegen nicht hier: data/audio/ ist über den")
    print("Dateinamen inhaltsadressiert und überschreibt nie eine Aufnahme.")
