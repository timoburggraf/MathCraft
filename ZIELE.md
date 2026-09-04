# Zielbeschreibung — Adaptiver Tutor mit Elternseite

*Aufgestellt am 29.07.2026. Die Ausgangslage ist gemessen, nicht geschätzt.*

> **Nachtrag vom 29.07.2026, nach Umsetzung von Z1–Z6.** Z5 beschrieb einen
> Tutor, der nach festen Schwellen entscheidet. Auf ausdrückliche Entscheidung
> von Timo Burggraf entscheidet jetzt ein Sprachmodell — allein, ohne dass eine
> Schwelle es überstimmen kann. Was das ändert, steht in **Z7** am Ende; die
> Schwellen aus Z5 gelten weiter als Rückfall, solange kein Plan vorliegt, und
> als Maßstab der Elternseite.

## Zielbild

Der Dienst zu Hause sieht, was das Kind tut, stellt den Aufgabenvorrat daraufhin
selbständig um, erklärt ihm bei Bedarf den Weg an einem Beispiel — und die
Elternseite macht beides sichtbar und steuerbar: sie zeigt, was sitzt und was
hakt, warum der Tutor umgestellt hat, und nimmt Wünsche entgegen, die
nachweislich wirken.

## Ausgangslage, gemessen am 29.07.2026

| Größe | Wert |
|---|---|
| Curriculum | 11 Bereiche, 77 Fertigkeiten, 8 Stufen |
| Vorrat | 67 Pakete, 536 Aufgaben, durchgehend 8 Aufgaben je Paket |
| Stufenabdeckung | Stufen 1–6 belegt; Stufe 7 (8 Fertigkeiten) und 8 (2) haben **null** Pakete |
| Fertigkeiten ohne jedes Paket | **10 von 77** |
| Aufgabentypen | `zahl` 262 (49 %), `wahl` 151 (28 %), `entdecken` **2** — stark schief |
| Lernstand | ausschließlich `localStorage` auf dem Gerät (`src/app.html:338`, `:371`) |
| Dienst | 4 Routen: `/`, `/health`, `/version`, `/app.apk`. Kein `/sync`, kein `/eltern` |
| Adaptivität heute | `nextUnit()` wählt nach `stars<2`, Zielstufe je Bereich, Weltwechsel, wenig gespielt. Wiederholung per Leitner, Abstände 0/0/1/3/7/21 Tage |
| Ablehnungsprotokoll | `data/verworfen.json`, 1 Eintrag |

**Der entscheidende Punkt:** Auf dem Server liegen null Nutzungsdaten. Jede
Aussage über das Kind ist heute unbelegbar.

## Warum ein Teil der Zielwerte vorläufig ist

Zielwerte für Trefferquoten, Abbruchraten oder Sitzungslängen lassen sich nicht
seriös festlegen, solange keine Messung existiert. Die unten mit **(v)**
markierten Werte sind fachlich begründete Startannahmen und werden nach
**14 Tagen Realdaten** einmalig auf die dann gemessene Basis neu gesetzt. Alles
ohne Markierung ist ein hartes Ziel, das nicht von Basisdaten abhängt.

---

## Z1 — Datengrundlage: der Lernstand erreicht den Dienst

