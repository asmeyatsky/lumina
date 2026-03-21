"""
Tests for fact extraction.

Tests cover statistic extraction, date extraction, verifiability
scoring, and handling of content with no factual claims.
"""

from __future__ import annotations

import pytest

from lumina.infrastructure.nlp.fact_extractor import (
    ExtractedFact,
    FactExtractor,
    FactType,
)


class TestFactExtractor:
    """Tests for FactExtractor."""

    def test_extracts_statistics(self) -> None:
        """Sentences with statistics/numbers should be extracted as facts."""
        extractor = FactExtractor()

        text = (
            "The company grew by 45% in 2024. "
            "Revenue reached $2.5 billion last quarter. "
            "This represents a significant milestone."
        )
        facts = extractor.extract_facts(text)

        stat_facts = [f for f in facts if f.fact_type == FactType.STATISTIC]
        assert len(stat_facts) >= 1
        assert any(f.has_number for f in stat_facts)

    def test_extracts_dates(self) -> None:
        """Sentences with dates should be extracted as facts."""
        extractor = FactExtractor()

        text = (
            "The product was launched on January 15, 2024. "
            "The next update is scheduled for Q2 2025. "
            "Users have enjoyed the new features."
        )
        facts = extractor.extract_facts(text)

        # At least one fact should have a date
        date_facts = [f for f in facts if f.has_date]
        assert len(date_facts) >= 1

    def test_scores_verifiability(self) -> None:
        """Facts with more signals should have higher verifiability scores."""
        extractor = FactExtractor()

        # This sentence has a number, date, and source attribution
        text_high = (
            "According to Gartner, the market grew by 30% in January 2024."
        )
        # This has only a number
        text_low = "The product has over 1,000 users."

        facts_high = extractor.extract_facts(text_high)
        facts_low = extractor.extract_facts(text_low)

        assert len(facts_high) >= 1
        assert len(facts_low) >= 1

        # The sentence with all three signals should score higher
        assert facts_high[0].verifiability_score > facts_low[0].verifiability_score

    def test_handles_content_with_no_facts(self) -> None:
        """Content without verifiable facts should return an empty list."""
        extractor = FactExtractor()

        text = (
            "This is a wonderful day. "
            "The sky looks beautiful. "
            "Everyone seems happy."
        )
        facts = extractor.extract_facts(text)
        assert facts == []

    def test_citability_score(self) -> None:
        """Citability score should be higher for fact-rich content."""
        extractor = FactExtractor()

        fact_rich = (
            "According to McKinsey, 75% of companies adopted AI by 2024. "
            "Revenue grew by $3.2 billion in Q3 2024. "
            "Dr. Smith published the findings on 2024-06-15."
        )
        fact_poor = (
            "Things are going well. "
            "People are optimistic about the future. "
            "The team is working hard."
        )

        score_rich = extractor.compute_citability_score(fact_rich)
        score_poor = extractor.compute_citability_score(fact_poor)

        assert score_rich > score_poor
        assert score_rich > 0.0
        assert score_poor == 0.0

    def test_extracts_named_sources(self) -> None:
        """Sentences with source attributions should be extracted."""
        extractor = FactExtractor()

        text = (
            "According to Bloomberg, the market is shifting. "
            "A study by Harvard found that AI adoption is accelerating."
        )
        facts = extractor.extract_facts(text)

        source_facts = [f for f in facts if f.has_source]
        assert len(source_facts) >= 1

    def test_handles_empty_content(self) -> None:
        """Empty content should return no facts."""
        extractor = FactExtractor()
        assert extractor.extract_facts("") == []
        assert extractor.extract_facts("   ") == []
        assert extractor.compute_citability_score("") == 0.0
