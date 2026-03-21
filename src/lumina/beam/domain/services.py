"""
BEAM Domain Services — Pure domain logic with no infrastructure dependencies

Architectural Intent:
- Stateless services encapsulating domain logic that doesn't belong to a single entity
- No I/O, no side effects — pure functions operating on domain types
- GEOScoringService: rule-based heuristic scoring for six GEO factors
- RAGSimulationService: simulates RAG chunking and fact survival
- RewriteService: generates rule-based improvement suggestions
"""

from __future__ import annotations

import math
import re
from uuid import uuid4

from lumina.shared.domain.value_objects import Score

from lumina.beam.domain.entities import (
    ContentAsset,
    ContentChunk,
    GEOScore,
    RAGSimulationResult,
    RewriteSuggestion,
)
from lumina.beam.domain.value_objects import GEOFactor, GEOWeights


class GEOScoringService:
    """Pure domain service for computing GEO scores from content text.

    All scoring methods are deterministic, rule-based heuristics that analyse
    textual features to estimate how well content performs on each GEO factor.
    """

    _ANSWER_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"\b(what|how|why|when|where|who)\b.*\?", re.IGNORECASE),
        re.compile(r"^#{1,3}\s+.+\?$", re.MULTILINE),
        re.compile(r"^\s*[-*]\s+", re.MULTILINE),
        re.compile(r"^\s*\d+\.\s+", re.MULTILINE),
        re.compile(r"\b(in short|to summarize|the answer is|simply put)\b", re.IGNORECASE),
    )

    _CITABILITY_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?%?\b"),
        re.compile(
            r"\b(?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+\d{1,2},?\s+\d{4}\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
        re.compile(r"\baccording to\b", re.IGNORECASE),
        re.compile(r"\b(?:study|research|report|survey)\b.*\bfound\b", re.IGNORECASE),
        re.compile(r"\b(?:Dr\.|Prof\.|Professor)\s+[A-Z][a-z]+", re.IGNORECASE),
        re.compile(r'"[^"]{10,}"'),
    )

    _FRESHNESS_PATTERNS: tuple[re.Pattern[str], ...] = (
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
    )

    @staticmethod
    def score_entity_density(content: str, brand_entities: list[str]) -> Score:
        """Score entity density by measuring branded entity mention frequency.

        Higher density of recognised entity mentions indicates better entity
        coverage for AI retrieval systems.

        Args:
            content: The text content to analyse.
            brand_entities: List of entity names/phrases to look for.

        Returns:
            A Score (0-100) based on entity density.
        """
        if not content or not brand_entities:
            return Score(value=0.0)

        words = content.split()
        word_count = len(words)
        if word_count == 0:
            return Score(value=0.0)

        content_lower = content.lower()
        total_mentions = 0
        entities_found = 0

        for entity in brand_entities:
            entity_lower = entity.lower()
            count = content_lower.count(entity_lower)
            if count > 0:
                total_mentions += count
                entities_found += 1

        if entities_found == 0:
            return Score(value=0.0)

        entity_coverage = entities_found / len(brand_entities)
        density_ratio = total_mentions / word_count
        density_score = min(density_ratio * 500, 1.0)

        raw_score = (entity_coverage * 0.6 + density_score * 0.4) * 100
        return Score(value=round(min(raw_score, 100.0), 2))

    @staticmethod
    def score_answer_shape(content: str) -> Score:
        """Score how well content is shaped for AI answer extraction.

        Checks for Q&A patterns, direct answer structures, list formatting,
        and summary phrases that AI engines favour.

        Args:
            content: The text content to analyse.

        Returns:
            A Score (0-100) based on answer-shape quality.
        """
        if not content:
            return Score(value=0.0)

        signals = 0
        max_signals = len(GEOScoringService._ANSWER_PATTERNS) * 2

        for pattern in GEOScoringService._ANSWER_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                signals += min(len(matches), 3)

        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if paragraphs:
            short_paragraphs = sum(1 for p in paragraphs if len(p.split()) <= 60)
            if short_paragraphs / len(paragraphs) > 0.5:
                signals += 2

        headings = re.findall(r"^#{1,4}\s+", content, re.MULTILINE)
        if len(headings) >= 2:
            signals += 2

        raw_score = min(signals / max_signals, 1.0) * 100
        return Score(value=round(min(raw_score, 100.0), 2))

    @staticmethod
    def score_fact_citability(content: str) -> Score:
        """Score how many citable facts the content contains.

        Looks for specific numbers, dates, named sources, direct quotes,
        and verifiable claims that AI engines can cite.

        Args:
            content: The text content to analyse.

        Returns:
            A Score (0-100) based on fact citability.
        """
        if not content:
            return Score(value=0.0)

        signals = 0
        max_signals = len(GEOScoringService._CITABILITY_PATTERNS) * 3

        for pattern in GEOScoringService._CITABILITY_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                signals += min(len(matches), 5)

        raw_score = min(signals / max_signals, 1.0) * 100
        return Score(value=round(min(raw_score, 100.0), 2))

    @staticmethod
    def score_freshness(content: str) -> Score:
        """Score freshness signals in the content.

        Checks for dates, 'updated' indicators, recency language,
        and temporal references that signal the content is current.

        Args:
            content: The text content to analyse.

        Returns:
            A Score (0-100) based on freshness signals.
        """
        if not content:
            return Score(value=0.0)

        signals = 0
        max_signals = len(GEOScoringService._FRESHNESS_PATTERNS) * 2

        for pattern in GEOScoringService._FRESHNESS_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                signals += min(len(matches), 3)

        raw_score = min(signals / max_signals, 1.0) * 100
        return Score(value=round(min(raw_score, 100.0), 2))

    @staticmethod
    def calculate_geo_score(
        content: str,
        brand_entities: list[str],
        weights: GEOWeights | None = None,
    ) -> GEOScore:
        """Run all six scoring heuristics and compute the overall GEO score.

        Args:
            content: The text content to analyse.
            brand_entities: Brand entity names for entity density scoring.
            weights: Optional custom weights. Uses PRD defaults if omitted.

        Returns:
            A complete GEOScore with all six factor scores and weighted overall.
        """
        entity_density = GEOScoringService.score_entity_density(content, brand_entities)
        answer_shape = GEOScoringService.score_answer_shape(content)
        fact_citability = GEOScoringService.score_fact_citability(content)
        freshness_signals = GEOScoringService.score_freshness(content)

        semantic_authority = GEOScoringService._score_semantic_authority(content)
        rag_survivability = GEOScoringService._score_rag_survivability(content)

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

        from dataclasses import replace

        return replace(geo, overall=overall)

    @staticmethod
    def _score_semantic_authority(content: str) -> Score:
        """Score semantic authority based on authoritative language patterns.

        Checks for definitional statements, expert terminology, structured
        arguments, and citation-like references.
        """
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
    def _score_rag_survivability(content: str) -> Score:
        """Score RAG survivability based on content structure.

        Content that is well-structured with clear sections, self-contained
        paragraphs, and explicit fact statements survives chunking better.
        """
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
            if re.search(r"\b\d+\b", s) or re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", s)
        )
        if sentences and factual / max(len(sentences), 1) > 0.3:
            signals += 2

        if len(content.split()) >= 200:
            signals += 2

        raw_score = min(signals / max_signals, 1.0) * 100
        return Score(value=round(min(raw_score, 100.0), 2))


