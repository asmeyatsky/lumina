"""
BEAM Value Objects

Architectural Intent:
- Immutable, identity-less domain concepts specific to the BEAM bounded context
- Enforce domain invariants at construction time
- Enumerations for content types and GEO scoring factors
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lumina.shared.domain.value_objects import Score


class ContentType(str, Enum):
    """Types of content assets that BEAM can analyse and optimise."""

    WEB_PAGE = "web_page"
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    BLOG_POST = "blog_post"
    LANDING_PAGE = "landing_page"


class GEOFactor(str, Enum):
    """The six GEO scoring factors from the LUMINA PRD."""

    ENTITY_DENSITY = "entity_density"
    ANSWER_SHAPE = "answer_shape"
    FACT_CITABILITY = "fact_citability"
    RAG_SURVIVABILITY = "rag_survivability"
    SEMANTIC_AUTHORITY = "semantic_authority"
    FRESHNESS_SIGNALS = "freshness_signals"


@dataclass(frozen=True)
class GEOWeights:
    """Weights for each GEO factor in overall score computation.

    Defaults are from the LUMINA PRD:
    - Entity Density: 20%
    - Answer Shape: 20%
    - Fact Citability: 20%
    - RAG Survivability: 20%
    - Semantic Authority: 10%
    - Freshness Signals: 10%
    """

    entity_density: float = 0.20
    answer_shape: float = 0.20
    fact_citability: float = 0.20
    rag_survivability: float = 0.20
    semantic_authority: float = 0.10
    freshness_signals: float = 0.10

    def __post_init__(self) -> None:
        total = (
            self.entity_density
            + self.answer_shape
            + self.fact_citability
            + self.rag_survivability
            + self.semantic_authority
            + self.freshness_signals
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"GEOWeights must sum to 1.0, got {total}")
        for name in (
            "entity_density",
            "answer_shape",
            "fact_citability",
            "rag_survivability",
            "semantic_authority",
            "freshness_signals",
        ):
            val = getattr(self, name)
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"Weight {name} must be between 0.0 and 1.0, got {val}")

    def weight_for_factor(self, factor: GEOFactor) -> float:
        """Return the weight for a given GEO factor."""
        return getattr(self, factor.value)


@dataclass(frozen=True)
class ContentAuditSummary:
    """Summary of a brand's content estate audit."""

    total_assets: int
    avg_geo_score: Score
    assets_below_threshold: int
    top_improvement_opportunities: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.total_assets < 0:
            raise ValueError("total_assets must be non-negative")
        if self.assets_below_threshold < 0:
            raise ValueError("assets_below_threshold must be non-negative")
        if self.assets_below_threshold > self.total_assets:
            raise ValueError(
                "assets_below_threshold cannot exceed total_assets"
            )
