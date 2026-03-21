"""
BEAM Domain Entity Tests

Tests for GEOScore, ContentAsset, ContentChunk, and related entities.
Validates immutability, event collection, and score computation.
"""

from __future__ import annotations

import pytest

from lumina.shared.domain.value_objects import BrandId, Score, URL

from lumina.beam.domain.entities import (
    ContentAsset,
    ContentChunk,
    GEOScore,
    RewriteSuggestion,
)
from lumina.beam.domain.events import ContentScored, RewriteSuggestionGenerated
from lumina.beam.domain.value_objects import ContentType, GEOFactor, GEOWeights


def _make_geo_score(
    entity_density: float = 70.0,
    answer_shape: float = 80.0,
    fact_citability: float = 60.0,
    rag_survivability: float = 50.0,
    semantic_authority: float = 90.0,
    freshness_signals: float = 40.0,
) -> GEOScore:
    """Helper to create a GEOScore with configurable factor values."""
    return GEOScore(
        overall=Score(value=0.0),
        entity_density=Score(value=entity_density),
        answer_shape=Score(value=answer_shape),
        fact_citability=Score(value=fact_citability),
        rag_survivability=Score(value=rag_survivability),
        semantic_authority=Score(value=semantic_authority),
        freshness_signals=Score(value=freshness_signals),
    )


def _make_asset(
    asset_id: str = "asset-1",
    brand_id: str = "brand-1",
) -> ContentAsset:
    """Helper to create a minimal ContentAsset."""
    return ContentAsset(
        id=asset_id,
        brand_id=BrandId(value=brand_id),
        url=URL(value="https://example.com/page"),
        title="Test Page",
        raw_content="Some test content for scoring.",
        content_type=ContentType.WEB_PAGE,
    )


class TestGEOScoreWeightedOverall:
    """Test GEOScore.weighted_overall() calculation."""

    def test_weighted_overall_with_default_weights(self) -> None:
        """Weighted overall uses PRD weights: 20/20/20/20/10/10."""
        geo = _make_geo_score(
            entity_density=70.0,
            answer_shape=80.0,
            fact_citability=60.0,
            rag_survivability=50.0,
            semantic_authority=90.0,
            freshness_signals=40.0,
        )
        result = geo.weighted_overall()

        expected = (
            70.0 * 0.20
            + 80.0 * 0.20
            + 60.0 * 0.20
            + 50.0 * 0.20
            + 90.0 * 0.10
            + 40.0 * 0.10
        )
        assert result.value == round(expected, 2)

    def test_weighted_overall_with_custom_weights(self) -> None:
        """Weighted overall respects custom weights."""
        geo = _make_geo_score(
            entity_density=100.0,
            answer_shape=0.0,
            fact_citability=0.0,
            rag_survivability=0.0,
            semantic_authority=0.0,
            freshness_signals=0.0,
        )
        weights = GEOWeights(
            entity_density=1.0,
            answer_shape=0.0,
            fact_citability=0.0,
            rag_survivability=0.0,
            semantic_authority=0.0,
            freshness_signals=0.0,
        )
        result = geo.weighted_overall(weights)
        assert result.value == 100.0

    def test_weighted_overall_all_zeros(self) -> None:
        """All zero scores produce a zero weighted overall."""
        geo = _make_geo_score(
            entity_density=0.0,
            answer_shape=0.0,
            fact_citability=0.0,
            rag_survivability=0.0,
            semantic_authority=0.0,
            freshness_signals=0.0,
        )
        result = geo.weighted_overall()
        assert result.value == 0.0

    def test_weighted_overall_all_perfect(self) -> None:
        """All perfect scores produce a perfect weighted overall."""
        geo = _make_geo_score(
            entity_density=100.0,
            answer_shape=100.0,
            fact_citability=100.0,
            rag_survivability=100.0,
            semantic_authority=100.0,
            freshness_signals=100.0,
        )
        result = geo.weighted_overall()
        assert result.value == 100.0

    def test_weighted_overall_returns_score_type(self) -> None:
        """The result is a Score value object."""
        geo = _make_geo_score()
        result = geo.weighted_overall()
        assert isinstance(result, Score)


