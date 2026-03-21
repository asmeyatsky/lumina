"""
GRAPH Application Commands (Write-side Use Cases)

Architectural Intent:
- Each command orchestrates a single use case
- Commands depend only on domain ports — never on infrastructure directly
- Domain events collected on aggregates are published after persistence
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
from uuid import uuid4

from lumina.shared.domain.value_objects import BrandId, Score
from lumina.shared.ports.event_bus import EventBusPort

from lumina.graph.domain.entities import EntityProfile, EntityDimension, KnowledgeGap
from lumina.graph.domain.events import (
    EntityProfileCreated,
    KnowledgeGapIdentified,
)
from lumina.graph.domain.value_objects import DimensionType
from lumina.graph.domain.ports import GraphRepositoryPort
from lumina.graph.domain.services import GapAnalysisService, JsonLdGenerationService
from lumina.graph.domain.value_objects import JsonLdDocument


# ---------------------------------------------------------------------------
# DTOs for command inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DimensionInput:
    """Lightweight input DTO for creating a dimension."""

    dimension_type: DimensionType
    data: dict[str, str]
    completeness_score: float
    sources: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


class CreateEntityProfileCommand:
    """Creates a new entity profile for a brand with initial dimensions."""

    def __init__(
        self,
        repository: GraphRepositoryPort,
        event_bus: EventBusPort,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus

    async def execute(
        self,
        *,
        brand_id: str,
        name: str,
        description: str,
        dimensions: list[DimensionInput] | None = None,
    ) -> EntityProfile:
        profile_id = str(uuid4())
        now = datetime.now(UTC)

        entity_dims: list[EntityDimension] = []
        for dim_input in (dimensions or []):
            entity_dims.append(
                EntityDimension.from_dict(
                    dimension_type=dim_input.dimension_type,
                    data=dim_input.data,
                    completeness_score=Score(dim_input.completeness_score),
                    sources=dim_input.sources,
                    last_verified_at=now,
                )
            )

        profile = EntityProfile(
            id=profile_id,
            brand_id=BrandId(brand_id),
            name=name,
            description=description,
            dimensions=tuple(entity_dims),
            health_score=Score(0.0),
            created_at=now,
            updated_at=now,
            domain_events=(
                EntityProfileCreated(
                    aggregate_id=profile_id,
                    brand_id=brand_id,
                    profile_name=name,
                ),
            ),
        )

        # Recalculate health based on initial dimensions
        profile = profile.calculate_health()

        await self._repository.save_profile(profile)
        await self._event_bus.publish(list(profile.domain_events))

        return profile.clear_events()


class UpdateEntityDimensionCommand:
    """Updates a specific dimension on an entity profile, recalculates health."""

    def __init__(
        self,
        repository: GraphRepositoryPort,
        event_bus: EventBusPort,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus

    async def execute(
        self,
        *,
        profile_id: str,
        dimension_id: str,
        new_data: dict[str, str],
        new_completeness: float | None = None,
    ) -> EntityProfile:
        profile = await self._repository.get_profile(profile_id)
        if profile is None:
            from lumina.shared.domain.errors import EntityNotFoundError

            raise EntityNotFoundError(f"Profile {profile_id} not found")

        completeness = Score(new_completeness) if new_completeness is not None else None
        profile = profile.update_dimension(dimension_id, new_data, completeness)
        profile = profile.calculate_health()

        await self._repository.save_profile(profile)
        await self._event_bus.publish(list(profile.domain_events))

        return profile.clear_events()


class RunGapAnalysisCommand:
    """Runs gap analysis against AI knowledge data, persists gaps, publishes events."""

    def __init__(
        self,
        repository: GraphRepositoryPort,
        event_bus: EventBusPort,
        gap_service: GapAnalysisService | None = None,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus
        self._gap_service = gap_service or GapAnalysisService()

    async def execute(
        self,
        *,
        profile_id: str,
        ai_knowledge: dict[str, dict],
    ) -> list[KnowledgeGap]:
        profile = await self._repository.get_profile(profile_id)
        if profile is None:
            from lumina.shared.domain.errors import EntityNotFoundError

            raise EntityNotFoundError(f"Profile {profile_id} not found")

        gaps = self._gap_service.analyze_gaps(profile, ai_knowledge)

        events = []
        for gap in gaps:
            await self._repository.save_gap(gap)
            events.append(
                KnowledgeGapIdentified(
                    aggregate_id=profile.id,
                    brand_id=gap.brand_id.value,
                    dimension_type=gap.dimension_type.value,
                    severity=gap.severity.value,
                    description=gap.description,
                )
            )

        if events:
            await self._event_bus.publish(events)

        return gaps


class GenerateJsonLdCommand:
    """Generates JSON-LD documents for a brand's entity profile."""

    def __init__(
        self,
        repository: GraphRepositoryPort,
        json_ld_service: JsonLdGenerationService | None = None,
    ) -> None:
        self._repository = repository
        self._json_ld_service = json_ld_service or JsonLdGenerationService()

    async def execute(self, *, profile_id: str) -> list[JsonLdDocument]:
        profile = await self._repository.get_profile(profile_id)
        if profile is None:
            from lumina.shared.domain.errors import EntityNotFoundError

            raise EntityNotFoundError(f"Profile {profile_id} not found")

        return self._json_ld_service.generate_json_ld(profile)
