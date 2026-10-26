# Benutzerhandbuch

## Oberfläche

Die Anwendung besteht aus einem Live-Dashboard und mehreren Tabs:

- **Dashboard** – Gerät, Generation, Status, Transferrate (MB/s), Kapazitätsauslastung.
- **Backup** – Quellenauswahl, Backup-Optionen, Start/Abbruch, Fortschritt.
- **Tape Operations** – Rewind, Eject, Retension, Erase, Status, Generationsauswahl.
- **Job Queue** – Anzeige enqueueter Jobs.
- **Restore** – Wiederherstellung aus Band oder Volume-Dateien.
- **Audit Log** – Echtzeit-Protokoll.

## Backup erstellen

1. Im Tab **Backup** Quellen hinzufügen (Ordner, Dateien, Mountpoints) über **Add Folder / Add File / Add Disk**.
2. Optionen wählen:
   - **Compression**: `none`, `software_zstd`, `software_gzip`, `hardware`
   - **Checksum**: `md5`, `sha256`, `sha512`
   - **Label**: Name des Archivs
   - **Block size**: Standard 262144
   - **Encrypt**: optional, mit Passphrase
3. **Start Backup** klicken.

Während des Backups zeigt das Dashboard Transferrate und Fortschritt. Bei Erreichen des Bandendes (EOT) erscheint ein modalen Dialog zur Anforderung des nächsten Bandes.

## Multivolume (mehrere Bänder)

Sobald ein Band voll ist, pausiert der Job und fordert Band #N an. Nach Einlegen und Bestätigung wird nahtlos fortgesetzt. Große Dateien werden automatisch in passende Teile gesplittet.

## Restore (Wiederherstellung)

1. Tab **Restore** öffnen.
2. Zielverzeichnis wählen.
3. **Restore from Tape** (liest vom Gerät, fordert bei Multivolume weitere Bänder an) oder **Restore from Volume Files** (Offline-Restore aus Image-Dateien).
4. Passphrase angeben, falls das Archiv verschlüsselt ist.

Die Wiederherstellung verifiziert SHA-256-Hashes automatisch.

## Tape-Operationen

- **Rewind** – Band zum Anfang zurückspulen.
- **Eject** – Band auswerfen (offline).
- **Retension** – Band retensionieren.
- **Erase** – Band löschen.
- **Status** – Status abfragen.
- **Generation** – LTO-Generation manuell setzen (LTO-1 bis LTO-10).

## Audit-Log

Alle Aktionen werden thread-sicher protokolliert (GUI + rotierende Logdatei unter `~/.lto_tape_studio/audit.log`).
