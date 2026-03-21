"""
BEAM Domain Service Tests

Tests for GEOScoringService, RAGSimulationService, and RewriteService.
All tests are pure domain tests with no infrastructure dependencies.
"""

from __future__ import annotations

import pytest

from lumina.shared.domain.value_objects import BrandId, Score, URL

from lumina.beam.domain.entities import ContentAsset, GEOScore
from lumina.beam.domain.services import GEOScoringService, RAGSimulationService, RewriteService
from lumina.beam.domain.value_objects import ContentType, GEOFactor


class TestGEOScoringServiceEntityDensity:
    """Test GEOScoringService.score_entity_density with various entity counts."""

    def test_empty_content_returns_zero(self) -> None:
        """Empty content scores zero for entity density."""
        score = GEOScoringService.score_entity_density("", ["Brand"])
        assert score.value == 0.0

    def test_no_entities_returns_zero(self) -> None:
        """No entities list scores zero."""
        score = GEOScoringService.score_entity_density("Some content", [])
        assert score.value == 0.0

    def test_no_entity_matches_returns_zero(self) -> None:
        """Content with no matching entities scores zero."""
        score = GEOScoringService.score_entity_density(
            "This is generic content with no brand mentions.",
            ["Acme Corp", "WidgetPro"],
        )
        assert score.value == 0.0

    def test_high_entity_density(self) -> None:
        """Content with many entity mentions scores high."""
        content = (
            "Acme Corp is a leading provider. Acme Corp offers innovative solutions. "
            "The Acme Corp platform integrates with WidgetPro seamlessly. "
            "WidgetPro users love WidgetPro features. Acme Corp and WidgetPro together."
        )
        score = GEOScoringService.score_entity_density(
            content, ["Acme Corp", "WidgetPro"]
        )
        assert score.value > 50.0

    def test_single_entity_partial_coverage(self) -> None:
        """Content mentioning only one of multiple entities gets partial score."""
        content = "Acme Corp is great. Acme Corp leads the industry."
        score = GEOScoringService.score_entity_density(
            content, ["Acme Corp", "WidgetPro", "DataFlow"]
        )
        assert 0.0 < score.value < 100.0

    def test_case_insensitive_matching(self) -> None:
        """Entity matching is case-insensitive."""
        content = "acme corp builds great products. ACME CORP is innovative."
        score = GEOScoringService.score_entity_density(content, ["Acme Corp"])
        assert score.value > 0.0


class TestGEOScoringServiceAnswerShape:
    """Test GEOScoringService.score_answer_shape with Q&A vs narrative content."""

    def test_empty_content_returns_zero(self) -> None:
        """Empty content scores zero for answer shape."""
        score = GEOScoringService.score_answer_shape("")
        assert score.value == 0.0

    def test_qa_format_scores_higher(self) -> None:
        """Q&A-formatted content scores higher than pure narrative."""
        qa_content = """## What is LUMINA?

LUMINA is an AI Visibility Platform. In short, it helps brands be the answer.

## How does it work?

- It monitors AI engines
- It scores content for GEO factors
- It provides optimisation recommendations

## Why use LUMINA?

To summarize, LUMINA ensures your brand appears in AI-generated answers."""

        narrative_content = (
            "The company was founded in 2020. It grew rapidly over the next few years. "
            "The product was well received by the market and gained significant traction. "
            "Customers reported high satisfaction with the platform and its capabilities."
        )

        qa_score = GEOScoringService.score_answer_shape(qa_content)
        narrative_score = GEOScoringService.score_answer_shape(narrative_content)

        assert qa_score.value > narrative_score.value

    def test_list_content_scores_well(self) -> None:
        """Content with lists and structure scores well."""
        content = """## Key Features

1. Real-time monitoring
2. AI engine coverage
3. GEO scoring

- Dashboard analytics
- Custom reports
- API access"""

        score = GEOScoringService.score_answer_shape(content)
        assert score.value > 0.0

    def test_returns_valid_score(self) -> None:
        """Answer shape score is always between 0 and 100."""
        score = GEOScoringService.score_answer_shape("Some content.")
        assert 0.0 <= score.value <= 100.0


class TestGEOScoringServiceFactCitability:
    """Test fact citability scoring."""

    def test_content_with_numbers_and_dates(self) -> None:
        """Content with numbers, dates, and sources scores well."""
        content = (
            "According to a 2024 study, 85% of users prefer AI-generated answers. "
            "Dr. Smith found that response accuracy improved by 23% in March 2024. "
            "The report, published on 2024-01-15, surveyed 10,000 participants."
        )
        score = GEOScoringService.score_fact_citability(content)
        assert score.value > 30.0

    def test_vague_content_scores_low(self) -> None:
        """Content without specific facts scores low."""
        content = (
            "The product is really good. Many people like it. "
            "It has great features and works well."
        )
        score = GEOScoringService.score_fact_citability(content)
        assert score.value < 20.0


