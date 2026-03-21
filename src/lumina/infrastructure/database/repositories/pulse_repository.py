"""
PostgreSQL Repository — PULSE bounded context

Implements PulseRepositoryPort by mapping between frozen domain dataclasses
and SQLAlchemy ORM models, using async sessions throughout.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lumina.shared.domain.value_objects import AIEngine, BrandId, Score, URL
from lumina.pulse.domain.entities import (
    Citation,
    CitationResult,
    MonitoringRun,
    PromptBattery,
    PromptTemplate,
)
from lumina.pulse.domain.value_objects import CitationPosition, RunStatus, Sentiment

from lumina.infrastructure.database.models import (
    AIEngineEnum,
    CitationModel,
    CitationPositionEnum,
    CitationResultModel,
    MonitoringRunModel,
    PromptBatteryModel,
    PromptTemplateModel,
    RunStatusEnum,
    SentimentEnum,
)


class PulseRepository:
    """Async PostgreSQL implementation of PulseRepositoryPort."""

    def __init__(self, session: AsyncSession, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ------------------------------------------------------------------
    # MonitoringRun
    # ------------------------------------------------------------------

    async def save_run(self, run: MonitoringRun) -> None:
        existing = await self._session.get(MonitoringRunModel, run.id)
        if existing is not None:
            existing.brand_id = run.brand_id.value
            existing.battery_id = run.battery_id
            existing.status = RunStatusEnum(run.status.value)
            existing.started_at = run.started_at
            existing.completed_at = run.completed_at
            existing.updated_at = existing.updated_at  # triggers onupdate

            # Sync results: clear existing and re-add
            existing.results.clear()
            for cr in run.results:
                existing.results.append(self._citation_result_to_model(cr, run.id))
        else:
            model = MonitoringRunModel(
                id=run.id,
                tenant_id=self._tenant_id,
                brand_id=run.brand_id.value,
                battery_id=run.battery_id,
                status=RunStatusEnum(run.status.value),
                started_at=run.started_at,
                completed_at=run.completed_at,
            )
            for cr in run.results:
                model.results.append(self._citation_result_to_model(cr, run.id))
            self._session.add(model)

        await self._session.flush()

    async def get_run(self, run_id: str) -> Optional[MonitoringRun]:
        model = await self._session.get(MonitoringRunModel, run_id)
        if model is None or model.tenant_id != self._tenant_id:
            return None
        return self._run_model_to_domain(model)

    async def list_runs_for_brand(
        self, brand_id: str, limit: int = 50
    ) -> list[MonitoringRun]:
        stmt = (
            select(MonitoringRunModel)
            .where(
                MonitoringRunModel.tenant_id == self._tenant_id,
                MonitoringRunModel.brand_id == brand_id,
            )
            .order_by(MonitoringRunModel.started_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._run_model_to_domain(m) for m in result.scalars().all()]

    # ------------------------------------------------------------------
    # PromptBattery
    # ------------------------------------------------------------------

    async def save_battery(self, battery: PromptBattery) -> None:
        existing = await self._session.get(PromptBatteryModel, battery.id)
        if existing is not None:
            existing.brand_id = battery.brand_id.value
            existing.name = battery.name
            existing.vertical = battery.vertical
            existing.schedule_cron = battery.schedule_cron
            existing.is_active = battery.is_active

            existing.prompts.clear()
            for pt in battery.prompts:
                existing.prompts.append(self._prompt_template_to_model(pt, battery.id))
        else:
            model = PromptBatteryModel(
                id=battery.id,
                tenant_id=self._tenant_id,
                brand_id=battery.brand_id.value,
                name=battery.name,
                vertical=battery.vertical,
                schedule_cron=battery.schedule_cron,
                is_active=battery.is_active,
            )
            for pt in battery.prompts:
                model.prompts.append(self._prompt_template_to_model(pt, battery.id))
            self._session.add(model)

        await self._session.flush()

    async def get_battery(self, battery_id: str) -> Optional[PromptBattery]:
        model = await self._session.get(PromptBatteryModel, battery_id)
        if model is None or model.tenant_id != self._tenant_id:
            return None
        return self._battery_model_to_domain(model)

    async def list_batteries_for_brand(
        self, brand_id: str
    ) -> list[PromptBattery]:
        stmt = (
            select(PromptBatteryModel)
            .where(
                PromptBatteryModel.tenant_id == self._tenant_id,
                PromptBatteryModel.brand_id == brand_id,
            )
            .order_by(PromptBatteryModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._battery_model_to_domain(m) for m in result.scalars().all()]

    # ------------------------------------------------------------------
    # Mapping helpers: domain -> ORM
    # ------------------------------------------------------------------

    def _prompt_template_to_model(
        self, pt: PromptTemplate, battery_id: str
    ) -> PromptTemplateModel:
        return PromptTemplateModel(
            id=pt.id,
            tenant_id=self._tenant_id,
            battery_id=battery_id,
            text=pt.text,
            category=pt.category,
            intent_tags=list(pt.intent_tags),
        )

    def _citation_result_to_model(
        self, cr: CitationResult, run_id: str
    ) -> CitationResultModel:
        model = CitationResultModel(
            id=cr.id,
            tenant_id=self._tenant_id,
            run_id=run_id,
            engine=AIEngineEnum(cr.engine.value),
            prompt_text=cr.prompt_text,
            raw_response=cr.raw_response,
            sentiment=SentimentEnum(cr.sentiment.value),
            accuracy_score=cr.accuracy_score.value,
            response_latency_ms=cr.response_latency_ms,
        )
        for c in cr.citations:
            model.citations.append(
                CitationModel(
                    tenant_id=self._tenant_id,
                    citation_result_id=cr.id,
                    brand_name=c.brand_name,
                    context=c.context,
                    position=CitationPositionEnum(c.position.value),
                    is_recommendation=c.is_recommendation,
                    source_url=c.source_url.value if c.source_url else None,
                )
            )
        return model

    # ------------------------------------------------------------------
    # Mapping helpers: ORM -> domain
    # ------------------------------------------------------------------

    def _run_model_to_domain(self, model: MonitoringRunModel) -> MonitoringRun:
        results = tuple(
            self._citation_result_model_to_domain(cr) for cr in model.results
        )
        return MonitoringRun(
            id=model.id,
            brand_id=BrandId(model.brand_id),
            battery_id=model.battery_id,
            started_at=model.started_at,
            completed_at=model.completed_at,
            status=RunStatus(model.status.value),
            results=results,
        )

    def _citation_result_model_to_domain(
        self, model: CitationResultModel
    ) -> CitationResult:
        citations = tuple(
            Citation(
                brand_name=c.brand_name,
                context=c.context,
                position=CitationPosition(c.position.value),
                is_recommendation=c.is_recommendation,
                source_url=URL(c.source_url) if c.source_url else None,
            )
            for c in model.citations
        )
        return CitationResult(
            id=model.id,
            run_id=model.run_id,
            engine=AIEngine(model.engine.value),
            prompt_text=model.prompt_text,
            raw_response=model.raw_response,
            citations=citations,
            sentiment=Sentiment(model.sentiment.value),
            accuracy_score=Score(model.accuracy_score),
            response_latency_ms=model.response_latency_ms,
        )

    def _battery_model_to_domain(self, model: PromptBatteryModel) -> PromptBattery:
        prompts = tuple(
            PromptTemplate(
                id=pt.id,
                text=pt.text,
                category=pt.category,
                intent_tags=tuple(pt.intent_tags) if pt.intent_tags else (),
            )
            for pt in model.prompts
        )
        return PromptBattery(
            id=model.id,
            brand_id=BrandId(model.brand_id),
            name=model.name,
            prompts=prompts,
            vertical=model.vertical,
            schedule_cron=model.schedule_cron,
            is_active=model.is_active,
        )
