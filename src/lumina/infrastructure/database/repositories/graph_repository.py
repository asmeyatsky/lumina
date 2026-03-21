"""
PostgreSQL Repository — GRAPH bounded context

Implements GraphRepositoryPort by mapping between frozen domain dataclasses
and SQLAlchemy ORM models, using async sessions throughout.
"""

from __future__ import annotations

from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lumina.shared.domain.value_objects import AIEngine, BrandId, Score
from lumina.graph.domain.entities import EntityDimension, EntityProfile, KnowledgeGap
from lumina.graph.domain.value_objects import DimensionType, GapSeverity

from lumina.infrastructure.database.models import (
    AIEngineEnum,
    DimensionTypeEnum,
    EntityDimensionModel,
    EntityProfileModel,
    GapSeverityEnum,
    KnowledgeGapModel,
)

# Severity ordering for query results
_SEVERITY_ORDER = {
    GapSeverityEnum.CRITICAL: 0,
    GapSeverityEnum.HIGH: 1,
    GapSeverityEnum.MEDIUM: 2,
    GapSeverityEnum.LOW: 3,
}


class GraphRepository:
    """Async PostgreSQL implementation of GraphRepositoryPort."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ------------------------------------------------------------------
    # EntityProfile
    # ------------------------------------------------------------------

    async def save_profile(self, profile: EntityProfile) -> None:
        existing = await self._session.get(EntityProfileModel, profile.id)
        if existing is not None:
            existing.brand_id = profile.brand_id.value
            existing.name = profile.name
            existing.description = profile.description
            existing.health_score = profile.health_score.value
            existing.updated_at = profile.updated_at

            existing.dimensions.clear()
            await self._session.flush()
            for dim in profile.dimensions:
                existing.dimensions.append(self._dimension_to_model(dim, profile.id))
        else:
            model = EntityProfileModel(
                id=profile.id,
                tenant_id=self._tenant_id,
                brand_id=profile.brand_id.value,
                name=profile.name,
                description=profile.description,
                health_score=profile.health_score.value,
                created_at=profile.created_at,
                updated_at=profile.updated_at,
            )
            for dim in profile.dimensions:
                model.dimensions.append(self._dimension_to_model(dim, profile.id))
            self._session.add(model)

        await self._session.flush()

    async def get_profile(self, profile_id: str) -> EntityProfile | None:
        model = await self._session.get(EntityProfileModel, profile_id)
        if model is None or model.tenant_id != self._tenant_id:
            return None
        return self._profile_model_to_domain(model)

    async def list_profiles_for_brand(self, brand_id: str) -> list[EntityProfile]:
        stmt = (
            select(EntityProfileModel)
            .where(
                EntityProfileModel.tenant_id == self._tenant_id,
                EntityProfileModel.brand_id == brand_id,
            )
            .order_by(EntityProfileModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._profile_model_to_domain(m) for m in result.scalars().all()]

    # ------------------------------------------------------------------
    # KnowledgeGap
    # ------------------------------------------------------------------

    async def save_gap(self, gap: KnowledgeGap) -> None:
        existing = await self._session.get(KnowledgeGapModel, gap.id)
        if existing is not None:
            existing.brand_id = gap.brand_id.value
            existing.dimension_type = DimensionTypeEnum(gap.dimension_type.value)
            existing.description = gap.description
            existing.severity = GapSeverityEnum(gap.severity.value)
            existing.identified_from = (
                AIEngineEnum(gap.identified_from.value) if gap.identified_from else None
            )
            existing.recommended_action = gap.recommended_action
        else:
            model = KnowledgeGapModel(
                id=gap.id,
                tenant_id=self._tenant_id,
                brand_id=gap.brand_id.value,
                dimension_type=DimensionTypeEnum(gap.dimension_type.value),
                description=gap.description,
                severity=GapSeverityEnum(gap.severity.value),
                identified_from=(
                    AIEngineEnum(gap.identified_from.value) if gap.identified_from else None
                ),
                recommended_action=gap.recommended_action,
            )
            self._session.add(model)

        await self._session.flush()

    async def get_gaps_for_brand(self, brand_id: str) -> list[KnowledgeGap]:
        stmt = (
            select(KnowledgeGapModel)
            .where(
                KnowledgeGapModel.tenant_id == self._tenant_id,
                KnowledgeGapModel.brand_id == brand_id,
            )
        )
        result = await self._session.execute(stmt)
        gaps = [self._gap_model_to_domain(m) for m in result.scalars().all()]
        # Sort by severity order (CRITICAL first)
        gaps.sort(key=lambda g: _SEVERITY_ORDER.get(
            GapSeverityEnum(g.severity.value), 99
        ))
        return gaps

    # ------------------------------------------------------------------
    # Mapping helpers: domain -> ORM
    # ------------------------------------------------------------------

    def _dimension_to_model(
        self, dim: EntityDimension, profile_id: str
    ) -> EntityDimensionModel:
        return EntityDimensionModel(
            id=dim.id,
            tenant_id=self._tenant_id,
            profile_id=profile_id,
            dimension_type=DimensionTypeEnum(dim.dimension_type.value),
            data=dim.data_as_dict,
            completeness_score=dim.completeness_score.value,
            sources=list(dim.sources),
            last_verified_at=dim.last_verified_at,
        )

    # ------------------------------------------------------------------
    # Mapping helpers: ORM -> domain
    # ------------------------------------------------------------------

    def _profile_model_to_domain(self, model: EntityProfileModel) -> EntityProfile:
        dimensions = tuple(
            EntityDimension(
                id=d.id,
                dimension_type=DimensionType(d.dimension_type.value),
                data=tuple(sorted(d.data.items())) if d.data else (),
                completeness_score=Score(d.completeness_score),
                sources=tuple(d.sources) if d.sources else (),
                last_verified_at=d.last_verified_at,
            )
            for d in model.dimensions
        )
        return EntityProfile(
            id=model.id,
            brand_id=BrandId(model.brand_id),
            name=model.name,
            description=model.description,
            dimensions=dimensions,
            health_score=Score(model.health_score),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _gap_model_to_domain(self, model: KnowledgeGapModel) -> KnowledgeGap:
        return KnowledgeGap(
            id=model.id,
            brand_id=BrandId(model.brand_id),
            dimension_type=DimensionType(model.dimension_type.value),
            description=model.description,
            severity=GapSeverity(model.severity.value),
            identified_from=(
                AIEngine(model.identified_from.value) if model.identified_from else None
            ),
            recommended_action=model.recommended_action,
        )