class TestGEOScoringServiceFreshness:
    """Test freshness signal scoring."""

    def test_content_with_dates_and_updates(self) -> None:
        """Content with dates and update indicators scores well."""
        content = (
            "Last updated: January 2025. "
            "As of 2025-01-15, the latest data shows significant improvements. "
            "This year, the platform has seen a 40% increase in adoption."
        )
        score = GEOScoringService.score_freshness(content)
        assert score.value > 30.0

    def test_timeless_content_scores_low(self) -> None:
        """Content without temporal signals scores low."""
        content = (
            "The product is useful. It helps businesses grow. "
            "Teams find it valuable for their work."
        )
        score = GEOScoringService.score_freshness(content)
        assert score.value < 20.0


class TestGEOScoringServiceCalculateGEOScore:
    """Test the full GEO score calculation."""

    def test_calculate_returns_geo_score(self) -> None:
        """calculate_geo_score returns a fully populated GEOScore."""
        content = (
            "## What does Acme Corp offer?\n\n"
            "Acme Corp provides innovative solutions. According to research, "
            "95% of customers are satisfied. Updated January 2025.\n\n"
            "1. Feature one\n2. Feature two\n3. Feature three"
        )
        score = GEOScoringService.calculate_geo_score(content, ["Acme Corp"])

        assert isinstance(score, GEOScore)
        assert isinstance(score.overall, Score)
        assert 0.0 <= score.overall.value <= 100.0
        assert score.overall.value > 0.0

    def test_overall_matches_weighted_calculation(self) -> None:
        """The overall score in the result matches weighted_overall()."""
        content = "Acme Corp is great. Acme Corp builds products."
        score = GEOScoringService.calculate_geo_score(content, ["Acme Corp"])

        expected_overall = score.weighted_overall()
        assert score.overall.value == expected_overall.value


class TestRAGSimulationServiceChunkContent:
    """Test RAGSimulationService.chunk_content."""

    def test_empty_content_returns_empty(self) -> None:
        """Empty content produces no chunks."""
        chunks = RAGSimulationService.chunk_content("")
        assert chunks == ()

    def test_produces_correct_number_of_chunks(self) -> None:
        """Content is split into the expected number of chunks."""
        words = ["word"] * 1000
        content = " ".join(words)

        chunks = RAGSimulationService.chunk_content(content, chunk_size=512)

        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.text
            assert chunk.token_count > 0
            assert chunk.chunk_id

    def test_small_content_single_chunk(self) -> None:
        """Small content fits in a single chunk."""
        content = "This is a short piece of content."
        chunks = RAGSimulationService.chunk_content(content, chunk_size=512)

        assert len(chunks) == 1
        assert chunks[0].text == content

    def test_chunk_has_embedding_quality(self) -> None:
        """Each chunk has an embedding quality score."""
        content = "This is a test with number 42 and some facts."
        chunks = RAGSimulationService.chunk_content(content, chunk_size=512)

        for chunk in chunks:
            assert isinstance(chunk.embedding_quality, Score)
            assert 0.0 <= chunk.embedding_quality.value <= 100.0


class TestRAGSimulationServiceExtractKeyFacts:
    """Test RAGSimulationService.extract_key_facts."""

    def test_empty_content_returns_empty(self) -> None:
        """Empty content produces no facts."""
        facts = RAGSimulationService.extract_key_facts("")
        assert facts == ()

    def test_finds_numeric_facts(self) -> None:
        """Extracts sentences containing numbers and statistics."""
        content = (
            "The company was founded in 2015. It has grown to 500 employees. "
            "Revenue increased by 45% last year. "
            "The sky is blue and the grass is green."
        )
        facts = RAGSimulationService.extract_key_facts(content)

        assert len(facts) >= 2
        assert any("500" in f or "45%" in f or "2015" in f for f in facts)

    def test_finds_sourced_claims(self) -> None:
        """Extracts sentences with source attributions."""
        content = (
            "According to the annual report, profits doubled. "
            "The weather was pleasant today."
        )
        facts = RAGSimulationService.extract_key_facts(content)

        assert len(facts) >= 1
        assert any("according to" in f.lower() for f in facts)


