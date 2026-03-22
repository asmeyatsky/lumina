"""
Tests for ORBIT Domain Entities

Verifies:
- AgentSession lifecycle (start, set_plan, begin_cycle, record_action, complete)
- AgentSession invariant enforcement (empty goal, guardrail limits)
- AgentPlan step management and progress tracking
- PlanStep dependency resolution
- AgentInsight confidence validation
- ExecutionCycle action recording
- Domain event emission at each state transition
"""

from __future__ import annotations

import pytest
from datetime import datetime, UTC

from lumina.orbit.domain.entities import (
    AgentAction,
    AgentInsight,
    AgentPlan,
    AgentSession,
    ExecutionCycle,
    PlanStep,
)
from lumina.orbit.domain.events import (
    ActionExecuted,
    CycleCompleted,
    GoalAchieved,
    InsightGenerated,
    PlanCreated,
    SessionFailed,
    SessionStarted,
)
from lumina.orbit.domain.value_objects import (
    ActionStatus,
    AutonomyLevel,
    CyclePhase,
    Guardrails,
    InsightSeverity,
    ModuleTarget,
    SessionState,
    StepStatus,
)


class TestAgentSession:
    """Tests for the AgentSession aggregate root."""

    def test_start_creates_session_with_event(self) -> None:
        session = AgentSession.start(
            brand_id="brand-1",
            goal="Diagnose citation drop",
        )
        assert session.brand_id == "brand-1"
        assert session.goal == "Diagnose citation drop"
        assert session.state == SessionState.PLANNING
        assert session.autonomy_level == AutonomyLevel.GUIDED
        assert session.cycle_count == 0
        assert session.total_actions == 0
        assert len(session.domain_events) == 1
        assert isinstance(session.domain_events[0], SessionStarted)

    def test_empty_goal_raises(self) -> None:
        with pytest.raises(ValueError, match="goal cannot be empty"):
            AgentSession(brand_id="brand-1", goal="")

    def test_whitespace_goal_raises(self) -> None:
        with pytest.raises(ValueError, match="goal cannot be empty"):
            AgentSession(brand_id="brand-1", goal="   ")

    def test_set_plan_guided_goes_to_awaiting_approval(self) -> None:
        session = AgentSession.start(
            brand_id="brand-1",
            goal="Test goal",
            autonomy_level=AutonomyLevel.GUIDED,
        )
        plan = AgentPlan(steps=(PlanStep(tool_name="calculate_avs"),), rationale="Test")

        session = session.set_plan(plan)
        assert session.state == SessionState.AWAITING_APPROVAL
        assert session.plan is not None
        assert any(isinstance(e, PlanCreated) for e in session.domain_events)

    def test_set_plan_autonomous_goes_directly_to_executing(self) -> None:
        session = AgentSession.start(
            brand_id="brand-1",
            goal="Test goal",
            autonomy_level=AutonomyLevel.AUTONOMOUS,
        )
        plan = AgentPlan(steps=(PlanStep(tool_name="calculate_avs"),), rationale="Test")

        session = session.set_plan(plan)
        assert session.state == SessionState.EXECUTING

    def test_approve_plan_transitions_to_executing(self) -> None:
        session = AgentSession.start(
            brand_id="brand-1",
            goal="Test goal",
            autonomy_level=AutonomyLevel.GUIDED,
        )
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)
        assert session.state == SessionState.AWAITING_APPROVAL

        session = session.approve_plan()
        assert session.state == SessionState.EXECUTING

    def test_approve_plan_wrong_state_raises(self) -> None:
        session = AgentSession.start(brand_id="brand-1", goal="Test")
        with pytest.raises(ValueError, match="Cannot approve plan"):
            session.approve_plan()

    def test_begin_cycle_adds_cycle(self) -> None:
        session = AgentSession.start(
            brand_id="brand-1",
            goal="Test",
            autonomy_level=AutonomyLevel.AUTONOMOUS,
        )
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)

        session = session.begin_cycle()
        assert session.cycle_count == 1
        assert session.state == SessionState.EXECUTING
        assert session.current_cycle is not None
        assert session.current_cycle.cycle_number == 1

    def test_begin_cycle_respects_max_cycles(self) -> None:
        session = AgentSession.start(
            brand_id="brand-1",
            goal="Test",
            autonomy_level=AutonomyLevel.AUTONOMOUS,
            guardrails=Guardrails(max_cycles=1),
        )
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)

        # First cycle OK
        session = session.begin_cycle()
        # Complete the cycle
        session = session.complete_cycle("Done", ())
        # Second cycle should fail
        with pytest.raises(ValueError, match="Cannot start new cycle"):
            session.begin_cycle()

    def test_record_action_adds_to_current_cycle(self) -> None:
        session = AgentSession.start(
            brand_id="brand-1",
            goal="Test",
            autonomy_level=AutonomyLevel.AUTONOMOUS,
        )
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)
        session = session.begin_cycle()

        action = AgentAction(
            module=ModuleTarget.PULSE,
            tool_name="run_monitoring",
            status=ActionStatus.SUCCEEDED,
            duration_ms=150,
        )
        session = session.record_action(action)

        assert session.total_actions == 1
        assert session.current_cycle is not None
        assert session.current_cycle.action_count == 1
        assert any(isinstance(e, ActionExecuted) for e in session.domain_events)

    def test_record_action_no_cycle_raises(self) -> None:
        session = AgentSession.start(brand_id="brand-1", goal="Test")
        action = AgentAction(module=ModuleTarget.PULSE, tool_name="test")
        with pytest.raises(ValueError, match="No active cycle"):
            session.record_action(action)

    def test_complete_cycle_with_insights(self) -> None:
        session = AgentSession.start(
            brand_id="brand-1",
            goal="Test",
            autonomy_level=AutonomyLevel.AUTONOMOUS,
        )
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)
        session = session.begin_cycle()

        insight = AgentInsight(
            severity=InsightSeverity.WARNING,
            confidence=0.85,
            finding="Citation rate dropped 15%",
            source_module=ModuleTarget.PULSE,
        )
        session = session.complete_cycle("Analysis complete", (insight,))

        assert session.cycles[-1].completed_at is not None
        assert session.cycles[-1].synthesis == "Analysis complete"
        assert len(session.insights) == 1
        assert any(isinstance(e, CycleCompleted) for e in session.domain_events)
        assert any(isinstance(e, InsightGenerated) for e in session.domain_events)

    def test_mark_complete(self) -> None:
        session = AgentSession.start(brand_id="brand-1", goal="Test")
        session = session.mark_complete()
        assert session.state == SessionState.COMPLETE
        assert session.completed_at is not None
        assert session.is_terminal is True
        assert any(isinstance(e, GoalAchieved) for e in session.domain_events)

    def test_mark_failed(self) -> None:
        session = AgentSession.start(brand_id="brand-1", goal="Test")
        session = session.mark_failed("Guardrail limit reached")
        assert session.state == SessionState.FAILED
        assert session.failure_reason == "Guardrail limit reached"
        assert session.is_terminal is True
        assert any(isinstance(e, SessionFailed) for e in session.domain_events)

    def test_pause_and_resume(self) -> None:
        session = AgentSession.start(brand_id="brand-1", goal="Test")
        session = session.pause()
        assert session.state == SessionState.PAUSED

        session = session.resume()
        assert session.state == SessionState.EXECUTING

    def test_resume_wrong_state_raises(self) -> None:
        session = AgentSession.start(brand_id="brand-1", goal="Test")
        with pytest.raises(ValueError, match="Cannot resume"):
            session.resume()

    def test_is_frozen(self) -> None:
        session = AgentSession.start(brand_id="brand-1", goal="Test")
        with pytest.raises(AttributeError):
            session.brand_id = "brand-2"  # type: ignore[misc]


