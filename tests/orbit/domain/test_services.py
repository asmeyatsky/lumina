"""
Tests for ORBIT Domain Services

Verifies:
- GuardrailService blocks disallowed modules and tools
- GuardrailService enforces action limits
- PlanAnalysisService validates plan steps against tools
- PlanAnalysisService detects circular dependencies
- InsightAggregationService ranks by severity then confidence
- CycleMetricsService computes correct success rates
"""

from __future__ import annotations

import pytest

from lumina.orbit.domain.entities import (
    AgentAction,
    AgentInsight,
    AgentPlan,
    AgentSession,
    ExecutionCycle,
    PlanStep,
)
from lumina.orbit.domain.services import (
    CycleMetricsService,
    GuardrailService,
    InsightAggregationService,
    PlanAnalysisService,
)
from lumina.orbit.domain.value_objects import (
    ActionStatus,
    AutonomyLevel,
    Guardrails,
    InsightSeverity,
    ModuleTarget,
    StepStatus,
    ToolDefinition,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_session(**kwargs) -> AgentSession:
    """Helper to create a session with overrides."""
    defaults = {
        "brand_id": "brand-1",
        "goal": "Test goal",
        "autonomy_level": AutonomyLevel.AUTONOMOUS,
    }
    defaults.update(kwargs)
    return AgentSession.start(**defaults)


def _sample_tools() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition(
            module=ModuleTarget.PULSE,
            name="run_monitoring",
            description="Run monitoring",
            input_schema=(("brand_id", "string", "Brand", True),),
        ),
        ToolDefinition(
            module=ModuleTarget.INTELLIGENCE,
            name="calculate_avs",
            description="Calculate AVS",
            input_schema=(("brand_id", "string", "Brand", True),),
        ),
    )


# ---------------------------------------------------------------------------
# GuardrailService
# ---------------------------------------------------------------------------


class TestGuardrailService:
    """Tests for the GuardrailService."""

    def test_allowed_action_passes(self) -> None:
        session = _make_session()
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)
        session = session.begin_cycle()

        action = AgentAction(
            module=ModuleTarget.PULSE,
            tool_name="run_monitoring",
        )
        allowed, reason = GuardrailService.validate_action(action, session)
        assert allowed is True
        assert reason == ""

    def test_disallowed_module_blocked(self) -> None:
        session = _make_session(
            guardrails=Guardrails(
                allowed_modules=(ModuleTarget.PULSE,),
            ),
        )
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)
        session = session.begin_cycle()

        action = AgentAction(
            module=ModuleTarget.BEAM,
            tool_name="score_content",
        )
        allowed, reason = GuardrailService.validate_action(action, session)
        assert allowed is False
        assert "not in allowed_modules" in reason

    def test_blocked_tool_rejected(self) -> None:
        session = _make_session(
            guardrails=Guardrails(
                blocked_tools=("pulse__run_monitoring",),
            ),
        )
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)
        session = session.begin_cycle()

        action = AgentAction(
            module=ModuleTarget.PULSE,
            tool_name="run_monitoring",
        )
        allowed, reason = GuardrailService.validate_action(action, session)
        assert allowed is False
        assert "blocked by guardrails" in reason

    def test_total_action_limit_enforced(self) -> None:
        session = _make_session(
            guardrails=Guardrails(max_total_actions=1),
        )
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)
        session = session.begin_cycle()

        # Record one action to hit the limit
        action1 = AgentAction(
            module=ModuleTarget.PULSE,
            tool_name="run_monitoring",
            status=ActionStatus.SUCCEEDED,
        )
        session = session.record_action(action1)

        # Next action should be blocked
        action2 = AgentAction(
            module=ModuleTarget.INTELLIGENCE,
            tool_name="calculate_avs",
        )
        allowed, reason = GuardrailService.validate_action(action2, session)
        assert allowed is False
        assert "Total action limit" in reason

    def test_can_continue_terminal_state(self) -> None:
        session = _make_session()
        session = session.mark_complete()
        can, reason = GuardrailService.can_continue(session)
        assert can is False
        assert "terminal state" in reason

    def test_can_continue_max_cycles(self) -> None:
        session = _make_session(guardrails=Guardrails(max_cycles=1))
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)
        session = session.begin_cycle()
        session = session.complete_cycle("Done", ())
        can, reason = GuardrailService.can_continue(session)
        assert can is False
        assert "Max cycles" in reason


# ---------------------------------------------------------------------------
# PlanAnalysisService
# ---------------------------------------------------------------------------


