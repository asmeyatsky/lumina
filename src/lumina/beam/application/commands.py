"""
BEAM Application Commands — Write-side use cases

Architectural Intent:
- Each command encapsulates a single write-side use case
- Commands depend on ports (protocols), never on concrete infrastructure
- Domain events are collected on aggregates and published after persistence
- Parallelism-first: BulkAuditCommand uses asyncio.gather with semaphore
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import uuid4

from lumina.shared.domain.value_objects import BrandId, Score, URL
from lumina.shared.ports.event_bus import EventBusPort

from lumina.beam.domain.entities import ContentAsset, GEOScore
from lumina.beam.domain.events import BulkAuditCompleted
from lumina.beam.domain.ports import BeamRepositoryPort, ContentCrawlerPort
from lumina.beam.domain.services import GEOScoringService, RAGSimulationService, RewriteService
from lumina.beam.domain.value_objects import ContentType


@dataclass(frozen=True)
class ScoreContentResult:
    """Result of scoring a content asset."""

    asset: ContentAsset
    geo_score: GEOScore


@dataclass(frozen=True)
class ScoreContentCommand:
    """Ingests content from a URL or raw text, runs the GEO scoring pipeline,
    persists the result, and publishes domain events.
    """

    repository: BeamRepositoryPort
    crawler: ContentCrawlerPort
    event_bus: EventBusPort
    scoring_service: GEOScoringService

    async def execute(
        self,
        brand_id: str,
        url: str | None = None,
        raw_content: str | None = None,
        title: str | None = None,
        content_type: ContentType = ContentType.WEB_PAGE,
        brand_entities: list[str] | None = None,
    ) -> ScoreContentResult:
        """Execute the content scoring use case.

        Either url or raw_content must be provided. If url is provided,
        the content will be crawled first.

        Args:
            brand_id: The brand this content belongs to.
            url: Optional URL to crawl for content.
            raw_content: Optional raw content text (used if url not provided).
            title: Optional title (auto-extracted if crawling).
            content_type: The type of content asset.
            brand_entities: Entity names for entity density scoring.

        Returns:
            ScoreContentResult with the scored asset and GEO score.

        Raises:
            ValueError: If neither url nor raw_content is provided.
        """
        if not url and not raw_content:
            raise ValueError("Either url or raw_content must be provided")

        entities = brand_entities or []

        if url:
            crawled_title, crawled_content = await self.crawler.crawl_url(url)
            actual_title = title or crawled_title
            actual_content = crawled_content
            actual_url = URL(value=url)
        else:
            actual_title = title or "Untitled"
            actual_content = raw_content or ""
            actual_url = URL(value="https://content.local/inline")

        asset_id = str(uuid4())
        geo_score = self.scoring_service.calculate_geo_score(
            actual_content, entities
        )

        asset = ContentAsset(
            id=asset_id,
            brand_id=BrandId(value=brand_id),
            url=actual_url,
            title=actual_title,
            raw_content=actual_content,
            content_type=content_type,
        )

        asset = asset.score(geo_score)

        await self.repository.save_asset(asset)
        await self.repository.save_score(asset_id, geo_score)
        await self.event_bus.publish(list(asset.domain_events))

        return ScoreContentResult(asset=asset, geo_score=geo_score)


@dataclass(frozen=True)
class RunRAGSimulationCommand:
    """Runs a RAG retrieval simulation on a content asset and persists the result."""

    repository: BeamRepositoryPort
    event_bus: EventBusPort
    simulation_service: RAGSimulationService

    async def execute(
        self,
        asset_id: str,
        query: str,
        chunk_size: int = 512,
    ):
        """Execute the RAG simulation use case.

        Args:
            asset_id: The content asset to simulate retrieval on.
            query: The simulated query to test against.
            chunk_size: Target token count per chunk.

        Returns:
            The RAGSimulationResult.

        Raises:
            ValueError: If the asset is not found.
        """
        asset = await self.repository.get_asset(asset_id)
        if asset is None:
            raise ValueError(f"Asset {asset_id} not found")

        chunks = self.simulation_service.chunk_content(
            asset.raw_content, chunk_size
        )
        result = self.simulation_service.simulate_retrieval(chunks, query)

        from dataclasses import replace
        result = replace(result, asset_id=asset_id)

        await self.repository.save_simulation_result(result)

        from lumina.beam.domain.events import RAGSimulationCompleted

        event = RAGSimulationCompleted(
            aggregate_id=asset_id,
            brand_id=asset.brand_id.value,
            asset_id=asset_id,
            survivability_score=result.survivability_score.value,
            facts_lost_count=len(result.lost_facts),
        )
        await self.event_bus.publish([event])

        return result


@dataclass(frozen=True)
class GenerateRewritesCommand:
    """Generates rewrite suggestions for a scored content asset."""

    repository: BeamRepositoryPort
    event_bus: EventBusPort
    rewrite_service: RewriteService

    async def execute(self, asset_id: str):
        """Execute the rewrite suggestion generation use case.

        Args:
            asset_id: The content asset to generate suggestions for.

        Returns:
            The updated ContentAsset with suggestions attached.

        Raises:
            ValueError: If the asset is not found or has not been scored.
        """
        asset = await self.repository.get_asset(asset_id)
        if asset is None:
            raise ValueError(f"Asset {asset_id} not found")
        if asset.geo_score is None:
            raise ValueError(
                f"Asset {asset_id} has not been scored yet. Run scoring first."
            )

        suggestions = self.rewrite_service.generate_suggestions(
            asset, asset.geo_score
        )
        updated_asset = asset.add_suggestions(suggestions)

        await self.repository.save_asset(updated_asset)
        await self.event_bus.publish(list(updated_asset.domain_events))

        return updated_asset


@dataclass(frozen=True)
class BulkAuditCommand:
    """Scores multiple URLs in parallel with rate limiting.

    Uses asyncio.gather with a semaphore to control concurrency.
    """

    repository: BeamRepositoryPort
    crawler: ContentCrawlerPort
    event_bus: EventBusPort
    scoring_service: GEOScoringService
    max_concurrency: int = 5

    async def execute(
        self,
        brand_id: str,
        urls: list[str],
        brand_entities: list[str] | None = None,
    ) -> list[ScoreContentResult]:
        """Execute the bulk audit use case.

        Scores all provided URLs in parallel, respecting the concurrency limit.

        Args:
            brand_id: The brand these URLs belong to.
            urls: List of URLs to crawl and score.
            brand_entities: Entity names for entity density scoring.

        Returns:
            A list of ScoreContentResult for each successfully scored URL.
        """
        semaphore = asyncio.Semaphore(self.max_concurrency)

        score_cmd = ScoreContentCommand(
            repository=self.repository,
            crawler=self.crawler,
            event_bus=self.event_bus,
            scoring_service=self.scoring_service,
        )

        async def score_one(url: str) -> ScoreContentResult | None:
            async with semaphore:
                try:
                    return await score_cmd.execute(
                        brand_id=brand_id,
                        url=url,
                        brand_entities=brand_entities,
                    )
                except Exception:
                    return None

        tasks = [score_one(url) for url in urls]
        raw_results = await asyncio.gather(*tasks)
        results = [r for r in raw_results if r is not None]

        if results:
            scores = [r.geo_score.overall.value for r in results]
            avg_score = sum(scores) / len(scores)

            audit_event = BulkAuditCompleted(
                aggregate_id=brand_id,
                brand_id=brand_id,
                total_assets=len(results),
                avg_score=round(avg_score, 2),
            )
            await self.event_bus.publish([audit_event])

        return results
