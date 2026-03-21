"""
GRAPH Domain Value Objects

Architectural Intent:
- Immutable, identity-less concepts specific to the Entity Intelligence context
- DimensionType and GapSeverity are the core enumerations driving gap analysis
- EntityHealth, SchemaOrgType, and JsonLdDocument carry structured data
  without identity, enforcing invariants at construction time
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from lumina.shared.domain.value_objects import Score


class DimensionType(str, Enum):
    """Facets of entity knowledge that AI engines may reference."""

    IDENTITY = "identity"
    PRODUCTS_SERVICES = "products_services"
    PEOPLE = "people"
    TOPIC_AUTHORITY = "topic_authority"
    ACHIEVEMENTS = "achievements"
    RELATIONSHIPS = "relationships"
    COMPETITIVE_POSITION = "competitive_position"
    TEMPORAL_DATA = "temporal_data"


class GapSeverity(str, Enum):
    """Impact level of a knowledge gap on AI visibility."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class EntityHealth:
    """Snapshot of an entity profile's overall health."""

    overall_score: Score
    dimension_scores: tuple[tuple[DimensionType, Score], ...]
    gaps_count: int
    last_audit_at: datetime

    def get_dimension_score(self, dim_type: DimensionType) -> Score | None:
        for dt, score in self.dimension_scores:
            if dt == dim_type:
                return score
        return None


@dataclass(frozen=True)
class SchemaOrgType:
    """A schema.org type with its properties."""

    schema_type: str  # e.g. "Organization", "Product"
    properties: tuple[tuple[str, str], ...]  # (property_name, property_value) pairs


@dataclass(frozen=True)
class JsonLdDocument:
    """An immutable JSON-LD document for structured data output."""

    context: str = field(default="https://schema.org")
    type: str = ""
    properties: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary suitable for JSON output."""
        result: dict = {
            "@context": self.context,
            "@type": self.type,
        }
        for key, value in self.properties:
            result[key] = value
        return result
