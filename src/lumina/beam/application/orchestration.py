"""
BEAM Content Scoring Pipeline — Parallel orchestration of the full scoring flow

Architectural Intent:
- Orchestrates crawl -> parallel factor scoring -> aggregate -> suggest
- Uses asyncio.gather for parallelism-first design
- Depends only on ports and domain services, never on infrastructure directly
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from uuid import uuid4

from lumina.shared.domain.value_objects import BrandId, Score, URL
from lumina.shared.ports.event_bus import EventBusPort

from lumina.beam.domain.entities import ContentAsset, GEOScore
from lumina.beam.domain.ports import BeamRepositoryPort, ContentCrawlerPort
from lumina.beam.domain.services import GEOScoringService, RewriteService
from lumina.beam.domain.value_objects import ContentType, GEOWeights


@dataclass(frozen=True)
class ScoringPipelineResult:
    """Result of the full content scoring pipeline."""

    asset: ContentAsset
    geo_score: GEOScore
    suggestions_generated: int


class ContentScoringPipeline:
    """Orchestrates the full scoring flow with parallel factor scoring.

    Pipeline stages:
    1. Crawl content (or accept raw text)
    2. Score all 6 GEO factors in parallel using asyncio.gather
    3. Aggregate into a GEOScore with weighted overall
    4. Generate rewrite suggestions for weak factors
    5. Persist and publish events
    """

    def __init__(
        self,
        repository: BeamRepositoryPort,
        crawler: ContentCrawlerPort,
        event_bus: EventBusPort,
        scoring_service: GEOScoringService | None = None,
        rewrite_service: RewriteService | None = None,
        weights: GEOWeights | None = None,
    ) -> None:
        self._repository = repository
        self._crawler = crawler
        self._event_bus = event_bus
        self._scoring_service = scoring_service or GEOScoringService()
        self._rewrite_service = rewrite_service or RewriteService()
        self._weights = weights or GEOWeights()

    async def execute(
        self,
        brand_id: str,
        url: str | None = None,
        raw_content: str | None = None,
        title: str | None = None,
        content_type: ContentType = ContentType.WEB_PAGE,
        brand_entities: list[str] | None = None,
        generate_suggestions: bool = True,
    ) -> ScoringPipelineResult:
        """Execute the full content scoring pipeline.

        Args:
            brand_id: The brand this content belongs to.
            url: Optional URL to crawl.
            raw_content: Optional raw content (used if no URL).
            title: Optional title.
            content_type: Type of the content asset.
            brand_entities: Entity names for density scoring.
            generate_suggestions: Whether to auto-generate rewrite suggestions.

        Returns:
            ScoringPipelineResult with the scored asset and metadata.

        Raises:
            ValueError: If neither url nor raw_content is provided.
        """
        if not url and not raw_content:
            raise ValueError("Either url or raw_content must be provided")

        entities = brand_entities or []

        if url:
            actual_title, actual_content = await self._crawler.crawl_url(url)
            actual_title = title or actual_title
            actual_url = URL(value=url)
        else:
            actual_title = title or "Untitled"
            actual_content = raw_content or ""
            actual_url = URL(value="https://content.local/inline")

        geo_score = await self._score_all_factors_parallel(
            actual_content, entities
        )

        asset_id = str(uuid4())
        asset = ContentAsset(
            id=asset_id,
            brand_id=BrandId(value=brand_id),
            url=actual_url,
            title=actual_title,
            raw_content=actual_content,
            content_type=content_type,
        )
        asset = asset.score(geo_score)

        suggestions_count = 0
        if generate_suggestions:
            suggestions = self._rewrite_service.generate_suggestions(
                asset, geo_score
            )
            asset = asset.add_suggestions(suggestions)
            suggestions_count = len(suggestions)

        await self._repository.save_asset(asset)
        await self._repository.save_score(asset_id, geo_score)
        await self._event_bus.publish(list(asset.domain_events))

        return ScoringPipelineResult(
            asset=asset,
            geo_score=geo_score,
            suggestions_generated=suggestions_count,
        )

    async def _score_all_factors_parallel(
        self, content: str, brand_entities: list[str]
    ) -> GEOScore:
        """Score all six GEO factors in parallel using asyncio.gather.

        Each factor scoring is wrapped in a coroutine to enable parallel
        execution even though the underlying methods are synchronous.
        """
        loop = asyncio.get_event_loop()
        svc = self._scoring_service

        entity_density_task = loop.run_in_executor(
            None, svc.score_entity_density, content, brand_entities
        )
        answer_shape_task = loop.run_in_executor(
            None, svc.score_answer_shape, content
        )
        fact_citability_task = loop.run_in_executor(
            None, svc.score_fact_citability, content
        )
        freshness_task = loop.run_in_executor(
            None, svc.score_freshness, content
        )
        authority_task = loop.run_in_executor(
            None, svc._score_semantic_authority, content
        )
        survivability_task = loop.run_in_executor(
            None, svc._score_rag_survivability, content
        )

        (
            entity_density,
            answer_shape,
            fact_citability,
            freshness_signals,
            semantic_authority,
            rag_survivability,
        ) = await asyncio.gather(
            entity_density_task,
            answer_shape_task,
            fact_citability_task,
            freshness_task,
            authority_task,
            survivability_task,
        )

        geo = GEOScore(
            overall=Score(value=0.0),
            entity_density=entity_density,
            answer_shape=answer_shape,
            fact_citability=fact_citability,
            rag_survivability=rag_survivability,
            semantic_authority=semantic_authority,
            freshness_signals=freshness_signals,
        )
        overall = geo.weighted_overall(self._weights)
        return replace(geo, overall=overall)
