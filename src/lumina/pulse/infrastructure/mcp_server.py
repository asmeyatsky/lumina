"""
PULSE MCP Server — Model Context Protocol server for the PULSE bounded context

Architectural Intent:
- Exposes PULSE capabilities as MCP tools and resources
- One MCP server per bounded context (PULSE boundary)
- Tools map to application commands; resources map to queries
- No domain logic in this layer — pure orchestration
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

from lumina.shared.ports.ai_engine import AIEnginePort
from lumina.shared.ports.event_bus import EventBusPort

from lumina.pulse.application.commands import (
    CreatePromptBatteryCommand,
    RunMonitoringCommand,
)
from lumina.pulse.application.queries import (
    GetCitationTrendsQuery,
    GetMonitoringRunQuery,
    GetShareOfVoiceQuery,
)
from lumina.pulse.domain.ports import PulseRepositoryPort

logger = logging.getLogger(__name__)


def create_pulse_mcp_server(
    repository: PulseRepositoryPort,
    event_bus: EventBusPort,
    engines: list[AIEnginePort],
) -> Server:
    """Create and configure the PULSE MCP server.

    Args:
        repository: The persistence port for PULSE aggregates.
        event_bus: The domain event bus for publishing events.
        engines: List of AI engine adapters to query.

    Returns:
        Configured MCP Server ready to be run.
    """
    server = Server("lumina-pulse")

    # -- Tool listing -------------------------------------------------------

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="run_monitoring",
                description=(
                    "Execute a full monitoring run for a brand using a specified "
                    "prompt battery. Queries all configured AI engines in parallel, "
                    "extracts citations, analyzes sentiment, and saves results."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "battery_id": {
                            "type": "string",
                            "description": "ID of the prompt battery to execute",
                        },
                        "brand_name": {
                            "type": "string",
                            "description": "Name of the brand to monitor",
                        },
                        "competitors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of competitor brand names",
                            "default": [],
                        },
                    },
                    "required": ["battery_id", "brand_name"],
                },
            ),
            Tool(
                name="create_prompt_battery",
                description=(
                    "Create a new prompt battery for a brand. A battery is a "
                    "collection of prompt templates that are executed together "
                    "during monitoring runs."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {
                            "type": "string",
                            "description": "ID of the brand this battery belongs to",
                        },
                        "name": {
                            "type": "string",
                            "description": "Human-readable name for the battery",
                        },
                        "prompts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "category": {"type": "string"},
                                    "intent_tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["text", "category"],
                            },
                            "description": "List of prompt templates",
                        },
                        "vertical": {
                            "type": "string",
                            "description": "Industry vertical (e.g., fintech, healthcare)",
                        },
                        "schedule_cron": {
                            "type": "string",
                            "description": "Cron expression for scheduled execution",
                        },
                    },
                    "required": [
                        "brand_id",
                        "name",
                        "prompts",
                        "vertical",
                        "schedule_cron",
                    ],
                },
            ),
        ]

    # -- Tool execution ------------------------------------------------------

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "run_monitoring":
            return await _handle_run_monitoring(arguments)
        elif name == "create_prompt_battery":
            return await _handle_create_prompt_battery(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _handle_run_monitoring(
        arguments: dict[str, Any],
    ) -> list[TextContent]:
        battery_id = arguments["battery_id"]
        brand_name = arguments["brand_name"]
        competitors = tuple(arguments.get("competitors", []))

        command = RunMonitoringCommand(
            repository=repository,
            event_bus=event_bus,
            engines=engines,
            brand_name=brand_name,
            competitors=competitors,
        )

        try:
            run = await command.execute(battery_id)
            result = {
                "run_id": run.id,
                "status": run.status.value,
                "brand_id": run.brand_id.value,
                "battery_id": run.battery_id,
                "started_at": run.started_at.isoformat(),
                "completed_at": (
                    run.completed_at.isoformat() if run.completed_at else None
                ),
                "total_results": len(run.results),
                "total_citations": sum(
                    len(r.citations)
                    for r in run.results
                ),
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as exc:
            logger.exception("run_monitoring failed")
            return [TextContent(type="text", text=f"Error: {exc}")]

    async def _handle_create_prompt_battery(
        arguments: dict[str, Any],
    ) -> list[TextContent]:
        command = CreatePromptBatteryCommand(repository=repository)

        try:
            battery = await command.execute(
                brand_id=arguments["brand_id"],
                name=arguments["name"],
                prompts=arguments["prompts"],
                vertical=arguments["vertical"],
                schedule_cron=arguments["schedule_cron"],
            )
            result = {
                "battery_id": battery.id,
                "brand_id": battery.brand_id.value,
                "name": battery.name,
                "prompt_count": len(battery.prompts),
                "vertical": battery.vertical,
                "schedule_cron": battery.schedule_cron,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as exc:
            logger.exception("create_prompt_battery failed")
            return [TextContent(type="text", text=f"Error: {exc}")]

    # -- Resource listing ----------------------------------------------------

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="pulse://runs/{run_id}",
                name="Monitoring Run Details",
                description="Get detailed results of a specific monitoring run",
                mimeType="application/json",
            ),
            Resource(
                uri="pulse://brands/{brand_id}/trends",
                name="Citation Trends",
                description="Get citation trend data for a brand",
                mimeType="application/json",
            ),
            Resource(
                uri="pulse://brands/{brand_id}/share-of-voice",
                name="Share of Voice",
                description="Get share of voice data for a brand vs competitors",
                mimeType="application/json",
            ),
        ]

    # -- Resource reading ----------------------------------------------------

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        uri_str = str(uri)

        if uri_str.startswith("pulse://runs/"):
            run_id = uri_str.removeprefix("pulse://runs/")
            return await _read_run_resource(run_id)
        elif uri_str.endswith("/trends"):
            # pulse://brands/{brand_id}/trends
            parts = uri_str.removeprefix("pulse://brands/").split("/")
            brand_id = parts[0]
            return await _read_trends_resource(brand_id)
        elif uri_str.endswith("/share-of-voice"):
            # pulse://brands/{brand_id}/share-of-voice
            parts = uri_str.removeprefix("pulse://brands/").split("/")
            brand_id = parts[0]
            return await _read_sov_resource(brand_id)
        else:
            return json.dumps({"error": f"Unknown resource: {uri_str}"})

    async def _read_run_resource(run_id: str) -> str:
        query = GetMonitoringRunQuery(repository=repository)
        run = await query.execute(run_id)
        if run is None:
            return json.dumps({"error": f"Run {run_id} not found"})

        return json.dumps(
            {
                "run_id": run.id,
                "brand_id": run.brand_id.value,
                "battery_id": run.battery_id,
                "status": run.status.value,
                "started_at": run.started_at.isoformat(),
                "completed_at": (
                    run.completed_at.isoformat() if run.completed_at else None
                ),
                "result_count": len(run.results),
                "results": [
                    {
                        "id": r.id,
                        "engine": r.engine.value,
                        "prompt_text": r.prompt_text,
                        "citation_count": len(r.citations),
                        "sentiment": r.sentiment.value,
                        "latency_ms": r.response_latency_ms,
                    }
                    for r in run.results
                ],
            },
            indent=2,
        )

    async def _read_trends_resource(brand_id: str) -> str:
        query = GetCitationTrendsQuery(repository=repository)
        now = datetime.now(UTC)
        # Default to last 30 days
        from datetime import timedelta

        period_start = now - timedelta(days=30)
        trend = await query.execute(brand_id, period_start, now)

        return json.dumps(
            {
                "brand_id": trend.brand_id.value,
                "period_start": trend.period_start.isoformat(),
                "period_end": trend.period_end.isoformat(),
                "citation_frequency": trend.citation_frequency.value,
                "avg_position": trend.avg_position,
                "sentiment_breakdown": trend.sentiment_breakdown,
            },
            indent=2,
        )

    async def _read_sov_resource(brand_id: str) -> str:
        query = GetShareOfVoiceQuery(repository=repository)
        benchmark = await query.execute(brand_id, [])

        sov_data: dict[str, Any] = {}
        for key, sov in benchmark.share_of_voice_map.items():
            sov_data[key] = {
                "citation_count": sov.citation_count,
                "total_citations": sov.total_citations,
                "percentage": sov.percentage.value,
            }

        return json.dumps(
            {
                "brand_id": benchmark.brand_id.value,
                "competitors": [c.value for c in benchmark.competitor_brand_ids],
                "share_of_voice": sov_data,
            },
            indent=2,
        )

    return server


async def run_pulse_server(
    repository: PulseRepositoryPort,
    event_bus: EventBusPort,
    engines: list[AIEnginePort],
) -> None:
    """Start the PULSE MCP server using stdio transport."""
    server = create_pulse_mcp_server(repository, event_bus, engines)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)
