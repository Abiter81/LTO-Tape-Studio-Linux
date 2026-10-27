# Installation

## System prerequisites

- Linux (tested on CachyOS/Arch; other distributions with adjustments)
- Python 3.10 or newer
- `mt-st` (provides `mt`)
- `sg3-utils` (provides `sg_inq`, `sg_logs`, `sg_modes`)
- `udev`
- Optional: `pyudev` (better device detection)

### Install packages

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

## Python dependencies

```bash
pip install -r requirements.txt
```

Contents of `requirements.txt`:
```
PySide6>=6.5
pyudev>=0.24
psutil>=5.9
zstandard>=0.21
cryptography>=42
```

## Install udev rules

The file `resources/99-lto-tape.rules` provides persistent symlinks and group permissions.

```bash
sudo cp resources/99-lto-tape.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -aG tape $USER
```

Log out and back in afterwards so the group membership takes effect.

## Run the application

```bash
python main.py
```

## Build AppImage (optional)

```bash
chmod +x build_appimage_6.sh
./build_appimage_6.sh
```

The resulting AppImage is located in the project directory and is portable.