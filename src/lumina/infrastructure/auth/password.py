"""
Password hashing utilities for LUMINA.

Uses PBKDF2-HMAC-SHA256 with a random salt (hashlib-based, no external deps).
Format: ``$pbkdf2-sha256$<iterations>$<b64-salt>$<b64-hash>``
"""

from __future__ import annotations

import base64
import hashlib
import os

_ITERATIONS = 260_000
_HASH_NAME = "sha256"
_DK_LEN = 32
_SALT_LEN = 16


def hash_password(plain: str) -> str:
    """Derive a salted PBKDF2-SHA256 hash from a plain-text password."""
    salt = os.urandom(_SALT_LEN)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, plain.encode("utf-8"), salt, _ITERATIONS, dklen=_DK_LEN)
    b64_salt = base64.b64encode(salt).decode("ascii")
    b64_hash = base64.b64encode(dk).decode("ascii")
    return f"$pbkdf2-sha256${_ITERATIONS}${b64_salt}${b64_hash}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a stored hash string."""
    try:
        parts = hashed.split("$")
        # Expected: ['', 'pbkdf2-sha256', '<iterations>', '<b64-salt>', '<b64-hash>']
        if len(parts) != 5 or parts[1] != "pbkdf2-sha256":
            return False
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3])
        stored_hash = base64.b64decode(parts[4])
        dk = hashlib.pbkdf2_hmac(_HASH_NAME, plain.encode("utf-8"), salt, iterations, dklen=len(stored_hash))
        return dk == stored_hash
    except Exception:
        return False
