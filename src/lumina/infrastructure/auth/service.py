"""
Authentication / authorisation service for LUMINA.

Coordinates user registration, login, token management, tenant creation,
team invitations, and API key lifecycle.  Designed to work with an in-memory
store for local development and tests, and to be swapped for a real database
repository in production.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC

from lumina.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from lumina.infrastructure.auth.password import hash_password, verify_password
from lumina.infrastructure.auth.rbac import Role


# ---------------------------------------------------------------------------
# Lightweight data transfer objects
# ---------------------------------------------------------------------------

@dataclass
class UserDTO:
    id: str
    email: str
    name: str
    is_active: bool
    created_at: datetime


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass
class TenantDTO:
    id: str
    name: str
    slug: str
    plan_tier: str
    is_active: bool
    created_at: datetime


@dataclass
class InvitationDTO:
    tenant_id: str
    email: str
    role: str
    invited_at: datetime


@dataclass
class APIKeyDTO:
    id: str
    tenant_id: str
    name: str
    raw_key: str  # Only available at creation time
    permissions: list[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# In-memory record types (private)
# ---------------------------------------------------------------------------

@dataclass
class _UserRecord:
    id: str
    email: str
    name: str
    hashed_password: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class _TenantRecord:
    id: str
    name: str
    slug: str
    plan_tier: str = "starter"
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class _MembershipRecord:
    user_id: str
    tenant_id: str
    role: str
    invited_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    accepted_at: datetime | None = None


@dataclass
class _APIKeyRecord:
    id: str
    tenant_id: str
    key_hash: str
    name: str
    permissions: list[str]
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class AuthService:
    """Application-layer authentication and authorisation service.

    By default uses a simple in-memory store.  Pass your own repository
    dicts/objects to override for production.
    """

    def __init__(self) -> None:
        self._users: dict[str, _UserRecord] = {}  # keyed by user id
        self._users_by_email: dict[str, str] = {}  # email -> user id
        self._tenants: dict[str, _TenantRecord] = {}  # keyed by tenant id
        self._memberships: list[_MembershipRecord] = []
        self._api_keys: dict[str, _APIKeyRecord] = {}  # keyed by key id
        self._api_key_hashes: dict[str, str] = {}  # hash -> key id

    # --- User registration & login -------------------------------------------

    def register_user(self, email: str, password: str, name: str) -> UserDTO:
        """Register a new user.  Raises ``ValueError`` if the email is taken."""
        email = email.strip().lower()
        if email in self._users_by_email:
            raise ValueError(f"Email already registered: {email}")

        user_id = str(uuid.uuid4())
        record = _UserRecord(
            id=user_id,
            email=email,
            name=name.strip(),
            hashed_password=hash_password(password),
        )
        self._users[user_id] = record
        self._users_by_email[email] = user_id
        return UserDTO(
            id=record.id,
            email=record.email,
            name=record.name,
            is_active=record.is_active,
            created_at=record.created_at,
        )

    def login(self, email: str, password: str) -> TokenPair:
        """Authenticate and return an access/refresh token pair.

        Raises ``ValueError`` on invalid credentials.
        """
        email = email.strip().lower()
        user_id = self._users_by_email.get(email)
        if user_id is None:
            raise ValueError("Invalid email or password")
        user = self._users[user_id]
        if not user.is_active:
            raise ValueError("Account is deactivated")
        if not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")

        # Pick the first tenant+role for the user (if any) to embed in the token.
        tenant_id = ""
        role = Role.VIEWER.value
        for m in self._memberships:
            if m.user_id == user_id:
                tenant_id = m.tenant_id
                role = m.role
                break

        access = create_access_token(user_id, tenant_id, role)
        refresh = create_refresh_token(user_id)
        return TokenPair(access_token=access, refresh_token=refresh)

    def refresh_token(self, refresh_tok: str) -> TokenPair:
        """Exchange a valid refresh token for a new token pair.

        Raises ``ValueError`` when the refresh token is invalid or expired.
        """
        try:
            payload = decode_token(refresh_tok)
        except Exception as exc:
            raise ValueError(f"Invalid refresh token: {exc}")
        if payload.get("type") != "refresh":
            raise ValueError("Token is not a refresh token")

        user_id = payload["sub"]
        user = self._users.get(user_id)
        if user is None or not user.is_active:
            raise ValueError("User not found or inactive")

        tenant_id = ""
        role = Role.VIEWER.value
        for m in self._memberships:
            if m.user_id == user_id:
                tenant_id = m.tenant_id
                role = m.role
                break

        access = create_access_token(user_id, tenant_id, role)
        refresh = create_refresh_token(user_id)
        return TokenPair(access_token=access, refresh_token=refresh)

    # --- Tenant management ----------------------------------------------------

    def create_tenant(self, name: str, owner_user_id: str) -> TenantDTO:
        """Create a new tenant and make *owner_user_id* the owner."""
        if owner_user_id not in self._users:
            raise ValueError("Owner user not found")

        tenant_id = str(uuid.uuid4())
        slug = _slugify(name)
        # Ensure slug uniqueness
        existing_slugs = {t.slug for t in self._tenants.values()}
        if slug in existing_slugs:
            slug = f"{slug}-{tenant_id[:8]}"

        record = _TenantRecord(id=tenant_id, name=name.strip(), slug=slug)
        self._tenants[tenant_id] = record

        membership = _MembershipRecord(
            user_id=owner_user_id,
            tenant_id=tenant_id,
            role=Role.OWNER.value,
            accepted_at=datetime.now(UTC),
        )
        self._memberships.append(membership)

        return TenantDTO(
            id=record.id,
            name=record.name,
            slug=record.slug,
            plan_tier=record.plan_tier,
            is_active=record.is_active,
            created_at=record.created_at,
        )

    def invite_member(self, tenant_id: str, email: str, role: str) -> InvitationDTO:
        """Invite a user (by email) to a tenant with the given role.

        If the user does not exist yet, the invitation is still recorded so it
        can be fulfilled when they register.
        """
        if tenant_id not in self._tenants:
            raise ValueError("Tenant not found")

        email = email.strip().lower()
        now = datetime.now(UTC)

        # If user already exists, create the membership immediately.
        user_id = self._users_by_email.get(email)
        if user_id:
            # Check for existing membership
            for m in self._memberships:
                if m.user_id == user_id and m.tenant_id == tenant_id:
                    raise ValueError("User is already a member of this tenant")
            self._memberships.append(
                _MembershipRecord(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    role=role,
                    invited_at=now,
                    accepted_at=now,
                )
            )

        return InvitationDTO(
            tenant_id=tenant_id,
            email=email,
            role=role,
            invited_at=now,
        )

    # --- API keys -------------------------------------------------------------

    def create_api_key(
        self, tenant_id: str, name: str, permissions: list[str]
    ) -> APIKeyDTO:
        """Generate a new API key for a tenant.  The raw key is returned only once."""
        if tenant_id not in self._tenants:
            raise ValueError("Tenant not found")

        raw_key = f"lum_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = str(uuid.uuid4())

        record = _APIKeyRecord(
            id=key_id,
            tenant_id=tenant_id,
            key_hash=key_hash,
            name=name,
            permissions=permissions,
        )
        self._api_keys[key_id] = record
        self._api_key_hashes[key_hash] = key_id

        return APIKeyDTO(
            id=key_id,
            tenant_id=tenant_id,
            name=name,
            raw_key=raw_key,
            permissions=permissions,
            created_at=record.created_at,
        )

    def validate_api_key(self, raw_key: str) -> tuple[str, list[str]] | None:
        """Validate a raw API key string.

        Returns ``(tenant_id, permissions)`` on success, ``None`` on failure.
        """
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = self._api_key_hashes.get(key_hash)
        if key_id is None:
            return None
        record = self._api_keys.get(key_id)
        if record is None or not record.is_active:
            return None

        # Update last_used_at
        record.last_used_at = datetime.now(UTC)
        return (record.tenant_id, record.permissions)

    # --- Helpers (for current_user endpoint, etc.) ----------------------------

    def get_user(self, user_id: str) -> UserDTO | None:
        """Return user DTO by id, or None."""
        record = self._users.get(user_id)
        if record is None:
            return None
        return UserDTO(
            id=record.id,
            email=record.email,
            name=record.name,
            is_active=record.is_active,
            created_at=record.created_at,
        )

    def get_memberships_for_user(self, user_id: str) -> list[dict]:
        """Return a list of tenants and roles for a given user."""
        results = []
        for m in self._memberships:
            if m.user_id == user_id:
                tenant = self._tenants.get(m.tenant_id)
                results.append({
                    "tenant_id": m.tenant_id,
                    "tenant_name": tenant.name if tenant else "",
                    "role": m.role,
                })
        return results
