"""
Event Bus Port — Interface for domain event publishing and subscription

Architectural Intent:
- Cross-bounded-context communication via domain events
- Application layer publishes events after use case completion
- Infrastructure provides concrete implementation (in-memory, MCP, message broker)
"""

from __future__ import annotations

from collections.abc import Callable, Awaitable
from typing import Protocol

from lumina.shared.domain.events import DomainEvent


class EventBusPort(Protocol):
    """Port for publishing and subscribing to domain events."""

    async def publish(self, events: list[DomainEvent]) -> None:
        """Publish a batch of domain events."""
        ...

    async def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        """Subscribe a handler to a specific event type."""
        ...
