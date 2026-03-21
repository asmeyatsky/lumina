"""
SQLAlchemy models for LUMINA authentication and authorization.

Tables:
- users: registered platform users
- tenants: organisations / workspaces
- tenant_memberships: many-to-many with role
- api_keys: machine-to-machine credentials
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Shared declarative base for auth models."""

    pass


class UserModel(Base):
    __tablename__ = "users"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: str = Column(String(255), unique=True, nullable=False, index=True)
    name: str = Column(String(255), nullable=False)
    hashed_password: str = Column(Text, nullable=False)
    is_active: bool = Column(Boolean, default=True, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    memberships = relationship("TenantMembershipModel", back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class TenantModel(Base):
    __tablename__ = "tenants"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = Column(String(255), nullable=False)
    slug: str = Column(String(255), unique=True, nullable=False, index=True)
    plan_tier: str = Column(
        SAEnum("starter", "growth", "enterprise", name="plan_tier_enum"),
        default="starter",
        nullable=False,
    )
    is_active: bool = Column(Boolean, default=True, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    memberships = relationship("TenantMembershipModel", back_populates="tenant", lazy="selectin")
    api_keys = relationship("APIKeyModel", back_populates="tenant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"


class TenantMembershipModel(Base):
    __tablename__ = "tenant_memberships"

    user_id: str = Column(String(36), ForeignKey("users.id"), primary_key=True)
    tenant_id: str = Column(String(36), ForeignKey("tenants.id"), primary_key=True)
    role: str = Column(
        SAEnum("owner", "admin", "member", "viewer", name="membership_role_enum"),
        nullable=False,
    )
    invited_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    accepted_at: datetime | None = Column(DateTime(timezone=True), nullable=True)

    user = relationship("UserModel", back_populates="memberships")
    tenant = relationship("TenantModel", back_populates="memberships")

    __table_args__ = (
        Index("ix_membership_tenant_user", "tenant_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<Membership user={self.user_id} tenant={self.tenant_id} role={self.role}>"


class APIKeyModel(Base):
    __tablename__ = "api_keys"

    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: str = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    key_hash: str = Column(String(128), unique=True, nullable=False, index=True)
    name: str = Column(String(255), nullable=False)
    permissions: list | None = Column(JSON, nullable=True)
    is_active: bool = Column(Boolean, default=True, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    last_used_at: datetime | None = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("TenantModel", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<APIKey {self.name} tenant={self.tenant_id}>"