class TestPlanAnalysisService:
    """Tests for the PlanAnalysisService."""

    def test_valid_plan_passes(self) -> None:
        steps = (
            PlanStep(
                module=ModuleTarget.PULSE,
                tool_name="run_monitoring",
                description="Monitor",
            ),
        )
        valid, issues = PlanAnalysisService.validate_plan_steps(
            steps, _sample_tools(), Guardrails(),
        )
        assert valid is True
        assert issues == []

    def test_unknown_tool_flagged(self) -> None:
        steps = (
            PlanStep(
                module=ModuleTarget.PULSE,
                tool_name="nonexistent_tool",
                description="Bad tool",
            ),
        )
        valid, issues = PlanAnalysisService.validate_plan_steps(
            steps, _sample_tools(), Guardrails(),
        )
        assert valid is False
        assert any("unknown tool" in i for i in issues)

    def test_disallowed_module_flagged(self) -> None:
        steps = (
            PlanStep(
                module=ModuleTarget.BEAM,
                tool_name="score_content",
                description="Score",
            ),
        )
        guardrails = Guardrails(allowed_modules=(ModuleTarget.PULSE,))
        valid, issues = PlanAnalysisService.validate_plan_steps(
            steps, _sample_tools(), guardrails,
        )
        assert valid is False
        assert any("disallowed module" in i for i in issues)

    def test_no_cycle_detected_in_linear_plan(self) -> None:
        steps = (
            PlanStep(id="s1", tool_name="t1"),
            PlanStep(id="s2", tool_name="t2", depends_on=("s1",)),
            PlanStep(id="s3", tool_name="t3", depends_on=("s2",)),
        )
        assert PlanAnalysisService.detect_cycles(steps) is False

    def test_cycle_detected(self) -> None:
        steps = (
            PlanStep(id="s1", tool_name="t1", depends_on=("s2",)),
            PlanStep(id="s2", tool_name="t2", depends_on=("s1",)),
        )
        assert PlanAnalysisService.detect_cycles(steps) is True

    def test_self_cycle_detected(self) -> None:
        steps = (
            PlanStep(id="s1", tool_name="t1", depends_on=("s1",)),
        )
        assert PlanAnalysisService.detect_cycles(steps) is True


# ---------------------------------------------------------------------------
# InsightAggregationService
# ---------------------------------------------------------------------------


class TestInsightAggregationService:
    """Tests for the InsightAggregationService."""

    def test_rank_by_severity_then_confidence(self) -> None:
        insights = (
            AgentInsight(severity=InsightSeverity.INFO, confidence=0.9, finding="A"),
            AgentInsight(severity=InsightSeverity.CRITICAL, confidence=0.7, finding="B"),
            AgentInsight(severity=InsightSeverity.WARNING, confidence=0.8, finding="C"),
            AgentInsight(severity=InsightSeverity.CRITICAL, confidence=0.9, finding="D"),
        )
        ranked = InsightAggregationService.rank_insights(insights)
        assert ranked[0].finding == "D"  # critical, 0.9
        assert ranked[1].finding == "B"  # critical, 0.7
        assert ranked[2].finding == "C"  # warning, 0.8
        assert ranked[3].finding == "A"  # info, 0.9

    def test_summarize_by_module(self) -> None:
        insights = (
            AgentInsight(source_module=ModuleTarget.PULSE, finding="A"),
            AgentInsight(source_module=ModuleTarget.PULSE, finding="B"),
            AgentInsight(source_module=ModuleTarget.BEAM, finding="C"),
        )
        by_module = InsightAggregationService.summarize_by_module(insights)
        assert len(by_module["pulse"]) == 2
        assert len(by_module["beam"]) == 1

    def test_critical_count(self) -> None:
        insights = (
            AgentInsight(severity=InsightSeverity.CRITICAL, finding="A"),
            AgentInsight(severity=InsightSeverity.INFO, finding="B"),
            AgentInsight(severity=InsightSeverity.CRITICAL, finding="C"),
        )
        assert InsightAggregationService.critical_count(insights) == 2


# ---------------------------------------------------------------------------
# CycleMetricsService
# ---------------------------------------------------------------------------


class TestCycleMetricsService:
    """Tests for the CycleMetricsService."""

    def test_success_rate_all_succeeded(self) -> None:
        cycle = ExecutionCycle(
            actions=(
                AgentAction(status=ActionStatus.SUCCEEDED, tool_name="t1"),
                AgentAction(status=ActionStatus.SUCCEEDED, tool_name="t2"),
            ),
        )
        assert CycleMetricsService.success_rate(cycle) == pytest.approx(1.0)

    def test_success_rate_mixed(self) -> None:
        cycle = ExecutionCycle(
            actions=(
                AgentAction(status=ActionStatus.SUCCEEDED, tool_name="t1"),
                AgentAction(status=ActionStatus.FAILED, tool_name="t2"),
            ),
        )
        assert CycleMetricsService.success_rate(cycle) == pytest.approx(0.5)

    def test_success_rate_empty_cycle(self) -> None:
        cycle = ExecutionCycle()
        assert CycleMetricsService.success_rate(cycle) == 1.0

    def test_average_action_duration(self) -> None:
        cycle = ExecutionCycle(
            actions=(
                AgentAction(tool_name="t1", duration_ms=100),
                AgentAction(tool_name="t2", duration_ms=200),
                AgentAction(tool_name="t3", duration_ms=300),
            ),
        )
        assert CycleMetricsService.average_action_duration_ms(cycle) == pytest.approx(200.0)

    def test_modules_touched(self) -> None:
        session = _make_session()
        plan = AgentPlan(steps=(), rationale="Test")
        session = session.set_plan(plan)
        session = session.begin_cycle()

        session = session.record_action(
            AgentAction(module=ModuleTarget.PULSE, tool_name="t1", status=ActionStatus.SUCCEEDED)
        )
        session = session.record_action(
            AgentAction(module=ModuleTarget.BEAM, tool_name="t2", status=ActionStatus.SUCCEEDED)
        )
        session = session.record_action(
            AgentAction(module=ModuleTarget.PULSE, tool_name="t3", status=ActionStatus.SUCCEEDED)
        )

        modules = CycleMetricsService.modules_touched(session)
        assert modules == {"pulse", "beam"}
