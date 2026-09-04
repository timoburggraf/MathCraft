#!/usr/bin/env bash
# Startet MathCraft am Rechner.
#
# Die App wird ueber http://localhost ausgeliefert statt als Datei-URL. Bei
# einer file://-Adresse behandeln Browser jeden Aufruf als eigene Herkunft —
# der Lernstand waere dann je nach Aufrufweg mal da und mal weg. Ueber
# localhost bleibt er zuverlaessig erhalten.
#
# Der Server laeuft nur lokal (127.0.0.1) und ist von aussen nicht erreichbar.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8771

command -v python3 >/dev/null || { echo "python3 wird gebraucht."; exit 1; }
[ -f "$DIR/index.html" ] || { echo "index.html fehlt — zuerst build/build.py laufen lassen."; exit 1; }

# Laeuft schon ein Server auf dem Port? Dann diesen mitbenutzen.
if ! curl -sf -o /dev/null "http://127.0.0.1:$PORT/index.html" 2>/dev/null; then
  python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DIR" >/dev/null 2>&1 &
  SERVER=$!
  trap 'kill $SERVER 2>/dev/null || true' EXIT
  for _ in $(seq 20); do
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/index.html" && break
    sleep .1
  done
fi

URL="http://localhost:$PORT/index.html"
echo "MathCraft laeuft: $URL"
echo "Zum Beenden dieses Fenster schliessen oder Strg+C druecken."

# Chrome bevorzugt (beste Sprachausgabe), sonst der Standardbrowser.
for BROWSER in google-chrome chromium chromium-browser xdg-open; do
  if command -v "$BROWSER" >/dev/null; then
    "$BROWSER" "$URL" >/dev/null 2>&1 &
    break
  fi
done

wait ${SERVER:-$$} 2>/dev/null || true