*Ohne dieses Ziel ist kein anderes messbar.*

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Ereignis je beantworteter Aufgabe mit `unitId`, `skillId`, `stage`, `type`, richtig/falsch, Antwortdauer in ms, Versuche, Tipp benutzt, Zeitstempel | 100 % der Antworten | Abgleich `stats.answers` auf dem Gerät gegen Ereigniszahl im Dienst, Abweichung 0 |
| Übertragung nach WLAN-Kontakt | ≥ 95 % der Ereignisse binnen 24 h | Zeitstempeldifferenz Erzeugung → Eingang |
| Verlust bei Offline-Betrieb | 0 Ereignisse bei bis zu 90 Tagen ohne WLAN | Testlauf mit simulierter Offline-Phase |
| Doppelte Übertragung | Ereigniszahl bleibt bei wiederholtem Sync konstant | zweimal `/sync` mit gleicher Nutzlast |
| Dauer und Größe | < 2 s, < 200 KB für 30 Tage Daten | Messung am Endpunkt |
| Datenschutz | Kein Klarname, keine Freitexte des Kindes verlassen das Gerät | Prüfung der Nutzlast im Test |
| Mehrere Geräte | Je Gerät ist ablesbar, wie viel es beigesteuert hat und ob seine Zählung aufgeht; ein Testgerät lässt sich aus der Auswertung nehmen, ohne seine Aufzeichnung zu löschen | Testfall und Sichtprüfung |

## Z2 — Elternseite: sehen, was gut und was schlecht läuft

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Abdeckung | Alle 77 Fertigkeiten haben einen Zustand: *sitzt* / *hakt* / *in Arbeit* / *noch nicht geübt* — keine Leerstellen | Abzählen auf der Seite |
| Definition **sitzt** | ≥ 10 Antworten und ≥ 90 % richtig | fest verdrahtete Regel, auf der Seite dokumentiert |
| Definition **hakt** | ≥ 6 Antworten und ≤ 50 % richtig, **oder** 3 Fehlversuche in Folge | dito |
| Verlauf | Trefferquote je Bereich über 8 Wochen, Wochenauflösung | Diagramm vorhanden |
| Ladezeit | < 1 s bei 90 Tagen Daten | Messung |
| Verständlichkeit | Jede Kennzahl trägt ihre Definition im Klartext daneben, keine nackten Prozentwerte | Sichtprüfung |
| Erster Blick | Ganz oben steht das Fazit in ganzen Sätzen: wie viel geübt wurde, ob es zu leicht oder zu schwer war, was hakt. Alles darunter ist Beleg | Sichtprüfung |
| Arbeitssprache | Kein interner Bezeichner (`geo_umfang`) im Fließtext — auch nicht in dem, was der Tutor schreibt | Sichtprüfung |
| Technik zuletzt | Zählstände, Geräte und Vorratslücken stehen aufgeklappt erst am Seitenende | Sichtprüfung |

## Z3 — Nachvollziehen, was der Tutor geändert hat

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Lückenlosigkeit | Jede Anpassung erzeugt einen Protokolleintrag: Zeitpunkt, Art, Begründung, Zahlen, auf denen sie beruht | Anzahl Anpassungen = Anzahl Einträge, keine Ausnahme |
| Arten | vorgezogen · zurückgestellt · neu erzeugt · übersprungen · vom Prüfer abgelehnt | alle fünf im Protokoll darstellbar |
| Darstellung | Die letzten 20 Entscheidungen in je einem deutschen Satz mit Beleg | Sichtprüfung |
| Ablehnungen | `data/verworfen.json` erscheint auf der Seite, inklusive Versuchsprotokoll | heute 1 Eintrag, muss sichtbar sein |

## Z4 — Elternwünsche, die nachweislich wirken

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Wunscharten je Bereich und Fertigkeit | *mehr davon* · *weniger davon* · *erst später* · *jetzt dran* | alle vier bedienbar |
| Wirksamkeit | Der Wunsch beeinflusst spätestens das **2. Paket** nach dem nächsten Sync | Protokoll Z3 weist den Wunsch als Begründung aus |
| Rückmeldung | Die Seite zeigt die Wirkung in Zahlen: „seit deinem Wunsch: 12 Aufgaben in *Mal & Geteilt*, 8 richtig" | Sichtprüfung |
| Schutz vor Fehlgriffen | *jetzt dran* auf eine Stufe > 1 über dem aktuellen Niveau wird angezeigt und begründet gewarnt, nicht stillschweigend ausgeführt | Testfall |
| Rücknehmbarkeit | Jeder Wunsch ist mit einem Tipp widerrufbar, Wirkung endet binnen 1 Paket | Testfall |

