# MathCraft

Adaptiver Mathe-Trainer für **Grundschulkinder, die in Mathe mehr wollen** —
Klasse 2 bis 4, einstellbar. Leichter Einstieg, dann sukzessive schwerer, und
die Lernkurve wird nicht vorgegeben, sondern von einem **LLM-Tutor** laufend an
das angepasst, was das Kind kann und was es interessiert. Wo es losgeht, sagt
die eingestellte [Schulklasse](#mehr-als-ein-kind); wie es weitergeht, das Kind
selbst.

Läuft als **Android-App** (Redmi Note 13 Pro) und im Browser. Der Fortschritt
bleibt auf dem Gerät; gespielt wird immer offline.

> Schwesterprojekt eines Vokabeltrainers derselben Bauart — gleiche Plattform,
> gleicher Aufbau, andere Zielgruppe. Wer eines kennt, findet sich im anderen
> zurecht.

---

## Einrichten

Auf einem frischen Rechner, von null bis zur laufenden App:

```bash
git clone https://github.com/timoburggraf/MathCraft.git
cd MathCraft

python3 -m venv .venv
.venv/bin/pip install -U anthropic google-genai Pillow playwright cryptography

cp .env.beispiel .env       # und dort die eigenen Schlüssel eintragen
.venv/bin/python konfig.py  # zeigt, was gesetzt ist (nie einen Wert selbst)

.venv/bin/python build/build.py    # baut index.html aus src/app.html
./"MathCraft starten.sh"           # öffnet sie im Browser
```

**Ohne einen einzigen Schlüssel** läuft bereits alles Wesentliche: die App, der
Heim-Dienst, die Elternseite und sämtliche Tests. Der Aufgabenvorrat
(`data/units_seed.json`), die Bilder und die Vorlesestimmen liegen fertig im
Repository. Ein Schlüssel wird erst gebraucht, wenn **Neues entstehen** soll:

| Wofür | Schlüssel | Wer ihn braucht |
|---|---|---|
| Neue Aufgabenpakete, Tutor, Erklärungen | `ANTHROPIC_API_KEY` | `build/generate_units.py`, `tutor/lehrer.py`, `tutor/erklaerer.py` |
| Neue Illustrationen und Vorlesestimmen | `GEMINI_API_KEY` | `build/make_images.py`, `build/tts_erzeugen.py` |
| Signierte Android-Release-APK | `MC_KEYSTORE`, `MC_KEYSTORE_PW` | `build/android.sh` |

Jeder läuft auf **eigene Rechnung** — beide Anbieter rechnen je Konto ab. Die
Kosten stehen bei den jeweiligen Abschnitten weiter unten. Neue Aufgaben lassen
sich auch **ganz ohne Sprachmodell** erzeugen: `build/kern_pakete.py` baut sie
aus den deterministischen Kernen, kostenlos.

> `konfig.py` liest zuerst die Umgebung, dann die `.env`. Die `.env` steht in
> `.gitignore` und verlässt den eigenen Rechner nie. Im Quelltext steht kein
> einziger Schlüssel — wer einen dort hineinschreibt, macht ihn öffentlich.

**Was hier nicht liegt:** Lernstände. `data/telemetrie/` und alles Weitere, was
von einem echten Kind stammt, ist von der Versionsverwaltung ausgenommen und
bleibt auf dem Rechner, auf dem es entsteht.

---

## Der Unterschied zum Vokabeltrainer

Beim Vokabeltrainer steht der Stoff fest: 1551 Wörter aus dem Schulbuch. Hier
gibt es keinen festen Stoff. Ein Lehrplan legt nur den **Rahmen** fest — welche
Fertigkeit auf welcher Stufe dran ist und in welchem Zahlenraum. Was daraus an
Aufgaben wird, erzeugt Claude, und zwar zugeschnitten auf den aktuellen Stand.

Das Kind bekommt also nicht Paket 17 von 177, sondern das Paket, das jetzt dran
ist — in einer Themenwelt, die es mag.

---

## Aufbau

**Zwölf Welten** (= mathematische Bereiche) auf der Landkarte:

Zahlenland · Plus & Minus · Mal & Geteilt · Muster & Folgen · Formen & Räume ·
Knobelwelt · Roboterwerkstatt · Möglichkeiten · Messen & Wiegen ·
Daten & Tabellen · Zahlengeheimnisse · Sachaufgaben

**89 Fertigkeiten** auf **8 Stufen** — von „Zahlen bis 20" (Anfang Klasse 2) bis
zu Schubfachschluss und Primfaktorzerlegung (Knobelolympiade). Jede Stufe legt
Zahlenraum und erlaubte Rechenarten fest; der Validator prüft jede Aufgabe
dagegen.

| Stufe | | Zahlenraum | entspricht |
|---|---|---|---|
| 1 | Erste Schritte | 20 | Anfang Klasse 2 |
| 2 | Sicher bis 20 | 20 | Klasse 2 |
| 3 | Der Hunderter | 100 | Klasse 2 |
| 4 | Mal und Geteilt | 100 | Ende Klasse 2 |
| 5 | Der Tausender | 1 000 | Klasse 3 |
| 6 | Große Zahlen | 10 000 | Klasse 4 |
| 7 | Zahlenforscher | 100 000 | Klasse 5/6 |
| 8 | Meisterprüfung | 1 000 000 | Knobelolympiade |

**Dreizehn Aufgabenarten**, damit es nicht zum Ausfüllen von Rechenblättern wird:

| Art | Bedienung |
|---|---|
| Neu entdecken | eine Idee wird gezeigt und erklärt, keine Wertung |
| Ausrechnen | eigenes Ziffernfeld (keine Systemtastatur, die die Aufgabe verdeckt) |
| Auswählen | vier Möglichkeiten, genau eine stimmt |
| Stimmt das? | Behauptung prüfen, zwei große Knöpfe |
| Ordnen | Zahlenkarten in die richtige Reihenfolge tippen |
| Zuordnen | Paare verbinden |
| Schritt für Schritt | Sachaufgabe in zwei bis drei Schritten |
| Hinschauen | kleines Gitter: Feld antippen oder auswählen |
| Logikrätsel | Hinweise lesen, Denkhilfe zum Mitnotieren, eine Antwort tippen |
| Wer steht wo? | Positionsrätsel ganz ohne Zahlen, gleiche Bedienung wie Logikrätsel |
| Roboter | Befehlsfolge im Kopf ausführen (Zielfeld tippen), selbst programmieren (Befehlskarten) oder den falschen Befehl finden — der Roboter fährt danach sichtbar los |
| Bildwahl | Fragebild oben, vier Bilder zur Auswahl (Spiegeln, Drehen, Bildmatrix, Analogie) |
| Zählen | Würfelgebäude im Bild, Anzahl über das Ziffernfeld — auch die verdeckten Würfel zählen |

**Die Denkschule (V2)** legt über die Welten fünf Denkdisziplinen — Mustererkennung,
Logik & Deduktion, Algorithmik, Kombinatorik & Strategie, Raum & Form. Warum
und mit welchen Zielwerten, steht in [ZIELE-V2.md](ZIELE-V2.md). Das Prinzip
dahinter: Für Rätsel, die sich nicht als Term nachrechnen lassen (Logikgitter,
Roboterprogramme, Bildmuster), kommt **zuerst ein deterministischer Kern**
(`build/*_kern.py`), der Lösung, Hinweise und Ablenker festlegt und per
vollständiger Enumeration oder Simulation beweist, dass genau eine Antwort
stimmt. Ein Sprachmodell darf höchstens noch die Geschichte drumherum erzählen.
Schwierigkeit heißt dort **Denktiefe** — längere Befehlsfolgen, größere Gitter,
indirektere Hinweise —, nie größere Zahlen.

**Themenwelten** als Einkleidung, rotierend: Blockwelt, Arena, Burgenbau,
Fußball, Baukasten, Sammelmonster, Weltraum, Dinozeit, Rennstrecke, Ninja.
Nur sprachlich — keine Logos, keine Spielgrafiken. Reine Privatnutzung.

**Vorgelesen wird auf Knopfdruck.** Er ist acht und liest noch langsam: Eine
Sachaufgabe, die er sich anhören kann, ist eine Rechenaufgabe — eine, die er
entziffern muss, ist eine Leseaufgabe. Längere Aufgaben liest die App von selbst
einmal vor.

**Erklärt wird auf Wunsch.** Nach einer falschen Antwort steht die Lösung da —
aber zu wissen, was herauskommt, ist nicht dasselbe wie zu wissen, wie man
daraufkommt. Ein Tipp auf **Erklär es mir** holt vom Heim-Dienst eine Erklärung
in zwei bis drei kurzen Sätzen, vorgerechnet an einer gleichartigen Aufgabe mit
anderen Zahlen (nicht an dieser — wer die Antwort vorgesagt bekommt, hat nichts
gelernt). Bleibt er zweimal an derselben Aufgabe hängen, kommt sie von selbst.
Das Beispiel läuft durch denselben Prüfer wie die Pakete; was nicht aufgeht,
wird verworfen und der feste Tipp bleibt stehen.

---

## Mehr als ein Kind

Dieselbe App wird von Kindern verwendet, die nicht in derselben Klasse sitzen.
Ein Viertklässler, der bei „Zahlen bis 20“ anfangen muss, hört wieder auf,
bevor es interessant wird.

**Einstellungen ▸ Schulklasse** setzt deshalb einen **Boden**, keine Decke:

| Klasse | Start bei | Vorratsband |
|---|---|---|
| 2 | Stufe 1 · Erste Schritte | 1–4 |
| 3 | Stufe 4 · Mal und Geteilt | 4–6 |
| 4 | Stufe 5 · Der Tausender | 5–7 |
| 5 | Stufe 6 · Große Zahlen | 6–8 |
| 6 | Stufe 7 · Zahlenforscher | 7–8 |

Der Einstieg liegt je Klasse bewusst **eine Stufe unter** dem, was der Lehrplan
dieser Klasse verlangt: Der Anfang soll gelingen, nicht beeindrucken. Nach oben
zählt weiterhin nur, was das Kind zeigt — wer zwei Pakete fehlerfrei löst,
steigt von selbst. Umstellen ändert nur den Boden; Sterne, Level und
Wiederholungstermine bleiben unangetastet.

Die Zuordnung steht an genau einer Stelle: `KLASSEN` in `build/curriculum.py`.
Die App bekommt sie beim Bauen mitgeliefert, damit Lehrplan und Oberfläche
nicht auseinanderlaufen können.

**Passenden Vorrat erzeugen** — sonst steht ein Viertklässler nach ein paar
Tagen ohne Nachschub da:

```bash
.venv/bin/python build/kern_pakete.py --alle --klasse 4     # kostenlos, aus den Kernen
.venv/bin/python build/generate_units.py --seed --klasse 4  # mit Claude, kostet Guthaben
```

> Der Lernstand hängt am Gerät. Zwei Kinder auf **einem** Gerät teilen sich
> heute noch einen Fortschritt — für zwei Kinder braucht es zwei Geräte oder
> zwei Browser-Profile. Auf der Elternseite lassen sich die Geräte dann
> getrennt auswerten.

---

## Der Fundus — nichts Erzeugtes wird vernichtet

Jedes Paket, jedes Bild und jede Tonspur hat Rechenzeit und Geld gekostet.
Wird etwas ersetzt, wandert die alte Fassung deshalb zuerst nach
[`fundus/`](fundus/README.md), statt überschrieben zu werden:

```
fundus/pakete/<fertigkeit>@<stufe>/<zeitstempel>.json
fundus/bilder/<name>/<zeitstempel>.png
```

Betroffen sind `kern_pakete.py --force`, `generate_units.py --skill …` und
`make_images.py --force`. Die **Vorlesestimmen** brauchen das nicht: ihr
Dateiname ist der crc32 des gesprochenen Textes, ein geänderter Text bekommt
also eine neue Datei statt die alte zu überschreiben — `data/audio/` ist von
sich aus ein Fundus.

```bash
.venv/bin/python build/fundus.py      # was gerade drinliegt
```

---

## Motivation

* **XP & Level** — 10 Stufen von *Rookie* bis *Legende*
* **Tagesziel** als Ring (einstellbar, Standard 15 Aufgaben)
* **Streak** — Tage in Folge, mit Bestwert
* **1–3 Sterne** pro Paket, je nach Trefferquote auf Anhieb
* **16 Abzeichen** (*Volltreffer*, *Knobelkopf*, *Weltmeister*, *Rechenkönig* …)
* **Landkarte** mit zwölf Welten, jede mit eigener Illustration
* Konfetti, Klänge, Tastatursteuerung

**Langzeitgedächtnis.** Jede Fertigkeit hat einen Level 0–5. Richtig auf Anhieb
hebt ihn, falsch senkt ihn um eins (nicht auf null — das würde nur frustrieren).
Je nach Level kommt sie nach **1, 3, 7 oder 21 Tagen** von selbst wieder
(Leitner-Prinzip), sichtbar auf dem Knopf **Wiederholen**.

---

## Kein Rechenfehler kommt beim Kind an

Ein Sprachmodell verrechnet sich. Eine falsch als richtig markierte Aufgabe wäre
der schlimmste Fehler dieses Projekts — das Kind lernt dann Unsinn und verliert
das Vertrauen in die App. Deshalb ist zwischen Modell und Tablet ein Prüfer
geschaltet (`build/validate.py`), der **jede einzelne Aufgabe** durchleuchtet:

1. **Nachgerechnet.** Jede Rechenaufgabe muss ihren Rechenweg als prüfbaren Term
   mitliefern (`"8+5"`). Der wird ausgewertet und muss exakt die angegebene
   Antwort ergeben. Ausgewertet wird über einen eingeschränkten Syntaxbaum, nicht
   über `eval` — der Term kommt schließlich aus einem Sprachmodell.
2. **Regeln.** Zahlenraum und Rechenart passen zur Stufe, keine negativen
   Ergebnisse für Zweitklässler, genau eine Antwort stimmt, die Ablenker sind
   nachweislich falsch, keine doppelten Optionen.
3. **Form.** Text höchstens zwei Sätze, keine Platzhalter, kein Formelsatz, die
   richtige Antwort verrät sich nicht durch ihre Länge.

Wird etwas beanstandet, geht das Paket **mit den Mängeln im Klartext** zurück an
das Modell und wird neu gebaut. Nach drei Fehlversuchen fliegt es raus und landet
im Protokoll. Was in der App landet, ist nachgerechnet.

`build/validator_test.py` prüft den Prüfer: 47 absichtlich kaputte Aufgaben
(falsche Lösung, zwei richtige Optionen, Zahlenraum gesprengt, Code im Term)
müssen alle abgelehnt werden — und einwandfreie ebenso zuverlässig durchgehen.

---

## Aufbau der Dateien

```
src/app.html                    ← DIE QUELLE — hier wird entwickelt
index.html                      ← gebaute Web-App (alles eingebettet)
dist/MathCraft.apk              ← gebaute Android-App (signiert)
build/
  curriculum.py                 ← Bereiche, Fertigkeiten, Stufen, Zahlenräume
  schema.py                     ← das JSON-Schema, in dem Claude abliefern muss
  generate_units.py             ← Aufgaben-Generator (Claude Opus 5)
  validate.py                   ← der Prüfer
  validate_v2.py                ← Rechenlast-Budget und Logikgitter-Prüfung (Denkschule)
  disziplinen.py                ← die fünf Denkdisziplinen über dem Lehrplan (V2)
  raetsel_kern.py               ← deterministische Kerne: Logikgitter, Zahlenfolgen, Positionsrätsel
  grafik_kern.py                ← deterministische Kerne: Würfelgebäude, Spiegelbild, Drehfigur (SVG)
  muster_kern.py                ← deterministische Kerne: Bildmatrix, Analogie (SVG)
  algo_kern.py                  ← deterministische Kerne: Gitter-Roboter, Zahlenmaschine
  spiel_kern.py                 ← deterministischer Kern: Nim-Gewinnstrategie
  verkleidung.py                ← LLM darf nur Namen und Sätze um einen Kern bauen
  kern_pakete.py                ← baut aus den Kernen fertige Pakete, ganz ohne Sprachmodell
  build.py                      ← baut index.html
  make_images.py                ← Illustrationen (Nano Banana)
  make_android_assets.py        ← App-Icon und Splash aus dem Hero-Bild
  android.sh                    ← baut die APK
  validator_test.py / logic_test.py / qa_test.py / smoke_test.py
  update_test.py                ← die Update-Kette gegen einen echten Dienst
  sync_test.py                  ← Z1: kommt der Lernstand vollständig an?
  eltern_test.py                ← Z2: sagt die Elternseite die Wahrheit?
  adaptiv_test.py               ← Z5 und Z3: weicht der Tutor richtig ab, und sagt er es?
  wunsch_test.py                ← Z4: wirken die Elternwünsche?
  erklaer_test.py               ← Z6: wird eine falsch gerechnete Erklärung verworfen?
  klassen_test.py               ← Klassenstufe: Boden, keine Decke — und der Fundus vernichtet nichts
tutor/
  server.py                     ← der Heim-Dienst (Routen)
  speicher.py                   ← Ablage der Messdaten, idempotent
  auswertung.py                 ← rechnet Ereignisse in Aussagen um; alle Schwellen
  protokoll.py                  ← was der Tutor entschieden hat, als deutscher Satz
  eltern.py                     ← die Elternseite
  erklaerer.py                  ← Erklärung am Beispiel, nachgerechnet
konfig.py                       ← Schlüssel und rechnerspezifische Pfade, aus Umgebung oder .env
build/fundus.py                 ← legt ab, was ersetzt wird — nichts Erzeugtes geht verloren
fundus/                         ← die abgelegten Vorgängerfassungen
.env.beispiel                   ← Vorlage dafür; die ausgefüllte .env bleibt lokal
data/units_seed.json            ← Grundstock, wird in die App gebacken
data/audio/<stimme>/*.opus      ← vorproduzierte Vorlesestimmen (zephyr, puck, leda)
img/raw/*.png                   ← Illustrationen im Original
```

**Nicht im Repository** — steht in `.gitignore` und bleibt auf dem eigenen
Rechner: alles, was von einem echten Kind stammt (`data/telemetrie/`,
`data/erklaerungen/`, `data/entscheidungen.jsonl`, `data/verworfen.json`,
`data/tutorplan.json`), die `.env` mit den Schlüsseln, und die Bauergebnisse
(`index.html`, `www/`, `dist/`). Die Protokolldateien legen der Erzeuger und
der Prüfer beim ersten Lauf selbst an; fehlen sie, bleiben die entsprechenden
Abschnitte der Elternseite einfach leer.

Die Ziele, an denen sich `tutor/` messen lässt, stehen in **[ZIELE.md](ZIELE.md)** —
samt der Schwellen, ab denen eine Fertigkeit als „sitzt“ oder „hakt“ gilt. Wer
sie ändert, ändert damit auch, was Eltern über ihr Kind erfahren.

`index.html`, `www/` und `dist/` sind **Bauergebnisse** — Änderungen gehören in
`src/app.html`, danach `build/build.py` bzw. `build/android.sh`.

### Neu bauen

```bash
python3 -m venv .venv && .venv/bin/pip install -U anthropic google-genai Pillow playwright cryptography
.venv/bin/python build/build.py            # index.html neu erzeugen
.venv/bin/python build/validator_test.py   # Prüfungen des Prüfers (absichtlich kaputte Aufgaben)
.venv/bin/python build/logic_test.py       # Prüfungen der Lernlogik und der App-Renderer
.venv/bin/python build/qa_test.py          # Passform auf 6 Displayformaten
.venv/bin/python build/smoke_test.py       # klickt die App komplett durch
.venv/bin/python build/raetsel_kern_test.py build/grafik_kern_test.py   # (je einzeln aufrufen)
.venv/bin/python build/muster_kern_test.py; .venv/bin/python build/algo_kern_test.py
.venv/bin/python build/spiel_kern_test.py; .venv/bin/python build/validate_v2_test.py
.venv/bin/python build/klassen_test.py     # Klassenstufe (Boden, keine Decke) und der Fundus
```

Pakete aus den deterministischen Kernen (kostenlos, ohne Sprachmodell):

```bash
.venv/bin/python build/kern_pakete.py --alle              # fehlende Kern-Pakete nachlegen
.venv/bin/python build/kern_pakete.py --skill algo_finden --stage 5 --force
```

Neue Aufgaben erzeugen (kostet API-Guthaben):

```bash
.venv/bin/python build/generate_units.py --seed            # fehlende Grundstock-Pakete
.venv/bin/python build/generate_units.py --skill mal_alle --stage 4 --n 2
.venv/bin/python build/generate_units.py --seed --dry-run  # nur zeigen, was liefe
```

Die Schlüssel (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) liefert `konfig.py` aus
der Umgebung oder der `.env` — siehe [Einrichten](#einrichten). Im Quelltext
steht keiner. Die fertige `index.html` enthält ebenfalls keinerlei Schlüssel
und ruft im Betrieb nichts ab: Das Kind spielt offline.

**Kosten:** rund 0,05–0,10 € je erzeugtem Paket, mit Prompt-Caching darunter.
Ein Budgetdeckel je Lauf ist eingebaut (`--budget`).

---

## Android-App

```bash
build/android.sh              # signierte Release-APK -> dist/MathCraft.apk
build/android.sh debug        # Debug-APK (erlaubt WebView-Fernsteuerung)
build/android.sh install      # bauen und auf ein angeschlossenes Geraet spielen
```

Dieselbe Web-App, verpackt mit **Capacitor**. Für das Vorlesen übernimmt auf
Android `@capacitor-community/text-to-speech`. Die Hardware-Zurück-Taste
navigiert in der App, statt sie zu beenden.

**Toolchain** liegt im Benutzerverzeichnis, nichts davon im System: JDK 17
unter `~/.local/android-tools/`, Android SDK unter `~/Android/Sdk`. Stehen sie
woanders, `MC_JAVA_HOME` und `MC_ANDROID_HOME` in der `.env` setzen.

**Signierschlüssel.** Wo er liegt und wie er heißt, steht in der `.env`
(`MC_KEYSTORE`, `MC_KEYSTORE_PW`) — **nie** im Projekt. Wer noch keinen hat,
legt sich einen an:

```bash
keytool -genkeypair -v -keystore ~/.keystores/mathcraft.jks \
        -alias mathcraft -keyalg RSA -keysize 2048 -validity 10000
```

> Den Keystore aufbewahren: Nur mit ihm lassen sich künftige Versionen als
> Update installieren. Geht er verloren, muss die App auf dem Gerät erst
> deinstalliert werden — und der Lernstand ist weg.

| | |
|---|---|
| Paketname | `de.burggraf.mathcraft` — für eine schon installierte App nie ändern. Wer bei null anfängt, setzt in `capacitor.config.json`, `android/app/build.gradle` und `android/app/src/main/res/values/strings.xml` seinen eigenen. |
| Signaturschlüssel | Pfad aus `MC_KEYSTORE` — **unbedingt aufbewahren** |
| `versionCode` | zählt `build/android.sh` bei jedem Release automatisch hoch |

---

## Updates ohne Kabel

Die App wird weiterentwickelt — eine APK jedes Mal per USB aufs Handy zu
schieben, hält niemand durch. Deshalb läuft zu Hause ein kleiner Dienst, und in
der App genügt ein Knopf.

```bash
.venv/bin/python tutor/server.py          # auf 0.0.0.0:8790
```

Dauerhaft im Hintergrund:

```bash
mkdir -p ~/.config/systemd/user
cp tutor/mathcraft.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now mathcraft
loginctl enable-linger $USER              # läuft auch ohne Anmeldung
```

**Ablauf auf dem Handy:** Einstellungen ▸ *Update* ▸ **Nach Update suchen**. Gibt es
etwas Neues, steht dort, was sich geändert hat; ein Tipp auf *Herunterladen*
startet den Download, danach fragt Android selbst, ob installiert werden soll.
Der Lernstand bleibt dabei erhalten — gleicher Paketname, gleicher Schlüssel,
höherer `versionCode`.

Die Adresse des Rechners backt `build/build.py` als Voreinstellung ein (die
aktuelle WLAN-Adresse); in den Einstellungen ist sie änderbar, falls sich die
IP ändert. Eine feste Adresse lässt sich beim Bauen vorgeben:

```bash
MC_SERVER=192.168.1.20:8790 build/android.sh      # oder dauerhaft in die .env
MC_NOTES="Neue Knobelaufgaben ab Stufe 5." build/android.sh
```

`MC_NOTES` ist der Text, den das Kind beim Update zu lesen bekommt — ohne Angabe
steht dort ein allgemeiner Hinweis.

> Der Dienst ist **nur im Heimnetz** erreichbar und spricht Klartext-HTTP;
> dafür erlaubt die App `usesCleartextTraffic`. Für einen Dienst, der nie das
> WLAN verlässt, ist das vertretbar — nach außen geöffnet werden sollte er nicht.

## Die Elternseite

`http://<Rechner>:8790/eltern` — erreichbar, sobald `tutor/server.py` läuft.
Was dort steht und woran es sich messen lässt, steht vollständig in
**[ZIELE.md](ZIELE.md)**; hier nur der Überblick:

Von oben nach unten: erst die Antwort, dann die Belege, zuletzt die Technik.

| Abschnitt | Was er beantwortet |
|---|---|
| Kurz gesagt | Wie es läuft, in fünf Sätzen — wie viel geübt wurde, ob es zu leicht oder zu schwer war, was hakt |
| Was der Tutor sich denkt | Was er vorhat und warum, in seinen eigenen Worten |
| War es zu leicht oder zu schwer? | Wie oft eine Sitzung goldrichtig lag (70–85 %) |
| Was besonders auffällt | Was sitzt, was hakt — mit den Zahlen dahinter |
| Wie es sich entwickelt | Trefferquote je Welt über acht Wochen |
| Was der Tutor verändert hat | Jede Anpassung als ein deutscher Satz mit Beleg |
| Deine Wünsche | mehr · weniger · jetzt dran · erst später, je Welt und Fertigkeit |
| Alle Fertigkeiten | Alle 89, auch die nie geübten — sonst entstünden blinde Flecken |
| Technik und Datengrundlage | Zählen Gerät und Dienst gleich? Welches Gerät liefert was? Reicht der Nachschub? |

Übt mehr als ein Gerät mit, steht im Technikteil je Gerät, wie viel es
beigesteuert hat. Ein Gerät, das nur zum Ausprobieren lief, lässt sich dort mit
einem Tipp aus der Auswertung nehmen — seine Aufzeichnung bleibt erhalten.

Die App überträgt beim Start und nach jeder Sitzung, ohne Zutun. Ist der
Rechner nicht erreichbar, wartet sie — bis zu 90 Tage, ohne etwas zu verlieren.
Übertragen wird eine Geräte-Kennung, nie ein Name.

## Was noch kommt

**Der Tutor legt selbst nach.** Heute erzeugt `build/generate_units.py` Pakete
auf Zuruf. Als Nächstes soll der Dienst das von sich aus tun, sobald die
Elternseite eine Vorratslücke zeigt — gerade stehen dort **10 von 77
Fertigkeiten ohne ein einziges Paket** (Stufen 7 und 8).

**Die Basiswerte setzen.** Mehrere Zielwerte in ZIELE.md sind mit **(v)**
markiert: fachlich begründete Startannahmen, die nach 14 Tagen echter Nutzung
einmalig auf die dann gemessene Basis neu gesetzt werden.

---

## Lizenz

[MIT](LICENSE) — nutzen, ändern, weitergeben ausdrücklich erwünscht.

Zwei Dinge fallen nicht darunter: Die **Illustrationen** (`img/`) und die
**Vorlesestimmen** (`data/audio/`) sind mit Google Gemini erzeugt; wer sie
weiterverwendet, sieht dort in die Nutzungsbedingungen. Und die **Themenwelten**
sind bewusst nur sprachlich gehalten — Blockwelt, Arena, Sammelmonster. Die
internen Kennungen im Lehrplan tragen noch die Namen der Spiele, die Pate
standen; im sichtbaren Text der App taucht keine Marke, kein Logo und keine
Spielgrafik auf, und das soll so bleiben.

---

## Fortschritt zurücksetzen

Einstellungen ▸ *Alles löschen*. Der Fortschritt hängt am Gerät bzw. am
Browser-Profil — Handy und Rechner zählen getrennt.
