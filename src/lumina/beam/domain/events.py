"""
BEAM Domain Events

Architectural Intent:
- Immutable records of significant domain state changes within the BEAM context
- Published after successful use-case completion
- Consumed by other bounded contexts via the event bus
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class ContentScored(DomainEvent):
    """Raised when a content asset receives a new GEO score."""

    brand_id: str = ""
    asset_id: str = ""
    url: str = ""
    overall_score: float = 0.0
    previous_score: float | None = None


@dataclass(frozen=True)
class RewriteSuggestionGenerated(DomainEvent):
    """Raised when a rewrite suggestion is generated for a content asset."""

    brand_id: str = ""
    asset_id: str = ""
    factor: str = ""
    expected_impact: float = 0.0


@dataclass(frozen=True)
class RAGSimulationCompleted(DomainEvent):
    """Raised when a RAG simulation completes for a content asset."""

    brand_id: str = ""
    asset_id: str = ""
    survivability_score: float = 0.0
    facts_lost_count: int = 0


@dataclass(frozen=True)
class BulkAuditCompleted(DomainEvent):
    """Raised when a bulk content audit finishes for a brand."""

    brand_id: str = ""
    total_assets: int = 0
    avg_score: float = 0.0