## Z5 — Adaptivität, die Langeweile und Überforderung messbar vermeidet

Das ist der inhaltliche Kern, und der einzige Bereich, in dem heute
nachweislich zu wenig passiert.

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| **Nordstern:** Anteil Aufgaben im Zielband 70–85 % Trefferquote je Sitzung | ≥ 70 % der Sitzungen im Band **(v)** | rollierend über 4 Wochen |
| Definition **langweilig** | Fertigkeit mit Leitner-Stufe ≥ 4 und ≥ 90 % richtig in den letzten 10 Antworten | feste Regel |
| Anteil langweiliger Aufgaben am Vorgelegten | ≤ 10 % **(v)** — jenseits der Leitner-Wiederholung, die davon ausgenommen bleibt | aus Z1-Daten |
| Definition **zu schwer** | ≤ 40 % richtig in den letzten 6 Antworten einer Fertigkeit | feste Regel |
| Verhalten bei *zu schwer* | Fertigkeit wird zurückgestellt, die Vorbedingung zuerst vorgelegt; Rückkehr erst bei ≥ 70 % in der Vorbedingung | Protokoll Z3 belegt die Kette |
| Abbrüche | Sitzungen mit < 5 Antworten ≤ 15 % **(v)** | aus Z1-Daten |
| Vorratsdeckung | Für jede Fertigkeit, die das Kind binnen 4 Wochen erreichen kann, existiert ≥ 1 Paket — heute reißt die Kette bei Stufe 7 | Abgleich Curriculum gegen `units_seed.json`; **10 von 77 Fertigkeiten sind heute unversorgt, Ziel 0** |
| Typenmischung | Kein Aufgabentyp über 35 % des Vorgelegten — heute liegt `zahl` bei 49 % | Auszählung |

## Z6 — Erklärung am Beispiel per LLM *(später, nach Z1–Z5)*

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Auslöser | Auf Wunsch ab dem 1. Fehler über den Knopf *Erklär es mir*, von allein ab dem 2. Fehlversuch an derselben Aufgabe | Testfall |
| Zurückhaltung | Kein Knopf bei richtiger Antwort und keiner, wenn kein Rechner eingetragen ist — er darf nie ins Leere führen | Testfall |
| Inhalt | Erklärung an einer **gleichartigen** Aufgabe, nicht die Lösung der vorliegenden | Stichprobe 20 Erklärungen, 20 erfüllen es |
| Schlüsselhaltung | Kein API-Schlüssel auf dem Kindergerät, Aufruf ausschließlich über den Heim-Dienst | Prüfung der APK, binäres Kriterium |
| Rechenprüfung | Das Beispiel wird wie die Pakete nachgerechnet; was nicht aufgeht, wird verworfen | ≥ 95 % bestehen, Rest fällt auf den statischen `hint` zurück |
| Antwortzeit | ≤ 3 s bis zum ersten Wort, ≤ 6 s vollständig | Messung |
| Rückfall ohne Dienst | Statischer `hint` erscheint, keine Fehlermeldung | Testfall offline |
| Wirkung | Trefferquote in der nächsten Aufgabe derselben Fertigkeit ≥ 60 % **(v)** | aus Z1-Daten |

## Z7 — Der Tutor entscheidet selbst *(Nachtrag, ersetzt die Entscheidungshoheit aus Z5)*

Ein Sprachmodell sieht sich den ganzen Verlauf an und stellt den Plan auf. Es
entscheidet allein: Keine Schwelle aus Z5 kann es überstimmen. Will es eine
Fertigkeit sechs Stufen über dem Stand des Kindes, bekommt es sie.

