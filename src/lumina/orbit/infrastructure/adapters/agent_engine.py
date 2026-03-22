"""
Claude Agent Engine — Anthropic SDK adapter implementing AgentEnginePort

Architectural Intent:
- Uses Claude via the Anthropic SDK as the reasoning engine for ORBIT
- Translates LUMINA tool definitions into Claude tool-use schemas
- Runs multi-turn reasoning loops to plan, decide, and synthesize
- Pure infrastructure adapter — no domain logic
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import datetime, UTC
from uuid import uuid4

from lumina.orbit.domain.entities import (
    AgentAction,
    AgentInsight,
    AgentPlan,
    AgentSession,
    PlanStep,
)
from lumina.orbit.domain.value_objects import (
    ActionStatus,
    AgentContext,
    InsightSeverity,
    ModuleTarget,
    StepStatus,
    ToolDefinition,
)

logger = logging.getLogger(__name__)

# System prompt for the ORBIT agent
ORBIT_SYSTEM_PROMPT = """\
You are ORBIT, the autonomous AI Visibility agent for the LUMINA platform.
Your role is to orchestrate LUMINA's module tools to monitor, diagnose, optimise,
and defend a brand's visibility across AI answer engines (Claude, GPT-4o, Gemini, Perplexity).

LUMINA Modules:
- PULSE: Citation monitoring — runs AI engine queries, extracts citations and sentiment
- GRAPH: Entity intelligence — manages the brand's knowledge graph across 8 dimensions
- BEAM: Content optimisation — scores content for AI retrieval using 6-factor GEO model
- SIGNAL: Distribution — plans and executes content distribution to AI-crawled surfaces
- INTELLIGENCE: Unified scoring — calculates the AI Visibility Score (AVS) and root causes
- AGENCY: White-label — manages multi-client reporting and branding

You operate in observe-plan-act-synthesize cycles. In each cycle:
1. OBSERVE: Analyse the current state and prior results
2. PLAN: Decide which tools to call and in what order
3. ACT: Execute tool calls against LUMINA modules
4. SYNTHESIZE: Distil findings into actionable insights

