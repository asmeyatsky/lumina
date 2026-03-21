"""
BEAM Application Command Tests

Tests for use cases with mocked ports (repository, crawler, event bus).
Validates full command flows, parallelisation, and event publishing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from lumina.shared.domain.events import DomainEvent
from lumina.shared.domain.value_objects import BrandId, Score, URL

from lumina.beam.application.commands import (
    BulkAuditCommand,
    GenerateRewritesCommand,
    ScoreContentCommand,
)
from lumina.beam.domain.entities import ContentAsset, GEOScore, RAGSimulationResult
from lumina.beam.domain.events import BulkAuditCompleted, ContentScored, RewriteSuggestionGenerated
from lumina.beam.domain.services import GEOScoringService, RAGSimulationService, RewriteService
from lumina.beam.domain.value_objects import ContentType


class FakeRepository:
    """In-memory fake implementation of BeamRepositoryPort for testing."""

    def __init__(self) -> None:
        self.assets: dict[str, ContentAsset] = {}
        self.scores: dict[str, list[GEOScore]] = {}
        self.simulations: dict[str, RAGSimulationResult] = {}

    async def save_asset(self, asset: ContentAsset) -> None:
        self.assets[asset.id] = asset

    async def get_asset(self, asset_id: str) -> ContentAsset | None:
        return self.assets.get(asset_id)

    async def list_assets_for_brand(self, brand_id: str) -> list[ContentAsset]:
        return [
            a for a in self.assets.values() if a.brand_id.value == brand_id
        ]

    async def save_score(self, asset_id: str, score: GEOScore) -> None:
        if asset_id not in self.scores:
            self.scores[asset_id] = []
        self.scores[asset_id].append(score)

    async def get_score_history(self, asset_id: str) -> list[GEOScore]:
        return self.scores.get(asset_id, [])

    async def save_simulation_result(self, result: RAGSimulationResult) -> None:
        self.simulations[result.asset_id] = result


class FakeCrawler:
    """Fake implementation of ContentCrawlerPort for testing."""

    def __init__(
        self,
        responses: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self.responses = responses or {}
        self.crawled_urls: list[str] = []

    async def crawl_url(self, url: str) -> tuple[str, str]:
        self.crawled_urls.append(url)
        if url in self.responses:
            return self.responses[url]
        return (
            "Test Page",
            "Acme Corp provides innovative solutions. "
            "According to research, 85% of customers recommend Acme Corp. "
            "Updated January 2025. "
            "## What is Acme Corp?\n\n"
            "Acme Corp is a leading technology company.\n\n"
            "1. Feature one\n2. Feature two\n3. Feature three",
        )

    async def crawl_sitemap(self, sitemap_url: str) -> list[str]:
        return list(self.responses.keys())


class FakeEventBus:
    """Fake implementation of EventBusPort for testing."""

    def __init__(self) -> None:
        self.published_events: list[DomainEvent] = []

    async def publish(self, events: list[DomainEvent]) -> None:
        self.published_events.extend(events)

    async def subscribe(self, event_type: type, handler: Any) -> None:
        pass


class TestScoreContentCommand:
    """Test ScoreContentCommand full flow."""

    @pytest.fixture
    def repository(self) -> FakeRepository:
        return FakeRepository()

    @pytest.fixture
    def crawler(self) -> FakeCrawler:
        return FakeCrawler()

    @pytest.fixture
    def event_bus(self) -> FakeEventBus:
        return FakeEventBus()

    @pytest.fixture
    def scoring_service(self) -> GEOScoringService:
        return GEOScoringService()

    async def test_score_content_from_url(
        self,
        repository: FakeRepository,
        crawler: FakeCrawler,
        event_bus: FakeEventBus,
        scoring_service: GEOScoringService,
    ) -> None:
        """Scoring content from a URL crawls, scores, saves, and publishes."""
        cmd = ScoreContentCommand(
            repository=repository,
            crawler=crawler,
            event_bus=event_bus,
            scoring_service=scoring_service,
        )

        result = await cmd.execute(
            brand_id="brand-1",
            url="https://example.com/page",
            brand_entities=["Acme Corp"],
        )

        assert result.asset.id
        assert result.asset.brand_id.value == "brand-1"
        assert result.geo_score.overall.value > 0.0
        assert result.asset.geo_score is not None

        assert "https://example.com/page" in crawler.crawled_urls

        assert result.asset.id in repository.assets
        assert result.asset.id in repository.scores

        assert len(event_bus.published_events) >= 1
        scored_events = [
            e for e in event_bus.published_events if isinstance(e, ContentScored)
        ]
        assert len(scored_events) == 1

    async def test_score_content_from_raw_text(
        self,
        repository: FakeRepository,
        crawler: FakeCrawler,
        event_bus: FakeEventBus,
        scoring_service: GEOScoringService,
    ) -> None:
        """Scoring raw content text does not crawl any URL."""
        cmd = ScoreContentCommand(
            repository=repository,
            crawler=crawler,
            event_bus=event_bus,
            scoring_service=scoring_service,
        )

        result = await cmd.execute(
            brand_id="brand-1",
            raw_content="Acme Corp builds great products. 95% customer satisfaction.",
            title="Test Content",
            brand_entities=["Acme Corp"],
        )

        assert result.asset.title == "Test Content"
        assert len(crawler.crawled_urls) == 0
        assert result.geo_score.overall.value > 0.0

    async def test_score_content_requires_url_or_content(
        self,
        repository: FakeRepository,
        crawler: FakeCrawler,
        event_bus: FakeEventBus,
        scoring_service: GEOScoringService,
    ) -> None:
        """Raises ValueError if neither URL nor raw_content is provided."""
        cmd = ScoreContentCommand(
            repository=repository,
            crawler=crawler,
            event_bus=event_bus,
            scoring_service=scoring_service,
        )

        with pytest.raises(ValueError, match="Either url or raw_content"):
            await cmd.execute(brand_id="brand-1")


class TestBulkAuditCommand:
    """Test BulkAuditCommand parallelisation."""

    @pytest.fixture
    def repository(self) -> FakeRepository:
        return FakeRepository()

    @pytest.fixture
    def event_bus(self) -> FakeEventBus:
        return FakeEventBus()

    @pytest.fixture
    def scoring_service(self) -> GEOScoringService:
        return GEOScoringService()

    async def test_bulk_audit_scores_all_urls(
        self,
        repository: FakeRepository,
        event_bus: FakeEventBus,
        scoring_service: GEOScoringService,
    ) -> None:
        """Bulk audit scores all provided URLs."""
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]
        crawler = FakeCrawler(
            responses={
                url: ("Page Title", "Acme Corp content with facts. 42% growth in 2024.")
                for url in urls
            }
        )

        cmd = BulkAuditCommand(
            repository=repository,
            crawler=crawler,
            event_bus=event_bus,
            scoring_service=scoring_service,
            max_concurrency=2,
        )

        results = await cmd.execute(
            brand_id="brand-1",
            urls=urls,
            brand_entities=["Acme Corp"],
        )

        assert len(results) == 3
        assert len(repository.assets) == 3

        audit_events = [
            e for e in event_bus.published_events if isinstance(e, BulkAuditCompleted)
        ]
        assert len(audit_events) == 1
        assert audit_events[0].total_assets == 3

    async def test_bulk_audit_handles_failures_gracefully(
        self,
        repository: FakeRepository,
        event_bus: FakeEventBus,
        scoring_service: GEOScoringService,
    ) -> None:
        """Bulk audit continues when individual URLs fail."""

        class FailingCrawler:
            def __init__(self) -> None:
                self.call_count = 0

            async def crawl_url(self, url: str) -> tuple[str, str]:
                self.call_count += 1
                if "fail" in url:
                    raise RuntimeError("Crawl failed")
                return ("Title", "Acme Corp content.")

            async def crawl_sitemap(self, sitemap_url: str) -> list[str]:
                return []

        crawler = FailingCrawler()

        cmd = BulkAuditCommand(
            repository=repository,
            crawler=crawler,
            event_bus=event_bus,
            scoring_service=scoring_service,
        )

        results = await cmd.execute(
            brand_id="brand-1",
            urls=[
                "https://example.com/good",
                "https://example.com/fail",
                "https://example.com/also-good",
            ],
            brand_entities=["Acme Corp"],
        )

        assert len(results) == 2
        assert crawler.call_count == 3

    async def test_bulk_audit_respects_concurrency_limit(
        self,
        repository: FakeRepository,
        event_bus: FakeEventBus,
        scoring_service: GEOScoringService,
    ) -> None:
        """Bulk audit uses a semaphore to limit concurrency."""
        import asyncio

        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        class TrackingCrawler:
            async def crawl_url(self, url: str) -> tuple[str, str]:
                nonlocal max_concurrent, current_concurrent
                async with lock:
                    current_concurrent += 1
                    if current_concurrent > max_concurrent:
                        max_concurrent = current_concurrent
                await asyncio.sleep(0.01)
                async with lock:
                    current_concurrent -= 1
                return ("Title", "Content here.")

            async def crawl_sitemap(self, sitemap_url: str) -> list[str]:
                return []

        crawler = TrackingCrawler()
        cmd = BulkAuditCommand(
            repository=repository,
            crawler=crawler,
            event_bus=event_bus,
            scoring_service=scoring_service,
            max_concurrency=2,
        )

        urls = [f"https://example.com/page{i}" for i in range(6)]
        await cmd.execute(brand_id="brand-1", urls=urls)

        assert max_concurrent <= 2


class TestGenerateRewritesCommand:
    """Test GenerateRewritesCommand produces suggestions."""

    @pytest.fixture
    def repository(self) -> FakeRepository:
        return FakeRepository()

    @pytest.fixture
    def event_bus(self) -> FakeEventBus:
        return FakeEventBus()

    @pytest.fixture
    def rewrite_service(self) -> RewriteService:
        return RewriteService()

    async def test_generates_suggestions_for_scored_asset(
        self,
        repository: FakeRepository,
        event_bus: FakeEventBus,
        rewrite_service: RewriteService,
    ) -> None:
        """Generates suggestions for a previously scored content asset."""
        geo_score = GEOScore(
            overall=Score(value=40.0),
            entity_density=Score(value=30.0),
            answer_shape=Score(value=45.0),
            fact_citability=Score(value=25.0),
            rag_survivability=Score(value=50.0),
            semantic_authority=Score(value=55.0),
            freshness_signals=Score(value=35.0),
        )

        asset = ContentAsset(
            id="asset-1",
            brand_id=BrandId(value="brand-1"),
            url=URL(value="https://example.com/page"),
            title="Test Page",
            raw_content="Some test content.",
            content_type=ContentType.WEB_PAGE,
        )
        asset = asset.score(geo_score)
        await repository.save_asset(asset)

        cmd = GenerateRewritesCommand(
            repository=repository,
            event_bus=event_bus,
            rewrite_service=rewrite_service,
        )

        updated_asset = await cmd.execute(asset_id="asset-1")

        assert len(updated_asset.suggestions) > 0

        rewrite_events = [
            e
            for e in event_bus.published_events
            if isinstance(e, RewriteSuggestionGenerated)
        ]
        assert len(rewrite_events) > 0

    async def test_raises_for_unscored_asset(
        self,
        repository: FakeRepository,
        event_bus: FakeEventBus,
        rewrite_service: RewriteService,
    ) -> None:
        """Raises ValueError if the asset has not been scored yet."""
        asset = ContentAsset(
            id="asset-2",
            brand_id=BrandId(value="brand-1"),
            url=URL(value="https://example.com/page2"),
            title="Unscored Page",
            raw_content="Content without a score.",
            content_type=ContentType.WEB_PAGE,
        )
        await repository.save_asset(asset)

        cmd = GenerateRewritesCommand(
            repository=repository,
            event_bus=event_bus,
            rewrite_service=rewrite_service,
        )

        with pytest.raises(ValueError, match="has not been scored"):
            await cmd.execute(asset_id="asset-2")

    async def test_raises_for_missing_asset(
        self,
        repository: FakeRepository,
        event_bus: FakeEventBus,
        rewrite_service: RewriteService,
    ) -> None:
        """Raises ValueError if the asset does not exist."""
        cmd = GenerateRewritesCommand(
            repository=repository,
            event_bus=event_bus,
            rewrite_service=rewrite_service,
        )

        with pytest.raises(ValueError, match="not found"):
            await cmd.execute(asset_id="nonexistent")
