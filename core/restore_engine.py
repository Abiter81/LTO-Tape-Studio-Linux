"""Restore engine: reads LTO Tape Studio archives and reconstructs files."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from .archive_format import iter_records
from .checksum import HashAlgorithm, compute_file
from .compression_engine import CompressionEngine, CompressionMode
from .hardware_controller import HardwareController
from .logger import TapeLogger
from .multivolume_manager import MultiVolumeManager


@dataclass
class RestoreJob:
    destination: Path
    checksum: HashAlgorithm = HashAlgorithm.SHA256
    passphrase: str = ""


class RestoreEngine(QObject):
    progress = Signal(float)
    status = Signal(str)
    current_file = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, controller: Optional[HardwareController] = None, logger: Optional[TapeLogger] = None) -> None:
        super().__init__()
        self.controller = controller
        self.logger = logger or TapeLogger.instance()
        self.compression_engine = CompressionEngine(self.logger)
        self.multivolume = MultiVolumeManager(controller, self.logger) if controller else None
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    # ------------------------------------------------------------------ #
    def restore_from_file(self, volume_paths: List[Path], job: RestoreJob) -> None:
        """Restore from a list of volume image files (for testing/offline)."""
        threading.Thread(target=self._restore_files, args=(volume_paths, job), daemon=True).start()

    def restore_from_tape(self, job: RestoreJob) -> None:
        threading.Thread(target=self._restore_tape, args=(job,), daemon=True).start()

    def _open_volume_stream(self, fh: BinaryIO) -> BinaryIO:
        magic = fh.readline().decode("utf-8", errors="replace").strip()
        parts = magic.split()
        mode_str = parts[1] if len(parts) > 1 else "none"
        try:
            mode = CompressionMode(mode_str)
        except ValueError:
            mode = CompressionMode.NONE
        return self.compression_engine.wrap_reader(fh, mode)

    def _restore_files(self, volume_paths: List[Path], job: RestoreJob) -> None:
        self._restore_streams([open(p, "rb") for p in volume_paths], job, close_streams=True)

    def _restore_tape(self, job: RestoreJob) -> None:
        assert self.controller is not None
        streams = []
        try:
            raw = open(self.controller.device, "rb", buffering=0)
            streams.append(raw)
            self._restore_streams(streams, job, close_streams=True, tape=True)
        except Exception as exc:
            self.logger.error(f"restore failed: {exc}")
            self.finished.emit(False, str(exc))

    def _restore_streams(self, raw_streams: List[BinaryIO], job: RestoreJob, close_streams: bool = True, tape: bool = False) -> None:
        try:
            job.destination.mkdir(parents=True, exist_ok=True)
            # Reassemble parts: path -> list of (part_index, data, meta)
            parts_map: Dict[str, List[tuple]] = {}
            file_meta: Dict[str, dict] = {}
            total_files = 0
            processed_bytes = 0

            stream_iter = iter(raw_streams)
            current_raw = next(stream_iter, None)
            while current_raw is not None:
                stream = self._open_volume_stream(current_raw)
                for rtype, meta, data in iter_records(stream):
                    if self._cancel.is_set():
                        raise RuntimeError("cancelled")
                    if rtype == "VOLUME":
                        self.logger.info(f"Reading volume {meta.get('volume')}")
                        continue
                    if rtype == "VOLUME_END":
                        continue
                    if rtype == "END":
                        continue
                    if rtype in ("FILE", "FILEPART"):
                        path = meta["path"]
                        file_meta[path] = meta
                        parts_map.setdefault(path, []).append((meta.get("part", 0), meta.get("offset", 0), data, meta))
                # next volume
                if tape and self.multivolume is not None:
                    # request next tape
                    self.multivolume.request_next_volume(f"Bitte naechstes Band fuer Restore einlegen.")
                    try:
                        current_raw = open(self.controller.device, "rb", buffering=0)
                    except Exception:
                        current_raw = None
                else:
                    current_raw = next(stream_iter, None)
                try:
                    stream.close()
                except Exception:
                    pass
                if current_raw is None:
                    break

            # Write files
            all_paths = sorted(parts_map.keys())
            total = len(all_paths) or 1
            for idx, path in enumerate(all_paths):
                if self._cancel.is_set():
                    break
                self.current_file.emit(path)
                parts = sorted(parts_map[path], key=lambda x: x[0])
                out_path = job.destination / path
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "wb") as out:
                    for _part_idx, _offset, data, meta in parts:
                        if meta.get("encrypted"):
                            from .encryption import decrypt_bytes
                            try:
                                data = decrypt_bytes(data, job.passphrase)
                            except Exception as exc:
                                self.logger.error(f"decryption failed for {path}: {exc}")
                                raise
                        out.write(data)
                # restore mode/mtime
                try:
                    m = file_meta[path]
                    os.chmod(out_path, m.get("mode", 0o644))
                    os.utime(out_path, (m.get("mtime", 0), m.get("mtime", 0)))
                except Exception:
                    pass
                # verify
                expected = file_meta[path].get("sha256", "")
                if expected:
                    actual = compute_file(out_path, job.checksum)
                    if actual.lower() != expected.lower():
                        self.logger.error(f"checksum mismatch: {path}")
                    else:
                        self.logger.info(f"verified: {path}")
                total_files += 1
                self.progress.emit((idx + 1) / total)

            msg = f"Restore completed: {total_files} files"
            self.logger.info(msg)
            self.status.emit("Completed")
            self.finished.emit(True, msg)
        except Exception as exc:
            self.logger.error(f"restore failed: {exc}")
            self.status.emit(f"Failed: {exc}")
            self.finished.emit(False, str(exc))
        finally:
            if close_streams:
                for s in raw_streams:
                    try:
                        s.close()
                    except Exception:
                        pass