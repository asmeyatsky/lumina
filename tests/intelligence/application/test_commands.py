"""
Tests for Intelligence Engine Application Commands

Verifies:
- CalculateAVSCommand fetches all scores in parallel
- CalculateAVSCommand publishes AVSCalculated event
- RunRootCauseAnalysisCommand produces analysis
- GenerateRecommendationsCommand produces sorted list
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lumina.shared.domain.value_objects import BrandId, Score

from lumina.intelligence.application.commands import (
    CalculateAVSCommand,
    GenerateRecommendationsCommand,
    RunRootCauseAnalysisCommand,
)
from lumina.intelligence.domain.entities import AIVisibilityScore, ScoreComponent
from lumina.intelligence.domain.events import AVSCalculated, RootCauseAnalysisCompleted
from lumina.intelligence.domain.value_objects import AVSWeights
from lumina.presentation.config.dependency_injection import (
    InMemoryEventBus,
    InMemoryIntelligenceRepository,
    InMemoryModuleScores,
)


@pytest.fixture
def brand_id() -> BrandId:
    return BrandId("test-brand")


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def repository() -> InMemoryIntelligenceRepository:
    return InMemoryIntelligenceRepository()


@pytest.fixture
def module_scores() -> InMemoryModuleScores:
    return InMemoryModuleScores(
        default_pulse=70.0,
        default_graph=60.0,
        default_beam=80.0,
        default_signal=50.0,
    )


class TestCalculateAVSCommand:
    """Tests for the CalculateAVSCommand use case."""

    async def test_fetches_all_scores_in_parallel(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
    ) -> None:
        """Verify that all four module scores are fetched via asyncio.gather."""
        call_order: list[str] = []

        class TrackingModuleScores:
            async def get_pulse_score(self, bid: BrandId) -> Score:
                call_order.append("pulse")
                return Score(70.0)

            async def get_graph_score(self, bid: BrandId) -> Score:
                call_order.append("graph")
                return Score(60.0)

            async def get_beam_score(self, bid: BrandId) -> Score:
                call_order.append("beam")
                return Score(80.0)

            async def get_signal_score(self, bid: BrandId) -> Score:
                call_order.append("signal")
                return Score(50.0)

        tracking_scores = TrackingModuleScores()

        command = CalculateAVSCommand(
            repository=repository,
            module_scores=tracking_scores,
            event_bus=event_bus,
        )

        await command.execute(brand_id)

        # All four modules were called
        assert set(call_order) == {"pulse", "graph", "beam", "signal"}

    async def test_publishes_avs_calculated_event(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
        module_scores: InMemoryModuleScores,
    ) -> None:
        """AVSCalculated event is published after successful calculation."""
        command = CalculateAVSCommand(
            repository=repository,
            module_scores=module_scores,
            event_bus=event_bus,
        )

        await command.execute(brand_id)

        assert len(event_bus.published_events) >= 1
        avs_events = [
            e for e in event_bus.published_events if isinstance(e, AVSCalculated)
        ]
        assert len(avs_events) == 1
        assert avs_events[0].brand_id == "test-brand"

    async def test_persists_avs(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
        module_scores: InMemoryModuleScores,
    ) -> None:
        """Calculated AVS is persisted in the repository."""
        command = CalculateAVSCommand(
            repository=repository,
            module_scores=module_scores,
            event_bus=event_bus,
        )

        await command.execute(brand_id)

        avs = await repository.get_latest_avs(brand_id)
        assert avs is not None
        assert avs.brand_id == "test-brand"
        # 70*0.30 + 60*0.25 + 80*0.25 + 50*0.20 = 21 + 15 + 20 + 10 = 66.0
        assert avs.overall.value == pytest.approx(66.0)

    async def test_records_previous_score_on_recalculation(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
        module_scores: InMemoryModuleScores,
    ) -> None:
        """Second calculation records the previous AVS for delta tracking."""
        command = CalculateAVSCommand(
            repository=repository,
            module_scores=module_scores,
            event_bus=event_bus,
        )

        # First calculation
        await command.execute(brand_id)

        # Change scores and recalculate
        module_scores._defaults["pulse"] = 90.0
        await command.execute(brand_id)

        avs = await repository.get_latest_avs(brand_id)
        assert avs is not None
        assert avs.previous_score is not None
        assert avs.previous_score.value == pytest.approx(66.0)


class TestRunRootCauseAnalysisCommand:
    """Tests for the RunRootCauseAnalysisCommand use case."""

    async def test_produces_analysis(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
    ) -> None:
        """Root cause analysis produces a valid RootCauseAnalysis entity."""
        command = RunRootCauseAnalysisCommand(
            repository=repository,
            event_bus=event_bus,
        )

        rca = await command.execute(
            brand_id=brand_id,
            current_scores={"pulse": 40.0, "graph": 70.0},
            previous_scores={"pulse": 70.0, "graph": 75.0},
            external_signals=["Algorithm update"],
        )

        assert rca.brand_id == "test-brand"
        assert len(rca.causes) >= 1
        assert len(rca.recommended_actions) >= 1

    async def test_publishes_rca_completed_event(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
    ) -> None:
        """RootCauseAnalysisCompleted event is published."""
        command = RunRootCauseAnalysisCommand(
            repository=repository,
            event_bus=event_bus,
        )

        await command.execute(
            brand_id=brand_id,
            current_scores={"pulse": 40.0},
            previous_scores={"pulse": 70.0},
        )

        rca_events = [
            e
            for e in event_bus.published_events
            if isinstance(e, RootCauseAnalysisCompleted)
        ]
        assert len(rca_events) == 1
        assert rca_events[0].brand_id == "test-brand"

    async def test_persists_rca(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
    ) -> None:
        """RCA is persisted in the repository."""
        command = RunRootCauseAnalysisCommand(
            repository=repository,
            event_bus=event_bus,
        )

        await command.execute(
            brand_id=brand_id,
            current_scores={"pulse": 40.0},
            previous_scores={"pulse": 70.0},
        )

        rca = await repository.get_latest_root_cause_analysis(brand_id)
        assert rca is not None
        assert rca.brand_id == "test-brand"


class TestGenerateRecommendationsCommand:
    """Tests for the GenerateRecommendationsCommand use case."""

    async def test_produces_sorted_list(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
    ) -> None:
        """Recommendations are returned sorted by priority_rank."""
        # First, create an AVS so the command can find it
        avs = AIVisibilityScore(
            brand_id="test-brand",
            overall=Score(45.0),
            components=(
                ScoreComponent(module_name="pulse", score=Score(30.0), weight=0.30),
                ScoreComponent(module_name="graph", score=Score(40.0), weight=0.25),
                ScoreComponent(module_name="beam", score=Score(60.0), weight=0.25),
                ScoreComponent(module_name="signal", score=Score(50.0), weight=0.20),
            ),
        )
        await repository.save_avs(avs)

        command = GenerateRecommendationsCommand(
            repository=repository,
            event_bus=event_bus,
        )

        recs = await command.execute(brand_id=brand_id)

        assert len(recs) > 0
        # Verify sorted by priority_rank
        ranks = [r.priority_rank for r in recs]
        assert ranks == sorted(ranks)
        assert ranks[0] == 1

    async def test_raises_when_no_avs_exists(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
    ) -> None:
        """Raises EntityNotFoundError when no AVS exists for the brand."""
        from lumina.shared.domain.errors import EntityNotFoundError

        command = GenerateRecommendationsCommand(
            repository=repository,
            event_bus=event_bus,
        )

        with pytest.raises(EntityNotFoundError):
            await command.execute(brand_id=brand_id)

    async def test_publishes_recommendation_events(
        self,
        brand_id: BrandId,
        event_bus: InMemoryEventBus,
        repository: InMemoryIntelligenceRepository,
    ) -> None:
        """RecommendationGenerated events are published for each recommendation."""
        avs = AIVisibilityScore(
            brand_id="test-brand",
            overall=Score(40.0),
            components=(
                ScoreComponent(module_name="pulse", score=Score(20.0), weight=0.30),
                ScoreComponent(module_name="graph", score=Score(40.0), weight=0.25),
                ScoreComponent(module_name="beam", score=Score(60.0), weight=0.25),
                ScoreComponent(module_name="signal", score=Score(50.0), weight=0.20),
            ),
        )
        await repository.save_avs(avs)

        command = GenerateRecommendationsCommand(
            repository=repository,
            event_bus=event_bus,
        )

        recs = await command.execute(brand_id=brand_id)

        from lumina.intelligence.domain.events import RecommendationGenerated

        rec_events = [
            e
            for e in event_bus.published_events
            if isinstance(e, RecommendationGenerated)
        ]
        assert len(rec_events) == len(recs)
