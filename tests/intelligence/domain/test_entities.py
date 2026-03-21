"""
Tests for Intelligence Engine Domain Entities

Verifies:
- AIVisibilityScore.calculate_delta() produces correct values
- ScoreComponent weight constraints and weighted_score calculation
- Recommendation entity immutability (frozen dataclass)
- RootCause contribution_weight constraints
"""

from __future__ import annotations

import pytest
from datetime import datetime, UTC

from lumina.shared.domain.value_objects import Score

from lumina.intelligence.domain.entities import (
    AIVisibilityScore,
    Recommendation,
    RootCause,
    RootCauseAnalysis,
    ScoreComponent,
)
from lumina.intelligence.domain.value_objects import EffortLevel


class TestAIVisibilityScore:
    """Tests for the AIVisibilityScore aggregate."""

    def test_calculate_delta_with_previous_score(self) -> None:
        """Delta is current minus previous score."""
        avs = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(72.5),
            previous_score=Score(65.0),
        )
        assert avs.calculate_delta() == pytest.approx(7.5)

    def test_calculate_delta_negative(self) -> None:
        """Delta can be negative when score drops."""
        avs = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(40.0),
            previous_score=Score(55.0),
        )
        assert avs.calculate_delta() == pytest.approx(-15.0)

    def test_calculate_delta_no_previous(self) -> None:
        """Delta is 0.0 when there is no previous score."""
        avs = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(72.5),
            previous_score=None,
        )
        assert avs.calculate_delta() == 0.0

    def test_calculate_delta_zero_change(self) -> None:
        """Delta is 0.0 when scores are identical."""
        avs = AIVisibilityScore(
            brand_id="brand-1",
            overall=Score(50.0),
            previous_score=Score(50.0),
        )
        assert avs.calculate_delta() == 0.0

    def test_avs_is_frozen(self) -> None:
        """AIVisibilityScore is immutable."""
        avs = AIVisibilityScore(brand_id="brand-1", overall=Score(50.0))
        with pytest.raises(AttributeError):
            avs.brand_id = "brand-2"  # type: ignore[misc]

    def test_avs_default_events_empty(self) -> None:
        """Domain events default to empty tuple."""
        avs = AIVisibilityScore(brand_id="brand-1", overall=Score(50.0))
        assert avs.domain_events == ()


class TestScoreComponent:
    """Tests for the ScoreComponent value object."""

    def test_valid_modules(self) -> None:
        """All four module names are accepted."""
        for module in ("pulse", "graph", "beam", "signal"):
            sc = ScoreComponent(module_name=module, score=Score(50.0), weight=0.25)
            assert sc.module_name == module

    def test_invalid_module_raises(self) -> None:
        """Invalid module name raises ValueError."""
        with pytest.raises(ValueError, match="module_name must be one of"):
            ScoreComponent(module_name="invalid", score=Score(50.0), weight=0.25)

    def test_weighted_score(self) -> None:
        """Weighted score is score * weight."""
        sc = ScoreComponent(module_name="pulse", score=Score(80.0), weight=0.30)
        assert sc.weighted_score == pytest.approx(24.0)

    def test_weight_out_of_range_raises(self) -> None:
        """Weight outside [0, 1] raises ValueError."""
        with pytest.raises(ValueError, match="weight must be between 0 and 1"):
            ScoreComponent(module_name="pulse", score=Score(50.0), weight=1.5)

    def test_weights_sum_correctly(self) -> None:
        """Default weights from four components sum to 1.0."""
        components = (
            ScoreComponent(module_name="pulse", score=Score(50.0), weight=0.30),
            ScoreComponent(module_name="graph", score=Score(50.0), weight=0.25),
            ScoreComponent(module_name="beam", score=Score(50.0), weight=0.25),
            ScoreComponent(module_name="signal", score=Score(50.0), weight=0.20),
        )
        total_weight = sum(c.weight for c in components)
        assert total_weight == pytest.approx(1.0)

    def test_raw_metrics_as_tuple(self) -> None:
        """Raw metrics are stored as a tuple of key-value pairs."""
        metrics = (("citations", 42), ("responses", 100))
        sc = ScoreComponent(
            module_name="pulse",
            score=Score(50.0),
            weight=0.30,
            raw_metrics=metrics,
        )
        assert sc.raw_metrics == metrics
        assert dict(sc.raw_metrics) == {"citations": 42, "responses": 100}


class TestRecommendation:
    """Tests for the Recommendation entity."""

    def test_recommendation_is_frozen(self) -> None:
        """Recommendation is immutable."""
        rec = Recommendation(
            brand_id="brand-1",
            source_module="pulse",
            action_description="Improve citations",
            expected_avs_impact=Score(10.0),
            effort_level=EffortLevel.LOW,
            priority_rank=1,
        )
        with pytest.raises(AttributeError):
            rec.priority_rank = 2  # type: ignore[misc]

    def test_recommendation_default_values(self) -> None:
        """Recommendation has sensible defaults."""
        rec = Recommendation()
        assert rec.brand_id == ""
        assert rec.source_module == ""
        assert rec.effort_level == EffortLevel.MEDIUM
        assert rec.priority_rank == 0
        assert rec.linked_entity_id == ""

    def test_recommendation_invalid_module(self) -> None:
        """Invalid source_module raises ValueError."""
        with pytest.raises(ValueError, match="source_module must be one of"):
            Recommendation(source_module="invalid")

    def test_effort_level_numeric(self) -> None:
        """EffortLevel numeric values are correct."""
        assert EffortLevel.LOW.numeric == 1
        assert EffortLevel.MEDIUM.numeric == 2
        assert EffortLevel.HIGH.numeric == 3


class TestRootCause:
    """Tests for the RootCause value object."""

    def test_root_cause_valid(self) -> None:
        """Valid RootCause construction."""
        rc = RootCause(
            factor="score_decline",
            module="pulse",
            evidence="Score dropped from 70 to 50",
            contribution_weight=0.6,
        )
        assert rc.factor == "score_decline"
        assert rc.contribution_weight == 0.6

    def test_root_cause_invalid_weight(self) -> None:
        """Contribution weight outside [0, 1] raises ValueError."""
        with pytest.raises(ValueError, match="contribution_weight must be between"):
            RootCause(
                factor="test",
                module="pulse",
                evidence="test",
                contribution_weight=1.5,
            )

    def test_root_cause_is_frozen(self) -> None:
        """RootCause is immutable."""
        rc = RootCause(
            factor="test",
            module="pulse",
            evidence="test",
            contribution_weight=0.5,
        )
        with pytest.raises(AttributeError):
            rc.factor = "changed"  # type: ignore[misc]
