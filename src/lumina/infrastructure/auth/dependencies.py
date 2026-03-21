"""
FastAPI dependencies for authentication and authorisation.

Provides injectable callables that extract and validate credentials
from incoming requests (JWT bearer tokens and API keys).
"""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from lumina.infrastructure.auth.jwt_handler import decode_token
from lumina.infrastructure.auth.rbac import Role, role_at_least

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """Extract and decode the JWT from the ``Authorization: Bearer <token>`` header.

    Returns a dict with ``user_id``, ``tenant_id``, and ``role`` keys.
    The decoded user info is also stored on ``request.state.current_user``.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — access token required",
        )

    user_info = {
        "user_id": payload["sub"],
        "tenant_id": payload.get("tenant_id"),
        "role": payload.get("role"),
    }
    request.state.current_user = user_info
    return user_info


async def get_current_tenant(
    user: Annotated[dict, Depends(get_current_user)],
) -> str:
    """Return the tenant_id extracted from the authenticated user's JWT."""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant associated with this token",
        )
    return tenant_id


def require_role(min_role: Role):
    """Dependency factory that enforces a minimum role level.

    Usage::

        @router.post("/admin-action", dependencies=[Depends(require_role(Role.ADMIN))])
        async def do_admin_thing(): ...
    """

    async def _checker(
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        role_str = user.get("role", "")
        try:
            role = Role(role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown role: {role_str}",
            )
        if not role_at_least(role, min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least '{min_role.value}' role",
            )
        return user

    return _checker


async def get_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> dict | None:
    """Validate an ``X-API-Key`` header for machine-to-machine auth.

    Returns ``None`` when the header is absent (allowing fallback to JWT).
    When present, the key is verified via the auth service stored in
    ``request.app.state``.  Only tenants on the *enterprise* plan may
    use API key authentication.
    """
    if api_key is None:
        return None

    auth_service = getattr(request.app.state, "auth_service", None)
    if auth_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service not available",
        )

    result = auth_service.validate_api_key(api_key)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    tenant_id, permissions = result
    return {
        "tenant_id": tenant_id,
        "permissions": permissions,
        "auth_method": "api_key",
    }
