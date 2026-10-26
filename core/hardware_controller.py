"""Low-level LTO tape hardware controller.

Wraps ``mt-st`` (``mt``), ``sg3-utils`` (``sg_*``) and device discovery to
provide a high-level, Pythonic API for LTO-1 .. LTO-10 tape drives. All
subprocess calls are isolated here so the rest of the application stays
testable without real hardware.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .logger import TapeLogger


class TapeGeneration(Enum):
    LTO1 = "LTO-1"
    LTO2 = "LTO-2"
    LTO3 = "LTO-3"
    LTO4 = "LTO-4"
    LTO5 = "LTO-5"
    LTO6 = "LTO-6"
    LTO7 = "LTO-7"
    LTO8 = "LTO-8"
    LTO9 = "LTO-9"
    LTO10 = "LTO-10"


@dataclass(frozen=True)
class GenerationSpec:
    """Static capabilities of an LTO generation."""

    generation: TapeGeneration
    native_capacity_bytes: int
    compressed_capacity_bytes: int
    native_transfer_rate_mbps: float
    max_block_size: int
    default_block_size: int = 262144


# Capacities are uncompressed native / 2.5x (or gen-specific) compressed.
_GENERATION_SPECS: Dict[TapeGeneration, GenerationSpec] = {
    TapeGeneration.LTO1: GenerationSpec(TapeGeneration.LTO1, 100 * 10**9, 200 * 10**9, 20.0, 262144),
    TapeGeneration.LTO2: GenerationSpec(TapeGeneration.LTO2, 200 * 10**9, 400 * 10**9, 40.0, 262144),
    TapeGeneration.LTO3: GenerationSpec(TapeGeneration.LTO3, 400 * 10**9, 800 * 10**9, 80.0, 262144),
    TapeGeneration.LTO4: GenerationSpec(TapeGeneration.LTO4, 800 * 10**9, 1600 * 10**9, 120.0, 262144),
    TapeGeneration.LTO5: GenerationSpec(TapeGeneration.LTO5, 1500 * 10**9, 3000 * 10**9, 140.0, 1048576),
    TapeGeneration.LTO6: GenerationSpec(TapeGeneration.LTO6, 2500 * 10**9, 6250 * 10**9, 160.0, 1048576),
    TapeGeneration.LTO7: GenerationSpec(TapeGeneration.LTO7, 6000 * 10**9, 15000 * 10**9, 300.0, 1048576),
    TapeGeneration.LTO8: GenerationSpec(TapeGeneration.LTO8, 12000 * 10**9, 30000 * 10**9, 360.0, 1048576),
    TapeGeneration.LTO9: GenerationSpec(TapeGeneration.LTO9, 18000 * 10**9, 45000 * 10**9, 400.0, 1048576),
    TapeGeneration.LTO10: GenerationSpec(TapeGeneration.LTO10, 36000 * 10**9, 90000 * 10**9, 500.0, 1048576),
}


class TapeStatus(Enum):
    UNKNOWN = "unknown"
    READY = "ready"
    NOT_READY = "not_ready"
    WRITE_PROTECTED = "write_protected"
    EOT = "end_of_tape"
    BOT = "beginning_of_tape"
    OFFLINE = "offline"


@dataclass
class DeviceInfo:
    """Discovered tape device."""

    path: str  # e.g. /dev/nst0
    sg_path: Optional[str] = None  # e.g. /dev/sg1
    model: str = "Unknown"
    serial: str = "Unknown"
    generation: Optional[TapeGeneration] = None
    firmware: str = "Unknown"


@dataclass
class TapeTelemetry:
    """Live telemetry snapshot."""

    status: TapeStatus = TapeStatus.UNKNOWN
    bytes_written: int = 0
    bytes_read: int = 0
    block_size: int = 0
    generation: Optional[TapeGeneration] = None
    compression_ratio: float = 1.0
    temperature_c: Optional[float] = None
    load_count: Optional[int] = None
    raw: Dict[str, str] = field(default_factory=dict)


class HardwareController:
    """Manages a single tape drive."""

    DEFAULT_DEVICE = "/dev/nst0"

    def __init__(self, device: str = DEFAULT_DEVICE, logger: Optional[TapeLogger] = None) -> None:
        self.device = device
        self.sg_device: Optional[str] = None
        self.logger = logger or TapeLogger.instance()
        self._lock = threading.RLock()
        self._generation: Optional[TapeGeneration] = None
        self._compression_hw: bool = False
        self._block_size: int = 0
        self._bytes_written: int = 0
        self._bytes_read: int = 0

    # ------------------------------------------------------------------ #
    # Tooling helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def tool_available(name: str) -> bool:
        return shutil.which(name) is not None

    def _run(self, cmd: List[str], timeout: int = 60) -> Tuple[int, str, str]:
        self.logger.debug(f"exec: {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except FileNotFoundError as exc:
            self.logger.error(f"binary not found: {exc}")
            return 127, "", str(exc)
        except subprocess.TimeoutExpired:
            self.logger.error(f"command timed out: {' '.join(cmd)}")
            return 124, "", "timeout"
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error(f"command failed: {exc}")
            return 1, "", str(exc)

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    @classmethod
    def discover_devices(cls) -> List[DeviceInfo]:
        """Discover tape drives via pyudev (preferred) or /sys fallback."""
        devices: List[DeviceInfo] = []
        # Try pyudev first
        try:
            import pyudev
            context = pyudev.Context()
            for dev in context.list_devices(subsystem="scsi_tape"):
                devnode = dev.device_node
                if not devnode:
                    continue
                sg = None
                # find matching sg device
                for g in context.list_devices(subsystem="scsi_generic"):
                    if g.get("ID_PATH") == dev.get("ID_PATH"):
                        sg = g.device_node
                        break
                devices.append(DeviceInfo(
                    path=devnode,
                    sg_path=sg,
                    model=dev.get("ID_MODEL", "Unknown") or "Unknown",
                    serial=dev.get("ID_SERIAL_SHORT", "Unknown") or "Unknown",
                ))
            if devices:
                return devices
        except Exception:
            pass
        # /sys/class/scsi_tape
        base = Path("/sys/class/scsi_tape")
        if base.exists():
            for entry in sorted(base.iterdir()):
                name = entry.name  # e.g. nst0 / st0
                dev_path = f"/dev/{name}"
                sg = None
                # try to find matching sg device via sysfs
                try:
                    # /sys/class/scsi_tape/nst0/device/scsi_generic/sgX
                    gen_dir = entry / "device" / "scsi_generic"
                    if gen_dir.exists():
                        sgs = list(gen_dir.iterdir())
                        if sgs:
                            sg = f"/dev/{sgs[0].name}"
                except Exception:
                    sg = None
                model = "Unknown"
                serial = "Unknown"
                try:
                    model_path = entry / "device" / "model"
                    if model_path.exists():
                        model = model_path.read_text().strip()
                    serial_path = entry / "device" / "serial" if (entry / "device" / "serial").exists() else None
                    if serial_path:
                        serial = serial_path.read_text().strip()
                except Exception:
                    pass
                devices.append(DeviceInfo(path=dev_path, sg_path=sg, model=model, serial=serial))
        # Fallback: common device nodes
        if not devices:
            for n in range(4):
                for prefix in ("nst", "st"):
                    p = f"/dev/{prefix}{n}"
                    if Path(p).exists():
                        devices.append(DeviceInfo(path=p))
        return devices

    def set_device(self, device: str, sg_device: Optional[str] = None) -> None:
        with self._lock:
            self.device = device
            self.sg_device = sg_device
            self._generation = None
            self._bytes_written = 0
            self._bytes_read = 0
            self.logger.info(f"Active tape device set to {device}")

    # ------------------------------------------------------------------ #
    # Generation specs
    # ------------------------------------------------------------------ #
    @staticmethod
    def specs_for(gen: TapeGeneration) -> GenerationSpec:
        return _GENERATION_SPECS[gen]

    @staticmethod
    def all_generations() -> List[TapeGeneration]:
        return list(TapeGeneration)

    def detect_generation(self) -> Optional[TapeGeneration]:
        """Best-effort generation detection from drive model / inquiry."""
        if self._generation is not None:
            return self._generation
        # Try sg_inq
        target = self.sg_device or self.device
        if self.tool_available("sg_inq") and target:
            rc, out, err = self._run(["sg_inq", target])
            if rc == 0:
                text = out.lower()
                for gen in reversed(list(TapeGeneration)):
                    token = gen.value.lower().replace("-", "")
                    if token in text.replace("-", ""):
                        self._generation = gen
                        self.logger.info(f"Detected generation {gen.value} via sg_inq")
                        return gen
        # Try mt status
        rc, out, err = self._run(["mt", "-f", self.device, "status"])
        if rc == 0:
            text = (out + err).lower()
            for gen in reversed(list(TapeGeneration)):
                if gen.value.lower() in text:
                    self._generation = gen
                    return gen
        # Heuristic from model string
        model = ""
        for d in self.discover_devices():
            if d.path == self.device:
                model = d.model.lower()
        for gen in reversed(list(TapeGeneration)):
            if gen.value.lower().replace("-", "") in model.replace("-", "").replace(" ", ""):
                self._generation = gen
                return gen
        return self._generation

    def set_generation(self, gen: TapeGeneration) -> None:
        with self._lock:
            self._generation = gen
            self.logger.info(f"Generation set to {gen.value}")

    def current_generation(self) -> Optional[TapeGeneration]:
        return self._generation

    def native_capacity(self) -> Optional[int]:
        g = self._generation or self.detect_generation()
        if g is None:
            return None
        return self.specs_for(g).native_capacity_bytes

    def compressed_capacity(self) -> Optional[int]:
        g = self._generation or self.detect_generation()
        if g is None:
            return None
        return self.specs_for(g).compressed_capacity_bytes

    # ------------------------------------------------------------------ #
    # Status & telemetry
    # ------------------------------------------------------------------ #
    def status(self) -> TapeTelemetry:
        telem = TapeTelemetry(generation=self._generation)
        rc, out, err = self._run(["mt", "-f", self.device, "status"])
        text = out + "\n" + err
        telem.raw["mt_status"] = text.strip()
        low = text.lower()
        if "not ready" in low or "no tape" in low or "offline" in low:
            telem.status = TapeStatus.NOT_READY
        elif "write protect" in low:
            telem.status = TapeStatus.WRITE_PROTECTED
        elif "eot" in low or "end of tape" in low or "end-of-tape" in low:
            telem.status = TapeStatus.EOT
        elif "bot" in low or "beginning of tape" in low:
            telem.status = TapeStatus.BOT
        elif rc == 0:
            telem.status = TapeStatus.READY
        else:
            telem.status = TapeStatus.UNKNOWN
        # block size parse
        m = re.search(r"blocksize\s*=\s*(\d+)", low)
        if m:
            telem.block_size = int(m.group(1))
            self._block_size = telem.block_size
        telem.bytes_written = self._bytes_written
        telem.bytes_read = self._bytes_read
        return telem

    def is_eot(self) -> bool:
        return self.status().status == TapeStatus.EOT

    def is_ready(self) -> bool:
        return self.status().status in (TapeStatus.READY, TapeStatus.BOT)

    # ------------------------------------------------------------------ #
    # Basic operations
    # ------------------------------------------------------------------ #
    def rewind(self) -> bool:
        rc, _, err = self._run(["mt", "-f", self.device, "rewind"])
        if rc != 0:
            self.logger.error(f"rewind failed: {err}")
            return False
        self._bytes_written = 0
        self._bytes_read = 0
        self.logger.info("Tape rewound to BOT")
        return True

    def eject(self) -> bool:
        rc, _, err = self._run(["mt", "-f", self.device, "offline"])
        if rc != 0:
            self.logger.error(f"eject failed: {err}")
            return False
        self.logger.info("Tape ejected/offline")
        return True

    def retension(self) -> bool:
        rc, _, err = self._run(["mt", "-f", self.device, "retension"])
        if rc != 0:
            self.logger.error(f"retension failed: {err}")
            return False
        self.logger.info("Tape retensioned")
        return True

    def erase(self) -> bool:
        rc, _, err = self._run(["mt", "-f", self.device, "erase"], timeout=3600)
        if rc != 0:
            self.logger.error(f"erase failed: {err}")
            return False
        self.logger.info("Tape erased")
        return True

    def fsf(self, count: int = 1) -> bool:
        rc, _, err = self._run(["mt", "-f", self.device, "fsf", str(count)])
        if rc != 0:
            self.logger.error(f"fsf failed: {err}")
            return False
        return True

    def bsf(self, count: int = 1) -> bool:
        rc, _, err = self._run(["mt", "-f", self.device, "bsf", str(count)])
        if rc != 0:
            self.logger.error(f"bsf failed: {err}")
            return False
        return True

    def write_filemark(self, count: int = 1) -> bool:
        rc, _, err = self._run(["mt", "-f", self.device, "weof", str(count)])
        if rc != 0:
            self.logger.error(f"write filemark failed: {err}")
            return False
        return True

    # ------------------------------------------------------------------ #
    # Block size
    # ------------------------------------------------------------------ #
    def set_block_size(self, size: int) -> bool:
        # mt setblk
        rc, _, err = self._run(["mt", "-f", self.device, "setblk", str(size)])
        if rc != 0:
            self.logger.error(f"setblk failed: {err}")
            return False
        self._block_size = size
        self.logger.info(f"Block size set to {size}")
        return True

    def get_block_size(self) -> int:
        if self._block_size:
            return self._block_size
        t = self.status()
        if t.block_size:
            self._block_size = t.block_size
        return self._block_size

    # ------------------------------------------------------------------ #
    # Hardware compression
    # ------------------------------------------------------------------ #
    def set_hardware_compression(self, enabled: bool) -> bool:
        # mt compression 1/0
        val = "1" if enabled else "0"
        rc, _, err = self._run(["mt", "-f", self.device, "compression", val])
        if rc != 0:
            self.logger.warning(f"mt compression failed ({err}); trying sg mode page")
            return self._set_compression_sg(enabled)
        self._compression_hw = enabled
        self.logger.info(f"Hardware compression {'enabled' if enabled else 'disabled'}")
        return True

    def _set_compression_sg(self, enabled: bool) -> bool:
        if not (self.tool_available("sg_modes") and self.sg_device):
            return False
        # Best-effort; not all drives support via this path.
        self.logger.info("sg_modes compression toggle not implemented in detail; skipped")
        return False

    def hardware_compression_enabled(self) -> bool:
        return self._compression_hw

    # ------------------------------------------------------------------ #
    # Telemetry bookkeeping
    # ------------------------------------------------------------------ #
    def account_write(self, n: int) -> None:
        self._bytes_written += n

    def account_read(self, n: int) -> None:
        self._bytes_read += n

    def sg_logs(self) -> Dict[str, str]:
        """Best-effort telemetry via sg_logs (temperature, errors, etc.)."""
        result: Dict[str, str] = {}
        target = self.sg_device or self.device
        if not self.tool_available("sg_logs"):
            return result
        rc, out, err = self._run(["sg_logs", target])
        if rc != 0:
            return result
        for line in out.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                result[key.strip()] = val.strip()
        return result

    def reset_counters(self) -> None:
        self._bytes_written = 0
        self._bytes_read = 0