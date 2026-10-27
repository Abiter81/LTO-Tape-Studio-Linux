# User Guide – LTO Tape Studio

## 1. Overview

**LTO Tape Studio** is a professional enterprise desktop application for the complete control, management and archiving of LTO tape drives (LTO-1 to LTO-10) under Linux. It offers a modern dark-theme interface, real-time telemetry, multivolume support, cryptographic integrity verification and optional encryption.

**Programmed by Jörg Althaus**

### Key features at a glance

| Feature | Description |
|---|---|
| **LTO-1 … LTO-10** | Dynamic support of all generations with automatic capacity, block size and transfer rate adjustment |
| **Multivolume** | Seamless continuation across multiple tapes at EOT, with interactive tape-change dialog |
| **Multi-source backup** | Any number of folders, files and mount points simultaneously as source queue |
| **3 compression modes** | Uncompressed, software (zstandard/gzip), hardware (drive registers) |
| **Integrity** | MD5, SHA-256, SHA-512 for bit-rot detection |
| **Encryption** | Optional Fernet/AES encryption with passphrase |
| **Read-after-write** | Optional physical verification of written data |
| **Telemetry** | Live transfer rate (MB/s), capacity usage, temperature, load count |
| **Audit log** | Thread-safe real-time logging (GUI + rotating file) |
| **Scheduler** | In-process job scheduling with repetition |
| **i18n** | English / German switchable |

---

## 2. Interface in detail

### 2.1 Live dashboard (top area, always visible)

The dashboard shows the current state of the tape drive in real time and updates every second.

| Element | Meaning |
|---|---|
| **Device** | Active device (e.g. `/dev/nst0`) |
| **Generation** | Detected or manually set LTO generation (LTO-1 … LTO-10) |
| **Status** | `ready`, `not_ready`, `write_protected`, `end_of_tape`, `beginning_of_tape`, `offline`, `unknown` |
| **Speed** | Current transfer rate in MB/s (during running jobs) |
| **Capacity** | Written / total capacity in GB |
| **Progress bar** | Capacity usage in percent |
| **Telemetry** | Hardware telemetry (temperature in °C, load count) – best-effort via `sg_logs` |

### 2.2 Tabs

#### Tab "Backup"
Source selection and backup options.

**Source selector:**
- **Add Folder** – Add a single folder as source
- **Add File** – Add individual files
- **Add Disk/Mount** – Add a complete mount point / disk as source
- **Remove** – Remove selected entries
- **Clear** – Clear all entries
- Multi-selection possible (extended selection)

**Backup options:**
| Option | Values | Description |
|---|---|---|
| Compression | `none`, `software_zstd`, `software_gzip`, `hardware` | Compression mode |
| Checksum | `md5`, `sha256`, `sha512` | Hash algorithm for integrity check |
| Label | Text | Name of the archive (written into the volume header) |
| Block size | Number (default 262144) | Block size in bytes |
| Encrypt | Checkbox + passphrase | Optional Fernet encryption |
| Verify (read-after-write) | Checkbox | Physical verification after writing |

**Actions:**
- **Start Backup** – Starts the backup job in a worker thread
- **Cancel** – Cancels the running job
- **Progress bar** – 0–100 % of the total volume
- **Current file** – Shows the file currently being processed

**Settings are saved automatically** (label, block size, encrypt state, compression, hash, language). The passphrase is **not** persisted for security reasons.

#### Tab "Tape Operations"
Direct tape control and generation selection.

| Control | Function |
|---|---|
| Generation (ComboBox) | Set LTO-1 to LTO-10 manually |
| Rewind | Rewind tape to beginning (BOT) |
| Eject | Eject tape (offline) |
| Retension | Retension tape (equalise tension) |
| Erase | Completely erase tape |
| Status | Query drive status |

#### Tab "Job Queue"
Display of enqueued backup jobs with ability to cancel selected jobs.

#### Tab "Restore"
Restore from tape or volume files.

| Element | Function |
|---|---|
| Destination | Target directory for restored files |
| Passphrase | Passphrase for encrypted archives |
| Browse | Directory selection dialog |
| Restore from Tape | Reads from device (multivolume: requests further tapes) |
| Restore from Volume Files | Offline restore from image files |

Restore verifies SHA-256 hashes automatically.

### 2.3 Menu bar

| Menu | Entries |
|---|---|
| **Help** | About (version, author, description) |
| **Language** | English / German (restart recommended for full effect) |

### 2.4 Audit log (bottom area)
Real-time protocol of all actions with timestamp, level, thread and message. Written simultaneously to a rotating log file (`~/.lto_tape_studio/audit.log`, max. 5 MB, 5 backups).

---

## 3. Backup process (detailed)

