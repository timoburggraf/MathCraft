# ZIELE-V3 — Anschaulich statt Text, Geometrie, und ein Denk-Check

Stand 25.10.2026. Baut auf [ZIELE-V2.md](ZIELE-V2.md) auf; alle Leitplanken dort
gelten weiter (Schwierigkeit ist Denktiefe, Rechenlast-Budget D2, jede
V2-Aufgabe deterministisch geprüft, kein Sprachmodell im Kern-Pfad, die
Klassenstufe ist ein Boden und keine Decke, nichts Erzeugtes wird vernichtet).

## Ausgangslage (gemessen, 29.07.–17.09.2026, 668 Antworten)

- **Roboter** (algo_befolgen/algo_finden): alle Pakete zu Ende gespielt, nie
  weggetippt, einzige „super“-Bewertung. **Spiegeln** laut Rückmeldung der
  Eltern besonders beliebt (Daten liegen noch ungesynct auf dem Gerät).
- **Reihenfolgen** (komb_reihen@5, reine Textaufgaben „Wie viele
  Reihenfolgen …?“): 16× geöffnet, 13× in Sekunden weggetippt, 37 % richtig
  bei 12 s Median — geraten. Ein Elternwunsch „jetzt“ schob das Paket 14× vor;
  die Sofort-Abbruch-Pause galt nur 24 h, danach kam es sofort wieder.
- **Textlast:** 565 von 754 Aufgaben (75 %) sind Textaufgaben. In den fünf
  Denkdisziplinen sind es 205 von 354 (58 %). Was das Kind mag, hat ≤ 12 Wörter.
- **Geometrie** ist im Bestand fast nur Text (Umfang, Fläche, Körper) — die
  größte Lücke gegenüber dem Lehrplan der Klassen 3–5.

## G1 — Reihenfolgen und Auswahlen zum Anfassen: Aufgabentyp `legen`

Figuren (Emoji-Karten) werden durch Antippen auf Plätze gelegt. Die App
sammelt jede gefundene Anordnung, erkennt Doppelte und Regelverstöße. Modus
`alle`: das Kind sagt selbst „Das sind alle!“ — richtig, wenn wirklich alle
gefunden sind (Systematik ist der Denkweg). Modus `zaehlen`: Zahl eingeben,
das Brett darf zum Ausprobieren benutzt werden.

| Kriterium | Zielwert |
|---|---|
| Fertigkeiten | komb_reihen (geordnet, Stufe 4 und 5) und komb_paare (ungeordnet, Stufe 4 und 5) laufen über den Kern `legen_kern.py`; die alten Textpakete liegen im Fundus |
| Lösbarkeit | Modus `alle` nur bei Gesamtzahl 2…8; Gesamtzahl kommt aus vollständiger Aufzählung im Kern |
| Gleichheit | JS-Regelprüfung in `src/app.html` zählt für jede `legen`-Aufgabe im Bestand dieselbe Gesamtzahl wie der Kern (logic_test) |

## G2 — Weniger Text

Textaufgabe heißt hier: kein Bildtyp (`bildwahl`, `bildzahl`, `roboter`,
`positionen`, `logikgitter`, `gitter`, `ordnen`, `legen`) **und** mehr als 12
Wörter in der Frage.

| Kriterium | Zielwert |
|---|---|
| Anteil in den fünf Denkdisziplinen | ≤ 35 % Textaufgaben (vorher 58 % nach der alten, gröberen Zählung) — gemessen von `build/textlast.py` |
| Zahlenfolgen | must_einfach, must_schritt, must_rueck, must_wechsel, must_verdopp, must_fibo kommen als reine Zahlenfolge („3, 5, 9, 17, … Welche Zahl kommt als Nächstes?“) deterministisch aus raetsel_kern, ohne Sprachmodell-Geschichte |
| Bildfolgen | must_figur wird Punktmuster-Bildaufgabe (`bildzahl`, kern.art `punktmuster`) |
| Wer steht wo? | log_reihen@4 wird `positionen` (Kern wie log_position, 3–4 Figuren) |

## G3 — Geometrie Klasse 3–5, „📝 Papier erlaubt“

Fünf neue Fertigkeiten der Disziplin Raum & Form, je zwei Pakete (eigene
Stufe und Stufe+1), Kern `build/geo_kern.py`:

| Fertigkeit | Stufe | Inhalt | Typ |
|---|---|---|---|
| geo_ansicht | 4 | Würfelgebäude von oben / vorne / rechts — welches Bild stimmt? | bildwahl |
| geo_netzfalten | 4 | Welches Netz faltet sich zum Würfel? Welche Fläche liegt gegenüber? | bildwahl |
| geo_flaeche_umfang | 4 | Fläche und Umfang von Kästchenfiguren; Rechtecke mit vorgegebener Fläche/Umfang (📝) | bildzahl, zahl |
| geo_quader | 5 | Wie viele Würfel fehlen bis zum vollen Quader? | bildzahl |
| geo_karte | 5 | Schatzkarte: Koordinaten, Wege, Maßstab (📝) | bildwahl, bildzahl |

