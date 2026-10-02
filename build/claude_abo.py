# -*- coding: utf-8 -*-
"""Aufrufe über das Claude-Abo: `claude -p` headless statt API-Schlüssel.

Warum der Schlüssel aus der Umgebung muss: Ist ANTHROPIC_API_KEY (oder
ANTHROPIC_AUTH_TOKEN) gesetzt, rechnet Claude Code diesen ab statt des Abos.
Der Subprozess bekommt deshalb eine Umgebungskopie ohne beide Variablen.
Muster: Flashforge_AI/c5_wache.py (abo_json, _claude_pfad).

Es gibt hier keinen Rückfall auf den Schlüssel. Scheitert ein Aufruf, wird
AboFehler geworfen; der Aufrufer bricht den Lauf mit klarer Meldung ab.
Schlüsselwerte werden nirgends ausgegeben.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time

ZEITLIMIT = 900            # Sekunden je Aufruf; Opus mit effort high braucht Zeit
MAX_AUSGABE = 64000        # Obergrenze des Modells für Ausgabe-Token


class AboFehler(Exception):
    """Der Abo-Weg ist ausgefallen. Kein stiller Rückfall auf die API."""


def claude_pfad():
    """Die claude-CLI finden, auch wenn der PATH sie nicht enthält (cron,
    systemd, setsid-Start: dort fehlt ~/.npm-global/bin)."""
    gefunden = shutil.which("claude")
    if gefunden:
        return gefunden
    for p in ("~/.npm-global/bin/claude", "~/.local/bin/claude",
              "~/.claude/local/claude", "/usr/local/bin/claude"):
        voll = os.path.expanduser(p)
        if os.path.isfile(voll) and os.access(voll, os.X_OK):
            return voll
    return None


def _umgebung(max_tokens):
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    if max_tokens:
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(min(int(max_tokens), MAX_AUSGABE))
    return env


def kommandozeile(programm, modell, system, schema=None, effort="high",
                  ausgabe="json"):
    """Die Argumentliste (ohne Prompt – der geht per stdin)."""
    cmd = [programm, "-p", "--model", modell, "--effort", effort,
           "--system-prompt", system,
           "--tools", "",                      # keine Werkzeuge nötig
           "--no-session-persistence",
           # Kein Fremdkontext: keine Nutzer-CLAUDE.md/-Hooks, keine MCP-Server,
           # keine Skills. Gemessen: Kontext sinkt von ~72.000 auf ~900 Token.
           "--setting-sources", "project",
           "--strict-mcp-config", "--disable-slash-commands",
           "--output-format", ausgabe]
    if ausgabe == "stream-json":
        cmd.append("--verbose")
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema, ensure_ascii=False)]
    return cmd


def abo_aufruf(modell, system, prompt, schema=None, effort="high",
               zeitlimit=ZEITLIMIT, max_tokens=None):
    """Ein Aufruf über das Abo.

    schema: reines JSON-Schema (bei der API stand es unter format["schema"]).
    Rückgabe: dict mit
        daten       geparstes JSON (nur mit schema) oder None
        text        Antworttext
        stop_reason z. B. "end_turn" / "max_tokens" / "refusal"
        usage       dict input_tokens, output_tokens, cache_*_input_tokens
        liste_usd   total_cost_usd laut CLI – nur Listenpreis, KEINE echten Kosten
        dauer       Sekunden
    Wirft AboFehler, wenn der Abo-Weg ausfällt.
    """
    programm = claude_pfad()
    if not programm:
        raise AboFehler("`claude` nirgends gefunden (PATH, ~/.npm-global/bin, "
                        "~/.local/bin, ~/.claude/local, /usr/local/bin). "
                        "Abo-Weg nicht verfügbar – kein Rückfall auf den "
                        "API-Schlüssel; mit --api ausdrücklich umschalten.")
    cmd = kommandozeile(programm, modell, system, schema, effort)
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="mathcraft_abo_") as neutral:
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                               timeout=zeitlimit, env=_umgebung(max_tokens),
                               cwd=neutral)
        except FileNotFoundError:
            raise AboFehler(f"{programm} nicht ausführbar")
        except subprocess.TimeoutExpired:
            raise AboFehler(f"Zeitlimit {zeitlimit} s überschritten ({modell})")
    dauer = time.time() - t0
    if r.returncode != 0:
        raise AboFehler(f"claude endete mit Exit {r.returncode}: "
                        f"{(r.stderr or r.stdout).strip()[:300]}")
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise AboFehler(f"Ausgabe von claude ist kein gültiges JSON: {e}: "
                        f"{r.stdout[:200]!r}")
    if not isinstance(d, dict):
        raise AboFehler("Ausgabe von claude hat unerwartete Form")
    text = d.get("result") or ""
    if d.get("is_error"):
        raise AboFehler(f"claude meldet Fehler ({d.get('subtype')}): {text[:300]}")
    daten = None
    if schema is not None:
        daten = d.get("structured_output")
        if daten is None:
            # Notanker: manche Läufe legen das JSON nur in "result"
            try:
                daten = json.loads(text)
            except json.JSONDecodeError:
                if d.get("stop_reason") in ("max_tokens", "refusal"):
                    daten = None            # Aufrufer behandelt wie bisher
                else:
                    raise AboFehler("Antwort ohne structured_output und kein "
                                    f"gültiges JSON in result: {text[:200]!r}")
    return {"daten": daten, "text": text,
            "stop_reason": d.get("stop_reason"),
            "usage": d.get("usage") or {},
            "liste_usd": d.get("total_cost_usd"),
            "dauer": dauer}