1. **Collect sources** – All specified paths are traversed recursively; files are captured with metadata (path, size, mtime, mode).
2. **Compute hash** – The chosen hash (MD5/SHA-256/SHA-512) is computed for each file.
3. **Switch compression** – For hardware compression the drive register is set.
4. **Set block size** – If specified.
5. **Open volume** – Preamble `LTOVS1 <compression>` + VOLUME record.
6. **Stream files** – Each file is split into configurable parts (default 64 MB); encrypted if needed; parts are written as `FILEPART` records.
7. **Capacity monitoring** – When tape capacity is reached (98 % safety margin) the volume is closed and the next tape is requested.
8. **EOT detection** – Write errors and status queries detect the end of tape; multivolume switch is triggered.
9. **Finish** – END record, rewind tape.
10. **Optional: verification** – Read-after-write reads the archive back and compares hashes.

### Multivolume tape change

As soon as a tape is full:
1. The job pauses automatically.
2. A modal dialog appears: "Please insert tape #X".
3. After insertion and confirmation (OK) the new medium is initialised (rewind, volume header).
4. The stream continues seamlessly.
5. On cancel the job is terminated.

Large files are split automatically so that no record crosses a tape boundary.

---

## 4. Restore process (detailed)

1. **Open volume** – Read preamble → detect compression mode.
2. **Parse records** – `VOLUME`, `FILEPART`, `VOLUME_END`, `END`.
3. **Group parts** – Sorted by file path.
4. **Reassemble** – Parts are joined in correct order; decrypted if encrypted.
5. **Write files** – Create target path, restore mode and mtime.
6. **Hash verification** – SHA-256 (or chosen algorithm) is compared; mismatch is logged.
7. **Multivolume** – When restoring from tape, further tapes are requested.

---

## 5. Compression modes in detail

| Mode | Description | Use case |
|---|---|---|
| **none (uncompressed)** | Direct data stream, no influence | Maximum integrity, already compressed data |
| **software_zstd** | CPU-based zstandard compression (gzip fallback) | High compression, moderate CPU load |
| **software_gzip** | gzip compression | Universal compatibility |
| **hardware** | Drive's own on-the-fly compression (`mt compression 1`) | Maximum throughput, no host CPU load |

With software compression the stream is transparently wrapped; the container format stays identical.

---

## 6. Integrity & security

### Checksums
- **MD5** – Fast, for non-critical checks
- **SHA-256** – Standard, recommended
- **SHA-512** – Maximum security

Hashes are computed per file and stored in the last `FILEPART` record. On restore they are compared automatically.

### Encryption
- **Algorithm:** Fernet (AES-128-CBC + HMAC-SHA256)
- **Key derivation:** PBKDF2-HMAC-SHA256, 200,000 iterations, salt `lto-tape-studio`
- **Application:** Per part (file chunk), not the whole archive
- **Passphrase:** Not stored; must be entered on restore

### Read-after-write
Optional physical verification: after writing, the tape is rewound, the archive is read back and every file hash is recomputed and compared. Detects write errors and bit rot early.

---

## 7. Configuration

Configuration file: `~/.lto_tape_studio/config.json`

Stored values:
- `label` – Last backup label
- `block_size` – Last block size
- `encrypt` – Encrypt checkbox state
- `compression` – Last compression mode
- `hash` – Last hash algorithm
- `language` – Selected language (en/de)

Log file: `~/.lto_tape_studio/audit.log` (rotating, 5 MB, 5 backups)

---

## 8. System integration

### udev rules
The file `resources/99-lto-tape.rules` creates persistent symlinks (`/dev/tape0`, `/dev/ntape0`) and sets group permissions (`GROUP="tape"`, `MODE="0660"`).

### Desktop integration
`resources/lto_tape_studio.desktop` with icon and categories `System;Archiving;`.

### AppImage
Portable AppImage with embedded Python dependencies, Qt libraries and binaries. Programmer credit "Jörg Althaus" in metadata.

---

## 9. Keyboard shortcuts & usage notes

- **Multivolume dialog:** OK = confirm next tape, Cancel = abort job
- **Progress:** Real-time updates via Qt signals (thread-safe)
- **Pause/Resume:** Backup engine supports pausing and resuming (API)

---

## 10. Troubleshooting (quick reference)

| Problem | Solution |
|---|---|
| `mt: command not found` | Install `mt-st` |
| Permission denied | `sudo usermod -aG tape $USER`, log in again |
| No device found | Check udev rules, power on drive |
| EOT not detected | App catches write errors + capacity thresholds |
| Checksum mismatch | Check passphrase, all volumes in order |
| AppImage does not start | `chmod +x`, check FUSE |
| Tests | `QT_QPA_PLATFORM=offscreen python tests/test_roundtrip.py` |

---

## 11. License & author

**Programmed by Jörg Althaus**

Enterprise LTO tape management and archiving for Linux. See repository root for license details.