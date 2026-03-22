"""
ORBIT Application Commands (Use Cases)

Architectural Intent:
- Commands orchestrate domain logic and infrastructure interactions
- Each command represents a single write-side use case
- Parallelism-first: independent operations run concurrently via asyncio.gather
- Domain events are published after successful persistence
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, UTC

from lumina.shared.ports.event_bus import EventBusPort

from lumina.orbit.domain.entities import (
    AgentAction,
    AgentInsight,
    AgentSession,
    ExecutionCycle,
)
from lumina.orbit.domain.ports import (
    AgentEnginePort,
    ModuleBridgePort,
    OrbitRepositoryPort,
)
from lumina.orbit.domain.services import GuardrailService, PlanAnalysisService
from lumina.orbit.domain.value_objects import (
    ActionStatus,
    AgentContext,
    AutonomyLevel,
    Guardrails,
    ModuleTarget,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartSessionCommand:
    """Start a new autonomous agent session for a brand.

    Creates the session, asks the agent engine to generate a plan,
    validates the plan against guardrails, and persists the result.
    """

    repository: OrbitRepositoryPort
    agent_engine: AgentEnginePort
    module_bridge: ModuleBridgePort
    event_bus: EventBusPort

    async def execute(
        self,
        brand_id: str,
        goal: str,
        autonomy_level: AutonomyLevel = AutonomyLevel.GUIDED,
        context: AgentContext | None = None,
        guardrails: Guardrails | None = None,
    ) -> AgentSession:
        """Execute the start-session pipeline.

        1. Create session aggregate.
        2. Fetch available tools from module bridge.
        3. Ask agent engine to create a plan.
        4. Validate plan against guardrails.
        5. Attach plan to session.
        6. Persist and publish events.
        """
        effective_context = context or AgentContext(brand_id=brand_id)
        effective_guardrails = guardrails or Guardrails()

        # Create session
        session = AgentSession.start(
            brand_id=brand_id,
            goal=goal,
            autonomy_level=autonomy_level,
            context=effective_context,
            guardrails=effective_guardrails,
        )

        # Fetch available tools
        available_tools = await self.module_bridge.list_tools()

        # Generate plan via agent engine
        plan = await self.agent_engine.create_plan(
            goal=goal,
            context=effective_context,
            available_tools=available_tools,
        )

        # Validate plan
        is_valid, issues = PlanAnalysisService.validate_plan_steps(
            plan.steps, available_tools, effective_guardrails,
        )
        has_cycles = PlanAnalysisService.detect_cycles(plan.steps)

        if not is_valid or has_cycles:
            all_issues = issues + (["Circular dependency detected in plan"] if has_cycles else [])
            logger.warning("Plan validation failed: %s", all_issues)
            session = session.mark_failed(
                f"Plan validation failed: {'; '.join(all_issues)}"
            )
            await self.repository.save_session(session)
            if session.domain_events:
                await self.event_bus.publish(list(session.domain_events))
            return session

        # Attach plan
        session = session.set_plan(plan)

        await self.repository.save_session(session)

        if session.domain_events:
            await self.event_bus.publish(list(session.domain_events))

        return session


@dataclass(frozen=True)
class ApprovePlanCommand:
    """Human approves the agent's plan, allowing execution to proceed."""

    repository: OrbitRepositoryPort
    event_bus: EventBusPort

    async def execute(self, session_id: str) -> AgentSession:
        session = await self.repository.get_session(session_id)
        if session is None:
            from lumina.shared.domain.errors import EntityNotFoundError
            raise EntityNotFoundError(f"Session {session_id} not found")

        session = session.approve_plan()
        await self.repository.save_session(session)

        if session.domain_events:
            await self.event_bus.publish(list(session.domain_events))

        return session


