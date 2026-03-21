"""
Tests for SIGNAL domain entities.

Validates immutability, state transitions, coverage calculation,
and domain event collection on the DistributionPlan aggregate root.
"""

from __future__ import annotations

from datetime import datetime, UTC

import pytest

from lumina.shared.domain.value_objects import BrandId, Score, URL

from lumina.signal.domain.entities import (
    CitationSurface,
    DistributionAction,
    DistributionPlan,
)
from lumina.signal.domain.events import CoverageUpdated, SignalDistributed
from lumina.signal.domain.value_objects import (
    ActionStatus,
    ActionType,
    PresenceStatus,
    SurfaceCategory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_surface(
    *,
    id: str = "surface-1",
    name: str = "Wikipedia",
    category: SurfaceCategory = SurfaceCategory.AUTHORITY_PUBLICATIONS,
    weight: float = 90.0,
    presence: PresenceStatus = PresenceStatus.ABSENT,
) -> CitationSurface:
    return CitationSurface(
        id=id,
        name=name,
        category=category,
        url=URL("https://en.wikipedia.org"),
        estimated_llm_weight=Score(weight),
        brand_presence=presence,
        last_checked_at=datetime.now(UTC),
    )


def _make_action(
    *,
    id: str = "action-1",
    plan_id: str = "plan-1",
    surface_id: str = "surface-1",
    status: ActionStatus = ActionStatus.PLANNED,
) -> DistributionAction:
    return DistributionAction(
        id=id,
        plan_id=plan_id,
        surface_id=surface_id,
        action_type=ActionType.PUBLISH_CONTENT,
        content="Test content",
        status=status,
        scheduled_at=datetime.now(UTC),
    )


def _make_plan(
    *,
    id: str = "plan-1",
    brand_id: str = "test-brand",
    surfaces: tuple[CitationSurface, ...] = (),
    actions: tuple[DistributionAction, ...] = (),
) -> DistributionPlan:
    return DistributionPlan(
        id=id,
        brand_id=BrandId(brand_id),
        target_surfaces=surfaces,
        actions=actions,
    )


# ---------------------------------------------------------------------------
# Tests: DistributionPlan.add_action
# ---------------------------------------------------------------------------


class TestDistributionPlanAddAction:
    def test_add_action_creates_new_plan_with_action(self) -> None:
        plan = _make_plan()
        action = _make_action()

        new_plan = plan.add_action(action)

        assert new_plan is not plan
        assert len(new_plan.actions) == 1
        assert new_plan.actions[0] is action
        assert len(plan.actions) == 0  # original unchanged

    def test_add_action_preserves_existing_actions(self) -> None:
        action1 = _make_action(id="action-1")
        action2 = _make_action(id="action-2")
        plan = _make_plan(actions=(action1,))

        new_plan = plan.add_action(action2)

        assert len(new_plan.actions) == 2
        assert new_plan.actions[0].id == "action-1"
        assert new_plan.actions[1].id == "action-2"

    def test_add_action_preserves_plan_identity(self) -> None:
        plan = _make_plan(id="plan-42", brand_id="my-brand")
        action = _make_action()

        new_plan = plan.add_action(action)

        assert new_plan.id == "plan-42"
        assert new_plan.brand_id.value == "my-brand"


# ---------------------------------------------------------------------------
# Tests: DistributionPlan.mark_action_complete
# ---------------------------------------------------------------------------


class TestDistributionPlanMarkActionComplete:
    def test_mark_action_complete_updates_status(self) -> None:
        action = _make_action(id="action-1", status=ActionStatus.PLANNED)
        plan = _make_plan(actions=(action,))

        new_plan = plan.mark_action_complete("action-1", "https://result.com")

        assert new_plan.actions[0].status == ActionStatus.COMPLETED
        assert new_plan.actions[0].result_url == "https://result.com"
        assert new_plan.actions[0].completed_at is not None

    def test_mark_action_complete_collects_signal_distributed_event(self) -> None:
        surface = _make_surface(id="s-1")
        action = _make_action(id="action-1", surface_id="s-1")
        plan = _make_plan(surfaces=(surface,), actions=(action,))

        new_plan = plan.mark_action_complete("action-1", "https://result.com")

        assert len(new_plan.domain_events) == 1
        event = new_plan.domain_events[0]
        assert isinstance(event, SignalDistributed)
        assert event.surface_id == "s-1"
        assert event.result_url == "https://result.com"

    def test_mark_action_complete_raises_for_unknown_action(self) -> None:
        plan = _make_plan(actions=(_make_action(id="action-1"),))

        with pytest.raises(ValueError, match="Action nonexistent not found"):
            plan.mark_action_complete("nonexistent", "https://result.com")

    def test_mark_action_complete_leaves_other_actions_unchanged(self) -> None:
        action1 = _make_action(id="action-1", status=ActionStatus.PLANNED)
        action2 = _make_action(id="action-2", status=ActionStatus.PLANNED)
        plan = _make_plan(actions=(action1, action2))

        new_plan = plan.mark_action_complete("action-1", "https://r.com")

        assert new_plan.actions[0].status == ActionStatus.COMPLETED
        assert new_plan.actions[1].status == ActionStatus.PLANNED


# ---------------------------------------------------------------------------
# Tests: DistributionPlan.calculate_coverage
# ---------------------------------------------------------------------------


class TestDistributionPlanCalculateCoverage:
    def test_calculate_coverage_with_no_surfaces(self) -> None:
        plan = _make_plan()
        new_plan = plan.calculate_coverage()
        assert new_plan.coverage_score.value == 0.0

    def test_calculate_coverage_all_completed(self) -> None:
        s1 = _make_surface(id="s-1")
        s2 = _make_surface(id="s-2")
        a1 = _make_action(id="a-1", surface_id="s-1", status=ActionStatus.COMPLETED)
        a2 = _make_action(id="a-2", surface_id="s-2", status=ActionStatus.COMPLETED)

        plan = _make_plan(surfaces=(s1, s2), actions=(a1, a2))
        new_plan = plan.calculate_coverage()

        assert new_plan.coverage_score.value == 100.0

    def test_calculate_coverage_partial(self) -> None:
        s1 = _make_surface(id="s-1")
        s2 = _make_surface(id="s-2")
        a1 = _make_action(id="a-1", surface_id="s-1", status=ActionStatus.COMPLETED)
        a2 = _make_action(id="a-2", surface_id="s-2", status=ActionStatus.PLANNED)

        plan = _make_plan(surfaces=(s1, s2), actions=(a1, a2))
        new_plan = plan.calculate_coverage()

        assert new_plan.coverage_score.value == 50.0

    def test_calculate_coverage_emits_event_on_change(self) -> None:
        s1 = _make_surface(id="s-1")
        a1 = _make_action(id="a-1", surface_id="s-1", status=ActionStatus.COMPLETED)
        plan = _make_plan(surfaces=(s1,), actions=(a1,))

        new_plan = plan.calculate_coverage()

        assert len(new_plan.domain_events) == 1
        event = new_plan.domain_events[0]
        assert isinstance(event, CoverageUpdated)
        assert event.old_coverage == 0.0
        assert event.new_coverage == 100.0

    def test_calculate_coverage_no_event_when_unchanged(self) -> None:
        plan = _make_plan()  # 0 surfaces, 0 actions, coverage=0
        new_plan = plan.calculate_coverage()
        assert len(new_plan.domain_events) == 0


# ---------------------------------------------------------------------------
# Tests: CitationSurface immutability
# ---------------------------------------------------------------------------


class TestCitationSurfaceImmutability:
    def test_citation_surface_is_frozen(self) -> None:
        surface = _make_surface()

        with pytest.raises(AttributeError):
            surface.name = "Modified"  # type: ignore[misc]

    def test_citation_surface_fields_are_accessible(self) -> None:
        surface = _make_surface(
            id="s-42",
            name="Wikidata",
            category=SurfaceCategory.STRUCTURED_DATA,
            weight=88.0,
            presence=PresenceStatus.PARTIAL,
        )

        assert surface.id == "s-42"
        assert surface.name == "Wikidata"
        assert surface.category == SurfaceCategory.STRUCTURED_DATA
        assert surface.estimated_llm_weight.value == 88.0
        assert surface.brand_presence == PresenceStatus.PARTIAL

    def test_distribution_plan_is_frozen(self) -> None:
        plan = _make_plan()
        with pytest.raises(AttributeError):
            plan.id = "new-id"  # type: ignore[misc]

    def test_distribution_action_is_frozen(self) -> None:
        action = _make_action()
        with pytest.raises(AttributeError):
            action.status = ActionStatus.COMPLETED  # type: ignore[misc]
