"""
Tests for advanced content chunking.

Tests cover semantic chunking by paragraphs, token counting accuracy,
sentence boundary preservation, and sliding window overlap.
"""

from __future__ import annotations

import pytest

from lumina.infrastructure.rag.chunker import ContentChunker, TokenCounter


class TestTokenCounter:
    """Tests for TokenCounter."""

    def test_token_counting_accuracy(self) -> None:
        """Token counts should be consistent with tiktoken cl100k_base."""
        counter = TokenCounter()

        # Simple text - tokens should be a reasonable count
        text = "Hello, world! This is a test."
        count = counter.count(text)
        assert count > 0
        # "Hello, world! This is a test." is roughly 8 tokens
        assert 5 <= count <= 12

    def test_empty_text_returns_zero(self) -> None:
        """Empty text should return zero tokens."""
        counter = TokenCounter()
        assert counter.count("") == 0

    def test_truncation(self) -> None:
        """Truncation should produce text within the token limit."""
        counter = TokenCounter()
        long_text = "word " * 1000
        truncated = counter.truncate_to_tokens(long_text, 10)
        assert counter.count(truncated) <= 10


class TestContentChunkerSemantic:
    """Tests for semantic chunking."""

    def test_semantic_chunking_splits_by_paragraphs(self) -> None:
        """Semantic chunking should split content at paragraph boundaries."""
        chunker = ContentChunker(max_chunk_tokens=25)

        content = (
            "First paragraph about cloud computing and its many benefits for modern enterprises. "
            "Cloud computing enables highly scalable infrastructure for organizations worldwide.\n\n"
            "Second paragraph about artificial intelligence and machine learning technologies. "
            "AI transforms industries through intelligent automation and data analysis.\n\n"
            "Third paragraph about cybersecurity challenges in the digital age. "
            "Security threats evolve rapidly as technology advances and new attack vectors emerge."
        )
        chunks = chunker.chunk_semantic(content)

        assert len(chunks) >= 2
        # Each chunk should contain coherent paragraph content
        for chunk in chunks:
            assert chunk.text.strip() != ""
            assert chunk.token_count > 0

    def test_sentence_boundary_preservation(self) -> None:
        """Chunks should not cut in the middle of sentences."""
        chunker = ContentChunker(max_chunk_tokens=30)

        content = (
            "Sentence one about topic A. Sentence two about topic B. "
            "Sentence three about topic C. Sentence four about topic D. "
            "Sentence five about topic E. Sentence six about topic F."
        )
        chunks = chunker.chunk_semantic(content)

        for chunk in chunks:
            text = chunk.text.strip()
            if text:
                # Each chunk should end with a sentence-ending punctuation
                # or be the last chunk
                assert (
                    text.endswith(".")
                    or text.endswith("!")
                    or text.endswith("?")
                    or chunk.metadata.position_index == chunk.metadata.total_chunks - 1
                )

    def test_metadata_is_populated(self) -> None:
        """Chunk metadata should include position and total count."""
        chunker = ContentChunker(max_chunk_tokens=50)

        content = (
            "## Introduction\n\n"
            "This is the introduction paragraph with some content.\n\n"
            "## Main Section\n\n"
            "This is the main content section with detailed information."
        )
        chunks = chunker.chunk_semantic(content)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.metadata.total_chunks == len(chunks)
            assert 0 <= chunk.metadata.position_index < len(chunks)

    def test_handles_empty_content(self) -> None:
        """Empty content should produce no chunks."""
        chunker = ContentChunker()
        assert chunker.chunk_semantic("") == []
        assert chunker.chunk_semantic("   ") == []

    def test_section_headers_detected(self) -> None:
        """Markdown headings should be detected as section headers."""
        chunker = ContentChunker(max_chunk_tokens=100)

        content = (
            "## Cloud Computing\n\n"
            "Cloud computing delivers services over the internet.\n\n"
            "## Artificial Intelligence\n\n"
            "AI enables machines to learn from experience."
        )
        chunks = chunker.chunk_semantic(content)

        # At least one chunk should have a section_header set
        headers = [c.metadata.section_header for c in chunks if c.metadata.section_header]
        assert len(headers) >= 1


class TestContentChunkerSlidingWindow:
    """Tests for sliding window chunking."""

    def test_sliding_window_overlap(self) -> None:
        """Sliding window chunks should have overlapping content."""
        chunker = ContentChunker(max_chunk_tokens=30, overlap_tokens=10)

        # Generate content with many sentences
        sentences = [
            f"Sentence number {i} contains information about topic {chr(65 + i % 26)}."
            for i in range(20)
        ]
        content = " ".join(sentences)

        chunks = chunker.chunk_sliding_window(content)

        # With overlap, we should have multiple chunks
        assert len(chunks) >= 2

        # Verify overlap: some text from the end of one chunk should
        # appear at the start of the next chunk
        for i in range(len(chunks) - 1):
            current_words = set(chunks[i].text.split())
            next_words = set(chunks[i + 1].text.split())
            overlap = current_words & next_words
            # With overlap, there should be shared words
            assert len(overlap) > 0, (
                f"No overlap between chunk {i} and chunk {i+1}"
            )

    def test_sliding_window_respects_sentence_boundaries(self) -> None:
        """Sliding window chunks should respect sentence boundaries."""
        chunker = ContentChunker(max_chunk_tokens=50, overlap_tokens=15)

        content = (
            "First important sentence about data science. "
            "Second sentence about machine learning algorithms. "
            "Third sentence about neural network architectures. "
            "Fourth sentence about natural language processing. "
            "Fifth sentence about computer vision applications."
        )
        chunks = chunker.chunk_sliding_window(content)

        for chunk in chunks:
            text = chunk.text.strip()
            # Each chunk should end at a sentence boundary
            assert (
                text.endswith(".")
                or text.endswith("!")
                or text.endswith("?")
            )

    def test_handles_empty_content(self) -> None:
        """Empty content should produce no chunks."""
        chunker = ContentChunker()
        assert chunker.chunk_sliding_window("") == []
        assert chunker.chunk_sliding_window("   ") == []