class TestRAGSimulationServiceSimulateRetrieval:
    """Test RAGSimulationService.simulate_retrieval."""

    def test_empty_chunks_returns_empty_result(self) -> None:
        """Empty chunks produce an empty simulation result."""
        result = RAGSimulationService.simulate_retrieval((), "test query")

        assert result.survivability_score.value == 0.0
        assert result.survived_facts == ()
        assert result.lost_facts == ()

    def test_simulation_identifies_survived_facts(self) -> None:
        """Facts in retrieved chunks are marked as survived."""
        content = (
            "The company earned 50 million in revenue. "
            "According to the CEO, growth was 25% year over year. "
            "The product launched in January 2024."
        )
        chunks = RAGSimulationService.chunk_content(content, chunk_size=512)
        result = RAGSimulationService.simulate_retrieval(chunks, "company revenue growth")

        assert isinstance(result.survivability_score, Score)
        assert 0.0 <= result.survivability_score.value <= 100.0


class TestRewriteServiceGenerateSuggestions:
    """Test RewriteService.generate_suggestions."""

    def _make_scored_asset(self, geo_score: GEOScore) -> ContentAsset:
        """Helper to create a scored ContentAsset."""
        asset = ContentAsset(
            id="asset-1",
            brand_id=BrandId(value="brand-1"),
            url=URL(value="https://example.com/page"),
            title="Test Page",
            raw_content="Some content for testing.",
            content_type=ContentType.WEB_PAGE,
        )
        return asset.score(geo_score)

    def test_targets_lowest_scoring_factors(self) -> None:
        """Suggestions target the lowest-scoring GEO factors."""
        geo = GEOScore(
            overall=Score(value=50.0),
            entity_density=Score(value=90.0),
            answer_shape=Score(value=85.0),
            fact_citability=Score(value=20.0),
            rag_survivability=Score(value=30.0),
            semantic_authority=Score(value=95.0),
            freshness_signals=Score(value=15.0),
        )
        asset = self._make_scored_asset(geo)

        suggestions = RewriteService.generate_suggestions(asset, geo)

        assert len(suggestions) > 0
        suggestion_factors = {s.factor for s in suggestions}
        assert GEOFactor.FRESHNESS_SIGNALS in suggestion_factors
        assert GEOFactor.FACT_CITABILITY in suggestion_factors

    def test_produces_valid_suggestions(self) -> None:
        """Each suggestion has all required fields populated."""
        geo = GEOScore(
            overall=Score(value=40.0),
            entity_density=Score(value=30.0),
            answer_shape=Score(value=40.0),
            fact_citability=Score(value=35.0),
            rag_survivability=Score(value=45.0),
            semantic_authority=Score(value=50.0),
            freshness_signals=Score(value=40.0),
        )
        asset = self._make_scored_asset(geo)

        suggestions = RewriteService.generate_suggestions(asset, geo)

        for suggestion in suggestions:
            assert suggestion.id
            assert suggestion.asset_id == asset.id
            assert suggestion.original_text
            assert suggestion.suggested_text
            assert isinstance(suggestion.factor, GEOFactor)
            assert isinstance(suggestion.expected_impact, Score)
            assert suggestion.rationale

    def test_high_scoring_asset_gets_fewer_suggestions(self) -> None:
        """Assets scoring well on most factors get fewer suggestions."""
        low_geo = GEOScore(
            overall=Score(value=30.0),
            entity_density=Score(value=20.0),
            answer_shape=Score(value=25.0),
            fact_citability=Score(value=30.0),
            rag_survivability=Score(value=35.0),
            semantic_authority=Score(value=40.0),
            freshness_signals=Score(value=30.0),
        )
        high_geo = GEOScore(
            overall=Score(value=85.0),
            entity_density=Score(value=90.0),
            answer_shape=Score(value=85.0),
            fact_citability=Score(value=82.0),
            rag_survivability=Score(value=88.0),
            semantic_authority=Score(value=92.0),
            freshness_signals=Score(value=80.0),
        )

        low_asset = self._make_scored_asset(low_geo)
        high_asset = self._make_scored_asset(high_geo)

        low_suggestions = RewriteService.generate_suggestions(low_asset, low_geo)
        high_suggestions = RewriteService.generate_suggestions(high_asset, high_geo)

        assert len(low_suggestions) > len(high_suggestions)

    def test_expected_impact_reflects_gap(self) -> None:
        """Expected impact is higher for factors with lower scores."""
        geo = GEOScore(
            overall=Score(value=40.0),
            entity_density=Score(value=10.0),
            answer_shape=Score(value=70.0),
            fact_citability=Score(value=10.0),
            rag_survivability=Score(value=70.0),
            semantic_authority=Score(value=70.0),
            freshness_signals=Score(value=70.0),
        )
        asset = self._make_scored_asset(geo)

        suggestions = RewriteService.generate_suggestions(asset, geo)

        entity_suggestions = [
            s for s in suggestions if s.factor == GEOFactor.ENTITY_DENSITY
        ]
        if entity_suggestions:
            assert entity_suggestions[0].expected_impact.value > 20.0
