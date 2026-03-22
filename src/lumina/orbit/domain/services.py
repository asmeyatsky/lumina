"""
ORBIT Pure Domain Services

Architectural Intent:
- Stateless, pure functions encapsulating domain logic
- No I/O, no side effects — only domain computations
- Operate exclusively on domain entities and value objects
"""

from __future__ import annotations

from lumina.orbit.domain.entities import (
    AgentAction,
    AgentInsight,
    AgentSession,
    ExecutionCycle,
    PlanStep,
)
from lumina.orbit.domain.value_objects import (
    ActionStatus,
    Guardrails,
    InsightSeverity,
    ModuleTarget,
    StepStatus,
    ToolDefinition,
)


class GuardrailService:
    """Enforces safety constraints on agent actions.

    All checks are pure — no I/O. Guardrails prevent the agent from
    exceeding configured limits or touching forbidden modules/tools.
    """

    @staticmethod
    def validate_action(
        action: AgentAction,
        session: AgentSession,
    ) -> tuple[bool, str]:
        """Validate whether an action is permitted under the session's guardrails.

        Returns:
            (is_allowed, reason) — reason is empty if allowed, describes violation otherwise.
        """
        guardrails = session.guardrails

        # Check module is allowed
        if action.module not in guardrails.allowed_modules:
            return False, f"Module {action.module.value} is not in allowed_modules"

        # Check tool is not blocked
        qualified = f"{action.module.value}__{action.tool_name}"
        if qualified in guardrails.blocked_tools or action.tool_name in guardrails.blocked_tools:
            return False, f"Tool {qualified} is blocked by guardrails"

        # Check total action limit
        if session.total_actions >= guardrails.max_total_actions:
            return False, (
                f"Total action limit reached: "
                f"{session.total_actions}/{guardrails.max_total_actions}"
            )

        # Check per-cycle action limit
        current_cycle = session.current_cycle
        if current_cycle is not None:
            if current_cycle.action_count >= guardrails.max_actions_per_cycle:
                return False, (
                    f"Per-cycle action limit reached: "
                    f"{current_cycle.action_count}/{guardrails.max_actions_per_cycle}"
                )

        return True, ""

    @staticmethod
    def can_continue(session: AgentSession) -> tuple[bool, str]:
        """Check whether the session can continue executing.

        Returns:
            (can_continue, reason)
        """
        if session.is_terminal:
            return False, f"Session is in terminal state: {session.state.value}"

        if session.cycle_count >= session.guardrails.max_cycles:
            return False, (
                f"Max cycles reached: "
                f"{session.cycle_count}/{session.guardrails.max_cycles}"
            )

        if session.total_actions >= session.guardrails.max_total_actions:
            return False, (
                f"Max total actions reached: "
                f"{session.total_actions}/{session.guardrails.max_total_actions}"
            )

        return True, ""


class PlanAnalysisService:
    """Analyses and validates execution plans."""

    @staticmethod
    def validate_plan_steps(
        steps: tuple[PlanStep, ...],
        available_tools: tuple[ToolDefinition, ...],
        guardrails: Guardrails,
    ) -> tuple[bool, list[str]]:
        """Validate that all plan steps reference valid, allowed tools.

        Returns:
            (is_valid, list_of_issues)
        """
        issues: list[str] = []

        # Build lookup of available tools
        tool_lookup: set[str] = set()
        for tool in available_tools:
            tool_lookup.add(f"{tool.module.value}__{tool.name}")

        # Build lookup of allowed modules
        allowed_modules = {m.value for m in guardrails.allowed_modules}

        for step in steps:
            # Check module is allowed
            if step.module.value not in allowed_modules:
                issues.append(
                    f"Step '{step.description}' targets disallowed module: {step.module.value}"
                )

            # Check tool exists
            qualified = f"{step.module.value}__{step.tool_name}"
            if qualified not in tool_lookup:
                issues.append(
                    f"Step '{step.description}' references unknown tool: {qualified}"
                )

            # Check dependencies reference valid step IDs
            step_ids = {s.id for s in steps}
            for dep in step.depends_on:
                if dep not in step_ids:
                    issues.append(
                        f"Step '{step.description}' depends on unknown step ID: {dep}"
                    )

        # Check total steps don't exceed action limit
        if len(steps) > guardrails.max_total_actions:
            issues.append(
                f"Plan has {len(steps)} steps, exceeding max_total_actions ({guardrails.max_total_actions})"
            )

        return len(issues) == 0, issues

    @staticmethod
    def detect_cycles(steps: tuple[PlanStep, ...]) -> bool:
        """Detect circular dependencies in plan steps.

        Returns True if a cycle is detected (invalid).
        """
        step_ids = {s.id for s in steps}
        dep_map: dict[str, tuple[str, ...]] = {s.id: s.depends_on for s in steps}

        visited: set[str] = set()
        in_stack: set[str] = set()

        def dfs(node: str) -> bool:
            if node in in_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            in_stack.add(node)
            for dep in dep_map.get(node, ()):
                if dep in step_ids and dfs(dep):
                    return True
            in_stack.discard(node)
            return False

        for sid in step_ids:
            if dfs(sid):
                return True
        return False


class InsightAggregationService:
    """Aggregates and ranks insights across cycles."""

    @staticmethod
    def rank_insights(insights: tuple[AgentInsight, ...]) -> list[AgentInsight]:
        """Rank insights by severity (critical first) then confidence (highest first).

        Returns:
            A sorted list of insights.
        """
        return sorted(
            insights,
            key=lambda i: (-i.severity.numeric, -i.confidence),
        )

    @staticmethod
    def summarize_by_module(
        insights: tuple[AgentInsight, ...],
    ) -> dict[str, list[AgentInsight]]:
        """Group insights by source module."""
        by_module: dict[str, list[AgentInsight]] = {}
        for insight in insights:
            key = insight.source_module.value
            by_module.setdefault(key, []).append(insight)
        return by_module

    @staticmethod
    def critical_count(insights: tuple[AgentInsight, ...]) -> int:
        """Count insights with critical severity."""
        return sum(1 for i in insights if i.severity == InsightSeverity.CRITICAL)


class CycleMetricsService:
    """Computes metrics from execution cycles."""

    @staticmethod
    def success_rate(cycle: ExecutionCycle) -> float:
        """Fraction of actions that succeeded in a cycle."""
        if not cycle.actions:
            return 1.0
        succeeded = sum(1 for a in cycle.actions if a.status == ActionStatus.SUCCEEDED)
        return succeeded / len(cycle.actions)

    @staticmethod
    def average_action_duration_ms(cycle: ExecutionCycle) -> float:
        """Average duration of actions in a cycle (milliseconds)."""
        completed = [a for a in cycle.actions if a.duration_ms > 0]
        if not completed:
            return 0.0
        return sum(a.duration_ms for a in completed) / len(completed)

    @staticmethod
    def modules_touched(session: AgentSession) -> set[str]:
        """Set of module names touched across all cycles."""
        modules: set[str] = set()
        for cycle in session.cycles:
            for action in cycle.actions:
                modules.add(action.module.value)
        return modules