class TestContentAssetScore:
    """Test ContentAsset.score() produces new instances with events."""

    def test_score_produces_new_instance(self) -> None:
        """Scoring an asset returns a new instance (immutability)."""
        asset = _make_asset()
        geo = _make_geo_score()

        scored_asset = asset.score(geo)

        assert scored_asset is not asset
        assert scored_asset.geo_score is geo
        assert asset.geo_score is None

    def test_score_records_content_scored_event(self) -> None:
        """Scoring records a ContentScored domain event."""
        asset = _make_asset()
        geo = _make_geo_score()

        scored_asset = asset.score(geo)

        assert len(scored_asset.domain_events) == 1
        event = scored_asset.domain_events[0]
        assert isinstance(event, ContentScored)
        assert event.aggregate_id == asset.id
        assert event.asset_id == asset.id
        assert event.brand_id == asset.brand_id.value
        assert event.url == asset.url.value
        assert event.previous_score is None

    def test_score_tracks_previous_score(self) -> None:
        """Re-scoring includes the previous score in the event."""
        asset = _make_asset()
        geo1 = _make_geo_score(entity_density=50.0)
        geo2 = _make_geo_score(entity_density=80.0)

        scored_once = asset.score(geo1)
        scored_twice = scored_once.score(geo2)

        events = scored_twice.domain_events
        assert len(events) == 2
        second_event = events[1]
        assert isinstance(second_event, ContentScored)
        assert second_event.previous_score == geo1.overall.value

    def test_score_sets_last_scored_at(self) -> None:
        """Scoring sets the last_scored_at timestamp."""
        asset = _make_asset()
        geo = _make_geo_score()

        scored_asset = asset.score(geo)

        assert scored_asset.last_scored_at is not None
        assert asset.last_scored_at is None

    def test_original_asset_unchanged(self) -> None:
        """The original asset is not modified (frozen dataclass)."""
        asset = _make_asset()
        geo = _make_geo_score()

        _ = asset.score(geo)

        assert asset.geo_score is None
        assert asset.last_scored_at is None
        assert len(asset.domain_events) == 0


class TestContentAssetAddSuggestions:
    """Test ContentAsset.add_suggestions() produces new instances with events."""

    def test_add_suggestions_returns_new_instance(self) -> None:
        """Adding suggestions returns a new instance."""
        asset = _make_asset()
        suggestion = RewriteSuggestion(
            id="sug-1",
            asset_id=asset.id,
            original_text="generic text",
            suggested_text="specific brand text",
            factor=GEOFactor.ENTITY_DENSITY,
            expected_impact=Score(value=15.0),
            rationale="Improve entity density.",
        )

        updated = asset.add_suggestions((suggestion,))

        assert updated is not asset
        assert len(updated.suggestions) == 1
        assert len(asset.suggestions) == 0

    def test_add_suggestions_records_events(self) -> None:
        """Each suggestion generates a RewriteSuggestionGenerated event."""
        asset = _make_asset()
        suggestions = (
            RewriteSuggestion(
                id="sug-1",
                asset_id=asset.id,
                original_text="text1",
                suggested_text="improved1",
                factor=GEOFactor.ENTITY_DENSITY,
                expected_impact=Score(value=10.0),
                rationale="Reason 1.",
            ),
            RewriteSuggestion(
                id="sug-2",
                asset_id=asset.id,
                original_text="text2",
                suggested_text="improved2",
                factor=GEOFactor.ANSWER_SHAPE,
                expected_impact=Score(value=20.0),
                rationale="Reason 2.",
            ),
        )

        updated = asset.add_suggestions(suggestions)

        assert len(updated.domain_events) == 2
        for event in updated.domain_events:
            assert isinstance(event, RewriteSuggestionGenerated)


class TestContentChunkImmutability:
    """Test ContentChunk immutability."""

    def test_chunk_is_frozen(self) -> None:
        """ContentChunk cannot be mutated after creation."""
        chunk = ContentChunk(
            chunk_id="chunk-1",
            text="Some text content",
            token_count=4,
            key_facts=("Fact 1",),
            embedding_quality=Score(value=75.0),
        )

        with pytest.raises(AttributeError):
            chunk.text = "Modified text"  # type: ignore[misc]

    def test_chunk_key_facts_tuple(self) -> None:
        """ContentChunk key_facts is a tuple (immutable)."""
        chunk = ContentChunk(
            chunk_id="chunk-1",
            text="Some text",
            token_count=2,
            key_facts=("Fact A", "Fact B"),
            embedding_quality=Score(value=50.0),
        )

        assert isinstance(chunk.key_facts, tuple)
        assert len(chunk.key_facts) == 2


class TestGEOScoreImmutability:
    """Test GEOScore immutability."""

    def test_geo_score_is_frozen(self) -> None:
        """GEOScore cannot be mutated after creation."""
        geo = _make_geo_score()

        with pytest.raises(AttributeError):
            geo.overall = Score(value=99.0)  # type: ignore[misc]
