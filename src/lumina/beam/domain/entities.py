"""
BEAM Domain Entities

Architectural Intent:
- Frozen dataclasses enforce immutability — state changes produce new instances
- Domain events are collected on aggregates for post-persistence dispatch
- GEOScore is a rich value object encapsulating the six-factor scoring model
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.value_objects import BrandId, Score, URL

from lumina.beam.domain.events import ContentScored, RewriteSuggestionGenerated
from lumina.beam.domain.value_objects import ContentType, GEOFactor, GEOWeights


@dataclass(frozen=True)
class GEOScore:
    """Six-factor GEO score for a content asset.

    Each factor is scored 0-100. The weighted overall score uses PRD weights:
    Entity Density 20%, Answer Shape 20%, Fact Citability 20%,
    RAG Survivability 20%, Semantic Authority 10%, Freshness Signals 10%.
    """

    overall: Score
    entity_density: Score
    answer_shape: Score
    fact_citability: Score
    rag_survivability: Score
    semantic_authority: Score
    freshness_signals: Score

    def weighted_overall(self, weights: GEOWeights | None = None) -> Score:
        """Compute the weighted overall GEO score.

        Args:
            weights: Optional custom weights. Uses PRD defaults if not provided.

        Returns:
            A Score representing the weighted average of all six factors.
        """
        w = weights or GEOWeights()
        weighted = (
            self.entity_density.value * w.entity_density
            + self.answer_shape.value * w.answer_shape
            + self.fact_citability.value * w.fact_citability
            + self.rag_survivability.value * w.rag_survivability
            + self.semantic_authority.value * w.semantic_authority
            + self.freshness_signals.value * w.freshness_signals
        )
        return Score(value=round(weighted, 2))


@dataclass(frozen=True)
class ContentChunk:
    """A chunk of content produced by the RAG simulation chunking process."""

    chunk_id: str
    text: str
    token_count: int
    key_facts: tuple[str, ...]
    embedding_quality: Score


@dataclass(frozen=True)
class RewriteSuggestion:
    """A rule-based suggestion for improving a content asset's GEO score."""

    id: str
    asset_id: str
    original_text: str
    suggested_text: str
    factor: GEOFactor
    expected_impact: Score
    rationale: str


@dataclass(frozen=True)
class RAGSimulationResult:
    """Result of a RAG retrieval simulation on a content asset."""

    asset_id: str
    chunks: tuple[ContentChunk, ...]
    survived_facts: tuple[str, ...]
    lost_facts: tuple[str, ...]
    survivability_score: Score


@dataclass(frozen=True)
class ContentAsset:
    """Aggregate root representing a piece of content to be optimised for AI retrieval.

    Immutable — all state transitions return new instances with domain events collected.
    """

    id: str
    brand_id: BrandId
    url: URL
    title: str
    raw_content: str
    content_type: ContentType
    geo_score: GEOScore | None = None
    last_scored_at: datetime | None = None
    suggestions: tuple[RewriteSuggestion, ...] = ()
    domain_events: tuple = ()

    def score(self, geo_score: GEOScore) -> ContentAsset:
        """Apply a new GEO score, producing a new ContentAsset with a ContentScored event.

        Args:
            geo_score: The newly computed GEO score.

        Returns:
            A new ContentAsset with the score applied and a domain event recorded.
        """
        previous_score = self.geo_score.overall.value if self.geo_score else None
        event = ContentScored(
            aggregate_id=self.id,
            brand_id=self.brand_id.value,
            asset_id=self.id,
            url=self.url.value,
            overall_score=geo_score.overall.value,
            previous_score=previous_score,
        )
        return replace(
            self,
            geo_score=geo_score,
            last_scored_at=datetime.now(UTC),
            domain_events=self.domain_events + (event,),
        )

    def add_suggestions(
        self, suggestions: tuple[RewriteSuggestion, ...]
    ) -> ContentAsset:
        """Attach rewrite suggestions, producing a new ContentAsset with events.

        Args:
            suggestions: Tuple of rewrite suggestions to attach.

        Returns:
            A new ContentAsset with suggestions and corresponding domain events.
        """
        new_events: list = []
        for suggestion in suggestions:
            new_events.append(
                RewriteSuggestionGenerated(
                    aggregate_id=self.id,
                    brand_id=self.brand_id.value,
                    asset_id=self.id,
                    factor=suggestion.factor.value,
                    expected_impact=suggestion.expected_impact.value,
                )
            )
        return replace(
            self,
            suggestions=self.suggestions + suggestions,
            domain_events=self.domain_events + tuple(new_events),
        )
