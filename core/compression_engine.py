"""Compression engine supporting uncompressed, software and hardware modes.

Software compression is implemented as transparent stream wrappers so the
backup pipeline can treat all modes uniformly. Hardware compression is
delegated to the drive via :class:`HardwareController`.
"""

from __future__ import annotations

import gzip
import io
import threading
from enum import Enum
from typing import BinaryIO, Optional

from .logger import TapeLogger

# Optional backends
try:  # pragma: no cover - import availability
    import zstandard as _zstd  # type: ignore
except Exception:  # noqa: BLE001
    _zstd = None

try:
    import pyzstd as _pyzstd  # type: ignore
except Exception:  # noqa: BLE001
    _pyzstd = None


class CompressionMode(Enum):
    NONE = "none"
    SOFTWARE_ZSTD = "software_zstd"
    SOFTWARE_GZIP = "software_gzip"
    HARDWARE = "hardware"


class CompressionEngine:
    """Factory for compressing/decompressing streams."""

    def __init__(self, logger: Optional[TapeLogger] = None) -> None:
        self.logger = logger or TapeLogger.instance()
        self._lock = threading.Lock()

    @staticmethod
    def software_available() -> bool:
        return _zstd is not None or _pyzstd is not None

    @staticmethod
    def preferred_software_mode() -> CompressionMode:
        if _zstd is not None or _pyzstd is not None:
            return CompressionMode.SOFTWARE_ZSTD
        return CompressionMode.SOFTWARE_GZIP

    def wrap_writer(self, raw: BinaryIO, mode: CompressionMode) -> BinaryIO:
        if mode == CompressionMode.NONE or mode == CompressionMode.HARDWARE:
            return raw
        if mode == CompressionMode.SOFTWARE_GZIP:
            return gzip.GzipFile(fileobj=raw, mode="wb")
        if mode == CompressionMode.SOFTWARE_ZSTD:
            if _zstd is not None and hasattr(_zstd, "ZstdFile"):
                return _zstd.ZstdFile(raw, "wb")
            if _pyzstd is not None and hasattr(_pyzstd, "ZstdFile"):
                return _pyzstd.ZstdFile(raw, "wb")
            if _zstd is not None:
                cctx = _zstd.ZstdCompressor()
                return cctx.stream_writer(raw)
        self.logger.warning("No zstd backend available; falling back to gzip")
        return gzip.GzipFile(fileobj=raw, mode="wb")

    def wrap_reader(self, raw: BinaryIO, mode: CompressionMode) -> BinaryIO:
        if mode == CompressionMode.NONE or mode == CompressionMode.HARDWARE:
            return raw
        if mode == CompressionMode.SOFTWARE_GZIP:
            return gzip.GzipFile(fileobj=raw, mode="rb")
        if mode == CompressionMode.SOFTWARE_ZSTD:
            if _zstd is not None and hasattr(_zstd, "ZstdFile"):
                return _zstd.ZstdFile(raw, "rb")
            if _pyzstd is not None and hasattr(_pyzstd, "ZstdFile"):
                return _pyzstd.ZstdFile(raw, "rb")
            if _zstd is not None:
                dctx = _zstd.ZstdDecompressor()
                return dctx.stream_reader(raw)
        return gzip.GzipFile(fileobj=raw, mode="rb")


class _ZstdWriter(io.RawIOBase):
    def __init__(self, raw: BinaryIO, cctx: object) -> None:
        self._raw = raw
        self._compressor = cctx.stream_writer(raw) if hasattr(cctx, "stream_writer") else None
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> int:  # type: ignore[override]
        if self._compressor is not None:
            self._compressor.write(data)
            return len(data)
        return self._raw.write(data)

    def flush(self) -> None:  # type: ignore[override]
        if self._compressor is not None:
            self._compressor.flush()
        self._raw.flush()

    def close(self) -> None:  # type: ignore[override]
        if self._compressor is not None:
            self._compressor.close()
        self._raw.close()


class _ZstdReader(io.RawIOBase):
    def __init__(self, raw: BinaryIO, dctx: object) -> None:
        self._reader = dctx.stream_reader(raw) if hasattr(dctx, "stream_reader") else raw

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        return self._reader.read(size)

    def close(self) -> None:  # type: ignore[override]
        try:
            self._reader.close()
        except Exception:
            pass


class _PyzstdWriter(io.RawIOBase):
    def __init__(self, raw: BinaryIO) -> None:
        self._raw = raw
        self._c = _pyzstd.ZstdCompressor() if _pyzstd else None
        self._buf = bytearray()

    def write(self, data: bytes) -> int:  # type: ignore[override]
        if self._c is not None:
            self._raw.write(self._c.compress(data))
        else:
            self._raw.write(data)
        return len(data)

    def flush(self) -> None:  # type: ignore[override]
        self._raw.flush()

    def close(self) -> None:  # type: ignore[override]
        self._raw.close()


class _PyzstdReader(io.RawIOBase):
    def __init__(self, raw: BinaryIO) -> None:
        self._raw = raw
        self._d = _pyzstd.ZstdDecompressor() if _pyzstd else None
        self._pending = b""

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        data = self._raw.read() if size < 0 else self._raw.read(size)
        if self._d is not None and data:
            try:
                return self._d.decompress(data)
            except Exception:
                return data
        return data

    def close(self) -> None:  # type: ignore[override]
        self._raw.close()