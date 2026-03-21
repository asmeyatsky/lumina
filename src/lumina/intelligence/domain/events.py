"""
Intelligence Engine Domain Events

Architectural Intent:
- Immutable event records capturing state transitions in the Intelligence bounded context
- Published after use-case completion for cross-context communication
- All extend the shared DomainEvent base class
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class AVSCalculated(DomainEvent):
    """Emitted when a new AI Visibility Score is calculated for a brand."""

    brand_id: str = ""
    new_score: float = 0.0
    previous_score: float | None = None
    delta: float = 0.0


@dataclass(frozen=True)
class AVSDropDetected(DomainEvent):
    """Emitted when the AVS drops by more than a configured threshold."""

    brand_id: str = ""
    drop_amount: float = 0.0
    threshold: float = 0.0


@dataclass(frozen=True)
class RecommendationGenerated(DomainEvent):
    """Emitted when a new recommendation is generated for a brand."""

    brand_id: str = ""
    source_module: str = ""
    action: str = ""
    expected_impact: float = 0.0


@dataclass(frozen=True)
class RootCauseAnalysisCompleted(DomainEvent):
    """Emitted when a root cause analysis finishes for a brand."""

    brand_id: str = ""
    trigger: str = ""
    cause_count: int = 0
