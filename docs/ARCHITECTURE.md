# Architektur

## Modulstruktur

```
lto_tape_studio/
├── main.py
├── core/
│   ├── hardware_controller.py   # Low-Level SCSI/mt, Telemetry, EOT
│   ├── multivolume_manager.py   # Multivolume-Koordination
│   ├── compression_engine.py    # none/software/hardware
│   ├── backup_engine.py         # Multi-Source-Pipeline
│   ├── restore_engine.py        # Wiederherstellung
│   ├── archive_format.py        # Containerformat
│   ├── checksum.py              # MD5/SHA-256/SHA-512
│   ├── encryption.py            # Fernet (optional)
│   ├── config.py                # JSON-Konfiguration
│   ├── i18n.py                  # Übersetzungen
│   ├── scheduler.py             # Job-Scheduling
│   └── logger.py                # Thread-sicheres Audit-Logging
├── ui/
│   ├── main_window.py
│   └── widgets/
└── resources/
```

## Containerformat (Multivolume)

Jedes Volume beginnt mit einem `VOLUME`-Record und endet mit `VOLUME_END`. Dateien werden in `FILEPART`-Records gesplittet, sodass kein Record eine Bandgrenze überschreitet. Jeder Record:

```
<TYPE>\t<JSON_META>\t<DATA_LEN>\n<DATA_BYTES>
```

Ein Preamble `LTOVS1 <compression>` steht unkomprimiert vor dem komprimierten Stream.

## Datenfluss (Backup)

1. Quellen einsammeln (`_collect`).
2. Hardware-Kompression umschalten.
3. Volume öffnen, Preamble + VOLUME-Record schreiben.
4. Für jede Datei: Hash berechnen, in Parts splitten, ggf. verschlüsseln, streamen.
5. Bei EOT/Kapazität: Volume schließen, nächstes Band anfordern, Volume neu öffnen.
6. Abschluss: END-Record, Rewind.

## Datenfluss (Restore)

1. Volume-Preamble lesen → Kompressionsmodus.
2. Records parsen, Parts nach Pfad gruppieren.
3. Dateien reassemblieren, entschlüsseln, Hashes verifizieren.

## Threading

Backup/Restore laufen in Worker-Threads; GUI-Updates über Qt-Signale. Multivolume-Wechsel blockiert den Worker bis zur GUI-Bestätigung (Event).