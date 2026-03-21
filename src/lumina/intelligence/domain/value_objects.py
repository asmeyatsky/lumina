"""
Intelligence Engine Value Objects

Architectural Intent:
- Immutable, identity-less domain concepts specific to the Intelligence Engine
- Enforce invariants at construction time
- Frozen dataclasses and enums only
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EffortLevel(str, Enum):
    """Effort required to implement a recommendation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def numeric(self) -> int:
        """Return numeric value for effort-based calculations (lower is easier)."""
        return {"low": 1, "medium": 2, "high": 3}[self.value]


@dataclass(frozen=True)
class AVSWeights:
    """Default weights for the AI Visibility Score calculation.

    The four weights correspond to the four LUMINA modules and must sum to 1.0.
    """

    citation_frequency: float = 0.30   # PULSE weight
    entity_depth: float = 0.25         # GRAPH weight
    content_geo: float = 0.25          # BEAM weight
    distribution_coverage: float = 0.20  # SIGNAL weight

    def __post_init__(self) -> None:
        total = (
            self.citation_frequency
            + self.entity_depth
            + self.content_geo
            + self.distribution_coverage
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"AVSWeights must sum to 1.0, got {total}")
        for name, val in [
            ("citation_frequency", self.citation_frequency),
            ("entity_depth", self.entity_depth),
            ("content_geo", self.content_geo),
            ("distribution_coverage", self.distribution_coverage),
        ]:
            if val < 0.0 or val > 1.0:
                raise ValueError(f"{name} must be between 0 and 1, got {val}")


@dataclass(frozen=True)
class AVSTrend:
    """Trend data for AI Visibility Score over a time period."""

    brand_id: str
    period: str
    scores: tuple[tuple[datetime, float], ...]
    trend_direction: str  # "up", "down", "stable"
    change_rate: float

    def __post_init__(self) -> None:
        if self.trend_direction not in ("up", "down", "stable"):
            raise ValueError(
                f"trend_direction must be 'up', 'down', or 'stable', got '{self.trend_direction}'"
            )


@dataclass(frozen=True)
class ImpactEstimate:
    """Estimated impact of a recommended action on the AVS."""

    action: str
    estimated_avs_change: float
    confidence: float
    time_to_effect_days: int

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")
        if self.time_to_effect_days < 0:
            raise ValueError(
                f"time_to_effect_days must be non-negative, got {self.time_to_effect_days}"
            )