class TestAgentPlan:
    """Tests for the AgentPlan entity."""

    def test_pending_steps(self) -> None:
        steps = (
            PlanStep(id="s1", tool_name="t1", status=StepStatus.COMPLETED),
            PlanStep(id="s2", tool_name="t2", status=StepStatus.PENDING),
            PlanStep(id="s3", tool_name="t3", status=StepStatus.PENDING),
        )
        plan = AgentPlan(steps=steps)
        assert len(plan.pending_steps) == 2

    def test_is_complete(self) -> None:
        steps = (
            PlanStep(id="s1", tool_name="t1", status=StepStatus.COMPLETED),
            PlanStep(id="s2", tool_name="t2", status=StepStatus.COMPLETED),
        )
        plan = AgentPlan(steps=steps)
        assert plan.is_complete is True

    def test_is_not_complete(self) -> None:
        steps = (
            PlanStep(id="s1", tool_name="t1", status=StepStatus.COMPLETED),
            PlanStep(id="s2", tool_name="t2", status=StepStatus.PENDING),
        )
        plan = AgentPlan(steps=steps)
        assert plan.is_complete is False

    def test_progress_fraction(self) -> None:
        steps = (
            PlanStep(id="s1", tool_name="t1", status=StepStatus.COMPLETED),
            PlanStep(id="s2", tool_name="t2", status=StepStatus.PENDING),
            PlanStep(id="s3", tool_name="t3", status=StepStatus.SKIPPED),
            PlanStep(id="s4", tool_name="t4", status=StepStatus.PENDING),
        )
        plan = AgentPlan(steps=steps)
        assert plan.progress_fraction == pytest.approx(0.5)

    def test_empty_plan_is_complete(self) -> None:
        plan = AgentPlan(steps=())
        assert plan.is_complete is True
        assert plan.progress_fraction == 1.0

    def test_ready_steps_respects_dependencies(self) -> None:
        steps = (
            PlanStep(id="s1", tool_name="t1", status=StepStatus.COMPLETED),
            PlanStep(id="s2", tool_name="t2", depends_on=("s1",)),
            PlanStep(id="s3", tool_name="t3", depends_on=("s2",)),
        )
        plan = AgentPlan(steps=steps)
        ready = plan.ready_steps
        assert len(ready) == 1
        assert ready[0].id == "s2"

    def test_update_step(self) -> None:
        step = PlanStep(id="s1", tool_name="t1")
        plan = AgentPlan(steps=(step,))
        updated = step.mark_completed("Done")
        new_plan = plan.update_step("s1", updated)
        assert new_plan.steps[0].status == StepStatus.COMPLETED
        assert new_plan.steps[0].result_summary == "Done"


