"""
Tests for Intelligence Engine Domain Services

Verifies:
- AVSCalculationService produces correct weighted scores
- AVSCalculationService detects significant changes
- RecommendationService prioritises by impact/effort ratio
- RootCauseAnalysisService identifies biggest component drops
"""

from __future__ import annotations

import pytest

from lumina.shared.domain.value_objects import Score

from lumina.intelligence.domain.entities import (
    AIVisibilityScore,
    Recommendation,
    ScoreComponent,
)
from lumina.intelligence.domain.events import AVSCalculated, AVSDropDetected
from lumina.intelligence.domain.services import (
    AVSCalculationService,
    RecommendationService,
    RootCauseAnalysisService,
)
from lumina.intelligence.domain.value_objects import AVSWeights, EffortLevel


class TestAVSCalculationService:
    """Tests for the AVS calculation domain service."""

    def test_calculate_avs_correct_weighted_score(self) -> None:
        """AVS overall score is the weighted sum of all module scores."""
        weights = AVSWeights()  # 0.30, 0.25, 0.25, 0.20

        avs = AVSCalculationService.calculate_avs(
            pulse_score=Score(80.0),
            graph_score=Score(60.0),
            beam_score=Score(70.0),
            signal_score=Score(50.0),
            weights=weights,
            brand_id="brand-1",
        )

        # Expected: 80*0.30 + 60*0.25 + 70*0.25 + 50*0.20
        # = 24.0 + 15.0 + 17.5 + 10.0 = 66.5
        assert avs.overall.value == pytest.approx(66.5)
        assert avs.brand_id == "brand-1"
        assert len(avs.components) == 4

    def test_calculate_avs_all_zeros(self) -> None:
        """AVS with all zero scores produces 0.0."""
        avs = AVSCalculationService.calculate_avs(
            pulse_score=Score(0.0),
            graph_score=Score(0.0),
            beam_score=Score(0.0),
            signal_score=Score(0.0),
            weights=AVSWeights(),
        )
        assert avs.overall.value == 0.0

    def test_calculate_avs_all_perfect(self) -> None:
        """AVS with all perfect scores produces 100.0."""
        avs = AVSCalculationService.calculate_avs(
            pulse_score=Score(100.0),
            graph_score=Score(100.0),
            beam_score=Score(100.0),
            signal_score=Score(100.0),
            weights=AVSWeights(),
        )
        assert avs.overall.value == 100.0

    def test_calculate_avs_emits_avs_calculated_event(self) -> None:
        """AVS calculation always emits an AVSCalculated event."""
        avs = AVSCalculationService.calculate_avs(
            pulse_score=Score(50.0),
            graph_score=Score(50.0),
            beam_score=Score(50.0),
            signal_score=Score(50.0),
            weights=AVSWeights(),
            brand_id="brand-1",
        )

        assert len(avs.domain_events) >= 1
        calc_events = [e for e in avs.domain_events if isinstance(e, AVSCalculated)]
        assert len(calc_events) == 1
        assert calc_events[0].brand_id == "brand-1"
        assert calc_events[0].new_score == 50.0

    def test_calculate_avs_with_previous_score(self) -> None:
        """AVS with a previous score records the delta correctly."""
        previous = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(70.0),
        )

        avs = AVSCalculationService.calculate_avs(
            pulse_score=Score(50.0),
            graph_score=Score(50.0),
            beam_score=Score(50.0),
            signal_score=Score(50.0),
            weights=AVSWeights(),
            brand_id="brand-1",
            previous_avs=previous,
        )

        assert avs.previous_score is not None
        assert avs.previous_score.value == 70.0
        assert avs.calculate_delta() == pytest.approx(-20.0)

    def test_calculate_avs_emits_drop_event_on_significant_drop(self) -> None:
        """A drop > 5.0 emits an AVSDropDetected event."""
        previous = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(70.0),
        )

        avs = AVSCalculationService.calculate_avs(
            pulse_score=Score(50.0),
            graph_score=Score(50.0),
            beam_score=Score(50.0),
            signal_score=Score(50.0),
            weights=AVSWeights(),
            brand_id="brand-1",
            previous_avs=previous,
        )

        drop_events = [e for e in avs.domain_events if isinstance(e, AVSDropDetected)]
        assert len(drop_events) == 1
        assert drop_events[0].drop_amount == pytest.approx(20.0)

    def test_calculate_avs_no_drop_event_on_small_change(self) -> None:
        """A small change does not emit AVSDropDetected."""
        previous = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(50.0),
        )

        avs = AVSCalculationService.calculate_avs(
            pulse_score=Score(48.0),
            graph_score=Score(50.0),
            beam_score=Score(50.0),
            signal_score=Score(50.0),
            weights=AVSWeights(),
            brand_id="brand-1",
            previous_avs=previous,
        )

        drop_events = [e for e in avs.domain_events if isinstance(e, AVSDropDetected)]
        assert len(drop_events) == 0

    def test_calculate_avs_custom_weights(self) -> None:
        """Custom weights produce correct results."""
        weights = AVSWeights(
            citation_frequency=0.40,
            entity_depth=0.20,
            content_geo=0.20,
            distribution_coverage=0.20,
        )

        avs = AVSCalculationService.calculate_avs(
            pulse_score=Score(100.0),
            graph_score=Score(0.0),
            beam_score=Score(0.0),
            signal_score=Score(0.0),
            weights=weights,
        )

        assert avs.overall.value == pytest.approx(40.0)

    def test_detect_significant_change_true(self) -> None:
        """Detects significant change when delta exceeds threshold."""
        current = AIVisibilityScore(overall=Score(80.0))
        previous = AIVisibilityScore(overall=Score(70.0))

        assert AVSCalculationService.detect_significant_change(current, previous) is True

    def test_detect_significant_change_false(self) -> None:
        """No significant change when delta is below threshold."""
        current = AIVisibilityScore(overall=Score(72.0))
        previous = AIVisibilityScore(overall=Score(70.0))

        assert AVSCalculationService.detect_significant_change(current, previous) is False

    def test_detect_significant_change_custom_threshold(self) -> None:
        """Custom threshold works correctly."""
        current = AIVisibilityScore(overall=Score(73.0))
        previous = AIVisibilityScore(overall=Score(70.0))

        assert (
            AVSCalculationService.detect_significant_change(
                current, previous, threshold=3.0
            )
            is True
        )
        assert (
            AVSCalculationService.detect_significant_change(
                current, previous, threshold=5.0
            )
            is False
        )

    def test_detect_significant_change_uses_absolute(self) -> None:
        """Significant change detection uses absolute values."""
        current = AIVisibilityScore(overall=Score(60.0))
        previous = AIVisibilityScore(overall=Score(70.0))

        assert AVSCalculationService.detect_significant_change(current, previous) is True


