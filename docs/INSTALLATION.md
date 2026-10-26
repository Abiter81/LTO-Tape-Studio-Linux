# Installation

## Systemvoraussetzungen

- Linux (getestet auf CachyOS/Arch; andere Distributionen mit Anpassungen)
- Python 3.10 oder neuer
- `mt-st` (stellt `mt` bereit)
- `sg3-utils` (stellt `sg_inq`, `sg_logs`, `sg_modes` bereit)
- `udev`
- Optional: `pyudev` (bessere Geräteerkennung)

### Pakete installieren

**Arch / CachyOS:**
```bash
sudo pacman -S mt-st sg3_utils python-pyqt6 python-psutil python-zstandard python-cryptography
```

**Debian / Ubuntu:**
```bash
sudo apt install mt-st sg3-utils python3-pyqt6 python3-psutil python3-zstandard python3-cryptography
```

**Fedora:**
```bash
sudo dnf install mt-st sg3-utils python3-PyQt6 python3-psutil python3-zstandard python3-cryptography
```

## Python-Abhängigkeiten

```bash
pip install -r requirements.txt
```

Inhalt von `requirements.txt`:
```
PySide6>=6.5
pyudev>=0.24
psutil>=5.9
zstandard>=0.21
cryptography>=42
```

## udev-Regeln installieren

Die Datei `resources/99-lto-tape.rules` stellt persistente Symlinks und Gruppenrechte bereit.

```bash
sudo cp resources/99-lto-tape.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -aG tape $USER
```

Danach neu anmelden, damit die Gruppenmitgliedschaft wirksam wird.

## Anwendung starten

```bash
python main.py
```

## AppImage bauen (optional)

```bash
chmod +x build_appimage_6.sh
./build_appimage_6.sh
```

Das resultierende AppImage liegt im Projektverzeichnis und ist portabel.