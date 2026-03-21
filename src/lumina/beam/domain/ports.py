"""
BEAM Domain Ports — Protocol interfaces for infrastructure dependencies

Architectural Intent:
- Defined in the domain layer so the domain never depends on infrastructure
- Infrastructure adapters implement these protocols
- Application layer receives concrete implementations via dependency injection
"""

from __future__ import annotations

from typing import Protocol

from lumina.beam.domain.entities import ContentAsset, GEOScore, RAGSimulationResult


class BeamRepositoryPort(Protocol):
    """Persistence port for BEAM aggregates and read models."""

    async def save_asset(self, asset: ContentAsset) -> None:
        """Persist a content asset (upsert)."""
        ...

    async def get_asset(self, asset_id: str) -> ContentAsset | None:
        """Retrieve a content asset by its identifier."""
        ...

    async def list_assets_for_brand(self, brand_id: str) -> list[ContentAsset]:
        """List all content assets belonging to a brand."""
        ...

    async def save_score(self, asset_id: str, score: GEOScore) -> None:
        """Persist a GEO score record for historical tracking."""
        ...

    async def get_score_history(self, asset_id: str) -> list[GEOScore]:
        """Retrieve the score history for a content asset."""
        ...

    async def save_simulation_result(
        self, result: RAGSimulationResult
    ) -> None:
        """Persist a RAG simulation result."""
        ...


class ContentCrawlerPort(Protocol):
    """Port for crawling web content."""

    async def crawl_url(self, url: str) -> tuple[str, str]:
        """Crawl a URL and return (title, content) as plain text.

        Args:
            url: The URL to crawl.

        Returns:
            A tuple of (page title, extracted text content).
        """
        ...

    async def crawl_sitemap(self, sitemap_url: str) -> list[str]:
        """Parse a sitemap and return all discovered URLs.

        Args:
            sitemap_url: URL of the sitemap XML.

        Returns:
            A list of URLs found in the sitemap.
        """
        ...


class VectorStorePort(Protocol):
    """Port for vector embedding storage and similarity search."""

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        ...

    async def similarity_search(
        self,
        query_embedding: list[float],
        chunks: list[tuple[str, list[float]]],
    ) -> list[tuple[str, float]]:
        """Find the most similar chunks to a query embedding.

        Args:
            query_embedding: The query vector.
            chunks: List of (chunk_id, embedding) pairs to search against.

        Returns:
            List of (chunk_id, similarity_score) pairs, ordered by similarity descending.
        """
        ...

    async def store_embeddings(
        self, asset_id: str, chunks: list[tuple[str, list[float]]]
    ) -> None:
        """Store chunk embeddings for a content asset.

        Args:
            asset_id: The content asset these chunks belong to.
            chunks: List of (chunk_id, embedding) pairs to store.
        """
        ...


class AIRewritePort(Protocol):
    """Port for AI-powered content rewriting."""

    async def rewrite_for_geo(
        self, content: str, factor: str, instructions: str
    ) -> str:
        """Rewrite content to improve a specific GEO factor.

        Args:
            content: The original content text to rewrite.
            factor: The GEO factor to optimise for.
            instructions: Specific rewriting instructions.

        Returns:
            The rewritten content text.
        """
        ...