class TestRecommendationService:
    """Tests for the recommendation domain service."""

    def test_prioritize_by_impact_effort_ratio(self) -> None:
        """Recommendations are sorted by impact/effort ratio (highest first)."""
        recs = [
            Recommendation(
                id="rec-1",
                source_module="pulse",
                action_description="Low effort, high impact",
                expected_avs_impact=Score(30.0),
                effort_level=EffortLevel.LOW,
            ),
            Recommendation(
                id="rec-2",
                source_module="graph",
                action_description="High effort, high impact",
                expected_avs_impact=Score(30.0),
                effort_level=EffortLevel.HIGH,
            ),
            Recommendation(
                id="rec-3",
                source_module="beam",
                action_description="Medium effort, medium impact",
                expected_avs_impact=Score(20.0),
                effort_level=EffortLevel.MEDIUM,
            ),
        ]

        prioritized = RecommendationService.prioritize(recs)

        assert len(prioritized) == 3
        # rec-1: 30/1 = 30.0
        # rec-3: 20/2 = 10.0
        # rec-2: 30/3 = 10.0 (tied with rec-3, but rec-2 has higher impact -> earlier)
        assert prioritized[0].id == "rec-1"
        assert prioritized[0].priority_rank == 1
        # rec-2 and rec-3 have same ratio (10.0), rec-2 has higher impact
        assert prioritized[1].id == "rec-2"
        assert prioritized[1].priority_rank == 2
        assert prioritized[2].id == "rec-3"
        assert prioritized[2].priority_rank == 3

    def test_prioritize_assigns_ranks(self) -> None:
        """All recommendations get sequential priority_rank values."""
        recs = [
            Recommendation(
                id=f"rec-{i}",
                source_module="pulse",
                expected_avs_impact=Score(float(10 * i)),
                effort_level=EffortLevel.MEDIUM,
            )
            for i in range(1, 6)
        ]

        prioritized = RecommendationService.prioritize(recs)

        ranks = [r.priority_rank for r in prioritized]
        assert ranks == [1, 2, 3, 4, 5]

    def test_generate_recommendations_from_low_components(self) -> None:
        """Low-scoring components generate improvement recommendations."""
        avs = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(35.0),
            components=(
                ScoreComponent(module_name="pulse", score=Score(20.0), weight=0.30),
                ScoreComponent(module_name="graph", score=Score(30.0), weight=0.25),
                ScoreComponent(module_name="beam", score=Score(80.0), weight=0.25),
                ScoreComponent(module_name="signal", score=Score(90.0), weight=0.20),
            ),
        )

        recs = RecommendationService.generate_recommendations(
            avs=avs, gaps=[], content_scores=[], coverage={},
        )

        # pulse (20) and graph (30) are below 50, so should generate HIGH and MEDIUM effort recs
        pulse_recs = [r for r in recs if r.source_module == "pulse"]
        graph_recs = [r for r in recs if r.source_module == "graph"]
        assert len(pulse_recs) >= 1
        assert len(graph_recs) >= 1
        # pulse score 20 < 25 -> HIGH effort
        assert any(r.effort_level == EffortLevel.HIGH for r in pulse_recs)

    def test_generate_recommendations_empty_inputs(self) -> None:
        """Empty gaps/content/coverage still produces component-based recommendations."""
        avs = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(50.0),
            components=(
                ScoreComponent(module_name="pulse", score=Score(50.0), weight=0.30),
                ScoreComponent(module_name="graph", score=Score(50.0), weight=0.25),
                ScoreComponent(module_name="beam", score=Score(50.0), weight=0.25),
                ScoreComponent(module_name="signal", score=Score(50.0), weight=0.20),
            ),
        )

        recs = RecommendationService.generate_recommendations(
            avs=avs, gaps=[], content_scores=[], coverage={},
        )

        # All scores are exactly 50, so each is < 75 -> generates optimise recommendations
        assert len(recs) > 0
        assert all(r.priority_rank > 0 for r in recs)


