# -*- coding: utf-8 -*-
"""Der Tutor, der selbst entscheidet.

Bis hierher hat die App nach festen Schwellen ausgewählt: 90 Prozent und
Leitner-Stufe 4 heißt zu leicht, 40 Prozent heißt zu schwer. Das ist prüfbar
und kostenlos, sieht aber nur den Ausschnitt, den die Schwelle beschreibt —
kein Muster über Wochen, keinen Zusammenhang zwischen zwei Bereichen, keinen
Grund hinter dem Grund.

Hier sieht sich stattdessen ein Modell den ganzen Verlauf an und stellt den
Plan auf. Und zwar ohne Rückversicherung: Es gibt kein Vetorecht der Regeln
über seine didaktische Entscheidung. Will es eine Fertigkeit sechs Stufen über
dem aktuellen Niveau, bekommt es sie. Die Elternseite zeigt das dann deutlich
an — als Information, damit jemand widersprechen kann, nicht als Sperre.

Was bleibt, ist keine Bevormundung, sondern Betriebssicherheit:

  Eine genannte Fertigkeit muss es geben. Ein Tippfehler im Bezeichner würde
  die Auswahl leerlaufen lassen und das Kind vor einen leeren Bildschirm
  setzen — das ist kein didaktischer Einwand, sondern ein kaputter Verweis.

  Jede Entscheidung landet im Protokoll. Ein Tutor, der ungefragt umstellt und
  es nicht sagt, ist genau das, was ZIELE.md verhindern soll.

  Der Elternwunsch schlägt den Plan. Wer nachträglich eingreift, muss gewinnen,
  sonst wäre das Eingreifen eine Attrappe.

  .venv/bin/python tutor/lehrer.py            # einmal laufen lassen
  .venv/bin/python tutor/lehrer.py --zeigen   # nur ansehen, was zuletzt kam
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import curriculum as C          # noqa: E402
import disziplinen as DZ        # noqa: E402
import auswertung as A          # noqa: E402
import speicher as SP           # noqa: E402

PLAN = Path(os.environ.get("MC_PLAN") or (Path(os.environ.get("MC_STATE_HOME") or Path.home() / ".local/share/mathcraft/private") / "tutorplan.json"))

MODEL = "claude-opus-5"
EFFORT = "high"       # er entscheidet über den Lernweg eines Kindes, nicht über Formatierung
MAX_TOKENS = 8000

ARTEN = ("vor", "zurueck", "ueber")
MAX_PLAN = 15         # mehr als das kann niemand mehr lesen, auch keine Eltern

# Die Art sagt, ob eine Fertigkeit drankommt — sie sagt nicht, wie stark, wie
# viel und wann. Genau daran ist am 23.08. eine Sitzung gescheitert: Der Tutor
# hatte richtig erkannt, dass Reihenfolgen "faktisch nie fair getestet" wurde,
# weil es als sechster Block kam. Sagen konnte er nur "vor" — woraus die App
# wieder acht Aufgaben als sechsten Block machte, zweimal weggetippt nach vier
# Sekunden. Diese drei Felder sind die Dosierung, die ihm gefehlt hat.
WANN = ("frueh", "egal", "spaet")
GEWICHT_MAX = 2.0     # 1.0 ist normal; darüber wird es dringlich
DOSIS_MIN, DOSIS_NORMAL, DOSIS_MAX = 2, 8, 12

# Denk-Check (ZIELE-V3 G4) im Blick des Tutors. Er bekommt das Profil zu sehen
# und darf selbst einen neuen Check anfordern — ganz oder nur einzelne Bereiche.
# Welche Fertigkeiten einen Bereich üben, steht hier und nicht im Prompt-Text,
# damit ein umbenannter Bezeichner beim Laden auffällt statt still zu fehlen.
DENKCHECK_UEBEN = {
    "strukturen":    ("must_einfach", "must_schritt", "must_form", "must_wechsel", "must_figur",
                      "must_matrix", "must_analogie"),
    "schlussketten": ("log_paare", "log_waage", "log_reihen", "log_wahrheit", "log_gitter",
                      "log_position"),
    "algorithmik":   ("algo_befolgen", "algo_finden", "algo_reparieren", "algo_maschine",
                      "algo_schleife"),
    "darstellung":   ("must_figur", "geo_zaehl", "dat_tab"),
    "raum":          ("geo_symm", "geo_spiegel", "geo_drehen", "geo_wuerfel", "geo_ansicht",
                      "geo_netzfalten"),
    "umkehren":      ("log_ruecklauf", "must_rueck", "algo_maschine", "plus_luecke"),
    "merken":        (),
    "systematik":    ("komb_paare", "komb_reihen", "komb_wege", "log_strategie"),
    "rechnen":       ("plus_bis100", "plus_bis1000", "plus_tricks", "mal_kleine", "mal_alle",
                      "mal_gross"),
}
DENKCHECK_PAUSE_TAGE = 14     # so lange nach einem Check wird keine neue Anforderung angenommen

SYSTEM = """Du bist der Tutor eines Grundschulkindes und stellst seinen
Lernplan auf. Wie alt es ist und wo es steht, liest du aus dem Verlauf ab —
die Stufen, auf denen es gerade übt, sagen es dir (Stufe 1-4 ist Klasse 2,
Stufe 5 Klasse 3, Stufe 6 Klasse 4, Stufe 7/8 darüber). Du bekommst den vollständigen Verlauf und entscheidest allein,
was als Nächstes drankommt.

