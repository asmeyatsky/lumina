"""
Intelligence Engine MCP Server

Architectural Intent:
- Exposes Intelligence Engine capabilities as an MCP (Model Context Protocol) server
- Tools map to application-layer commands
- Resources provide read-only access to domain state
- One MCP server per bounded context
"""

from __future__ import annotations

import json
from datetime import datetime, UTC
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

from lumina.shared.domain.value_objects import BrandId

from lumina.intelligence.application.commands import (
    CalculateAVSCommand,
    GenerateRecommendationsCommand,
    RunRootCauseAnalysisCommand,
)
from lumina.intelligence.application.queries import (
    GetAVSQuery,
    GetAVSTrendsQuery,
    GetRecommendationQueueQuery,
)
from lumina.intelligence.domain.ports import IntelligenceRepositoryPort, ModuleScorePort
from lumina.shared.ports.event_bus import EventBusPort


def create_intelligence_mcp_server(
    repository: IntelligenceRepositoryPort,
    module_scores: ModuleScorePort,
    event_bus: EventBusPort,
) -> Server:
    """Create and configure the Intelligence Engine MCP server.

    Args:
        repository: The Intelligence repository adapter.
        module_scores: The module score fetching adapter.
        event_bus: The event bus adapter.

    Returns:
        A configured MCP Server instance.
    """
    server = Server("lumina-intelligence")

    # --- Tool definitions ---

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="calculate_avs",
                description=(
                    "Calculate the AI Visibility Score for a brand by fetching scores "
                    "from all four LUMINA modules (PULSE, GRAPH, BEAM, SIGNAL) and "
                    "computing a weighted composite score."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {
                            "type": "string",
                            "description": "The unique identifier for the brand.",
                        },
                    },
                    "required": ["brand_id"],
                },
            ),
            Tool(
                name="run_root_cause_analysis",
                description=(
                    "Analyse why the AVS changed significantly by comparing current "
                    "and previous module scores and correlating with external signals."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {
                            "type": "string",
                            "description": "The unique identifier for the brand.",
                        },
                        "current_scores": {
                            "type": "object",
                            "description": "Current module scores (module_name -> value).",
                        },
                        "previous_scores": {
                            "type": "object",
                            "description": "Previous module scores (module_name -> value).",
                        },
                        "external_signals": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "External context signals.",
                        },
                    },
                    "required": ["brand_id", "current_scores", "previous_scores"],
                },
            ),
            Tool(
                name="generate_recommendations",
                description=(
                    "Generate and prioritise actionable recommendations to improve "
                    "the brand's AI Visibility Score."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {
                            "type": "string",
                            "description": "The unique identifier for the brand.",
                        },
                        "gaps": {
                            "type": "array",
                            "description": "Knowledge gaps from GRAPH module.",
                        },
                        "content_scores": {
                            "type": "array",
                            "description": "Content scoring data from BEAM module.",
                        },
                        "coverage": {
                            "type": "object",
                            "description": "Distribution coverage from SIGNAL module.",
                        },
                    },
                    "required": ["brand_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        brand_id = BrandId(arguments["brand_id"])

        if name == "calculate_avs":
            command = CalculateAVSCommand(
                repository=repository,
                module_scores=module_scores,
                event_bus=event_bus,
            )
            await command.execute(brand_id)

            query = GetAVSQuery(repository=repository)
            avs = await query.execute(brand_id)

            result = {
                "brand_id": avs.brand_id,
                "overall_score": avs.overall.value,
                "components": [
                    {
                        "module": c.module_name,
                        "score": c.score.value,
                        "weight": c.weight,
                        "weighted_score": c.weighted_score,
                    }
                    for c in avs.components
                ],
                "delta": avs.calculate_delta(),
                "calculated_at": avs.calculated_at.isoformat(),
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "run_root_cause_analysis":
            command = RunRootCauseAnalysisCommand(
                repository=repository,
                event_bus=event_bus,
            )
            rca = await command.execute(
                brand_id=brand_id,
                current_scores=arguments["current_scores"],
                previous_scores=arguments["previous_scores"],
                external_signals=arguments.get("external_signals", []),
            )

            result = {
                "brand_id": rca.brand_id,
                "trigger": rca.trigger,
                "causes": [
                    {
                        "factor": c.factor,
                        "module": c.module,
                        "evidence": c.evidence,
                        "contribution_weight": c.contribution_weight,
                    }
                    for c in rca.causes
                ],
                "recommended_actions": list(rca.recommended_actions),
                "analyzed_at": rca.analyzed_at.isoformat(),
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "generate_recommendations":
            command = GenerateRecommendationsCommand(
                repository=repository,
                event_bus=event_bus,
            )
            recommendations = await command.execute(
                brand_id=brand_id,
                gaps=arguments.get("gaps", []),
                content_scores=arguments.get("content_scores", []),
                coverage=arguments.get("coverage", {}),
            )

            result = {
                "brand_id": brand_id.value,
                "recommendations": [
                    {
                        "id": r.id,
                        "source_module": r.source_module,
                        "action": r.action_description,
                        "expected_avs_impact": r.expected_avs_impact.value,
                        "effort_level": r.effort_level.value,
                        "priority_rank": r.priority_rank,
                    }
                    for r in recommendations
                ],
                "count": len(recommendations),
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        raise ValueError(f"Unknown tool: {name}")

    # --- Resource definitions ---

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="intelligence://brands/{brand_id}/avs",
                name="AI Visibility Score",
                description="Current AI Visibility Score for a brand.",
                mimeType="application/json",
            ),
            Resource(
                uri="intelligence://brands/{brand_id}/recommendations",
                name="Recommendation Queue",
                description="Prioritised recommendation queue for a brand.",
                mimeType="application/json",
            ),
            Resource(
                uri="intelligence://brands/{brand_id}/trends",
                name="AVS Trends",
                description="AI Visibility Score trend data for a brand.",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        parts = str(uri).split("/")
        # Expected format: intelligence://brands/{brand_id}/{resource_type}
        # After split: ['intelligence:', '', 'brands', '{brand_id}', '{resource_type}']
        if len(parts) < 5 or parts[2] != "brands":
            raise ValueError(f"Invalid resource URI: {uri}")

        brand_id = BrandId(parts[3])
        resource_type = parts[4]

        if resource_type == "avs":
            query = GetAVSQuery(repository=repository)
            avs = await query.execute(brand_id)
            result = {
                "brand_id": avs.brand_id,
                "overall_score": avs.overall.value,
                "components": [
                    {
                        "module": c.module_name,
                        "score": c.score.value,
                        "weight": c.weight,
                    }
                    for c in avs.components
                ],
                "calculated_at": avs.calculated_at.isoformat(),
            }
            return json.dumps(result, indent=2)

        elif resource_type == "recommendations":
            query = GetRecommendationQueueQuery(repository=repository)
            recs = await query.execute(brand_id)
            result = {
                "brand_id": brand_id.value,
                "recommendations": [
                    {
                        "id": r.id,
                        "source_module": r.source_module,
                        "action": r.action_description,
                        "expected_avs_impact": r.expected_avs_impact.value,
                        "effort_level": r.effort_level.value,
                        "priority_rank": r.priority_rank,
                    }
                    for r in recs
                ],
            }
            return json.dumps(result, indent=2)

        elif resource_type == "trends":
            query = GetAVSTrendsQuery(repository=repository)
            trend = await query.execute(brand_id)
            result = {
                "brand_id": trend.brand_id,
                "period": trend.period,
                "trend_direction": trend.trend_direction,
                "change_rate": trend.change_rate,
                "data_points": len(trend.scores),
            }
            return json.dumps(result, indent=2)

        raise ValueError(f"Unknown resource type: {resource_type}")

    return server


async def run_intelligence_mcp_server(
    repository: IntelligenceRepositoryPort,
    module_scores: ModuleScorePort,
    event_bus: EventBusPort,
) -> None:
    """Start the Intelligence Engine MCP server over stdio."""
    server = create_intelligence_mcp_server(repository, module_scores, event_bus)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
