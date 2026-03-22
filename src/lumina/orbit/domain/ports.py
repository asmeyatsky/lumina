"""
ORBIT Ports (Protocol Interfaces)

Architectural Intent:
- Ports define the contracts the domain requires from the outside world
- Protocol-based (structural subtyping) — no inheritance required
- Infrastructure layer provides concrete adapters
"""

from __future__ import annotations

from typing import Protocol

from lumina.orbit.domain.entities import (
    AgentAction,
    AgentInsight,
    AgentPlan,
    AgentSession,
)
from lumina.orbit.domain.value_objects import (
    AgentContext,
    ModuleTarget,
    ToolDefinition,
)


class OrbitRepositoryPort(Protocol):
    """Port for persisting and retrieving ORBIT session aggregates."""

    async def save_session(self, session: AgentSession) -> None:
        """Persist an agent session (upsert)."""
        ...

    async def get_session(self, session_id: str) -> AgentSession | None:
        """Retrieve a session by ID."""
        ...

    async def get_sessions_for_brand(
        self, brand_id: str, limit: int = 20
    ) -> list[AgentSession]:
        """Retrieve sessions for a brand, most recent first."""
        ...

    async def get_active_session(self, brand_id: str) -> AgentSession | None:
        """Retrieve the currently active (non-terminal) session for a brand."""
        ...


class AgentEnginePort(Protocol):
    """Port for the AI reasoning engine that powers the agent.

    The agent engine is responsible for planning, deciding actions,
    and synthesizing insights. The implementation uses Claude via
    the Anthropic SDK with tool-use to reason over LUMINA's capabilities.
    """

    async def create_plan(
        self,
        goal: str,
        context: AgentContext,
        available_tools: tuple[ToolDefinition, ...],
    ) -> AgentPlan:
        """Generate an execution plan for the given goal.

        Args:
            goal: Natural language description of what to achieve.
            context: Brand context including current state and focus areas.
            available_tools: Tools the agent can use from LUMINA modules.

        Returns:
            An AgentPlan with ordered steps.
        """
        ...

    async def decide_next_actions(
        self,
        session: AgentSession,
        available_tools: tuple[ToolDefinition, ...],
        observations: tuple[str, ...],
    ) -> tuple[AgentAction, ...]:
        """Decide what actions to take next based on session state.

        The engine analyses the current session state, prior cycle results,
        and fresh observations to determine the optimal next actions.

        Args:
            session: The current session state.
            available_tools: Tools available from LUMINA modules.
            observations: Fresh observations from the current cycle.

        Returns:
            Tuple of actions to execute (may be empty if goal is met).
        """
        ...

    async def synthesize(
        self,
        session: AgentSession,
        actions_results: tuple[AgentAction, ...],
    ) -> tuple[str, tuple[AgentInsight, ...]]:
        """Synthesize findings from executed actions.

        Analyses the results of actions taken in the current cycle and
        produces a narrative synthesis and structured insights.

        Args:
            session: The current session state.
            actions_results: The completed actions with their results.

        Returns:
            A tuple of (synthesis_text, insights).
        """
        ...

    async def evaluate_goal_completion(
        self,
        session: AgentSession,
    ) -> tuple[bool, str]:
        """Determine whether the session goal has been achieved.

        Args:
            session: The current session state with all cycles.

        Returns:
            A tuple of (is_complete, reasoning).
        """
        ...


class ModuleBridgePort(Protocol):
    """Port for executing tool calls against LUMINA modules.

    The module bridge is the adapter that routes agent tool calls
    to the appropriate LUMINA MCP server or application command.
    """

    async def call_tool(
        self,
        module: ModuleTarget,
        tool_name: str,
        arguments: dict[str, object],
    ) -> str:
        """Execute a tool call on a LUMINA module.

        Args:
            module: The target module (PULSE, GRAPH, BEAM, etc.).
            tool_name: The tool to call within that module.
            arguments: The tool arguments.

        Returns:
            JSON string containing the tool result.

        Raises:
            ValueError: If the module or tool is not found.
        """
        ...

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        """List all available tools across all LUMINA modules."""
        ...
