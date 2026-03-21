"""
GRAPH Application Queries (Read-side Use Cases)

Architectural Intent:
- Read-only use cases that never mutate state
- Queries depend on domain ports and services for projection logic
- Each query returns a well-defined read model
"""

from __future__ import annotations

from lumina.shared.domain.errors import EntityNotFoundError

from lumina.graph.domain.entities import (
    EntityProfile,
    KnowledgeGap,
    CompetitorEntityComparison,
)
from lumina.graph.domain.value_objects import EntityHealth, GapSeverity
from lumina.graph.domain.ports import GraphRepositoryPort
from lumina.graph.domain.services import EntityScoringService, CompetitorBenchmarkService


# ---------------------------------------------------------------------------
# Severity ordering for gap prioritisation
# ---------------------------------------------------------------------------
_SEVERITY_ORDER = {
    GapSeverity.CRITICAL: 0,
    GapSeverity.HIGH: 1,
    GapSeverity.MEDIUM: 2,
    GapSeverity.LOW: 3,
}


class GetEntityProfileQuery:
    """Returns the full entity profile with all dimensions."""

    def __init__(self, repository: GraphRepositoryPort) -> None:
        self._repository = repository

    async def execute(self, *, profile_id: str) -> EntityProfile:
        profile = await self._repository.get_profile(profile_id)
        if profile is None:
            raise EntityNotFoundError(f"Profile {profile_id} not found")
        return profile


class GetKnowledgeGapsQuery:
    """Returns prioritised gaps for a brand, ordered by severity."""

    def __init__(self, repository: GraphRepositoryPort) -> None:
        self._repository = repository

    async def execute(self, *, brand_id: str) -> list[KnowledgeGap]:
        gaps = await self._repository.get_gaps_for_brand(brand_id)
        return sorted(gaps, key=lambda g: _SEVERITY_ORDER.get(g.severity, 99))


class GetEntityHealthQuery:
    """Returns current entity health metrics for a profile."""

    def __init__(
        self,
        repository: GraphRepositoryPort,
        scoring_service: EntityScoringService | None = None,
    ) -> None:
        self._repository = repository
        self._scoring = scoring_service or EntityScoringService()

    async def execute(self, *, profile_id: str) -> EntityHealth:
        profile = await self._repository.get_profile(profile_id)
        if profile is None:
            raise EntityNotFoundError(f"Profile {profile_id} not found")
        return self._scoring.calculate_overall_health(profile)


class CompareCompetitorsQuery:
    """Returns side-by-side entity comparisons between a brand and its competitors."""

    def __init__(
        self,
        repository: GraphRepositoryPort,
        benchmark_service: CompetitorBenchmarkService | None = None,
    ) -> None:
        self._repository = repository
        self._benchmark = benchmark_service or CompetitorBenchmarkService()

    async def execute(
        self,
        *,
        brand_id: str,
        competitor_brand_ids: list[str],
    ) -> list[CompetitorEntityComparison]:
        brand_profiles = await self._repository.list_profiles_for_brand(brand_id)
        if not brand_profiles:
            raise EntityNotFoundError(f"No profiles found for brand {brand_id}")

        brand_profile = brand_profiles[0]

        competitor_profiles = []
        for comp_id in competitor_brand_ids:
            comp_profiles = await self._repository.list_profiles_for_brand(comp_id)
            if comp_profiles:
                competitor_profiles.append(comp_profiles[0])

        return self._benchmark.compare_entities(brand_profile, competitor_profiles)
