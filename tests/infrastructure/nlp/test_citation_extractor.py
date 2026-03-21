"""
Tests for ML-powered citation extraction.

Tests cover brand mention extraction, citation position determination,
handling of absent brands, multiple mentions, and API failure fallback.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from lumina.infrastructure.nlp.citation_extractor import MLCitationExtractor
from lumina.pulse.domain.value_objects import CitationPosition


# ---------------------------------------------------------------------------
# Fixtures: mock Anthropic client
# ---------------------------------------------------------------------------

@dataclass
class _MockContent:
    text: str


@dataclass
class _MockResponse:
    content: list[_MockContent]


def _make_client(response_json: list[dict[str, Any]]) -> AsyncMock:
    """Create a mock Anthropic client that returns the given JSON."""
    client = AsyncMock()
    client.messages.create = AsyncMock(
        return_value=_MockResponse(
            content=[_MockContent(text=json.dumps(response_json))]
        )
    )
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMLCitationExtractor:
    """Tests for MLCitationExtractor."""

    @pytest.mark.asyncio
    async def test_extracts_brand_mention_from_ai_response(self) -> None:
        """The extractor should identify a brand mention with context."""
        api_response = [
            {
                "brand_name": "Acme",
                "context": "Acme is a leading provider of cloud services.",
                "position": "first",
                "is_recommendation": True,
                "sentiment": "positive",
            }
        ]
        client = _make_client(api_response)
        extractor = MLCitationExtractor(anthropic_client=client)

        citations = await extractor.extract_citations_ml(
            response="Acme is a leading provider of cloud services.",
            brand="Acme",
            competitors=(),
        )

        assert len(citations) == 1
        assert citations[0].brand_name == "Acme"
        assert "leading provider" in citations[0].context
        assert citations[0].position == CitationPosition.FIRST
        assert citations[0].is_recommendation is True

    @pytest.mark.asyncio
    async def test_determines_correct_citation_position(self) -> None:
        """The extractor should assign correct ordinal positions."""
        api_response = [
            {
                "brand_name": "AlphaCorp",
                "context": "AlphaCorp leads the market.",
                "position": "first",
                "is_recommendation": False,
                "sentiment": "positive",
            },
            {
                "brand_name": "BetaInc",
                "context": "BetaInc is a strong alternative.",
                "position": "second",
                "is_recommendation": False,
                "sentiment": "neutral",
            },
            {
                "brand_name": "GammaCo",
                "context": "GammaCo offers budget options.",
                "position": "third",
                "is_recommendation": False,
                "sentiment": "neutral",
            },
        ]
        client = _make_client(api_response)
        extractor = MLCitationExtractor(anthropic_client=client)

        citations = await extractor.extract_citations_ml(
            response="AlphaCorp leads the market. BetaInc is a strong alternative. GammaCo offers budget options.",
            brand="AlphaCorp",
            competitors=("BetaInc", "GammaCo"),
        )

        assert len(citations) == 3
        assert citations[0].position == CitationPosition.FIRST
        assert citations[1].position == CitationPosition.SECOND
        assert citations[2].position == CitationPosition.THIRD

    @pytest.mark.asyncio
    async def test_handles_response_with_no_brand_mention(self) -> None:
        """When the brand is not found, it should be marked NOT_CITED."""
        api_response = [
            {
                "brand_name": "Acme",
                "context": "",
                "position": "not_cited",
                "is_recommendation": False,
                "sentiment": "neutral",
            }
        ]
        client = _make_client(api_response)
        extractor = MLCitationExtractor(anthropic_client=client)

        citations = await extractor.extract_citations_ml(
            response="The weather is nice today.",
            brand="Acme",
            competitors=(),
        )

        assert len(citations) == 1
        assert citations[0].brand_name == "Acme"
        assert citations[0].position == CitationPosition.NOT_CITED
        assert citations[0].context == ""

    @pytest.mark.asyncio
    async def test_handles_multiple_brand_mentions(self) -> None:
        """The extractor should handle multiple mentions of the same brand."""
        api_response = [
            {
                "brand_name": "Acme",
                "context": "Acme offers great products.",
                "position": "first",
                "is_recommendation": True,
                "sentiment": "positive",
            },
            {
                "brand_name": "Acme",
                "context": "Acme also provides excellent support.",
                "position": "first",
                "is_recommendation": False,
                "sentiment": "positive",
            },
        ]
        client = _make_client(api_response)
        extractor = MLCitationExtractor(anthropic_client=client)

        citations = await extractor.extract_citations_ml(
            response="Acme offers great products. Acme also provides excellent support.",
            brand="Acme",
            competitors=(),
        )

        assert len(citations) == 2
        assert all(c.brand_name == "Acme" for c in citations)

    @pytest.mark.asyncio
    async def test_fallback_to_rule_based_on_api_failure(self) -> None:
        """When the API call fails, fall back to rule-based extraction."""
        client = AsyncMock()
        client.messages.create = AsyncMock(
            side_effect=RuntimeError("API unavailable")
        )
        extractor = MLCitationExtractor(anthropic_client=client)

        citations = await extractor.extract_citations_ml(
            response="Acme is the best choice for cloud computing.",
            brand="Acme",
            competitors=("BetaCorp",),
        )

        # Should still find Acme via rule-based fallback
        acme_citations = [c for c in citations if c.brand_name == "Acme"]
        assert len(acme_citations) >= 1
        assert acme_citations[0].position != CitationPosition.NOT_CITED

    @pytest.mark.asyncio
    async def test_caches_results(self) -> None:
        """Subsequent calls with the same input should use the cache."""
        api_response = [
            {
                "brand_name": "Acme",
                "context": "Acme is great.",
                "position": "first",
                "is_recommendation": False,
                "sentiment": "positive",
            }
        ]
        client = _make_client(api_response)
        extractor = MLCitationExtractor(anthropic_client=client)

        # First call hits the API
        result1 = await extractor.extract_citations_ml(
            response="Acme is great.",
            brand="Acme",
            competitors=(),
        )

        # Second call should use cache
        result2 = await extractor.extract_citations_ml(
            response="Acme is great.",
            brand="Acme",
            competitors=(),
        )

        assert result1 == result2
        # API should only be called once
        assert client.messages.create.call_count == 1
