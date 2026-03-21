"""
PULSE Domain Services — Pure business logic with no infrastructure dependencies

Architectural Intent:
- Domain services contain logic that doesn't naturally belong to a single entity
- All methods are pure functions: deterministic, no side effects, no I/O
- CitationExtractionService uses heuristics and string matching for citation extraction
- SentimentAnalysisService uses rule-based keyword matching
- BenchmarkService computes competitive metrics from citation data
"""

from __future__ import annotations

import re
from typing import Optional

from lumina.shared.domain.value_objects import BrandId, Percentage

from lumina.pulse.domain.entities import Citation
from lumina.pulse.domain.events import CompetitorCitationSurge
from lumina.pulse.domain.value_objects import (
    CitationPosition,
    CompetitorBenchmark,
    Sentiment,
    ShareOfVoice,
)


# -- Positive / Negative keyword lists for rule-based sentiment ----------

_POSITIVE_KEYWORDS: tuple[str, ...] = (
    "best",
    "excellent",
    "outstanding",
    "recommend",
    "top",
    "leading",
    "great",
    "superior",
    "innovative",
    "trusted",
    "reliable",
    "popular",
    "preferred",
    "highly rated",
    "award-winning",
    "impressive",
    "fantastic",
    "remarkable",
    "exceptional",
    "love",
)

_NEGATIVE_KEYWORDS: tuple[str, ...] = (
    "worst",
    "poor",
    "bad",
    "avoid",
    "terrible",
    "unreliable",
    "disappointing",
    "inferior",
    "overpriced",
    "outdated",
    "problematic",
    "failing",
    "criticized",
    "controversial",
    "lacking",
    "mediocre",
    "subpar",
    "complaint",
    "issue",
    "concern",
)

# -- Recommendation phrases -----------------------------------------------

_RECOMMENDATION_PHRASES: tuple[str, ...] = (
    "i recommend",
    "i would recommend",
    "i'd recommend",
    "we recommend",
    "highly recommend",
    "top pick",
    "best choice",
    "best option",
    "go with",
    "you should try",
    "consider using",
    "you should use",
    "the best",
    "my top",
    "number one",
    "#1",
)


class CitationExtractionService:
    """Extracts brand citations from AI engine responses using string matching.

    Uses heuristic analysis to find brand mentions, determine their ordinal
    position within the response, and detect recommendation language.
    """

    @staticmethod
    def extract_citations(
        raw_response: str,
        brand_name: str,
        competitors: tuple[str, ...] = (),
    ) -> tuple[Citation, ...]:
        """Extract all brand and competitor citations from a raw AI response.

        Args:
            raw_response: The full text response from an AI engine.
            brand_name: The primary brand to look for.
            competitors: Competitor brand names to also detect.

        Returns:
            Tuple of Citation objects for every detected mention.
        """
        all_brands = (brand_name,) + competitors
        citations: list[Citation] = []

        # Build an ordered list of (position_in_text, brand) for position ranking
        brand_first_occurrence: list[tuple[int, str]] = []
        response_lower = raw_response.lower()

        for brand in all_brands:
            idx = response_lower.find(brand.lower())
            if idx != -1:
                brand_first_occurrence.append((idx, brand))

        # Sort by first occurrence to determine ordinal position
        brand_first_occurrence.sort(key=lambda x: x[0])

        # Map brand -> ordinal position
        position_map: dict[str, CitationPosition] = {}
        for rank, (_, brand) in enumerate(brand_first_occurrence):
            if rank == 0:
                position_map[brand.lower()] = CitationPosition.FIRST
            elif rank == 1:
                position_map[brand.lower()] = CitationPosition.SECOND
            elif rank == 2:
                position_map[brand.lower()] = CitationPosition.THIRD
            else:
                position_map[brand.lower()] = CitationPosition.MENTIONED

        # Extract all occurrences of each brand
        for brand in all_brands:
            pattern = re.compile(re.escape(brand), re.IGNORECASE)
            matches = list(pattern.finditer(raw_response))

            if not matches:
                # Brand not cited — emit a NOT_CITED citation for tracking
                citations.append(
                    Citation(
                        brand_name=brand,
                        context="",
                        position=CitationPosition.NOT_CITED,
                        is_recommendation=False,
                        source_url=None,
                    )
                )
                continue

            # For each occurrence, extract surrounding context
            for match in matches:
                context = _extract_context(raw_response, match.start(), match.end())
                position = position_map.get(brand.lower(), CitationPosition.MENTIONED)
                is_rec = _is_recommendation(context)

                citations.append(
                    Citation(
                        brand_name=brand,
                        context=context,
                        position=position,
                        is_recommendation=is_rec,
                        source_url=None,
                    )
                )

        return tuple(citations)


