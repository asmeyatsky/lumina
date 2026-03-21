"""
Intelligence Engine Pure Domain Services

Architectural Intent:
- Stateless, pure functions encapsulating domain logic
- No I/O, no side effects — only domain computations
- Operate exclusively on domain entities and value objects
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.value_objects import Score

from lumina.intelligence.domain.entities import (
    AIVisibilityScore,
    Recommendation,
    RootCause,
    RootCauseAnalysis,
    ScoreComponent,
)
from lumina.intelligence.domain.events import AVSCalculated, AVSDropDetected
from lumina.intelligence.domain.value_objects import AVSWeights, EffortLevel


class AVSCalculationService:
    """Pure domain service for computing the AI Visibility Score."""

    @staticmethod
    def calculate_avs(
        pulse_score: Score,
        graph_score: Score,
        beam_score: Score,
        signal_score: Score,
        weights: AVSWeights,
        brand_id: str = "",
        previous_avs: AIVisibilityScore | None = None,
    ) -> AIVisibilityScore:
        """Calculate a weighted AI Visibility Score from the four module scores.

        Args:
            pulse_score: Score from the PULSE monitoring module.
            graph_score: Score from the GRAPH entity intelligence module.
            beam_score: Score from the BEAM content optimisation module.
            signal_score: Score from the SIGNAL distribution module.
            weights: The weighting configuration for each module.
            brand_id: The brand this score belongs to.
            previous_avs: The previous AVS, if any, for delta calculation.

        Returns:
            A new AIVisibilityScore aggregate with domain events attached.
        """
        components = (
            ScoreComponent(
                module_name="pulse",
                score=pulse_score,
                weight=weights.citation_frequency,
            ),
            ScoreComponent(
                module_name="graph",
                score=graph_score,
                weight=weights.entity_depth,
            ),
            ScoreComponent(
                module_name="beam",
                score=beam_score,
                weight=weights.content_geo,
            ),
            ScoreComponent(
                module_name="signal",
                score=signal_score,
                weight=weights.distribution_coverage,
            ),
        )

        raw_overall = sum(c.weighted_score for c in components)
        overall = Score(round(min(max(raw_overall, 0.0), 100.0), 2))

        previous_score = previous_avs.overall if previous_avs is not None else None

        avs = AIVisibilityScore(
            id=str(uuid4()),
            brand_id=brand_id,
            overall=overall,
            components=components,
            calculated_at=datetime.now(UTC),
            previous_score=previous_score,
        )

        delta = avs.calculate_delta()

        event = AVSCalculated(
            aggregate_id=avs.id,
            brand_id=brand_id,
            new_score=overall.value,
            previous_score=previous_score.value if previous_score else None,
            delta=delta,
        )

        events: list = [event]

        # Detect significant drops
        if previous_score is not None and delta < -5.0:
            drop_event = AVSDropDetected(
                aggregate_id=avs.id,
                brand_id=brand_id,
                drop_amount=abs(delta),
                threshold=5.0,
            )
            events.append(drop_event)

        return replace(avs, domain_events=tuple(events))

    @staticmethod
    def detect_significant_change(
        current: AIVisibilityScore,
        previous: AIVisibilityScore,
        threshold: float = 5.0,
    ) -> bool:
        """Detect whether the change between two AVS values is significant.

        Args:
            current: The current AVS.
            previous: The previous AVS.
            threshold: The minimum absolute change to be considered significant.

        Returns:
            True if the absolute change exceeds the threshold.
        """
        delta = abs(current.overall.value - previous.overall.value)
        return delta >= threshold


class RootCauseAnalysisService:
    """Pure domain service for analysing root causes of AVS changes."""

    @staticmethod
    def analyze(
        current_scores: dict[str, float],
        previous_scores: dict[str, float],
        external_signals: list[str],
        brand_id: str = "",
    ) -> RootCauseAnalysis:
        """Analyse component-level changes to identify root causes of AVS movement.

        Compares current and previous module scores, identifies the modules with
        the largest drops, and correlates with external signals to produce a
        prioritised list of causes.

        Args:
            current_scores: Module name -> current score value.
            previous_scores: Module name -> previous score value.
            external_signals: External context (e.g. "algorithm update", "competitor launch").
            brand_id: The brand under analysis.

        Returns:
            A RootCauseAnalysis aggregate with identified causes and actions.
        """
        causes: list[RootCause] = []

        # Calculate deltas for each module
        all_modules = set(current_scores.keys()) | set(previous_scores.keys())
        deltas: dict[str, float] = {}
        for module in all_modules:
            current_val = current_scores.get(module, 0.0)
            previous_val = previous_scores.get(module, 0.0)
            deltas[module] = current_val - previous_val

        # Sort by largest negative delta (biggest drops first)
        sorted_modules = sorted(deltas.items(), key=lambda x: x[1])

        # Total absolute change for contribution weight normalisation
        total_abs_change = sum(abs(d) for d in deltas.values())
        if total_abs_change == 0.0:
            total_abs_change = 1.0  # avoid division by zero

        for module, delta in sorted_modules:
            if delta < 0:
                contribution = abs(delta) / total_abs_change
                evidence = (
                    f"{module} score dropped from {previous_scores.get(module, 0.0):.1f} "
                    f"to {current_scores.get(module, 0.0):.1f} "
                    f"(delta: {delta:+.1f})"
                )
                causes.append(
                    RootCause(
                        factor=f"{module}_score_decline",
                        module=module,
                        evidence=evidence,
                        contribution_weight=round(contribution, 4),
                    )
                )

        # Include external signals as contributing factors
        for signal in external_signals:
            causes.append(
                RootCause(
                    factor="external_signal",
                    module="external",
                    evidence=signal,
                    contribution_weight=0.0,
                )
            )

        # Generate recommended actions based on the top causes
        recommended_actions: list[str] = []
        for cause in causes:
            if cause.module == "external":
                recommended_actions.append(
                    f"Investigate external factor: {cause.evidence}"
                )
            elif cause.module == "pulse":
                recommended_actions.append(
                    "Review citation monitoring — check for reduced AI engine mentions"
                )
            elif cause.module == "graph":
                recommended_actions.append(
                    "Audit entity knowledge graph — fill identified knowledge gaps"
                )
            elif cause.module == "beam":
                recommended_actions.append(
                    "Re-score content assets — optimise underperforming pages for AI consumption"
                )
            elif cause.module == "signal":
                recommended_actions.append(
                    "Expand distribution coverage — submit to additional AI-crawled surfaces"
                )

        trigger = "AVS score change detected"
        if causes:
            top_cause = causes[0]
            trigger = (
                f"AVS change driven primarily by {top_cause.module} "
                f"(contribution: {top_cause.contribution_weight:.0%})"
            )

        return RootCauseAnalysis(
            id=str(uuid4()),
            brand_id=brand_id,
            trigger=trigger,
            causes=tuple(causes),
            recommended_actions=tuple(recommended_actions),
            analyzed_at=datetime.now(UTC),
        )


class RecommendationService:
    """Pure domain service for generating and prioritising recommendations."""

    @staticmethod
    def generate_recommendations(
        avs: AIVisibilityScore,
        gaps: list[dict[str, object]],
        content_scores: list[dict[str, object]],
        coverage: dict[str, object],
        brand_id: str = "",
    ) -> list[Recommendation]:
        """Generate prioritised recommendations based on the current AVS state.

        Analyses component scores, knowledge gaps, content performance, and
        distribution coverage to produce actionable recommendations.

        Args:
            avs: The current AI Visibility Score.
            gaps: Knowledge gaps from GRAPH module.
            content_scores: Content scoring data from BEAM module.
            coverage: Distribution coverage data from SIGNAL module.
            brand_id: The brand to generate recommendations for.

        Returns:
            A prioritised list of Recommendation entities.
        """
        recommendations: list[Recommendation] = []
        effective_brand_id = brand_id or avs.brand_id

        # Analyse each component for improvement opportunities
        for component in avs.components:
            if component.score.value < 50.0:
                # Low-scoring modules get high-impact recommendations
                impact = Score(min(round((50.0 - component.score.value) * 0.6, 2), 100.0))
                recommendations.append(
                    Recommendation(
                        id=str(uuid4()),
                        brand_id=effective_brand_id,
                        source_module=component.module_name,
                        action_description=(
                            f"Improve {component.module_name} score — "
                            f"currently at {component.score.value:.0f}/100"
                        ),
                        expected_avs_impact=impact,
                        effort_level=EffortLevel.HIGH if component.score.value < 25.0 else EffortLevel.MEDIUM,
                        linked_entity_id="",
                    )
                )
            elif component.score.value < 75.0:
                impact = Score(min(round((75.0 - component.score.value) * 0.4, 2), 100.0))
                recommendations.append(
                    Recommendation(
                        id=str(uuid4()),
                        brand_id=effective_brand_id,
                        source_module=component.module_name,
                        action_description=(
                            f"Optimise {component.module_name} — "
                            f"moderate gains available from {component.score.value:.0f}/100"
                        ),
                        expected_avs_impact=impact,
                        effort_level=EffortLevel.LOW,
                        linked_entity_id="",
                    )
                )

        # Generate recommendations from knowledge gaps
        for gap in gaps:
            gap_name = str(gap.get("name", "unknown"))
            gap_severity = float(gap.get("severity", 5.0))
            entity_id = str(gap.get("entity_id", ""))
            impact_val = min(round(gap_severity * 2.0, 2), 100.0)
            recommendations.append(
                Recommendation(
                    id=str(uuid4()),
                    brand_id=effective_brand_id,
                    source_module="graph",
                    action_description=f"Fill knowledge gap: {gap_name}",
                    expected_avs_impact=Score(impact_val),
                    effort_level=EffortLevel.MEDIUM,
                    linked_entity_id=entity_id,
                )
            )

        # Generate recommendations from low content scores
        for content in content_scores:
            content_score = float(content.get("score", 50.0))
            asset_id = str(content.get("asset_id", ""))
            url = str(content.get("url", ""))
            if content_score < 60.0:
                impact_val = min(round((60.0 - content_score) * 0.5, 2), 100.0)
                recommendations.append(
                    Recommendation(
                        id=str(uuid4()),
                        brand_id=effective_brand_id,
                        source_module="beam",
                        action_description=f"Rewrite content at {url} for AI readability",
                        expected_avs_impact=Score(impact_val),
                        effort_level=EffortLevel.MEDIUM,
                        linked_entity_id=asset_id,
                    )
                )

        # Generate recommendations from coverage gaps
        coverage_pct = float(coverage.get("coverage_percentage", 100.0))
        if coverage_pct < 80.0:
            impact_val = min(round((80.0 - coverage_pct) * 0.3, 2), 100.0)
            recommendations.append(
                Recommendation(
                    id=str(uuid4()),
                    brand_id=effective_brand_id,
                    source_module="signal",
                    action_description="Expand distribution to uncovered AI-crawled surfaces",
                    expected_avs_impact=Score(impact_val),
                    effort_level=EffortLevel.LOW,
                    linked_entity_id="",
                )
            )

        # Prioritise by impact/effort ratio
        return RecommendationService.prioritize(recommendations)

    @staticmethod
    def prioritize(recommendations: list[Recommendation]) -> list[Recommendation]:
        """Sort recommendations by expected AVS impact divided by effort level.

        Higher impact and lower effort items appear first. Ties are broken by
        the original expected_avs_impact descending.

        Args:
            recommendations: The list to prioritise.

        Returns:
            A new list sorted by impact/effort ratio, with priority_rank assigned.
        """
        def sort_key(rec: Recommendation) -> tuple[float, float]:
            ratio = rec.expected_avs_impact.value / rec.effort_level.numeric
            return (-ratio, -rec.expected_avs_impact.value)

        sorted_recs = sorted(recommendations, key=sort_key)

        ranked: list[Recommendation] = []
        for rank, rec in enumerate(sorted_recs, start=1):
            ranked.append(
                Recommendation(
                    id=rec.id,
                    brand_id=rec.brand_id,
                    source_module=rec.source_module,
                    action_description=rec.action_description,
                    expected_avs_impact=rec.expected_avs_impact,
                    effort_level=rec.effort_level,
                    priority_rank=rank,
                    linked_entity_id=rec.linked_entity_id,
                    created_at=rec.created_at,
                )
            )

        return ranked
