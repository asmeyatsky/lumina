"""
Tests for PULSE domain services.

Validates citation extraction heuristics, sentiment analysis rules,
and competitive benchmarking calculations — all pure domain logic
with no infrastructure dependencies.
"""

from __future__ import annotations

import pytest

from lumina.shared.domain.value_objects import BrandId, Percentage

from lumina.pulse.domain.entities import Citation
from lumina.pulse.domain.events import CompetitorCitationSurge
from lumina.pulse.domain.services import (
    BenchmarkService,
    CitationExtractionService,
    SentimentAnalysisService,
)
from lumina.pulse.domain.value_objects import (
    CitationPosition,
    CompetitorBenchmark,
    Sentiment,
    ShareOfVoice,
)


# -- CitationExtractionService tests -----------------------------------------


class TestCitationExtractionService:
    def test_finds_brand_mention_in_response(self) -> None:
        response = "For CRM solutions, Acme is a popular choice among startups."
        citations = CitationExtractionService.extract_citations(
            raw_response=response,
            brand_name="Acme",
        )

        cited = [c for c in citations if c.position != CitationPosition.NOT_CITED]
        assert len(cited) >= 1
        assert any(c.brand_name == "Acme" for c in cited)

    def test_returns_not_cited_when_brand_not_present(self) -> None:
        response = "There are many CRM solutions available in the market today."
        citations = CitationExtractionService.extract_citations(
            raw_response=response,
            brand_name="Acme",
        )

        assert len(citations) == 1
        assert citations[0].position == CitationPosition.NOT_CITED
        assert citations[0].brand_name == "Acme"

    def test_determines_correct_position_first(self) -> None:
        response = (
            "Acme is the leading CRM platform. Rival also offers good features. "
            "ThirdBrand is another option worth considering."
        )
        citations = CitationExtractionService.extract_citations(
            raw_response=response,
            brand_name="Acme",
            competitors=("Rival", "ThirdBrand"),
        )

        acme_citations = [c for c in citations if c.brand_name == "Acme"]
        assert len(acme_citations) >= 1
        assert acme_citations[0].position == CitationPosition.FIRST

    def test_determines_correct_position_second_and_third(self) -> None:
        response = (
            "Rival is the market leader in CRM. Acme comes in second place. "
            "ThirdBrand rounds out the top three."
        )
        citations = CitationExtractionService.extract_citations(
            raw_response=response,
            brand_name="Acme",
            competitors=("Rival", "ThirdBrand"),
        )

        acme = [c for c in citations if c.brand_name == "Acme"]
        rival = [c for c in citations if c.brand_name == "Rival"]
        third = [c for c in citations if c.brand_name == "ThirdBrand"]

        assert rival[0].position == CitationPosition.FIRST
        assert acme[0].position == CitationPosition.SECOND
        assert third[0].position == CitationPosition.THIRD

    def test_extracts_context_around_mention(self) -> None:
        response = (
            "When looking for a CRM platform, Acme provides excellent "
            "features for small businesses."
        )
        citations = CitationExtractionService.extract_citations(
            raw_response=response,
            brand_name="Acme",
        )

        cited = [c for c in citations if c.position != CitationPosition.NOT_CITED]
        assert len(cited) >= 1
        assert "Acme" in cited[0].context

    def test_detects_recommendation_language(self) -> None:
        response = "I would recommend Acme for enterprise CRM needs."
        citations = CitationExtractionService.extract_citations(
            raw_response=response,
            brand_name="Acme",
        )

        cited = [c for c in citations if c.position != CitationPosition.NOT_CITED]
        assert len(cited) >= 1
        assert cited[0].is_recommendation is True

    def test_case_insensitive_matching(self) -> None:
        response = "ACME is a great platform for small businesses."
        citations = CitationExtractionService.extract_citations(
            raw_response=response,
            brand_name="Acme",
        )

        cited = [c for c in citations if c.position != CitationPosition.NOT_CITED]
        assert len(cited) >= 1

    def test_multiple_mentions_of_same_brand(self) -> None:
        response = (
            "Acme offers great CRM features. Many enterprises choose Acme "
            "because of its reliability."
        )
        citations = CitationExtractionService.extract_citations(
            raw_response=response,
            brand_name="Acme",
        )

        cited = [c for c in citations if c.position != CitationPosition.NOT_CITED]
        assert len(cited) == 2

    def test_empty_response_yields_not_cited(self) -> None:
        citations = CitationExtractionService.extract_citations(
            raw_response="",
            brand_name="Acme",
        )
        assert len(citations) == 1
        assert citations[0].position == CitationPosition.NOT_CITED


