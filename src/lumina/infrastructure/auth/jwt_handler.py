"""
JWT token management for LUMINA.

Uses PyJWT with HS256 signing.  The secret is read from the ``JWT_SECRET``
environment variable (falls back to an insecure default for local dev).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, UTC

import jwt

_SECRET = os.environ.get("JWT_SECRET", "lumina-dev-secret-change-me")
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 30
_REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token containing user, tenant, and role claims."""
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a signed JWT refresh token (longer-lived, minimal claims)."""
    now = datetime.now(UTC)
    expire = now + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token, returning the payload dict.

    Raises ``jwt.ExpiredSignatureError`` or ``jwt.InvalidTokenError`` on failure.
    """
    return jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
