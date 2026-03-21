"""
Agency Domain Value Objects

Architectural Intent:
- Immutable, identity-less domain concepts specific to the Agency bounded context
- Enforce invariants at construction time
- Enums for plan tiers and report types
- Frozen dataclasses for composite value objects
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lumina.shared.domain.value_objects import Score


class AgencyPlanTier(str, Enum):
    """Plan tiers controlling the maximum number of managed client brands."""

    STARTER = "starter"           # up to 5 clients
    PROFESSIONAL = "professional"  # up to 25 clients
    UNLIMITED = "unlimited"        # no limit

    @property
    def max_clients(self) -> int | None:
        """Return the maximum number of clients allowed, or None for unlimited."""
        limits = {
            "starter": 5,
            "professional": 25,
            "unlimited": None,
        }
        return limits[self.value]


class ReportType(str, Enum):
    """Types of reports that can be generated for client brands."""

    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_REVIEW = "monthly_review"
    QUARTERLY_ANALYSIS = "quarterly_analysis"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ClientOverview:
    """Summary view of a single client brand within an agency portfolio."""

    brand_id: str
    brand_name: str
    avs_score: Score
    avs_trend: float
    citation_count: int
    top_recommendation: str


@dataclass(frozen=True)
class PortfolioSummary:
    """Aggregated summary of an agency's entire client portfolio."""

    agency_id: str
    total_clients: int
    avg_avs: Score
    clients_improving: int
    clients_declining: int
    top_performer: str
    needs_attention: list[str]
