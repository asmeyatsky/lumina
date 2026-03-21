"""
Tests for the LUMINA authentication and authorisation system.

Covers:
- Password hashing and verification
- JWT token creation and decoding
- RBAC permission checks
- Register + login flow via AuthService
- API key validation
- Tenant isolation
"""

from __future__ import annotations

import time
from datetime import timedelta

import jwt
import pytest

from lumina.infrastructure.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from lumina.infrastructure.auth.password import hash_password, verify_password
from lumina.infrastructure.auth.rbac import (
    Permission,
    Role,
    ROLE_PERMISSIONS,
    has_permission,
    role_at_least,
)
from lumina.infrastructure.auth.service import AuthService


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    """Tests for password hash / verify round-trip."""

    def test_hash_returns_pbkdf2_format(self) -> None:
        hashed = hash_password("my-secret")
        assert hashed.startswith("$pbkdf2-sha256$")
        parts = hashed.split("$")
        assert len(parts) == 5

    def test_verify_correct_password(self) -> None:
        hashed = hash_password("correct-horse-battery")
        assert verify_password("correct-horse-battery", hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = hash_password("correct-horse-battery")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_for_same_password(self) -> None:
        """Each call uses a unique salt, so hashes must differ."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        # But both must verify correctly
        assert verify_password("same-password", h1) is True
        assert verify_password("same-password", h2) is True

    def test_verify_garbage_hash_returns_false(self) -> None:
        assert verify_password("anything", "not-a-valid-hash") is False

    def test_verify_empty_password(self) -> None:
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("non-empty", hashed) is False


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

class TestJWT:
    """Tests for JWT creation and decoding."""

    def test_create_and_decode_access_token(self) -> None:
        token = create_access_token("user-1", "tenant-1", "admin")
        payload = decode_token(token)
        assert payload["sub"] == "user-1"
        assert payload["tenant_id"] == "tenant-1"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self) -> None:
        token = create_refresh_token("user-2")
        payload = decode_token(token)
        assert payload["sub"] == "user-2"
        assert payload["type"] == "refresh"
        assert "tenant_id" not in payload

    def test_access_token_contains_jti(self) -> None:
        t1 = create_access_token("u", "t", "member")
        t2 = create_access_token("u", "t", "member")
        p1 = decode_token(t1)
        p2 = decode_token(t2)
        assert p1["jti"] != p2["jti"]

    def test_expired_token_raises(self) -> None:
        token = create_access_token(
            "user-1", "tenant-1", "admin",
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token)

    def test_invalid_token_raises(self) -> None:
        with pytest.raises(jwt.InvalidTokenError):
            decode_token("this.is.garbage")

    def test_custom_expiry(self) -> None:
        token = create_access_token(
            "u", "t", "viewer",
            expires_delta=timedelta(hours=2),
        )
        payload = decode_token(token)
        assert payload["sub"] == "u"


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

class TestRBAC:
    """Tests for role / permission logic."""

    def test_owner_has_all_permissions(self) -> None:
        for perm in Permission:
            assert has_permission(Role.OWNER, perm) is True, f"Owner should have {perm}"

    def test_admin_has_manage_team_but_not_billing(self) -> None:
        assert has_permission(Role.ADMIN, Permission.MANAGE_TEAM) is True
        assert has_permission(Role.ADMIN, Permission.MANAGE_BILLING) is False

    def test_member_has_read_write_api_access(self) -> None:
        assert has_permission(Role.MEMBER, Permission.READ) is True
        assert has_permission(Role.MEMBER, Permission.WRITE) is True
        assert has_permission(Role.MEMBER, Permission.API_ACCESS) is True
        assert has_permission(Role.MEMBER, Permission.DELETE) is False

    def test_viewer_has_read_only(self) -> None:
        assert has_permission(Role.VIEWER, Permission.READ) is True
        assert has_permission(Role.VIEWER, Permission.WRITE) is False
        assert has_permission(Role.VIEWER, Permission.DELETE) is False
        assert has_permission(Role.VIEWER, Permission.MANAGE_TEAM) is False
        assert has_permission(Role.VIEWER, Permission.MANAGE_BILLING) is False
        assert has_permission(Role.VIEWER, Permission.API_ACCESS) is False

    def test_role_at_least(self) -> None:
        assert role_at_least(Role.OWNER, Role.VIEWER) is True
        assert role_at_least(Role.ADMIN, Role.ADMIN) is True
        assert role_at_least(Role.VIEWER, Role.ADMIN) is False
        assert role_at_least(Role.MEMBER, Role.MEMBER) is True
        assert role_at_least(Role.MEMBER, Role.ADMIN) is False

    def test_role_permissions_keys_cover_all_roles(self) -> None:
        for role in Role:
            assert role in ROLE_PERMISSIONS, f"Missing permissions for {role}"


# ---------------------------------------------------------------------------
# AuthService — register + login flow
# ---------------------------------------------------------------------------

class TestAuthServiceRegistration:
    """Tests for user registration and login via the auth service."""

    def _make_service(self) -> AuthService:
        return AuthService()

    def test_register_and_login(self) -> None:
        svc = self._make_service()
        user = svc.register_user("alice@example.com", "Str0ngP@ss!", "Alice")
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.is_active is True

        tokens = svc.login("alice@example.com", "Str0ngP@ss!")
        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.token_type == "bearer"

    def test_register_duplicate_email_raises(self) -> None:
        svc = self._make_service()
        svc.register_user("dup@example.com", "password1!", "Dup")
        with pytest.raises(ValueError, match="already registered"):
            svc.register_user("dup@example.com", "password2!", "Dup2")

    def test_login_wrong_password(self) -> None:
        svc = self._make_service()
        svc.register_user("bob@example.com", "correct-pw!", "Bob")
        with pytest.raises(ValueError, match="Invalid email or password"):
            svc.login("bob@example.com", "wrong-pw!")

    def test_login_nonexistent_user(self) -> None:
        svc = self._make_service()
        with pytest.raises(ValueError, match="Invalid email or password"):
            svc.login("nobody@example.com", "pw!")

    def test_refresh_token_flow(self) -> None:
        svc = self._make_service()
        svc.register_user("carol@example.com", "pass1234!", "Carol")
        tokens = svc.login("carol@example.com", "pass1234!")

        new_tokens = svc.refresh_token(tokens.refresh_token)
        assert new_tokens.access_token
        assert new_tokens.refresh_token
        assert new_tokens.access_token != tokens.access_token

    def test_refresh_with_access_token_fails(self) -> None:
        svc = self._make_service()
        svc.register_user("dan@example.com", "pass1234!", "Dan")
        tokens = svc.login("dan@example.com", "pass1234!")
        with pytest.raises(ValueError, match="not a refresh token"):
            svc.refresh_token(tokens.access_token)

    def test_get_user(self) -> None:
        svc = self._make_service()
        user = svc.register_user("eve@example.com", "pass1234!", "Eve")
        fetched = svc.get_user(user.id)
        assert fetched is not None
        assert fetched.email == "eve@example.com"

    def test_get_nonexistent_user(self) -> None:
        svc = self._make_service()
        assert svc.get_user("no-such-id") is None


# ---------------------------------------------------------------------------
# AuthService — tenant creation and invitations
# ---------------------------------------------------------------------------

class TestAuthServiceTenants:
    """Tests for tenant management."""

    def _make_service_with_user(self) -> tuple[AuthService, str]:
        svc = AuthService()
        user = svc.register_user("owner@example.com", "pass1234!", "Owner")
        return svc, user.id

    def test_create_tenant(self) -> None:
        svc, uid = self._make_service_with_user()
        tenant = svc.create_tenant("Acme Corp", uid)
        assert tenant.name == "Acme Corp"
        assert tenant.slug == "acme-corp"
        assert tenant.plan_tier == "starter"
        assert tenant.is_active is True

    def test_create_tenant_unknown_owner_fails(self) -> None:
        svc = AuthService()
        with pytest.raises(ValueError, match="Owner user not found"):
            svc.create_tenant("X Corp", "no-such-user")

    def test_invite_member(self) -> None:
        svc, uid = self._make_service_with_user()
        tenant = svc.create_tenant("Acme Corp", uid)
        svc.register_user("member@example.com", "pass1234!", "Member")
        invitation = svc.invite_member(tenant.id, "member@example.com", "member")
        assert invitation.tenant_id == tenant.id
        assert invitation.email == "member@example.com"
        assert invitation.role == "member"

    def test_invite_member_to_nonexistent_tenant_fails(self) -> None:
        svc = AuthService()
        with pytest.raises(ValueError, match="Tenant not found"):
            svc.invite_member("fake-tenant", "a@b.com", "viewer")

    def test_invite_duplicate_member_fails(self) -> None:
        svc, uid = self._make_service_with_user()
        tenant = svc.create_tenant("T1", uid)
        svc.register_user("m@e.com", "pass1234!", "M")
        svc.invite_member(tenant.id, "m@e.com", "member")
        with pytest.raises(ValueError, match="already a member"):
            svc.invite_member(tenant.id, "m@e.com", "viewer")

    def test_login_after_tenant_creation_includes_tenant(self) -> None:
        svc, uid = self._make_service_with_user()
        tenant = svc.create_tenant("ACME", uid)
        tokens = svc.login("owner@example.com", "pass1234!")
        payload = decode_token(tokens.access_token)
        assert payload["tenant_id"] == tenant.id
        assert payload["role"] == "owner"

    def test_get_memberships_for_user(self) -> None:
        svc, uid = self._make_service_with_user()
        svc.create_tenant("T1", uid)
        svc.create_tenant("T2", uid)
        memberships = svc.get_memberships_for_user(uid)
        assert len(memberships) == 2
        assert all(m["role"] == "owner" for m in memberships)


# ---------------------------------------------------------------------------
# AuthService — API key management
# ---------------------------------------------------------------------------

class TestAuthServiceAPIKeys:
    """Tests for API key creation and validation."""

    def _make_service_with_tenant(self) -> tuple[AuthService, str, str]:
        svc = AuthService()
        user = svc.register_user("admin@example.com", "pass1234!", "Admin")
        tenant = svc.create_tenant("KeyCorp", user.id)
        return svc, user.id, tenant.id

    def test_create_api_key(self) -> None:
        svc, _, tid = self._make_service_with_tenant()
        key = svc.create_api_key(tid, "CI Pipeline", ["read", "write"])
        assert key.raw_key.startswith("lum_")
        assert key.name == "CI Pipeline"
        assert key.permissions == ["read", "write"]

    def test_validate_api_key(self) -> None:
        svc, _, tid = self._make_service_with_tenant()
        key = svc.create_api_key(tid, "Test Key", ["read"])
        result = svc.validate_api_key(key.raw_key)
        assert result is not None
        tenant_id, perms = result
        assert tenant_id == tid
        assert perms == ["read"]

    def test_validate_invalid_key_returns_none(self) -> None:
        svc, _, tid = self._make_service_with_tenant()
        assert svc.validate_api_key("lum_nonexistent") is None

    def test_api_key_for_nonexistent_tenant_fails(self) -> None:
        svc = AuthService()
        with pytest.raises(ValueError, match="Tenant not found"):
            svc.create_api_key("no-tenant", "key", [])

    def test_multiple_api_keys_per_tenant(self) -> None:
        svc, _, tid = self._make_service_with_tenant()
        k1 = svc.create_api_key(tid, "Key 1", ["read"])
        k2 = svc.create_api_key(tid, "Key 2", ["read", "write"])

        r1 = svc.validate_api_key(k1.raw_key)
        r2 = svc.validate_api_key(k2.raw_key)
        assert r1 is not None and r1[1] == ["read"]
        assert r2 is not None and r2[1] == ["read", "write"]


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    """Verify that tenants are properly isolated."""

    def test_tokens_scope_to_correct_tenant(self) -> None:
        svc = AuthService()
        u1 = svc.register_user("t1@example.com", "pass1234!", "User1")
        u2 = svc.register_user("t2@example.com", "pass1234!", "User2")

        tenant_a = svc.create_tenant("Tenant A", u1.id)
        tenant_b = svc.create_tenant("Tenant B", u2.id)

        tok_a = svc.login("t1@example.com", "pass1234!")
        tok_b = svc.login("t2@example.com", "pass1234!")

        payload_a = decode_token(tok_a.access_token)
        payload_b = decode_token(tok_b.access_token)

        assert payload_a["tenant_id"] == tenant_a.id
        assert payload_b["tenant_id"] == tenant_b.id
        assert payload_a["tenant_id"] != payload_b["tenant_id"]

    def test_api_keys_isolated_per_tenant(self) -> None:
        svc = AuthService()
        u1 = svc.register_user("a1@example.com", "pass1234!", "A1")
        u2 = svc.register_user("a2@example.com", "pass1234!", "A2")
        t1 = svc.create_tenant("Iso-A", u1.id)
        t2 = svc.create_tenant("Iso-B", u2.id)

        k1 = svc.create_api_key(t1.id, "K1", ["read"])
        k2 = svc.create_api_key(t2.id, "K2", ["read"])

        r1 = svc.validate_api_key(k1.raw_key)
        r2 = svc.validate_api_key(k2.raw_key)

        assert r1 is not None and r1[0] == t1.id
        assert r2 is not None and r2[0] == t2.id
        assert r1[0] != r2[0]

    def test_membership_does_not_leak_across_tenants(self) -> None:
        svc = AuthService()
        u1 = svc.register_user("m1@example.com", "pass1234!", "M1")
        u2 = svc.register_user("m2@example.com", "pass1234!", "M2")
        t1 = svc.create_tenant("TenantX", u1.id)
        t2 = svc.create_tenant("TenantY", u2.id)

        memberships_u1 = svc.get_memberships_for_user(u1.id)
        memberships_u2 = svc.get_memberships_for_user(u2.id)

        assert len(memberships_u1) == 1
        assert memberships_u1[0]["tenant_id"] == t1.id
        assert len(memberships_u2) == 1
        assert memberships_u2[0]["tenant_id"] == t2.id
