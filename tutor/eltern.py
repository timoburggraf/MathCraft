# -*- coding: utf-8 -*-
"""Die Elternseite: was das Kind kann, was hakt, und was der Tutor daraus macht.

Eine Seite, kein Programm. Alles wird beim Aufruf gerechnet und als fertiges
HTML ausgeliefert — kein JavaScript, kein Nachladen, nichts, was in zwei Jahren
kaputtgeht, weil eine Bibliothek weiterzieht.

Eine Regel zieht sich durch: Neben jeder Zahl steht, wie sie zustande kommt.
Eine Trefferquote ohne die Angabe, woraus sie gebildet wurde, verleitet zu
Schlüssen, die die Daten nicht hergeben.
"""
import html
from datetime import datetime

import auswertung as A
import curriculum as C

FARBE = {"sitzt": "#2fd77f", "hakt": "#ff5a68", "arbeit": "#ffb238", "unberuehrt": "#5a6a8c"}

# Elternwunsch 03.09.2026: Diese Abschnitte werten weiterhin geräteübergreifend
# aus (Elternwünsche, Tutorplan, Vorratsteil, Technik samt Gerätetabelle und
# Z1-Gegenprobe) — der dezente Zusatz an ihrer Überschrift sagt das dazu,
# damit niemand annimmt, sie folgten der Spieler-Auswahl oben auf der Seite.
_ALLE_SPIELER = ('<span class="muted" style="font-weight:400;font-size:13px">'
                 ' — gilt für alle Spieler</span>')

CSS = """
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0b1020;
  color:#eef3ff;margin:0;padding:0 16px 64px;line-height:1.5;
  background-image:radial-gradient(900px 600px at 8% -10%,rgba(91,140,255,.22),transparent 60%),
    radial-gradient(760px 520px at 102% 4%,rgba(37,208,192,.14),transparent 58%);
  background-attachment:fixed}
.wrap{max-width:60rem;margin:0 auto}
h1{font-size:28px;margin:28px 0 2px}
h2{font-size:19px;margin:30px 0 10px}
h3{font-size:15px;margin:0 0 8px}
a{color:#25d0c0}
.muted{color:#94a6c8}
.def{color:#7f92b4;font-size:13px;font-style:italic;margin:2px 0 10px}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);
  border-radius:16px;padding:16px;margin-bottom:12px}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
.kpi b{display:block;font-size:27px;line-height:1.15}
.kpi span{color:#94a6c8;font-size:13.5px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid rgba(255,255,255,.07)}
th{color:#94a6c8;font-weight:600;font-size:12.5px;text-transform:uppercase;letter-spacing:.04em}
td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;padding:1px 9px;border-radius:999px;font-size:12.5px;
  font-weight:700;white-space:nowrap}
.bar{height:8px;background:rgba(255,255,255,.1);border-radius:99px;overflow:hidden}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#25d0c0,#ffb238)}
.spark{display:flex;align-items:flex-end;gap:3px;height:46px}
.spark div{flex:1;border-radius:3px 3px 0 0;min-width:6px}
.leer{padding:26px 16px;text-align:center;color:#94a6c8}
.wf{display:flex;gap:4px;justify-content:flex-end;flex-wrap:wrap;margin:0}
.wb{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.13);color:#cddcf5;
  border-radius:8px;padding:3px 8px;font-size:12px;font-family:inherit;cursor:pointer;
  white-space:nowrap}
.wb:hover{background:rgba(255,255,255,.13)}
.wb.an{background:rgba(37,208,192,.22);border-color:#25d0c0;color:#25d0c0;font-weight:700}
.scroll{overflow-x:auto}
.warn{border-color:rgba(255,90,104,.5);background:rgba(255,90,104,.10)}
.ok{border-color:rgba(47,215,127,.4);background:rgba(47,215,127,.09)}
"""


def esc(s):
    return html.escape(str(s), quote=True)


def pct(x):
    return f"{x*100:.0f} %"


