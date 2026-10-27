# Benutzerhandbuch – LTO Tape Studio

## 1. Überblick

**LTO Tape Studio** ist eine professionelle Enterprise-Desktop-Anwendung zur vollständigen Steuerung, Verwaltung und Archivierung von LTO-Bandlaufwerken (LTO-1 bis LTO-10) unter Linux. Sie bietet ein modernes Dark-Theme-Interface, Echtzeit-Telemetrie, Multivolume-Unterstützung, kryptografische Integritätsprüfung und optionale Verschlüsselung.

**Programmed by Jörg Althaus**

### Kernfunktionen auf einen Blick

| Funktion | Beschreibung |
|---|---|
| **LTO-1 … LTO-10** | Dynamische Unterstützung aller Generationen mit automatischer Kapazitäts-, Blockgrößen- und Transferraten-Anpassung |
| **Multivolume** | Nahtlose Fortsetzung über mehrere Bänder bei EOT, mit interaktivem Bandwechsel-Dialog |
| **Multi-Source-Backup** | Beliebig viele Ordner, Dateien und Mountpoints gleichzeitig als Quell-Queue |
| **3 Kompressionsmodi** | Unkomprimiert, Software (zstandard/gzip), Hardware (Laufwerksregister) |
| **Integrität** | MD5, SHA-256, SHA-512 zur Bit-Rot-Erkennung |
| **Verschlüsselung** | Optionale Fernet/AES-Verschlüsselung mit Passphrase |
| **Read-after-Write** | Optionale physische Verifikation geschriebener Daten |
| **Telemetrie** | Live-Transferrate (MB/s), Kapazitätsauslastung, Temperatur, Load-Count |
| **Audit-Log** | Thread-sicheres Echtzeit-Logging (GUI + rotierende Datei) |
| **Scheduler** | In-Process Job-Scheduling mit Wiederholung |
| **i18n** | Englisch / Deutsch umschaltbar |

---

## 2. Oberfläche im Detail

### 2.1 Live-Dashboard (oberer Bereich, immer sichtbar)

Das Dashboard zeigt den aktuellen Zustand des Bandlaufwerks in Echtzeit und aktualisiert sich jede Sekunde.

| Element | Bedeutung |
|---|---|
| **Device** | Aktives Gerät (z. B. `/dev/nst0`) |
| **Generation** | Erkannte oder manuell gesetzte LTO-Generation (LTO-1 … LTO-10) |
| **Status** | `ready`, `not_ready`, `write_protected`, `end_of_tape`, `beginning_of_tape`, `offline`, `unknown` |
| **Speed** | Aktuelle Transferrate in MB/s (während laufender Jobs) |
| **Capacity** | Geschriebene / Gesamtkapazität in GB |
| **Fortschrittsbalken** | Kapazitätsauslastung in Prozent |
| **Telemetry** | Hardware-Telemetrie (Temperatur in °C, Load-Count) – best-effort via `sg_logs` |

### 2.2 Tabs

#### Tab „Backup"
Quellenauswahl und Backup-Optionen.

**Quellenauswahl (Source Selector):**
- **Add Folder** – Einzelnen Ordner als Quelle hinzufügen
- **Add File** – Einzelne Dateien hinzufügen
- **Add Disk/Mount** – Kompletten Mountpoint / Festplatte als Quelle
- **Remove** – Ausgewählte Einträge entfernen
- **Clear** – Alle Einträge leeren
- Mehrfachauswahl möglich (Extended Selection)

**Backup-Optionen:**
| Option | Werte | Beschreibung |
|---|---|---|
| Compression | `none`, `software_zstd`, `software_gzip`, `hardware` | Kompressionsmodus |
| Checksum | `md5`, `sha256`, `sha512` | Hash-Algorithmus für Integritätsprüfung |
| Label | Text | Name des Archivs (wird in Volume-Header geschrieben) |
| Block size | Zahl (Standard 262144) | Blockgröße in Bytes |
| Encrypt | Checkbox + Passphrase | Optionale Fernet-Verschlüsselung |
| Verify (read-after-write) | Checkbox | Physische Verifikation nach dem Schreiben |

**Aktionen:**
- **Start Backup** – Startet den Backup-Job in einem Worker-Thread
- **Cancel** – Bricht den laufenden Job ab
- **Fortschrittsbalken** – 0–100 % des Gesamtvolumens
- **Current file** – Zeigt die aktuell verarbeitete Datei an

