# ZIELE-V2 — Denkschule: Begabtenförderung statt Stoffvermittlung

*Aufgestellt am 01.09.2026. Die Ausgangslage ist gemessen, nicht geschätzt.
[ZIELE.md](ZIELE.md) gilt weiter, wo dieses Dokument nichts anderes sagt —
insbesondere Z1 (Datengrundlage), Z3 (Protokoll), Z7 (der Tutor entscheidet
selbst) und das Qualitätsversprechen: kein Fehler erreicht das Kind.*

## Zielbild

MathCraft wird vom adaptiven Schulstoff-Trainer zum Begabtenförderprogramm.
Im Zentrum stehen fünf **Denkdisziplinen** statt elf Stoffwelten:
Mustererkennung, Logik & Deduktion, Algorithmik, Kombinatorik & Strategie,
Raum & Form. Rechnen ist Mittel, nicht Zweck — jede Aufgabe hat ein
Rechenlast-Budget, damit Anstrengung aus dem Denken kommt, nicht aus dem
Ziffernschieben. Einstieg ist immer die anspruchsvolle Zielaufgabe; fehlende
Basics legt der Tutor als kurze **Pre-Lessons** davor, mit sichtbarem Bezug
zum Ziel — nach oben ohne Limit. **Nordstern ist die Motivation**, gemessen an
Wochenmenge, Sofort-Abbrüchen und einem direkten Spaß-Signal. Ein **Avatar**
lebt sichtbar am Bildschirmrand — ein Haustier, das einem etwas beibringt —
und wird der Ansprechpartner des Kindes; er fragt bei Abbrüchen sparsam nach dem Grund,
und seine Antworten fließen in den Tutorplan ein. Das LLM erfindet die
Geschichte, nie die Wahrheit: Jede V2-Aufgabe ist deterministisch auf
Lösbarkeit und Eindeutigkeit geprüft. **V1 bleibt vollständig erhalten** und
ist im Optionsmenü umschaltbar.

## Ausgangslage, gemessen am 01.09.2026 (KW 31–35, 570 Antworten)

| Größe | Wert |
|---|---|
| Mediane Antwortzeit | KW 31: 14,2 s → KW 34/35: 21–23 s — Aufgaben wurden anstrengender, nicht anspruchsvoller |
| Trefferquote | 81 % → 70–72 % — er kann es weiterhin, es dauert nur länger |
| Wochenmenge | 188 → 228 → **24** → 56 → 74 Antworten (KW 33/34 = Sommerferien, aber der Trend hält in KW 35) |
| Sofort-Abbrüche | 9 der letzten 25 Sitzungen enden 0/0 — Paket geöffnet, sofort weggetippt (36 %) |
| Extremfall Rechenlast | `geo_umfang`: 40 % richtig bei 51 s median je Aufgabe |
| Planauslieferung | Der Tutorplan vom 26.08. stellt fest: von zehn vorgezogenen Fertigkeiten wurde **keine einzige** gestellt |
| Logik-/Knobel-Keimzellen | `log_gitter`, `log_reihen`, `log_strategie`, `must_figur`, `komb_taube` existieren im Curriculum, sind aber kaum mit Paketen versorgt |

**Die Diagnose in einem Satz:** Das Kind weiß, *was* zu tun ist — die Aufgaben
wurden nur rechenaufwendiger, nicht denkinteressanter, und darauf reagiert er
mit Sofort-Abbruch.

## Warum ein Teil der Zielwerte vorläufig ist

Wie in ZIELE.md: Mit **(v)** markierte Werte sind begründete Startannahmen und
werden nach **14 Tagen echter V2-Nutzung in Schulwochen** einmalig auf die
gemessene Basis neu gesetzt. Ferienwochen zählen nicht als Basis.

---

## V0 — Vorarbeit: Der Plan muss das Gerät erreichen *(Pflicht, vor allem anderen)*

Die beste Adaptivität ist Theater, wenn der Plan das Handy nicht steuert.

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Ursache gefunden | Es ist belegt, warum vom Plan vom 26.08. nichts gestellt wurde | Diagnosebericht mit Codestelle |
| Wirksamkeit | Nach einem Sync mit neuem Plan bestimmt der Plan das nächste Paket | erweiterter `adaptiv_test.py` + realer Nachweis auf der Elternseite |
| Sichtbarkeit | Die Elternseite zeigt je Planposten: gestellt / noch nicht dran / nicht stellbar (kein Paket) | Sichtprüfung |