class TestRootCauseAnalysisService:
    """Tests for the root cause analysis domain service."""

    def test_identifies_biggest_drops(self) -> None:
        """Biggest module score drops appear first in causes."""
        rca = RootCauseAnalysisService.analyze(
            current_scores={"pulse": 40.0, "graph": 70.0, "beam": 65.0, "signal": 80.0},
            previous_scores={"pulse": 70.0, "graph": 75.0, "beam": 70.0, "signal": 80.0},
            external_signals=[],
            brand_id="brand-1",
        )

        # pulse dropped 30 points — biggest drop, should be first cause
        assert len(rca.causes) >= 1
        assert rca.causes[0].module == "pulse"
        assert rca.causes[0].contribution_weight > 0

    def test_includes_external_signals(self) -> None:
        """External signals appear as causes."""
        rca = RootCauseAnalysisService.analyze(
            current_scores={"pulse": 50.0},
            previous_scores={"pulse": 60.0},
            external_signals=["Google algorithm update detected"],
            brand_id="brand-1",
        )

        external_causes = [c for c in rca.causes if c.module == "external"]
        assert len(external_causes) == 1
        assert "Google algorithm update" in external_causes[0].evidence

    def test_generates_recommended_actions(self) -> None:
        """Recommended actions are generated for each identified cause."""
        rca = RootCauseAnalysisService.analyze(
            current_scores={"pulse": 40.0, "beam": 50.0},
            previous_scores={"pulse": 70.0, "beam": 60.0},
            external_signals=[],
            brand_id="brand-1",
        )

        assert len(rca.recommended_actions) >= 2

    def test_no_drops_no_causes(self) -> None:
        """No drops means no decline causes."""
        rca = RootCauseAnalysisService.analyze(
            current_scores={"pulse": 80.0, "graph": 80.0},
            previous_scores={"pulse": 70.0, "graph": 70.0},
            external_signals=[],
            brand_id="brand-1",
        )

        decline_causes = [
            c for c in rca.causes if c.module != "external"
        ]
        assert len(decline_causes) == 0

    def test_contribution_weights_are_normalised(self) -> None:
        """Contribution weights should be proportional to each module's change."""
        rca = RootCauseAnalysisService.analyze(
            current_scores={"pulse": 40.0, "graph": 55.0},
            previous_scores={"pulse": 70.0, "graph": 60.0},
            external_signals=[],
            brand_id="brand-1",
        )

        decline_causes = [c for c in rca.causes if c.module != "external"]
        if decline_causes:
            # The pulse drop (30) should have higher weight than graph drop (5)
            pulse_cause = [c for c in decline_causes if c.module == "pulse"]
            graph_cause = [c for c in decline_causes if c.module == "graph"]
            if pulse_cause and graph_cause:
                assert pulse_cause[0].contribution_weight > graph_cause[0].contribution_weight

    def test_trigger_description_references_top_cause(self) -> None:
        """Trigger description references the primary contributing module."""
        rca = RootCauseAnalysisService.analyze(
            current_scores={"pulse": 30.0, "graph": 70.0},
            previous_scores={"pulse": 80.0, "graph": 75.0},
            external_signals=[],
            brand_id="brand-1",
        )

        assert "pulse" in rca.trigger
