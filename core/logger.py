"""Thread-safe audit logger for LTO Tape Studio.

Provides a singleton :class:`TapeLogger` that fans out log records to the
Python :mod:`logging` hierarchy (file handler) and to registered Qt signal
listeners so the GUI can display real-time audit output.
"""

from __future__ import annotations

import logging
import threading
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, Signal


@dataclass
class LogEntry:
    """A single audit log record."""

    timestamp: datetime
    level: str
    message: str
    thread: str

    def formatted(self) -> str:
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] [{self.level}] [{self.thread}] {self.message}"


class _SignalBridge(QObject):
    """Qt object used to emit log entries across threads."""

    entry_emitted = Signal(object)


class TapeLogger:
    """Singleton, thread-safe logger with GUI fan-out."""

    _instance: Optional["TapeLogger"] = None
    _lock = threading.Lock()

    def __init__(self, log_file: Optional[Path] = None) -> None:
        self._entries: List[LogEntry] = []
        self._listeners: List[Callable[[LogEntry], None]] = []
        self._entries_lock = threading.Lock()
        self._bridge = _SignalBridge()
        self._bridge.entry_emitted.connect(self._on_entry)
        self._python_logger = logging.getLogger("lto_tape_studio")
        self._python_logger.setLevel(logging.DEBUG)
        if not self._python_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s"))
            self._python_logger.addHandler(handler)
        if log_file is not None:
            self.attach_file(log_file)

    @classmethod
    def instance(cls, log_file: Optional[Path] = None) -> "TapeLogger":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(log_file)
            return cls._instance

    def attach_file(self, path: Path) -> None:
        """Attach a file handler to the underlying Python logger."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(message)s"))
        self._python_logger.addHandler(fh)

    def register_listener(self, callback: Callable[[LogEntry], None]) -> None:
        with self._entries_lock:
            self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[LogEntry], None]) -> None:
        with self._entries_lock:
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass

    def _on_entry(self, entry: LogEntry) -> None:
        with self._entries_lock:
            self._entries.append(entry)
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(entry)
            except Exception:  # pragma: no cover - defensive
                pass

    def _emit(self, level: str, message: str) -> None:
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            thread=threading.current_thread().name,
        )
        # Route through the bridge so GUI updates happen on the main thread.
        self._bridge.entry_emitted.emit(entry)
        getattr(self._python_logger, level.lower(), self._python_logger.info)(message)

    def debug(self, message: str) -> None:
        self._emit("DEBUG", message)

    def info(self, message: str) -> None:
        self._emit("INFO", message)

    def warning(self, message: str) -> None:
        self._emit("WARNING", message)

    def error(self, message: str) -> None:
        self._emit("ERROR", message)

    def critical(self, message: str) -> None:
        self._emit("CRITICAL", message)

    def entries(self) -> List[LogEntry]:
        with self._entries_lock:
            return list(self._entries)