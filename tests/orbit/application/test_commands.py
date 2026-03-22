"""
Tests for ORBIT Application Commands

Verifies:
- StartSessionCommand creates session, generates plan, validates, persists
- RunCycleCommand executes actions and synthesizes
- ApprovePlanCommand transitions state
- PauseSessionCommand and ResumeSessionCommand lifecycle
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, UTC

from lumina.orbit.application.commands import (
    ApprovePlanCommand,
    PauseSessionCommand,
    ResumeSessionCommand,
    RunCycleCommand,
    StartSessionCommand,
)
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
    AutonomyLevel,
    Guardrails,
    InsightSeverity,
    ModuleTarget,
    SessionState,
    ToolDefinition,
)
from lumina.presentation.config.dependency_injection import (
    InMemoryEventBus,
    InMemoryOrbitRepository,
)


# ---------------------------------------------------------------------------
# Mock adapters
# ---------------------------------------------------------------------------


class MockAgentEngine:
    """Mock agent engine for testing."""

    def __init__(self) -> None:
        self.plan_calls: int = 0
        self.decide_calls: int = 0
        self.synthesize_calls: int = 0
        self.eval_calls: int = 0
        self._goal_complete = False

    async def create_plan(self, goal, context, available_tools) -> AgentPlan:
        self.plan_calls += 1
        return AgentPlan(
            steps=(
                PlanStep(
                    module=ModuleTarget.INTELLIGENCE,
                    tool_name="calculate_avs",
                    description="Calculate baseline AVS",
                    arguments_json=json.dumps({"brand_id": context.brand_id}),
                ),
            ),
            rationale="Start with AVS baseline",
        )

    async def decide_next_actions(self, session, available_tools, observations):
        self.decide_calls += 1
        return (
            AgentAction(
                module=ModuleTarget.INTELLIGENCE,
                tool_name="calculate_avs",
                arguments_json=json.dumps({"brand_id": session.brand_id}),
            ),
        )

    async def synthesize(self, session, actions_results):
        self.synthesize_calls += 1
        insight = AgentInsight(
            severity=InsightSeverity.INFO,
            confidence=0.8,
            finding="AVS calculated successfully",
            source_module=ModuleTarget.INTELLIGENCE,
        )
        return "Cycle synthesis: baseline AVS established", (insight,)

    async def evaluate_goal_completion(self, session):
        self.eval_calls += 1
        # Complete after first cycle
        self._goal_complete = True
        return True, "Goal achieved"


class MockModuleBridge:
    """Mock module bridge for testing."""

    def __init__(self) -> None:
        self.call_log: list[tuple[str, str]] = []

    async def call_tool(self, module, tool_name, arguments):
        self.call_log.append((module.value, tool_name))
        return json.dumps({"status": "ok", "module": module.value, "tool": tool_name})

    async def list_tools(self):
        return (
            ToolDefinition(
                module=ModuleTarget.INTELLIGENCE,
                name="calculate_avs",
                description="Calculate AVS",
                input_schema=(("brand_id", "string", "Brand", True),),
            ),
            ToolDefinition(
                module=ModuleTarget.PULSE,
                name="run_monitoring",
                description="Monitor",
                input_schema=(("brand_id", "string", "Brand", True),),
            ),
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def repository() -> InMemoryOrbitRepository:
    return InMemoryOrbitRepository()


@pytest.fixture
def agent_engine() -> MockAgentEngine:
    return MockAgentEngine()


@pytest.fixture
def module_bridge() -> MockModuleBridge:
    return MockModuleBridge()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStartSessionCommand:
    """Tests for the StartSessionCommand."""

    async def test_creates_session_with_plan(
        self,
        repository: InMemoryOrbitRepository,
        agent_engine: MockAgentEngine,
        module_bridge: MockModuleBridge,
        event_bus: InMemoryEventBus,
    ) -> None:
        command = StartSessionCommand(
            repository=repository,
            agent_engine=agent_engine,
            module_bridge=module_bridge,
            event_bus=event_bus,
        )

        session = await command.execute(
            brand_id="brand-1",
            goal="Diagnose citation drop",
            autonomy_level=AutonomyLevel.GUIDED,
        )

        assert session.brand_id == "brand-1"
        assert session.goal == "Diagnose citation drop"
        assert session.plan is not None
        assert len(session.plan.steps) == 1
        assert session.state == SessionState.AWAITING_APPROVAL
        assert agent_engine.plan_calls == 1

        # Verify persisted
        stored = await repository.get_session(session.id)
        assert stored is not None
        assert stored.id == session.id

    async def test_autonomous_session_goes_directly_to_executing(
        self,
        repository: InMemoryOrbitRepository,
        agent_engine: MockAgentEngine,
        module_bridge: MockModuleBridge,
        event_bus: InMemoryEventBus,
    ) -> None:
        command = StartSessionCommand(
            repository=repository,
            agent_engine=agent_engine,
            module_bridge=module_bridge,
            event_bus=event_bus,
        )

        session = await command.execute(
            brand_id="brand-1",
            goal="Full audit",
            autonomy_level=AutonomyLevel.AUTONOMOUS,
        )

        assert session.state == SessionState.EXECUTING

    async def test_publishes_events(
        self,
        repository: InMemoryOrbitRepository,
        agent_engine: MockAgentEngine,
        module_bridge: MockModuleBridge,
        event_bus: InMemoryEventBus,
    ) -> None:
        command = StartSessionCommand(
            repository=repository,
            agent_engine=agent_engine,
            module_bridge=module_bridge,
            event_bus=event_bus,
        )

        await command.execute(brand_id="brand-1", goal="Test")

        assert len(event_bus.published_events) > 0


class TestApprovePlanCommand:
    """Tests for the ApprovePlanCommand."""

    async def test_approve_transitions_to_executing(
        self,
        repository: InMemoryOrbitRepository,
        agent_engine: MockAgentEngine,
        module_bridge: MockModuleBridge,
        event_bus: InMemoryEventBus,
    ) -> None:
        # Create session in awaiting_approval state
        start_cmd = StartSessionCommand(
            repository=repository,
            agent_engine=agent_engine,
            module_bridge=module_bridge,
            event_bus=event_bus,
        )
        session = await start_cmd.execute(
            brand_id="brand-1",
            goal="Test",
            autonomy_level=AutonomyLevel.GUIDED,
        )
        assert session.state == SessionState.AWAITING_APPROVAL

        # Approve
        approve_cmd = ApprovePlanCommand(
            repository=repository,
            event_bus=event_bus,
        )
        session = await approve_cmd.execute(session.id)
        assert session.state == SessionState.EXECUTING


class TestRunCycleCommand:
    """Tests for the RunCycleCommand."""

    async def test_executes_cycle_and_synthesizes(
        self,
        repository: InMemoryOrbitRepository,
        agent_engine: MockAgentEngine,
        module_bridge: MockModuleBridge,
        event_bus: InMemoryEventBus,
    ) -> None:
        # Create and approve session
        start_cmd = StartSessionCommand(
            repository=repository,
            agent_engine=agent_engine,
            module_bridge=module_bridge,
            event_bus=event_bus,
        )
        session = await start_cmd.execute(
            brand_id="brand-1",
            goal="Calculate AVS",
            autonomy_level=AutonomyLevel.AUTONOMOUS,
        )

        # Run cycle
        cycle_cmd = RunCycleCommand(
            repository=repository,
            agent_engine=agent_engine,
            module_bridge=module_bridge,
            event_bus=event_bus,
        )
        session = await cycle_cmd.execute(session.id)

        assert session.cycle_count == 1
        assert session.total_actions >= 1
        assert agent_engine.decide_calls == 1
        assert agent_engine.synthesize_calls == 1
        assert agent_engine.eval_calls == 1

        # Module bridge was called
        assert len(module_bridge.call_log) >= 1

        # Goal achieved after first cycle (mock engine says so)
        assert session.state == SessionState.COMPLETE

    async def test_nonexistent_session_raises(
        self,
        repository: InMemoryOrbitRepository,
        agent_engine: MockAgentEngine,
        module_bridge: MockModuleBridge,
        event_bus: InMemoryEventBus,
    ) -> None:
        from lumina.shared.domain.errors import EntityNotFoundError

        cycle_cmd = RunCycleCommand(
            repository=repository,
            agent_engine=agent_engine,
            module_bridge=module_bridge,
            event_bus=event_bus,
        )
        with pytest.raises(EntityNotFoundError):
            await cycle_cmd.execute("nonexistent-id")


class TestPauseResumeCommands:
    """Tests for pause and resume commands."""

    async def test_pause_and_resume(
        self,
        repository: InMemoryOrbitRepository,
        agent_engine: MockAgentEngine,
        module_bridge: MockModuleBridge,
        event_bus: InMemoryEventBus,
    ) -> None:
        # Create session
        start_cmd = StartSessionCommand(
            repository=repository,
            agent_engine=agent_engine,
            module_bridge=module_bridge,
            event_bus=event_bus,
        )
        session = await start_cmd.execute(
            brand_id="brand-1",
            goal="Test",
            autonomy_level=AutonomyLevel.AUTONOMOUS,
        )

        # Pause
        pause_cmd = PauseSessionCommand(repository=repository)
        session = await pause_cmd.execute(session.id)
        assert session.state == SessionState.PAUSED

        # Resume
        resume_cmd = ResumeSessionCommand(repository=repository)
        session = await resume_cmd.execute(session.id)
        assert session.state == SessionState.EXECUTING
