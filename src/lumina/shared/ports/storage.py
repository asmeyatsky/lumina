"""
Storage Port — Generic repository interface

Architectural Intent:
- Base protocol for all repository ports
- Concrete repositories live in infrastructure layer
- Domain layer depends only on this interface
"""

from __future__ import annotations

from typing import Protocol, TypeVar, Generic

T = TypeVar("T")


class RepositoryPort(Protocol[T]):
    """Generic repository port for aggregate persistence."""

    async def get_by_id(self, id: str) -> T | None:
        """Retrieve an aggregate by its identifier."""
        ...

    async def save(self, entity: T) -> None:
        """Persist an aggregate (insert or update)."""
        ...

    async def delete(self, id: str) -> None:
        """Remove an aggregate by its identifier."""
        ...
