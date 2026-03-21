"""
ML-powered citation extraction using Claude API.

Implements CitationNLPPort to provide high-accuracy citation extraction
from AI engine responses. Falls back to the rule-based CitationExtractionService
when the API call fails.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from typing import Any

from lumina.pulse.domain.entities import Citation
from lumina.pulse.domain.services import CitationExtractionService
from lumina.pulse.domain.value_objects import CitationPosition, Sentiment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

CITATION_EXTRACTION_PROMPT = """\
You are a citation analysis expert. Analyse the following AI engine response \
and extract all brand citations.

**Brand to track:** {brand}
**Competitors to detect:** {competitors}

**AI Response to analyse:**
{response}

For each brand or competitor mentioned, extract:
1. brand_name: The exact brand name as it appears
2. context: The surrounding sentence or passage (50-200 chars)
3. position: The ordinal position of first appearance among all brands \
(first, second, third, or mentioned)
4. is_recommendation: Whether the text recommends this brand (true/false)
5. sentiment: The sentiment toward this brand in context \
(positive, neutral, negative)

Return a JSON array of objects. If a brand or competitor is NOT mentioned, \
include it with position "not_cited" and empty context.

Return ONLY the JSON array, no other text.
"""

CITATION_EXTRACTION_SYSTEM = (
    "You are a precise citation extraction engine. "
    "Return only valid JSON arrays. Never add commentary."
)


# ---------------------------------------------------------------------------
# LRU cache for API results
# ---------------------------------------------------------------------------

class _LRUCache:
    """Simple LRU cache backed by an OrderedDict."""

    def __init__(self, max_size: int = 256) -> None:
        self._cache: OrderedDict[str, list[Citation]] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> list[Citation] | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, value: list[Citation]) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
        self._cache[key] = value


# ---------------------------------------------------------------------------
# Position string -> CitationPosition mapping
# ---------------------------------------------------------------------------

_POSITION_MAP: dict[str, CitationPosition] = {
    "first": CitationPosition.FIRST,
    "second": CitationPosition.SECOND,
    "third": CitationPosition.THIRD,
    "mentioned": CitationPosition.MENTIONED,
    "not_cited": CitationPosition.NOT_CITED,
}


def _parse_position(raw: str) -> CitationPosition:
    """Convert a position string from the LLM response to a CitationPosition."""
    return _POSITION_MAP.get(raw.lower().strip(), CitationPosition.MENTIONED)


def _parse_sentiment(raw: str) -> Sentiment:
    """Convert a sentiment string from the LLM response to a Sentiment."""
    normalised = raw.lower().strip()
    if normalised == "positive":
        return Sentiment.POSITIVE
    if normalised == "negative":
        return Sentiment.NEGATIVE
    return Sentiment.NEUTRAL


# ---------------------------------------------------------------------------
# MLCitationExtractor — implements CitationNLPPort
# ---------------------------------------------------------------------------

class MLCitationExtractor:
    """ML-powered citation extraction using Claude via the Anthropic SDK.

    Satisfies the ``CitationNLPPort`` protocol defined in
    ``lumina.pulse.domain.ports``.

    Parameters
    ----------
    anthropic_client:
        An instantiated ``anthropic.AsyncAnthropic`` client.
    model:
        The Claude model identifier to use.
    cache_size:
        Maximum number of cached extraction results.
    """

    def __init__(
        self,
        anthropic_client: Any,
        model: str = "claude-sonnet-4-20250514",
        cache_size: int = 256,
    ) -> None:
        self._client = anthropic_client
        self._model = model
        self._cache = _LRUCache(max_size=cache_size)
        self._rule_based = CitationExtractionService()

    # -- Cache key -----------------------------------------------------------

    @staticmethod
    def _cache_key(response: str, brand: str, competitors: tuple[str, ...]) -> str:
        raw = f"{brand}|{'|'.join(competitors)}|{response}"
        return hashlib.sha256(raw.encode()).hexdigest()

    # -- Public API (CitationNLPPort) ----------------------------------------

    async def extract_citations_ml(
        self,
        response: str,
        brand: str,
        competitors: tuple[str, ...],
    ) -> list[Citation]:
        """Extract citations using Claude for structured extraction.

        Falls back to rule-based extraction if the API call fails.
        """
        # Check cache first
        key = self._cache_key(response, brand, competitors)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            citations = await self._extract_via_api(response, brand, competitors)
            self._cache.put(key, citations)
            return citations
        except Exception:
            logger.warning(
                "ML citation extraction failed, falling back to rule-based",
                exc_info=True,
            )
            return self._fallback(response, brand, competitors)

    # -- Private helpers -----------------------------------------------------

    async def _extract_via_api(
        self,
        response: str,
        brand: str,
        competitors: tuple[str, ...],
    ) -> list[Citation]:
        """Call Claude API with the extraction prompt and parse the result."""
        competitors_str = ", ".join(competitors) if competitors else "(none)"
        user_prompt = CITATION_EXTRACTION_PROMPT.format(
            brand=brand,
            competitors=competitors_str,
            response=response,
        )

        api_response = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=CITATION_EXTRACTION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_text = api_response.content[0].text
        parsed = self._parse_api_response(raw_text)
        return parsed

    @staticmethod
    def _parse_api_response(raw_text: str) -> list[Citation]:
        """Parse the JSON array returned by Claude into Citation objects."""
        # Strip markdown code fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last line (code fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        items: list[dict[str, Any]] = json.loads(text)

        citations: list[Citation] = []
        for item in items:
            brand_name = item.get("brand_name", "").strip()
            if not brand_name:
                continue

            position = _parse_position(item.get("position", "mentioned"))
            context = item.get("context", "").strip()
            is_recommendation = bool(item.get("is_recommendation", False))

            # For NOT_CITED entries, context can be empty
            if position == CitationPosition.NOT_CITED:
                context = ""

            # Skip entries with no context and non-NOT_CITED position
            if not context and position != CitationPosition.NOT_CITED:
                continue

            citations.append(
                Citation(
                    brand_name=brand_name,
                    context=context,
                    position=position,
                    is_recommendation=is_recommendation,
                    source_url=None,
                )
            )

        return citations

    def _fallback(
        self,
        response: str,
        brand: str,
        competitors: tuple[str, ...],
    ) -> list[Citation]:
        """Fall back to rule-based extraction."""
        results = CitationExtractionService.extract_citations(
            raw_response=response,
            brand_name=brand,
            competitors=competitors,
        )
        return list(results)