def datum(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%d.%m.%Y") if ms else "–"


def tag(zustand):
    return (f'<span class="tag" style="background:{FARBE[zustand]}22;color:{FARBE[zustand]}">'
            f'{esc(A.ZUSTAND_TEXT[zustand])}</span>')


# Die Bezeichner, unter denen der Tutor die Fertigkeiten kennt, sind seine
# Arbeitssprache. In seinem Text an die Eltern haben sie nichts verloren:
# „geo_umfang“ sagt niemandem etwas, „Umfang“ schon. Die längsten zuerst,
# sonst zerlegt ein kurzer Bezeichner den Namen eines längeren.
_BEZEICHNER = sorted(((s["id"], s["title"]) for s in C.SKILLS),
                     key=lambda x: -len(x[0]))


def klartext(text):
    for kennung, titel in _BEZEICHNER:
        text = text.replace(kennung, titel)
    return text


# --------------------------------------------------------------------- Bausteine

def _kpi(wert, beschriftung, definition, farbe=None):
    f = f"style=\"color:{farbe}\"" if farbe else ""
    return (f'<div class="card kpi"><b {f}>{wert}</b><span>{esc(beschriftung)}</span>'
            f'<div class="def">{esc(definition)}</div></div>')


def _spark(reihe):
    """Acht Wochenbalken. Höhe ist die Trefferquote, Blässe die Datenmenge."""
    maxn = max((w["n"] for w in reihe), default=0)
    zellen = []
    for w in reihe:
        if not w["n"]:
            zellen.append('<div style="height:3px;background:rgba(255,255,255,.10)" '
                          'title="keine Aufgaben in dieser Woche"></div>')
            continue
        h = max(6, round(w["quote"] * 46))
        deck = .35 + .65 * (w["n"] / maxn if maxn else 1)
        zellen.append(
            f'<div style="height:{h}px;background:#25d0c0;opacity:{deck:.2f}" '
            f'title="{w["woche"]}: {w["richtig"]}/{w["n"]} richtig = {pct(w["quote"])}"></div>')
    return '<div class="spark">' + "".join(zellen) + "</div>"


def _kopf(u):
    z = u["zaehlstand"]
    return f"""
    <h1>Wie läuft es?</h1>
    <div class="muted">Stand vom {esc(datum(u["bis"]))} · Daten ab {esc(datum(u["von"]))}
      · {z["geraete"]} Gerät{"e" if z["geraete"] != 1 else ""}
      {'· <a href="#technik">Achtung: die Zählung geht nicht auf</a>'
       if z["abweichung"] else ""}</div>"""


def _fazit(u, name=None):
    """Die Antwort auf „Wie läuft es?“ in ganzen Sätzen, ganz oben.

    Alles darunter ist Beleg. Wer die Seite in zwei Minuten zwischen Tür und
    Angel liest, soll nach dem ersten Absatz wissen, woran er ist — und nicht
    erst vier Abschnitte weiter unten aus Prozentzahlen zusammensuchen müssen,
    was sie bedeuten. Gerechnet wird hier nichts Neues: Es sind dieselben
    Zahlen, die weiter unten einzeln nachzulesen sind.

    name: der Spielername des gewählten Geräts (Elternwunsch 03.09.2026) —
    steht er da, ersetzt er "er" im Fließtext; sonst bleibt es bei "er".
    """
    er = name or "Er"
    n, tage = u["nordstern"], u["tage"]
    hakt = [f for f in u["fertigkeiten"] if f["zustand"] == "hakt"]
    sitzt = [f for f in u["fertigkeiten"] if f["zustand"] == "sitzt"]
    saetze = []

    # Wie viel, wie gut, über welchen Zeitraum
    umfang = (f'{u["antworten"]} Aufgaben gerechnet, {pct(u["quote"])} davon richtig')
    if len(tage) <= 1:
        saetze.append(f'{er} hat {umfang} — alles an einem einzigen Tag.')
    else:
        saetze.append(f'{er} hat {umfang}, verteilt über {len(tage)} Übungstage.')

    # Traf der Schwierigkeitsgrad?
    if n["gewertet"] < 4:
        saetze.append('Für eine Aussage über den Schwierigkeitsgrad sind es noch zu '
                      'wenige Sitzungen.')
    elif n["zu_leicht"] > n["im_band"] and n["zu_leicht"] >= n["zu_schwer"]:
        saetze.append(f'Die Aufgaben waren überwiegend zu leicht: von {n["gewertet"]} '
                      f'gewerteten Sitzungen liefen {n["zu_leicht"]} über 85 % richtig, '
                      f'nur {n["im_band"]} lagen goldrichtig und {n["zu_schwer"]} waren '
                      f'zu schwer.')
    elif n["zu_schwer"] > n["im_band"]:
        saetze.append(f'Die Aufgaben waren überwiegend zu schwer: {n["zu_schwer"]} von '
                      f'{n["gewertet"]} gewerteten Sitzungen lagen unter 70 % richtig.')
    else:
        saetze.append(f'Der Schwierigkeitsgrad passt: {n["im_band"]} von {n["gewertet"]} '
                      f'gewerteten Sitzungen lagen goldrichtig.')

    # Was auffällt
    if hakt:
        h = ", ".join(f'{f["titel"]} ({f["richtig"]} von {f["n"]})' for f in hakt[:3])
        saetze.append(f'{"Eine Fertigkeit hakt" if len(hakt) == 1 else f"{len(hakt)} Fertigkeiten haken"}: {h}.')
    if sitzt:
        s = ", ".join(f["titel"] for f in sitzt[:3])
        saetze.append(f'Sicher sitzt {s}.' if len(sitzt) == 1
                      else f'Sicher sitzen: {s}.')
    if not hakt and not sitzt:
        saetze.append('Noch hat keine einzelne Fertigkeit genug Aufgaben für ein '
                      'Urteil — dafür braucht es zehn Antworten in derselben Sache.')

    # Zu viel auf einmal? Das ist die häufigste Ursache für schwache Blöcke.
    proTag = len(u["sitzungen"]) / max(1, len(tage))
    if proTag >= 8:
        saetze.append(f'Auffällig ist die Dichte: im Schnitt {proTag:.0f} Sitzungen am Tag. '
                      f'Zwei kurze Blöcke, dafür an mehreren Tagen, sagen mehr aus — und '
                      f'die schwachen Blöcke liegen fast immer am Ende einer langen Serie.')

    kacheln = "".join([
        _kpi(u["antworten"], "Aufgaben gerechnet",
             f'an {len(tage)} Tag{"en" if len(tage) != 1 else ""}, '
             f'in {len(u["sitzungen"])} Sitzungen'),
        _kpi(pct(u["quote"]), "davon richtig",
             f'{u["richtig"]} von {u["antworten"]} beantworteten Aufgaben, '
             f'Wiederholungen mitgezählt',
             FARBE["sitzt"] if u["quote"] >= 0.7 else FARBE["arbeit"]),
        _kpi(f'Stufe {u["stufe"]}', "steht er gerade",
             "die höchste Stufe, auf der er sich gehalten hat"),
    ])

    return f"""
    <div class="card" style="margin-top:14px;border-color:rgba(37,208,192,.35);
      background:rgba(37,208,192,.07)">
      <h3>Kurz gesagt</h3>
      <div style="font-size:16px;line-height:1.65">{esc(" ".join(saetze))}</div>
    </div>
    <div class="grid">{kacheln}</div>"""


def _paket_titel(unit_id):
    """Aus einer Paket-Id ('skill@stufe') den Titel der Fertigkeit — dasselbe
    Bedürfnis wie überall sonst auf dieser Seite: der Tutor kennt Bezeichner,
    die Eltern sollen Titel lesen (Z2)."""
    sid = (unit_id or "").split("@")[0]
    sk = next((s for s in C.SKILLS if s["id"] == sid), None)
    return sk["title"] if sk else (unit_id or "?")


def _motivation(u, name=None):
    """D6: 'Wie es ihm damit geht' — die Motivationslage in ganzen Sätzen,
    gleich nach dem Fazit. Jede Kennzahl trägt ihre Definition daneben
    (Z2-Stil); wo noch keine Daten vorliegen, steht das ehrlich da, statt
    einer leeren Tabelle oder einer irreführenden Null.

    name: siehe _fazit — ersetzt "er" im Fließtext, wenn vorhanden.
    """
    er = name or "er"
    m = u["motivation"]
    saetze = []

    zahlen = [w["n"] for w in m["wochenmenge"]]
    if not sum(zahlen):
        saetze.append("Zur Wochenmenge liegen noch keine Angaben vor.")
    else:
        mitte = len(zahlen) // 2 or 1
        erste, zweite = sum(zahlen[:mitte]), sum(zahlen[mitte:])
        if zweite > erste * 1.2:
            trend = "die Menge steigt"
        elif zweite < erste * 0.8:
            trend = "die Menge sinkt"
        else:
            trend = "die Menge hält sich etwa gleich"
        saetze.append(f'In den letzten vier Wochen hat {er} '
                      f'{", ".join(str(n) for n in zahlen)} Aufgaben je Woche gerechnet — '
                      f'{trend}.')

    nn = m["nullnull"]
    if not nn["von"]:
        saetze.append("Zu Sofort-Abbrüchen liegen noch keine Angaben vor.")
    else:
        saetze.append(f'Von den letzten {nn["von"]} Sitzungen waren {nn["anzahl"]} '
                      f'sogenannte 0/0-Sitzungen ({pct(nn["anteil"])}) — das Paket wurde '
                      f'geöffnet und sofort wieder verlassen, ohne eine einzige Aufgabe '
                      f'zu beantworten.')

    ag = m["abbruchgruende"]
    if not ag:
        saetze.append("Abbruchgründe hat er noch keine genannt.")
    else:
        eintraege = "; ".join(
            f'am {datum(e["t"])} bei {_paket_titel(e["unit"])}: {e["text"]}' for e in ag[:5])
        saetze.append(f'Zuletzt hat {er} beim Abbrechen angetippt: {eintraege}.')

    sp = m["spass"]
    if not sp["n"]:
        saetze.append("Zum Spaß-Signal liegen noch keine Angaben vor.")
    else:
        g = sp["gesamt"]
        saetze.append(f'Von {sp["n"]} Rückmeldungen zum Spaß-Signal fand {er} es '
                      f'{g.get(3,0)}× super, {g.get(2,0)}× ging so, {g.get(1,0)}× nicht gut.')

    disz = u["disziplinen"]
    if not any(d["n"] for d in disz):
        tabelle = ('<div class="muted" style="font-size:14px">Zur Denkschule liegen noch '
                  'keine Angaben vor.</div>')
    else:
        zeilen = "".join(
            f'<tr><td>{esc(d["titel"])}</td><td class="r">{d["n"] or "–"}</td>'
            f'<td class="r">{pct(d["quote"]) if d["n"] else "–"}</td></tr>' for d in disz)
        tabelle = ('<div class="scroll"><table><tr><th>Disziplin</th>'
                  '<th class="r">Antworten</th><th class="r">Trefferquote</th></tr>'
                  + zeilen + '</table></div>')

    return f"""
    <h2>Wie es ihm damit geht</h2>
    <div class="card">
      <div class="def">Wochenmenge und Sofort-Abbrüche sind die Nordstern-Größen aus
        ZIELE-V2.md, Abschnitt D6: Die Menge zeigt, ob er dranbleibt; eine
        0/0-Sitzung heißt, ein Paket wurde geöffnet und ohne eine einzige Antwort
        sofort wieder verlassen. Ein Abbruchgrund ist eine von vier Antworten, die
        er seinem Begleiter beim Abbrechen antippen kann. Das Spaß-Signal ist ein
        freiwilliger Tipp auf ein Gesicht nach einem fertig gespielten Paket.</div>
      <div style="font-size:15.5px;line-height:1.65">{esc(" ".join(saetze))}</div>
    </div>
    <div class="card">
      <h3>Die Denkschule</h3>
      <div class="def">Antworten und Trefferquote je Denkdisziplin (ZIELE-V2.md, Abschnitt D1).</div>
      {tabelle}
    </div>"""


def _nordstern(n):
    gut = n["anteil"] >= 0.70 and n["gewertet"] >= 4
    return f"""
    <h2>War es zu leicht oder zu schwer?</h2>
    <div class="def">Zu leicht ist genauso ein Fehler wie zu schwer. Gelernt wird
      dort, wo etwa {int(A.BAND_UNTEN*100)} bis {int(A.BAND_OBEN*100)} % richtig sind —
      darüber langweilt er sich, darunter gibt er auf. Gezählt werden nur Sitzungen
      ab {A.KURZE_SITZUNG} Aufgaben; aus dreien lässt sich nichts ablesen.</div>
    <div class="grid">
      {_kpi(n["im_band"], "Sitzungen goldrichtig",
            f'{int(A.BAND_UNTEN*100)} bis {int(A.BAND_OBEN*100)} % richtig — '
            f'{pct(n["anteil"])} von {n["gewertet"]} gewerteten',
            FARBE["sitzt"] if gut else (FARBE["arbeit"] if n["gewertet"] else None))}
      {_kpi(n["zu_leicht"], "Sitzungen zu leicht",
            f'über {int(A.BAND_OBEN*100)} % richtig — er langweilt sich',
            FARBE["arbeit"] if n["zu_leicht"] > n["im_band"] else None)}
      {_kpi(n["zu_schwer"], "Sitzungen zu schwer",
            f'unter {int(A.BAND_UNTEN*100)} % richtig — es überfordert ihn',
            FARBE["hakt"] if n["zu_schwer"] > n["im_band"] else None)}
      {_kpi(n["kurz"], "früh abgebrochen",
            f'weniger als {A.KURZE_SITZUNG} Aufgaben — {pct(n["anteil_kurz"])} '
            f'aller {n["sitzungen"]} Sitzungen',
            FARBE["hakt"] if n["anteil_kurz"] > 0.15 and n["sitzungen"] >= 5 else None)}
    </div>"""


def _auffaellig(fert):
    hakt = sorted([f for f in fert if f["zustand"] == "hakt"], key=lambda f: (f["quote"], -f["n"]))
    sitzt = sorted([f for f in fert if f["zustand"] == "sitzt"], key=lambda f: -f["quote"])

    def liste(items, leer):
        if not items:
            return f'<div class="muted" style="font-size:14px">{esc(leer)}</div>'
        return "<table>" + "".join(
            f'<tr><td>{esc(f["titel"])}<div class="muted" style="font-size:12.5px">'
            f'Stufe {f["stufe"]}{" · zuletzt dreimal daneben" if f["serie_aus"] else ""}</div></td>'
            f'<td class="r">{f["richtig"]}/{f["n"]}</td>'
            f'<td class="r">{pct(f["quote"])}</td></tr>' for f in items[:8]) + "</table>"

    return f"""
    <h2>Was besonders auffällt</h2>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">
      <div class="card">
        <h3 style="color:{FARBE["hakt"]}">Das hakt ({len(hakt)})</h3>
        <div class="def">{esc(A.DEFINITION["hakt"])}</div>
        {liste(hakt, "Nichts hakt gerade.")}
      </div>
      <div class="card">
        <h3 style="color:{FARBE["sitzt"]}">Das sitzt ({len(sitzt)})</h3>
        <div class="def">{esc(A.DEFINITION["sitzt"])}</div>
        {liste(sitzt, "Noch keine Fertigkeit hat die Schwelle erreicht.")}
      </div>
    </div>"""


def _verlauf(u):
    v = u["verlauf"]
    von, bis = v["wochen"][0], v["wochen"][-1]
    zeilen = []
    for b in u["bereiche"]:
        reihe = v["bereiche"][b["id"]]
        if not any(w["n"] for w in reihe):
            continue
        zeilen.append(f"""<tr>
          <td style="width:34%">{esc(b["emoji"])} {esc(b["titel"])}
            <div class="muted" style="font-size:12.5px">{b["richtig"]}/{b["n"]} richtig</div></td>
          <td>{_spark(reihe)}</td>
          <td class="r">{pct(b["quote"]) if b["n"] else "–"}</td></tr>""")
    if not zeilen:
        inhalt = '<div class="leer">Noch keine Aufgaben in diesem Zeitraum.</div>'
    else:
        inhalt = ('<div class="scroll"><table><tr><th>Welt</th>'
                  f'<th>{A.WOCHEN} Wochen</th><th class="r">gesamt</th></tr>'
                  + "".join(zeilen) + "</table></div>")
    return f"""
    <h2>Wie es sich entwickelt</h2>
    <div class="card">
      <div class="def">Ein Balken je Woche vom {esc(von)} bis {esc(bis)}. Die Höhe ist die
        Trefferquote der Woche, die Deckkraft zeigt, wie viele Aufgaben dahinterstehen —
        ein blasser hoher Balken beruht auf wenigen Antworten.</div>
      {inhalt}
    </div>"""


def _fertigkeiten(u):
    import speicher as SP
    wuensche = SP.wuensche_lesen()
    teile = []
    for b in u["bereiche"]:
        fs = [f for f in u["fertigkeiten"] if f["bereich"] == b["id"]]
        zeilen = "".join(
            f'<tr><td>{esc(f["titel"])}</td>'
            f'<td class="r muted">{f["stufe"]}</td>'
            f'<td class="r">{f["n"] or "–"}</td>'
            f'<td class="r">{pct(f["quote"]) if f["n"] else "–"}</td>'
            f'<td class="r">{esc(datum(f["letzte"]))}</td>'
            f'<td class="r">{tag(f["zustand"])}</td>'
            f'<td class="r">{_wunschknoepfe("skill", f["id"], _aktiv(wuensche, "skill", f["id"]))}'
            f'</td></tr>' for f in fs)
        teile.append(f"""<div class="card">
          <h3>{esc(b["emoji"])} {esc(b["titel"])}
            <span class="muted" style="font-weight:400;font-size:13.5px">
              — {b["sitzt"]} sitzt, {b["hakt"]} hakt, {b["arbeit"]} in Arbeit,
              {b["unberuehrt"]} noch nicht geübt</span></h3>
          <div class="scroll"><table>
            <tr><th>Fertigkeit</th><th class="r">Stufe</th><th class="r">Aufgaben</th>
                <th class="r">richtig</th><th class="r">zuletzt</th><th class="r">Zustand</th>
                <th class="r">Wunsch</th></tr>
            {zeilen}</table></div></div>""")

    gezaehlt = len(u["fertigkeiten"])
    return f"""
    <h2>Alle Fertigkeiten</h2>
    <div class="def">Alle {gezaehlt} Fertigkeiten des Lehrplans stehen hier, auch die noch
      nie geübten — sonst entstünde der Eindruck, es gäbe sie nicht.
      „{esc(A.ZUSTAND_TEXT["sitzt"])}“ heißt {esc(A.DEFINITION["sitzt"])};
      „{esc(A.ZUSTAND_TEXT["hakt"])}“ heißt {esc(A.DEFINITION["hakt"])};
      „{esc(A.ZUSTAND_TEXT["arbeit"])}“ heißt {esc(A.DEFINITION["arbeit"])}.</div>
    {"".join(teile)}"""


PLAN_TEXT = {"vor": "jetzt dran", "zurueck": "zurückgestellt", "ueber": "übersprungen"}

# V0/D: Was aus einem Planposten seit seiner Erstellung wirklich wurde. Ohne
# das bliebe unsichtbar, dass der Tutorplan vom 26.08. keine einzige seiner
# zehn vorgezogenen Fertigkeiten tatsächlich gestellt hat (ZIELE-V2.md, V0).
PLANPOSTEN_TEXT = {"gestellt": "gestellt", "verweigert": "verweigert",
                    "dran": "noch nicht dran",
                    "keins": "nicht stellbar — kein offenes Paket"}
PLANPOSTEN_FARBE = {"gestellt": FARBE["sitzt"], "verweigert": FARBE["hakt"],
                     "dran": FARBE["arbeit"], "keins": FARBE["hakt"]}


def _einheiten_je_fertigkeit():
    """Welche Paket-Ids zu welcher Fertigkeit gehören.

    Ein Sitzungsende-Ereignis kennt nur die Paket-Id, keine Fertigkeit — um
    einem Planposten (der eine Fertigkeit nennt) seine Sofort-Abbrüche
    zuzuordnen, muss diese Abbildung erst hergestellt werden. units_seed.json
    trägt keine eigene Id — das Gerät bildet sie zur Laufzeit aus
    "Fertigkeit@Stufe" (src/app.html), also wird hier genauso gebildet.
    """
    import json
    je = {}
    datei = A.ROOT / "data" / "units_seed.json"
    if datei.exists():
        try:
            for unit in json.loads(datei.read_text("utf-8")).get("units", []):
                sk, stufe = unit.get("skill"), unit.get("stage")
                if sk and stufe is not None:
                    je.setdefault(sk, []).append(f"{sk}@{stufe}")
        except (ValueError, OSError):
            pass
    return je


def _planposten_status(skill_id, seit, einheiten_je_fertigkeit, offene_gesamt):
    """gestellt / verweigert / nicht stellbar / noch nicht dran — in dieser
    Reihenfolge geprüft: Eine einzige Antwort zählt als "gestellt", auch wenn
    davor schon Sofort-Abbrüche liefen."""
    import speicher as SP
    ev = SP.alle_ereignisse()
    if any(e.get("e") == "a" and e.get("t", 0) >= seit and e.get("k") == skill_id
           for e in ev):
        return "gestellt"
    einheiten = set(einheiten_je_fertigkeit.get(skill_id) or [])
    abbrueche = sum(1 for e in ev if e.get("e") == "s" and e.get("t", 0) >= seit
                     and int(e.get("n") or 0) == 0 and e.get("u") in einheiten)
    if abbrueche >= 2:
        return "verweigert"
    if not (einheiten & offene_gesamt):
        return "keins"
    return "dran"


def _tutor(u):
    """Was der Tutor sich denkt — mit eigenen Worten, nicht in einer Schablone.

    Er entscheidet ohne Rückversicherung: Keine Schwelle überstimmt ihn. Was
    diese Seite leisten muss, ist deshalb nicht Kontrolle, sondern Sichtbarkeit
    — und ein Weg, ihm nachträglich zu widersprechen. Ein Sprung über mehrere
    Stufen wird angezeigt, aber nicht verhindert.
    """
    import lehrer as L
    p = L.lies_plan()
    if not p:
        return f"""
        <h2>Was der Tutor sich denkt{_ALLE_SPIELER}</h2>
        <div class="card">
          <div class="muted" style="font-size:14px">Noch hat er nicht nachgedacht.
            Er meldet sich von selbst, sobald genug Verlauf da ist —
            {L.NEUE_ANTWORTEN} Antworten genügen. Du kannst ihn auch von Hand
            anstoßen:</div>
          <form method="post" action="/tutor-jetzt" style="margin-top:10px">
            <button class="wb">Jetzt nachdenken lassen</button></form>
        </div>"""

    stufe = A.aktuelle_stufe()
    titel = {s["id"]: s for s in C.SKILLS}
    aktiv = {f["id"]: f for f in u["fertigkeiten"]}

    # V0/D: der Offen-Stand und die Paket-Zuordnung gelten für den ganzen Plan,
    # deshalb einmal vorher berechnet statt je Zeile neu.
    import speicher as SP
    seit_plan = p.get("t", 0)
    einheiten_je_fertigkeit = _einheiten_je_fertigkeit()
    offene_gesamt = SP.offene_pakete()

    zeilen, verworfen = [], list(p.get("hinweise") or [])
    for e in p.get("plan", []):
        sk = titel.get(e["skill"])
        if not sk:
            # Darf nicht lautlos verschwinden: Wenn der Tutor etwas nennt, das
            # es nicht gibt, ist das ein Befund über den Tutor.
            verworfen.append(f'unbekannte Fertigkeit „{e["skill"]}“ — Entscheidung '
                             f'nicht ausgeführt')
            continue
        f = aktiv.get(e["skill"], {})
        sprung = sk["stage"] - stufe
        hinweis = ""
        if e["art"] == "vor" and sprung > 1:
            hinweis = (f'<div style="color:{FARBE["arbeit"]};font-size:13px;margin-top:4px">'
                       f'⚠ Stufe {sk["stage"]}, er steht bei {stufe} — ein Sprung über '
                       f'{sprung} Stufen. Der Tutor will das so; wenn du anders denkst, '
                       f'stell es unten auf „erst später“.</div>')
        bisher = (f' · bisher {f["richtig"]}/{f["n"]} richtig' if f.get("n")
                  else " · noch nie geübt")
        status = _planposten_status(e["skill"], seit_plan, einheiten_je_fertigkeit,
                                     offene_gesamt)
        # D3: ist dieser Posten ein Vorlauf (Feld "fuer"), zeigt die Tabelle die
        # Kette mit an — sonst bliebe unsichtbar, dass er nicht für sich steht,
        # sondern eine Basics-Lücke vor einem anderen Ziel schließt.
        fuer_sk = titel.get(e.get("fuer") or "")
        vorlauf = (f'<div style="font-size:13px;margin-top:4px;color:{FARBE["arbeit"]}">'
                   f'↳ Vorlauf für {esc(fuer_sk["title"])}</div>' if fuer_sk else "")
        zeilen.append(
            f'<tr><td style="white-space:nowrap;width:1%">'
            f'<span class="tag" style="background:rgba(91,140,255,.2);color:#8fb0ff">'
            f'{esc(PLAN_TEXT.get(e["art"], e["art"]))}</span></td>'
            f'<td><b>{esc(sk["title"])}</b> '
            f'<span class="muted">Stufe {sk["stage"]}{esc(bisher)}</span>'
            f'<div style="font-size:14px;margin-top:2px">{esc(klartext(e["grund"]))}</div>'
            f'{vorlauf}'
            f'<div style="font-size:13px;margin-top:4px;color:{PLANPOSTEN_FARBE[status]}">'
            f'seit diesem Plan: {esc(PLANPOSTEN_TEXT[status])}</div>'
            f'{hinweis}</td>'
            f'<td style="text-align:right">'
            f'{_wunschknoepfe("skill", e["skill"], _aktiv(SP_wuensche(), "skill", e["skill"]))}'
            f'</td></tr>')

    erzeugen = "".join(
        f'<li>{esc((titel.get(e["skill"]) or {}).get("title", e["skill"]))} '
        f'(Stufe {e["stufe"]}): {esc(klartext(e["warum"]))}</li>' for e in p.get("erzeugen", []))
    k = p.get("kosten") or {}

    return f"""
    <h2>Was der Tutor sich denkt{_ALLE_SPIELER}</h2>
    <div class="card">
      <div class="def">Der Tutor entscheidet selbst — keine feste Schwelle überstimmt
        ihn. Hier steht, was er vorhat und warum, in seinen eigenen Worten. Bist du
        anderer Meinung, stell es rechts um; ein Elternwunsch geht seinem Plan vor.</div>
      <h3>Was ihm auffällt</h3>
      <div style="font-size:15.5px;line-height:1.6">{esc(klartext(p.get("beobachtung", "")))}</div>
      <h3 style="margin-top:18px">Für dich</h3>
      <div style="font-size:15.5px;line-height:1.6;white-space:pre-line">{esc(klartext(p.get("eltern", "")))}</div>
      <div class="muted" style="font-size:12.5px;margin-top:12px">
        Stand {esc(p.get("datum", "?"))} · auf Grundlage von
        {p.get("grundlage", {}).get("antworten", 0)} Antworten
        {f'· {k.get("rein", 0)} Token rein, {k.get("raus", 0)} raus' if k else ""}
      </div>
    </div>
    {'<div class="card"><h3>Seine Entscheidungen</h3><div class="scroll"><table>'
     + "".join(zeilen) + '</table></div></div>' if zeilen else ''}
    {'<div class="card warn"><h3>Davon ließ sich nicht alles ausführen</h3>'
     '<div class="def">Der Tutor entscheidet frei, aber er kann sich nur auf '
     'Fertigkeiten beziehen, die es gibt. Was hier steht, wurde übergangen.</div>'
     '<ul style="margin:6px 0 0 18px;font-size:14px;line-height:1.6">'
     + "".join(f"<li>{esc(h)}</li>" for h in verworfen)
     + '</ul></div>' if verworfen else ''}
    {f'<div class="card"><h3>Er hätte gern neue Pakete</h3><ul style="margin:6px 0 0 18px;'
     f'font-size:14.5px;line-height:1.6">{erzeugen}</ul>'
     f'<div class="def" style="margin-top:8px">Erzeugen kostet Geld und passiert '
     f'nicht von selbst: build/generate_units.py --skill &lt;Bezeichner&gt; --stage &lt;n&gt;'
     f'</div></div>' if erzeugen else ''}
    <div class="card">
      <form method="post" action="/tutor-jetzt">
        <button class="wb">Noch einmal nachdenken lassen</button>
        <span class="def" style="margin-left:8px">Kostet einen Modellaufruf, etwa 3 Cent.</span>
      </form>
    </div>"""


def SP_wuensche():
    import speicher as SP
    return SP.wuensche_lesen()


WUNSCH_TEXT = {"mehr": "mehr davon", "weniger": "weniger davon",
               "jetzt": "jetzt dran", "spaeter": "erst später"}


def _wunschknoepfe(ziel, kennung, aktiv):
    """Vier Knöpfe in einem Formular. Ohne JavaScript, damit die Seite in fünf
    Jahren noch tut, was sie heute tut."""
    knoepfe = "".join(
        f'<button name="art" value="{k}" class="wb{" an" if aktiv == k else ""}" '
        f'title="{esc(t)}">{esc(t)}</button>' for k, t in WUNSCH_TEXT.items())
    weg = ('<button name="art" value="weg" class="wb" title="Wunsch zurücknehmen">'
           '✕</button>' if aktiv else "")
    return (f'<form method="post" action="/wunsch" class="wf">'
            f'<input type="hidden" name="ziel" value="{esc(ziel)}">'
            f'<input type="hidden" name="id" value="{esc(kennung)}">'
            f'{knoepfe}{weg}</form>')


def _ziel_skills(w):
    """Die Fertigkeit(en), auf die sich ein Wunsch bezieht — bei einem
    Bereichswunsch alle Fertigkeiten dieses Bereichs."""
    if w.get("ziel") == "skill":
        return {w.get("id")}
    return {s["id"] for s in C.SKILLS if s["area"] == w.get("id")}


def _ziel_einheiten(w, einheiten_je_fertigkeit):
    ids = set()
    for sk in _ziel_skills(w):
        ids.update(einheiten_je_fertigkeit.get(sk) or [])
    return ids


def _wunsch_status(w, einheiten_je_fertigkeit, wirkung):
    """A/D: was aus einem Wunsch geworden ist, in einem von drei Worten.

    erfüllt am …    — ein "jetzt"-Wunsch, den der Dienst als erledigt markiert
                      hat (Paket einmal vollständig gespielt)
    wird verweigert — seit dem Wunsch mindestens zwei Sofort-Abbrüche und
                      keine einzige Antwort — nur bei "jetzt"/"mehr" sinnvoll,
                      denn nur die schieben dem Kind etwas heran
    wirkt           — sonst, der Regelfall
    """
    if w.get("status") == "erfuellt":
        return f'erfüllt am {datum(w.get("erfuellt_am") or w.get("t", 0))}', FARBE["sitzt"]
    if w.get("art") in ("jetzt", "mehr") and not wirkung["n"]:
        import speicher as SP
        einheiten = _ziel_einheiten(w, einheiten_je_fertigkeit)
        abbrueche = sum(1 for e in SP.alle_ereignisse()
                         if e.get("e") == "s" and e.get("t", 0) >= w.get("t", 0)
                         and int(e.get("n") or 0) == 0 and e.get("u") in einheiten)
        if abbrueche >= 2:
            return f'wird verweigert ({abbrueche}× weggetippt)', FARBE["hakt"]
    return "wirkt", FARBE["sitzt"]


def _wuensche(u):
    """Z4: was die Eltern angefragt haben, und was daraus geworden ist."""
    import speicher as SP
    liste = SP.wuensche_lesen()
    stufe = A.aktuelle_stufe()
    titel_von = {f["id"]: f for f in u["fertigkeiten"]}
    bereich_von = {b["id"]: b for b in u["bereiche"]}
    einheiten_je_fertigkeit = _einheiten_je_fertigkeit()

    if not liste:
        zeilen = ('<div class="muted" style="font-size:14px">Noch keine Wünsche. '
                  'Unten bei jeder Fertigkeit und hier bei jeder Welt kannst du sagen, '
                  'was häufiger, seltener, sofort oder später drankommen soll. '
                  'Der Tutor richtet sich spätestens beim zweiten Paket danach.</div>')
    else:
        z = []
        for w in sorted(liste, key=lambda x: -x.get("t", 0)):
            f = titel_von.get(w.get("id"))
            b = bereich_von.get(w.get("id"))
            name = (f["titel"] if f else (b["titel"] if b else w.get("id", "?")))
            wirkung = A.wunsch_wirkung(w)
            warnung = ""
            if w.get("art") == "jetzt" and f and f["stufe"] > stufe + 1:
                warnung = (f'<div style="color:{FARBE["hakt"]};font-size:13px;margin-top:3px">'
                           f'⚠ Stufe {f["stufe"]}, er steht bei {stufe}. Das ist ein Sprung '
                           f'über {f["stufe"]-stufe} Stufen — er wird das vermutlich nicht '
                           f'lösen können. Der Wunsch wird trotzdem ausgeführt.</div>')
            seit = (f'{wirkung["n"]} Aufgaben, davon {wirkung["richtig"]} richtig'
                    if wirkung["n"] else "seither noch nichts geübt")
            status_text, status_farbe = _wunsch_status(w, einheiten_je_fertigkeit, wirkung)
            z.append(
                f'<tr><td><b>{esc(name)}</b>'
                f'<div class="muted" style="font-size:12.5px">'
                f'{esc(WUNSCH_TEXT.get(w.get("art"), w.get("art","")))} · '
                f'seit {esc(datum(w.get("t", 0)))}: {esc(seit)} · '
                f'<span style="color:{status_farbe}">{esc(status_text)}</span></div>'
                f'{warnung}</td>'
                f'<td style="text-align:right">'
                f'{_wunschknoepfe(w.get("ziel","skill"), w.get("id",""), w.get("art"))}</td></tr>')
        zeilen = '<div class="scroll"><table>' + "".join(z) + "</table></div>"

    welten = "".join(
        f'<tr><td>{esc(b["emoji"])} {esc(b["titel"])}</td>'
        f'<td style="text-align:right">{_wunschknoepfe("bereich", b["id"], _aktiv(liste, "bereich", b["id"]))}</td></tr>'
        for b in u["bereiche"])

    return f"""
    <h2>Deine Wünsche{_ALLE_SPIELER}</h2>
    <div class="card">
      <div class="def">Ein Wunsch wirkt spätestens auf das zweite Paket, nachdem das Handy
        das nächste Mal im WLAN war. Er taucht dann oben im Protokoll als Begründung auf,
        und hier steht in Zahlen, was seither tatsächlich geübt wurde.
        Zurücknehmen geht jederzeit mit ✕.</div>
      {zeilen}
    </div>
    <div class="card">
      <h3>Nach Welt</h3>
      <div class="def">Gilt für alle Fertigkeiten dieser Welt. Einzelne Fertigkeiten
        stellst du weiter unten ein.</div>
      <div class="scroll"><table>{welten}</table></div>
    </div>"""


def _aktiv(liste, ziel, kennung):
    for w in liste:
        if w.get("ziel") == ziel and w.get("id") == kennung:
            return w.get("art")
    return None


def _protokoll():
    """Z3: jede Anpassung mit Begründung, die letzten zwanzig im Klartext."""
    import protokoll as P
    eintraege = P.eintraege(20)
    z = P.zaehlung()
    summe = sum(z.values())

    kacheln = "".join(
        f'<span class="tag" style="background:rgba(255,255,255,.07);color:#cddcf5;'
        f'margin-right:6px">{esc(text)}: {z[k]}</span>'
        for k, text in P.ARTEN.items())

    if not eintraege:
        liste = ('<div class="muted" style="font-size:14px">Noch hat der Tutor nichts '
                 'angepasst. Sobald er ein Paket vorzieht, zurückstellt oder überspringt, '
                 'steht es hier — mit den Zahlen, auf denen die Entscheidung beruht.</div>')
    else:
        zeilen = []
        for e in eintraege:
            wann = P._datum(e["t"]) + ("*" if e.get("ungenau") else "")
            # Bei einer Ablehnung steht das Versuchsprotokoll darunter — sonst
            # bliebe offen, woran der Prüfer sich gestoßen hat.
            versuche = "".join(
                f'<div class="muted" style="font-size:12.5px">· {esc(z)}</div>'
                for z in (e.get("log") or [])[:5])
            zeilen.append(
                f'<tr><td class="muted" style="white-space:nowrap;width:1%">{esc(wann)}</td>'
                f'<td class="muted" style="white-space:nowrap;width:1%;font-size:12.5px">'
                f'{esc(e["quelle"])}</td>'
                f'<td>{esc(P.satz(e))}{versuche}</td></tr>')
        liste = '<div class="scroll"><table>' + "".join(zeilen) + "</table></div>"

    ungenau = any(e.get("ungenau") for e in eintraege)
    fussnote = ('<div class="def" style="margin-top:8px">* Die Ablehnungen des Prüfers '
                'stehen ohne eigenen Zeitpunkt in der Datei; genommen wird ihr '
                'Änderungsdatum.</div>' if ungenau else "")

    return f"""
    <h2>Was der Tutor verändert hat</h2>
    <div class="card">
      <div class="def">Jede Anpassung erzeugt einen Eintrag — ohne Ausnahme, sonst wäre
        nicht nachvollziehbar, warum dein Kind gerade diese Aufgaben bekommt. Hier stehen
        die letzten {min(20, summe)} von insgesamt {summe}.</div>
      <div style="margin-bottom:12px">{kacheln}</div>
      {liste}
      {fussnote}
    </div>"""


TYP_TEXT = {"zahl": "Ausrechnen", "wahl": "Auswählen", "wahrfalsch": "Stimmt das?",
            "ordnen": "Ordnen", "paare": "Zuordnen", "mehrschritt": "Schritt für Schritt",
            "gitter": "Hinschauen", "entdecken": "Neu entdecken"}


def _vorrat(u):
    vr = u["vorrat"]
    typen = u["typen"]
    schief = [t for t in typen if t["anteil"] > A.TYP_MAX]
    liste = "".join(
        f'<tr><td>{esc(TYP_TEXT.get(t["typ"], t["typ"]))}</td><td class="r">{t["n"]}</td>'
        f'<td class="r" style="color:{FARBE["hakt"] if t["anteil"] > A.TYP_MAX else "inherit"}">'
        f'{pct(t["anteil"])}</td></tr>' for t in typen)
    fehlend = ", ".join(f'{esc(s["titel"])} (Stufe {s["stufe"]})' for s in vr["liste"][:12])
    return f"""
    <h3 style="margin-top:22px">Woran es beim Nachschub hakt</h3>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">
      <div class="card {"warn" if vr["unversorgt"] else "ok"}">
        <h3>Fertigkeiten ohne ein einziges Paket{_ALLE_SPIELER}</h3>
        <div class="def">Erreicht er eine davon, hat der Tutor nichts anzubieten.
          Ziel sind null.</div>
        <div class="kpi"><b style="color:{FARBE["hakt"] if vr["unversorgt"] else FARBE["sitzt"]}">
          {vr["unversorgt"]}</b><span>von {vr["gesamt"]} Fertigkeiten</span></div>
        {f'<div class="muted" style="font-size:13px;margin-top:8px">{fehlend}</div>' if fehlend else ""}
      </div>
      <div class="card {"warn" if schief else ""}">
        <h3>Welche Aufgabenarten er bekommt</h3>
        <div class="def">Kein Typ soll über {int(A.TYP_MAX*100)} % liegen — sonst übt er
          immer dasselbe Format, egal welchen Stoff.</div>
        {'<table><tr><th>Art</th><th class="r">Aufgaben</th><th class="r">Anteil</th></tr>'
         + liste + '</table>' if typen else '<div class="muted">Noch keine Aufgaben.</div>'}
      </div>
    </div>"""


def _geraete(u):
    """Welches Gerät wie viel beigesteuert hat — und was davon mitzählt.

    Solange nur ein Kind übt, ist das eine Fußnote. Sobald ein zweites Gerät
    auftaucht, ist es die Antwort auf die Frage, wessen Zahlen man hier
    eigentlich liest.
    """
    zeilen = []
    for g in u["geraete"]:
        luecke = g["gemeldet"] - g["antworten"]
        anmerkung = ""
        if not g["gezaehlt"]:
            anmerkung = "zählt nicht mit"
        elif luecke > 0:
            anmerkung = (f'{luecke} Antworten hat dieses Gerät gezählt, aber nie '
                         f'hierher geschickt')
        elif luecke < 0:
            anmerkung = f'{-luecke} Antworten mehr angekommen als gemeldet'
        # Trägt das Gerät einen Spielernamen (Elternwunsch 02.09.2026), steht der
        # voran — "Alex (a1b2c3d4…)" statt der nackten Kennung.
        kennung = f'{esc(g["name"])} ({esc(g["dev"][:8])}…)' if g.get("name") \
            else f'{esc(g["dev"][:8])}…'
        zeilen.append(
            f'<tr><td style="font-family:ui-monospace,monospace">{kennung}'
            f'<div class="muted" style="font-size:12.5px">{esc(anmerkung)}</div></td>'
            f'<td class="r">{g["antworten"]}</td>'
            f'<td class="r muted">{g["gemeldet"]}</td>'
            f'<td class="r muted" style="white-space:nowrap">{esc(datum(g["zuletzt"]))}</td>'
            f'<td class="r">'
            f'<form method="post" action="/geraet" class="wf">'
            f'<input type="hidden" name="dev" value="{esc(g["dev"])}">'
            f'<button name="art" value="{"aus" if g["gezaehlt"] else "ein"}" class="wb">'
            f'{"nicht mitzählen" if g["gezaehlt"] else "wieder mitzählen"}</button>'
            f'</form></td></tr>')
    return f"""
    <h3 style="margin-top:22px">Welches Gerät welche Zahlen liefert</h3>
    <div class="card">
      <div class="def">Ein Gerät, das nur zum Ausprobieren lief, verfälscht jede Zahl
        auf dieser Seite. „Nicht mitzählen“ nimmt es aus der Auswertung, ohne seine
        Aufzeichnung wegzuwerfen — rückgängig zu machen ist es jederzeit.</div>
      <div class="scroll"><table>
        <tr><th>Gerät</th><th class="r">hier angekommen</th><th class="r">selbst gezählt</th>
            <th class="r">zuletzt gesehen</th><th class="r"></th></tr>
        {"".join(zeilen)}</table></div>
    </div>"""


def _technik(u):
    """Alles, was die Seite über sich selbst weiß — ans Ende und zugeklappt.

    Zählstände, Vorratslücken und Geräte gehören zur Wahrheit dieser Seite,
    aber nicht an ihren Anfang: Wer wissen will, wie es seinem Kind geht, soll
    nicht zuerst eine Ereigniszählung lesen müssen.
    """
    z = u["zaehlstand"]
    if z["abweichung"] == 0:
        stand = ('<div class="card ok"><h3>Die Zählung geht auf</h3>'
                 '<div class="muted" style="font-size:14px">Gerät und Dienst zählen '
                 f'gleich viele Antworten: {u["antworten"]} beantwortete Aufgaben aus '
                 f'{u["ereignisse"]} Ereignissen.</div></div>')
    elif z["abweichung"] < 0:
        stand = ('<div class="card warn"><h3>Es fehlen Antworten</h3>'
                 '<div class="muted" style="font-size:14px">'
                 f'Die Geräte haben {z["antworten_geraete"]} Antworten gezählt, hier '
                 f'angekommen sind {z["antworten_hier"]} — es fehlen '
                 f'{-z["abweichung"]}. Welches Gerät die Lücke hat, steht unten. '
                 'Alles, was auf dieser Seite steht, beruht nur auf dem, was '
                 'angekommen ist.</div></div>')
    else:
        stand = ('<div class="card warn"><h3>Hier liegt mehr, als gemeldet wurde</h3>'
                 '<div class="muted" style="font-size:14px">'
                 f'Angekommen sind {z["antworten_hier"]} Antworten, gezählt haben die '
                 f'Geräte {z["antworten_geraete"]}. Das passiert, wenn ein Gerät seinen '
                 'Fortschritt gelöscht hat, die alten Daten hier aber liegen '
                 'bleiben.</div></div>')
    verfallen = (f'<div class="def">{z["verfallen"]} Ereignisse waren älter als '
                 f'{A.WOCHEN*7} Tage und sind auf dem Gerät verfallen.</div>'
                 if z["verfallen"] else "")
    return f"""
    <h2 id="technik">Technik und Datengrundlage{_ALLE_SPIELER}</h2>
    <details{" open" if z["abweichung"] else ""}>
      <summary class="muted" style="cursor:pointer;font-size:14px;margin-bottom:12px">
        Woher die Zahlen kommen, welches Gerät sie liefert und ob der Nachschub reicht
      </summary>
      {stand}{verfallen}
      {_geraete(u)}
      {_vorrat(u)}
    </details>"""


# ------------------------------------------------------------------- Die Seite

def _spieler_beschriftung(g):
    """Eintrag in der Auswahl: Spielername, sonst gekürzte Kennung; ein
    ausgeblendetes (ignoriertes) Gerät trägt zusätzlich „ · Testgerät“."""
    name = g["name"] or f'{g["dev"][:8]}…'
    return name + (" · Testgerät" if not g["gezaehlt"] else "")


def _spieler_auswahl(stand, gewaehlt):
    """Oben auf der Seite: welches Gerät — welches Kind — wird gezeigt?

    Ein GET-Formular ohne JavaScript-Framework, wie die Wunsch-Knöpfe weiter
    unten: onchange schickt es sofort ab. Ausgeblendete (ignorierte) Geräte
    stehen mit in der Liste — nur mitgezählt werden sie deshalb noch lange
    nicht (siehe _testgeraet_hinweis).
    """
    optionen = "".join(
        f'<option value="{esc(g["dev"])}"'
        f'{" selected" if gewaehlt and g["dev"] == gewaehlt["dev"] else ""}>'
        f'{esc(_spieler_beschriftung(g))}</option>' for g in stand)
    return f"""
    <form method="get" action="/eltern" style="margin:24px 0 0">
      <label class="muted" style="font-size:13px">Welches Kind?
        <select name="spieler" onchange="this.form.submit()"
          style="margin-left:8px;background:rgba(255,255,255,.07);color:#eef3ff;
            border:1px solid rgba(255,255,255,.16);border-radius:8px;
            padding:4px 10px;font-family:inherit;font-size:14px">
          {optionen}
        </select>
      </label>
    </form>"""


def _testgeraet_hinweis():
    return ('<div class="def" style="margin-top:8px">Dieses Gerät ist als '
            'Testgerät ausgeblendet — es zählt nicht in Auswertung oder '
            'Tutorplan mit.</div>')


def seite(zusatz="", spieler=None):
    """spieler: die Geräte-Id aus /eltern?spieler=... (server.py reicht sie
    unverändert durch). Sie bestimmt, wessen Ereignisse die spielerbezogenen
    Abschnitte zeigen (Elternwunsch 03.09.2026) — Elternwünsche, Tutorplan,
    Vorratsteil und Technik bleiben davon unberührt (_ALLE_SPIELER).

    Fehlt der Parameter oder passt er zu keinem bekannten Gerät, fällt die
    Auswahl still auf das zählende Gerät mit den meisten Antworten zurück;
    gibt es noch gar kein Gerät, verhält sich die Seite wie eh und je.
    """
    import speicher as SP
    stand = SP.geraetestand()
    gewaehlt = None
    if stand:
        je_dev = {g["dev"]: g for g in stand}
        gewaehlt = je_dev.get(spieler) if spieler else None
        if gewaehlt is None:
            gewaehlt = next((g for g in stand if g["gezaehlt"]), stand[0])

    if gewaehlt:
        u = A.ueberblick(ereignisse=SP.ereignisse_von(gewaehlt["dev"]))
        name = gewaehlt["name"] or None
    else:
        u = A.ueberblick()
        name = None

    kopfzusatz = _spieler_auswahl(stand, gewaehlt) if stand else ""
    if gewaehlt and not gewaehlt["gezaehlt"]:
        kopfzusatz += _testgeraet_hinweis()

    if not u["ereignisse"]:
        inhalt = f"""
        {kopfzusatz}
        <h1>Wie läuft es?</h1>
        <div class="card leer">
          <p>Noch sind keine Daten angekommen.</p>
          <p class="muted" style="font-size:14px">Sobald das Handy im WLAN zu Hause ist,
            schickt die App den Lernstand hierher — beim Start und nach jeder Sitzung.
            In der App steht die Adresse dieses Rechners unter
            Einstellungen ▸ Lernstand für die Elternseite.</p>
        </div>{_motivation(u, name)}{zusatz}{_tutor(u)}{_protokoll()}{_wuensche(u)}"""
    else:
        inhalt = (kopfzusatz + _kopf(u) + _fazit(u, name) + _motivation(u, name) + zusatz
                  + _tutor(u) + _nordstern(u["nordstern"])
                  + _auffaellig(u["fertigkeiten"]) + _verlauf(u)
                  + _protokoll() + _wuensche(u) + _fertigkeiten(u) + _technik(u))

    return f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MathCraft — Elternseite</title>
<style>{CSS}</style>
<div class="wrap">
{inhalt}
<div class="muted" style="font-size:13px;margin-top:34px">
  <a href="/">Zur Update-Seite</a> · Alle Schwellen stehen in ZIELE.md und in
  tutor/auswertung.py; wer sie ändert, ändert die Aussagen dieser Seite.
</div>
</div></html>"""