Aufgaben mit `"papier": true` zeigen „📝 Papier und Stift erlaubt“. Papier
dient Skizzen und Zwischenergebnissen, nicht langen Rechnungen: die Zahlen
bleiben klein, das D2-Budget gilt unverändert.

## G4 — Der Denk-Check (Screening)

Fachliche Grundlage: das Merkmalssystem mathematisch begabter Grundschulkinder
von Käpnick (Klasse 3/4) mit seinen Indikatoraufgaben; die Empfehlung der
Begabungsforschung, ein Screening nur als Einstieg in eine längere
Prozessbeobachtung zu nutzen (PriMa Hamburg, Prozessdiagnostik); Aufgaben
möglichst ohne Lesen (wie die CogAT-Kurzform); adaptive Vorgabe, die mit
einem Bruchteil der Aufgaben auskommt.

**Was er nicht ist:** kein IQ-Test, keine Norm, kein Vergleich mit anderen
Kindern. Er liefert ein Stärken-Schwächen-Profil des Kindes in sich und
Startstufen je Disziplin.

| Dimension (Schlüssel) | nach Käpnick | Aufgaben aus | Boden für Disziplin |
|---|---|---|---|
| strukturen | Strukturen erkennen und nutzen | Bildmatrix (2–5), Analogie (6–8) | muster |
| schlussketten | mit Komplexität umgehen | positionen (3–6 Figuren) | logik |
| algorithmik | (V2-Disziplin) | roboter | algorithmik |
| darstellung | Wechsel der Repräsentationsebenen | Punktmuster → Zahl | — |
| raum | räumliches Vorstellungsvermögen (nur Interessenwert) | Spiegeln, Drehen, Würfelgebäude | raum |
| umkehren | Umkehrbarkeit von Gedankengängen | Zahlenmaschine rückwärts | — |
| merken | Speichern mit Hilfe erkannter Strukturen | Merkbild (5 s zeigen, dann wählen) | — |
| systematik | systematisches Probieren | legen | kombinatorik |
| rechnen | Schulstoff-Anker | reine Rechenaufgaben | — |

| Kriterium | Zielwert |
|---|---|
| Dauer | zwei Runden (A: strukturen, schlussketten, algorithmik, darstellung, raum; B: umkehren, merken, systematik, rechnen), je ≤ 12 min; jederzeit unterbrechbar und fortsetzbar |
| Verfahren | je Dimension 4 Aufgaben im beschleunigten Treppenverfahren: Start eine Stufe unter dem Klassen-Einstieg; richtig → +2, solange noch kein Fehler kam, danach richtig → +1; falsch → −1; Stufen 2…8 (sonst könnte ein starkes Kind mit 4 Aufgaben gar nicht oben ankommen) |
| Schätzung | E = (höchste richtig gelöste Stufe + niedrigste darüberliegende falsch gelöste) / 2; gibt es über der höchsten richtigen keine falsche: höchste richtige + 0,5 und Vermerk „Decke nicht erreicht“ (z = 1); nie richtig: niedrigste versuchte − 0,5 und z = −1 |
| Bedingungen | alles vorgelesen, keine sichtbare Zeit, neutrale Rückmeldung (kein Rot), Aufgaben aus einer festen, geprüften Aufgabenbank (`data/denkcheck.json`, jede Aufgabe durch validate.check_task) |
| Wirkung | Boden je Disziplin = ⌊E⌋ − 1 (eine Stufe unter dem Gezeigten, wie bei der Klasse); Lernstand (Sterne, Leitner) bleibt unberührt |
| Kind | sieht nur seine Stärken („Deine Superkräfte“), nie eine Schwäche |
| Eltern | Profil aller Dimensionen mit Stufe, Treffern, Median-Zeit, Datum und dem Hinweis, was der Check nicht ist; Wiederholung frühestens nach 90 Tagen vorgeschlagen |
| Elternbogen | Beobachtungsbogen zu begabungsstützenden Eigenschaften (Freude am Knobeln, Ausdauer, Selbstständigkeit, eigene Ideen, Merkfähigkeit, Begründen, Gespür für Unstimmigkeiten, Konzentration, Umgang mit Misserfolg), je 1–4, gespeichert mit Datum |

## G5 — Wunsch-Bremse

