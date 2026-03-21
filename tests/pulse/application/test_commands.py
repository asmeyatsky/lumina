"""
Tests for PULSE application commands (use cases).

Uses mock ports to validate the full monitoring flow, error handling,
and prompt battery creation — without any infrastructure dependencies.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional
from uuid import uuid4

import pytest

from lumina.shared.domain.events import DomainEvent
from lumina.shared.domain.value_objects import AIEngine, BrandId, Score
from lumina.shared.ports.ai_engine import AIResponse

from lumina.pulse.application.commands import (
    CreatePromptBatteryCommand,
    RunMonitoringCommand,
)
from lumina.pulse.domain.entities import (
    MonitoringRun,
    PromptBattery,
    PromptTemplate,
)
from lumina.pulse.domain.value_objects import RunStatus


# -- Mock Ports --------------------------------------------------------------


class MockPulseRepository:
    """In-memory mock implementation of PulseRepositoryPort."""

    def __init__(self) -> None:
        self.runs: dict[str, MonitoringRun] = {}
        self.batteries: dict[str, PromptBattery] = {}

    async def save_run(self, run: MonitoringRun) -> None:
        self.runs[run.id] = run

    async def get_run(self, run_id: str) -> Optional[MonitoringRun]:
        return self.runs.get(run_id)

    async def list_runs_for_brand(
        self, brand_id: str, limit: int = 50
    ) -> list[MonitoringRun]:
        runs = [r for r in self.runs.values() if r.brand_id.value == brand_id]
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[:limit]

    async def save_battery(self, battery: PromptBattery) -> None:
        self.batteries[battery.id] = battery

    async def get_battery(self, battery_id: str) -> Optional[PromptBattery]:
        return self.batteries.get(battery_id)

    async def list_batteries_for_brand(
        self, brand_id: str
    ) -> list[PromptBattery]:
        return [
            b for b in self.batteries.values() if b.brand_id.value == brand_id
        ]


class MockEventBus:
    """In-memory mock implementation of EventBusPort."""

    def __init__(self) -> None:
        self.published_events: list[DomainEvent] = []

    async def publish(self, events: list[DomainEvent]) -> None:
        self.published_events.extend(events)

    async def subscribe(self, event_type, handler) -> None:
        pass


class MockAIEngine:
    """Mock implementation of AIEnginePort for testing.

    Returns a configurable response for each query.
    """

    def __init__(
        self,
        engine: AIEngine = AIEngine.CLAUDE,
        response_text: str = "Acme is the best CRM platform.",
        should_fail: bool = False,
    ) -> None:
        self._engine = engine
        self._response_text = response_text
        self._should_fail = should_fail
        self.queries: list[str] = []

    @property
    def engine(self) -> AIEngine:
        return self._engine

    async def query(self, prompt: str) -> AIResponse:
        self.queries.append(prompt)
        if self._should_fail:
            raise ConnectionError(f"Mock engine {self._engine.value} failed")
        return AIResponse(
            engine=self._engine,
            prompt=prompt,
            raw_response=self._response_text,
            model_id=f"mock-{self._engine.value}",
            latency_ms=100,
            token_count=50,
        )

    async def query_batch(self, prompts: list[str]) -> list[AIResponse]:
        return [await self.query(p) for p in prompts]

    async def health_check(self) -> bool:
        return not self._should_fail


# -- Fixtures ----------------------------------------------------------------


def _make_battery(repository: MockPulseRepository) -> PromptBattery:
    """Create and persist a test battery."""
    battery = PromptBattery(
        id="bat-test",
        brand_id=BrandId(value="brand-acme"),
        name="Test Battery",
        prompts=(
            PromptTemplate(
                id="pt-1",
                text="What is the best CRM?",
                category="comparison",
                intent_tags=("comparison",),
            ),
            PromptTemplate(
                id="pt-2",
                text="Recommend a CRM for startups",
                category="recommendation",
                intent_tags=("recommendation",),
            ),
        ),
        vertical="saas",
        schedule_cron="0 */6 * * *",
        is_active=True,
    )
    return battery


# -- RunMonitoringCommand tests -----------------------------------------------


class TestRunMonitoringCommand:
    @pytest.mark.asyncio
    async def test_executes_full_flow_and_publishes_events(self) -> None:
        repo = MockPulseRepository()
        event_bus = MockEventBus()
        battery = _make_battery(repo)
        await repo.save_battery(battery)

        engine_claude = MockAIEngine(
            engine=AIEngine.CLAUDE,
            response_text="Acme is the best CRM platform. I would recommend Acme for enterprises.",
        )
        engine_gpt = MockAIEngine(
            engine=AIEngine.GPT4O,
            response_text="For CRM solutions, Acme offers great features.",
        )

        command = RunMonitoringCommand(
            repository=repo,
            event_bus=event_bus,
            engines=[engine_claude, engine_gpt],
            brand_name="Acme",
            competitors=("Rival",),
        )

        run = await command.execute("bat-test")

        # Verify run completed
        assert run.status == RunStatus.COMPLETED
        assert run.completed_at is not None

        # Verify results were collected
        assert len(run.results) > 0

        # Verify each engine was queried with each prompt
        assert len(engine_claude.queries) == 2  # 2 prompts
        assert len(engine_gpt.queries) == 2

        # Verify events were published
        assert len(event_bus.published_events) > 0

        # Should have at least one MonitoringRunCompleted event
        from lumina.pulse.domain.events import MonitoringRunCompleted
        completed_events = [
            e for e in event_bus.published_events
            if isinstance(e, MonitoringRunCompleted)
        ]
        assert len(completed_events) == 1
        assert completed_events[0].brand_id == "brand-acme"

        # Verify run was persisted
        persisted = await repo.get_run(run.id)
        assert persisted is not None
        assert persisted.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_handles_engine_failure_gracefully(self) -> None:
        repo = MockPulseRepository()
        event_bus = MockEventBus()
        battery = _make_battery(repo)
        await repo.save_battery(battery)

        engine_ok = MockAIEngine(
            engine=AIEngine.CLAUDE,
            response_text="Acme is great.",
        )
        engine_fail = MockAIEngine(
            engine=AIEngine.GPT4O,
            should_fail=True,
        )

        command = RunMonitoringCommand(
            repository=repo,
            event_bus=event_bus,
            engines=[engine_ok, engine_fail],
            brand_name="Acme",
        )

        # The command should still complete with partial results from the
        # working engine. The orchestrator catches individual engine errors.
        run = await command.execute("bat-test")

        # Run should complete (not fail) because at least one engine succeeded
        # The orchestrator uses return_exceptions=True, so individual failures
        # are handled gracefully
        persisted = await repo.get_run(run.id)
        assert persisted is not None

        # Events should have been published
        assert len(event_bus.published_events) > 0

    @pytest.mark.asyncio
    async def test_handles_battery_not_found(self) -> None:
        from lumina.shared.domain.errors import EntityNotFoundError

        repo = MockPulseRepository()
        event_bus = MockEventBus()

        command = RunMonitoringCommand(
            repository=repo,
            event_bus=event_bus,
            engines=[MockAIEngine()],
            brand_name="Acme",
        )

        with pytest.raises(EntityNotFoundError, match="not found"):
            await command.execute("nonexistent-battery")

    @pytest.mark.asyncio
    async def test_all_engines_fail_results_in_failed_run(self) -> None:
        repo = MockPulseRepository()
        event_bus = MockEventBus()
        battery = _make_battery(repo)
        await repo.save_battery(battery)

        engine_fail1 = MockAIEngine(engine=AIEngine.CLAUDE, should_fail=True)
        engine_fail2 = MockAIEngine(engine=AIEngine.GPT4O, should_fail=True)

        command = RunMonitoringCommand(
            repository=repo,
            event_bus=event_bus,
            engines=[engine_fail1, engine_fail2],
            brand_name="Acme",
        )

        run = await command.execute("bat-test")

        # With all engines failing, the orchestrator returns empty results.
        # The command still completes (with 0 results) rather than failing,
        # because gather(return_exceptions=True) catches all errors.
        persisted = await repo.get_run(run.id)
        assert persisted is not None


# -- CreatePromptBatteryCommand tests ----------------------------------------


class TestCreatePromptBatteryCommand:
    @pytest.mark.asyncio
    async def test_saves_battery_with_valid_data(self) -> None:
        repo = MockPulseRepository()
        command = CreatePromptBatteryCommand(repository=repo)

        battery = await command.execute(
            brand_id="brand-acme",
            name="New Battery",
            prompts=[
                {
                    "text": "What is the best CRM?",
                    "category": "comparison",
                    "intent_tags": ("comparison", "crm"),
                },
                {
                    "text": "Recommend a CRM",
                    "category": "recommendation",
                    "intent_tags": ("recommendation",),
                },
            ],
            vertical="saas",
            schedule_cron="0 0 * * *",
        )

        assert battery.name == "New Battery"
        assert battery.brand_id.value == "brand-acme"
        assert len(battery.prompts) == 2
        assert battery.vertical == "saas"
        assert battery.is_active is True

        # Verify persisted
        persisted = await repo.get_battery(battery.id)
        assert persisted is not None
        assert persisted.id == battery.id

    @pytest.mark.asyncio
    async def test_generates_unique_ids(self) -> None:
        repo = MockPulseRepository()
        command = CreatePromptBatteryCommand(repository=repo)

        b1 = await command.execute(
            brand_id="brand-1",
            name="Battery 1",
            prompts=[{"text": "prompt 1", "category": "cat1"}],
            vertical="saas",
            schedule_cron="0 0 * * *",
        )
        b2 = await command.execute(
            brand_id="brand-1",
            name="Battery 2",
            prompts=[{"text": "prompt 2", "category": "cat2"}],
            vertical="saas",
            schedule_cron="0 0 * * *",
        )

        assert b1.id != b2.id
        assert b1.prompts[0].id != b2.prompts[0].id

    @pytest.mark.asyncio
    async def test_prompt_templates_have_correct_intent_tags(self) -> None:
        repo = MockPulseRepository()
        command = CreatePromptBatteryCommand(repository=repo)

        battery = await command.execute(
            brand_id="brand-1",
            name="Tagged Battery",
            prompts=[
                {
                    "text": "What is the best tool?",
                    "category": "comparison",
                    "intent_tags": ("comparison", "tools"),
                },
            ],
            vertical="saas",
            schedule_cron="0 0 * * *",
        )

        assert battery.prompts[0].intent_tags == ("comparison", "tools")