**Einstellungen werden automatisch gespeichert** (Label, Blockgröße, Encrypt-Status, Kompression, Hash, Sprache). Die Passphrase wird aus Sicherheitsgründen **nicht** persistiert.

#### Tab „Tape Operations"
Direkte Bandsteuerung und Generationsauswahl.

| Bedienelement | Funktion |
|---|---|
| Generation (ComboBox) | LTO-1 bis LTO-10 manuell setzen |
| Rewind | Band zum Anfang (BOT) zurückspulen |
| Eject | Band auswerfen (offline) |
| Retension | Band retensionieren (Spannung ausgleichen) |
| Erase | Band vollständig löschen |
| Status | Status des Laufwerks abfragen |

#### Tab „Job Queue"
Anzeige enqueueter Backup-Jobs mit Möglichkeit zum Abbruch ausgewählter Jobs.

#### Tab „Restore"
Wiederherstellung aus Band oder Volume-Dateien.

| Element | Funktion |
|---|---|
| Destination | Zielverzeichnis für wiederhergestellte Dateien |
| Passphrase | Passphrase bei verschlüsselten Archiven |
| Browse | Verzeichnisauswahl-Dialog |
| Restore from Tape | Liest vom Gerät (Multivolume: fordert weitere Bänder an) |
| Restore from Volume Files | Offline-Restore aus Image-Dateien |

Die Wiederherstellung verifiziert SHA-256-Hashes automatisch.

### 2.3 Menüleiste

| Menü | Einträge |
|---|---|
| **Help** | About (Version, Autor, Beschreibung) |
| **Language** | English / Deutsch (Neustart für volle Wirkung empfohlen) |

### 2.4 Audit-Log (unterer Bereich)
Echtzeit-Protokoll aller Aktionen mit Zeitstempel, Level, Thread und Nachricht. Wird gleichzeitig in eine rotierende Logdatei (`~/.lto_tape_studio/audit.log`, max. 5 MB, 5 Backups) geschrieben.

---

## 3. Backup-Ablauf (Detailliert)

1. **Quellen einsammeln** – Alle angegebenen Pfade werden rekursiv durchlaufen; Dateien werden mit Metadaten (Pfad, Größe, mtime, Mode) erfasst.
2. **Hash berechnen** – Für jede Datei wird der gewählte Hash (MD5/SHA-256/SHA-512) berechnet.
3. **Kompression umschalten** – Bei Hardware-Kompression wird das Laufwerksregister gesetzt.
4. **Blockgröße setzen** – Falls angegeben.
5. **Volume öffnen** – Preamble `LTOVS1 <compression>` + VOLUME-Record.
6. **Dateien streamen** – Jede Datei wird in konfigurierbare Parts (Standard 64 MB) gesplittet; bei Bedarf verschlüsselt; Parts werden als `FILEPART`-Records geschrieben.
7. **Kapazitätsüberwachung** – Bei Erreichen der Bandkapazität (98 % Sicherheitsmarge) wird das Volume geschlossen und das nächste Band angefordert.
8. **EOT-Erkennung** – Schreibfehler und Statusabfragen erkennen das Bandende; Multivolume-Wechsel wird ausgelöst.
9. **Abschluss** – END-Record, Rewind des Bandes.
10. **Optional: Verifikation** – Read-after-Write liest das Archiv zurück und vergleicht Hashes.

### Multivolume-Bandwechsel

Sobald ein Band voll ist:
1. Der Job pausiert automatisch.
2. Ein modaler Dialog erscheint: „Bitte Band #X einlegen".
3. Nach Einlegen und Bestätigung (OK) wird das neue Medium initialisiert (Rewind, Volume-Header).
4. Der Stream wird nahtlos fortgesetzt.
5. Bei Abbruch (Cancel) wird der Job beendet.

Große Dateien werden automatisch so gesplittet, dass kein Record eine Bandgrenze überschreitet.

---

## 4. Restore-Ablauf (Detailliert)

1. **Volume öffnen** – Preamble lesen → Kompressionsmodus erkennen.
2. **Records parsen** – `VOLUME`, `FILEPART`, `VOLUME_END`, `END`.
3. **Parts gruppieren** – Nach Dateipfad sortiert.
4. **Reassemblieren** – Parts werden in richtiger Reihenfolge zusammengefügt; bei Verschlüsselung entschlüsselt.
5. **Dateien schreiben** – Zielpfad erstellen, Mode und mtime wiederherstellen.
6. **Hash-Verifikation** – SHA-256 (oder gewählter Algorithmus) wird verglichen; Mismatch wird geloggt.
7. **Multivolume** – Bei Restore von Band werden weitere Bänder angefordert.

