"""
Tests for SIGNAL application commands (use cases).

All infrastructure ports are mocked to isolate command logic.
"""

from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import AsyncMock

import pytest

from lumina.shared.domain.value_objects import BrandId, Score, URL

from lumina.signal.application.commands import (
    CreateDistributionPlanCommand,
    ExecuteDistributionActionCommand,
    GeneratePRBriefCommand,
)
from lumina.signal.domain.entities import (
    CitationSurface,
    DistributionAction,
    DistributionPlan,
)
from lumina.signal.domain.events import (
    DistributionPlanCreated,
    PRBriefGenerated,
    SignalDistributed,
)
from lumina.signal.domain.services import (
    CoverageCalculationService,
    PRBriefGenerationService,
    SurfacePrioritizationService,
)
from lumina.signal.domain.value_objects import (
    ActionStatus,
    ActionType,
    PresenceStatus,
    SurfaceCategory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_surface(
    *,
    id: str = "s-1",
    name: str = "Wikipedia",
    presence: PresenceStatus = PresenceStatus.ABSENT,
    weight: float = 90.0,
) -> CitationSurface:
    return CitationSurface(
        id=id,
        name=name,
        category=SurfaceCategory.AUTHORITY_PUBLICATIONS,
        url=URL("https://en.wikipedia.org"),
        estimated_llm_weight=Score(weight),
        brand_presence=presence,
        last_checked_at=datetime.now(UTC),
    )


def _make_mock_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.save_plan = AsyncMock()
    repo.get_plan = AsyncMock(return_value=None)
    repo.list_plans_for_brand = AsyncMock(return_value=[])
    repo.save_surface = AsyncMock()
    repo.get_surfaces_for_brand = AsyncMock(return_value=[])
    repo.save_pr_brief = AsyncMock()
    repo.get_pr_briefs_for_brand = AsyncMock(return_value=[])
    return repo


def _make_mock_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


# ---------------------------------------------------------------------------
# CreateDistributionPlanCommand
# ---------------------------------------------------------------------------


class TestCreateDistributionPlanCommand:
    @pytest.mark.asyncio
    async def test_creates_and_saves_plan(self) -> None:
        repo = _make_mock_repository()
        event_bus = _make_mock_event_bus()

        surfaces = [
            _make_surface(id="s-1", presence=PresenceStatus.ABSENT),
            _make_surface(id="s-2", presence=PresenceStatus.PRESENT),
        ]

        cmd = CreateDistributionPlanCommand(
            repository=repo,
            event_bus=event_bus,
            prioritization_service=SurfacePrioritizationService(),
            coverage_service=CoverageCalculationService(),
        )

        plan = await cmd.execute(
            brand_id="test-brand",
            surfaces=surfaces,
            brand_gaps=["s-1"],
        )

        # Plan was saved
        repo.save_plan.assert_called_once()
        saved_plan = repo.save_plan.call_args[0][0]
        assert saved_plan.brand_id.value == "test-brand"

        # Events were published (DistributionPlanCreated + SurfaceGapIdentified)
        event_bus.publish.assert_called_once()
        published_events = event_bus.publish.call_args[0][0]
        assert any(isinstance(e, DistributionPlanCreated) for e in published_events)

        # Plan returned has correct structure
        assert plan.brand_id.value == "test-brand"
        assert len(plan.target_surfaces) == 2

    @pytest.mark.asyncio
    async def test_generates_actions_for_absent_surfaces(self) -> None:
        repo = _make_mock_repository()
        event_bus = _make_mock_event_bus()

        surfaces = [
            _make_surface(id="s-1", presence=PresenceStatus.ABSENT),
            _make_surface(id="s-2", presence=PresenceStatus.ABSENT),
            _make_surface(id="s-3", presence=PresenceStatus.PRESENT),
        ]

        cmd = CreateDistributionPlanCommand(
            repository=repo,
            event_bus=event_bus,
            prioritization_service=SurfacePrioritizationService(),
            coverage_service=CoverageCalculationService(),
        )

        plan = await cmd.execute(
            brand_id="test-brand",
            surfaces=surfaces,
            brand_gaps=[],
        )

        # Only absent surfaces get actions
        assert len(plan.actions) == 2
        action_surface_ids = {a.surface_id for a in plan.actions}
        assert "s-1" in action_surface_ids
        assert "s-2" in action_surface_ids
        assert "s-3" not in action_surface_ids

    @pytest.mark.asyncio
    async def test_plan_events_are_cleared_on_return(self) -> None:
        repo = _make_mock_repository()
        event_bus = _make_mock_event_bus()

        cmd = CreateDistributionPlanCommand(
            repository=repo,
            event_bus=event_bus,
            prioritization_service=SurfacePrioritizationService(),
            coverage_service=CoverageCalculationService(),
        )

        plan = await cmd.execute(
            brand_id="test-brand",
            surfaces=[_make_surface()],
            brand_gaps=[],
        )

        # Events should be cleared after publishing
        assert len(plan.domain_events) == 0


# ---------------------------------------------------------------------------
# ExecuteDistributionActionCommand
# ---------------------------------------------------------------------------


class TestExecuteDistributionActionCommand:
    @pytest.mark.asyncio
    async def test_executes_action_and_publishes_event(self) -> None:
        repo = _make_mock_repository()
        event_bus = _make_mock_event_bus()
        syndication_port = AsyncMock()
        syndication_port.syndicate_to_platform = AsyncMock(
            return_value="https://published.com/article"
        )
        structured_data_port = AsyncMock()
        wikidata_port = AsyncMock()

        # Set up a plan with one planned action
        surface = _make_surface(id="s-1")
        action = DistributionAction(
            id="action-1",
            plan_id="plan-1",
            surface_id="s-1",
            action_type=ActionType.PUBLISH_CONTENT,
            content="Brand article content",
            status=ActionStatus.PLANNED,
            scheduled_at=datetime.now(UTC),
        )
        existing_plan = DistributionPlan(
            id="plan-1",
            brand_id=BrandId("test-brand"),
            target_surfaces=(surface,),
            actions=(action,),
        )
        repo.get_plan = AsyncMock(return_value=existing_plan)

        cmd = ExecuteDistributionActionCommand(
            repository=repo,
            event_bus=event_bus,
            structured_data_port=structured_data_port,
            syndication_port=syndication_port,
            wikidata_port=wikidata_port,
        )

        result = await cmd.execute(plan_id="plan-1", action_id="action-1")

        # Action is now completed
        completed_action = result.actions[0]
        assert completed_action.status == ActionStatus.COMPLETED
        assert completed_action.result_url == "https://published.com/article"

        # Plan was saved
        repo.save_plan.assert_called_once()

        # Events were published (SignalDistributed + CoverageUpdated)
        event_bus.publish.assert_called_once()
        published_events = event_bus.publish.call_args[0][0]
        assert any(isinstance(e, SignalDistributed) for e in published_events)

    @pytest.mark.asyncio
    async def test_raises_for_missing_plan(self) -> None:
        repo = _make_mock_repository()
        repo.get_plan = AsyncMock(return_value=None)
        event_bus = _make_mock_event_bus()

        cmd = ExecuteDistributionActionCommand(
            repository=repo,
            event_bus=event_bus,
            structured_data_port=AsyncMock(),
            syndication_port=AsyncMock(),
            wikidata_port=AsyncMock(),
        )

        with pytest.raises(ValueError, match="not found"):
            await cmd.execute(plan_id="nonexistent", action_id="a-1")

    @pytest.mark.asyncio
    async def test_routes_structured_data_to_search_console(self) -> None:
        repo = _make_mock_repository()
        event_bus = _make_mock_event_bus()
        structured_data_port = AsyncMock()
        structured_data_port.submit_to_google_search_console = AsyncMock(return_value=True)

        action = DistributionAction(
            id="action-1",
            plan_id="plan-1",
            surface_id="s-1",
            action_type=ActionType.SUBMIT_STRUCTURED_DATA,
            content='{"@type": "Organization"}',
            status=ActionStatus.PLANNED,
            scheduled_at=datetime.now(UTC),
        )
        surface = _make_surface(id="s-1")
        existing_plan = DistributionPlan(
            id="plan-1",
            brand_id=BrandId("test-brand"),
            target_surfaces=(surface,),
            actions=(action,),
        )
        repo.get_plan = AsyncMock(return_value=existing_plan)

        cmd = ExecuteDistributionActionCommand(
            repository=repo,
            event_bus=event_bus,
            structured_data_port=structured_data_port,
            syndication_port=AsyncMock(),
            wikidata_port=AsyncMock(),
        )

        result = await cmd.execute(plan_id="plan-1", action_id="action-1")

        structured_data_port.submit_to_google_search_console.assert_called_once()
        assert result.actions[0].status == ActionStatus.COMPLETED


# ---------------------------------------------------------------------------
# GeneratePRBriefCommand
# ---------------------------------------------------------------------------


class TestGeneratePRBriefCommand:
    @pytest.mark.asyncio
    async def test_generates_and_saves_brief(self) -> None:
        repo = _make_mock_repository()
        event_bus = _make_mock_event_bus()

        cmd = GeneratePRBriefCommand(
            repository=repo,
            event_bus=event_bus,
            brief_service=PRBriefGenerationService(),
        )

        brief = await cmd.execute(
            brand_name="Acme Corp",
            entity_data={
                "brand_id": "acme",
                "industry": "technology",
                "key_products": "Widget, Gadget",
            },
            target_narrative="Innovation Leader",
        )

        # Brief was saved
        repo.save_pr_brief.assert_called_once()

        # Event was published
        event_bus.publish.assert_called_once()
        published_events = event_bus.publish.call_args[0][0]
        assert len(published_events) == 1
        assert isinstance(published_events[0], PRBriefGenerated)
        assert published_events[0].headline == brief.headline

        # Brief has correct content
        assert brief.brand_id.value == "acme"
        assert "Acme Corp" in brief.headline
        assert "Innovation Leader" in brief.headline
        assert len(brief.key_messages) > 0
        assert len(brief.target_publications) > 0

    @pytest.mark.asyncio
    async def test_brief_includes_entity_anchors(self) -> None:
        repo = _make_mock_repository()
        event_bus = _make_mock_event_bus()

        cmd = GeneratePRBriefCommand(
            repository=repo,
            event_bus=event_bus,
            brief_service=PRBriefGenerationService(),
        )

        brief = await cmd.execute(
            brand_name="TestBrand",
            entity_data={
                "brand_id": "testbrand",
                "key_products": "Alpha, Beta",
                "leadership": "John Smith",
            },
            target_narrative="Market Disruptor",
        )

        assert "TestBrand" in brief.entity_anchors
        assert "Alpha" in brief.entity_anchors
        assert "Beta" in brief.entity_anchors
        assert "John Smith" in brief.entity_anchors
