"""
GRAPH Domain Events

Architectural Intent:
- Capture every meaningful state change in the Entity Intelligence context
- Events are immutable records published after aggregate persistence
- Other bounded contexts (PULSE, SIGNAL) subscribe to these events
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class EntityProfileCreated(DomainEvent):
    """Raised when a new entity profile is created for a brand."""

    brand_id: str = ""
    profile_name: str = ""


@dataclass(frozen=True)
class EntityDimensionUpdated(DomainEvent):
    """Raised when a dimension's data or completeness changes."""

    brand_id: str = ""
    dimension_type: str = ""
    old_completeness: float = 0.0
    new_completeness: float = 0.0


@dataclass(frozen=True)
class KnowledgeGapIdentified(DomainEvent):
    """Raised when gap analysis discovers a missing or weak dimension."""

    brand_id: str = ""
    dimension_type: str = ""
    severity: str = ""
    description: str = ""


@dataclass(frozen=True)
class EntityHealthChanged(DomainEvent):
    """Raised when the overall entity health score changes materially."""

    brand_id: str = ""
    old_score: float = 0.0
    new_score: float = 0.0
