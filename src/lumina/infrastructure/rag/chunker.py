"""
Advanced content chunking for RAG simulation.

Provides semantic chunking (by paragraphs/sections), sliding window
chunking with configurable overlap, token counting via tiktoken,
sentence boundary preservation, and chunk metadata enrichment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import tiktoken


@dataclass(frozen=True)
class ChunkMetadata:
    """Metadata attached to a content chunk."""

    section_header: Optional[str] = None
    position_index: int = 0
    total_chunks: int = 0
    key_entities: tuple[str, ...] = ()
    starts_with_heading: bool = False


@dataclass(frozen=True)
class Chunk:
    """A chunk of content with metadata."""

    text: str
    token_count: int
    metadata: ChunkMetadata


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

_SENTENCE_BOUNDARY = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z\d\"'])"
)

_HEADING_PATTERN = re.compile(
    r"^(#{1,6})\s+(.+)$", re.MULTILINE
)

_ENTITY_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, preserving sentence boundaries."""
    sentences = _SENTENCE_BOUNDARY.split(text)
    return [s.strip() for s in sentences if s.strip()]


def _extract_entities(text: str) -> tuple[str, ...]:
    """Extract capitalized multi-word names as entity candidates."""
    matches = _ENTITY_PATTERN.findall(text)
    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return tuple(result[:10])  # Cap at 10 entities per chunk


# ---------------------------------------------------------------------------
# Token counter
# ---------------------------------------------------------------------------

