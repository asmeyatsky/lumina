"""
Tests for answer shape detection.

Tests cover Q&A format detection, list structure detection, definition
detection, and scoring of unstructured narrative content.
"""

from __future__ import annotations

import pytest

from lumina.infrastructure.nlp.answer_detector import (
    AnswerDetector,
    PatternType,
)


class TestAnswerDetector:
    """Tests for AnswerDetector."""

    def test_detects_qa_format(self) -> None:
        """Q&A-formatted content should be detected."""
        detector = AnswerDetector()

        content = (
            "## What is cloud computing?\n\n"
            "Cloud computing is the delivery of computing services over the internet.\n\n"
            "## How does it work?\n\n"
            "It works by hosting applications and data on remote servers."
        )
        result = detector.detect(content)

        assert result.score > 0.0
        assert PatternType.QA_PAIR in result.pattern_types_found

    def test_detects_list_structures(self) -> None:
        """Numbered and bulleted lists should be detected."""
        detector = AnswerDetector()

        content = (
            "The top benefits of cloud computing:\n\n"
            "1. Scalability on demand\n"
            "2. Cost efficiency\n"
            "3. Global accessibility\n"
            "4. Automatic updates\n\n"
            "Additional advantages include:\n\n"
            "- Reduced IT overhead\n"
            "- Improved collaboration\n"
            "- Enhanced security\n"
        )
        result = detector.detect(content)

        assert result.score > 0.0
        found_types = result.pattern_types_found
        assert (
            PatternType.NUMBERED_LIST in found_types
            or PatternType.BULLET_LIST in found_types
        )

    def test_detects_definitions(self) -> None:
        """Definition patterns should be detected."""
        detector = AnswerDetector()

        content = (
            "Machine learning is a subset of artificial intelligence. "
            "Deep learning refers to neural networks with many layers. "
            "Natural language processing is defined as the ability of "
            "computers to understand human language."
        )
        result = detector.detect(content)

        assert result.score > 0.0
        assert PatternType.DEFINITION in result.pattern_types_found

    def test_scores_narrative_content_low(self) -> None:
        """Pure narrative without structural patterns should score low."""
        detector = AnswerDetector()

        content = (
            "The morning sun cast a warm glow over the valley. "
            "Birds sang in the trees as the mist slowly lifted from "
            "the river. The farmer walked through the fields, checking "
            "the crops that had been planted weeks before. Everything "
            "seemed peaceful and the harvest would be good this year. "
            "The village below was just beginning to wake up."
        )
        result = detector.detect(content)

        # Narrative content should have a very low score
        assert result.score < 0.3

    def test_detects_comparisons(self) -> None:
        """Comparison patterns should be detected."""
        detector = AnswerDetector()

        content = (
            "AWS vs Azure: both are leading cloud platforms. "
            "AWS is faster than Azure for certain workloads. "
            "Compared to Google Cloud, AWS has more services."
        )
        result = detector.detect(content)

        assert result.score > 0.0
        assert PatternType.COMPARISON in result.pattern_types_found

    def test_handles_empty_content(self) -> None:
        """Empty content should return a zero score."""
        detector = AnswerDetector()

        result = detector.detect("")
        assert result.score == 0.0
        assert result.detected_patterns == ()

        result = detector.detect("   ")
        assert result.score == 0.0

    def test_detects_step_sequences(self) -> None:
        """Step/phase sequences should be detected."""
        detector = AnswerDetector()

        content = (
            "How to deploy to production:\n\n"
            "Step 1: Build the application\n"
            "Step 2: Run the test suite\n"
            "Step 3: Deploy to staging\n"
            "Step 4: Promote to production\n"
        )
        result = detector.detect(content)

        assert result.score > 0.0
        assert PatternType.STEP_SEQUENCE in result.pattern_types_found

    def test_pattern_counts_are_populated(self) -> None:
        """Pattern counts dictionary should reflect detected patterns."""
        detector = AnswerDetector()

        content = (
            "Cloud computing is the delivery of computing services.\n\n"
            "1. Scalability\n"
            "2. Cost savings\n"
            "3. Flexibility\n"
        )
        result = detector.detect(content)

        assert isinstance(result.pattern_counts, dict)
        # At least one pattern type should have a count
        if result.detected_patterns:
            assert sum(result.pattern_counts.values()) > 0