---

## 5. Kompressionsmodi im Detail

| Modus | Beschreibung | Einsatz |
|---|---|---|
| **none (Unkomprimiert)** | Direkter Datenstrom, keine Beeinflussung | Maximale Integrität, bereits komprimierte Daten |
| **software_zstd** | CPU-basierte zstandard-Kompression (Fallback gzip) | Hohe Kompression, moderate CPU-Last |
| **software_gzip** | gzip-Kompression | Universelle Kompatibilität |
| **hardware** | Laufwerks-eigene On-the-Fly-Kompression (`mt compression 1`) | Maximale Durchsatzrate, keine Host-CPU-Last |

Bei Software-Kompression wird der Stream transparent gewrappt; das Containerformat bleibt identisch.

---

## 6. Integrität & Sicherheit

### Checksummen
- **MD5** – Schnell, für nicht-kritische Prüfungen
- **SHA-256** – Standard, empfohlen
- **SHA-512** – Maximale Sicherheit

Hashes werden pro Datei berechnet und im letzten `FILEPART`-Record gespeichert. Bei Restore wird automatisch verglichen.

### Verschlüsselung
- **Algorithmus:** Fernet (AES-128-CBC + HMAC-SHA256)
- **Schlüsselableitung:** PBKDF2-HMAC-SHA256, 200.000 Iterationen, Salt `lto-tape-studio`
- **Anwendung:** Pro Part (Datei-Chunk), nicht das gesamte Archiv
- **Passphrase:** Wird nicht gespeichert; muss bei Restore eingegeben werden

### Read-after-Write
Optionale physische Verifikation: Nach dem Schreiben wird das Band zurückgespult, das Archiv zurückgelesen und jeder Datei-Hash neu berechnet und verglichen. Erkennt Schreibfehler und Bit-Rot frühzeitig.

---

## 7. Konfiguration

Konfigurationsdatei: `~/.lto_tape_studio/config.json`

Gespeicherte Werte:
- `label` – Letztes Backup-Label
- `block_size` – Letzte Blockgröße
- `encrypt` – Encrypt-Checkbox-Zustand
- `compression` – Letzter Kompressionsmodus
- `hash` – Letzter Hash-Algorithmus
- `language` – Gewählte Sprache (en/de)

Logdatei: `~/.lto_tape_studio/audit.log` (rotierend, 5 MB, 5 Backups)

---

## 8. Systemintegration

### udev-Regeln
Die Datei `resources/99-lto-tape.rules` erstellt persistente Symlinks (`/dev/tape0`, `/dev/ntape0`) und setzt Gruppenrechte (`GROUP="tape"`, `MODE="0660"`).

### Desktop-Integration
`resources/lto_tape_studio.desktop` mit Icon und Kategorien `System;Archiving;`.

### AppImage
Portables AppImage mit eingebetteten Python-Abhängigkeiten, Qt-Bibliotheken und Binaries. Programmer-Credit „Jörg Althaus" in Metadaten.

---

## 9. Tastenkürzel & Bedienhinweise

- **Multivolume-Dialog:** OK = nächstes Band bestätigen, Cancel = Job abbrechen
- **Fortschritt:** Echtzeit-Updates via Qt-Signale (thread-sicher)
- **Pause/Resume:** Backup-Engine unterstützt Pausieren und Fortsetzen (API)

---

## 10. Fehlerbehebung (Kurzreferenz)

| Problem | Lösung |
|---|---|
| `mt: command not found` | `mt-st` installieren |
| Permission denied | `sudo usermod -aG tape $USER`, neu anmelden |
| Kein Gerät gefunden | udev-Regeln prüfen, Laufwerk einschalten |
| EOT nicht erkannt | App fängt Schreibfehler + Kapazitätsschwellen ab |
| Checksum-Mismatch | Passphrase prüfen, alle Volumes in Reihenfolge |
| AppImage startet nicht | `chmod +x`, FUSE prüfen |
| Tests | `QT_QPA_PLATFORM=offscreen python tests/test_roundtrip.py` |

---

## 11. Lizenz & Autor

**Programmed by Jörg Althaus**

Enterprise LTO tape management and archiving for Linux. Siehe Repository-Root für Lizenzdetails.