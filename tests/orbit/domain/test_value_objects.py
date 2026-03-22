"""
Tests for ORBIT Domain Value Objects

Verifies:
- AutonomyLevel properties and approval requirements
- AgentContext invariant validation
- Guardrails invariant validation
- ToolDefinition qualified naming
- InsightSeverity ordering
"""

from __future__ import annotations

import pytest

from lumina.orbit.domain.value_objects import (
    AgentContext,
    AutonomyLevel,
    Guardrails,
    InsightSeverity,
    ModuleTarget,
    ToolDefinition,
)


class TestAutonomyLevel:
    """Tests for the AutonomyLevel enum."""

    def test_supervised_requires_both_approvals(self) -> None:
        assert AutonomyLevel.SUPERVISED.requires_plan_approval is True
        assert AutonomyLevel.SUPERVISED.requires_action_approval is True

    def test_guided_requires_plan_approval_only(self) -> None:
        assert AutonomyLevel.GUIDED.requires_plan_approval is True
        assert AutonomyLevel.GUIDED.requires_action_approval is False

    def test_autonomous_requires_no_approval(self) -> None:
        assert AutonomyLevel.AUTONOMOUS.requires_plan_approval is False
        assert AutonomyLevel.AUTONOMOUS.requires_action_approval is False

    def test_values_are_strings(self) -> None:
        assert AutonomyLevel.SUPERVISED.value == "supervised"
        assert AutonomyLevel.GUIDED.value == "guided"
        assert AutonomyLevel.AUTONOMOUS.value == "autonomous"


class TestAgentContext:
    """Tests for the AgentContext value object."""

    def test_valid_context(self) -> None:
        ctx = AgentContext(
            brand_id="brand-1",
            brand_name="Acme Corp",
            current_avs=72.5,
            focus_areas=("citations", "entity gaps"),
        )
        assert ctx.brand_id == "brand-1"
        assert ctx.brand_name == "Acme Corp"
        assert ctx.current_avs == 72.5
        assert len(ctx.focus_areas) == 2

    def test_empty_brand_id_raises(self) -> None:
        with pytest.raises(ValueError, match="brand_id cannot be empty"):
            AgentContext(brand_id="")

    def test_whitespace_brand_id_raises(self) -> None:
        with pytest.raises(ValueError, match="brand_id cannot be empty"):
            AgentContext(brand_id="   ")

    def test_invalid_avs_raises(self) -> None:
        with pytest.raises(ValueError, match="current_avs must be between"):
            AgentContext(brand_id="brand-1", current_avs=150.0)

    def test_invalid_max_actions_raises(self) -> None:
        with pytest.raises(ValueError, match="max_actions_per_cycle must be >= 1"):
            AgentContext(brand_id="brand-1", max_actions_per_cycle=0)

    def test_none_avs_is_allowed(self) -> None:
        ctx = AgentContext(brand_id="brand-1", current_avs=None)
        assert ctx.current_avs is None

    def test_is_frozen(self) -> None:
        ctx = AgentContext(brand_id="brand-1")
        with pytest.raises(AttributeError):
            ctx.brand_id = "brand-2"  # type: ignore[misc]


class TestGuardrails:
    """Tests for the Guardrails value object."""

    def test_defaults(self) -> None:
        g = Guardrails()
        assert g.max_cycles == 5
        assert g.max_actions_per_cycle == 10
        assert g.max_total_actions == 30
        assert len(g.allowed_modules) == 6

    def test_invalid_max_cycles_raises(self) -> None:
        with pytest.raises(ValueError, match="max_cycles must be >= 1"):
            Guardrails(max_cycles=0)

    def test_invalid_max_actions_per_cycle_raises(self) -> None:
        with pytest.raises(ValueError, match="max_actions_per_cycle must be >= 1"):
            Guardrails(max_actions_per_cycle=0)

    def test_invalid_max_total_actions_raises(self) -> None:
        with pytest.raises(ValueError, match="max_total_actions must be >= 1"):
            Guardrails(max_total_actions=0)

    def test_custom_allowed_modules(self) -> None:
        g = Guardrails(allowed_modules=(ModuleTarget.PULSE, ModuleTarget.BEAM))
        assert len(g.allowed_modules) == 2

    def test_is_frozen(self) -> None:
        g = Guardrails()
        with pytest.raises(AttributeError):
            g.max_cycles = 99  # type: ignore[misc]


class TestToolDefinition:
    """Tests for the ToolDefinition value object."""

    def test_qualified_name(self) -> None:
        tool = ToolDefinition(
            module=ModuleTarget.PULSE,
            name="run_monitoring",
            description="Run monitoring",
            input_schema=(("brand_id", "string", "Brand", True),),
        )
        assert tool.qualified_name == "pulse__run_monitoring"

    def test_is_frozen(self) -> None:
        tool = ToolDefinition(
            module=ModuleTarget.GRAPH,
            name="run_gap_analysis",
            description="Analyse gaps",
            input_schema=(),
        )
        with pytest.raises(AttributeError):
            tool.name = "changed"  # type: ignore[misc]


class TestInsightSeverity:
    """Tests for the InsightSeverity enum."""

    def test_numeric_ordering(self) -> None:
        assert InsightSeverity.INFO.numeric < InsightSeverity.WARNING.numeric
        assert InsightSeverity.WARNING.numeric < InsightSeverity.CRITICAL.numeric

    def test_numeric_values(self) -> None:
        assert InsightSeverity.INFO.numeric == 1
        assert InsightSeverity.WARNING.numeric == 2
        assert InsightSeverity.CRITICAL.numeric == 3
