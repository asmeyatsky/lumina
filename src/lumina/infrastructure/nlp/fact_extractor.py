"""
Fact extraction for citability scoring.

Extracts verifiable factual claims from text, identifying statistics,
dates, named sources, and specific claims. Scores each fact for
verifiability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class FactType(str, Enum):
    """Classification of extracted facts."""

    STATISTIC = "statistic"
    DATE = "date"
    NAMED_SOURCE = "named_source"
    SPECIFIC_CLAIM = "specific_claim"
    QUOTE = "quote"


@dataclass(frozen=True)
class ExtractedFact:
    """A single fact extracted from text with verifiability metadata."""

    text: str
    fact_type: FactType
    has_number: bool
    has_date: bool
    has_source: bool
    verifiability_score: float
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.verifiability_score <= 1.0:
            object.__setattr__(
                self,
                "verifiability_score",
                max(0.0, min(1.0, self.verifiability_score)),
            )
        if not 0.0 <= self.confidence <= 1.0:
            object.__setattr__(
                self,
                "confidence",
                max(0.0, min(1.0, self.confidence)),
            )


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_STATISTIC_PATTERN = re.compile(
    r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*%"
    r"|\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|trillion|thousand)"
    r"|\$\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s*(?:million|billion|trillion))?"
    r"|\b\d{1,3}(?:,\d{3})+\b",
    re.IGNORECASE,
)

_DATE_PATTERN = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b(?:Q[1-4])\s+\d{4}\b"
    r"|\b(?:in|since|from|by)\s+\d{4}\b",
    re.IGNORECASE,
)

_SOURCE_PATTERN = re.compile(
    r"\baccording to\s+[A-Z][a-zA-Z\s]+\b"
    r"|\b(?:study|research|report|survey|analysis)\s+(?:by|from)\s+[A-Z]"
    r"|\b(?:Dr\.|Prof\.|Professor)\s+[A-Z][a-z]+"
    r"|\b(?:published|reported)\s+(?:in|by)\s+[A-Z]",
    re.IGNORECASE,
)

_QUOTE_PATTERN = re.compile(r'"[^"]{10,}"')

_SPECIFIC_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:increased|decreased|grew|declined|rose|fell)\s+(?:by\s+)?\d", re.IGNORECASE),
    re.compile(r"\b(?:more|less|fewer|greater)\s+than\s+\d", re.IGNORECASE),
    re.compile(r"\b(?:ranked|rated)\s+(?:#?\d|first|second|third)", re.IGNORECASE),
    re.compile(r"\b(?:founded|established|launched|released)\s+in\s+\d{4}", re.IGNORECASE),
)


class FactExtractor:
    """Extracts verifiable factual claims from text.

    Identifies statistics, dates, named sources, quotes, and specific
    claims, then scores each for verifiability based on the presence
    of numbers, dates, and source attributions.
    """

    def extract_facts(self, text: str) -> list[ExtractedFact]:
        """Extract all verifiable facts from the given text.

        Returns a list of ExtractedFact objects, each scored for
        verifiability.
        """
        if not text or not text.strip():
            return []

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        facts: list[ExtractedFact] = []
        seen_texts: set[str] = set()

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            extracted = self._extract_from_sentence(sentence)
            for fact in extracted:
                if fact.text not in seen_texts:
                    seen_texts.add(fact.text)
                    facts.append(fact)

        return facts

    def compute_citability_score(self, text: str) -> float:
        """Compute an overall citability score for the text (0.0 to 1.0).

        Based on the density and verifiability of extracted facts.
        """
        if not text or not text.strip():
            return 0.0

        facts = self.extract_facts(text)
        if not facts:
            return 0.0

        # Average verifiability
        avg_verifiability = sum(f.verifiability_score for f in facts) / len(facts)

        # Fact density: facts per 100 words
        word_count = len(text.split())
        if word_count == 0:
            return 0.0
        density = len(facts) / word_count * 100

        # Combine: 60% density impact (capped at 1.0), 40% avg verifiability
        density_score = min(density / 5.0, 1.0)
        score = density_score * 0.6 + avg_verifiability * 0.4

        return round(min(score, 1.0), 4)

    def _extract_from_sentence(self, sentence: str) -> list[ExtractedFact]:
        """Extract facts from a single sentence."""
        facts: list[ExtractedFact] = []

        has_number = bool(_STATISTIC_PATTERN.search(sentence))
        has_date = bool(_DATE_PATTERN.search(sentence))
        has_source = bool(_SOURCE_PATTERN.search(sentence))
        has_quote = bool(_QUOTE_PATTERN.search(sentence))
        has_specific_claim = any(p.search(sentence) for p in _SPECIFIC_CLAIM_PATTERNS)

        # Determine fact type (in priority order)
        if has_number and has_source:
            fact_type = FactType.STATISTIC
            confidence = 0.95
        elif has_number:
            fact_type = FactType.STATISTIC
            confidence = 0.85
        elif has_quote:
            fact_type = FactType.QUOTE
            confidence = 0.90
        elif has_source:
            fact_type = FactType.NAMED_SOURCE
            confidence = 0.85
        elif has_date:
            fact_type = FactType.DATE
            confidence = 0.80
        elif has_specific_claim:
            fact_type = FactType.SPECIFIC_CLAIM
            confidence = 0.75
        else:
            # No factual signals in this sentence
            return []

        # Compute verifiability score
        verifiability = self._compute_verifiability(
            has_number=has_number,
            has_date=has_date,
            has_source=has_source,
        )

        facts.append(
            ExtractedFact(
                text=sentence,
                fact_type=fact_type,
                has_number=has_number,
                has_date=has_date,
                has_source=has_source,
                verifiability_score=verifiability,
                confidence=confidence,
            )
        )

        return facts

    @staticmethod
    def _compute_verifiability(
        has_number: bool,
        has_date: bool,
        has_source: bool,
    ) -> float:
        """Compute a verifiability score from 0.0 to 1.0.

        Each signal contributes to the score:
        - Has a number/statistic: +0.35
        - Has a date: +0.30
        - Has a named source: +0.35
        """
        score = 0.0
        if has_number:
            score += 0.35
        if has_date:
            score += 0.30
        if has_source:
            score += 0.35
        return min(score, 1.0)
