# -*- coding: utf-8 -*-
"""Central MathCraft configuration.

Credentials are read exclusively from the authenticated shared Vault client.
MC_KEYSTORE_PW maps to MATHCRAFT_KEYSTORE_PW. Normal settings may come from
process environment or .env. No plaintext credential fallback is accepted.
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
    "ANTHROPIC_API_KEY": {
        "zweck": "Zugang zu Claude — erzeugt den Lehrplan, die Aufgabenpakete und die Erklärungen.",
        "quelle": "https://console.anthropic.com/settings/keys",
    },
    "GEMINI_API_KEY": {
        "zweck": "Zugang zu Google Gemini — erzeugt die Illustrationen und die Vorlesestimmen.",
        "quelle": "https://aistudio.google.com/apikey",
    },
    "MC_KEYSTORE_PW": {
        "zweck": "Passwort des Android-Signierschlüssels (siehe MC_KEYSTORE).",
        "quelle": "README.md (Anleitung zum Anlegen des Keystores)",
    },
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
                print(f"[konfig] .env Zeile {nr} ohne '=' — übergangen",
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
    if name in HERKUNFT:
        return geheim(name)
    aus_umgebung = os.environ.get(name)
    if aus_umgebung:
        return aus_umgebung
    return _lade_env().get(name) or standard


def geheim(name):
    """Read a required credential from the central Vault, without env fallback."""
    from _project_vault import get_secret
    vault_name = "MATHCRAFT_KEYSTORE_PW" if name == "MC_KEYSTORE_PW" else name
    value = get_secret(vault_name)
    if not value or value.startswith("USE_VAULT"):
        raise SystemExit(f"{vault_name} fehlt im zentralen Vault.")
    return value


def vorhanden(name):
    """Ob ein Schlüssel da ist, ohne dass sein Fehlen abbricht. Für Läufe, die
    ohne ihn einen sinnvollen Trockenmodus haben (z. B. build/tts_erzeugen.py)."""
    from _project_vault import get_secret
    vault_name = "MATHCRAFT_KEYSTORE_PW" if name == "MC_KEYSTORE_PW" else name
    return bool(get_secret(vault_name))


if __name__ == "__main__":
    # Selbstauskunft: was ist gesetzt, was fehlt. Zeigt nie einen Wert an.
    print(f"Projekt: {ROOT}")
    print(f".env:    {ENV_DATEI if ENV_DATEI.exists() else 'fehlt (nur Umgebung zählt)'}")
    print()
    for name in HERKUNFT:
        quelle = "Vault" if vorhanden(name) else ""
        print(f"  {'✔' if quelle else '—'} {name:<22} {quelle or 'nicht gesetzt'}")
    print()
    for name in ("MC_SERVER", "MC_KEYSTORE"):
        print(f"  · {name:<22} {wert(name) or 'nicht gesetzt'}")