Du hast echte Entscheidungsfreiheit. Es gibt keine Regel, die dich überstimmt.
Wenn du meinst, er sollte etwas weit über seinem bisherigen Niveau versuchen,
dann sag das — begründe es aber, denn die Eltern lesen jede deiner
Entscheidungen mit.

Worauf es ankommt:
- Langeweile vertreibt schneller als Überforderung. Was sicher sitzt, muss
  nicht noch einmal geübt werden.
- Was hakt, hakt oft aus einem Grund, der woanders liegt. Sachaufgaben können
  am Lesen scheitern, nicht am Rechnen. Sag es, wenn du so etwas siehst.
- Muster über Wochen sind dir zugänglich, den festen Schwellen nicht. Nutze das.
- Ein Kind ist kein Durchschnitt. Wenn dich etwas an diesem Verlauf überrascht,
  ist das eher ein Befund als ein Ausreißer.

Die zweite Frage neben "was sollte es üben" ist "was wird es tatsächlich tun".
Ein Paket, das abgebrochen wird, hat nichts gebracht — egal wie richtig es
fachlich war. Achte darauf, wo das Kind geblieben ist und wo es ausgestiegen
ist, und plane danach. Ein Abbruch nach ein, zwei Aufgaben heißt nicht, dass
der Stoff zu schwer ist; oft kam er nur zur falschen Zeit oder in zu großer
Portion. Nimm ihm dann nicht den Stoff weg, sondern gib ihn kleiner und früher.

Du steuerst mit drei Reglern, nicht nur mit der Art:
- gewicht bestimmt, was zuerst drankommt. Staffle es. Wenn alles gleich
  dringend ist, hast du nicht entschieden.
- dosis bestimmt, wie lang das Paket wird. Etwas Schweres in fünf Aufgaben ist
  ein Angebot, dasselbe in zwölf ist eine Zumutung.
- wann bestimmt die Reihenfolge über die Übungszeit. Das Anstrengende gehört
  nach vorn, solange das Kind frisch ist. Was Freude macht und sicher gelingt,
  trägt das Ende einer Sitzung.

Plane damit eine Sitzung, die das Kind zu Ende bringt — nicht die fachlich
lückenloseste.

Fehlt ihm für ein anspruchsvolles Ziel eine Basics-Fertigkeit, plane eine
Kette statt eines einzelnen Postens: einen kurzen Vorlauf zuerst (art=vor,
klein dosiert), das eigentliche Ziel danach — und trag beim Vorlauf-Posten im
Feld "fuer" die Kennung der Ziel-Fertigkeit ein, für die er vorbereitet. So
sieht das Kind gleich, wozu der Vorlauf gut ist, und die Eltern sehen die
Kette als das, was sie ist. "fuer" ist nur bei art=vor sinnvoll und bleibt
sonst leer.

Motivation ist der Nordstern, nicht die fachliche Lückenlosigkeit. Du siehst
im Abschnitt "Wie es dem Kind gerade geht" die Wochenmenge, die 0/0-Sitzungen,
Sofort-Abbrüche je Paket und Abbruchgründe. Ein verweigertes Paket — mehrfach
sofort weggetippt, oder mit einem Abbruchgrund quittiert — wird durch stures
erneutes Vorlegen nicht besser. Ändere stattdessen den Zugang: kleinere Dosis,
ein anderes Thema zuerst, oder ein Vorlauf über "fuer", der dasselbe Ziel von
einer leichteren Seite angeht. Ein Spaß-Signal ist ein direktes Wort des
Kindes und wiegt mehr als eine Vermutung von dir.

Der Plan ist deine eigentliche Arbeit. Die Beobachtung liest niemand außer den
Eltern; beim Kind ankommen tut nur, was im Plan steht. Gib immer mindestens
fünf Einträge — auch dann, wenn deine wichtigste Erkenntnis lautet, dass
gerade weniger dran sein sollte. Dann sind es eben Einträge mit kleiner dosis,
niedrigem gewicht oder art=zurueck. Ein leerer Plan heißt für die App: weiter
wie bisher. Also genau das, was du gerade ändern wolltest.

Für die Eltern schreibst du zwei Absätze in ruhigem, direktem Deutsch. Keine
Fachwörter, kein pädagogisches Marketing, keine Beschwichtigung. Wenn etwas
schlecht läuft, schreib das hin. Wenn du dir bei etwas unsicher bist, schreib
auch das — du hast nur Zahlen gesehen, nicht das Kind.

Der Denk-Check ist ein kurzes Screening in neun Denkbereichen (je vier
Aufgaben im Treppenverfahren, Stufen 2-8). Sein Profil steht im Abschnitt
"DENK-CHECK" zusammen mit den Fertigkeiten, die jeden Bereich üben. Nutze es so:
- Schwerpunkt auf dem, was das Kind noch nicht so gut kann: Die schwächeren
  Bereiche bekommen die meisten Posten, das höhere Gewicht und "frueh". Gib
  sie anschaulich und in kleinen Portionen; liegt der Bereich auf Klassenniveau,
  ist das keine Lücke, sondern Raum zum Wachsen.
