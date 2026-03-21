"""
GRAPH Domain Entities

Architectural Intent:
- All entities are frozen dataclasses (immutable aggregates)
- State transitions return new instances; originals are never mutated
- Domain events are collected on the aggregate root (EntityProfile)
  and dispatched by the application layer after persistence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.value_objects import BrandId, Score, AIEngine

from lumina.graph.domain.value_objects import DimensionType, GapSeverity
from lumina.graph.domain.events import (
    DomainEvent,
    EntityDimensionUpdated,
    EntityHealthChanged,
)


@dataclass(frozen=True)
class EntityDimension:
    """A single facet of an entity's knowledge representation."""

    id: str
    dimension_type: DimensionType
    data: tuple[tuple[str, str], ...]  # immutable dict representation
    completeness_score: Score
    sources: tuple[str, ...]
    last_verified_at: datetime

    @staticmethod
    def from_dict(
        *,
        id: str | None = None,
        dimension_type: DimensionType,
        data: dict[str, str],
        completeness_score: Score,
        sources: tuple[str, ...] = (),
        last_verified_at: datetime | None = None,
    ) -> EntityDimension:
        return EntityDimension(
            id=id or str(uuid4()),
            dimension_type=dimension_type,
            data=tuple(sorted(data.items())),
            completeness_score=completeness_score,
            sources=sources,
            last_verified_at=last_verified_at or datetime.now(UTC),
        )

    @property
    def data_as_dict(self) -> dict[str, str]:
        return dict(self.data)


@dataclass(frozen=True)
class EntityProfile:
    """Aggregate root — the full entity knowledge graph for a brand."""

    id: str
    brand_id: BrandId
    name: str
    description: str
    dimensions: tuple[EntityDimension, ...] = ()
    health_score: Score = field(default_factory=lambda: Score(0.0))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    domain_events: tuple[DomainEvent, ...] = ()

    # ------------------------------------------------------------------
    # Aggregate behaviour — every mutation returns a new instance
    # ------------------------------------------------------------------

    def add_dimension(self, dimension: EntityDimension) -> EntityProfile:
        """Return a new profile with the given dimension appended."""
        new_dimensions = self.dimensions + (dimension,)
        return EntityProfile(
            id=self.id,
            brand_id=self.brand_id,
            name=self.name,
            description=self.description,
            dimensions=new_dimensions,
            health_score=self.health_score,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
            domain_events=self.domain_events,
        )

    def update_dimension(
        self,
        dimension_id: str,
        new_data: dict[str, str],
        new_completeness: Score | None = None,
    ) -> EntityProfile:
        """Return a new profile with an updated dimension and a domain event."""
        updated_dims: list[EntityDimension] = []
        events: list[DomainEvent] = list(self.domain_events)
        found = False

        for dim in self.dimensions:
            if dim.id == dimension_id:
                found = True
                old_completeness = dim.completeness_score
                merged_data = dict(dim.data)
                merged_data.update(new_data)
                completeness = new_completeness or old_completeness
                updated_dim = EntityDimension(
                    id=dim.id,
                    dimension_type=dim.dimension_type,
                    data=tuple(sorted(merged_data.items())),
                    completeness_score=completeness,
                    sources=dim.sources,
                    last_verified_at=datetime.now(UTC),
                )
                updated_dims.append(updated_dim)
                events.append(
                    EntityDimensionUpdated(
                        aggregate_id=self.id,
                        brand_id=self.brand_id.value,
                        dimension_type=dim.dimension_type.value,
                        old_completeness=old_completeness.value,
                        new_completeness=completeness.value,
                    )
                )
            else:
                updated_dims.append(dim)

        if not found:
            raise ValueError(f"Dimension {dimension_id} not found on profile {self.id}")

        return EntityProfile(
            id=self.id,
            brand_id=self.brand_id,
            name=self.name,
            description=self.description,
            dimensions=tuple(updated_dims),
            health_score=self.health_score,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
            domain_events=tuple(events),
        )

    def calculate_health(self) -> EntityProfile:
        """Return a new profile with health_score recalculated from dimension completeness.

        The score is the mean completeness across all eight dimension types.
        Missing dimension types contribute zero.  When the score changes, an
        ``EntityHealthChanged`` event is collected.
        """
        all_types = list(DimensionType)
        dim_by_type: dict[DimensionType, Score] = {}
        for dim in self.dimensions:
            existing = dim_by_type.get(dim.dimension_type)
            if existing is None or dim.completeness_score.value > existing.value:
                dim_by_type[dim.dimension_type] = dim.completeness_score

        total = sum(dim_by_type.get(dt, Score(0.0)).value for dt in all_types)
        raw = total / len(all_types)
        new_score = Score(round(raw, 2))

        events = list(self.domain_events)
        if new_score.value != self.health_score.value:
            events.append(
                EntityHealthChanged(
                    aggregate_id=self.id,
                    brand_id=self.brand_id.value,
                    old_score=self.health_score.value,
                    new_score=new_score.value,
                )
            )

        return EntityProfile(
            id=self.id,
            brand_id=self.brand_id,
            name=self.name,
            description=self.description,
            dimensions=self.dimensions,
            health_score=new_score,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
            domain_events=tuple(events),
        )

    def clear_events(self) -> EntityProfile:
        """Return a copy with all collected domain events cleared."""
        return EntityProfile(
            id=self.id,
            brand_id=self.brand_id,
            name=self.name,
            description=self.description,
            dimensions=self.dimensions,
            health_score=self.health_score,
            created_at=self.created_at,
            updated_at=self.updated_at,
            domain_events=(),
        )


@dataclass(frozen=True)
class KnowledgeGap:
    """An identified gap in entity knowledge that weakens AI visibility."""

    id: str
    brand_id: BrandId
    dimension_type: DimensionType
    description: str
    severity: GapSeverity
    identified_from: AIEngine | None = None
    recommended_action: str = ""


@dataclass(frozen=True)
class CompetitorEntityComparison:
    """Side-by-side dimension scores for a brand vs. a single competitor."""

    brand_id: BrandId
    competitor_id: BrandId
    dimension_scores: tuple[tuple[DimensionType, Score, Score], ...]
    # Each entry: (dimension_type, brand_score, competitor_score)

    def get_comparison(self, dim_type: DimensionType) -> tuple[Score, Score] | None:
        for dt, brand_s, comp_s in self.dimension_scores:
            if dt == dim_type:
                return (brand_s, comp_s)
        return None