class SentimentAnalysisService:
    """Rule-based sentiment analysis for citation contexts.

    Uses keyword matching to classify the sentiment of the text
    surrounding a brand citation. This is a lightweight approach
    suitable for fast, deterministic analysis without ML dependencies.
    """

    @staticmethod
    def analyze_sentiment(citation_context: str) -> Sentiment:
        """Classify the sentiment of a citation context string.

        Counts positive and negative keyword matches and returns
        the dominant sentiment. Ties resolve to NEUTRAL.

        Args:
            citation_context: The text surrounding a brand mention.

        Returns:
            Sentiment enum value.
        """
        if not citation_context or not citation_context.strip():
            return Sentiment.NEUTRAL

        context_lower = citation_context.lower()

        positive_count = sum(
            1 for kw in _POSITIVE_KEYWORDS if kw in context_lower
        )
        negative_count = sum(
            1 for kw in _NEGATIVE_KEYWORDS if kw in context_lower
        )

        if positive_count > negative_count:
            return Sentiment.POSITIVE
        elif negative_count > positive_count:
            return Sentiment.NEGATIVE
        else:
            return Sentiment.NEUTRAL


class BenchmarkService:
    """Competitive benchmarking calculations.

    Computes share of voice metrics and detects significant changes
    in competitor citation rates.
    """

    @staticmethod
    def calculate_share_of_voice(
        results_by_brand: dict[str, list[Citation]],
    ) -> CompetitorBenchmark:
        """Calculate share of voice for all brands in a citation dataset.

        Args:
            results_by_brand: Mapping of brand_id string to list of Citation
                objects for that brand. Only citations with position != NOT_CITED
                count toward the totals.

        Returns:
            CompetitorBenchmark with share of voice for each brand.
        """
        # Count actual citations (exclude NOT_CITED)
        citation_counts: dict[str, int] = {}
        for brand_key, citations in results_by_brand.items():
            cited = [
                c for c in citations if c.position != CitationPosition.NOT_CITED
            ]
            citation_counts[brand_key] = len(cited)

        total_citations = sum(citation_counts.values())

        # Build share of voice map
        sov_map: dict[str, ShareOfVoice] = {}
        for brand_key, count in citation_counts.items():
            pct = (count / total_citations * 100.0) if total_citations > 0 else 0.0
            sov_map[brand_key] = ShareOfVoice(
                brand_id=BrandId(value=brand_key),
                citation_count=count,
                total_citations=total_citations,
                percentage=Percentage(value=round(pct, 2)),
            )

        # Determine primary brand (first key) and competitors
        brand_keys = list(results_by_brand.keys())
        if not brand_keys:
            primary = BrandId(value="unknown")
            competitor_ids: tuple[BrandId, ...] = ()
        else:
            primary = BrandId(value=brand_keys[0])
            competitor_ids = tuple(BrandId(value=k) for k in brand_keys[1:])

        return CompetitorBenchmark(
            brand_id=primary,
            competitor_brand_ids=competitor_ids,
            share_of_voice_map=sov_map,
        )

    @staticmethod
    def detect_competitor_surge(
        current: CompetitorBenchmark,
        previous: CompetitorBenchmark,
        surge_threshold: float = 20.0,
    ) -> list[CompetitorCitationSurge]:
        """Detect competitors whose citation share surged between periods.

        Args:
            current: Current period's benchmark.
            previous: Previous period's benchmark.
            surge_threshold: Minimum absolute percentage-point increase
                to qualify as a surge (default 20%).

        Returns:
            List of CompetitorCitationSurge events for any competitor
            whose share of voice increased by more than the threshold.
        """
        surges: list[CompetitorCitationSurge] = []

        for competitor_id in current.competitor_brand_ids:
            comp_key = competitor_id.value
            current_sov = current.share_of_voice_map.get(comp_key)
            previous_sov = previous.share_of_voice_map.get(comp_key)

            if current_sov is None:
                continue

            current_pct = current_sov.percentage.value
            previous_pct = previous_sov.percentage.value if previous_sov else 0.0
            delta = current_pct - previous_pct

            if delta >= surge_threshold:
                surges.append(
                    CompetitorCitationSurge(
                        aggregate_id=current.brand_id.value,
                        brand_id=current.brand_id.value,
                        competitor_id=comp_key,
                        engine="all",
                        surge_percentage=round(delta, 2),
                    )
                )

        return surges


# -- Private helpers -------------------------------------------------------


def _extract_context(
    text: str, match_start: int, match_end: int, window: int = 150
) -> str:
    """Extract a context window around a match position.

    Returns up to `window` characters before and after the match,
    trimmed to sentence boundaries where possible.
    """
    ctx_start = max(0, match_start - window)
    ctx_end = min(len(text), match_end + window)
    context = text[ctx_start:ctx_end].strip()

    # Try to trim to sentence boundaries
    if ctx_start > 0:
        first_period = context.find(". ")
        if first_period != -1 and first_period < window // 2:
            context = context[first_period + 2 :]

    if ctx_end < len(text):
        last_period = context.rfind(".")
        if last_period != -1 and last_period > len(context) // 2:
            context = context[: last_period + 1]

    return context.strip()


def _is_recommendation(context: str) -> bool:
    """Check if the context contains recommendation language."""
    context_lower = context.lower()
    return any(phrase in context_lower for phrase in _RECOMMENDATION_PHRASES)