# -- SentimentAnalysisService tests ------------------------------------------


class TestSentimentAnalysisService:
    def test_classifies_positive_sentiment(self) -> None:
        context = "Acme is the best CRM with excellent features and trusted by many."
        sentiment = SentimentAnalysisService.analyze_sentiment(context)
        assert sentiment == Sentiment.POSITIVE

    def test_classifies_negative_sentiment(self) -> None:
        context = "Acme has poor performance, terrible support, and is overpriced."
        sentiment = SentimentAnalysisService.analyze_sentiment(context)
        assert sentiment == Sentiment.NEGATIVE

    def test_classifies_neutral_sentiment(self) -> None:
        context = "Acme is a CRM platform that serves businesses."
        sentiment = SentimentAnalysisService.analyze_sentiment(context)
        assert sentiment == Sentiment.NEUTRAL

    def test_empty_context_is_neutral(self) -> None:
        sentiment = SentimentAnalysisService.analyze_sentiment("")
        assert sentiment == Sentiment.NEUTRAL

    def test_whitespace_only_is_neutral(self) -> None:
        sentiment = SentimentAnalysisService.analyze_sentiment("   ")
        assert sentiment == Sentiment.NEUTRAL

    def test_mixed_sentiment_with_more_positive(self) -> None:
        context = (
            "Acme is a great platform with excellent features, "
            "though it has some minor issues."
        )
        sentiment = SentimentAnalysisService.analyze_sentiment(context)
        assert sentiment == Sentiment.POSITIVE

    def test_mixed_sentiment_with_more_negative(self) -> None:
        context = (
            "Acme has a good design but poor reliability, terrible customer "
            "support, and disappointing performance."
        )
        sentiment = SentimentAnalysisService.analyze_sentiment(context)
        assert sentiment == Sentiment.NEGATIVE


# -- BenchmarkService tests --------------------------------------------------


