"""
LUMINA Dependency Injection Container (Composition Root)

Architectural Intent:
- Single place where all ports are wired to their infrastructure adapters
- Factory methods produce fully-configured use case instances
- Configurable via environment variables for different deployment environments
- No domain or application code imports infrastructure — only this container does
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from lumina.shared.domain.events import DomainEvent
from lumina.shared.domain.value_objects import BrandId, Score
from lumina.shared.ports.event_bus import EventBusPort

from lumina.intelligence.application.commands import (
    CalculateAVSCommand,
    GenerateRecommendationsCommand,
    RunRootCauseAnalysisCommand,
)
from lumina.intelligence.application.queries import (
    GetAVSQuery,
    GetAVSTrendsQuery,
    GetRecommendationQueueQuery,
    GetRootCauseQuery,
)
from lumina.intelligence.domain.entities import (
    AIVisibilityScore,
    Recommendation,
    RootCauseAnalysis,
)
from lumina.intelligence.domain.ports import IntelligenceRepositoryPort, ModuleScorePort
from lumina.intelligence.domain.value_objects import AVSWeights


# =============================================================================
# In-Memory Adapters (default for development / testing)
# =============================================================================


class InMemoryEventBus:
    """In-memory event bus for development and testing."""

    def __init__(self) -> None:
        self._handlers: dict[type, list] = {}
        self._published: list[DomainEvent] = []

    async def publish(self, events: list[DomainEvent]) -> None:
        for event in events:
            self._published.append(event)
            handlers = self._handlers.get(type(event), [])
            for handler in handlers:
                await handler(event)

    async def subscribe(self, event_type: type[DomainEvent], handler: Any) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    @property
    def published_events(self) -> list[DomainEvent]:
        return list(self._published)


class InMemoryIntelligenceRepository:
    """In-memory repository for Intelligence Engine aggregates."""

    def __init__(self) -> None:
        self._avs_store: dict[str, list[AIVisibilityScore]] = {}
        self._recommendations: dict[str, list[Recommendation]] = {}
        self._rca_store: dict[str, list[RootCauseAnalysis]] = {}

    async def save_avs(self, avs: AIVisibilityScore) -> None:
        self._avs_store.setdefault(avs.brand_id, []).append(avs)

    async def get_latest_avs(self, brand_id: BrandId) -> AIVisibilityScore | None:
        records = self._avs_store.get(brand_id.value, [])
        if not records:
            return None
        return records[-1]

    async def get_avs_history(
        self, brand_id: BrandId, limit: int = 30
    ) -> list[AIVisibilityScore]:
        records = self._avs_store.get(brand_id.value, [])
        # Return most recent first, limited
        return list(reversed(records[-limit:]))

    async def save_recommendation(self, recommendation: Recommendation) -> None:
        self._recommendations.setdefault(recommendation.brand_id, []).append(
            recommendation
        )

    async def get_recommendations(self, brand_id: BrandId) -> list[Recommendation]:
        recs = self._recommendations.get(brand_id.value, [])
        return sorted(recs, key=lambda r: r.priority_rank)

    async def save_root_cause_analysis(self, rca: RootCauseAnalysis) -> None:
        self._rca_store.setdefault(rca.brand_id, []).append(rca)

    async def get_latest_root_cause_analysis(
        self, brand_id: BrandId
    ) -> RootCauseAnalysis | None:
        records = self._rca_store.get(brand_id.value, [])
        if not records:
            return None
        return records[-1]


class InMemoryModuleScores:
    """In-memory module score provider for development and testing.

    Returns configurable default scores. In production this would call
    each module's MCP server or internal API.
    """

    def __init__(
        self,
        default_pulse: float = 50.0,
        default_graph: float = 50.0,
        default_beam: float = 50.0,
        default_signal: float = 50.0,
    ) -> None:
        self._scores: dict[str, dict[str, float]] = {}
        self._defaults = {
            "pulse": default_pulse,
            "graph": default_graph,
            "beam": default_beam,
            "signal": default_signal,
        }

    def set_score(self, brand_id: str, module: str, value: float) -> None:
        """Set a specific score for testing."""
        self._scores.setdefault(brand_id, {})[module] = value

    async def get_pulse_score(self, brand_id: BrandId) -> Score:
        val = self._scores.get(brand_id.value, {}).get(
            "pulse", self._defaults["pulse"]
        )
        return Score(val)

    async def get_graph_score(self, brand_id: BrandId) -> Score:
        val = self._scores.get(brand_id.value, {}).get(
            "graph", self._defaults["graph"]
        )
        return Score(val)

    async def get_beam_score(self, brand_id: BrandId) -> Score:
        val = self._scores.get(brand_id.value, {}).get(
            "beam", self._defaults["beam"]
        )
        return Score(val)

    async def get_signal_score(self, brand_id: BrandId) -> Score:
        val = self._scores.get(brand_id.value, {}).get(
            "signal", self._defaults["signal"]
        )
        return Score(val)


# =============================================================================
# Container
# =============================================================================


class Container:
    """Dependency injection container — the composition root for LUMINA.

    Wires all ports to concrete adapters and provides factory methods
    for application-layer use cases. Configurable via environment variables.
    """

    def __init__(self) -> None:
        # Read configuration from environment
        self._env = os.environ.get("LUMINA_ENV", "development")

        # Weights configuration
        self._weights = AVSWeights(
            citation_frequency=float(os.environ.get("LUMINA_WEIGHT_PULSE", "0.30")),
            entity_depth=float(os.environ.get("LUMINA_WEIGHT_GRAPH", "0.25")),
            content_geo=float(os.environ.get("LUMINA_WEIGHT_BEAM", "0.25")),
            distribution_coverage=float(os.environ.get("LUMINA_WEIGHT_SIGNAL", "0.20")),
        )

        # Wire adapters
        self._event_bus = InMemoryEventBus()
        self._intelligence_repository = InMemoryIntelligenceRepository()
        self._module_scores = InMemoryModuleScores(
            default_pulse=float(os.environ.get("LUMINA_DEFAULT_PULSE_SCORE", "50.0")),
            default_graph=float(os.environ.get("LUMINA_DEFAULT_GRAPH_SCORE", "50.0")),
            default_beam=float(os.environ.get("LUMINA_DEFAULT_BEAM_SCORE", "50.0")),
            default_signal=float(os.environ.get("LUMINA_DEFAULT_SIGNAL_SCORE", "50.0")),
        )

    # --- Port accessors ---

    @property
    def event_bus(self) -> InMemoryEventBus:
        return self._event_bus

    @property
    def intelligence_repository(self) -> InMemoryIntelligenceRepository:
        return self._intelligence_repository

    @property
    def module_scores(self) -> InMemoryModuleScores:
        return self._module_scores

    # --- Command factories ---

    def calculate_avs_command(self) -> CalculateAVSCommand:
        return CalculateAVSCommand(
            repository=self._intelligence_repository,
            module_scores=self._module_scores,
            event_bus=self._event_bus,
            weights=self._weights,
        )

    def run_root_cause_analysis_command(self) -> RunRootCauseAnalysisCommand:
        return RunRootCauseAnalysisCommand(
            repository=self._intelligence_repository,
            event_bus=self._event_bus,
        )

    def generate_recommendations_command(self) -> GenerateRecommendationsCommand:
        return GenerateRecommendationsCommand(
            repository=self._intelligence_repository,
            event_bus=self._event_bus,
        )

    # --- Query factories ---

    def get_avs_query(self) -> GetAVSQuery:
        return GetAVSQuery(repository=self._intelligence_repository)

    def get_avs_trends_query(self) -> GetAVSTrendsQuery:
        return GetAVSTrendsQuery(repository=self._intelligence_repository)

    def get_recommendation_queue_query(self) -> GetRecommendationQueueQuery:
        return GetRecommendationQueueQuery(repository=self._intelligence_repository)

    def get_root_cause_query(self) -> GetRootCauseQuery:
        return GetRootCauseQuery(repository=self._intelligence_repository)

    # --- Lifecycle ---

    async def shutdown(self) -> None:
        """Release any resources held by the container."""
        # In-memory adapters need no cleanup; production adapters would
        # close database connections, MCP client sessions, etc.
        pass
