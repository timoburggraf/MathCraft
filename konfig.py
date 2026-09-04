# -*- coding: utf-8 -*-
"""Zentrale Stelle für alles, was von Rechner zu Rechner verschieden ist.

Im Quelltext steht kein einziger Schlüssel und kein einziger Pfad, der nur auf
einem bestimmten Rechner stimmt. Beides kommt von hier — und hierher kommt es
aus zwei Quellen, in dieser Reihenfolge:

  1. der Umgebung          ANTHROPIC_API_KEY=… .venv/bin/python build/…
  2. der Datei .env        im Projektwurzelverzeichnis, Zeilen NAME=wert

Die Umgebung gewinnt, damit sich ein einzelner Lauf abweichend versorgen lässt,
ohne die Datei anzufassen. Die .env liegt in .gitignore und verlässt den
Rechner nie; welche Namen hineingehören, steht in .env.beispiel.

Verwendung:

    import konfig
    schluessel = konfig.geheim("ANTHROPIC_API_KEY")   # fehlt er, bricht es ab
    adresse    = konfig.wert("MC_SERVER", "")         # optional, mit Vorgabe

Warum der Abbruch bei einem fehlenden Schlüssel und keine leere Zeichenkette:
ein leerer Schlüssel führt sonst erst tief in der API-Bibliothek zu einem
Fehler, der nicht sagt, was der Aufrufer tun soll. geheim() sagt es.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_DATEI = ROOT / ".env"
BEISPIEL = ROOT / ".env.beispiel"

# Wozu ein Eintrag da ist und wo man ihn herbekommt. Steht in der Fehlermeldung,
# damit niemand erst die Anleitung suchen muss.
HERKUNFT = {
    "ANTHROPIC_API_KEY":
        "Zugang zu Claude — erzeugt den Lehrplan, die Aufgabenpakete und die "
        "Erklärungen. Schlüssel unter https://console.anthropic.com/settings/keys",
    "GEMINI_API_KEY":
        "Zugang zu Google Gemini — erzeugt die Illustrationen und die "
        "Vorlesestimmen. Schlüssel unter https://aistudio.google.com/apikey",
    "MC_KEYSTORE_PW":
        "Passwort des Android-Signierschlüssels (siehe MC_KEYSTORE). Wer noch "
        "keinen hat, legt ihn nach der Anleitung in README.md an.",
}

_zwischenspeicher = None


def _lade_env():
    """Die .env einlesen. Fehlt sie, ist das kein Fehler — dann zählt nur die
    Umgebung. Gelesen wird höchstens einmal je Lauf."""
    global _zwischenspeicher
    if _zwischenspeicher is not None:
        return _zwischenspeicher

    werte = {}
    if ENV_DATEI.exists():
        for nr, zeile in enumerate(ENV_DATEI.read_text("utf-8").splitlines(), 1):
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#"):
                continue
            if "=" not in zeile:
                print(f"[konfig] .env Zeile {nr} ohne '=' — übergangen: {zeile}",
                      file=sys.stderr)
                continue
            name, _, wert = zeile.partition("=")
            wert = wert.strip()
            # Anführungszeichen sind erlaubt, weil viele sie aus Gewohnheit
            # setzen; im Wert haben sie dann nichts verloren.
            if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in "\"'":
                wert = wert[1:-1]
            werte[name.strip()] = wert
    _zwischenspeicher = werte
    return werte


def wert(name, standard=""):
    """Eine Einstellung lesen. Fehlt sie, kommt der Standard zurück."""
    aus_umgebung = os.environ.get(name)
    if aus_umgebung:
        return aus_umgebung
    return _lade_env().get(name) or standard


def geheim(name):
    """Einen Schlüssel lesen. Fehlt er, bricht der Lauf mit einer Anleitung ab."""
    gefunden = wert(name)
    if gefunden:
        return gefunden

    zeilen = [
        f"{name} ist weder in der Umgebung noch in {ENV_DATEI} gesetzt.",
        "",
        HERKUNFT.get(name, ""),
        "",
        "So kommt er dorthin:",
        f"  cp {BEISPIEL.name} .env      # einmalig, falls noch keine .env da ist",
        f"  # dann in .env die Zeile {name}=… ausfüllen",
        "",
        "Oder nur für diesen einen Lauf:",
        f"  {name}=… {' '.join(sys.argv[:2]) or 'befehl'}",
        "",
        ".env steht in .gitignore und wird nie mitversioniert.",
    ]
    raise SystemExit("\n".join(z for z in zeilen if z is not None))


def vorhanden(name):
    """Ob ein Schlüssel da ist, ohne dass sein Fehlen abbricht. Für Läufe, die
    ohne ihn einen sinnvollen Trockenmodus haben (z. B. build/tts_erzeugen.py)."""
    return bool(wert(name))


if __name__ == "__main__":
    # Selbstauskunft: was ist gesetzt, was fehlt. Zeigt nie einen Wert an.
    print(f"Projekt: {ROOT}")
    print(f".env:    {ENV_DATEI if ENV_DATEI.exists() else 'fehlt (nur Umgebung zählt)'}")
    print()
    for name in HERKUNFT:
        quelle = ("Umgebung" if os.environ.get(name)
                  else ".env" if _lade_env().get(name) else "")
        print(f"  {'✔' if quelle else '—'} {name:<22} {quelle or 'nicht gesetzt'}")
    print()
    for name in ("MC_SERVER", "MC_KEYSTORE"):
        print(f"  · {name:<22} {wert(name) or 'nicht gesetzt'}")
