# LTO Tape Studio – Dokumentation

Willkommen zur Dokumentation von **LTO Tape Studio**, der Enterprise-Desktop-Anwendung zur Steuerung und Archivierung von LTO-Bandlaufwerken unter Linux.

**Programmed by Jörg Althaus**

## Inhaltsverzeichnis

| Dokument | Beschreibung |
|---|---|
| [Installation](INSTALLATION.md) | Systemvoraussetzungen, Python-Abhängigkeiten, udev, Start |
| [Benutzerhandbuch](USER_GUIDE.md) | Bedienung: Backup, Restore, Tape-Operationen, Multivolume |
| [Architektur](ARCHITECTURE.md) | Modulstruktur, Datenfluss, Containerformat |
| [Fehlerbehebung](TROUBLESHOOTING.md) | Häufige Probleme und Lösungen |

## Schnellstart

```bash
git clone https://github.com/Abiter81/lto_tape_studio.git
cd lto_tape_studio
pip install -r requirements.txt
python main.py
```

## Lizenz

Siehe Repository-Root.
