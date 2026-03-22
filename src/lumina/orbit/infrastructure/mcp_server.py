"""
ORBIT MCP Server — Model Context Protocol server for the Autonomous Agent context

Architectural Intent:
- Exposes ORBIT capabilities as an MCP server (7th LUMINA MCP server)
- Tools: start_session, run_cycle, run_full_session, approve_plan, pause, resume
- Resources: session state, insights, metrics
- One MCP server per bounded context
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

from lumina.shared.ports.event_bus import EventBusPort

from lumina.orbit.application.commands import (
    ApprovePlanCommand,
    PauseSessionCommand,
    ResumeSessionCommand,
    RunCycleCommand,
    RunFullSessionCommand,
    StartSessionCommand,
)
from lumina.orbit.application.queries import (
    GetActiveSessionQuery,
    GetInsightsQuery,
    GetSessionMetricsQuery,
    GetSessionQuery,
)
from lumina.orbit.domain.ports import (
    AgentEnginePort,
    ModuleBridgePort,
    OrbitRepositoryPort,
)
from lumina.orbit.domain.value_objects import (
    AgentContext,
    AutonomyLevel,
    Guardrails,
)


def create_orbit_mcp_server(
    repository: OrbitRepositoryPort,
    agent_engine: AgentEnginePort,
    module_bridge: ModuleBridgePort,
    event_bus: EventBusPort,
) -> Server:
    """Create and configure the ORBIT MCP server.

    Args:
        repository: The ORBIT repository adapter.
        agent_engine: The Claude agent engine adapter.
        module_bridge: The module bridge adapter.
        event_bus: The event bus adapter.

    Returns:
        A configured MCP Server instance.
    """
    server = Server("lumina-orbit")

    # -- Tool definitions ---------------------------------------------------

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="start_session",
                description=(
                    "Start an autonomous ORBIT session for a brand. The agent will "
                    "plan how to achieve the stated goal using LUMINA's module tools, "
                    "then optionally await approval before executing."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {
                            "type": "string",
                            "description": "The brand to operate on.",
                        },
                        "goal": {
                            "type": "string",
                            "description": (
                                "Natural language description of what to achieve. "
                                "Example: 'Diagnose why our GPT-4o citation rate dropped 15% this week'"
                            ),
                        },
                        "autonomy_level": {
                            "type": "string",
                            "enum": ["supervised", "guided", "autonomous"],
                            "description": (
                                "How much human oversight: supervised (approve every action), "
                                "guided (approve plan only), autonomous (full auto within guardrails)."
                            ),
                        },
                        "brand_name": {
                            "type": "string",
                            "description": "Display name of the brand (optional).",
                        },
                        "focus_areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional focus areas to guide the agent.",
                        },
                        "max_cycles": {
                            "type": "integer",
                            "description": "Maximum execution cycles (default 5).",
                        },
                    },
                    "required": ["brand_id", "goal"],
                },
            ),
            Tool(
                name="run_cycle",
                description=(
                    "Execute a single observe-plan-act-synthesize cycle on an active session."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The session to run a cycle on.",
                        },
                    },
                    "required": ["session_id"],
                },
            ),
            Tool(
                name="run_full_session",
                description=(
                    "Run the complete autonomous loop — cycles repeat until the goal "
                    "is met or guardrails halt execution."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The session to run to completion.",
                        },
                    },
                    "required": ["session_id"],
                },
            ),
            Tool(
                name="approve_plan",
                description="Approve the agent's plan to allow execution to proceed.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The session whose plan to approve.",
                        },
                    },
                    "required": ["session_id"],
                },
            ),
            Tool(
                name="pause_session",
                description="Pause an active session for manual review.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                },
            ),
            Tool(
                name="resume_session",
                description="Resume a paused session.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:

        if name == "start_session":
            brand_id = arguments["brand_id"]
            goal = arguments["goal"]
            autonomy = AutonomyLevel(arguments.get("autonomy_level", "guided"))

            context = AgentContext(
                brand_id=brand_id,
                brand_name=arguments.get("brand_name", ""),
                focus_areas=tuple(arguments.get("focus_areas", [])),
            )
            guardrails = Guardrails(
                max_cycles=arguments.get("max_cycles", 5),
            )

            command = StartSessionCommand(
                repository=repository,
                agent_engine=agent_engine,
                module_bridge=module_bridge,
                event_bus=event_bus,
            )
            session = await command.execute(
                brand_id=brand_id,
                goal=goal,
                autonomy_level=autonomy,
                context=context,
                guardrails=guardrails,
            )

            result = _serialize_session_summary(session)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "run_cycle":
            command = RunCycleCommand(
                repository=repository,
                agent_engine=agent_engine,
                module_bridge=module_bridge,
                event_bus=event_bus,
            )
            session = await command.execute(arguments["session_id"])
            result = _serialize_session_summary(session)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "run_full_session":
            command = RunFullSessionCommand(
                repository=repository,
                agent_engine=agent_engine,
                module_bridge=module_bridge,
                event_bus=event_bus,
            )
            session = await command.execute(arguments["session_id"])
            result = _serialize_session_summary(session)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "approve_plan":
            command = ApprovePlanCommand(
                repository=repository,
                event_bus=event_bus,
            )
            session = await command.execute(arguments["session_id"])
            result = _serialize_session_summary(session)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "pause_session":
            command = PauseSessionCommand(repository=repository)
            session = await command.execute(arguments["session_id"])
            result = _serialize_session_summary(session)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "resume_session":
            command = ResumeSessionCommand(repository=repository)
            session = await command.execute(arguments["session_id"])
            result = _serialize_session_summary(session)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        raise ValueError(f"Unknown tool: {name}")

    # -- Resource definitions -----------------------------------------------

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="orbit://sessions/{session_id}",
                name="Agent Session",
                description="Full state of an autonomous agent session.",
                mimeType="application/json",
            ),
            Resource(
                uri="orbit://sessions/{session_id}/insights",
                name="Session Insights",
                description="Ranked insights generated during a session.",
                mimeType="application/json",
            ),
            Resource(
                uri="orbit://sessions/{session_id}/metrics",
                name="Session Metrics",
                description="Aggregate metrics for a session.",
                mimeType="application/json",
            ),
            Resource(
                uri="orbit://brands/{brand_id}/active",
                name="Active Session",
                description="Currently active session for a brand.",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        parts = str(uri).split("/")

        if len(parts) >= 4 and parts[2] == "sessions":
            session_id = parts[3]

            if len(parts) == 4:
                query = GetSessionQuery(repository=repository)
                session = await query.execute(session_id)
                return json.dumps(_serialize_session_full(session), indent=2)

            resource_type = parts[4] if len(parts) > 4 else ""

            if resource_type == "insights":
                query = GetInsightsQuery(repository=repository)
                insights = await query.execute(session_id)
                result = {
                    "session_id": session_id,
                    "insights": [
                        {
                            "severity": i.severity.value,
                            "confidence": i.confidence,
                            "finding": i.finding,
                            "evidence": i.evidence,
                            "recommended_action": i.recommended_action,
                            "source_module": i.source_module.value,
                        }
                        for i in insights
                    ],
                }
                return json.dumps(result, indent=2)

            elif resource_type == "metrics":
                query = GetSessionMetricsQuery(repository=repository)
                metrics = await query.execute(session_id)
                return json.dumps(metrics, indent=2)

        elif len(parts) >= 5 and parts[2] == "brands" and parts[4] == "active":
            brand_id = parts[3]
            query = GetActiveSessionQuery(repository=repository)
            session = await query.execute(brand_id)
            if session is None:
                return json.dumps({"active_session": None})
            return json.dumps(_serialize_session_summary(session), indent=2)

        raise ValueError(f"Unknown resource URI: {uri}")

    return server


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialize_session_summary(session) -> dict:
    """Compact session summary for tool responses."""
    result: dict[str, Any] = {
        "session_id": session.id,
        "brand_id": session.brand_id,
        "goal": session.goal,
        "state": session.state.value,
        "autonomy_level": session.autonomy_level.value,
        "cycle_count": session.cycle_count,
        "total_actions": session.total_actions,
        "insight_count": len(session.all_insights),
        "created_at": session.created_at.isoformat(),
    }
    if session.plan:
        result["plan"] = {
            "rationale": session.plan.rationale,
            "step_count": len(session.plan.steps),
            "progress": round(session.plan.progress_fraction, 2),
        }
    if session.completed_at:
        result["completed_at"] = session.completed_at.isoformat()
    if session.failure_reason:
        result["failure_reason"] = session.failure_reason
    return result


def _serialize_session_full(session) -> dict:
    """Full session serialisation for resource reads."""
    result = _serialize_session_summary(session)

    if session.plan:
        result["plan"]["steps"] = [
            {
                "id": s.id,
                "module": s.module.value,
                "tool": s.tool_name,
                "description": s.description,
                "status": s.status.value,
                "result_summary": s.result_summary,
            }
            for s in session.plan.steps
        ]

    result["cycles"] = [
        {
            "cycle_number": c.cycle_number,
            "phase": c.phase.value,
            "action_count": c.action_count,
            "succeeded": len(c.succeeded_actions),
            "failed": len(c.failed_actions),
            "synthesis": c.synthesis,
            "insight_count": len(c.insights),
            "started_at": c.started_at.isoformat(),
            "completed_at": c.completed_at.isoformat() if c.completed_at else None,
        }
        for c in session.cycles
    ]

    result["insights"] = [
        {
            "severity": i.severity.value,
            "confidence": i.confidence,
            "finding": i.finding,
            "recommended_action": i.recommended_action,
            "source_module": i.source_module.value,
        }
        for i in session.all_insights
    ]

    return result


async def run_orbit_mcp_server(
    repository: OrbitRepositoryPort,
    agent_engine: AgentEnginePort,
    module_bridge: ModuleBridgePort,
    event_bus: EventBusPort,
) -> None:
    """Start the ORBIT MCP server over stdio."""
    server = create_orbit_mcp_server(repository, agent_engine, module_bridge, event_bus)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
