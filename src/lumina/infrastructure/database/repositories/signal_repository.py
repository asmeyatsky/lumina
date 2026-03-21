"""
PostgreSQL Repository — SIGNAL bounded context

Implements SignalRepositoryPort by mapping between frozen domain dataclasses
and SQLAlchemy ORM models, using async sessions throughout.
"""

from __future__ import annotations

from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lumina.shared.domain.value_objects import BrandId, Score, URL
from lumina.signal.domain.entities import (
    CitationSurface,
    DistributionAction,
    DistributionPlan,
    PRBrief,
)
from lumina.signal.domain.value_objects import (
    ActionStatus,
    ActionType,
    PresenceStatus,
    SurfaceCategory,
)

from lumina.infrastructure.database.models import (
    ActionStatusEnum,
    ActionTypeEnum,
    CitationSurfaceModel,
    DistributionActionModel,
    DistributionPlanModel,
    PRBriefModel,
    PresenceStatusEnum,
    SurfaceCategoryEnum,
)


class SignalRepository:
    """Async PostgreSQL implementation of SignalRepositoryPort."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ------------------------------------------------------------------
    # DistributionPlan
    # ------------------------------------------------------------------

    async def save_plan(self, plan: DistributionPlan) -> None:
        existing = await self._session.get(DistributionPlanModel, plan.id)
        if existing is not None:
            existing.brand_id = plan.brand_id.value
            existing.coverage_score = plan.coverage_score.value

            existing.actions.clear()
            for action in plan.actions:
                existing.actions.append(self._action_to_model(action, plan.id))
        else:
            model = DistributionPlanModel(
                id=plan.id,
                tenant_id=self._tenant_id,
                brand_id=plan.brand_id.value,
                coverage_score=plan.coverage_score.value,
                created_at=plan.created_at,
            )
            for action in plan.actions:
                model.actions.append(self._action_to_model(action, plan.id))
            self._session.add(model)

        await self._session.flush()

    async def get_plan(self, plan_id: str) -> DistributionPlan | None:
        model = await self._session.get(DistributionPlanModel, plan_id)
        if model is None or model.tenant_id != self._tenant_id:
            return None
        return self._plan_model_to_domain(model)

    async def list_plans_for_brand(self, brand_id: str) -> list[DistributionPlan]:
        stmt = (
            select(DistributionPlanModel)
            .where(
                DistributionPlanModel.tenant_id == self._tenant_id,
                DistributionPlanModel.brand_id == brand_id,
            )
            .order_by(DistributionPlanModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._plan_model_to_domain(m) for m in result.scalars().all()]

    # ------------------------------------------------------------------
    # CitationSurface
    # ------------------------------------------------------------------

    async def save_surface(self, surface: CitationSurface) -> None:
        existing = await self._session.get(CitationSurfaceModel, surface.id)
        if existing is not None:
            existing.name = surface.name
            existing.category = SurfaceCategoryEnum(surface.category.value)
            existing.url = surface.url.value
            existing.estimated_llm_weight = surface.estimated_llm_weight.value
            existing.brand_presence = PresenceStatusEnum(surface.brand_presence.value)
            existing.last_checked_at = surface.last_checked_at
        else:
            model = CitationSurfaceModel(
                id=surface.id,
                tenant_id=self._tenant_id,
                brand_id=self._tenant_id,  # surfaces are tenant-scoped
                name=surface.name,
                category=SurfaceCategoryEnum(surface.category.value),
                url=surface.url.value,
                estimated_llm_weight=surface.estimated_llm_weight.value,
                brand_presence=PresenceStatusEnum(surface.brand_presence.value),
                last_checked_at=surface.last_checked_at,
            )
            self._session.add(model)

        await self._session.flush()

    async def get_surfaces_for_brand(self, brand_id: str) -> list[CitationSurface]:
        stmt = (
            select(CitationSurfaceModel)
            .where(
                CitationSurfaceModel.tenant_id == self._tenant_id,
                CitationSurfaceModel.brand_id == brand_id,
            )
            .order_by(CitationSurfaceModel.name)
        )
        result = await self._session.execute(stmt)
        return [self._surface_model_to_domain(m) for m in result.scalars().all()]

    # ------------------------------------------------------------------
    # PRBrief
    # ------------------------------------------------------------------

    async def save_pr_brief(self, brief: PRBrief) -> None:
        existing = await self._session.get(PRBriefModel, brief.id)
        if existing is not None:
            existing.brand_id = brief.brand_id.value
            existing.headline = brief.headline
            existing.narrative_angle = brief.narrative_angle
            existing.target_publications = list(brief.target_publications)
            existing.key_messages = list(brief.key_messages)
            existing.entity_anchors = list(brief.entity_anchors)
        else:
            model = PRBriefModel(
                id=brief.id,
                tenant_id=self._tenant_id,
                brand_id=brief.brand_id.value,
                headline=brief.headline,
                narrative_angle=brief.narrative_angle,
                target_publications=list(brief.target_publications),
                key_messages=list(brief.key_messages),
                entity_anchors=list(brief.entity_anchors),
                created_at=brief.created_at,
            )
            self._session.add(model)

        await self._session.flush()

    async def get_pr_briefs_for_brand(self, brand_id: str) -> list[PRBrief]:
        stmt = (
            select(PRBriefModel)
            .where(
                PRBriefModel.tenant_id == self._tenant_id,
                PRBriefModel.brand_id == brand_id,
            )
            .order_by(PRBriefModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._pr_brief_model_to_domain(m) for m in result.scalars().all()]

    # ------------------------------------------------------------------
    # Mapping helpers: domain -> ORM
    # ------------------------------------------------------------------

    def _action_to_model(
        self, action: DistributionAction, plan_id: str
    ) -> DistributionActionModel:
        return DistributionActionModel(
            id=action.id,
            tenant_id=self._tenant_id,
            plan_id=plan_id,
            surface_id=action.surface_id,
            action_type=ActionTypeEnum(action.action_type.value),
            content=action.content,
            status=ActionStatusEnum(action.status.value),
            scheduled_at=action.scheduled_at,
            completed_at=action.completed_at,
            result_url=action.result_url,
        )

    # ------------------------------------------------------------------
    # Mapping helpers: ORM -> domain
    # ------------------------------------------------------------------

    def _plan_model_to_domain(self, model: DistributionPlanModel) -> DistributionPlan:
        actions = tuple(
            DistributionAction(
                id=a.id,
                plan_id=a.plan_id,
                surface_id=a.surface_id,
                action_type=ActionType(a.action_type.value),
                content=a.content,
                status=ActionStatus(a.status.value),
                scheduled_at=a.scheduled_at,
                completed_at=a.completed_at,
                result_url=a.result_url,
            )
            for a in model.actions
        )
        return DistributionPlan(
            id=model.id,
            brand_id=BrandId(model.brand_id),
            actions=actions,
            coverage_score=Score(model.coverage_score),
            created_at=model.created_at,
        )

    def _surface_model_to_domain(self, model: CitationSurfaceModel) -> CitationSurface:
        return CitationSurface(
            id=model.id,
            name=model.name,
            category=SurfaceCategory(model.category.value),
            url=URL(model.url),
            estimated_llm_weight=Score(model.estimated_llm_weight),
            brand_presence=PresenceStatus(model.brand_presence.value),
            last_checked_at=model.last_checked_at,
        )

    def _pr_brief_model_to_domain(self, model: PRBriefModel) -> PRBrief:
        return PRBrief(
            id=model.id,
            brand_id=BrandId(model.brand_id),
            headline=model.headline,
            narrative_angle=model.narrative_angle,
            target_publications=tuple(model.target_publications) if model.target_publications else (),
            key_messages=tuple(model.key_messages) if model.key_messages else (),
            entity_anchors=tuple(model.entity_anchors) if model.entity_anchors else (),
            created_at=model.created_at,
        )