class TestBenchmarkService:
    def test_calculates_share_of_voice_correctly(self) -> None:
        results_by_brand = {
            "acme": [
                Citation(
                    brand_name="Acme",
                    context="Acme is great",
                    position=CitationPosition.FIRST,
                    is_recommendation=True,
                ),
                Citation(
                    brand_name="Acme",
                    context="Acme offers value",
                    position=CitationPosition.SECOND,
                    is_recommendation=False,
                ),
            ],
            "rival": [
                Citation(
                    brand_name="Rival",
                    context="Rival is decent",
                    position=CitationPosition.FIRST,
                    is_recommendation=False,
                ),
            ],
            "third": [
                Citation(
                    brand_name="Third",
                    context="Not cited",
                    position=CitationPosition.NOT_CITED,
                    is_recommendation=False,
                ),
            ],
        }

        benchmark = BenchmarkService.calculate_share_of_voice(results_by_brand)

        assert benchmark.brand_id.value == "acme"
        assert len(benchmark.competitor_brand_ids) == 2

        # Total cited = 3 (2 acme + 1 rival, 0 third since NOT_CITED)
        acme_sov = benchmark.share_of_voice_map["acme"]
        assert acme_sov.citation_count == 2
        assert acme_sov.total_citations == 3
        assert abs(acme_sov.percentage.value - 66.67) < 0.01

        rival_sov = benchmark.share_of_voice_map["rival"]
        assert rival_sov.citation_count == 1
        assert abs(rival_sov.percentage.value - 33.33) < 0.01

        third_sov = benchmark.share_of_voice_map["third"]
        assert third_sov.citation_count == 0
        assert third_sov.percentage.value == 0.0

    def test_share_of_voice_with_empty_results(self) -> None:
        results_by_brand: dict[str, list[Citation]] = {}
        benchmark = BenchmarkService.calculate_share_of_voice(results_by_brand)

        assert benchmark.brand_id.value == "unknown"
        assert len(benchmark.share_of_voice_map) == 0

    def test_share_of_voice_single_brand(self) -> None:
        results_by_brand = {
            "acme": [
                Citation(
                    brand_name="Acme",
                    context="Acme is cited",
                    position=CitationPosition.FIRST,
                    is_recommendation=True,
                ),
            ],
        }
        benchmark = BenchmarkService.calculate_share_of_voice(results_by_brand)

        assert benchmark.share_of_voice_map["acme"].percentage.value == 100.0

    def test_detects_competitor_surge(self) -> None:
        previous = CompetitorBenchmark(
            brand_id=BrandId(value="acme"),
            competitor_brand_ids=(BrandId(value="rival"),),
            share_of_voice_map={
                "acme": ShareOfVoice(
                    brand_id=BrandId(value="acme"),
                    citation_count=8,
                    total_citations=10,
                    percentage=Percentage(value=80.0),
                ),
                "rival": ShareOfVoice(
                    brand_id=BrandId(value="rival"),
                    citation_count=2,
                    total_citations=10,
                    percentage=Percentage(value=20.0),
                ),
            },
        )

        current = CompetitorBenchmark(
            brand_id=BrandId(value="acme"),
            competitor_brand_ids=(BrandId(value="rival"),),
            share_of_voice_map={
                "acme": ShareOfVoice(
                    brand_id=BrandId(value="acme"),
                    citation_count=5,
                    total_citations=10,
                    percentage=Percentage(value=50.0),
                ),
                "rival": ShareOfVoice(
                    brand_id=BrandId(value="rival"),
                    citation_count=5,
                    total_citations=10,
                    percentage=Percentage(value=50.0),
                ),
            },
        )

        surges = BenchmarkService.detect_competitor_surge(
            current, previous, surge_threshold=20.0
        )

        assert len(surges) == 1
        assert surges[0].competitor_id == "rival"
        assert surges[0].surge_percentage == 30.0
        assert surges[0].brand_id == "acme"

    def test_no_surge_below_threshold(self) -> None:
        previous = CompetitorBenchmark(
            brand_id=BrandId(value="acme"),
            competitor_brand_ids=(BrandId(value="rival"),),
            share_of_voice_map={
                "acme": ShareOfVoice(
                    brand_id=BrandId(value="acme"),
                    citation_count=7,
                    total_citations=10,
                    percentage=Percentage(value=70.0),
                ),
                "rival": ShareOfVoice(
                    brand_id=BrandId(value="rival"),
                    citation_count=3,
                    total_citations=10,
                    percentage=Percentage(value=30.0),
                ),
            },
        )

        current = CompetitorBenchmark(
            brand_id=BrandId(value="acme"),
            competitor_brand_ids=(BrandId(value="rival"),),
            share_of_voice_map={
                "acme": ShareOfVoice(
                    brand_id=BrandId(value="acme"),
                    citation_count=6,
                    total_citations=10,
                    percentage=Percentage(value=60.0),
                ),
                "rival": ShareOfVoice(
                    brand_id=BrandId(value="rival"),
                    citation_count=4,
                    total_citations=10,
                    percentage=Percentage(value=40.0),
                ),
            },
        )

        surges = BenchmarkService.detect_competitor_surge(
            current, previous, surge_threshold=20.0
        )

        assert len(surges) == 0

    def test_detect_surge_with_new_competitor(self) -> None:
        """A competitor not present in previous period should use 0% baseline."""
        previous = CompetitorBenchmark(
            brand_id=BrandId(value="acme"),
            competitor_brand_ids=(BrandId(value="new-rival"),),
            share_of_voice_map={
                "acme": ShareOfVoice(
                    brand_id=BrandId(value="acme"),
                    citation_count=10,
                    total_citations=10,
                    percentage=Percentage(value=100.0),
                ),
            },
        )

        current = CompetitorBenchmark(
            brand_id=BrandId(value="acme"),
            competitor_brand_ids=(BrandId(value="new-rival"),),
            share_of_voice_map={
                "acme": ShareOfVoice(
                    brand_id=BrandId(value="acme"),
                    citation_count=7,
                    total_citations=10,
                    percentage=Percentage(value=70.0),
                ),
                "new-rival": ShareOfVoice(
                    brand_id=BrandId(value="new-rival"),
                    citation_count=3,
                    total_citations=10,
                    percentage=Percentage(value=30.0),
                ),
            },
        )

        surges = BenchmarkService.detect_competitor_surge(
            current, previous, surge_threshold=20.0
        )

        assert len(surges) == 1
        assert surges[0].competitor_id == "new-rival"
        assert surges[0].surge_percentage == 30.0