Be precise, data-driven, and action-oriented. Always explain your reasoning.
When you identify issues, recommend specific corrective actions.
"""


def _build_tool_schemas(tools: tuple[ToolDefinition, ...]) -> list[dict]:
    """Convert LUMINA ToolDefinitions to Anthropic tool-use format."""
    schemas = []
    for tool in tools:
        properties: dict = {}
        required: list[str] = []
        for param_name, param_type, param_desc, param_required in tool.input_schema:
            properties[param_name] = {
                "type": param_type,
                "description": param_desc,
            }
            if param_required:
                required.append(param_name)

        schemas.append({
            "name": tool.qualified_name,
            "description": f"[{tool.module.value.upper()}] {tool.description}",
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        })
    return schemas


def _parse_plan_from_text(text: str) -> tuple[tuple[PlanStep, ...], str]:
    """Parse structured plan from the agent's text response.

    Expects JSON with keys 'rationale' and 'steps' where each step has
    'module', 'tool', 'description', and optional 'depends_on'.
    Falls back to a single-step plan if parsing fails.
    """
    try:
        # Try to extract JSON from the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            rationale = data.get("rationale", "")
            steps: list[PlanStep] = []
            step_ids: dict[int, str] = {}

            for i, step_data in enumerate(data.get("steps", [])):
                step_id = str(uuid4())
                step_ids[i] = step_id

                module_str = step_data.get("module", "intelligence")
                try:
                    module = ModuleTarget(module_str)
                except ValueError:
                    module = ModuleTarget.INTELLIGENCE

                depends_on_indices = step_data.get("depends_on", [])
                depends_on = tuple(
                    step_ids[idx] for idx in depends_on_indices if idx in step_ids
                )

                steps.append(PlanStep(
                    id=step_id,
                    module=module,
                    tool_name=step_data.get("tool", ""),
                    description=step_data.get("description", ""),
                    arguments_json=json.dumps(step_data.get("arguments", {})),
                    depends_on=depends_on,
                ))

            return tuple(steps), rationale
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    # Fallback: single step
    return (
        PlanStep(
            module=ModuleTarget.INTELLIGENCE,
            tool_name="calculate_avs",
            description="Calculate current AI Visibility Score as baseline",
        ),
    ), "Fallback: starting with AVS calculation"


def _parse_actions_from_text(
    text: str,
    available_tools: tuple[ToolDefinition, ...],
) -> tuple[AgentAction, ...]:
    """Parse planned actions from agent engine response."""
    try:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            actions: list[AgentAction] = []
            for action_data in data:
                module_str = action_data.get("module", "intelligence")
                try:
                    module = ModuleTarget(module_str)
                except ValueError:
                    module = ModuleTarget.INTELLIGENCE

                actions.append(AgentAction(
                    module=module,
                    tool_name=action_data.get("tool", ""),
                    arguments_json=json.dumps(action_data.get("arguments", {})),
                ))
            return tuple(actions)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return ()


def _parse_insights_from_text(text: str) -> tuple[AgentInsight, ...]:
    """Parse insights from the synthesis response."""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            insights: list[AgentInsight] = []
            for insight_data in data.get("insights", []):
                severity_str = insight_data.get("severity", "info")
                try:
                    severity = InsightSeverity(severity_str)
                except ValueError:
                    severity = InsightSeverity.INFO

                module_str = insight_data.get("source_module", "intelligence")
                try:
                    source_module = ModuleTarget(module_str)
                except ValueError:
                    source_module = ModuleTarget.INTELLIGENCE

                insights.append(AgentInsight(
                    severity=severity,
                    confidence=float(insight_data.get("confidence", 0.5)),
                    finding=insight_data.get("finding", ""),
                    evidence=insight_data.get("evidence", ""),
                    recommended_action=insight_data.get("recommended_action", ""),
                    source_module=source_module,
                ))
            return tuple(insights)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    return ()


class ClaudeAgentEngine:
    """Agent engine powered by Claude via the Anthropic SDK.

    Uses Claude's tool-use capability to reason about which LUMINA tools
    to call and in what order. The agent engine is stateless — all state
    is carried in the AgentSession aggregate.

    Args:
        api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
        model: Claude model to use for reasoning.
        max_tokens: Maximum tokens per reasoning call.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._client = None  # Lazy init

    def _get_client(self):
        """Lazy-init the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            except ImportError:
                logger.warning("anthropic SDK not installed — using mock engine")
                return None
        return self._client

    async def create_plan(
        self,
        goal: str,
        context: AgentContext,
        available_tools: tuple[ToolDefinition, ...],
    ) -> AgentPlan:
        """Generate an execution plan using Claude."""
        client = self._get_client()

        planning_prompt = (
            f"Goal: {goal}\n\n"
            f"Brand: {context.brand_name or context.brand_id}\n"
            f"Current AVS: {context.current_avs or 'unknown'}\n"
            f"Previous AVS: {context.previous_avs or 'unknown'}\n"
            f"Known issues: {', '.join(context.known_issues) or 'none'}\n"
            f"Focus areas: {', '.join(context.focus_areas) or 'none'}\n\n"
            "Available tools:\n"
        )
        for tool in available_tools:
            planning_prompt += f"  - {tool.qualified_name}: {tool.description}\n"

        planning_prompt += (
            "\nCreate a plan to achieve this goal. Respond with JSON:\n"
            "{\n"
            '  "rationale": "why this plan makes sense",\n'
            '  "steps": [\n'
            "    {\n"
            '      "module": "module_name",\n'
            '      "tool": "tool_name",\n'
            '      "description": "what this step does",\n'
            '      "arguments": {"key": "value"},\n'
            '      "depends_on": [0, 1]  // indices of prior steps\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        if client is not None:
            try:
                response = await client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=ORBIT_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": planning_prompt}],
                )
                text = response.content[0].text
                steps, rationale = _parse_plan_from_text(text)
            except Exception as exc:
                logger.error("Claude planning call failed: %s", exc)
                steps, rationale = _build_fallback_plan(goal, context, available_tools)
        else:
            steps, rationale = _build_fallback_plan(goal, context, available_tools)

        return AgentPlan(steps=steps, rationale=rationale)

    async def decide_next_actions(
        self,
        session: AgentSession,
        available_tools: tuple[ToolDefinition, ...],
        observations: tuple[str, ...],
    ) -> tuple[AgentAction, ...]:
        """Use Claude to decide next actions based on session state."""
        client = self._get_client()

        decision_prompt = (
            f"Session goal: {session.goal}\n"
            f"Brand: {session.brand_id}\n"
            f"Cycle: {session.cycle_count}\n"
            f"Total actions so far: {session.total_actions}\n\n"
            "Observations:\n"
        )
        for obs in observations:
            decision_prompt += f"  - {obs}\n"

        if session.plan:
            decision_prompt += "\nPlan progress:\n"
            for step in session.plan.steps:
                decision_prompt += (
                    f"  [{step.status.value}] {step.module.value}/{step.tool_name}: "
                    f"{step.description}\n"
                )

        decision_prompt += (
            "\nDecide what actions to take next. Respond with a JSON array:\n"
            "[\n"
            "  {\n"
            '    "module": "module_name",\n'
            '    "tool": "tool_name",\n'
            '    "arguments": {"key": "value"}\n'
            "  }\n"
            "]\n"
            "Return an empty array [] if the goal is already met."
        )

        if client is not None:
            try:
                response = await client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=ORBIT_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": decision_prompt}],
                )
                text = response.content[0].text
                return _parse_actions_from_text(text, available_tools)
            except Exception as exc:
                logger.error("Claude decide call failed: %s", exc)

        # Fallback: execute next ready steps from plan
        return _actions_from_plan(session, available_tools)

    async def synthesize(
        self,
        session: AgentSession,
        actions_results: tuple[AgentAction, ...],
    ) -> tuple[str, tuple[AgentInsight, ...]]:
        """Use Claude to synthesize findings from action results."""
        client = self._get_client()

        synthesis_prompt = (
            f"Session goal: {session.goal}\n"
            f"Brand: {session.brand_id}\n"
            f"Cycle: {session.cycle_count}\n\n"
            "Actions executed this cycle:\n"
        )
        for action in actions_results:
            status = action.status.value
            synthesis_prompt += (
                f"  [{status}] {action.module.value}/{action.tool_name} "
                f"({action.duration_ms}ms)\n"
            )
            if action.status == ActionStatus.SUCCEEDED and action.result_json:
                # Truncate long results
                result_preview = action.result_json[:500]
                synthesis_prompt += f"    Result: {result_preview}\n"
            elif action.status == ActionStatus.FAILED:
                synthesis_prompt += f"    Error: {action.error_message}\n"

        synthesis_prompt += (
            "\nSynthesize your findings. Respond with JSON:\n"
            "{\n"
            '  "synthesis": "narrative summary of what was learned",\n'
            '  "insights": [\n'
            "    {\n"
            '      "severity": "info|warning|critical",\n'
            '      "confidence": 0.0-1.0,\n'
            '      "finding": "what was discovered",\n'
            '      "evidence": "data supporting this finding",\n'
            '      "recommended_action": "what to do about it",\n'
            '      "source_module": "module_name"\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        if client is not None:
            try:
                response = await client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=ORBIT_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": synthesis_prompt}],
                )
                text = response.content[0].text
                insights = _parse_insights_from_text(text)

                # Extract synthesis text
                try:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start >= 0 and end > start:
                        data = json.loads(text[start:end])
                        synthesis = data.get("synthesis", text)
                    else:
                        synthesis = text
                except (json.JSONDecodeError, KeyError):
                    synthesis = text

                return synthesis, insights
            except Exception as exc:
                logger.error("Claude synthesis call failed: %s", exc)

        # Fallback synthesis
        succeeded = sum(1 for a in actions_results if a.status == ActionStatus.SUCCEEDED)
        failed = sum(1 for a in actions_results if a.status == ActionStatus.FAILED)
        synthesis = (
            f"Cycle {session.cycle_count}: Executed {len(actions_results)} actions "
            f"({succeeded} succeeded, {failed} failed)."
        )
        return synthesis, ()

    async def evaluate_goal_completion(
        self,
        session: AgentSession,
    ) -> tuple[bool, str]:
        """Use Claude to evaluate whether the goal has been achieved."""
        client = self._get_client()

        eval_prompt = (
            f"Goal: {session.goal}\n"
            f"Cycles completed: {session.cycle_count}\n"
            f"Total actions: {session.total_actions}\n\n"
            "Session insights:\n"
        )
        for insight in session.all_insights[-10:]:
            eval_prompt += f"  [{insight.severity.value}] {insight.finding}\n"

        if session.cycles:
            last_cycle = session.cycles[-1]
            if last_cycle.synthesis:
                eval_prompt += f"\nLatest synthesis: {last_cycle.synthesis}\n"

        eval_prompt += (
            "\nHas the goal been achieved? Respond with JSON:\n"
            '{"complete": true/false, "reasoning": "explanation"}'
        )

        if client is not None:
            try:
                response = await client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    system=ORBIT_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": eval_prompt}],
                )
                text = response.content[0].text
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(text[start:end])
                    return bool(data.get("complete", False)), data.get("reasoning", "")
            except Exception as exc:
                logger.error("Claude eval call failed: %s", exc)

        # Fallback: complete after plan is done or max cycles reached
        if session.plan and session.plan.is_complete:
            return True, "All plan steps completed"
        if session.cycle_count >= session.guardrails.max_cycles:
            return True, "Max cycles reached"
        return False, "Continuing"


# ---------------------------------------------------------------------------
# Fallback helpers (when Anthropic SDK is not available)
# ---------------------------------------------------------------------------


def _build_fallback_plan(
    goal: str,
    context: AgentContext,
    available_tools: tuple[ToolDefinition, ...],
) -> tuple[tuple[PlanStep, ...], str]:
    """Build a sensible default plan without calling Claude.

    Uses a diagnostic-first approach:
    1. Calculate current AVS (baseline)
    2. Run monitoring to check citations
    3. Run gap analysis if entity profile exists
    4. Score key content
    5. Recalculate AVS to measure change
    """
    brand_id = context.brand_id
    steps: list[PlanStep] = []

    # Step 0: Calculate baseline AVS
    step_0_id = str(uuid4())
    steps.append(PlanStep(
        id=step_0_id,
        module=ModuleTarget.INTELLIGENCE,
        tool_name="calculate_avs",
        description="Calculate baseline AI Visibility Score",
        arguments_json=json.dumps({"brand_id": brand_id}),
    ))

    # Step 1: Run monitoring
    step_1_id = str(uuid4())
    steps.append(PlanStep(
        id=step_1_id,
        module=ModuleTarget.PULSE,
        tool_name="run_monitoring",
        description="Run AI engine monitoring to check current citation state",
        arguments_json=json.dumps({"brand_id": brand_id}),
    ))

    # Step 2: Run gap analysis (depends on monitoring)
    step_2_id = str(uuid4())
    steps.append(PlanStep(
        id=step_2_id,
        module=ModuleTarget.GRAPH,
        tool_name="run_gap_analysis",
        description="Analyse entity knowledge gaps",
        arguments_json=json.dumps({"entity_id": brand_id}),
        depends_on=(step_1_id,),
    ))

    # Step 3: Generate recommendations (depends on AVS + gap analysis)
    step_3_id = str(uuid4())
    steps.append(PlanStep(
        id=step_3_id,
        module=ModuleTarget.INTELLIGENCE,
        tool_name="generate_recommendations",
        description="Generate prioritised improvement recommendations",
        arguments_json=json.dumps({"brand_id": brand_id}),
        depends_on=(step_0_id, step_2_id),
    ))

    rationale = (
        "Diagnostic-first approach: establish baseline AVS, monitor current "
        "citation state, identify entity knowledge gaps, then generate "
        "prioritised recommendations for improvement."
    )

    return tuple(steps), rationale


def _actions_from_plan(
    session: AgentSession,
    available_tools: tuple[ToolDefinition, ...],
) -> tuple[AgentAction, ...]:
    """Extract next ready actions from the session's plan."""
    if session.plan is None:
        return ()

    ready = session.plan.ready_steps
    actions: list[AgentAction] = []
    for step in ready[:session.guardrails.max_actions_per_cycle]:
        actions.append(AgentAction(
            module=step.module,
            tool_name=step.tool_name,
            arguments_json=step.arguments_json,
        ))
    return tuple(actions)