## D1 — Fünf Denkdisziplinen

V2 legt eine **Disziplin-Sicht** über das bestehende Curriculum. Die 77
Fertigkeiten bleiben (samt Lernstand); Rechen-Fertigkeiten werden zu
Pre-Lesson-Material. Neue Fertigkeiten kommen hinzu, wo eine Disziplin heute
dünn ist.

| Disziplin | Bestand | Neu in V2 |
|---|---|---|
| **Mustererkennung** | `must_*` (numerisch) | figürliche Matrizen (3×3-Bildmuster: Form/Farbe/Anzahl/Drehung), Analogien („A verhält sich zu B wie C zu ?") |
| **Logik & Deduktion** | `log_paare`, `log_waage`, `log_reihen`, `log_wahrheit`, `log_gitter` | Logikgitter in Stufen (2 Merkmale × 3 bis 4 × 4), Lügen-/Wahrheitsrätsel, Positionsrätsel — auch **komplett ohne Zahlen** (Busfahrer-mit-Schnurrbart-Typ) |
| **Algorithmik** | — (neu) | Befehlsfolgen für einen Roboter auf dem Gitter (befolgen, finden, **reparieren**), Regeln entdecken, Wiege-/Sortierstrategien |
| **Kombinatorik & Strategie** | `komb_*`, `log_strategie`, `log_invar` | Gewinnstrategien zum Ausprobieren (Nim-artig), systematisches Zählen mit Bild |
| **Raum & Form** | `geo_*`-Auswahl | Kopfgeometrie: Falten, Spiegeln, Würfelnetze, „von oben gesehen" |

**Umsetzungsstand 03.09.2026 — zwölf neue Fertigkeiten, alle mit
deterministischem Kern und ohne Sprachmodell erzeugt (`build/kern_pakete.py`),
je zwei Pakete (eigene Stufe und Stufe+1):**

| Disziplin | Neue Fertigkeiten (Stufe) | Kern | Aufgabentyp in der App |
|---|---|---|---|
| Mustererkennung | `must_matrix` (4), `must_analogie` (6) | `muster_kern.py` | Bildwahl |
| Logik & Deduktion | `log_position` (5) — Positionsrätsel ohne Zahlen | `raetsel_kern.py` | Wer steht wo? |
| Algorithmik | `algo_befolgen` (3), `algo_finden` (4), `algo_reparieren` (5), `algo_maschine` (5), `algo_schleife` (6) | `algo_kern.py` | Roboter (drei Modi), Zahlenmaschine als Ausrechnen/Auswählen |
| Kombinatorik & Strategie | `komb_nim` (5) — Nim-Gewinnzug | `spiel_kern.py` | Ausrechnen / Auswählen / Schritt für Schritt |
| Raum & Form | `geo_spiegel` (3), `geo_drehen` (4), `geo_wuerfel` (5) | `grafik_kern.py` | Bildwahl, Zählen |

Die Algorithmik hat dafür eine eigene zwölfte Welt („Roboterwerkstatt", `algo`)
bekommen, damit sie auch in V1 und auf der Elternseite sichtbar ist.

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Spielbar zum Start beim Kind (Tag 8) | ≥ 3 Disziplinen mit je ≥ 4 Paketen auf seinem Niveau | Vorratszählung |
| Vollausbau | alle 5 Disziplinen binnen Woche 2 per OTA | Vorratszählung |
| Textlast | Jedes Rätsel ist vollständig vorlesbar; Hinweise zusätzlich als Symbole/Bilder, wo möglich | Sichtprüfung, Stichprobe 20 |

## D2 — Rechenlast-Budget

**Grunddefinition (Timo, 03.09.2026):** Komplexität und Schwierigkeit kommen
nicht von großen Zahlen, sondern von komplexer Logik, komplexer Algorithmik
oder von mehreren Schritten, die man im Kopf machen muss. Eine höhere Stufe
erhöht also die Denktiefe (mehr Hinweise, größere Gitter, längere
Schlussketten, mehr mentale Zwischenschritte) — niemals bloß den Zahlenraum.
Der Deckel unten ist die eine Hälfte dieser Regel (Rechenlast begrenzen), die
Stufen-Gestaltung der Erzeuger ist die andere (Denktiefe steigern).

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Budget im Schema | Jede Aufgabe deklariert ihre elementaren Rechenschritte; der Validator zählt am Term nach | Schema + `validate.py` |
| Deckel | Disziplin-Aufgaben: ≤ 6 elementare Schritte (Kombinatorik: ≤ 8 — mehrgliedrige Zählketten aus Einmaleins-Schritten sind dort der Denkweg, kein Grind). Nur Pre-Lessons und ausdrückliche Rechen-Fertigkeiten dürfen darüber | Validator lehnt Verstöße ab |
| Wirkung | Mediane Antwortzeit V2-Aufgaben ≤ 20 s **(v)** bei gehaltener oder steigender Denkstufe | aus Z1-Daten |

## D3 — Challenge first: Pre-Lessons statt Lehrplan

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Dramaturgie | Eine Sitzung beginnt mit einer Disziplin-Aufgabe, nicht mit Basics — ≥ 80 % der Sitzungen | aus Z1-Daten |
| Pre-Lesson | Erkennt der Tutor eine Basics-Lücke für ein Ziel, legt er 2–4 Aufgaben davor — mit sichtbarem Bezug: „Das brauchst du gleich für …" | Sichtprüfung in der App |
| Nachvollziehbar | Jede Pre-Lesson-Kette steht im Protokoll: Ziel, Lücke, Vorlauf, Ergebnis | wie Z3 |
| Kein Limit | Z7 gilt unverändert — kein Plan wird wegen seiner Kühnheit abgeschwächt | Testfall aus Z7 |

## D4 — Der deterministische Kern: Prüfbarkeit jenseits des Rechnens

Ein Logikrätsel ist nicht als Term nachrechenbar — und genau da patzen
Sprachmodelle notorisch (unlösbar, zweideutig, widersprüchlich). Deshalb wird
das Erzeugungsprinzip umgedreht: **Der deterministische Kern kommt zuerst, das
LLM liefert nur die Verkleidung.**

| Rätselart | Kern | Prüfung |
|---|---|---|
| Logikgitter / Positionsrätsel | feste Lösungsbelegung → Hinweise werden daraus erzeugt | vollständige Enumeration: genau **eine** Lösung, kein Hinweis überflüssig |
| Muster & Folgen | Regel → Glieder werden berechnet | Regel anwenden, Glieder stimmen |
| Figürliche Matrizen | Regel → SVG wird gerendert | Rendering aus der Regel, Ablenker verletzen sie nachweislich |
| Algorithmik | Programm wird simuliert | Simulation liefert exakt die angegebene Endlage |

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Garantie | Jede V2-Aufgabe deterministisch geprüft: lösbar, eindeutig, Ablenker nachweislich falsch | `validate.py`-Ausbau |
| Prüfer geprüft | `validator_test.py` erweitert: absichtlich zweideutige, unlösbare und widersprüchliche Rätsel werden **alle** abgelehnt | ≥ 20 neue Negativfälle |
| Rollenteilung | Das LLM formuliert Geschichte und Einkleidung; Lösung, Hinweise und Ablenker kommen aus dem Kern | Codereview: kein LLM-Feld ist wahrheitstragend |

## D5 — Der Avatar: sichtbare Bezugsfigur aus der Blockwelt

Ein kleines Wesen, das am Bildschirmrand lebt — wie ein Haustier, das einem
etwas beibringt. Es ist ehrlich: ein schlauer Computer-Tutor, kein
vorgetäuschter Mensch. Der Stil ist **Blockwelt** (verniedlichte
Voxel-Figuren, eigenständig, keine Kopien existierender Spielfiguren —
die Projektlinie „keine Spielgrafiken" bleibt).

**Gefährten-System (Entscheidung Timo, 01.09.2026):** Drei Kandidaten stehen
zur Wahl — Blockwesen, Mini-Golem, Würfelfuchs (Entwürfe in
`img/raw/avatar_konzepte/`). **Das Kind wählt beim ersten V2-Start einen Starter
und tauft ihn** — das schafft Bindung. Die anderen beiden sind über
Knobel-Meilensteine **freispielbar** und danach als Begleiter wechselbar.
Die bestehenden Motivationssysteme werden angedockt statt verdoppelt: die
**16 Abzeichen** schalten kleine Ausrüstungs-Overlays frei (Denkerbrille,
Umhang, Helm …), das **XP-Level** lässt den Gefährten in bis zu drei
Wachstumsstufen mitwachsen. Ausdrücklich **keine Druckmechanik**: kein
Hunger, kein Verkümmern, kein Verlust bei Pausen — wer nicht spielt, findet
einen friedlich schlafenden Gefährten vor, keinen vorwurfsvollen.

**Präsenz:** schaut vom Rand herein, blinzelt, wippt; freut sich sichtbar bei
Erfolgen; schläft ein, wenn nichts passiert; verschwindet auch mal und kommt
wieder. Ein Tipp auf ihn öffnet eine Sprechblase (Gruß, kleiner Kommentar zum
Tag, Vorlesen-Knopf). Er sitzt nie über Eingabeflächen und blockiert nie eine
Aufgabe.

**Nachfragen — sparsam:** Nach einem Abbruch (oder auffälligem Muster) fragt
er mit vier antippbaren, vorgelesenen Optionen: *zu lang · langweilig · zu
schwer · wollte was anderes machen*. Höchstens **eine Nachfrage am Tag**, nie
zweimal hintereinander, immer wegtippbar. Die Antwort wird zum
Telemetrie-Ereignis und erreicht den Tutor.

**Technik — minimalistische Animation ohne Video:** 8–12 Posen-Stills
(Design und Posen: **Nano Banana Pro/Gemini**, iterativ am selben Charakter
editiert für Konsistenz; Freistellung auf Alpha), als WebP eingebettet,
**Gesamtbudget ≤ 300 KB**. Bewegung per CSS-Transforms und Posen-Wechsel
(hereinschauen = Translation + Rotation, Blinzeln = Frame-Tausch). Kein
Videoformat, kein zusätzlicher KI-Dienst erforderlich; für echte
Zeichentrick-Clips stünde Higgsfield bereit, wird für V2.0 aber nicht
gebraucht.

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Präsenz | Avatar auf jedem Hauptbildschirm sichtbar, mindestens 4 Verhaltensweisen (hereinschauen, blinzeln/wippen, freuen, schlafen/weggehen) | Sichtprüfung + `smoke_test.py` |
| Nachfrage-Deckel | max. 1/Tag, nie 2× in Folge, immer wegtippbar | Testfall |
| Datenkanal | Jede Antwort erzeugt ein Ereignis (Z1-konform, keine Freitexte), der Tutor sieht es beim nächsten Plan | Testfall + Sichtprüfung Tutorauszug |
| Starterwahl + Taufe | Wahldialog (3 Kandidaten) und Namensdialog beim ersten V2-Start; Name nur lokal, verlässt das Gerät nicht | Testfall + Z1-Datenschutzprüfung |
| Freispielen | Die zwei übrigen Gefährten sind an Meilensteine gebunden, in der App als „schlafen noch" sichtbar; nach dem Wecken jederzeit wechselbar | Testfall |
| Ausrüstung & Wachstum | Abzeichen schalten Ausrüstungs-Overlays frei; Wachstumsstufen hängen am bestehenden XP-Level — kein neuer Zähler | Testfall |
| Keine Druckmechanik | Kein Hunger, kein Verfall, kein Verlust bei Inaktivität — nirgendwo | Codereview + Sichtprüfung |
| Ehrlichkeit | Er stellt sich als Computer-Tutor vor; keine Behauptung, ein Mensch oder echtes Tier zu sein | Sichtprüfung der Texte |
| Abschaltbar | Einstellungen: Avatar aus (Nachfragen enden mit ihm) | Testfall |
| Gewicht | ≤ 300 KB je Gefährten-Posen-Set, Ausrüstungs-Overlays ≤ 20 KB je Stück; V2.0 liefert nur den Starter in Stufe 1, der Rest kommt per OTA, wenn das Kind ihn freigespielt hat | Messung beim Bauen |

## D6 — Motivationssignale und der Tutor

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Abbruchgrund | s. D5 — erreicht den Tutor als eigenes Ereignis | Testfall |
| Spaß-Signal | Nach Paketende gelegentlich (max. 1×/Sitzung) ein 1-Tipp-Smiley — nie verpflichtend | Testfall |
| Tutor sieht Motivation | Der Tutor-Prompt enthält: Wochenmengen-Trend, 0/0-Sitzungen, Abbruchgründe, Spaß-Signale, Disziplin-Präferenzen | Sichtprüfung des Prompts |
| Tutor plant Pre-Lessons | Der Plan kann Ketten ausdrücken: Ziel-Fertigkeit + Vorlauf | Schema des Plans + Testfall |
| Elternseite | Neuer Abschnitt: Motivationslage in ganzen Sätzen — Menge, Abbrüche, Gründe, Spaß-Signal | Sichtprüfung |

## D7 — V1/V2-Schalter

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Optionsmenü | Einstellungen: „Klassisch (V1)" ↔ „Denkschule (V2)", sofort wirksam, jederzeit umkehrbar | Testfall |
| Kein Datenverlust | Lernstand ist gemeinsam; Umschalten verwirft nichts | Testfall |
| Voreinstellung | Nach dem Update: V2 | Sichtprüfung |

---

## Nordstern und Abnahme

Gemessen über **4 zusammenhängende Schulwochen** echter V2-Nutzung:

| Nordstern-Größe | Ziel | heute |
|---|---|---|
| Wochenmenge | ≥ 150 Antworten **(v)** | 74 (KW 35) |
| Sofort-Abbrüche (0/0-Sitzungen) | ≤ 15 % **(v)** | 36 % |
| Zielband 70–85 % je Sitzung | gilt weiter (Z5) | — |
| Mediane Antwortzeit | ≤ 20 s **(v)** bei gehaltener/steigender Denkstufe | 21–23 s |
| Spaß-Signal | ≥ 70 % positiv **(v)** | nicht gemessen |

Dazu hart: V0 erfüllt · D4-Garantie ohne Ausnahme · alle 5 Disziplinen
versorgt · Avatar-Kriterien aus D5 vollständig.

## Wochenplan (01.09.–14.09.2026)

**Woche 1 — Fundament (ohne das Kind):**

| Tag | Arbeitspaket |
|---|---|
| 1 | **V0**: Planauslieferung diagnostizieren, fixen, Testfall. D7-Schalter als Gerüst |
| 2–3 | D1-Disziplin-Sicht über das Curriculum; D4-Kerne: Logikgitter-Generator + Eindeutigkeitsprüfer, Folgen-Generator |
| 3–4 | App-Darstellungen: Logikgitter-UI, Bildmuster-Matrix, Hinweisliste mit Vorlesen; Algorithmik-Kern (Gitter-Roboter) |
| 4–5 | D5-Avatar: Design + Posen (Nano Banana), Präsenz-Engine, Taufe-Dialog, Nachfrage + Telemetrie; D2-Budget in Schema/Validator |
| 5–6 | D6: Tutor-Prompt-Ausbau, Pre-Lesson-Ketten; Erstbestückung V2-Vorrat (≥ 3 Disziplinen × ≥ 4 Pakete); Tests, APK, OTA |
| 7 | Puffer; Elternseite: Disziplin-Sicht + Motivationsabschnitt |

**Woche 2 — mit dem Kind (iterativ, per OTA):**

| Tag | Arbeitspaket |
|---|---|
| 8 | Das Kind startet V2, tauft den Avatar |
| 9–13 | täglich: Telemetrie und Tutorplan sichten, nachsteuern; Disziplinen 4–5 nachliefern (Raum & Form, Strategie); Nachfrage-Verhalten feinjustieren |
| 14 | Messung gegen den Nordstern, Bericht an Timo; (v)-Werte neu setzen beginnt |

## Ausdrücklich nicht Teil von V2.0

Echte Programmiersprache/Editor (Algorithmik läuft über Befehlskarten),
Mehrspieler oder Vergleich mit anderen Kindern, Video-Animationen des Avatars,
Erreichbarkeit außerhalb des Heimnetzes, Play-Store-Vertrieb.
