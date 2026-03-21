"""
Intelligence Engine Application Queries (Read-Side Use Cases)

Architectural Intent:
- Queries are read-only operations that never mutate state
- Each query encapsulates a single read-side use case
- Return domain entities or value objects directly (no DTOs at this layer)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from lumina.shared.domain.value_objects import BrandId
from lumina.shared.domain.errors import EntityNotFoundError

from lumina.intelligence.domain.entities import (
    AIVisibilityScore,
    Recommendation,
    RootCauseAnalysis,
)
from lumina.intelligence.domain.ports import IntelligenceRepositoryPort
from lumina.intelligence.domain.value_objects import AVSTrend


@dataclass(frozen=True)
class GetAVSQuery:
    """Retrieve the current AI Visibility Score for a brand."""

    repository: IntelligenceRepositoryPort

    async def execute(self, brand_id: BrandId) -> AIVisibilityScore:
        """Fetch the latest AVS.

        Raises:
            EntityNotFoundError: If no AVS exists for the brand.
        """
        avs = await self.repository.get_latest_avs(brand_id)
        if avs is None:
            raise EntityNotFoundError(f"No AVS found for brand {brand_id.value}")
        return avs


@dataclass(frozen=True)
class GetAVSTrendsQuery:
    """Retrieve AVS trend data for a brand over a specified period."""

    repository: IntelligenceRepositoryPort

    async def execute(
        self, brand_id: BrandId, period: str = "30d", limit: int = 30
    ) -> AVSTrend:
        """Compute AVS trends from historical data.

        Args:
            brand_id: The brand to query.
            period: The time period label (e.g. '7d', '30d', '90d').
            limit: Maximum number of historical records to retrieve.

        Returns:
            An AVSTrend value object with trend direction and change rate.

        Raises:
            EntityNotFoundError: If no historical AVS data exists.
        """
        history = await self.repository.get_avs_history(brand_id, limit=limit)
        if not history:
            raise EntityNotFoundError(
                f"No AVS history found for brand {brand_id.value}"
            )

        # Build score time series (most recent first from repository, reverse for chronological)
        chronological = list(reversed(history))
        score_pairs: list[tuple[datetime, float]] = [
            (avs.calculated_at, avs.overall.value) for avs in chronological
        ]

        # Calculate trend direction and change rate
        if len(score_pairs) < 2:
            trend_direction = "stable"
            change_rate = 0.0
        else:
            first_score = score_pairs[0][1]
            last_score = score_pairs[-1][1]
            change = last_score - first_score
            change_rate = round(change, 2)

            if abs(change) < 1.0:
                trend_direction = "stable"
            elif change > 0:
                trend_direction = "up"
            else:
                trend_direction = "down"

        return AVSTrend(
            brand_id=brand_id.value,
            period=period,
            scores=tuple(score_pairs),
            trend_direction=trend_direction,
            change_rate=change_rate,
        )


@dataclass(frozen=True)
class GetRecommendationQueueQuery:
    """Retrieve the prioritised recommendation queue for a brand."""

    repository: IntelligenceRepositoryPort

    async def execute(self, brand_id: BrandId) -> list[Recommendation]:
        """Fetch all recommendations ordered by priority_rank."""
        return await self.repository.get_recommendations(brand_id)


@dataclass(frozen=True)
class GetRootCauseQuery:
    """Retrieve the most recent root cause analysis for a brand."""

    repository: IntelligenceRepositoryPort

    async def execute(self, brand_id: BrandId) -> RootCauseAnalysis:
        """Fetch the latest RCA.

        Raises:
            EntityNotFoundError: If no RCA exists for the brand.
        """
        rca = await self.repository.get_latest_root_cause_analysis(brand_id)
        if rca is None:
            raise EntityNotFoundError(
                f"No root cause analysis found for brand {brand_id.value}"
            )
        return rca