class TestPlanStep:
    """Tests for the PlanStep entity."""

    def test_is_ready_no_dependencies(self) -> None:
        step = PlanStep(id="s1", tool_name="t1")
        assert step.is_ready(frozenset()) is True

    def test_is_ready_with_met_dependencies(self) -> None:
        step = PlanStep(id="s2", tool_name="t2", depends_on=("s1",))
        assert step.is_ready(frozenset({"s1"})) is True

    def test_is_not_ready_with_unmet_dependencies(self) -> None:
        step = PlanStep(id="s2", tool_name="t2", depends_on=("s1",))
        assert step.is_ready(frozenset()) is False

    def test_mark_completed(self) -> None:
        step = PlanStep(id="s1", tool_name="t1")
        completed = step.mark_completed("All good")
        assert completed.status == StepStatus.COMPLETED
        assert completed.result_summary == "All good"
        # Original unchanged
        assert step.status == StepStatus.PENDING

    def test_mark_failed(self) -> None:
        step = PlanStep(id="s1", tool_name="t1")
        failed = step.mark_failed("Connection error")
        assert failed.status == StepStatus.FAILED
        assert failed.result_summary == "Connection error"


class TestAgentAction:
    """Tests for the AgentAction entity."""

    def test_mark_succeeded(self) -> None:
        action = AgentAction(module=ModuleTarget.PULSE, tool_name="run_monitoring")
        now = datetime.now(UTC)
        succeeded = action.mark_succeeded('{"ok": true}', now, 150)
        assert succeeded.status == ActionStatus.SUCCEEDED
        assert succeeded.result_json == '{"ok": true}'
        assert succeeded.duration_ms == 150
        assert succeeded.completed_at == now

    def test_mark_failed(self) -> None:
        action = AgentAction(module=ModuleTarget.BEAM, tool_name="score_content")
        now = datetime.now(UTC)
        failed = action.mark_failed("Timeout", now, 5000)
        assert failed.status == ActionStatus.FAILED
        assert failed.error_message == "Timeout"
        assert failed.duration_ms == 5000


class TestAgentInsight:
    """Tests for the AgentInsight entity."""

    def test_valid_confidence(self) -> None:
        insight = AgentInsight(confidence=0.85, finding="Test")
        assert insight.confidence == 0.85

    def test_confidence_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence must be between"):
            AgentInsight(confidence=1.5, finding="Test")

    def test_confidence_too_low_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence must be between"):
            AgentInsight(confidence=-0.1, finding="Test")

    def test_is_frozen(self) -> None:
        insight = AgentInsight(finding="Test")
        with pytest.raises(AttributeError):
            insight.finding = "Changed"  # type: ignore[misc]


class TestExecutionCycle:
    """Tests for the ExecutionCycle entity."""

    def test_add_action(self) -> None:
        cycle = ExecutionCycle(cycle_number=1)
        action = AgentAction(module=ModuleTarget.PULSE, tool_name="test")
        updated = cycle.add_action(action)
        assert updated.action_count == 1
        assert cycle.action_count == 0  # Original unchanged

    def test_succeeded_and_failed_actions(self) -> None:
        now = datetime.now(UTC)
        cycle = ExecutionCycle(cycle_number=1)
        ok = AgentAction(
            module=ModuleTarget.PULSE,
            tool_name="t1",
            status=ActionStatus.SUCCEEDED,
        )
        fail = AgentAction(
            module=ModuleTarget.BEAM,
            tool_name="t2",
            status=ActionStatus.FAILED,
        )
        cycle = cycle.add_action(ok)
        cycle = cycle.add_action(fail)
        assert len(cycle.succeeded_actions) == 1
        assert len(cycle.failed_actions) == 1

    def test_complete(self) -> None:
        cycle = ExecutionCycle(cycle_number=1)
        insight = AgentInsight(finding="Test insight")
        completed = cycle.complete("Summary", (insight,))
        assert completed.phase == CyclePhase.SYNTHESIZE
        assert completed.synthesis == "Summary"
        assert len(completed.insights) == 1
        assert completed.completed_at is not None