class TokenCounter:
    """Token counter using tiktoken with cl100k_base encoding."""

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self._encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        """Count the number of tokens in the given text."""
        if not text:
            return 0
        return len(self._encoding.encode(text))

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within max_tokens."""
        tokens = self._encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self._encoding.decode(tokens[:max_tokens])


# ---------------------------------------------------------------------------
# ContentChunker
# ---------------------------------------------------------------------------

@dataclass
class ContentChunker:
    """Advanced content chunker with semantic and sliding window modes.

    Parameters
    ----------
    max_chunk_tokens:
        Maximum token count per chunk (default 512).
    overlap_tokens:
        Number of overlap tokens for sliding window mode (default 50).
    encoding_name:
        Tiktoken encoding to use (default cl100k_base).
    """

    max_chunk_tokens: int = 512
    overlap_tokens: int = 50
    encoding_name: str = "cl100k_base"
    _token_counter: TokenCounter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._token_counter = TokenCounter(self.encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text."""
        return self._token_counter.count(text)

    # -- Semantic chunking ---------------------------------------------------

    def chunk_semantic(self, content: str) -> list[Chunk]:
        """Split content by paragraphs and sections, respecting token limits.

        Splits on double-newlines (paragraph boundaries) and markdown
        headings. If a paragraph exceeds the token limit, it is further
        split at sentence boundaries.

        Returns a list of Chunk objects with metadata.
        """
        if not content or not content.strip():
            return []

        # Split into sections by headings and paragraphs
        sections = self._split_into_sections(content)

        raw_chunks: list[tuple[str, Optional[str]]] = []
        for section_header, section_text in sections:
            paragraphs = [
                p.strip() for p in section_text.split("\n\n") if p.strip()
            ]
            if not paragraphs:
                continue

            current_text = ""
            for para in paragraphs:
                candidate = (
                    f"{current_text}\n\n{para}" if current_text else para
                )
                if self._token_counter.count(candidate) <= self.max_chunk_tokens:
                    current_text = candidate
                else:
                    # Flush current chunk if non-empty
                    if current_text:
                        raw_chunks.append((current_text, section_header))
                    # If the paragraph itself exceeds limit, split by sentences
                    if self._token_counter.count(para) > self.max_chunk_tokens:
                        sentence_chunks = self._split_by_sentences(para)
                        for sc in sentence_chunks:
                            raw_chunks.append((sc, section_header))
                        current_text = ""
                    else:
                        current_text = para

            if current_text:
                raw_chunks.append((current_text, section_header))

        # Build Chunk objects with metadata
        total = len(raw_chunks)
        chunks: list[Chunk] = []
        for idx, (text, header) in enumerate(raw_chunks):
            token_count = self._token_counter.count(text)
            entities = _extract_entities(text)
            starts_heading = text.lstrip().startswith("#")
            chunks.append(
                Chunk(
                    text=text,
                    token_count=token_count,
                    metadata=ChunkMetadata(
                        section_header=header,
                        position_index=idx,
                        total_chunks=total,
                        key_entities=entities,
                        starts_with_heading=starts_heading,
                    ),
                )
            )

        # Fix total_chunks now that we know the final count
        if chunks:
            final_total = len(chunks)
            chunks = [
                Chunk(
                    text=c.text,
                    token_count=c.token_count,
                    metadata=ChunkMetadata(
                        section_header=c.metadata.section_header,
                        position_index=c.metadata.position_index,
                        total_chunks=final_total,
                        key_entities=c.metadata.key_entities,
                        starts_with_heading=c.metadata.starts_with_heading,
                    ),
                )
                for c in chunks
            ]

        return chunks

    # -- Sliding window chunking ---------------------------------------------

    def chunk_sliding_window(self, content: str) -> list[Chunk]:
        """Split content using a sliding window with overlap.

        Uses token-level windowing with configurable overlap. Sentence
        boundaries are respected: the window expands or contracts slightly
        to avoid cutting mid-sentence.

        Returns a list of Chunk objects with metadata.
        """
        if not content or not content.strip():
            return []

        sentences = _split_sentences(content)
        if not sentences:
            return [
                Chunk(
                    text=content.strip(),
                    token_count=self._token_counter.count(content.strip()),
                    metadata=ChunkMetadata(
                        position_index=0, total_chunks=1
                    ),
                )
            ]

        # Pre-compute token counts for each sentence
        sentence_tokens = [self._token_counter.count(s) for s in sentences]

        chunks: list[Chunk] = []
        start_idx = 0

        while start_idx < len(sentences):
            # Greedily add sentences until we exceed max_chunk_tokens
            end_idx = start_idx
            current_tokens = 0

            while end_idx < len(sentences):
                added = sentence_tokens[end_idx]
                if current_tokens + added > self.max_chunk_tokens and end_idx > start_idx:
                    break
                current_tokens += added
                end_idx += 1

            chunk_text = " ".join(sentences[start_idx:end_idx])
            token_count = self._token_counter.count(chunk_text)
            entities = _extract_entities(chunk_text)

            chunks.append(
                Chunk(
                    text=chunk_text,
                    token_count=token_count,
                    metadata=ChunkMetadata(
                        position_index=len(chunks),
                        total_chunks=0,  # fixed up below
                        key_entities=entities,
                    ),
                )
            )

            # Advance by (window_size - overlap) in token terms
            # Find how many sentences to skip back for overlap
            overlap_tokens_remaining = self.overlap_tokens
            overlap_start = end_idx
            while overlap_start > start_idx and overlap_tokens_remaining > 0:
                overlap_start -= 1
                overlap_tokens_remaining -= sentence_tokens[overlap_start]

            # Move start to overlap_start, but ensure forward progress
            new_start = max(overlap_start, start_idx + 1)
            if new_start >= end_idx:
                # Ensure we don't get stuck
                new_start = end_idx
            start_idx = new_start

        # Fix total_chunks
        total = len(chunks)
        chunks = [
            Chunk(
                text=c.text,
                token_count=c.token_count,
                metadata=ChunkMetadata(
                    section_header=c.metadata.section_header,
                    position_index=c.metadata.position_index,
                    total_chunks=total,
                    key_entities=c.metadata.key_entities,
                    starts_with_heading=c.metadata.starts_with_heading,
                ),
            )
            for c in chunks
        ]

        return chunks

    # -- Private helpers -----------------------------------------------------

    def _split_into_sections(
        self, content: str
    ) -> list[tuple[Optional[str], str]]:
        """Split content into (heading, body) sections.

        If no headings are found, returns a single section with None heading.
        """
        headings = list(_HEADING_PATTERN.finditer(content))
        if not headings:
            return [(None, content)]

        sections: list[tuple[Optional[str], str]] = []

        # Text before first heading
        pre_heading = content[: headings[0].start()].strip()
        if pre_heading:
            sections.append((None, pre_heading))

        for i, match in enumerate(headings):
            header = match.group(2).strip()
            start = match.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(content)
            body = content[start:end].strip()
            if body:
                sections.append((header, body))

        return sections

    def _split_by_sentences(self, text: str) -> list[str]:
        """Split a long paragraph into chunks at sentence boundaries."""
        sentences = _split_sentences(text)
        if not sentences:
            return [text]

        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip() if current else sentence
            if self._token_counter.count(candidate) <= self.max_chunk_tokens:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

        return chunks
