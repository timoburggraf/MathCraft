#!/usr/bin/env bash
# Baut die Android-App aus dem aktuellen Stand.
#
#   build/android.sh              signierte Release-APK  -> dist/MathCraft.apk
#   build/android.sh debug        Debug-APK (WebView-Debugging moeglich)
#   build/android.sh install      Release bauen und auf ein angeschlossenes Geraet spielen
#
# Toolchain liegt komplett im Benutzerverzeichnis, nichts davon im System.
# Wo der Signierschluessel liegt und wie sein Passwort lautet, steht in der
# .env (MC_KEYSTORE, MC_KEYSTORE_PW) — niemals im Projekt. Siehe .env.beispiel.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT=$PWD

# Wo JDK und SDK liegen, ist von Rechner zu Rechner verschieden. Beides laesst
# sich in der .env (MC_JAVA_HOME, MC_ANDROID_HOME) setzen; ohne Eintrag gelten
# die ueblichen Orte. Nichts davon muss im System installiert sein.
lies() { .venv/bin/python -c "import konfig,sys;sys.stdout.write(konfig.wert('$1',''))"; }

JAVA_HOME="${JAVA_HOME:-$(lies MC_JAVA_HOME)}"
if [ -z "$JAVA_HOME" ]; then
  # Ein einzelnes jdk-17* im Werkzeugordner reicht als Fund; sonst das System-JDK.
  JAVA_HOME=$(ls -d "$HOME"/.local/android-tools/jdk-17* 2>/dev/null | head -1 || true)
  [ -n "$JAVA_HOME" ] || JAVA_HOME=$(dirname "$(dirname "$(readlink -f "$(command -v javac || command -v java)" 2>/dev/null)")" 2>/dev/null || true)
fi
ANDROID_HOME="${ANDROID_HOME:-$(lies MC_ANDROID_HOME)}"
[ -n "$ANDROID_HOME" ] || ANDROID_HOME="$HOME/Android/Sdk"
export JAVA_HOME ANDROID_HOME
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"

