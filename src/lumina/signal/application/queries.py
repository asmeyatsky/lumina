"""
SIGNAL Application Queries — Read-side use cases

Architectural Intent:
- Queries are read-only; they never mutate domain state
- Each query returns a specific view model or domain value object
- Queries depend on repository ports, never on infrastructure
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.signal.domain.entities import CitationSurface, DistributionPlan, PRBrief
from lumina.signal.domain.ports import SignalRepositoryPort
from lumina.signal.domain.services import CoverageCalculationService
from lumina.signal.domain.value_objects import (
    ActionStatus,
    DistributionCoverage,
    PresenceStatus,
)


@dataclass(frozen=True)
class PlanStatusView:
    """Read-only view of a distribution plan's status."""

    plan_id: str
    brand_id: str
    total_actions: int
    completed_actions: int
    failed_actions: int
    in_progress_actions: int
    coverage_score: float


@dataclass(frozen=True)
class SurfaceGapView:
    """Read-only view of a surface where the brand is absent."""

    surface_id: str
    surface_name: str
    category: str
    estimated_llm_weight: float


@dataclass(frozen=True)
class GetDistributionCoverageQuery:
    """Returns current distribution coverage metrics for a brand."""

    repository: SignalRepositoryPort
    coverage_service: CoverageCalculationService

    async def execute(self, brand_id: str) -> DistributionCoverage | None:
        """Compute aggregate coverage across all plans for a brand.

        Returns the coverage of the most recent plan, or None if no plans exist.
        """
        plans = await self.repository.list_plans_for_brand(brand_id)
        if not plans:
            return None

        # Use the most recent plan (last in list)
        latest_plan = max(plans, key=lambda p: p.created_at)
        return self.coverage_service.calculate_coverage(latest_plan)


@dataclass(frozen=True)
class GetPlanStatusQuery:
    """Returns the status of a specific distribution plan."""

    repository: SignalRepositoryPort

    async def execute(self, plan_id: str) -> PlanStatusView | None:
        """Retrieve plan status with action counts.

        Returns None if the plan does not exist.
        """
        plan = await self.repository.get_plan(plan_id)
        if plan is None:
            return None

        completed = sum(1 for a in plan.actions if a.status == ActionStatus.COMPLETED)
        failed = sum(1 for a in plan.actions if a.status == ActionStatus.FAILED)
        in_progress = sum(1 for a in plan.actions if a.status == ActionStatus.IN_PROGRESS)

        return PlanStatusView(
            plan_id=plan.id,
            brand_id=plan.brand_id.value,
            total_actions=len(plan.actions),
            completed_actions=completed,
            failed_actions=failed,
            in_progress_actions=in_progress,
            coverage_score=plan.coverage_score.value,
        )


@dataclass(frozen=True)
class GetSurfaceGapsQuery:
    """Returns surfaces where the brand is absent."""

    repository: SignalRepositoryPort

    async def execute(self, brand_id: str) -> list[SurfaceGapView]:
        """Identify all surfaces where the brand has no presence.

        Returns a list of SurfaceGapView sorted by estimated LLM weight descending.
        """
        surfaces = await self.repository.get_surfaces_for_brand(brand_id)

        gaps: list[SurfaceGapView] = []
        for surface in surfaces:
            if surface.brand_presence in (PresenceStatus.ABSENT, PresenceStatus.UNKNOWN):
                gaps.append(
                    SurfaceGapView(
                        surface_id=surface.id,
                        surface_name=surface.name,
                        category=surface.category.value,
                        estimated_llm_weight=surface.estimated_llm_weight.value,
                    )
                )

        return sorted(gaps, key=lambda g: g.estimated_llm_weight, reverse=True)


@dataclass(frozen=True)
class GetPRBriefsQuery:
    """Returns generated PR briefs for a brand."""

    repository: SignalRepositoryPort

    async def execute(self, brand_id: str) -> list[PRBrief]:
        """Retrieve all PR briefs for the given brand, ordered by creation time.

        Returns an empty list if no briefs exist.
        """
        briefs = await self.repository.get_pr_briefs_for_brand(brand_id)
        return sorted(briefs, key=lambda b: b.created_at, reverse=True)