@dataclass(frozen=True)
class RunCycleCommand:
    """Execute a single observe-plan-act-synthesize cycle.

    This is the core autonomous loop. It:
    1. Begins a new cycle on the session.
    2. Asks the agent engine what actions to take.
    3. Validates each action against guardrails.
    4. Executes actions via the module bridge.
    5. Asks the agent engine to synthesize findings.
    6. Completes the cycle.
    7. Evaluates whether the goal has been met.
    """

    repository: OrbitRepositoryPort
    agent_engine: AgentEnginePort
    module_bridge: ModuleBridgePort
    event_bus: EventBusPort

    async def execute(self, session_id: str) -> AgentSession:
        """Execute one cycle of the autonomous loop."""
        session = await self.repository.get_session(session_id)
        if session is None:
            from lumina.shared.domain.errors import EntityNotFoundError
            raise EntityNotFoundError(f"Session {session_id} not found")

        # Check we can continue
        can_continue, reason = GuardrailService.can_continue(session)
        if not can_continue:
            session = session.mark_failed(f"Guardrail stop: {reason}")
            await self.repository.save_session(session)
            if session.domain_events:
                await self.event_bus.publish(list(session.domain_events))
            return session

        # Begin new cycle
        session = session.begin_cycle()
        available_tools = await self.module_bridge.list_tools()

        # Gather observations from prior cycle results
        observations = self._build_observations(session)

        # Ask agent engine what to do
        planned_actions = await self.agent_engine.decide_next_actions(
            session=session,
            available_tools=available_tools,
            observations=observations,
        )

        # Execute each action through the module bridge
        completed_actions: list[AgentAction] = []
        for action in planned_actions:
            # Guardrail check
            is_allowed, violation = GuardrailService.validate_action(action, session)
            if not is_allowed:
                logger.warning("Action blocked by guardrail: %s", violation)
                failed_action = action.mark_failed(
                    f"Guardrail violation: {violation}",
                    completed_at=datetime.now(UTC),
                    duration_ms=0,
                )
                session = session.record_action(failed_action)
                completed_actions.append(failed_action)
                continue

            # Execute via module bridge
            executed = await self._execute_action(action)
            session = session.record_action(executed)
            completed_actions.append(executed)

        # Synthesize findings
        synthesis, insights = await self.agent_engine.synthesize(
            session=session,
            actions_results=tuple(completed_actions),
        )

        # Complete cycle
        session = session.complete_cycle(synthesis, insights)

        # Evaluate goal completion
        is_complete, completion_reasoning = await self.agent_engine.evaluate_goal_completion(
            session=session,
        )

        if is_complete:
            session = session.mark_complete()

        # Persist
        await self.repository.save_session(session)

        if session.domain_events:
            await self.event_bus.publish(list(session.domain_events))

        return session

    async def _execute_action(self, action: AgentAction) -> AgentAction:
        """Execute a single action and return the updated action with results."""
        start = datetime.now(UTC)
        try:
            arguments = json.loads(action.arguments_json) if action.arguments_json else {}
            result_json = await self.module_bridge.call_tool(
                module=action.module,
                tool_name=action.tool_name,
                arguments=arguments,
            )
            end = datetime.now(UTC)
            duration_ms = int((end - start).total_seconds() * 1000)
            return action.mark_succeeded(
                result_json=result_json,
                completed_at=end,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            end = datetime.now(UTC)
            duration_ms = int((end - start).total_seconds() * 1000)
            return action.mark_failed(
                error_message=str(exc),
                completed_at=end,
                duration_ms=duration_ms,
            )

    @staticmethod
    def _build_observations(session: AgentSession) -> tuple[str, ...]:
        """Build observations from prior cycle results."""
        observations: list[str] = []

        if len(session.cycles) > 1:
            # Summarize previous cycle
            prev = session.cycles[-2]
            if prev.completed_at is not None:
                observations.append(
                    f"Previous cycle {prev.cycle_number}: "
                    f"{len(prev.succeeded_actions)} succeeded, "
                    f"{len(prev.failed_actions)} failed"
                )
                if prev.synthesis:
                    observations.append(f"Prior synthesis: {prev.synthesis}")

        # Include accumulated insights
        for insight in session.insights[-5:]:  # Last 5 insights for context
            observations.append(
                f"[{insight.severity.value}] {insight.finding}"
            )

        return tuple(observations)


@dataclass(frozen=True)
class RunFullSessionCommand:
    """Run the complete autonomous loop until goal is met or guardrails halt execution.

    This is the high-level command that runs multiple cycles in sequence.
    """

    repository: OrbitRepositoryPort
    agent_engine: AgentEnginePort
    module_bridge: ModuleBridgePort
    event_bus: EventBusPort

    async def execute(self, session_id: str) -> AgentSession:
        """Run cycles until the session reaches a terminal state."""
        run_cycle = RunCycleCommand(
            repository=self.repository,
            agent_engine=self.agent_engine,
            module_bridge=self.module_bridge,
            event_bus=self.event_bus,
        )

        session = await self.repository.get_session(session_id)
        if session is None:
            from lumina.shared.domain.errors import EntityNotFoundError
            raise EntityNotFoundError(f"Session {session_id} not found")

        while not session.is_terminal and session.can_start_cycle:
            session = await run_cycle.execute(session_id)
            # Re-read in case the cycle command persisted updates
            refreshed = await self.repository.get_session(session_id)
            if refreshed is not None:
                session = refreshed

        # If we exited the loop without a terminal state, mark complete
        if not session.is_terminal:
            session = session.mark_complete()
            await self.repository.save_session(session)
            if session.domain_events:
                await self.event_bus.publish(list(session.domain_events))

        return session


@dataclass(frozen=True)
class PauseSessionCommand:
    """Pause an active session for manual review."""

    repository: OrbitRepositoryPort

    async def execute(self, session_id: str) -> AgentSession:
        session = await self.repository.get_session(session_id)
        if session is None:
            from lumina.shared.domain.errors import EntityNotFoundError
            raise EntityNotFoundError(f"Session {session_id} not found")

        session = session.pause()
        await self.repository.save_session(session)
        return session


@dataclass(frozen=True)
class ResumeSessionCommand:
    """Resume a paused session."""

    repository: OrbitRepositoryPort

    async def execute(self, session_id: str) -> AgentSession:
        session = await self.repository.get_session(session_id)
        if session is None:
            from lumina.shared.domain.errors import EntityNotFoundError
            raise EntityNotFoundError(f"Session {session_id} not found")

        session = session.resume()
        await self.repository.save_session(session)
        return session
