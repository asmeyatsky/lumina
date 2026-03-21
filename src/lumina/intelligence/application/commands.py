"""
Intelligence Engine Application Commands (Use Cases)

Architectural Intent:
- Commands orchestrate domain logic and infrastructure interactions
- Each command represents a single write-side use case
- Parallelism-first: module scores are fetched concurrently via asyncio.gather
- Domain events are published after successful persistence
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from lumina.shared.domain.value_objects import BrandId
from lumina.shared.ports.event_bus import EventBusPort

from lumina.intelligence.domain.entities import Recommendation, RootCauseAnalysis
from lumina.intelligence.domain.events import (
    RecommendationGenerated,
    RootCauseAnalysisCompleted,
)
from lumina.intelligence.domain.ports import IntelligenceRepositoryPort, ModuleScorePort
from lumina.intelligence.domain.services import (
    AVSCalculationService,
    RecommendationService,
    RootCauseAnalysisService,
)
from lumina.intelligence.domain.value_objects import AVSWeights


@dataclass(frozen=True)
class CalculateAVSCommand:
    """Fetch scores from all four modules in parallel, calculate AVS, persist, and publish events.

    This is the primary write-side use case for the Intelligence Engine.
    """

    repository: IntelligenceRepositoryPort
    module_scores: ModuleScorePort
    event_bus: EventBusPort
    weights: AVSWeights = AVSWeights()

    async def execute(self, brand_id: BrandId) -> None:
        """Execute the AVS calculation pipeline.

        1. Fetch all four module scores in parallel.
        2. Retrieve previous AVS for delta calculation.
        3. Calculate the new AVS via the domain service.
        4. Persist the new AVS.
        5. Publish domain events.
        """
        # Parallelism-first: fetch all module scores concurrently
        pulse_score, graph_score, beam_score, signal_score = await asyncio.gather(
            self.module_scores.get_pulse_score(brand_id),
            self.module_scores.get_graph_score(brand_id),
            self.module_scores.get_beam_score(brand_id),
            self.module_scores.get_signal_score(brand_id),
        )

        previous_avs = await self.repository.get_latest_avs(brand_id)

        avs = AVSCalculationService.calculate_avs(
            pulse_score=pulse_score,
            graph_score=graph_score,
            beam_score=beam_score,
            signal_score=signal_score,
            weights=self.weights,
            brand_id=brand_id.value,
            previous_avs=previous_avs,
        )

        await self.repository.save_avs(avs)

        if avs.domain_events:
            await self.event_bus.publish(list(avs.domain_events))


@dataclass(frozen=True)
class RunRootCauseAnalysisCommand:
    """Triggered when a significant AVS drop is detected. Analyses causes and persists the result."""

    repository: IntelligenceRepositoryPort
    event_bus: EventBusPort

    async def execute(
        self,
        brand_id: BrandId,
        current_scores: dict[str, float],
        previous_scores: dict[str, float],
        external_signals: list[str] | None = None,
    ) -> RootCauseAnalysis:
        """Execute root cause analysis.

        Args:
            brand_id: The brand under analysis.
            current_scores: Current module scores (module_name -> value).
            previous_scores: Previous module scores (module_name -> value).
            external_signals: Optional external context strings.

        Returns:
            The completed RootCauseAnalysis entity.
        """
        signals = external_signals or []

        rca = RootCauseAnalysisService.analyze(
            current_scores=current_scores,
            previous_scores=previous_scores,
            external_signals=signals,
            brand_id=brand_id.value,
        )

        await self.repository.save_root_cause_analysis(rca)

        event = RootCauseAnalysisCompleted(
            aggregate_id=rca.id,
            brand_id=brand_id.value,
            trigger=rca.trigger,
            cause_count=len(rca.causes),
        )
        await self.event_bus.publish([event])

        return rca


@dataclass(frozen=True)
class GenerateRecommendationsCommand:
    """Generate and prioritise recommendations based on the current AVS and module data."""

    repository: IntelligenceRepositoryPort
    event_bus: EventBusPort

    async def execute(
        self,
        brand_id: BrandId,
        gaps: list[dict[str, object]] | None = None,
        content_scores: list[dict[str, object]] | None = None,
        coverage: dict[str, object] | None = None,
    ) -> list[Recommendation]:
        """Execute recommendation generation.

        Args:
            brand_id: The brand to generate recommendations for.
            gaps: Knowledge gaps from GRAPH.
            content_scores: Content scores from BEAM.
            coverage: Distribution coverage from SIGNAL.

        Returns:
            A prioritised list of Recommendation entities.
        """
        avs = await self.repository.get_latest_avs(brand_id)
        if avs is None:
            from lumina.shared.domain.errors import EntityNotFoundError
            raise EntityNotFoundError(
                f"No AVS found for brand {brand_id.value}. Calculate AVS first."
            )

        recommendations = RecommendationService.generate_recommendations(
            avs=avs,
            gaps=gaps or [],
            content_scores=content_scores or [],
            coverage=coverage or {},
            brand_id=brand_id.value,
        )

        # Persist all recommendations
        for rec in recommendations:
            await self.repository.save_recommendation(rec)

        # Publish events for each generated recommendation
        events = [
            RecommendationGenerated(
                aggregate_id=rec.id,
                brand_id=brand_id.value,
                source_module=rec.source_module,
                action=rec.action_description,
                expected_impact=rec.expected_avs_impact.value,
            )
            for rec in recommendations
        ]
        if events:
            await self.event_bus.publish(events)

        return recommendations
