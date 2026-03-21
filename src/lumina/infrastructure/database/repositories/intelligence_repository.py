"""
PostgreSQL Repository — INTELLIGENCE bounded context

Implements IntelligenceRepositoryPort by mapping between frozen domain
dataclasses and SQLAlchemy ORM models, using async sessions throughout.
"""

from __future__ import annotations

from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lumina.shared.domain.value_objects import BrandId, Score
from lumina.intelligence.domain.entities import (
    AIVisibilityScore,
    Recommendation,
    RootCause,
    RootCauseAnalysis,
    ScoreComponent,
)
from lumina.intelligence.domain.value_objects import EffortLevel

from lumina.infrastructure.database.models import (
    AIVisibilityScoreModel,
    EffortLevelEnum,
    RecommendationModel,
    RootCauseAnalysisModel,
    ScoreComponentModel,
)


class IntelligenceRepository:
    """Async PostgreSQL implementation of IntelligenceRepositoryPort."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ------------------------------------------------------------------
    # AIVisibilityScore
    # ------------------------------------------------------------------

    async def save_avs(self, avs: AIVisibilityScore) -> None:
        existing = await self._session.get(AIVisibilityScoreModel, avs.id)
        if existing is not None:
            existing.brand_id = avs.brand_id
            existing.overall = avs.overall.value
            existing.calculated_at = avs.calculated_at
            existing.previous_score = avs.previous_score.value if avs.previous_score else None

            existing.components.clear()
            for comp in avs.components:
                existing.components.append(self._component_to_model(comp, avs.id))
        else:
            model = AIVisibilityScoreModel(
                id=avs.id,
                tenant_id=self._tenant_id,
                brand_id=avs.brand_id,
                overall=avs.overall.value,
                calculated_at=avs.calculated_at,
                previous_score=avs.previous_score.value if avs.previous_score else None,
            )
            for comp in avs.components:
                model.components.append(self._component_to_model(comp, avs.id))
            self._session.add(model)

        await self._session.flush()

    async def get_latest_avs(self, brand_id: BrandId) -> AIVisibilityScore | None:
        stmt = (
            select(AIVisibilityScoreModel)
            .where(
                AIVisibilityScoreModel.tenant_id == self._tenant_id,
                AIVisibilityScoreModel.brand_id == brand_id.value,
            )
            .order_by(AIVisibilityScoreModel.calculated_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalars().first()
        if model is None:
            return None
        return self._avs_model_to_domain(model)

    async def get_avs_history(
        self, brand_id: BrandId, limit: int = 30
    ) -> list[AIVisibilityScore]:
        stmt = (
            select(AIVisibilityScoreModel)
            .where(
                AIVisibilityScoreModel.tenant_id == self._tenant_id,
                AIVisibilityScoreModel.brand_id == brand_id.value,
            )
            .order_by(AIVisibilityScoreModel.calculated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._avs_model_to_domain(m) for m in result.scalars().all()]

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------

    async def save_recommendation(self, recommendation: Recommendation) -> None:
        existing = await self._session.get(RecommendationModel, recommendation.id)
        if existing is not None:
            existing.brand_id = recommendation.brand_id
            existing.source_module = recommendation.source_module
            existing.action_description = recommendation.action_description
            existing.expected_avs_impact = recommendation.expected_avs_impact.value
            existing.effort_level = EffortLevelEnum(recommendation.effort_level.value)
            existing.priority_rank = recommendation.priority_rank
            existing.linked_entity_id = recommendation.linked_entity_id
        else:
            model = RecommendationModel(
                id=recommendation.id,
                tenant_id=self._tenant_id,
                brand_id=recommendation.brand_id,
                source_module=recommendation.source_module,
                action_description=recommendation.action_description,
                expected_avs_impact=recommendation.expected_avs_impact.value,
                effort_level=EffortLevelEnum(recommendation.effort_level.value),
                priority_rank=recommendation.priority_rank,
                linked_entity_id=recommendation.linked_entity_id,
                created_at=recommendation.created_at,
            )
            self._session.add(model)

        await self._session.flush()

    async def get_recommendations(self, brand_id: BrandId) -> list[Recommendation]:
        stmt = (
            select(RecommendationModel)
            .where(
                RecommendationModel.tenant_id == self._tenant_id,
                RecommendationModel.brand_id == brand_id.value,
            )
            .order_by(RecommendationModel.priority_rank.asc())
        )
        result = await self._session.execute(stmt)
        return [self._recommendation_model_to_domain(m) for m in result.scalars().all()]

    # ------------------------------------------------------------------
    # RootCauseAnalysis
    # ------------------------------------------------------------------

    async def save_root_cause_analysis(self, rca: RootCauseAnalysis) -> None:
        causes_data = [
            {
                "factor": c.factor,
                "module": c.module,
                "evidence": c.evidence,
                "contribution_weight": c.contribution_weight,
            }
            for c in rca.causes
        ]
        existing = await self._session.get(RootCauseAnalysisModel, rca.id)
        if existing is not None:
            existing.brand_id = rca.brand_id
            existing.trigger = rca.trigger
            existing.causes = causes_data
            existing.recommended_actions = list(rca.recommended_actions)
            existing.analyzed_at = rca.analyzed_at
        else:
            model = RootCauseAnalysisModel(
                id=rca.id,
                tenant_id=self._tenant_id,
                brand_id=rca.brand_id,
                trigger=rca.trigger,
                causes=causes_data,
                recommended_actions=list(rca.recommended_actions),
                analyzed_at=rca.analyzed_at,
            )
            self._session.add(model)

        await self._session.flush()

    async def get_latest_root_cause_analysis(
        self, brand_id: BrandId
    ) -> RootCauseAnalysis | None:
        stmt = (
            select(RootCauseAnalysisModel)
            .where(
                RootCauseAnalysisModel.tenant_id == self._tenant_id,
                RootCauseAnalysisModel.brand_id == brand_id.value,
            )
            .order_by(RootCauseAnalysisModel.analyzed_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalars().first()
        if model is None:
            return None
        return self._rca_model_to_domain(model)

    # ------------------------------------------------------------------
    # Mapping helpers: domain -> ORM
    # ------------------------------------------------------------------

    def _component_to_model(
        self, comp: ScoreComponent, avs_id: str
    ) -> ScoreComponentModel:
        return ScoreComponentModel(
            tenant_id=self._tenant_id,
            avs_id=avs_id,
            module_name=comp.module_name,
            score=comp.score.value,
            weight=comp.weight,
            raw_metrics=dict(comp.raw_metrics) if comp.raw_metrics else {},
        )

    # ------------------------------------------------------------------
    # Mapping helpers: ORM -> domain
    # ------------------------------------------------------------------

    def _avs_model_to_domain(self, model: AIVisibilityScoreModel) -> AIVisibilityScore:
        components = tuple(
            ScoreComponent(
                module_name=c.module_name,
                score=Score(c.score),
                weight=c.weight,
                raw_metrics=tuple(sorted(c.raw_metrics.items())) if c.raw_metrics else (),
            )
            for c in model.components
        )
        return AIVisibilityScore(
            id=model.id,
            brand_id=model.brand_id,
            overall=Score(model.overall),
            components=components,
            calculated_at=model.calculated_at,
            previous_score=Score(model.previous_score) if model.previous_score is not None else None,
        )

    def _recommendation_model_to_domain(
        self, model: RecommendationModel
    ) -> Recommendation:
        return Recommendation(
            id=model.id,
            brand_id=model.brand_id,
            source_module=model.source_module,
            action_description=model.action_description,
            expected_avs_impact=Score(model.expected_avs_impact),
            effort_level=EffortLevel(model.effort_level.value),
            priority_rank=model.priority_rank,
            linked_entity_id=model.linked_entity_id,
            created_at=model.created_at,
        )

    def _rca_model_to_domain(self, model: RootCauseAnalysisModel) -> RootCauseAnalysis:
        causes = tuple(
            RootCause(
                factor=c["factor"],
                module=c["module"],
                evidence=c["evidence"],
                contribution_weight=c["contribution_weight"],
            )
            for c in (model.causes or [])
        )
        return RootCauseAnalysis(
            id=model.id,
            brand_id=model.brand_id,
            trigger=model.trigger,
            causes=causes,
            recommended_actions=tuple(model.recommended_actions) if model.recommended_actions else (),
            analyzed_at=model.analyzed_at,
        )
