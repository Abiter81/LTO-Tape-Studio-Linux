# Troubleshooting

## "mt: command not found"
Install `mt-st` (see Installation) and make sure `mt` is in PATH.

## "Permission denied" on device access
Add the user to the `tape` group and log in again:
```bash
sudo usermod -aG tape $USER
```

## No device found
- udev rules installed and reloaded?
- Drive powered on and SCSI-connected?
- Check `ls /dev/st* /dev/nst*`.
- `HardwareController.discover_devices()` uses pyudev or `/sys/class/scsi_tape`.

## EOT not detected
Some drives do not report EOT via `mt status`. The app additionally catches write errors and checks capacity thresholds.

## Restore fails with checksum mismatch
- Passphrase correct?
- All volumes in the correct order?
- Medium damaged? (bit rot) – compare hashes in the volume records.

## AppImage does not start
- Make executable: `chmod +x *.AppImage`
- FUSE installed? (required for AppImage)
- Test on Wayland/X11.

## Tests do not run
```bash
QT_QPA_PLATFORM=offscreen python tests/test_roundtrip.py
```