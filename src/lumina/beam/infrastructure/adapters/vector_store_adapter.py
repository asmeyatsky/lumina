"""
Vector Store Adapter — Infrastructure implementation of VectorStorePort

Uses the Pinecone client for vector storage and similarity search.
"""

from __future__ import annotations

import math
from typing import Any

from pinecone import Pinecone


class PineconeVectorStoreAdapter:
    """Implements VectorStorePort using the Pinecone vector database.

    Handles embedding storage, retrieval, and cosine similarity search.
    """

    def __init__(
        self,
        api_key: str,
        index_name: str,
        namespace: str = "beam",
        embedding_dimension: int = 1536,
    ) -> None:
        self._api_key = api_key
        self._index_name = index_name
        self._namespace = namespace
        self._embedding_dimension = embedding_dimension
        self._client = Pinecone(api_key=api_key)
        self._index = self._client.Index(index_name)

    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        This is a placeholder that returns a normalised hash-based vector.
        In production, this would delegate to an embedding model (e.g. OpenAI
        text-embedding-3-small or a local model).

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        embedding = [0.0] * self._embedding_dimension

        words = text.lower().split()
        for i, word in enumerate(words):
            idx = hash(word) % self._embedding_dimension
            embedding[idx] += 1.0 / (1.0 + i * 0.01)

        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    async def similarity_search(
        self,
        query_embedding: list[float],
        chunks: list[tuple[str, list[float]]],
    ) -> list[tuple[str, float]]:
        """Find the most similar chunks to a query embedding using cosine similarity.

        If chunks are provided inline, computes similarity locally.
        Otherwise queries the Pinecone index.

        Args:
            query_embedding: The query vector.
            chunks: List of (chunk_id, embedding) pairs to search against.

        Returns:
            List of (chunk_id, similarity_score) pairs, sorted by similarity descending.
        """
        if chunks:
            results = []
            for chunk_id, embedding in chunks:
                similarity = self._cosine_similarity(query_embedding, embedding)
                results.append((chunk_id, similarity))
            results.sort(key=lambda x: x[1], reverse=True)
            return results

        query_response = self._index.query(
            vector=query_embedding,
            top_k=10,
            namespace=self._namespace,
            include_values=False,
        )

        results = []
        for match in query_response.get("matches", []):
            results.append((match["id"], match["score"]))
        return results

    async def store_embeddings(
        self, asset_id: str, chunks: list[tuple[str, list[float]]]
    ) -> None:
        """Store chunk embeddings in Pinecone for a content asset.

        Args:
            asset_id: The content asset these chunks belong to.
            chunks: List of (chunk_id, embedding) pairs to store.
        """
        vectors: list[dict[str, Any]] = []
        for chunk_id, embedding in chunks:
            vectors.append(
                {
                    "id": chunk_id,
                    "values": embedding,
                    "metadata": {"asset_id": asset_id},
                }
            )

        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            self._index.upsert(
                vectors=batch,
                namespace=self._namespace,
            )

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            raise ValueError("Vectors must have the same dimension")

        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(x * x for x in b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)
