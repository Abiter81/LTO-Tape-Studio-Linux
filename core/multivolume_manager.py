"""Multi-volume (multi-tape) archive manager.

Detects End-of-Tape conditions, pauses the active job and requests the next
physical medium through a Qt signal. The GUI connects to
:pyattr:`tape_change_required` to show a modal dialog.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, Signal

from .hardware_controller import HardwareController, TapeStatus
from .logger import TapeLogger


@dataclass
class VolumeInfo:
    volume_number: int
    label: str
    bytes_written: int = 0
    checksum: Optional[str] = None
    completed: bool = False


class MultiVolumeManager(QObject):
    """Coordinates writing across multiple tapes."""

    tape_change_required = Signal(int, str)  # next volume number, message
    volume_completed = Signal(int)
    all_completed = Signal()

    def __init__(
        self,
        controller: HardwareController,
        logger: Optional[TapeLogger] = None,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.logger = logger or TapeLogger.instance()
        self.volumes: List[VolumeInfo] = []
        self.current_volume: int = 0
        self._change_event = threading.Event()
        self._next_volume_ready: bool = False
        self._lock = threading.Lock()

    def begin(self, base_label: str) -> VolumeInfo:
        self.current_volume = 1
        vol = VolumeInfo(volume_number=1, label=f"{base_label}-vol001")
        self.volumes.append(vol)
        self.logger.info(f"Starting multi-volume archive: {vol.label}")
        return vol

    def current(self) -> Optional[VolumeInfo]:
        if 0 <= self.current_volume - 1 < len(self.volumes):
            return self.volumes[self.current_volume - 1]
        return None

    def is_eot(self) -> bool:
        return self.controller.is_eot()

    def request_next_volume(self, message: str = "") -> None:
        """Block until the operator confirms a new tape is loaded."""
        nxt = self.current_volume + 1
        msg = message or f"Bitte Band #{nxt} einlegen und bestaetigen."
        self.logger.warning(f"End of tape reached. Requesting volume {nxt}.")
        self._change_event.clear()
        self._next_volume_ready = False
        self.tape_change_required.emit(nxt, msg)
        # Wait for confirm_volume_change()
        self._change_event.wait()
        if not self._next_volume_ready:
            raise RuntimeError("Tape change cancelled by operator")

    def confirm_volume_change(self) -> None:
        """Called by GUI after operator inserted the next tape."""
        with self._lock:
            self.current_volume += 1
            vol = VolumeInfo(volume_number=self.current_volume, label=f"vol{self.current_volume:03d}")
            self.volumes.append(vol)
            self._next_volume_ready = True
            try:
                self.controller.rewind()
            except Exception as exc:  # pragma: no cover
                self.logger.warning(f"rewind after change failed: {exc}")
        self._change_event.set()
        self.logger.info(f"Switched to volume {self.current_volume}")

    def cancel_volume_change(self) -> None:
        self._next_volume_ready = False
        self._change_event.set()

    def mark_volume_complete(self, bytes_written: int, checksum: Optional[str] = None) -> None:
        vol = self.current()
        if vol is not None:
            vol.bytes_written = bytes_written
            vol.checksum = checksum
            vol.completed = True
            self.volume_completed.emit(vol.volume_number)