| Kriterium | Zielwert |
|---|---|
| Pause | Ab dem 3. Sofort-Abbruch in Folge verdoppelt sich die Pause je weiterem Abbruch: 1, 2, 4, 8, höchstens 14 Tage |
| Elternseite | Ein aktiver Wunsch, dessen Pakete seit dem Wunsch ≥ 3× sofort weggetippt wurden, zeigt das mit Anzahl und schlägt das Zurücknehmen vor |

## Datenformate (verbindlich für alle Umsetzer)

### `legen`

```json
{"type": "legen", "q": "Lege alle Reihenfolgen. Der Fuchs steht nie ganz vorne.",
 "figuren": [{"name": "Fuchs", "bild": "🦊"}, {"name": "Eule", "bild": "🦉"}, {"name": "Golem", "bild": "🗿"}],
 "plaetze": 3, "geordnet": true, "modus": "alle",
 "regeln": [{"art": "nicht_platz", "a": 0, "platz": 0}],
 "a": 4, "kern": {"art": "legen", "n": 3, "plaetze": 3, "geordnet": true, "regeln": [...], "anzahl": 4},
 "hint": "Fang mit der Eule vorne an und probier alles dahinter."}
```

- Eine Anordnung ist eine Liste von `plaetze` verschiedenen Figur-Indizes.
  `geordnet: false` heißt Auswahl: Anordnungen mit derselben Menge sind gleich.
- Regeln (Indizes in `figuren`, Plätze ab 0 von vorne bzw. links):
  `nicht_platz {a, platz}` — a steht nicht auf diesem Platz;
  `auf_platz {a, platz}`; `direkt_hinter {a, b}` — a steht direkt hinter b
  (Platz a = Platz b + 1); `nebeneinander {a, b}`; `nicht_nebeneinander {a, b}`;
  `zusammen {a, b}` — a ist genau dann dabei, wenn b dabei ist;
  `nicht_zusammen {a, b}` — nie beide dabei. Bei geordnet nur die ersten fünf,
  bei ungeordnet nur `zusammen`/`nicht_zusammen` und `dabei {a}`/`nicht_dabei {a}`.
  Eine Regel, deren Figur nicht gelegt ist, gilt als erfüllt (außer `zusammen`, `dabei`).
- `modus: "alle"` nur bei `a` ∈ 2…8. `modus: "zaehlen"`: Antwort ist `a`.
- Figurenvorrat (Nominativ/Dativ für die Sätze im Kern):
  Fuchs 🦊 m, Eule 🦉 f, Golem 🗿 m, Katze 🐱 f, Drache 🐲 m, Biene 🐝 f.

### `bildzahl` / `bildwahl` — neue kern.art

`ansicht`, `netzfalten`, `gitterfigur`, `quader`, `karte` (geo_kern),
`punktmuster`, `merkbild` (figur_kern). Jede Art hat ein `pruefe_<art>(kern)
-> (ok, grund)`, das die Wahrheit ohne das SVG neu berechnet.
`bildzahl` darf künftig jede dieser Arten tragen (bisher nur `wuerfelgebaeude`).

### Neue Felder an Aufgaben

- `"papier": true` — Papier und Stift erlaubt (Anzeige in der App).
- `"merken_ms": 5000` — nur bei bildwahl: Fragebild so lange zeigen, dann
  ausblenden; erst danach erscheinen die Optionen.

### `data/denkcheck.json`

```json
{"version": 1, "dimensionen": {"strukturen": {"titel": "Muster und Strukturen", "runde": "A", "boden": "muster"}, ...},
 "aufgaben": [{"id": "strukturen-4-1", "dim": "strukturen", "stufe": 4, "task": {<gewöhnliche Aufgabe>}}, ...]}
```

Je Dimension und Stufe 2…8 mindestens zwei Aufgaben (bei Wiederholung des
Checks werden unbenutzte bevorzugt). Gesamtgröße ≤ 1 MB.

### Ereignisse

- Antworten im Denk-Check: gewöhnliches `"a"` mit `u: "denkcheck"`; die
  Auswertung auf dem Heim-Dienst zählt sie **nicht** in die Fertigkeiten-Statistik.
- Ergebnis je Dimension: `"c"` mit `i, t, s, k` (Dimension), `g` (Schätzung E,
  Zahl), `n` (Aufgaben), `c` (richtig), `ms` (Median-Dauer), `z` (1 = Decke
  nicht erreicht, −1 = Boden nicht erreicht, 0 sonst).

## Abnahme

Alle Testsuiten grün (auch wunsch_test, eltern_test und smoke_test, die seit
der Sicherheitsumstellung rot bzw. hängend waren), Bildschirmfotos im
Handyformat je neuem Aufgabentyp, unabhängige Gegenprüfung, Fassung auf dem
Heim-Dienst ausgerollt und dort nachgewiesen.
