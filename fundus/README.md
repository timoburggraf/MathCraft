# Fundus

Hier landet, was ersetzt wurde — damit es nicht verloren ist.

Jedes Aufgabenpaket, jedes Bild und jede Tonspur hat Rechenzeit, Geld und oft
mehrere Anläufe gekostet. Wird etwas neu erzeugt, ist die alte Fassung deshalb
nicht wertlos: Sie kann besser gewesen sein als die neue, sie kann zu einem
anderen Kind passen, und sie ist der einzige Beleg dafür, was ein Kind damals
tatsächlich vor sich hatte.

```
fundus/pakete/<fertigkeit>@<stufe>/<zeitstempel>.json
fundus/bilder/<name>/<zeitstempel>.png
```

Angelegt wird das automatisch, bevor überschrieben wird:

| Wer | Wann |
|---|---|
| `build/kern_pakete.py --force` | ersetzt ein vorhandenes Kern-Paket |
| `build/generate_units.py --skill …` | ersetzt ein vorhandenes Paket |
| `build/make_images.py --force` | überschreibt ein vorhandenes Bild |

**Die Vorlesestimmen stehen nicht hier.** `data/audio/<stimme>/<id>.opus` ist
über den Dateinamen inhaltsadressiert — die Kennung ist der crc32 des
gesprochenen Textes. Ein geänderter Text bekommt damit eine neue Datei, statt
die alte zu überschreiben. Die Sammlung ist von sich aus ein Fundus und hat
noch nie eine Aufnahme verloren; sie braucht diesen Ordner nicht.

**Zurückholen** geht von Hand: die Datei aus dem Fundus nach
`data/units_seed.json` bzw. `img/raw/` zurückkopieren. Absichtlich kein
Automatismus — wer eine alte Fassung zurückholt, soll sie vorher angesehen
haben.

Was gerade drinliegt:

```bash
.venv/bin/python build/fundus.py
```