[ -x "$JAVA_HOME/bin/java" ] || { echo "JDK 17 fehlt unter '$JAVA_HOME'.
Pfad in .env unter MC_JAVA_HOME eintragen (siehe README.md, Abschnitt Android)."; exit 1; }
[ -d "$ANDROID_HOME/platforms" ] || { echo "Android SDK fehlt unter '$ANDROID_HOME'.
Pfad in .env unter MC_ANDROID_HOME eintragen (siehe README.md, Abschnitt Android)."; exit 1; }

MODE=${1:-release}

# Die Fassung MUSS vor dem Bauen der Web-App feststehen: build.py backt sie in
# die index.html ein, damit die App weiss, welche Nummer sie traegt. Wird erst
# danach hochgezaehlt, meldet sich die App als die vorige Fassung — und wuerde
# sich beim Update-Check selbst ein Update anbieten.
if [ "$MODE" != "debug" ]; then
  GRADLE=android/app/build.gradle
  OLD_CODE=$(grep -oP 'versionCode \K[0-9]+' "$GRADLE")
  NEW_CODE=$((OLD_CODE + 1))
  NEW_NAME=${MC_VERSION_NAME:-"1.$NEW_CODE"}
  sed -i "s/versionCode $OLD_CODE/versionCode $NEW_CODE/" "$GRADLE"
  sed -i "s/versionName \"[^\"]*\"/versionName \"$NEW_NAME\"/" "$GRADLE"
  echo "▸ Version $NEW_NAME (Code $NEW_CODE, vorher $OLD_CODE)"
fi

echo "▸ Web-App bauen"
.venv/bin/python build/build.py | tail -2
cp index.html www/index.html

echo "▸ Nach Android uebernehmen"
npx cap sync android 2>&1 | grep -E "Copying web assets|Sync finished"

if [ "$MODE" = "debug" ]; then
  echo "▸ Debug-APK bauen"
  (cd android && ./gradlew assembleDebug --console=plain -q)
  APK=$ROOT/android/app/build/outputs/apk/debug/app-debug.apk
else
  echo "▸ Release-APK signieren und bauen"
  # konfig.py liest Umgebung und .env — bewusst ueber Python statt "source .env",
  # damit Anfuehrungszeichen und Sonderzeichen im Passwort nicht die Shell treffen.
  export MC_KEYSTORE="${MC_KEYSTORE:-$(lies MC_KEYSTORE)}"
  export MC_KEYSTORE_PW="${MC_KEYSTORE_PW:-$(lies MC_KEYSTORE_PW)}"
  : "${MC_KEYSTORE:=$HOME/.keystores/mathcraft.jks}"
  [ -f "$MC_KEYSTORE" ] || { echo "Keystore fehlt: $MC_KEYSTORE
Pfad in .env unter MC_KEYSTORE eintragen, oder mit 'build/android.sh debug'
eine unsignierte Debug-APK bauen. Anlegen: siehe README.md, Abschnitt Android."; exit 1; }
  [ -n "$MC_KEYSTORE_PW" ] || { echo "MC_KEYSTORE_PW fehlt — in .env eintragen."; exit 1; }
  (cd android && ./gradlew assembleRelease --console=plain -q)
  APK=$ROOT/android/app/build/outputs/apk/release/app-release.apk
fi

mkdir -p dist
# Bewusst if/else: eine fehlschlagende Kommandosubstitution im Namen wuerde
# unter "set -e" das Skript stillschweigend beenden.
if [ "$MODE" = "debug" ]; then
  OUT="$ROOT/dist/MathCraft-debug.apk"
else
  OUT="$ROOT/dist/MathCraft.apk"
fi
cp "$APK" "$OUT"

# Begleitzettel fuer den Heim-Dienst: daran erkennt die App, ob es etwas Neues
# gibt. MC_NOTES beim Aufruf setzen, um zu beschreiben, was sich geaendert hat.
if [ "$MODE" != "debug" ]; then
  CODE=$(grep -oP 'versionCode \K[0-9]+' android/app/build.gradle)
  NAME=$(grep -oP 'versionName "\K[^"]+' android/app/build.gradle)
  python3 - "$CODE" "$NAME" "${MC_NOTES:-}" <<'PY'
import json, sys, datetime, pathlib
code, name, notes = sys.argv[1], sys.argv[2], sys.argv[3]
pathlib.Path("dist/version.json").write_text(json.dumps({
    "versionCode": int(code), "versionName": name,
    "notes": notes or "Verbesserungen und neue Aufgaben.",
    "date": datetime.date.today().isoformat(),
}, ensure_ascii=False, indent=1), "utf-8")
PY
fi

echo
echo "✔ $OUT  ($(du -h "$OUT" | cut -f1))"
# Die neueste vorhandene Fassung der Build-Tools, nicht eine fest verdrahtete —
# welche installiert ist, unterscheidet sich von Rechner zu Rechner.
TOOLS=$(ls -d "$ANDROID_HOME"/build-tools/*/ 2>/dev/null | sort -V | tail -1)
"${TOOLS}apksigner" verify --print-certs "$OUT" 2>/dev/null \
  | grep -m1 "Signer #1 certificate DN" || true
"${TOOLS}aapt2" dump badging "$OUT" 2>/dev/null \
  | grep -oP "versionCode='\K[0-9]+" | head -1 | xargs -I{} echo "  versionCode {}"
if [ "$MODE" != "debug" ]; then
  echo "  → Laesst sich ueber die installierte App druebersetzen; der Lernstand bleibt."
fi

if [ "${1:-}" = "install" ] || [ "${2:-}" = "install" ]; then
  echo "▸ Auf Geraet installieren"
  adb install -r "$OUT"
fi
