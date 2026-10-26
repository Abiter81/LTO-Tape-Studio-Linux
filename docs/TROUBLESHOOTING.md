# Fehlerbehebung

## „mt: command not found“
`mt-st` installieren (siehe Installation) und sicherstellen, dass `mt` im PATH liegt.

## „Permission denied“ beim Gerätezugriff
Benutzer der Gruppe `tape` hinzufügen und neu anmelden:
```bash
sudo usermod -aG tape $USER
```

## Kein Gerät gefunden
- udev-Regeln installiert und neu geladen?
- Laufwerk eingeschaltet und SCSI-verbunden?
- `ls /dev/st* /dev/nst*` prüfen.
- `HardwareController.discover_devices()` nutzt pyudev oder `/sys/class/scsi_tape`.

## EOT wird nicht erkannt
Manche Laufwerke melden EOT nicht via `mt status`. Die App fängt zusätzlich Schreibfehler ab und prüft Kapazitätsschwellen.

## Restore schlägt mit Checksum-Mismatch fehl
- Passphrase korrekt?
- Alle Volumes in richtiger Reihenfolge?
- Medium beschädigt? (Bit-Rot) – Hashes in den Volume-Records vergleichen.

## AppImage startet nicht
- Ausführbar machen: `chmod +x *.AppImage`
- FUSE installiert? (für AppImage)
- Auf Wayland/X11 testen.

## Tests laufen nicht
```bash
QT_QPA_PLATFORM=offscreen python tests/test_roundtrip.py
```
