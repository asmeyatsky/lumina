"""
Enhanced GEO scoring pipeline integrating ML components.

Runs entity density, answer shape, fact citability, and RAG survivability
scorers in parallel using asyncio.gather, producing a complete GEOScore
domain entity.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Optional

from lumina.shared.domain.value_objects import Score
from lumina.beam.domain.entities import GEOScore
from lumina.beam.domain.value_objects import GEOWeights

from lumina.infrastructure.nlp.entity_recognizer import EntityRecognizer
from lumina.infrastructure.nlp.answer_detector import AnswerDetector
from lumina.infrastructure.nlp.fact_extractor import FactExtractor
from lumina.infrastructure.rag.retrieval_simulator import RetrievalSimulator

logger = logging.getLogger(__name__)


class GEOScoringPipeline:
    """Enhanced GEO scoring pipeline using ML components.

    Integrates:
    - EntityRecognizer for entity density scoring
    - AnswerDetector for answer shape scoring
    - FactExtractor for fact citability scoring
    - RetrievalSimulator for RAG survivability scoring
    - Rule-based heuristics for semantic authority and freshness

    All independent scorers run in parallel via asyncio.gather.

    Parameters
    ----------
    entity_recognizer:
        EntityRecognizer instance for entity density.
    answer_detector:
        AnswerDetector instance for answer shape.
    fact_extractor:
        FactExtractor instance for fact citability.
    retrieval_simulator:
        RetrievalSimulator instance for RAG survivability.
        If None, RAG survivability uses a heuristic fallback.
    """

    def __init__(
        self,
        entity_recognizer: EntityRecognizer,
        answer_detector: AnswerDetector,
        fact_extractor: FactExtractor,
        retrieval_simulator: Optional[RetrievalSimulator] = None,
    ) -> None:
        self._entity_recognizer = entity_recognizer
        self._answer_detector = answer_detector
        self._fact_extractor = fact_extractor
        self._retrieval_simulator = retrieval_simulator

    async def score(
        self,
        content: str,
        brand_entities: list[str] | None = None,
        weights: GEOWeights | None = None,
        asset_id: str = "",
    ) -> GEOScore:
        """Compute a complete GEO score for the content.

        Runs all six scoring dimensions, four in parallel using
        asyncio.gather, then computes the weighted overall score.
        """
        if not content or not content.strip():
            zero = Score(value=0.0)
            return GEOScore(
                overall=zero,
                entity_density=zero,
                answer_shape=zero,
                fact_citability=zero,
                rag_survivability=zero,
                semantic_authority=zero,
                freshness_signals=zero,
            )

        entities = brand_entities or []

        # Run all scorers in parallel
        results = await asyncio.gather(
            self._score_entity_density(content, entities),
            self._score_answer_shape(content),
            self._score_fact_citability(content),
            self._score_rag_survivability(content, asset_id),
            self._score_semantic_authority(content),
            self._score_freshness(content),
            return_exceptions=True,
        )

        # Extract results, falling back to 0 on exception
        scores: list[Score] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Scorer failed: %s", r)
                scores.append(Score(value=0.0))
            else:
                scores.append(r)

        (
            entity_density,
            answer_shape,
            fact_citability,
            rag_survivability,
            semantic_authority,
            freshness_signals,
        ) = scores

        geo = GEOScore(
            overall=Score(value=0.0),
            entity_density=entity_density,
            answer_shape=answer_shape,
            fact_citability=fact_citability,
            rag_survivability=rag_survivability,
            semantic_authority=semantic_authority,
            freshness_signals=freshness_signals,
        )

        overall = geo.weighted_overall(weights)
        return replace(geo, overall=overall)

    # -- Individual scorers --------------------------------------------------

    async def _score_entity_density(
        self, content: str, brand_entities: list[str]
    ) -> Score:
        """Score entity density using the EntityRecognizer."""
        recognizer = self._entity_recognizer

        # Add brand entities to custom list for recognition
        if brand_entities:
            recognizer = EntityRecognizer(
                custom_brands=brand_entities,
                custom_products=recognizer.custom_products,
                custom_entities=recognizer.custom_entities,
            )

        density = recognizer.compute_entity_density(content)

        # Also compute brand coverage if brand_entities provided
        if brand_entities:
            content_lower = content.lower()
            found = sum(
                1 for e in brand_entities if e.lower() in content_lower
            )
            coverage = found / len(brand_entities) if brand_entities else 0

            # Combine density and coverage
            density_score = min(density / 5.0, 1.0)
            raw_score = (coverage * 0.6 + density_score * 0.4) * 100
        else:
            raw_score = min(density * 10, 100.0)

        return Score(value=round(min(raw_score, 100.0), 2))

    async def _score_answer_shape(self, content: str) -> Score:
        """Score answer shape using the AnswerDetector."""
        result = self._answer_detector.detect(content)
        # Convert 0-1 score to 0-100
        return Score(value=round(min(result.score * 100, 100.0), 2))

    async def _score_fact_citability(self, content: str) -> Score:
        """Score fact citability using the FactExtractor."""
        citability = self._fact_extractor.compute_citability_score(content)
        return Score(value=round(min(citability * 100, 100.0), 2))

    async def _score_rag_survivability(
        self, content: str, asset_id: str
    ) -> Score:
        """Score RAG survivability using the RetrievalSimulator if available."""
        if self._retrieval_simulator is not None:
            try:
                result = await self._retrieval_simulator.simulate(
                    content=content, asset_id=asset_id
                )
                return result.survivability_score
            except Exception:
                logger.warning(
                    "RAG simulation failed, using heuristic fallback",
                    exc_info=True,
                )

        # Heuristic fallback: score based on structural features
        return self._heuristic_rag_survivability(content)

    @staticmethod
    async def _score_semantic_authority(content: str) -> Score:
        """Score semantic authority using rule-based heuristics."""
        import re

        if not content:
            return Score(value=0.0)

        signals = 0
        max_signals = 14

        authority_patterns = [
            re.compile(r"\b(?:defined as|refers to|is a|is the)\b", re.IGNORECASE),
            re.compile(r"\b(?:therefore|consequently|thus|hence)\b", re.IGNORECASE),
            re.compile(r"\b(?:according to|as stated by|research shows)\b", re.IGNORECASE),
            re.compile(r"\b(?:first|second|third|finally|in conclusion)\b", re.IGNORECASE),
            re.compile(r"\b(?:furthermore|moreover|additionally|however)\b", re.IGNORECASE),
            re.compile(r"\b(?:evidence|analysis|framework|methodology)\b", re.IGNORECASE),
            re.compile(r"\b(?:significantly|substantially|fundamentally)\b", re.IGNORECASE),
        ]

        for pattern in authority_patterns:
            matches = pattern.findall(content)
            if matches:
                signals += min(len(matches), 2)

        raw_score = min(signals / max_signals, 1.0) * 100
        return Score(value=round(min(raw_score, 100.0), 2))

    @staticmethod
    async def _score_freshness(content: str) -> Score:
        """Score freshness signals using rule-based heuristics."""
        import re

        if not content:
            return Score(value=0.0)

        signals = 0
        max_signals = 12

        freshness_patterns = [
            re.compile(
                r"\b(?:January|February|March|April|May|June|July|August|September|"
                r"October|November|December)\s+\d{4}\b",
                re.IGNORECASE,
            ),
            re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
            re.compile(r"\b(?:updated|last updated|revised|modified)\b", re.IGNORECASE),
            re.compile(r"\b(?:latest|recent|new|current|this year|this month)\b", re.IGNORECASE),
            re.compile(r"\b20[2-9]\d\b"),
            re.compile(r"\bas of\b", re.IGNORECASE),
        ]

        for pattern in freshness_patterns:
            matches = pattern.findall(content)
            if matches:
                signals += min(len(matches), 3)

        raw_score = min(signals / max_signals, 1.0) * 100
        return Score(value=round(min(raw_score, 100.0), 2))

    @staticmethod
    def _heuristic_rag_survivability(content: str) -> Score:
        """Heuristic RAG survivability scoring without retrieval simulation."""
        import re

        if not content:
            return Score(value=0.0)

        signals = 0
        max_signals = 10

        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if len(paragraphs) >= 3:
            signals += 2

        self_contained = 0
        for para in paragraphs:
            words = para.split()
            if 30 <= len(words) <= 150:
                self_contained += 1
        if paragraphs and self_contained / max(len(paragraphs), 1) > 0.5:
            signals += 2

        headings = re.findall(r"^#{1,4}\s+", content, re.MULTILINE)
        if len(headings) >= 2:
            signals += 2

        sentences = re.split(r"[.!?]+", content)
        factual = sum(
            1
            for s in sentences
            if re.search(r"\b\d+\b", s)
            or re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", s)
        )
        if sentences and factual / max(len(sentences), 1) > 0.3:
            signals += 2

        if len(content.split()) >= 200:
            signals += 2

        raw_score = min(signals / max_signals, 1.0) * 100
        return Score(value=round(min(raw_score, 100.0), 2))
