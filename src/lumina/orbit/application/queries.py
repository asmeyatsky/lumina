"""
ORBIT Application Queries (Read-Side Use Cases)

Architectural Intent:
- Queries are read-only operations that never mutate state
- Each query encapsulates a single read-side use case
- Return domain entities or value objects directly (no DTOs at this layer)
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.shared.domain.errors import EntityNotFoundError

from lumina.orbit.domain.entities import AgentInsight, AgentSession
from lumina.orbit.domain.ports import OrbitRepositoryPort
from lumina.orbit.domain.services import CycleMetricsService, InsightAggregationService


@dataclass(frozen=True)
class GetSessionQuery:
    """Retrieve an agent session by ID."""

    repository: OrbitRepositoryPort

    async def execute(self, session_id: str) -> AgentSession:
        session = await self.repository.get_session(session_id)
        if session is None:
            raise EntityNotFoundError(f"Session {session_id} not found")
        return session


@dataclass(frozen=True)
class GetSessionHistoryQuery:
    """Retrieve session history for a brand."""

    repository: OrbitRepositoryPort

    async def execute(
        self, brand_id: str, limit: int = 20
    ) -> list[AgentSession]:
        return await self.repository.get_sessions_for_brand(brand_id, limit=limit)


@dataclass(frozen=True)
class GetActiveSessionQuery:
    """Retrieve the currently active session for a brand, if any."""

    repository: OrbitRepositoryPort

    async def execute(self, brand_id: str) -> AgentSession | None:
        return await self.repository.get_active_session(brand_id)


@dataclass(frozen=True)
class GetInsightsQuery:
    """Retrieve and rank all insights from a session."""

    repository: OrbitRepositoryPort

    async def execute(self, session_id: str) -> list[AgentInsight]:
        session = await self.repository.get_session(session_id)
        if session is None:
            raise EntityNotFoundError(f"Session {session_id} not found")

        return InsightAggregationService.rank_insights(session.all_insights)


@dataclass(frozen=True)
class GetSessionMetricsQuery:
    """Retrieve aggregate metrics for a session."""

    repository: OrbitRepositoryPort

    async def execute(self, session_id: str) -> dict[str, object]:
        """Return a dictionary of session metrics.

        Keys:
            session_id, brand_id, state, cycle_count, total_actions,
            modules_touched, insight_count, critical_insights,
            average_cycle_success_rate
        """
        session = await self.repository.get_session(session_id)
        if session is None:
            raise EntityNotFoundError(f"Session {session_id} not found")

        # Per-cycle success rates
        cycle_rates = [
            CycleMetricsService.success_rate(c)
            for c in session.cycles
            if c.completed_at is not None
        ]
        avg_success = (
            sum(cycle_rates) / len(cycle_rates) if cycle_rates else 1.0
        )

        all_insights = session.all_insights

        return {
            "session_id": session.id,
            "brand_id": session.brand_id,
            "state": session.state.value,
            "cycle_count": session.cycle_count,
            "total_actions": session.total_actions,
            "modules_touched": sorted(CycleMetricsService.modules_touched(session)),
            "insight_count": len(all_insights),
            "critical_insights": InsightAggregationService.critical_count(all_insights),
            "average_cycle_success_rate": round(avg_success, 3),
        }
