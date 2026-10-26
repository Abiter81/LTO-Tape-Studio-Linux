"""Optional authenticated encryption helpers (Fernet / AES-128-CBC+HMAC)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def derive_key(passphrase: str, salt: bytes = b"lto-tape-studio") -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000)
    key = kdf.derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(key)


def make_fernet(passphrase: str) -> Fernet:
    return Fernet(derive_key(passphrase))


def encrypt_bytes(data: bytes, passphrase: str) -> bytes:
    return make_fernet(passphrase).encrypt(data)


def decrypt_bytes(data: bytes, passphrase: str) -> bytes:
    return make_fernet(passphrase).decrypt(data)