"""
ML-powered sentiment analysis using Claude API.

Provides nuanced sentiment classification of citation contexts with
confidence scoring. Supports batch analysis for efficiency.
Falls back to keyword-based analysis on failure.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from lumina.pulse.domain.value_objects import Sentiment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SENTIMENT_PROMPT_SINGLE = """\
Analyse the sentiment of the following text toward the mentioned brand or product.

Text: "{context}"

Return a JSON object with exactly two keys:
- "sentiment": one of "positive", "neutral", "negative"
- "confidence": a float between 0.0 and 1.0

Return ONLY the JSON object, no other text.
"""

SENTIMENT_PROMPT_BATCH = """\
Analyse the sentiment of each of the following texts toward the mentioned \
brand or product.

{contexts_block}

Return a JSON array where each element has:
- "index": the 0-based index of the text
- "sentiment": one of "positive", "neutral", "negative"
- "confidence": a float between 0.0 and 1.0

Return ONLY the JSON array, no other text.
"""

SENTIMENT_SYSTEM = (
    "You are a precise sentiment analysis engine. "
    "Return only valid JSON. Never add commentary."
)

# ---------------------------------------------------------------------------
# Keyword-based fallback
# ---------------------------------------------------------------------------

_POSITIVE_KEYWORDS: tuple[str, ...] = (
    "best", "excellent", "outstanding", "recommend", "top", "leading",
    "great", "superior", "innovative", "trusted", "reliable", "popular",
    "preferred", "highly rated", "award-winning", "impressive", "fantastic",
    "remarkable", "exceptional", "love",
)

_NEGATIVE_KEYWORDS: tuple[str, ...] = (
    "worst", "poor", "bad", "avoid", "terrible", "unreliable",
    "disappointing", "inferior", "overpriced", "outdated", "problematic",
    "failing", "criticized", "controversial", "lacking", "mediocre",
    "subpar", "complaint", "issue", "concern",
)


def _keyword_sentiment(text: str) -> Sentiment:
    """Simple keyword-based sentiment as a fallback."""
    lower = text.lower()
    pos = sum(1 for kw in _POSITIVE_KEYWORDS if kw in lower)
    neg = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in lower)
    if pos > neg:
        return Sentiment.POSITIVE
    if neg > pos:
        return Sentiment.NEGATIVE
    return Sentiment.NEUTRAL


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SentimentResult:
    """Sentiment analysis result with confidence score."""

    sentiment: Sentiment
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            object.__setattr__(
                self, "confidence", max(0.0, min(1.0, self.confidence))
            )


# ---------------------------------------------------------------------------
# MLSentimentAnalyzer
# ---------------------------------------------------------------------------

class MLSentimentAnalyzer:
    """ML-powered sentiment analyzer using Claude API.

    Parameters
    ----------
    anthropic_client:
        An instantiated ``anthropic.AsyncAnthropic`` client.
    model:
        The Claude model identifier to use.
    """

    def __init__(
        self,
        anthropic_client: Any,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self._client = anthropic_client
        self._model = model

    async def analyze(self, context: str) -> SentimentResult:
        """Analyse sentiment of a single citation context.

        Falls back to keyword analysis on API failure.
        """
        if not context or not context.strip():
            return SentimentResult(sentiment=Sentiment.NEUTRAL, confidence=1.0)

        try:
            return await self._analyze_single(context)
        except Exception:
            logger.warning(
                "ML sentiment analysis failed, falling back to keywords",
                exc_info=True,
            )
            return SentimentResult(
                sentiment=_keyword_sentiment(context),
                confidence=0.5,
            )

    async def analyze_batch(
        self, contexts: list[str]
    ) -> list[SentimentResult]:
        """Analyse sentiment of multiple contexts in a single API call.

        Falls back to keyword analysis per-context on API failure.
        """
        if not contexts:
            return []

        # Filter out empty contexts, remembering their indices
        non_empty: list[tuple[int, str]] = [
            (i, c) for i, c in enumerate(contexts) if c and c.strip()
        ]

        # Prepare defaults for all positions
        results: list[SentimentResult] = [
            SentimentResult(sentiment=Sentiment.NEUTRAL, confidence=1.0)
        ] * len(contexts)

        if not non_empty:
            return results

        try:
            batch_results = await self._analyze_batch_api(
                [c for _, c in non_empty]
            )
            for (original_idx, _), result in zip(non_empty, batch_results):
                results[original_idx] = result
            return results
        except Exception:
            logger.warning(
                "ML batch sentiment analysis failed, falling back to keywords",
                exc_info=True,
            )
            for original_idx, ctx in non_empty:
                results[original_idx] = SentimentResult(
                    sentiment=_keyword_sentiment(ctx),
                    confidence=0.5,
                )
            return results

    # -- Private helpers -----------------------------------------------------

    async def _analyze_single(self, context: str) -> SentimentResult:
        """Call Claude API for single sentiment analysis."""
        prompt = SENTIMENT_PROMPT_SINGLE.format(context=context)

        api_response = await self._client.messages.create(
            model=self._model,
            max_tokens=256,
            system=SENTIMENT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = api_response.content[0].text.strip()
        return self._parse_single_response(raw_text)

    async def _analyze_batch_api(
        self, contexts: list[str]
    ) -> list[SentimentResult]:
        """Call Claude API for batch sentiment analysis."""
        contexts_block = "\n".join(
            f'Text {i}: "{ctx}"' for i, ctx in enumerate(contexts)
        )
        prompt = SENTIMENT_PROMPT_BATCH.format(contexts_block=contexts_block)

        api_response = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SENTIMENT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = api_response.content[0].text.strip()
        return self._parse_batch_response(raw_text, len(contexts))

    @staticmethod
    def _parse_single_response(raw_text: str) -> SentimentResult:
        """Parse a single JSON sentiment response."""
        text = raw_text
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        data = json.loads(text)
        sentiment_str = data.get("sentiment", "neutral").lower().strip()
        confidence = float(data.get("confidence", 0.8))

        sentiment_map = {
            "positive": Sentiment.POSITIVE,
            "negative": Sentiment.NEGATIVE,
            "neutral": Sentiment.NEUTRAL,
        }
        sentiment = sentiment_map.get(sentiment_str, Sentiment.NEUTRAL)
        return SentimentResult(
            sentiment=sentiment,
            confidence=max(0.0, min(1.0, confidence)),
        )

    @staticmethod
    def _parse_batch_response(
        raw_text: str, expected_count: int
    ) -> list[SentimentResult]:
        """Parse a batch JSON sentiment response."""
        text = raw_text
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        items = json.loads(text)

        # Build index -> result mapping
        result_map: dict[int, SentimentResult] = {}
        sentiment_map = {
            "positive": Sentiment.POSITIVE,
            "negative": Sentiment.NEGATIVE,
            "neutral": Sentiment.NEUTRAL,
        }

        for item in items:
            idx = int(item.get("index", -1))
            sentiment_str = item.get("sentiment", "neutral").lower().strip()
            confidence = float(item.get("confidence", 0.8))
            sentiment = sentiment_map.get(sentiment_str, Sentiment.NEUTRAL)
            result_map[idx] = SentimentResult(
                sentiment=sentiment,
                confidence=max(0.0, min(1.0, confidence)),
            )

        results: list[SentimentResult] = []
        for i in range(expected_count):
            results.append(
                result_map.get(
                    i,
                    SentimentResult(sentiment=Sentiment.NEUTRAL, confidence=0.5),
                )
            )

        return results
