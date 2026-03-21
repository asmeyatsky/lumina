"""
PULSE Application Queries — Read-side use cases

Architectural Intent:
- Each query class encapsulates a single read-side use case
- Queries return domain objects or value objects, never raw dicts
- Queries operate through the repository port, never touching infra directly
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from lumina.shared.domain.value_objects import BrandId, Percentage

from lumina.pulse.domain.entities import CitationResult, MonitoringRun
from lumina.pulse.domain.ports import PulseRepositoryPort
from lumina.pulse.domain.services import BenchmarkService
from lumina.pulse.domain.value_objects import (
    CitationPosition,
    CitationTrend,
    CompetitorBenchmark,
    Sentiment,
    ShareOfVoice,
)


class GetCitationTrendsQuery:
    """Returns citation trends over time for a brand.

    Aggregates data from completed monitoring runs within the given
    time window and computes trend metrics.
    """

    def __init__(self, repository: PulseRepositoryPort) -> None:
        self._repository = repository

    async def execute(
        self,
        brand_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> CitationTrend:
        """Compute citation trend data for a brand over a time period.

        Args:
            brand_id: The brand to analyze.
            period_start: Start of the analysis window.
            period_end: End of the analysis window.

        Returns:
            CitationTrend with frequency, average position, and sentiment breakdown.
        """
        runs = await self._repository.list_runs_for_brand(brand_id)

        # Filter to completed runs within the time window
        relevant_runs = [
            run for run in runs
            if run.status.value == "completed"
            and run.started_at >= period_start
            and (run.completed_at is not None and run.completed_at <= period_end)
        ]

        total_results = 0
        total_cited = 0
        position_sum = 0.0
        position_count = 0
        sentiment_counts: dict[str, int] = {
            Sentiment.POSITIVE.value: 0,
            Sentiment.NEUTRAL.value: 0,
            Sentiment.NEGATIVE.value: 0,
        }

        for run in relevant_runs:
            for result in run.results:
                total_results += 1
                has_citation = False
                for citation in result.citations:
                    if citation.position != CitationPosition.NOT_CITED:
                        has_citation = True
                        position_sum += citation.position.value
                        position_count += 1

                if has_citation:
                    total_cited += 1
                    sentiment_counts[result.sentiment.value] += 1

        # Calculate metrics
        frequency = (total_cited / total_results * 100.0) if total_results > 0 else 0.0
        avg_position = (position_sum / position_count) if position_count > 0 else 0.0

        total_sentiments = sum(sentiment_counts.values())
        sentiment_breakdown: dict[str, float] = {}
        if total_sentiments > 0:
            for key, count in sentiment_counts.items():
                sentiment_breakdown[key] = round(count / total_sentiments * 100.0, 2)
        else:
            sentiment_breakdown = {k: 0.0 for k in sentiment_counts}

        return CitationTrend(
            brand_id=BrandId(value=brand_id),
            period_start=period_start,
            period_end=period_end,
            citation_frequency=Percentage(value=min(round(frequency, 2), 100.0)),
            avg_position=round(avg_position, 2),
            sentiment_breakdown=sentiment_breakdown,
        )


class GetShareOfVoiceQuery:
    """Returns current share of voice vs competitors for a brand.

    Computes competitive share of voice from the most recent
    monitoring run that contains citation data.
    """

    def __init__(self, repository: PulseRepositoryPort) -> None:
        self._repository = repository
        self._benchmark_service = BenchmarkService()

    async def execute(
        self,
        brand_id: str,
        competitor_brand_ids: list[str],
    ) -> CompetitorBenchmark:
        """Compute share of voice for a brand vs its competitors.

        Uses the most recent completed runs for each brand to build
        the competitive benchmark.

        Args:
            brand_id: The primary brand.
            competitor_brand_ids: List of competitor brand IDs.

        Returns:
            CompetitorBenchmark with share of voice data.
        """
        all_brand_ids = [brand_id] + competitor_brand_ids
        results_by_brand: dict[str, list] = {}

        for bid in all_brand_ids:
            runs = await self._repository.list_runs_for_brand(bid, limit=5)
            completed = [r for r in runs if r.status.value == "completed"]

            citations = []
            for run in completed:
                for result in run.results:
                    citations.extend(result.citations)

            results_by_brand[bid] = citations

        return self._benchmark_service.calculate_share_of_voice(results_by_brand)


class GetMonitoringRunQuery:
    """Returns details of a specific monitoring run."""

    def __init__(self, repository: PulseRepositoryPort) -> None:
        self._repository = repository

    async def execute(self, run_id: str) -> Optional[MonitoringRun]:
        """Retrieve a monitoring run by its ID.

        Args:
            run_id: The unique identifier of the run.

        Returns:
            The MonitoringRun if found, None otherwise.
        """
        return await self._repository.get_run(run_id)


class GetLatestResultsQuery:
    """Returns the most recent monitoring results for a brand.

    Provides a quick view of the latest citation data without
    needing to know the specific run ID.
    """

    def __init__(self, repository: PulseRepositoryPort) -> None:
        self._repository = repository

    async def execute(
        self,
        brand_id: str,
        limit: int = 1,
    ) -> list[MonitoringRun]:
        """Get the most recent completed monitoring runs for a brand.

        Args:
            brand_id: The brand to query.
            limit: Maximum number of runs to return.

        Returns:
            List of most recent completed MonitoringRun objects.
        """
        runs = await self._repository.list_runs_for_brand(brand_id, limit=limit * 3)
        completed = [r for r in runs if r.status.value == "completed"]
        return completed[:limit]