Der Grund für diese Setzung ist ein gemessener: Beim ersten Lauf über echte
Daten fand das Modell, dass drei voneinander unabhängig einbrechende
Fertigkeiten — Fläche 37 %, Zerlegen 30 %, Tabellenrechnen 39 % — dieselbe
Ursache haben: Malnehmen und Teilen wurden nie geübt, kein einziges Paket. Die
Schwellen aus Z5 hätten jede einzeln zurückgestellt und den Zusammenhang nie
gesehen, weil sie je Fertigkeit prüfen.

| Kriterium | Zielwert | Messverfahren |
|---|---|---|
| Entscheidungsfreiheit | Kein Plan wird wegen seiner Kühnheit abgeschwächt oder verworfen | Testfall mit einem Sprung über mehrere Stufen; er muss unverändert durchkommen |
| Betriebssicherheit | Eine Fertigkeit, die es nicht gibt, wird übergangen — und dabei auf der Elternseite benannt | Testfall mit erfundener Kennung |
| Sichtbarkeit | Beobachtung, Elternabsatz und jede Entscheidung mit **seiner eigenen** Begründung stehen auf der Elternseite, nicht in einer Schablone | Sichtprüfung |
| Widerspruch | Ein Elternwunsch schlägt den Plan, spätestens im 2. Paket | Testfall |
| Warnung ohne Sperre | Ein Sprung über mehr als eine Stufe wird angezeigt und **trotzdem ausgeführt** | Testfall |
| Reihenfolge | Sein Plan ist nach Wichtigkeit geordnet, und das Gerät hält sich daran. Die Niveau-Sortierung darf ihn nicht umstellen — sonst kommt jeder Einstieg auf niedriger Stufe nie an die Reihe | Testfall: eine niedrigstufige Fertigkeit vorn im Plan schlägt eine höherstufige dahinter |
| Rückmeldung | Er sieht bei jedem Nachdenken, welche Pakete seit seinem letzten Plan tatsächlich gestellt wurden — sonst rät er über die Gründe | Sichtprüfung des Auszugs |
| Lückenlosigkeit | Jede seiner Entscheidungen erzeugt einen Protokolleintrag mit Quelle „Tutor" | wie Z3 |
| Anlass | Er denkt nach, wenn ≥ 20 neue Antworten vorliegen oder der Plan älter als 20 Stunden ist | Testfall |
| Kosten | **rund 13 Cent je Aufruf** (gemessen: 4.630 Token rein, 4.746 raus), bei täglichem Lauf etwa 4 EUR im Monat | Abrechnung |

**Was damit bewusst aufgegeben wird:** Eine didaktische Fehlentscheidung ist
nicht nachrechenbar. Bei `12+5 = 18` schlägt der Prüfer zu; bei „ich stelle
Sachaufgaben zurück" gibt es nichts zu prüfen — eine falsche Einschätzung sieht
aus wie eine richtige. Die Absicherung ist deshalb keine technische, sondern
eine menschliche: Alles steht auf der Elternseite, und wer widerspricht, gewinnt.

---

## Abnahme

Das Gesamtziel gilt als erreicht, wenn über **4 zusammenhängende Wochen echter
Nutzung**:

1. Z1 bis Z5 alle harten Kriterien erfüllen,
2. der Nordstern aus Z5 auf dem nach 14 Tagen neu gesetzten Basiswert liegt
   oder darüber,
3. null Fertigkeiten unversorgt sind (heute 10),
4. mindestens **drei** Elternwünsche gestellt wurden und ihre Wirkung auf der
   Seite nachweisbar ist.

Z6 wird getrennt abgenommen.

## Reihenfolge

Z1 → Z2 → Z3 → Z5 → Z4 → Z6.

Z5 vor Z4, weil ein Elternwunsch erst dann etwas Sinnvolles steuern kann, wenn
die automatische Steuerung überhaupt existiert.

## Ausdrücklich nicht Teil des Ziels

Erreichbarkeit von außerhalb des Heimnetzes, mehrere Kinder, Konten oder
Anmeldung, Play-Store-Vertrieb, Sprachausgabe der Erklärungen.
