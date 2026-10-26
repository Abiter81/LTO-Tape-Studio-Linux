"""Multi-source backup pipeline with metadata cataloguing and multivolume support."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, List, Optional

from PySide6.QtCore import QObject, Signal

from .archive_format import VolumeHeader, VolumeTrailer, make_volume_header, write_record
from .checksum import HashAlgorithm, compute_file
from .compression_engine import CompressionEngine, CompressionMode
from .hardware_controller import HardwareController
from .logger import TapeLogger
from .multivolume_manager import MultiVolumeManager


@dataclass
class BackupJob:
    job_id: str
    sources: List[Path]
    label: str = "backup"
    compression: CompressionMode = CompressionMode.NONE
    checksum: HashAlgorithm = HashAlgorithm.SHA256
    block_size: int = 262144
    part_size: int = 64 * 1024 * 1024
    verify: bool = False
    encrypt: bool = False
    passphrase: str = ""


@dataclass
class FileEntry:
    path: Path
    rel: str
    size: int
    mtime: float
    mode: int
    digest: str = ""


class _Counter(BinaryIO):
    """Wraps a raw file-like object and counts bytes written."""

    def __init__(self, raw: BinaryIO) -> None:
        self._raw = raw
        self.count = 0

    def write(self, data: bytes) -> int:  # type: ignore[override]
        n = self._raw.write(data)
        self.count += n
        return n

    def read(self, *a, **k):  # pragma: no cover
        return self._raw.read(*a, **k)

    def flush(self) -> None:  # type: ignore[override]
        self._raw.flush()

    def close(self) -> None:  # type: ignore[override]
        self._raw.close()

    def __getattr__(self, name):
        return getattr(self._raw, name)


class BackupEngine(QObject):
    """Runs a backup job on a worker thread."""

    progress = Signal(float)          # 0..1
    speed = Signal(float)             # MB/s
    status = Signal(str)
    current_file = Signal(str)
    finished = Signal(bool, str)     # success, message

    def __init__(
        self,
        controller: HardwareController,
        logger: Optional[TapeLogger] = None,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.logger = logger or TapeLogger.instance()
        self.compression_engine = CompressionEngine(self.logger)
        self.multivolume = MultiVolumeManager(controller, self.logger)
        self._thread: Optional[threading.Thread] = None
        self._cancel = threading.Event()
        self._pause = threading.Event()
        self._pause.set()

    def start(self, job: BackupJob) -> None:
        if self._thread and self._thread.is_alive():
            self.logger.warning("Backup already running")
            return
        self._cancel.clear()
        self._pause.set()
        self._thread = threading.Thread(target=self._run, args=(job,), daemon=True, name="backup-worker")
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()
        self._pause.set()

    def pause(self) -> None:
        self._pause.clear()

    def resume(self) -> None:
        self._pause.set()

    # ------------------------------------------------------------------ #
    def _collect(self, job: BackupJob) -> List[FileEntry]:
        entries: List[FileEntry] = []
        for src in job.sources:
            src = Path(src)
            if src.is_file():
                entries.append(self._entry(src, src))
                continue
            if src.is_dir():
                for root, _, files in os.walk(src):
                    for name in files:
                        p = Path(root) / name
                        try:
                            entries.append(self._entry(p, src))
                        except OSError as exc:
                            self.logger.warning(f"skip {p}: {exc}")
            else:
                self.logger.warning(f"source not found: {src}")
        return entries

    def _entry(self, p: Path, base: Path) -> FileEntry:
        st = p.stat()
        try:
            if base.is_dir() and (base == p or base in p.parents):
                rel = str(p.relative_to(base))
                if rel == ".":
                    rel = p.name
            else:
                rel = p.name
        except (ValueError, OSError):
            rel = str(p)
        return FileEntry(path=p, rel=rel, size=st.st_size, mtime=st.st_mtime, mode=st.st_mode)

    # ------------------------------------------------------------------ #
    def _capacity(self, job: BackupJob) -> int:
        if job.compression == CompressionMode.HARDWARE:
            cap = self.controller.compressed_capacity() or self.controller.native_capacity()
        elif job.compression in (CompressionMode.SOFTWARE_ZSTD, CompressionMode.SOFTWARE_GZIP):
            cap = self.controller.compressed_capacity() or self.controller.native_capacity()
        else:
            cap = self.controller.native_capacity()
        if not cap:
            # Fallback generous default
            cap = 18 * 10**9
        return int(cap * 0.98)  # safety margin

    def _run(self, job: BackupJob) -> None:
        try:
            self.status.emit("Collecting sources...")
            entries = self._collect(job)
            total_bytes = sum(e.size for e in entries) or 1
            self.logger.info(f"Job {job.job_id}: {len(entries)} files, {total_bytes} bytes")

            if job.compression == CompressionMode.HARDWARE:
                self.controller.set_hardware_compression(True)
            else:
                self.controller.set_hardware_compression(False)

            if job.block_size:
                self.controller.set_block_size(job.block_size)

            self.multivolume.begin(job.label)

            # Open first volume
            cap = self._capacity(job)
            raw = open(self.controller.device, "wb", buffering=0)
            counter = _Counter(raw)
            counter.write(f"LTOVS1 {job.compression.value}\n".encode())
            stream = self.compression_engine.wrap_writer(counter, job.compression)
            vol_header = make_volume_header(
                volume=self.multivolume.current_volume,
                job_id=job.job_id,
                label=job.label,
                compression=job.compression.value,
                checksum_algo=job.checksum.value,
                previous=0,
            )
            write_record(stream, "VOLUME", vol_header.to_meta())
            stream.flush()
            record_count = 1

            written_total = 0
            start_time = time.time()
            last_bytes = 0
            last_time = start_time

            def remaining() -> int:
                return cap - counter.count

            def switch_volume() -> None:
                nonlocal raw, counter, stream, cap, record_count
                trailer = VolumeTrailer(
                    volume=self.multivolume.current_volume,
                    bytes_written=counter.count,
                    records=record_count,
                )
                write_record(stream, "VOLUME_END", {"volume": trailer.volume, "bytes_written": trailer.bytes_written, "records": trailer.records})
                stream.flush()
                try:
                    stream.close()
                except Exception:
                    pass
                try:
                    raw.close()
                except Exception:
                    pass
                self.multivolume.mark_volume_complete(counter.count)
                self.multivolume.request_next_volume(f"Band voll. Bitte Band #{self.multivolume.current_volume + 1} einlegen.")
                # reopen
                raw = open(self.controller.device, "wb", buffering=0)
                counter = _Counter(raw)
                counter.write(f"LTOVS1 {job.compression.value}\n".encode())
                stream = self.compression_engine.wrap_writer(counter, job.compression)
                if job.block_size:
                    self.controller.set_block_size(job.block_size)
                prev = self.multivolume.current_volume - 1
                vol_header = make_volume_header(
                    volume=self.multivolume.current_volume,
                    job_id=job.job_id,
                    label=job.label,
                    compression=job.compression.value,
                    checksum_algo=job.checksum.value,
                    previous=prev,
                )
                write_record(stream, "VOLUME", vol_header.to_meta())
                stream.flush()
                record_count = 1

            for entry_idx, entry in enumerate(entries):
                if self._cancel.is_set():
                    self.logger.warning("Job cancelled by user")
                    break
                self._pause.wait()
                self.current_file.emit(str(entry.path))

                try:
                    entry.digest = compute_file(entry.path, job.checksum)
                except Exception as exc:
                    self.logger.warning(f"checksum failed for {entry.path}: {exc}")
                    entry.digest = ""

                if remaining() < 4096:
                    switch_volume()

                # Treat every file as potentially split across volumes.
                total_parts = max(1, (entry.size + job.part_size - 1) // job.part_size) if entry.size > 0 else 1
                bytes_done = 0
                part_index = 0
                with open(entry.path, "rb") as fh:
                    while bytes_done < (entry.size if entry.size > 0 else 1) and not self._cancel.is_set():
                        self._pause.wait()
                        if entry.size == 0:
                            # empty file: write one empty part
                            if remaining() < 4096:
                                switch_volume()
                            if job.encrypt and job.passphrase:
                                from .encryption import encrypt_bytes
                                data_part = encrypt_bytes(b"", job.passphrase)
                                encrypted = True
                            else:
                                data_part = b""
                                encrypted = False
                            meta = {
                                "path": entry.rel,
                                "size": len(data_part),
                                "mtime": entry.mtime,
                                "mode": entry.mode,
                                "sha256": entry.digest,
                                "part": 0,
                                "parts": 1,
                                "offset": 0,
                                "total_size": 0,
                                "encrypted": encrypted,
                                "raw_size": 0,
                            }
                            hdr = f"FILEPART\t{json.dumps(meta, separators=(',', ':'))}\t{len(data_part)}\n".encode()
                            stream.write(hdr)
                            if data_part:
                                stream.write(data_part)
                            record_count += 1
                            bytes_done = 1  # mark done
                            break

                        if remaining() < 4096:
                            switch_volume()

                        max_part = remaining() - 8192
                        if max_part <= 0:
                            switch_volume()
                            continue

                        target = min(job.part_size, entry.size - bytes_done, max_part)
                        if target <= 0:
                            switch_volume()
                            continue

                        # Read the raw part into memory (needed for optional encryption)
                        raw_part = fh.read(target)
                        if not raw_part and target > 0:
                            break
                        if job.encrypt and job.passphrase and raw_part:
                            from .encryption import encrypt_bytes
                            data_part = encrypt_bytes(raw_part, job.passphrase)
                            encrypted = True
                        else:
                            data_part = raw_part
                            encrypted = False

                        meta = {
                            "path": entry.rel,
                            "size": len(data_part),
                            "mtime": entry.mtime,
                            "mode": entry.mode,
                            "sha256": entry.digest if (bytes_done + target >= entry.size) else "",
                            "part": part_index,
                            "parts": total_parts,
                            "offset": bytes_done,
                            "total_size": entry.size,
                            "encrypted": encrypted,
                            "raw_size": len(raw_part),
                        }
                        hdr = f"FILEPART\t{json.dumps(meta, separators=(',', ':'))}\t{len(data_part)}\n".encode()
                        try:
                            stream.write(hdr)
                        except OSError as exc:
                            self.logger.warning(f"write header failed: {exc}; switching volume")
                            switch_volume()
                            continue

                        # stream (possibly encrypted) bytes
                        to_write = data_part
                        pos = 0
                        chunk_sz = 1024 * 1024
                        while pos < len(to_write) and not self._cancel.is_set():
                            self._pause.wait()
                            chunk = to_write[pos:pos + chunk_sz]
                            try:
                                stream.write(chunk)
                            except OSError as exc:
                                self.logger.warning(f"write data failed: {exc}; cancelling job")
                                self._cancel.set()
                                break
                            pos += len(chunk)
                            written_total += len(chunk)
                            self.controller.account_write(len(chunk))

                            frac = min(1.0, written_total / total_bytes)
                            self.progress.emit(frac)
                            now_t = time.time()
                            dt = now_t - last_time
                            if dt >= 0.5:
                                delta = written_total - last_bytes
                                speed = (delta / dt) / (1024 * 1024)
                                self.speed.emit(speed)
                                last_bytes = written_total
                                last_time = now_t

                        if self._cancel.is_set():
                            break
                        stream.flush()
                        record_count += 1
                        bytes_done += target
                        part_index += 1

                self.logger.info(f"Archived {entry.rel} ({entry.size} bytes)")

            if not self._cancel.is_set():
                # END record
                write_record(stream, "END", {"job_id": job.job_id, "files": len(entries), "bytes": written_total})
                stream.flush()

            try:
                stream.close()
            except Exception:
                pass
            try:
                raw.close()
            except Exception:
                pass

            self.multivolume.mark_volume_complete(written_total)

            # Optional read-after-write verification
            verify_ok = True
            if job.verify and not self._cancel.is_set():
                self.status.emit("Verifying written data...")
                self.logger.info("Starting read-after-write verification")
                try:
                    self.controller.rewind()
                    raw = open(self.controller.device, "rb", buffering=0)
                    try:
                        raw.seek(0)
                    except Exception:
                        pass
                    # skip unkomprimierte Preamble
                    try:
                        raw.readline()
                    except Exception:
                        pass
                    stream = self.compression_engine.wrap_reader(raw, job.compression)
                    from .archive_format import iter_records
                    parts_map = {}
                    file_meta = {}
                    for rtype, meta, data in iter_records(stream):
                        if rtype in ("FILE", "FILEPART"):
                            p = meta["path"]
                            file_meta[p] = meta
                            parts_map.setdefault(p, []).append((meta.get("part", 0), data, meta))
                    # verify hashes
                    for path, parts in parts_map.items():
                        if self._cancel.is_set():
                            break
                        ordered = sorted(parts, key=lambda x: x[0])
                        import hashlib as _hl
                        h = _hl.new(job.checksum.value)
                        expected = ""
                        for _pi, data, meta in ordered:
                            if meta.get("encrypted"):
                                from .encryption import decrypt_bytes
                                try:
                                    data = decrypt_bytes(data, job.passphrase)
                                except Exception as exc:
                                    self.logger.error(f"verify decrypt failed {path}: {exc}")
                                    verify_ok = False
                                    break
                            h.update(data)
                            if meta.get("sha256"):
                                expected = meta["sha256"]
                        if expected:
                            if h.hexdigest().lower() != expected.lower():
                                self.logger.error(f"verify mismatch: {path}")
                                verify_ok = False
                            else:
                                self.logger.info(f"verified: {path}")
                    try:
                        raw.close()
                    except Exception:
                        pass
                    stream.close()
                except Exception as exc:
                    self.logger.error(f"verification failed: {exc}")
                    verify_ok = False

            try:
                self.controller.rewind()
            except Exception:
                pass
            elapsed = time.time() - start_time
            if self._cancel.is_set():
                msg = f"Backup cancelled: {written_total} bytes written"
                self.logger.warning(msg)
                self.status.emit("Cancelled")
                self.finished.emit(False, msg)
            else:
                vmsg = " (verified)" if (job.verify and verify_ok) else (" (VERIFY FAILED)" if (job.verify and not verify_ok) else "")
                msg = f"Backup completed: {len(entries)} files, {written_total} bytes in {elapsed:.1f}s{vmsg}"
                self.logger.info(msg)
                self.status.emit("Completed" if verify_ok else "Completed (verify failed)")
                self.progress.emit(1.0)
                self.finished.emit(verify_ok if job.verify else True, msg)
        except Exception as exc:
            self.logger.error(f"Backup failed: {exc}")
            self.status.emit(f"Failed: {exc}")
            self.finished.emit(False, str(exc))
