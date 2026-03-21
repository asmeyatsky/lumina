"""
BEAM Domain Layer — Content Optimisation for AI Retrieval

Exports aggregate roots, entities, value objects, domain events, and ports.
"""

from lumina.beam.domain.entities import (
    ContentAsset,
    ContentChunk,
    GEOScore,
    RAGSimulationResult,
    RewriteSuggestion,
)
from lumina.beam.domain.events import (
    BulkAuditCompleted,
    ContentScored,
    RAGSimulationCompleted,
    RewriteSuggestionGenerated,
)
from lumina.beam.domain.value_objects import (
    ContentAuditSummary,
    ContentType,
    GEOFactor,
    GEOWeights,
)

__all__ = [
    "ContentAsset",
    "ContentChunk",
    "GEOScore",
    "RAGSimulationResult",
    "RewriteSuggestion",
    "ContentScored",
    "RewriteSuggestionGenerated",
    "RAGSimulationCompleted",
    "BulkAuditCompleted",
    "ContentType",
    "GEOFactor",
    "GEOWeights",
    "ContentAuditSummary",
]
