"""
Role-Based Access Control (RBAC) for LUMINA.

Defines roles, permissions, and the mapping between them.
Provides a FastAPI dependency (``require_permission``) that can be injected
into route handlers to enforce authorisation.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status


class Role(str, Enum):
    """Tenant membership roles ordered from most to least privileged."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Permission(str, Enum):
    """Granular permissions that can be checked on any request."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MANAGE_TEAM = "manage_team"
    MANAGE_BILLING = "manage_billing"
    API_ACCESS = "api_access"


# Hierarchical permission mapping — more privileged roles inherit downward.
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.OWNER: {
        Permission.READ,
        Permission.WRITE,
        Permission.DELETE,
        Permission.MANAGE_TEAM,
        Permission.MANAGE_BILLING,
        Permission.API_ACCESS,
    },
    Role.ADMIN: {
        Permission.READ,
        Permission.WRITE,
        Permission.DELETE,
        Permission.MANAGE_TEAM,
        Permission.API_ACCESS,
    },
    Role.MEMBER: {
        Permission.READ,
        Permission.WRITE,
        Permission.API_ACCESS,
    },
    Role.VIEWER: {
        Permission.READ,
    },
}

# Privilege ordering for role comparisons (lower index = more privileged).
_ROLE_RANK: dict[Role, int] = {
    Role.OWNER: 0,
    Role.ADMIN: 1,
    Role.MEMBER: 2,
    Role.VIEWER: 3,
}


def has_permission(role: Role, permission: Permission) -> bool:
    """Return ``True`` if *role* includes *permission*."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def role_at_least(role: Role, min_role: Role) -> bool:
    """Return ``True`` if *role* is at least as privileged as *min_role*."""
    return _ROLE_RANK.get(role, 99) <= _ROLE_RANK.get(min_role, 99)


def require_permission(permission: Permission):
    """FastAPI dependency factory that checks the current user's role for *permission*.

    Usage::

        @router.get("/secrets", dependencies=[Depends(require_permission(Permission.MANAGE_BILLING))])
        async def get_secrets(): ...
    """

    async def _checker(request: Request) -> None:
        user = getattr(request.state, "current_user", None)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        role_str = user.get("role", "")
        try:
            role = Role(role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown role: {role_str}",
            )
        if not has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission.value}' denied for role '{role.value}'",
            )

    return _checker
