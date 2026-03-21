"""
PULSE Value Objects

Architectural Intent:
- Immutable, identity-less domain concepts specific to the PULSE bounded context
- Enforce invariants at construction time
- Enums model fixed classification schemes for citation analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from lumina.shared.domain.value_objects import BrandId, Percentage


class CitationPosition(Enum):
    """Ordinal position of a brand citation within an AI response.

    Ordering reflects prominence — FIRST is the most visible position.
    """

    FIRST = 1
    SECOND = 2
    THIRD = 3
    MENTIONED = 4
    NOT_CITED = 5

    def __lt__(self, other: CitationPosition) -> bool:
        return self.value < other.value

    def __le__(self, other: CitationPosition) -> bool:
        return self.value <= other.value

    def __gt__(self, other: CitationPosition) -> bool:
        return self.value > other.value

    def __ge__(self, other: CitationPosition) -> bool:
        return self.value >= other.value


class Sentiment(str, Enum):
    """Sentiment classification for a citation context."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class RunStatus(str, Enum):
    """Lifecycle status of a monitoring run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ShareOfVoice:
    """Share of voice metric for a single brand within a citation set.

    Represents how often a brand is cited relative to total citations.
    """

    brand_id: BrandId
    citation_count: int
    total_citations: int
    percentage: Percentage

    def __post_init__(self) -> None:
        if self.citation_count < 0:
            raise ValueError("citation_count must be non-negative")
        if self.total_citations < 0:
            raise ValueError("total_citations must be non-negative")
        if self.total_citations > 0 and self.citation_count > self.total_citations:
            raise ValueError("citation_count cannot exceed total_citations")


@dataclass(frozen=True)
class CitationTrend:
    """Trend data for a brand's citation performance over a time period."""

    brand_id: BrandId
    period_start: datetime
    period_end: datetime
    citation_frequency: Percentage
    avg_position: float
    sentiment_breakdown: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.period_start >= self.period_end:
            raise ValueError("period_start must precede period_end")
        if self.avg_position < 0.0:
            raise ValueError("avg_position must be non-negative")


@dataclass(frozen=True)
class CompetitorBenchmark:
    """Competitive benchmark comparing share of voice across brands."""

    brand_id: BrandId
    competitor_brand_ids: tuple[BrandId, ...]
    share_of_voice_map: dict[str, ShareOfVoice] = field(default_factory=dict)
