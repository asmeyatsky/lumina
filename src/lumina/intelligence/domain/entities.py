"""
Intelligence Engine Domain Entities

Architectural Intent:
- Frozen dataclasses enforce immutability (DDD aggregate invariant protection)
- Domain events are collected as tuples (immutable collections)
- All mutations produce new instances via dataclasses.replace()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.events import DomainEvent
from lumina.shared.domain.value_objects import Score

from lumina.intelligence.domain.value_objects import EffortLevel


@dataclass(frozen=True)
class ScoreComponent:
    """A single module's contribution to the overall AVS.

    Attributes:
        module_name: One of 'pulse', 'graph', 'beam', 'signal'.
        score: The module's normalised score (0-100).
        weight: The weight applied to this module in the AVS calculation.
        raw_metrics: Underlying metrics stored as an immutable tuple of key-value pairs.
    """

    module_name: str
    score: Score
    weight: float
    raw_metrics: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        valid_modules = ("pulse", "graph", "beam", "signal")
        if self.module_name not in valid_modules:
            raise ValueError(
                f"module_name must be one of {valid_modules}, got '{self.module_name}'"
            )
        if not (0.0 <= self.weight <= 1.0):
            raise ValueError(f"weight must be between 0 and 1, got {self.weight}")

    @property
    def weighted_score(self) -> float:
        """Return the score multiplied by its weight."""
        return self.score.value * self.weight


@dataclass(frozen=True)
class AIVisibilityScore:
    """Aggregate root for the AI Visibility Score.

    The AVS is the central metric that combines scores from all four LUMINA modules
    (PULSE, GRAPH, BEAM, SIGNAL) into a single 0-100 score.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    brand_id: str = ""
    overall: Score = field(default_factory=lambda: Score(0.0))
    components: tuple[ScoreComponent, ...] = ()
    calculated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    previous_score: Score | None = None
    domain_events: tuple[DomainEvent, ...] = ()

    def calculate_delta(self) -> float:
        """Calculate the change from the previous score.

        Returns:
            The difference (current - previous). Returns 0.0 if there is no previous score.
        """
        if self.previous_score is None:
            return 0.0
        return self.overall.value - self.previous_score.value


@dataclass(frozen=True)
class Recommendation:
    """A prioritised action recommendation derived from AVS analysis.

    Each recommendation links back to a specific module and entity,
    providing actionable guidance to improve the brand's AI visibility.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    brand_id: str = ""
    source_module: str = ""
    action_description: str = ""
    expected_avs_impact: Score = field(default_factory=lambda: Score(0.0))
    effort_level: EffortLevel = EffortLevel.MEDIUM
    priority_rank: int = 0
    linked_entity_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        valid_modules = ("pulse", "graph", "beam", "signal", "intelligence")
        if self.source_module and self.source_module not in valid_modules:
            raise ValueError(
                f"source_module must be one of {valid_modules}, got '{self.source_module}'"
            )


@dataclass(frozen=True)
class RootCause:
    """A single identified root cause contributing to an AVS change."""

    factor: str
    module: str
    evidence: str
    contribution_weight: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.contribution_weight <= 1.0):
            raise ValueError(
                f"contribution_weight must be between 0 and 1, got {self.contribution_weight}"
            )


@dataclass(frozen=True)
class RootCauseAnalysis:
    """Aggregate for root cause analysis of AVS changes.

    Triggered when a significant AVS change is detected, this entity
    captures the causes, evidence, and recommended corrective actions.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    brand_id: str = ""
    trigger: str = ""
    causes: tuple[RootCause, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
