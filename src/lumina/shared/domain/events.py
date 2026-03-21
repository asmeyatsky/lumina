"""
Base Domain Event Infrastructure

Architectural Intent:
- All domain state changes are captured as immutable events
- Events are collected on aggregates and dispatched after persistence
- Cross-bounded-context communication uses events exclusively
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events in LUMINA."""

    aggregate_id: str
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_type(self) -> str:
        return type(self).__name__
