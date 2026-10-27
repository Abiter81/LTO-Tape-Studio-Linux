# Architecture

## Module structure

```
lto_tape_studio/
├── main.py
├── core/
│   ├── hardware_controller.py   # Low-level SCSI/mt, telemetry, EOT
│   ├── multivolume_manager.py   # Multivolume coordination
│   ├── compression_engine.py    # none/software/hardware
│   ├── backup_engine.py         # Multi-source pipeline
│   ├── restore_engine.py        # Restore
│   ├── archive_format.py        # Container format
│   ├── checksum.py              # MD5/SHA-256/SHA-512
│   ├── encryption.py            # Fernet (optional)
│   ├── config.py                # JSON configuration
│   ├── i18n.py                  # Translations
│   ├── scheduler.py             # Job scheduling
│   └── logger.py                # Thread-safe audit logging
├── ui/
│   ├── main_window.py
│   └── widgets/
└── resources/
```

## Container format (multivolume)

Each volume starts with a `VOLUME` record and ends with `VOLUME_END`. Files are split into `FILEPART` records so that no record crosses a tape boundary. Each record:

```
<TYPE>\t<JSON_META>\t<DATA_LEN>\n<DATA_BYTES>
```

An uncompressed preamble `LTOVS1 <compression>` precedes the compressed stream.

## Data flow (backup)

1. Collect sources (`_collect`).
2. Switch hardware compression.
3. Open volume, write preamble + VOLUME record.
4. For each file: compute hash, split into parts, encrypt if needed, stream.
5. On EOT/capacity: close volume, request next tape, reopen volume.
6. Finish: END record, rewind.

## Data flow (restore)

1. Read volume preamble → compression mode.
2. Parse records, group parts by path.
3. Reassemble files, decrypt, verify hashes.

## Threading

Backup/restore run in worker threads; GUI updates via Qt signals. Multivolume switching blocks the worker until GUI confirmation (event).