"""Cryptographic integrity helpers (MD5, SHA-256, SHA-512)."""

from __future__ import annotations

import hashlib
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Union

CHUNK_SIZE = 1024 * 1024


class HashAlgorithm(Enum):
    MD5 = "md5"
    SHA256 = "sha256"
    SHA512 = "sha512"


def compute_file(path: Union[str, Path], algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> str:
    """Compute hex digest of a file."""
    h = hashlib.new(algorithm.value)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_stream(stream: BinaryIO, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> str:
    """Compute hex digest of a binary stream (consumes it)."""
    h = hashlib.new(algorithm.value)
    for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
        h.update(chunk)
    return h.hexdigest()


def verify_file(path: Union[str, Path], expected: str, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> bool:
    return compute_file(path, algorithm).lower() == expected.lower()