"""
SIGNAL Domain Value Objects

Architectural Intent:
- Immutable, identity-less concepts specific to the Distribution & Amplification context
- SurfaceCategory, PresenceStatus, ActionType, ActionStatus are the core enumerations
  driving distribution planning and surface mapping
- DistributionCoverage and SurfaceAffinity carry computed metrics without identity
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from lumina.shared.domain.value_objects import BrandId, Percentage, Score


class SurfaceCategory(str, Enum):
    """Categories of citation surfaces where LLMs draw training data."""

    STRUCTURED_DATA = "structured_data"
    AUTHORITY_PUBLICATIONS = "authority_publications"
    QA_PLATFORMS = "qa_platforms"
    DEVELOPER_COMMUNITIES = "developer_communities"
    ACADEMIC_RESEARCH = "academic_research"
    BUSINESS_DIRECTORIES = "business_directories"
    NEWS_SYNDICATION = "news_syndication"


class PresenceStatus(str, Enum):
    """Whether a brand is present on a given citation surface."""

    PRESENT = "present"
    PARTIAL = "partial"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    """Types of distribution actions that can be executed."""

    SUBMIT_STRUCTURED_DATA = "submit_structured_data"
    PUBLISH_CONTENT = "publish_content"
    UPDATE_WIKIDATA = "update_wikidata"
    SYNDICATE_ARTICLE = "syndicate_article"
    ENGAGE_COMMUNITY = "engage_community"
    SUBMIT_PR_BRIEF = "submit_pr_brief"


class ActionStatus(str, Enum):
    """Lifecycle status of a distribution action."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class DistributionCoverage:
    """Aggregate coverage metrics for a brand's distribution across surfaces."""

    brand_id: BrandId
    total_surfaces: int
    surfaces_with_presence: int
    coverage_percentage: Percentage
    by_category: tuple[tuple[SurfaceCategory, Percentage], ...]

    def get_category_coverage(self, category: SurfaceCategory) -> Percentage | None:
        for cat, pct in self.by_category:
            if cat == category:
                return pct
        return None


@dataclass(frozen=True)
class SurfaceAffinity:
    """How strongly a citation surface correlates with LLM training influence."""

    surface_id: str
    estimated_training_weight: Score
    citation_correlation: float
    last_updated_at: datetime