class RAGSimulationService:
    """Pure domain service that simulates RAG retrieval to assess fact survival.

    Chunks content, extracts key facts, and determines which facts survive
    the chunking process — a proxy for how well content will perform when
    ingested by AI retrieval systems.
    """

    @staticmethod
    def chunk_content(
        content: str, chunk_size: int = 512
    ) -> tuple[ContentChunk, ...]:
        """Split content into chunks of approximately chunk_size tokens.

        Uses whitespace-based token approximation (1 token ~ 0.75 words).

        Args:
            content: The text content to chunk.
            chunk_size: Target token count per chunk.

        Returns:
            A tuple of ContentChunk instances.
        """
        if not content:
            return ()

        words = content.split()
        words_per_chunk = max(int(chunk_size * 0.75), 1)

        chunks: list[ContentChunk] = []
        for i in range(0, len(words), words_per_chunk):
            chunk_words = words[i : i + words_per_chunk]
            text = " ".join(chunk_words)
            token_count = math.ceil(len(chunk_words) / 0.75)
            key_facts = RAGSimulationService._extract_facts_from_text(text)

            quality_signals = 0
            if key_facts:
                quality_signals += min(len(key_facts) * 15, 40)
            if len(chunk_words) >= 50:
                quality_signals += 20
            if re.search(r"\b\d+\b", text):
                quality_signals += 20
            if re.search(r"[.!?]", text):
                quality_signals += 20

            chunks.append(
                ContentChunk(
                    chunk_id=str(uuid4()),
                    text=text,
                    token_count=token_count,
                    key_facts=tuple(key_facts),
                    embedding_quality=Score(
                        value=round(min(quality_signals, 100.0), 2)
                    ),
                )
            )

        return tuple(chunks)

    @staticmethod
    def extract_key_facts(content: str) -> tuple[str, ...]:
        """Extract key factual claims from content.

        Identifies sentences containing specific data points: numbers,
        dates, percentages, named entities, and verifiable statements.

        Args:
            content: The text to extract facts from.

        Returns:
            A tuple of fact strings.
        """
        return tuple(RAGSimulationService._extract_facts_from_text(content))

    @staticmethod
    def _extract_facts_from_text(text: str) -> list[str]:
        """Internal helper to extract factual sentences from text."""
        if not text:
            return []

        sentences = re.split(r"(?<=[.!?])\s+", text)
        facts: list[str] = []

        fact_patterns = [
            re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?%?\b"),
            re.compile(
                r"\b(?:January|February|March|April|May|June|July|August|September|"
                r"October|November|December)\s+\d{1,2},?\s+\d{4}\b",
                re.IGNORECASE,
            ),
            re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
            re.compile(r"\baccording to\b", re.IGNORECASE),
            re.compile(r"\b(?:study|research|report)\b.*\bfound\b", re.IGNORECASE),
            re.compile(r"\b\d+(?:\.\d+)?%\b"),
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            for pattern in fact_patterns:
                if pattern.search(sentence):
                    facts.append(sentence)
                    break

        return facts

    @staticmethod
    def simulate_retrieval(
        chunks: tuple[ContentChunk, ...], query: str
    ) -> RAGSimulationResult:
        """Simulate RAG retrieval to determine which facts survive chunking.

        Uses keyword overlap as a proxy for embedding similarity to determine
        which chunks would be retrieved for a given query, then checks which
        facts from the original content are present in retrieved chunks.

        Args:
            chunks: The chunked content to search.
            query: The simulated query.

        Returns:
            A RAGSimulationResult with survived and lost facts.
        """
        if not chunks:
            return RAGSimulationResult(
                asset_id="",
                chunks=(),
                survived_facts=(),
                lost_facts=(),
                survivability_score=Score(value=0.0),
            )

        query_words = set(query.lower().split())
        chunk_scores: list[tuple[int, float]] = []
        for idx, chunk in enumerate(chunks):
            chunk_words = set(chunk.text.lower().split())
            overlap = len(query_words & chunk_words)
            score = overlap / max(len(query_words), 1)
            chunk_scores.append((idx, score))

        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        top_k = max(1, len(chunks) // 3)
        retrieved_indices = {idx for idx, _ in chunk_scores[:top_k]}

        all_facts: list[str] = []
        for chunk in chunks:
            all_facts.extend(chunk.key_facts)
        all_facts = list(dict.fromkeys(all_facts))

        retrieved_text = " ".join(
            chunks[idx].text for idx in retrieved_indices
        )
        retrieved_lower = retrieved_text.lower()

        survived: list[str] = []
        lost: list[str] = []
        for fact in all_facts:
            fact_words = set(fact.lower().split())
            overlap = sum(1 for w in fact_words if w in retrieved_lower)
            if overlap / max(len(fact_words), 1) > 0.5:
                survived.append(fact)
            else:
                lost.append(fact)

        total = len(all_facts)
        survivability = (len(survived) / total * 100) if total > 0 else 100.0

        asset_id = ""
        if chunks:
            asset_id = chunks[0].chunk_id.split("-")[0] if chunks[0].chunk_id else ""

        return RAGSimulationResult(
            asset_id=asset_id,
            chunks=chunks,
            survived_facts=tuple(survived),
            lost_facts=tuple(lost),
            survivability_score=Score(value=round(min(survivability, 100.0), 2)),
        )


class RewriteService:
    """Pure domain service for generating rule-based rewrite suggestions.

    Analyses a GEO score to identify the weakest factors and produces
    concrete text-level suggestions for improvement.
    """

    _FACTOR_SUGGESTIONS: dict[GEOFactor, list[tuple[str, str, str]]] = {
        GEOFactor.ENTITY_DENSITY: [
            (
                "generic reference",
                "Replace generic terms with specific brand/entity names",
                "AI engines favour content with explicit, recognisable entity mentions. "
                "Replace pronouns and generic nouns with the actual entity name.",
            ),
            (
                "missing entity context",
                "Add contextual entity descriptions on first mention",
                "Provide a brief description when an entity is first mentioned to "
                "help AI engines build entity associations.",
            ),
        ],
        GEOFactor.ANSWER_SHAPE: [
            (
                "narrative block",
                "Convert long narrative paragraphs into Q&A format with clear headings",
                "AI engines extract answers more effectively from content structured "
                "as questions and direct answers rather than prose.",
            ),
            (
                "missing structure",
                "Add numbered or bulleted lists for multi-part information",
                "List-formatted content is more easily parsed by AI retrieval systems "
                "and more likely to appear in AI-generated answers.",
            ),
        ],
        GEOFactor.FACT_CITABILITY: [
            (
                "vague claim",
                "Add specific numbers, dates, and source attributions to claims",
                "AI engines prefer content with verifiable data points. Replace "
                "vague statements with specific, citable facts.",
            ),
            (
                "unsourced statistic",
                "Attribute statistics to named sources with dates",
                "Source attribution increases the likelihood that AI engines will "
                "cite the content as authoritative.",
            ),
        ],
        GEOFactor.RAG_SURVIVABILITY: [
            (
                "long paragraph",
                "Break content into self-contained paragraphs of 50-150 words",
                "RAG systems chunk content into fragments. Self-contained paragraphs "
                "ensure key facts survive the chunking process.",
            ),
            (
                "context dependency",
                "Make each section independently understandable without prior context",
                "Each chunk should carry enough context to be meaningful when "
                "retrieved in isolation by a RAG system.",
            ),
        ],
        GEOFactor.SEMANTIC_AUTHORITY: [
            (
                "weak language",
                "Use definitional and authoritative language patterns",
                "Phrases like 'is defined as', 'refers to', and structured arguments "
                "signal semantic authority to AI retrieval systems.",
            ),
        ],
        GEOFactor.FRESHNESS_SIGNALS: [
            (
                "missing date",
                "Add explicit dates and 'last updated' timestamps",
                "AI engines use temporal signals to assess content freshness. "
                "Include publication and update dates prominently.",
            ),
        ],
    }

    @staticmethod
    def generate_suggestions(
        asset: ContentAsset, geo_score: GEOScore
    ) -> tuple[RewriteSuggestion, ...]:
        """Generate rewrite suggestions targeting the lowest-scoring GEO factors.

        Analyses the GEO score to find factors below acceptable thresholds
        and produces rule-based suggestions for the weakest areas.

        Args:
            asset: The content asset to generate suggestions for.
            geo_score: The GEO score to analyse for weaknesses.

        Returns:
            A tuple of RewriteSuggestion instances targeting the weakest factors.
        """
        factor_scores: list[tuple[GEOFactor, Score]] = [
            (GEOFactor.ENTITY_DENSITY, geo_score.entity_density),
            (GEOFactor.ANSWER_SHAPE, geo_score.answer_shape),
            (GEOFactor.FACT_CITABILITY, geo_score.fact_citability),
            (GEOFactor.RAG_SURVIVABILITY, geo_score.rag_survivability),
            (GEOFactor.SEMANTIC_AUTHORITY, geo_score.semantic_authority),
            (GEOFactor.FRESHNESS_SIGNALS, geo_score.freshness_signals),
        ]

        factor_scores.sort(key=lambda x: x[1].value)

        suggestions: list[RewriteSuggestion] = []
        for factor, score in factor_scores:
            if score.value >= 80.0 and len(suggestions) >= 1:
                continue

            templates = RewriteService._FACTOR_SUGGESTIONS.get(factor, [])
            for original, suggested, rationale in templates:
                expected_impact_value = min(
                    round((80.0 - score.value) * 0.6, 2), 100.0
                )
                expected_impact_value = max(expected_impact_value, 5.0)

                suggestions.append(
                    RewriteSuggestion(
                        id=str(uuid4()),
                        asset_id=asset.id,
                        original_text=original,
                        suggested_text=suggested,
                        factor=factor,
                        expected_impact=Score(value=expected_impact_value),
                        rationale=rationale,
                    )
                )

        return tuple(suggestions)