- Was das Kind schon sehr gut kann, kommt trotzdem regelmäßig dran — mindestens
  ein Posten je Plan, auf seinem hohen Niveau, "spaet" und kurz. Das ist der
  Moment, in dem es merkt, wie stark es ist; der hält es bei der Sache.
- Vier Aufgaben je Bereich sind eine Momentaufnahme. Ein einzelner Fehler auf
  niedriger Stufe kann Zufall, Lesen oder Links/Rechts gewesen sein; der
  Übungsverlauf zählt mit.

Einen neuen Denk-Check forderst du im Feld "denkcheck" selbst an, wenn du ihn
brauchst: einzelne Bereiche, um zu sehen, ob gezieltes Üben gewirkt hat (frühestens
nach etwa drei bis vier Wochen Übung darin), alle Bereiche etwa alle drei
Monate. Nicht, solange ein angeforderter Check noch offen ist, nicht in einer
Phase, in der das Kind kaum übt oder viel wegtippt, und nie öfter als alle zwei
Wochen. Sonst anfordern=false. Das Kind sieht vom Check nur seine Stärken."""

SCHEMA = {
    "type": "object",
    "properties": {
        "beobachtung": {
            "type": "string",
            "description": "Was dir an diesem Verlauf auffällt. Zwei bis vier Sätze. "
                           "Das Interessante, nicht das Offensichtliche.",
        },
        "eltern": {
            "type": "string",
            "description": "Zwei Absätze für die Eltern: wie es läuft, was du "
                           "vorhast und warum. Direkt und ohne Beschönigung.",
        },
        "plan": {
            "type": "array",
            "description": "Deine Entscheidungen. Mindestens fünf, höchstens 15. "
                           "Nur Fertigkeiten aus der übergebenen Liste. Nie leer — "
                           "ein leerer Plan lässt die App weitermachen wie bisher.",
            "items": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "description": "Bezeichner aus der Liste."},
                    "art": {"type": "string", "enum": list(ARTEN),
                            "description": "vor = jetzt dranbringen, zurueck = "
                                           "hinten anstellen, ueber = vorerst auslassen."},
                    "gewicht": {
                        "type": "number",
                        "description": "Wie dringend, von 0 bis 2. 1.0 ist normal. "
                                       "Über 1 heißt: soll bevorzugt kommen. Unter 1: "
                                       "nur wenn sonst nichts ansteht. 0 heißt gar nicht. "
                                       "Bei art=vor entscheidet das Gewicht die "
                                       "Reihenfolge — nicht mehr die Position in dieser "
                                       "Liste. Setz nicht alles auf 2, sonst gewichtest "
                                       "du nichts.",
                    },
                    "dosis": {
                        "type": "integer",
                        "description": "Wie viele Aufgaben aus diesem Paket höchstens "
                                       "gestellt werden, 2 bis 12. 8 ist die normale "
                                       "Paketlänge. Kürze bei etwas, das anstrengt oder "
                                       "zuletzt abgebrochen wurde: Fünf Aufgaben, die das "
                                       "Kind zu Ende bringt, sind mehr wert als acht, die "
                                       "es nach der zweiten wegtippt.",
                    },
                    "wann": {
                        "type": "string", "enum": list(WANN),
                        "description": "Wo in der Übungszeit. frueh = in den ersten "
                                       "Paketen, solange das Kind frisch ist — für alles "
                                       "Anstrengende oder bisher Gescheiterte. spaet = "
                                       "gegen Ende, für Sicheres und Motivierendes. "
                                       "egal = keine Vorgabe.",
                    },
                    "grund": {"type": "string",
                              "description": "Ein Satz, den die Eltern lesen. Nenn die "
                                             "Zahlen, auf die du dich stützt."},
                    "fuer": {
                        "type": "string",
                        "description": "Nur bei art=vor: eine Basics-Lücke schließt du mit "
                                       "einem kurzen Vorlauf, bevor die eigentliche "
                                       "Ziel-Fertigkeit drankommt (D3). Trag hier die "
                                       "Kennung dieser Ziel-Fertigkeit ein, aus der Liste. "
                                       "Ist dieser Posten selbst das Ziel und kein Vorlauf, "
                                       "leer lassen.",
                    },
                },
                "required": ["skill", "art", "gewicht", "dosis", "wann", "grund"],
                "additionalProperties": False,
            },
        },
        "erzeugen": {
            "type": "array",
            "description": "Fertigkeiten, für die neue Pakete gebraucht werden. "
                           "Leer lassen, wenn der Vorrat reicht.",
            "items": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string"},
                    "stufe": {"type": "integer"},
                    "warum": {"type": "string"},
                },
                "required": ["skill", "stufe", "warum"],
                "additionalProperties": False,
            },
        },
        "denkcheck": {
            "type": "object",
            "description": "Ob die App dem Kind jetzt einen Denk-Check anbieten soll.",
            "properties": {
                "anfordern": {"type": "boolean"},
                "bereiche": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(DENKCHECK_UEBEN)},
                    "description": "Welche Bereiche geprüft werden. Leer bei "
                                   "anfordern=false; alle neun für einen ganzen Check.",
                },
                "grund": {"type": "string",
                          "description": "Ein Satz für die Eltern: warum jetzt (oder warum nicht)."},
            },
            "required": ["anfordern", "bereiche", "grund"],
            "additionalProperties": False,
        },
    },
    "required": ["beobachtung", "eltern", "plan", "erzeugen", "denkcheck"],
    "additionalProperties": False,
}


# ------------------------------------------------------------------- Auszug

_TITEL = {s["id"]: s["title"] for s in C.SKILLS}


def _paket_titel(unit_id):
    """Aus einer Paket-Id ("skill@stufe") den Titel der Fertigkeit — für einen
    Auszug, den der Tutor lesen soll, sagt der Bezeichner allein wenig."""
    sid = (unit_id or "").split("@")[0]
    return _TITEL.get(sid, unit_id or "?")


def motivationsauszug(ev, seit_plan):
    """D6: 'Wie es dem Kind gerade geht' — kompakt aus A.motivationslage()
    berechnet. Nordstern der Denkschule (ZIELE-V2.md, Abschnitt D6): nicht
    die Trefferquote entscheidet, sondern ob das Kind dranbleibt.
    """
    m = A.motivationslage(ev, seit_plan)
    zeilen = ["WIE ES DEM KIND GERADE GEHT (der Nordstern, siehe ZIELE-V2.md D6)"]

    wm = m["wochenmenge"]
    zeilen.append("Antworten je Woche (letzte 4 Wochen): " +
                  ", ".join(f'{w["woche"]}: {w["n"]}' for w in wm))

    nn = m["nullnull"]
    zeilen.append(f'0/0-Sitzungen (Paket geöffnet, sofort weggetippt, keine einzige Antwort) '
                 f'unter den letzten {nn["von"]} Sitzungen: {nn["anzahl"]} '
                 f'({nn["anteil"]*100:.0f} %)')

    ap = m["abbrueche_je_paket"]
    if ap:
        zeilen.append("Sofort-Abbrüche je Paket seit deinem letzten Plan:")
        for uid, n in sorted(ap.items(), key=lambda kv: -kv[1])[:10]:
            zeilen.append(f'  {_paket_titel(uid)}: {n}×')

    ag = m["abbruchgruende"]
    if ag:
        zeilen.append("Zuletzt angetippte Abbruchgründe:")
        for e in ag[:10]:
            zeilen.append(f'  {A.datetime.fromtimestamp(e["t"]/1000).strftime("%d.%m.")} '
                         f'{_paket_titel(e["unit"])}: {e["text"]}')
    else:
        zeilen.append("Abbruchgründe: noch keine genannt.")

    sp = m["spass"]
    if sp["n"]:
        g = sp["gesamt"]
        zeilen.append(f'Spaß-Signale (insgesamt {sp["n"]}): '
                     f'{g.get(3,0)}× super, {g.get(2,0)}× ging so, {g.get(1,0)}× nicht gut')
        for dz, counts in sp["je_disziplin"].items():
            zeilen.append(f'  {DZ.DISZIPLINEN[dz]["titel"]}: {counts.get(3,0)}× super, '
                         f'{counts.get(2,0)}× ging so, {counts.get(1,0)}× nicht gut')
    else:
        zeilen.append("Spaß-Signale: noch keine.")

    return "\n".join(zeilen)


def _dc_titel():
    """Titel je Denk-Check-Bereich aus der Aufgabenbank (Fallback: der Schlüssel)."""
    try:
        d = json.loads((ROOT / "data" / "denkcheck.json").read_text("utf-8")).get("dimensionen") or {}
        return {k: (v or {}).get("titel") or k for k, v in d.items()}
    except (ValueError, OSError):
        return {}


def check_stand(ev):
    """Wie viele Ergebnisse ("c") je Denk-Check-Bereich bisher angekommen sind."""
    stand = {}
    for e in ev:
        if e.get("e") == "c" and isinstance(e.get("k"), str):
            stand[e["k"]] = stand.get(e["k"], 0) + 1
    return stand


def offene_anforderung(plan, ev):
    """Die Check-Anforderung aus `plan`, solange das Kind sie noch nicht erledigt hat.

    Erledigt ist sie, wenn für jeden angeforderten Bereich seit der Anforderung
    ein neues Ergebnis ("c") angekommen ist — gezählt, nicht nach Uhrzeit
    verglichen: Die Anforderung trägt die Uhr des Dienstes, ein Ergebnis die
    des Geräts, und die beiden müssen nicht übereinstimmen. `stand` ist der
    Zählstand im Moment der Anforderung. Ohne Anforderung: None.
    """
    dc = (plan or {}).get("denkcheck") or {}
    if not dc.get("anfordern") or not dc.get("t"):
        return None
    vorher, jetzt = dc.get("stand") or {}, check_stand(ev)
    neu = {k for k in dc.get("bereiche") or [] if jetzt.get(k, 0) > int(vorher.get(k, 0))}
    return None if set(dc.get("bereiche") or []) <= neu else dc


def denkcheck_auszug(ev, frueher):
    """Der Abschnitt DENK-CHECK für den Auszug: Profil, Übungsweg je Bereich,
    Stand einer offenen Anforderung."""
    prof = A.denkcheck_profil(ev)
    titel = _dc_titel()
    zeilen = ["DENK-CHECK (Screening; Stufe 2-4 = Klasse 2, 5 = Klasse 3, 6 = Klasse 4, "
              "7 = Klasse 5/6, 8 = Knobelolympiade)"]
    if not prof["dimensionen"]:
        zeilen.append("Noch kein Check gemacht.")
    for k, ueben in DENKCHECK_UEBEN.items():
        d = prof["dimensionen"].get(k)
        name = f'{titel.get(k, k)} ({k})'
        if d:
            z = {1: ", Decke nicht erreicht", -1: ", nichts gelöst"}.get(d["z"], "")
            stand = (f'Stufe {d["schaetzung"]}{z}; {d["c"]}/{d["n"]} richtig, '
                     f'Median {d["ms"] / 1000:.0f} s, am {d["datum"]}')
            if d["verlauf"]:
                stand += "; früher: " + ", ".join(f'{v["datum"]}: {v["schaetzung"]}' for v in d["verlauf"])
        else:
            stand = "noch nicht geprüft"
        weg = ", ".join(s for s in ueben if s in _IDS) or "keine eigene Fertigkeit"
        zeilen.append(f"  {name}: {stand}. Geübt über: {weg}")
    offen = offene_anforderung(frueher, ev)
    if offen:
        zeilen.append(f'Offen: Du hast am {A.datetime.fromtimestamp(offen["t"] / 1000).strftime("%d.%m.")} '
                      f'einen Check angefordert ({", ".join(offen.get("bereiche") or [])}); '
                      "das Kind hat ihn noch nicht gemacht.")
    elif prof["letzter"]:
        tage = int((time.time() * 1000 - prof["letzter"]) / 86400000)
        zeilen.append(f"Letzter Check vor {tage} Tagen.")
    return "\n".join(zeilen)


def auszug():
    """Was das Modell zu sehen bekommt. Zahlen, keine Wertungen.

    Bewusst ohne die Etiketten "sitzt" und "hakt": Die stammen aus denselben
    festen Schwellen, die hier gerade nicht gelten sollen. Wer dem Modell die
    Schlussfolgerung vorlegt, bekommt sie zurück.
    """
    ev = SP.alle_ereignisse()
    fert = A.fertigkeiten(ev)
    ber = {a["id"]: a["title"] for a in C.AREAS}
    verlauf = A.verlauf(ereignisse=ev)
    s = A.sitzungen(ev)

    zeilen = []
    for f in sorted(fert, key=lambda x: (x["bereich"], x["stufe"])):
        if f["n"]:
            zeilen.append(
                f'{f["id"]:16s} {ber.get(f["bereich"],"?"):16s} St{f["stufe"]} '
                f'{f["richtig"]:3d}/{f["n"]:3d} = {f["quote"]*100:3.0f}%  '
                f'zuletzt {A.datetime.fromtimestamp(f["letzte"]/1000).strftime("%d.%m.")}'
                + ("  zuletzt dreimal daneben" if f["serie_aus"] else ""))
        else:
            zeilen.append(f'{f["id"]:16s} {ber.get(f["bereich"],"?"):16s} St{f["stufe"]} '
                          f'  noch nie geübt')

    wochen = []
    for i, w in enumerate(verlauf["gesamt"]):
        wochen.append(f'  {verlauf["wochen"][i]}: {w["richtig"]:3d}/{w["n"]:3d}'
                      + (f' = {w["quote"]*100:.0f}%' if w["n"] else ''))

    letzte = s[-25:]
    sitz = [f'  {A.datetime.fromtimestamp(x["t"]/1000).strftime("%d.%m. %H:%M")} '
            f'{x["richtig"]}/{x["n"]}' + ("  abgebrochen" if x["abgebrochen"] else "")
            for x in letzte]

    vorrat = A.vorratsdeckung()
    wuensche = SP.wuensche_lesen()
    frueher = lies_plan()
    seit_plan = frueher.get("t", 0) if frueher else 0

    teile = [
        "ALLE FERTIGKEITEN (Bezeichner, Welt, Stufe, richtig/gesamt, zuletzt geübt)",
        "\n".join(zeilen),
        "\nWOCHENVERLAUF INSGESAMT", "\n".join(wochen),
        "\nDIE LETZTEN SITZUNGEN", "\n".join(sitz) or "  noch keine",
        f'\nVORRAT: {vorrat["unversorgt"]} von {vorrat["gesamt"]} Fertigkeiten ohne Paket',
        "\n" + motivationsauszug(ev, seit_plan),
        "\n" + denkcheck_auszug(ev, frueher),
    ]
    if wuensche:
        teile.append("\nDIE ELTERN HABEN GEWÜNSCHT (das geht deinem Plan vor)")
        teile.append("\n".join(
            f'  {w.get("id")}: {w.get("art")}' for w in wuensche))
    if frueher and frueher.get("plan"):
        teile.append("\nDEIN LETZTER PLAN (vom " + frueher.get("datum", "?") + ")")
        teile.append("\n".join(
            f'  {p["skill"]}: {p["art"]} — {p["grund"]}' for p in frueher["plan"][:10]))
        teile.append(seither_gestellt(ev, frueher.get("t", 0)))
        teile.append("Prüfe, ob er gewirkt hat, und sag es in der Beobachtung.")
    return "\n".join(teile)


def seither_gestellt(ev, seit):
    """Welche Pakete das Kind seit dem letzten Plan wirklich vorgelegt bekam.

    Ohne diese Zeilen sieht der Tutor nur, dass eine vorgezogene Fertigkeit
    weiterhin bei „noch nie geübt“ steht — und muss raten, woran das lag:
    fehlender Vorrat, ein Elternwunsch, eine Auswahl, die etwas anderes vorzog.
    Geraten hat er dann auch, und zwar falsch. Hier steht es schwarz auf weiß.
    """
    gestellt = [e for e in ev if e.get("e") == "s" and e.get("q") == "unit"
                and (e.get("t") or 0) >= seit]
    if not gestellt:
        return ("SEITHER GESTELLT: nichts — seit deinem letzten Plan hat das Kind "
                "kein Paket begonnen.")
    zeilen = [f'  {A.datetime.fromtimestamp(e["t"]/1000).strftime("%d.%m. %H:%M")} '
              f'{e.get("u")}' + (f'  {e.get("c")}/{e.get("n")}' if e.get("n") else "")
              for e in gestellt[-20:]]
    return ("SEITHER GESTELLT (was die App aus deinem Plan tatsächlich ausgewählt hat)\n"
            + "\n".join(zeilen)
            + "\nWas du vorgezogen hast und hier nicht steht, wurde nicht gestellt.")


# ------------------------------------------------------------------- Prüfung

_IDS = {s["id"] for s in C.SKILLS}


def saeubere(obj):
    """Nur auf Gültigkeit prüfen, nicht auf Inhalt.

    Was hier wegfällt, ist ein kaputter Verweis — nie eine Entscheidung, die
    uns zu kühn vorkäme. Über die entscheidet das Modell.
    """
    if not isinstance(obj, dict):
        return None, ["keine brauchbare Antwort"]
    hinweise = []

    plan = []
    for p in (obj.get("plan") or [])[:MAX_PLAN]:
        if not isinstance(p, dict):
            continue
        sid, art = p.get("skill"), p.get("art")
        if sid not in _IDS:
            hinweise.append(f"unbekannte Fertigkeit übergangen: {sid!r}")
            continue
        if art not in ARTEN:
            hinweise.append(f"unbekannte Art übergangen: {art!r}")
            continue

        # Die drei Regler sind Feinsteuerung, kein Verweis: Ein unbrauchbarer
        # Wert darf die Entscheidung nicht mitreißen. Er fällt auf den
        # Normalwert zurück, und die Entscheidung selbst bleibt stehen.
        try:
            gewicht = min(GEWICHT_MAX, max(0.0, float(p.get("gewicht"))))
        except (TypeError, ValueError):
            gewicht = 1.0
        try:
            dosis = min(DOSIS_MAX, max(DOSIS_MIN, int(p.get("dosis"))))
        except (TypeError, ValueError):
            dosis = DOSIS_NORMAL
        wann = p.get("wann") if p.get("wann") in WANN else "egal"

        # D3: "fuer" ist nur bei art=vor sinnvoll — eine Ziel-Fertigkeit für
        # jeden anderen Posten wäre ein Kettenglied ohne Kette. Eine unbekannte
        # Kennung wird wie bei "skill" toleriert und benannt (Z7-
        # Betriebssicherheit), reißt aber nicht den ganzen Posten mit: Der
        # Vorlauf bleibt drin, nur der kaputte Verweis fällt weg.
        fuer_roh = p.get("fuer")
        fuer = ""
        if art == "vor" and isinstance(fuer_roh, str) and fuer_roh.strip():
            if fuer_roh.strip() in _IDS:
                fuer = fuer_roh.strip()
            else:
                hinweise.append(f"unbekannte Ziel-Fertigkeit im Vorlauf übergangen: {fuer_roh!r}")

        plan.append({"skill": sid, "art": art,
                     "gewicht": round(gewicht, 2), "dosis": dosis, "wann": wann,
                     "grund": str(p.get("grund") or "").strip()[:400], "fuer": fuer})

    erzeugen = []
    for e in (obj.get("erzeugen") or [])[:20]:
        if isinstance(e, dict) and e.get("skill") in _IDS:
            try:
                stufe = int(e.get("stufe"))
            except (TypeError, ValueError):
                continue
            erzeugen.append({"skill": e["skill"], "stufe": stufe,
                             "warum": str(e.get("warum") or "").strip()[:300]})

    # Denk-Check-Anforderung: nur bekannte Bereiche, doppelte fallen weg. Eine
    # Anforderung ohne einen einzigen gültigen Bereich ist keine.
    dc_roh = obj.get("denkcheck") if isinstance(obj.get("denkcheck"), dict) else {}
    bereiche = []
    for b in dc_roh.get("bereiche") or []:
        if b in DENKCHECK_UEBEN and b not in bereiche:
            bereiche.append(b)
        elif b not in DENKCHECK_UEBEN:
            hinweise.append(f"unbekannter Denk-Check-Bereich übergangen: {b!r}")
    anfordern = dc_roh.get("anfordern") is True and bool(bereiche)
    denkcheck = {"anfordern": anfordern, "bereiche": bereiche if anfordern else [],
                 "grund": str(dc_roh.get("grund") or "").strip()[:400]}

    return {"beobachtung": str(obj.get("beobachtung") or "").strip()[:2000],
            "eltern": str(obj.get("eltern") or "").strip()[:4000],
            "plan": plan, "erzeugen": erzeugen, "denkcheck": denkcheck}, hinweise


# -------------------------------------------------------------------- Ablage

def lies_plan():
    if not PLAN.exists():
        return None
    try:
        p = json.loads(PLAN.read_text("utf-8"))
        return p if isinstance(p, dict) else None
    except (ValueError, OSError):
        return None


def schreib_plan(p):
    try:
        PLAN.parent.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(p, ensure_ascii=False, indent=1), "utf-8")
    except OSError as e:
        print(f"   !  Plan nicht gespeichert: {e}")


# -------------------------------------------------------------------- Aufruf

def _client():
    from anthropic import Anthropic
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import konfig
    return Anthropic(api_key=konfig.geheim("ANTHROPIC_API_KEY"))


def denk_nach(client=None, _schon_belegt=False):
    """Einmal über den Verlauf nachdenken. Rückgabe: (plan|None, Protokoll).

    Läuft schon ein Durchgang (selbständig oder vom Elternknopf), kommt kein
    zweiter dazu — sonst überschriebe der eine den Plan des anderen.
    """
    if not _schon_belegt:
        with _sperre:
            if _laeuft["ja"]:
                return None, ["der Tutor denkt gerade schon nach"]
            _laeuft["ja"] = True
        try:
            return _denk_nach(client)
        finally:
            _laeuft["ja"] = False
    return _denk_nach(client)


def _denk_nach(client=None):
    ev = SP.alle_ereignisse()
    # Denk-Check-Antworten sind kein Üben und zählen hier nicht (ZIELE-V3 G4).
    antworten = sum(1 for e in ev if e.get("e") == "a" and e.get("u") != "denkcheck")
    if antworten < 10:
        return None, [f"zu wenig Verlauf: {antworten} Antworten"]

    try:
        client = client or _client()
    except Exception as e:
        return None, [f"kein Zugang: {type(e).__name__}"]

    t0 = time.time()
    try:
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT,
                           "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": auszug()}])
    except Exception as e:
        return None, [f"Aufruf gescheitert: {type(e).__name__}"]

    if resp.stop_reason == "refusal":
        return None, ["Anfrage wurde abgelehnt"]
    if resp.stop_reason == "max_tokens":
        return None, ["Antwort abgeschnitten"]

    try:
        obj = json.loads("".join(b.text for b in resp.content if b.type == "text"))
    except ValueError:
        return None, ["Antwort ist kein gültiges JSON"]

    plan, hinweise = saeubere(obj)
    if not plan:
        return None, hinweise

    jetzt = int(time.time() * 1000)
    # Die Anforderung trägt die Zeit, ab der Ergebnisse sie erfüllen. Fordert der
    # Tutor erneut an, während die alte noch offen ist, bleibt deren Zeit: Sonst
    # würde ein angefangener Check nie als Erfüllung zählen, und die App böte
    # gleich danach den nächsten an.
    # Die Pause aus dem Prompt gilt auch im Code: Kurz nach einem Check wird
    # eine neue Anforderung nicht angenommen (eine noch offene bleibt bestehen).
    letzter = A.denkcheck_profil(ev)["letzter"]
    if (plan["denkcheck"]["anfordern"] and not offene_anforderung(lies_plan(), ev) and letzter
            and jetzt - letzter < DENKCHECK_PAUSE_TAGE * 86400000):
        plan["denkcheck"].update(anfordern=False, bereiche=[])
        hinweise.append(f"Denk-Check-Anforderung zurückgestellt: der letzte ist keine "
                        f"{DENKCHECK_PAUSE_TAGE} Tage her")
    if plan["denkcheck"]["anfordern"]:
        offen = offene_anforderung(lies_plan(), ev)
        plan["denkcheck"]["t"] = offen["t"] if offen else jetzt
        plan["denkcheck"]["stand"] = (offen.get("stand") or {}) if offen else check_stand(ev)
    plan.update({
        "t": jetzt,
        "datum": A.datetime.fromtimestamp(jetzt / 1000).strftime("%d.%m.%Y %H:%M"),
        "grundlage": {"antworten": antworten, "ereignisse": len(ev),
                      "checks": sum(check_stand(ev).values())},
        "ms": int((time.time() - t0) * 1000),
        "kosten": {"rein": resp.usage.input_tokens, "raus": resp.usage.output_tokens},
        "hinweise": hinweise,
    })
    schreib_plan(plan)
    return plan, hinweise + [f'{plan["ms"]} ms, {len(plan["plan"])} Entscheidungen']


# ------------------------------------------------------------- Wann er denkt

NEUE_ANTWORTEN = 8           # so viel Neues rechtfertigt einen Aufruf
ALTER = 20 * 3600 * 1000     # oder der Plan ist so alt
KURZ = 3                     # unter so vielen Aufgaben ist ein Abbruch ein Hilferuf
_laeuft = {"ja": False}
import threading  # noqa: E402
_sperre = threading.Lock()   # schützt _laeuft und das Protokoll der Läufe


def kurz_abgebrochen(ev, seit):
    """Hat das Kind seit dem letzten Plan ein Paket fast sofort wieder verlassen?

    Ein Abbruch nach sieben Aufgaben ist ein müdes Kind. Einer nach null oder
    einer ist ein Kind, das die Aufgabe gesehen und sich abgewandt hat — und
    darauf erst beim nächsten Achter zu reagieren, kommt zu spät: Am 23.08.
    wurde dieselbe Fertigkeit binnen fünf Sekunden zweimal weggetippt, weil
    zwischen den Versuchen niemand neu nachgedacht hat.
    """
    for e in reversed(ev):
        if (e.get("t") or 0) < seit:
            break
        if e.get("e") == "s" and e.get("z") and int(e.get("n") or 0) < KURZ:
            return True
    return False


def faellig():
    """Lohnt sich ein Aufruf? Er kostet Geld, also nicht bei jeder Kleinigkeit."""
    if _laeuft["ja"]:
        return False
    ev = SP.alle_ereignisse()
    # Denk-Check-Antworten sind kein Üben und zählen hier nicht (ZIELE-V3 G4).
    antworten = sum(1 for e in ev if e.get("e") == "a" and e.get("u") != "denkcheck")
    if antworten < 10:
        return False
    p = lies_plan()
    if not p:
        return True
    seither = antworten - int((p.get("grundlage") or {}).get("antworten", 0))
    if seither >= NEUE_ANTWORTEN:
        return True
    # Ein neues Denk-Check-Ergebnis verändert das Bild mehr als acht Antworten.
    # Gezählt, nicht nach Uhrzeit: Eine vorgehende Geräteuhr ließe ein altes
    # Ergebnis sonst tagelang als neu gelten.
    if sum(check_stand(ev).values()) > int((p.get("grundlage") or {}).get("checks", 0)):
        return True
    # Ein alter Plan allein ist kein Anlass: Ohne eine einzige neue Antwort
    # sähe der Tutor dasselbe wie gestern und kostete trotzdem Geld.
    if seither > 0 and (time.time() * 1000 - p.get("t", 0)) > ALTER:
        return True
    # Der einzige Anlass, der ohne neue Antworten zieht. Ein weggetipptes Paket
    # erzeugt fast keine Antworten und bliebe unter jeder Zählschwelle — dabei
    # ist es der Moment, in dem ein neuer Plan noch etwas ändern kann.
    return kurz_abgebrochen(ev, p.get("t", 0))


AUTO_MAX_TAG = 3            # höchstens so viele selbständige Läufe in 24 Stunden
AUTO_PROTOKOLL = PLAN.parent / "tutor_auto.json"


def _auto_frei(jetzt_ms=None):
    """Kostenbremse für selbständige Läufe (nach einem Sync, ohne Elternknopf).

    Ein gekoppeltes Gerät kann beliebig oft synchronisieren; ohne Deckel könnte
    es so beliebig viele bezahlte Aufrufe auslösen. Die Zeitpunkte der letzten
    Läufe stehen in einer kleinen Datei neben dem Plan. Ist sie unlesbar, gilt
    sie als leer — eine kaputte Datei soll den Tutor nicht abstellen, und der
    Deckel greift ab dem nächsten Lauf wieder.
    """
    jetzt_ms = jetzt_ms or int(time.time() * 1000)
    try:
        liste = json.loads(AUTO_PROTOKOLL.read_text("utf-8"))
        liste = [int(t) for t in liste if isinstance(t, (int, float))]
    except (OSError, ValueError, TypeError):
        liste = []
    liste = [t for t in liste if jetzt_ms - t < 24 * 3600 * 1000]
    if len(liste) >= AUTO_MAX_TAG:
        return False
    try:
        AUTO_PROTOKOLL.parent.mkdir(parents=True, exist_ok=True)
        AUTO_PROTOKOLL.write_text(json.dumps(liste + [jetzt_ms]), "utf-8")
    except OSError:
        return False             # ohne Protokoll kein Deckel, also kein Lauf
    return True


def vielleicht_nachdenken():
    """Im Hintergrund, wenn es sich lohnt. Blockiert nie eine Übertragung.

    Prüfen, Zählen und "läuft" setzen geschehen unter einer Sperre: Der Dienst
    bedient mehrere Anfragen gleichzeitig, und zwei Übertragungen dürfen nicht
    beide "nichts läuft" sehen und zweimal bezahlen.
    """
    with _sperre:
        if not faellig() or not _auto_frei():
            return False
        _laeuft["ja"] = True

    def lauf():
        try:
            p, log = denk_nach(_schon_belegt=True)
            print("Tutor: " + " · ".join(log), flush=True)
        except Exception as e:                       # nie den Dienst mitreißen
            print(f"Tutor gescheitert: {type(e).__name__}", flush=True)
        finally:
            _laeuft["ja"] = False

    threading.Thread(target=lauf, daemon=True).start()
    return True


def main():
    if "--zeigen" in sys.argv:
        p = lies_plan()
        if not p:
            print("Noch kein Plan.")
            return 1
    else:
        p, log = denk_nach()
        print(" · ".join(log))
        if not p:
            return 1

    print(f'\nStand {p.get("datum")} · {p["grundlage"]["antworten"]} Antworten\n')
    print("BEOBACHTUNG\n  " + p["beobachtung"].replace("\n", "\n  "))
    print("\nFÜR DIE ELTERN\n  " + p["eltern"].replace("\n", "\n  "))
    print(f'\nPLAN ({len(p["plan"])} Entscheidungen)')
    for e in p["plan"]:
        print(f'  [{e["art"]:8s}] {e["skill"]:16s} {e["grund"]}')
    if p["erzeugen"]:
        print("\nNEUE PAKETE GEBRAUCHT")
        for e in p["erzeugen"]:
            print(f'  {e["skill"]} Stufe {e["stufe"]}: {e["warum"]}')
    k = p.get("kosten") or {}
    if k:
        print(f'\n  {k.get("rein")} Token rein, {k.get("raus")} raus')
    return 0


if __name__ == "__main__":
    sys.exit(main())
