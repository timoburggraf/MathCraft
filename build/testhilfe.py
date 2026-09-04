# -*- coding: utf-8 -*-
"""Kleine Hilfen, die alle Browser-Tests brauchen.

Der eine Zweck, der hier alles begründet: Ein Test darf den echten Heim-Dienst
nicht mit Übungsdaten volllaufen lassen.

Die gebaute index.html trägt die WLAN-Adresse des Rechners als Voreinstellung
in sich — das ist im Betrieb genau richtig, damit niemand sie abtippen muss.
Im Test ist es eine Falle: Die App überträgt beim Start und nach jeder Sitzung
von sich aus, und ein Testlauf, der ein paar Pakete durchklickt, landet dann
im Lernstand des Kindes. Auf der Elternseite stünden anschließend Antwortzeiten
von 70 Millisekunden, und die Aussage der Seite wäre hin.

Deshalb: vor jedem page.goto() ohne_dienst(page) aufrufen. Wer eine Adresse
braucht, setzt sie danach im Test ausdrücklich.
"""

# Läuft vor jedem Skript der Seite, auch nach einem Neuladen. Ein Speicherstand
# mit leerer Adresse genügt — serverUrl() gibt dann nichts zurück, und jede
# Übertragung endet, bevor sie beginnt.
#
# Nur, wenn noch nichts gespeichert ist: Ein Test, der selbst eine Adresse
# einträgt und danach neu lädt, prüft damit ja gerade, dass sie bleibt.
_LEER = """
try {
  if (!localStorage.getItem('mathcraft_v1')) {
    localStorage.setItem('mathcraft_v1', JSON.stringify({v: 1, server: ''}));
  }
} catch (e) {}
"""

# freshState() holt sich sonst die eingebackene Adresse zurück, und mehrere
# Tests setzen den Stand zurück. Deshalb ist sie auch an der Quelle leer.
# S selbst wird nicht angefasst — was ein Test dort einträgt, bleibt seins.
_QUELLE = """
window.addEventListener('DOMContentLoaded', () => {
  try { BUILD.server = ''; } catch (e) {}
});
"""


def ohne_dienst(page):
    """Nimmt der Seite die eingebackene Serveradresse. Vor page.goto() aufrufen."""
    page.add_init_script(_LEER)
    page.add_init_script(_QUELLE)
    return page
