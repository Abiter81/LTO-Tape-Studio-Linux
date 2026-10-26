# LTO Tape Studio

**Programmed by Jörg Althaus**

Enterprise Linux desktop application for controlling and archiving to LTO tape drives (LTO-1 .. LTO-10).

## Dokumentation

Ausführliche Anleitung unter [`docs/`](docs/README.md).

## System prerequisites

- `mt-st` (`mt`)
- `sg3-utils` (`sg_inq`, `sg_modes`)
- `udev`
- Python 3.10+

## Python dependencies

See `requirements.txt`.

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

## Build AppImage

```bash
./build_appimage_6.sh
```

## udev

Install `resources/99-lto-tape.rules` to `/etc/udev/rules.d/` and reload:

```bash
sudo cp resources/99-lto-tape.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -aG tape $USER
```
