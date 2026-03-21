"""
Answer shape detection for GEO scoring.

Detects structural patterns in content that indicate how well it is
shaped for AI answer extraction: Q&A patterns, list/step structures,
definitions, and comparisons.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class PatternType(str, Enum):
    """Types of answer shape patterns detected in content."""

    QA_PAIR = "qa_pair"
    NUMBERED_LIST = "numbered_list"
    BULLET_LIST = "bullet_list"
    DEFINITION = "definition"
    COMPARISON = "comparison"
    STEP_SEQUENCE = "step_sequence"
    SUMMARY = "summary"
    HEADING_STRUCTURE = "heading_structure"


@dataclass(frozen=True)
class DetectedPattern:
    """A single detected answer shape pattern."""

    pattern_type: PatternType
    text: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass(frozen=True)
class AnswerShapeResult:
    """Result of answer shape analysis."""

    score: float
    detected_patterns: tuple[DetectedPattern, ...]
    pattern_types_found: tuple[PatternType, ...]
    pattern_counts: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_QA_PATTERN = re.compile(
    r"((?:^|\n)\s*(?:#{1,4}\s+)?(?:What|How|Why|When|Where|Who|Which|Can|Do|Does|Is|Are|Should|Will|Would)"
    r"[^\n]*\?)\s*\n+\s*([^\n?]+)",
    re.IGNORECASE | re.MULTILINE,
)

_NUMBERED_LIST_PATTERN = re.compile(
    r"(?:^|\n)\s*\d+[.)]\s+\S",
    re.MULTILINE,
)

_BULLET_LIST_PATTERN = re.compile(
    r"(?:^|\n)\s*[-*+]\s+\S",
    re.MULTILINE,
)

_DEFINITION_PATTERN = re.compile(
    r"\b(\w[\w\s]{1,40})\s+(?:is|are|refers to|is defined as|means|represents|"
    r"can be described as|is known as)\s+",
    re.IGNORECASE,
)

_COMPARISON_PATTERN = re.compile(
    r"\b(?:\w+\s+vs\.?\s+\w+"
    r"|compared\s+to\s+\w+"
    r"|(?:unlike|versus|as\s+opposed\s+to|in\s+contrast\s+to)\s+\w+"
    r"|(?:better|worse|faster|slower|cheaper|more\s+expensive)\s+than\s+\w+)\b",
    re.IGNORECASE,
)

_STEP_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:Step|Phase|Stage)\s+\d+[.:]\s*\S",
    re.IGNORECASE | re.MULTILINE,
)

_SUMMARY_PATTERN = re.compile(
    r"\b(?:in\s+summary|to\s+summarize|in\s+short|in\s+conclusion|"
    r"the\s+key\s+takeaway|bottom\s+line|the\s+answer\s+is|"
    r"simply\s+put|to\s+sum\s+up|overall)\b",
    re.IGNORECASE,
)

_HEADING_PATTERN = re.compile(
    r"^#{1,4}\s+.+$",
    re.MULTILINE,
)


class AnswerDetector:
    """Detects answer shape patterns in content for GEO scoring.

    Analyses content structure to determine how well it is formatted
    for AI answer extraction, looking for Q&A pairs, lists, definitions,
    comparisons, and other structured patterns.
    """

    def detect(self, content: str) -> AnswerShapeResult:
        """Analyse content for answer shape patterns.

        Returns an AnswerShapeResult with score (0.0-1.0), detected
        patterns, and pattern type summary.
        """
        if not content or not content.strip():
            return AnswerShapeResult(
                score=0.0,
                detected_patterns=(),
                pattern_types_found=(),
                pattern_counts={},
            )

        patterns: list[DetectedPattern] = []

        # Detect Q&A pairs
        for match in _QA_PATTERN.finditer(content):
            patterns.append(
                DetectedPattern(
                    pattern_type=PatternType.QA_PAIR,
                    text=match.group(0).strip()[:200],
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,
                )
            )

        # Detect numbered lists
        numbered_matches = list(_NUMBERED_LIST_PATTERN.finditer(content))
        if len(numbered_matches) >= 2:
            for match in numbered_matches:
                patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.NUMBERED_LIST,
                        text=match.group(0).strip()[:100],
                        start=match.start(),
                        end=match.end(),
                        confidence=0.85,
                    )
                )

        # Detect bullet lists
        bullet_matches = list(_BULLET_LIST_PATTERN.finditer(content))
        if len(bullet_matches) >= 2:
            for match in bullet_matches:
                patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.BULLET_LIST,
                        text=match.group(0).strip()[:100],
                        start=match.start(),
                        end=match.end(),
                        confidence=0.85,
                    )
                )

        # Detect definitions
        for match in _DEFINITION_PATTERN.finditer(content):
            # Extract a larger context around the definition
            ctx_end = min(len(content), match.end() + 100)
            patterns.append(
                DetectedPattern(
                    pattern_type=PatternType.DEFINITION,
                    text=content[match.start():ctx_end].strip()[:200],
                    start=match.start(),
                    end=match.end(),
                    confidence=0.8,
                )
            )

        # Detect comparisons
        for match in _COMPARISON_PATTERN.finditer(content):
            patterns.append(
                DetectedPattern(
                    pattern_type=PatternType.COMPARISON,
                    text=match.group(0).strip()[:200],
                    start=match.start(),
                    end=match.end(),
                    confidence=0.8,
                )
            )

        # Detect step sequences
        step_matches = list(_STEP_PATTERN.finditer(content))
        if len(step_matches) >= 2:
            for match in step_matches:
                patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.STEP_SEQUENCE,
                        text=match.group(0).strip()[:100],
                        start=match.start(),
                        end=match.end(),
                        confidence=0.9,
                    )
                )

        # Detect summary language
        for match in _SUMMARY_PATTERN.finditer(content):
            ctx_end = min(len(content), match.end() + 100)
            patterns.append(
                DetectedPattern(
                    pattern_type=PatternType.SUMMARY,
                    text=content[match.start():ctx_end].strip()[:200],
                    start=match.start(),
                    end=match.end(),
                    confidence=0.75,
                )
            )

        # Detect heading structure
        heading_matches = list(_HEADING_PATTERN.finditer(content))
        if len(heading_matches) >= 2:
            for match in heading_matches:
                patterns.append(
                    DetectedPattern(
                        pattern_type=PatternType.HEADING_STRUCTURE,
                        text=match.group(0).strip()[:100],
                        start=match.start(),
                        end=match.end(),
                        confidence=0.85,
                    )
                )

        # Compute score and summaries
        pattern_types = tuple(sorted(set(p.pattern_type for p in patterns)))
        pattern_counts: dict[str, int] = {}
        for p in patterns:
            key = p.pattern_type.value
            pattern_counts[key] = pattern_counts.get(key, 0) + 1

        score = self._compute_score(patterns, content)

        return AnswerShapeResult(
            score=score,
            detected_patterns=tuple(patterns),
            pattern_types_found=pattern_types,
            pattern_counts=pattern_counts,
        )

    @staticmethod
    def _compute_score(
        patterns: list[DetectedPattern], content: str
    ) -> float:
        """Compute an answer shape score from 0.0 to 1.0.

        Scores are based on:
        - Number of distinct pattern types found (diversity)
        - Total pattern count (density)
        - Pattern confidence scores
        """
        if not patterns:
            return 0.0

        # Diversity: how many different pattern types are present
        unique_types = set(p.pattern_type for p in patterns)
        max_types = len(PatternType)
        diversity_score = len(unique_types) / max_types

        # Density: patterns per 100 words (capped)
        word_count = len(content.split())
        if word_count == 0:
            return 0.0
        density = len(patterns) / word_count * 100
        density_score = min(density / 10.0, 1.0)

        # Average confidence
        avg_confidence = sum(p.confidence for p in patterns) / len(patterns)

        # Weighted combination
        score = (
            diversity_score * 0.45
            + density_score * 0.35
            + avg_confidence * 0.20
        )

        return round(min(score, 1.0), 4)
