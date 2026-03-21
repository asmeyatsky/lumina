"""
PostgreSQL Repository — BEAM bounded context

Implements BeamRepositoryPort by mapping between frozen domain dataclasses
and SQLAlchemy ORM models, using async sessions throughout.
"""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lumina.shared.domain.value_objects import BrandId, Score, URL
from lumina.beam.domain.entities import (
    ContentAsset,
    ContentChunk,
    GEOScore,
    RAGSimulationResult,
    RewriteSuggestion,
)
from lumina.beam.domain.value_objects import ContentType, GEOFactor

from lumina.infrastructure.database.models import (
    ContentAssetModel,
    ContentTypeEnum,
    GEOFactorEnum,
    GEOScoreModel,
    RAGSimulationResultModel,
    RewriteSuggestionModel,
)


class BeamRepository:
    """Async PostgreSQL implementation of BeamRepositoryPort."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ------------------------------------------------------------------
    # ContentAsset
    # ------------------------------------------------------------------

    async def save_asset(self, asset: ContentAsset) -> None:
        existing = await self._session.get(ContentAssetModel, asset.id)
        if existing is not None:
            existing.brand_id = asset.brand_id.value
            existing.url = asset.url.value
            existing.title = asset.title
            existing.raw_content = asset.raw_content
            existing.content_type = ContentTypeEnum(asset.content_type.value)
            existing.last_scored_at = asset.last_scored_at

            if asset.geo_score is not None:
                existing.geo_overall = asset.geo_score.overall.value
                existing.geo_entity_density = asset.geo_score.entity_density.value
                existing.geo_answer_shape = asset.geo_score.answer_shape.value
                existing.geo_fact_citability = asset.geo_score.fact_citability.value
                existing.geo_rag_survivability = asset.geo_score.rag_survivability.value
                existing.geo_semantic_authority = asset.geo_score.semantic_authority.value
                existing.geo_freshness_signals = asset.geo_score.freshness_signals.value
            else:
                existing.geo_overall = None
                existing.geo_entity_density = None
                existing.geo_answer_shape = None
                existing.geo_fact_citability = None
                existing.geo_rag_survivability = None
                existing.geo_semantic_authority = None
                existing.geo_freshness_signals = None

            existing.suggestions.clear()
            for s in asset.suggestions:
                existing.suggestions.append(self._suggestion_to_model(s, asset.id))
        else:
            model = ContentAssetModel(
                id=asset.id,
                tenant_id=self._tenant_id,
                brand_id=asset.brand_id.value,
                url=asset.url.value,
                title=asset.title,
                raw_content=asset.raw_content,
                content_type=ContentTypeEnum(asset.content_type.value),
                last_scored_at=asset.last_scored_at,
            )
            if asset.geo_score is not None:
                model.geo_overall = asset.geo_score.overall.value
                model.geo_entity_density = asset.geo_score.entity_density.value
                model.geo_answer_shape = asset.geo_score.answer_shape.value
                model.geo_fact_citability = asset.geo_score.fact_citability.value
                model.geo_rag_survivability = asset.geo_score.rag_survivability.value
                model.geo_semantic_authority = asset.geo_score.semantic_authority.value
                model.geo_freshness_signals = asset.geo_score.freshness_signals.value

            for s in asset.suggestions:
                model.suggestions.append(self._suggestion_to_model(s, asset.id))
            self._session.add(model)

        await self._session.flush()

    async def get_asset(self, asset_id: str) -> ContentAsset | None:
        model = await self._session.get(ContentAssetModel, asset_id)
        if model is None or model.tenant_id != self._tenant_id:
            return None
        return self._asset_model_to_domain(model)

    async def list_assets_for_brand(self, brand_id: str) -> list[ContentAsset]:
        stmt = (
            select(ContentAssetModel)
            .where(
                ContentAssetModel.tenant_id == self._tenant_id,
                ContentAssetModel.brand_id == brand_id,
            )
            .order_by(ContentAssetModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._asset_model_to_domain(m) for m in result.scalars().all()]

    # ------------------------------------------------------------------
    # GEOScore history
    # ------------------------------------------------------------------

    async def save_score(self, asset_id: str, score: GEOScore) -> None:
        model = GEOScoreModel(
            id=str(uuid4()),
            tenant_id=self._tenant_id,
            asset_id=asset_id,
            overall=score.overall.value,
            entity_density=score.entity_density.value,
            answer_shape=score.answer_shape.value,
            fact_citability=score.fact_citability.value,
            rag_survivability=score.rag_survivability.value,
            semantic_authority=score.semantic_authority.value,
            freshness_signals=score.freshness_signals.value,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_score_history(self, asset_id: str) -> list[GEOScore]:
        stmt = (
            select(GEOScoreModel)
            .where(
                GEOScoreModel.tenant_id == self._tenant_id,
                GEOScoreModel.asset_id == asset_id,
            )
            .order_by(GEOScoreModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [
            GEOScore(
                overall=Score(m.overall),
                entity_density=Score(m.entity_density),
                answer_shape=Score(m.answer_shape),
                fact_citability=Score(m.fact_citability),
                rag_survivability=Score(m.rag_survivability),
                semantic_authority=Score(m.semantic_authority),
                freshness_signals=Score(m.freshness_signals),
            )
            for m in result.scalars().all()
        ]

    # ------------------------------------------------------------------
    # RAG Simulation
    # ------------------------------------------------------------------

    async def save_simulation_result(self, result: RAGSimulationResult) -> None:
        chunks_data = [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "token_count": c.token_count,
                "key_facts": list(c.key_facts),
                "embedding_quality": c.embedding_quality.value,
            }
            for c in result.chunks
        ]
        model = RAGSimulationResultModel(
            id=str(uuid4()),
            tenant_id=self._tenant_id,
            asset_id=result.asset_id,
            survived_facts=list(result.survived_facts),
            lost_facts=list(result.lost_facts),
            survivability_score=result.survivability_score.value,
            chunks=chunks_data,
        )
        self._session.add(model)
        await self._session.flush()

    # ------------------------------------------------------------------
    # Mapping helpers: domain -> ORM
    # ------------------------------------------------------------------

    def _suggestion_to_model(
        self, s: RewriteSuggestion, asset_id: str
    ) -> RewriteSuggestionModel:
        return RewriteSuggestionModel(
            id=s.id,
            tenant_id=self._tenant_id,
            asset_id=asset_id,
            original_text=s.original_text,
            suggested_text=s.suggested_text,
            factor=GEOFactorEnum(s.factor.value),
            expected_impact=s.expected_impact.value,
            rationale=s.rationale,
        )

    # ------------------------------------------------------------------
    # Mapping helpers: ORM -> domain
    # ------------------------------------------------------------------

    def _asset_model_to_domain(self, model: ContentAssetModel) -> ContentAsset:
        geo_score: GEOScore | None = None
        if model.geo_overall is not None:
            geo_score = GEOScore(
                overall=Score(model.geo_overall),
                entity_density=Score(model.geo_entity_density),
                answer_shape=Score(model.geo_answer_shape),
                fact_citability=Score(model.geo_fact_citability),
                rag_survivability=Score(model.geo_rag_survivability),
                semantic_authority=Score(model.geo_semantic_authority),
                freshness_signals=Score(model.geo_freshness_signals),
            )

        suggestions = tuple(
            RewriteSuggestion(
                id=s.id,
                asset_id=s.asset_id,
                original_text=s.original_text,
                suggested_text=s.suggested_text,
                factor=GEOFactor(s.factor.value),
                expected_impact=Score(s.expected_impact),
                rationale=s.rationale,
            )
            for s in model.suggestions
        )

        return ContentAsset(
            id=model.id,
            brand_id=BrandId(model.brand_id),
            url=URL(model.url),
            title=model.title,
            raw_content=model.raw_content,
            content_type=ContentType(model.content_type.value),
            geo_score=geo_score,
            last_scored_at=model.last_scored_at,
            suggestions=suggestions,
        )
