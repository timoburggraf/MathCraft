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

PLAN = Path(os.environ.get("MC_PLAN") or (ROOT / "data" / "tutorplan.json"))

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

SYSTEM = """Du bist der Tutor eines achtjährigen Kindes und stellst seinen
Lernplan auf. Du bekommst den vollständigen Verlauf und entscheidest allein,
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
auch das — du hast nur Zahlen gesehen, nicht das Kind."""

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
    },
    "required": ["beobachtung", "eltern", "plan", "erzeugen"],
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

    return {"beobachtung": str(obj.get("beobachtung") or "").strip()[:2000],
            "eltern": str(obj.get("eltern") or "").strip()[:4000],
            "plan": plan, "erzeugen": erzeugen}, hinweise


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


def denk_nach(client=None):
    """Einmal über den Verlauf nachdenken. Rückgabe: (plan|None, Protokoll)."""
    ev = SP.alle_ereignisse()
    antworten = sum(1 for e in ev if e.get("e") == "a")
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
        return None, [f"Aufruf gescheitert: {type(e).__name__}: {e}"]

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
    plan.update({
        "t": jetzt,
        "datum": A.datetime.fromtimestamp(jetzt / 1000).strftime("%d.%m.%Y %H:%M"),
        "grundlage": {"antworten": antworten, "ereignisse": len(ev)},
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
    antworten = sum(1 for e in ev if e.get("e") == "a")
    if antworten < 10:
        return False
    p = lies_plan()
    if not p:
        return True
    seither = antworten - int((p.get("grundlage") or {}).get("antworten", 0))
    if seither >= NEUE_ANTWORTEN or (time.time() * 1000 - p.get("t", 0)) > ALTER:
        return True
    # Der einzige Anlass, der ohne neue Antworten zieht. Ein weggetipptes Paket
    # erzeugt fast keine Antworten und bliebe unter jeder Zählschwelle — dabei
    # ist es der Moment, in dem ein neuer Plan noch etwas ändern kann.
    return kurz_abgebrochen(ev, p.get("t", 0))


def vielleicht_nachdenken():
    """Im Hintergrund, wenn es sich lohnt. Blockiert nie eine Übertragung."""
    import threading

    if not faellig():
        return False

    def lauf():
        _laeuft["ja"] = True
        try:
            p, log = denk_nach()
            print("Tutor: " + " · ".join(log), flush=True)
        except Exception as e:                       # nie den Dienst mitreißen
            print(f"Tutor gescheitert: {type(e).__name__}: {e}", flush=True)
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
