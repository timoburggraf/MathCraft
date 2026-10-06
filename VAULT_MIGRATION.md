# Vault und privater Dienstbetrieb

Der laufende Dienst ist vom Benutzerkonto getrennt. `mathcraft` (UID 998,
kein Login) kann den vollständigen Vault und den Signierschlüssel der gemeinsamen
CA nicht lesen. Code und Python-Umgebung unter `/opt/mathcraft` gehören root;
private Schreibzugriffe sind auf `/var/lib/mathcraft/state` begrenzt.

## Credentials und Rotation

`konfig.geheim()` bezieht Anbieter- und Signier-Secrets aus dem zentralen
Vault. Der Produktionsdienst liest ausschließlich `/etc/mathcraft/vault.json`
(Besitzer mathcraft, 0600; Elternverzeichnis root:mathcraft 0750):

- `ANTHROPIC_API_KEY`
- `MATHCRAFT_PARENT_PASSWORD`
- `MATHCRAFT_SESSION_KEY`
- `MATHCRAFT_DEVICE_KEY`

Die drei Authentifizierungswerte wurden zufällig generiert und im Vault
abgelegt. Die Anbieterberechtigungen bleiben die des verwendeten API-Keys;
ein eigener beschränkter MathCraft-Anbieterschlüssel und ein Anbieterbudget
sind eine zusätzliche Schutzmaßnahme. Native Android-Signierschlüssel werden
niemals an den Server oder die mobile App projiziert.

Nach einer Vault-Rotation muss der Betreiber die minimale Projektion atomar
neu erzeugen und `mathcraft-secure` neu starten. `build/render_security_projection.py
--output <privater-Pfad-außerhalb-des-Projekts>` verlangt ein eigenes Verzeichnis
0700 und erzeugt eine Datei 0600; die anschließende privilegierte Installation
setzt Besitzer mathcraft. Niemals Werte mit Shell-Argumenten oder `cat` übertragen.
Rotation des Session-Keys beendet Sitzungen; Rotation des Device-Keys erfordert
neue Paarung. Alte Kopien und verschlüsselte Backups bleiben vertraulich.

## Deployment und Wiederherstellung

Die System-Units liegen als Methodik in `tutor/mathcraft-secure.service` und
`tutor/mathcraft-updates.service`. Der Produktions-WSGI-Server ist Gunicorn;
`requirements-server.lock` pinnt dessen Paket und Wheel-Prüfsumme. TLS-Material
liegt ausschließlich unter `/etc/mathcraft`; die gemeinsame CA wird zentral
verwaltet, der private CA-Schlüssel ist ausschließlich root zugänglich.
Der öffentliche CA-Anker für Android liegt in `android/app/src/main/res/raw`.
Das Dienstzertifikat ist derzeit 90 Tage gültig und muss rechtzeitig erneuert
werden. Eltern-Browser benötigen Vertrauen in diese öffentliche Projekt-CA.

Vor dem Umschalten wurden Code, alte Unit und private Daten verschlüsselt
archiviert; der finale Lernstand wurde nach Stoppen des alten Diensts
bytegleich in die neue private Ablage übertragen. Die ursprünglichen privaten
Dateien im Projekt wurden erst nach authentifizierter Backup-Prüfung entfernt.
Ein Rollback muss Authentifizierung und HTTPS beibehalten: keine Wiederaktivierung
des früher offenen Diensts. Release-Code wird root-verwaltet über
`/opt/mathcraft/current` ausgewählt. Vor neuen Releases eine geprüfte, sichere
Version und einen verschlüsselten Zustands-Snapshot für Wiederherstellung behalten.

## Eltern und Geräte

Eltern öffnen `https://192.168.0.152:8792/login` und verwenden den Vault-Eintrag
`MATHCRAFT_PARENT_PASSWORD`. Sitzungen sind serverseitig widerrufbar, maximal
acht Stunden gültig und durch Secure/HttpOnly/SameSite-Cookies geschützt.
Änderungsformulare haben einmalige CSRF-Tokens. Anmeldung und Paarung sind
begrenzt; Tutoraktionen höchstens dreimal pro Stunde. Synchronisation löst
keine automatische bezahlte Tutoraktion mehr aus.

Geräte werden auf der Elternseite anhand ihrer Gerätekennung freigegeben.
Der Paarungscode gilt fünf Minuten und nur einmal. Danach signiert die App
jede private Anfrage (Methode, Pfad, Zeit, Nonce und Body) mit einem eigenen
Geräteschlüssel. Zeitfenster, persistent gespeicherte Nonces und Widerruf schützen
vor Replay. Geräte dürfen nur ihren eigenen Lernstand liefern; bezahlte
Erklärungen müssen Eltern separat erlauben (zehn pro Tag/Gerät).

Android verwahrt den Geräteschlüssel verschlüsselt mit AndroidKeyStore;
Klartext-Netzwerk und App-Backups sind ausgeschaltet. Hardwarebindung ist ohne
echtes Gerät nicht verifiziert. Browser speichern ihre begrenzte Geräteberechtigung
in origin-gebundenem localStorage; kompromittierter Browser oder gleichberechtigte
lokale Prozesse bleiben eine Sicherheitsgrenze. Das neue APK ist signiert und
bereitgestellt, wird aber nicht ohne Interaktion auf einem Kindgerät installiert.
Alte Clients bleiben offline nutzbar; Sync verlangt Upgrade, richtige HTTPS-Adresse
und neue Paarung. Bereits installierte native Clients wurden nicht geändert.

## Prüfungen

`build/security_test.py` prüft mit Dummy-Secrets Autorisierung, CSRF, Replay,
Gerätepaarung, Widerruf, CORS, Ratenlimits und den echten JS-HMAC gegen den
Server. Es werden weder bezahlte Modelle noch Geräteaktionen ausgeführt.
Im Livebetrieb wurden anonym 401/403, gültiger Elternlogin 200, Logout und
Dienst-UID-/Dateizugriffsisolation separat nachgewiesen. Private Prüfberichte
und verschlüsselte Wiederherstellungsarchive liegen lokal im Vault-Auditbereich,
nicht in diesem App-Repository.
