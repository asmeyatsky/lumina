"""
Embedding service using OpenAI text-embedding-3-small.

Provides embedding generation, batch support with rate limiting,
in-memory LRU caching, and cosine similarity computation.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

# Embedding dimension for text-embedding-3-small
EMBEDDING_DIMENSION = 1536


# ---------------------------------------------------------------------------
# LRU embedding cache
# ---------------------------------------------------------------------------

class _EmbeddingCache:
    """In-memory LRU cache for embedding vectors."""

    def __init__(self, max_size: int = 1024) -> None:
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> list[float] | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, value: list[float]) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
        self._cache[key] = value

    def __len__(self) -> int:
        return len(self._cache)


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns a value between -1.0 and 1.0.
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Vector dimensions must match: {len(vec_a)} != {len(vec_b)}"
        )

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# EmbeddingService
# ---------------------------------------------------------------------------

class EmbeddingService:
    """Embedding service using OpenAI text-embedding-3-small.

    Satisfies the embedding needs of the RAG simulation pipeline.

    Parameters
    ----------
    openai_client:
        An instantiated ``openai.AsyncOpenAI`` client.
    model:
        The embedding model to use.
    cache_size:
        Maximum number of cached embeddings.
    batch_size:
        Maximum number of texts per API call.
    rate_limit_delay:
        Seconds to wait between batch API calls for rate limiting.
    """

    def __init__(
        self,
        openai_client: Any,
        model: str = "text-embedding-3-small",
        cache_size: int = 1024,
        batch_size: int = 100,
        rate_limit_delay: float = 0.1,
    ) -> None:
        self._client = openai_client
        self._model = model
        self._cache = _EmbeddingCache(max_size=cache_size)
        self._batch_size = batch_size
        self._rate_limit_delay = rate_limit_delay

    @staticmethod
    def _cache_key(text: str) -> str:
        """Generate a cache key for the given text."""
        return hashlib.sha256(text.encode()).hexdigest()

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text.

        Returns a cached result if available.
        """
        key = self._cache_key(text)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        embedding = response.data[0].embedding
        self._cache.put(key, embedding)
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts with rate limiting.

        Uses batching and caching for efficiency. Texts that are already
        cached are not sent to the API.
        """
        if not texts:
            return []

        # Separate cached vs uncached
        results: dict[int, list[float]] = {}
        uncached: list[tuple[int, str]] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            cached = self._cache.get(key)
            if cached is not None:
                results[i] = cached
            else:
                uncached.append((i, text))

        # Batch API calls for uncached texts
        for batch_start in range(0, len(uncached), self._batch_size):
            batch = uncached[batch_start: batch_start + self._batch_size]
            batch_texts = [text for _, text in batch]

            response = await self._client.embeddings.create(
                model=self._model,
                input=batch_texts,
            )

            for (original_idx, text), embedding_data in zip(
                batch, response.data
            ):
                embedding = embedding_data.embedding
                self._cache.put(self._cache_key(text), embedding)
                results[original_idx] = embedding

            # Rate limiting between batches
            if batch_start + self._batch_size < len(uncached):
                await asyncio.sleep(self._rate_limit_delay)

        # Reconstruct ordered results
        return [results[i] for i in range(len(texts))]

    async def similarity_search(
        self,
        query_embedding: list[float],
        chunk_embeddings: list[tuple[str, list[float]]],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Find the top-k most similar chunks to a query embedding.

        Parameters
        ----------
        query_embedding:
            The query vector.
        chunk_embeddings:
            List of (chunk_id, embedding) pairs.
        top_k:
            Number of top results to return.

        Returns
        -------
        List of (chunk_id, similarity_score) pairs, ordered by
        similarity descending.
        """
        if not chunk_embeddings:
            return []

        scored: list[tuple[str, float]] = []
        for chunk_id, embedding in chunk_embeddings:
            sim = cosine_similarity(query_embedding, embedding)
            scored.append((chunk_id, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
