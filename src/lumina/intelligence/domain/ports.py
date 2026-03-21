"""
Intelligence Engine Ports (Protocol Interfaces)

Architectural Intent:
- Ports define the contracts the domain requires from the outside world
- Protocol-based (structural subtyping) — no inheritance required
- Infrastructure layer provides concrete adapters
"""

from __future__ import annotations

from typing import Protocol

from lumina.shared.domain.value_objects import BrandId, Score

from lumina.intelligence.domain.entities import (
    AIVisibilityScore,
    Recommendation,
    RootCauseAnalysis,
)
from lumina.intelligence.domain.value_objects import AVSTrend


class IntelligenceRepositoryPort(Protocol):
    """Port for persisting and retrieving Intelligence Engine aggregates."""

    async def save_avs(self, avs: AIVisibilityScore) -> None:
        """Persist an AI Visibility Score."""
        ...

    async def get_latest_avs(self, brand_id: BrandId) -> AIVisibilityScore | None:
        """Retrieve the most recent AVS for a brand."""
        ...

    async def get_avs_history(
        self, brand_id: BrandId, limit: int = 30
    ) -> list[AIVisibilityScore]:
        """Retrieve historical AVS records for a brand, most recent first."""
        ...

    async def save_recommendation(self, recommendation: Recommendation) -> None:
        """Persist a recommendation."""
        ...

    async def get_recommendations(self, brand_id: BrandId) -> list[Recommendation]:
        """Retrieve all recommendations for a brand, ordered by priority_rank."""
        ...

    async def save_root_cause_analysis(self, rca: RootCauseAnalysis) -> None:
        """Persist a root cause analysis."""
        ...

    async def get_latest_root_cause_analysis(
        self, brand_id: BrandId
    ) -> RootCauseAnalysis | None:
        """Retrieve the most recent root cause analysis for a brand."""
        ...


class ModuleScorePort(Protocol):
    """Port for retrieving scores from the four LUMINA modules.

    Each method fetches the current normalised score from its respective
    bounded context. Implementations may call MCP servers, APIs, or
    in-process adapters.
    """

    async def get_pulse_score(self, brand_id: BrandId) -> Score:
        """Get the current PULSE (citation monitoring) score for a brand."""
        ...

    async def get_graph_score(self, brand_id: BrandId) -> Score:
        """Get the current GRAPH (entity intelligence) score for a brand."""
        ...

    async def get_beam_score(self, brand_id: BrandId) -> Score:
        """Get the current BEAM (content optimisation) score for a brand."""
        ...

    async def get_signal_score(self, brand_id: BrandId) -> Score:
        """Get the current SIGNAL (distribution) score for a brand."""
        ...
