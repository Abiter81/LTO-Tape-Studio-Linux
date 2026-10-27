# LTO Tape Studio – Documentation

Welcome to the documentation of **LTO Tape Studio**, the enterprise desktop application for controlling and archiving to LTO tape drives under Linux.

**Programmed by Jörg Althaus**

## Table of contents

| Document | Description |
|---|---|
| [Installation](INSTALLATION.md) | System prerequisites, Python dependencies, udev, startup |
| [User Guide](USER_GUIDE.md) | Operation: backup, restore, tape operations, multivolume |
| [Architecture](ARCHITECTURE.md) | Module structure, data flow, container format |
| [Troubleshooting](TROUBLESHOOTING.md) | Common problems and solutions |

German versions: [`docs/`](../README.md).

## Quick start

```bash
git clone https://github.com/Abiter81/LTO-Tape-Studio-Linux.git
cd LTO-Tape-Studio-Linux
pip install -r requirements.txt
python main.py
```

## License

See repository root.