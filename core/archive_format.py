"""Self-describing multivolume archive container format (LTO Tape Studio).

Each volume begins with a ``VOLUME`` record and ends with a ``VOLUME_END``
record. File data is split into ``FILE`` / ``FILEPART`` records so that no
record ever straddles a volume boundary, even when a single file is larger
than the remaining capacity of a tape.

Record layout on the (possibly compressed) stream::

    <TYPE>\\t<JSON_META>\\t<DATA_LEN>\\n<DATA_BYTES>

``DATA_LEN`` is the exact number of bytes that follow; the next record starts
immediately afterwards.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any, BinaryIO, Dict, Iterator, Optional, Tuple


@dataclass
class VolumeHeader:
    magic: str = "LTOVS1"
    version: int = 1
    volume: int = 1
    job_id: str = ""
    label: str = ""
    compression: str = "none"
    checksum_algo: str = "sha256"
    created: float = 0.0
    previous_volume: int = 0

    def to_meta(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VolumeTrailer:
    volume: int = 1
    bytes_written: int = 0
    records: int = 0
    volume_checksum: str = ""
    next_volume: bool = False


def write_record(stream: BinaryIO, rtype: str, meta: Dict[str, Any], data: bytes = b"") -> None:
    header = f"{rtype}\t{json.dumps(meta, separators=(',', ':'))}\t{len(data)}\n".encode("utf-8")
    stream.write(header)
    if data:
        stream.write(data)


def read_record(stream: BinaryIO) -> Optional[Tuple[str, Dict[str, Any], bytes]]:
    """Read one record; return None at clean EOF."""
    line = stream.readline()
    if not line:
        return None
    if line.endswith(b"\n"):
        line = line[:-1]
    if not line:
        # skip blank lines
        return read_record(stream)
    parts = line.split(b"\t", 2)
    if len(parts) != 3:
        raise ValueError(f"malformed record header: {line!r}")
    rtype = parts[0].decode("utf-8")
    meta = json.loads(parts[1].decode("utf-8"))
    size = int(parts[2])
    data = stream.read(size)
    if len(data) != size:
        raise EOFError(f"short read: expected {size}, got {len(data)}")
    return rtype, meta, data


def iter_records(stream: BinaryIO) -> Iterator[Tuple[str, Dict[str, Any], bytes]]:
    while True:
        rec = read_record(stream)
        if rec is None:
            break
        yield rec


def make_volume_header(volume: int, job_id: str, label: str, compression: str, checksum_algo: str, previous: int = 0) -> VolumeHeader:
    return VolumeHeader(
        volume=volume,
        job_id=job_id,
        label=label,
        compression=compression,
        checksum_algo=checksum_algo,
        created=time.time(),
        previous_volume=previous,
    )


def now() -> float:
    return time.time()