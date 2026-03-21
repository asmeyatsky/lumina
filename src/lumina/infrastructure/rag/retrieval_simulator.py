"""
RAG retrieval simulation pipeline.

Takes content, chunks it, embeds all chunks, generates synthetic queries,
and simulates retrieval to measure which facts survive the RAG pipeline.
Produces RAGSimulationResult domain entities.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

from lumina.shared.domain.value_objects import Score
from lumina.beam.domain.entities import ContentChunk, RAGSimulationResult

from lumina.infrastructure.nlp.fact_extractor import FactExtractor
from lumina.infrastructure.rag.chunker import ContentChunker
from lumina.infrastructure.rag.embedder import EmbeddingService, cosine_similarity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthetic query generation
# ---------------------------------------------------------------------------

_QUESTION_WORDS = ("what", "how", "why", "when", "where", "who", "which")


def _generate_synthetic_queries(content: str, max_queries: int = 5) -> list[str]:
    """Generate synthetic queries based on the content's key topics.

    Strategies:
    1. Extract existing questions from the content
    2. Turn headings into questions
    3. Create questions from key noun phrases
    """
    queries: list[str] = []
    seen: set[str] = set()

    def _add(q: str) -> None:
        normalised = q.strip().rstrip("?").lower()
        if normalised and normalised not in seen:
            seen.add(normalised)
            queries.append(q.strip())

    # 1. Extract existing questions
    existing_questions = re.findall(
        r"([^.!?\n]*\?)", content, re.MULTILINE
    )
    for q in existing_questions[:3]:
        q = q.strip()
        if len(q) > 10:
            _add(q)

    # 2. Turn headings into questions
    headings = re.findall(r"^#{1,4}\s+(.+)$", content, re.MULTILINE)
    for heading in headings[:3]:
        heading = heading.strip()
        if not heading.endswith("?"):
            _add(f"What is {heading}?")

    # 3. Extract key noun phrases and make questions
    # Find capitalized multi-word terms
    entities = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", content)
    unique_entities = list(dict.fromkeys(entities))
    for entity in unique_entities[:3]:
        _add(f"What is {entity}?")

    # 4. Extract sentences with statistics and ask about them
    stat_sentences = re.findall(
        r"([^.!?]*\d+(?:,\d{3})*(?:\.\d+)?%?[^.!?]*[.!?])", content
    )
    for sentence in stat_sentences[:2]:
        sentence = sentence.strip()
        if len(sentence) > 15:
            # Turn into a question by extracting the subject
            words = sentence.split()[:5]
            topic = " ".join(words)
            _add(f"What are the statistics about {topic}?")

    # 5. Fallback: use first paragraph as a summary query
    if not queries:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if paragraphs:
            first_para_words = paragraphs[0].split()[:10]
            _add(f"Tell me about {' '.join(first_para_words)}")

    return queries[:max_queries]


# ---------------------------------------------------------------------------
# RetrievalSimulator
# ---------------------------------------------------------------------------

class RetrievalSimulator:
    """RAG retrieval simulator that measures fact survival through chunking
    and embedding-based retrieval.

    Parameters
    ----------
    chunker:
        ContentChunker for splitting content into chunks.
    embedder:
        EmbeddingService for generating embeddings.
    fact_extractor:
        FactExtractor for identifying factual claims.
    top_k:
        Number of chunks to retrieve per query.
    """

    def __init__(
        self,
        chunker: ContentChunker,
        embedder: EmbeddingService,
        fact_extractor: FactExtractor | None = None,
        top_k: int = 3,
    ) -> None:
        self._chunker = chunker
        self._embedder = embedder
        self._fact_extractor = fact_extractor or FactExtractor()
        self._top_k = top_k

    async def simulate(
        self,
        content: str,
        asset_id: str = "",
        custom_queries: list[str] | None = None,
    ) -> RAGSimulationResult:
        """Run a full RAG retrieval simulation on the content.

        Steps:
        1. Chunk the content
        2. Extract facts from the full content
        3. Embed all chunks
        4. Generate (or use custom) queries
        5. For each query: embed, retrieve top-k chunks, check fact presence
        6. Aggregate fact survival statistics

        Returns a RAGSimulationResult domain entity.
        """
        if not content or not content.strip():
            return RAGSimulationResult(
                asset_id=asset_id,
                chunks=(),
                survived_facts=(),
                lost_facts=(),
                survivability_score=Score(value=0.0),
            )

        # 1. Chunk content
        raw_chunks = self._chunker.chunk_semantic(content)
        if not raw_chunks:
            return RAGSimulationResult(
                asset_id=asset_id,
                chunks=(),
                survived_facts=(),
                lost_facts=(),
                survivability_score=Score(value=0.0),
            )

        # 2. Extract facts from full content
        extracted_facts = self._fact_extractor.extract_facts(content)
        fact_texts = [f.text for f in extracted_facts]

        # Build domain ContentChunk objects
        chunk_texts = [c.text for c in raw_chunks]

        # 3. Embed all chunks
        chunk_embeddings = await self._embedder.embed_batch(chunk_texts)

        chunk_id_map: dict[str, int] = {}
        chunk_embedding_pairs: list[tuple[str, list[float]]] = []
        domain_chunks: list[ContentChunk] = []

        for idx, (raw_chunk, embedding) in enumerate(
            zip(raw_chunks, chunk_embeddings)
        ):
            chunk_id = str(uuid4())
            chunk_id_map[chunk_id] = idx
            chunk_embedding_pairs.append((chunk_id, embedding))

            # Extract per-chunk facts
            chunk_facts = self._fact_extractor.extract_facts(raw_chunk.text)
            chunk_fact_texts = tuple(f.text for f in chunk_facts)

            # Compute embedding quality heuristic
            quality_signals = 0
            if chunk_facts:
                quality_signals += min(len(chunk_facts) * 15, 40)
            word_count = len(raw_chunk.text.split())
            if word_count >= 50:
                quality_signals += 20
            if re.search(r"\b\d+\b", raw_chunk.text):
                quality_signals += 20
            if re.search(r"[.!?]", raw_chunk.text):
                quality_signals += 20

            domain_chunks.append(
                ContentChunk(
                    chunk_id=chunk_id,
                    text=raw_chunk.text,
                    token_count=raw_chunk.token_count,
                    key_facts=chunk_fact_texts,
                    embedding_quality=Score(
                        value=round(min(quality_signals, 100.0), 2)
                    ),
                )
            )

        # 4. Generate queries
        queries = custom_queries or _generate_synthetic_queries(content)
        if not queries:
            queries = ["Summarize the content"]

        # 5. Simulate retrieval for each query
        # Track which facts were found in retrieved chunks across all queries
        survived_set: set[str] = set()
        all_retrieved_texts: list[str] = []

        for query in queries:
            query_embedding = await self._embedder.embed(query)
            top_results = await self._embedder.similarity_search(
                query_embedding=query_embedding,
                chunk_embeddings=chunk_embedding_pairs,
                top_k=self._top_k,
            )

            for chunk_id, _sim in top_results:
                idx = chunk_id_map[chunk_id]
                all_retrieved_texts.append(chunk_texts[idx])

        retrieved_combined = " ".join(all_retrieved_texts).lower()

        # 6. Check fact survival
        survived: list[str] = []
        lost: list[str] = []

        for fact_text in fact_texts:
            # Check if key words from the fact appear in retrieved chunks
            fact_words = set(fact_text.lower().split())
            # Remove common stopwords for matching
            stopwords = {
                "the", "a", "an", "is", "are", "was", "were", "in", "on",
                "at", "to", "for", "of", "and", "or", "but", "with", "by",
                "from", "as", "it", "its", "this", "that", "has", "have",
                "had", "be", "been", "will", "would", "could", "should",
            }
            meaningful_words = fact_words - stopwords
            if not meaningful_words:
                meaningful_words = fact_words

            overlap = sum(1 for w in meaningful_words if w in retrieved_combined)
            overlap_ratio = overlap / max(len(meaningful_words), 1)

            if overlap_ratio > 0.5:
                survived.append(fact_text)
                survived_set.add(fact_text)
            else:
                lost.append(fact_text)

        # Compute survivability score
        total_facts = len(fact_texts)
        if total_facts > 0:
            survivability = len(survived) / total_facts * 100
        else:
            survivability = 100.0

        return RAGSimulationResult(
            asset_id=asset_id,
            chunks=tuple(domain_chunks),
            survived_facts=tuple(survived),
            lost_facts=tuple(lost),
            survivability_score=Score(
                value=round(min(survivability, 100.0), 2)
            ),
        )
