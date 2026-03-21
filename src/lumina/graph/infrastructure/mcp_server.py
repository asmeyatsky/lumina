"""
GRAPH MCP Server — Model Context Protocol server for the Entity Intelligence context

Architectural Intent:
- One MCP server per bounded context
- Exposes tools (write operations) and resources (read operations)
- Thin adapter layer — delegates to application commands and queries
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
)

from lumina.shared.domain.value_objects import BrandId
from lumina.shared.ports.event_bus import EventBusPort

from lumina.graph.domain.ports import GraphRepositoryPort
from lumina.graph.domain.value_objects import DimensionType
from lumina.graph.application.commands import (
    CreateEntityProfileCommand,
    DimensionInput,
    UpdateEntityDimensionCommand,
    RunGapAnalysisCommand,
    GenerateJsonLdCommand,
)
from lumina.graph.application.queries import (
    GetEntityProfileQuery,
    GetKnowledgeGapsQuery,
    GetEntityHealthQuery,
)


def create_graph_mcp_server(
    repository: GraphRepositoryPort,
    event_bus: EventBusPort,
) -> Server:
    """Factory that wires the GRAPH MCP server with its dependencies."""

    server = Server("lumina-graph")

    # ------------------------------------------------------------------
    # Tools (write operations)
    # ------------------------------------------------------------------

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="create_entity_profile",
                description="Create a new entity profile for a brand with optional initial dimensions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {"type": "string", "description": "Brand identifier"},
                        "name": {"type": "string", "description": "Entity name"},
                        "description": {"type": "string", "description": "Entity description"},
                        "dimensions": {
                            "type": "array",
                            "description": "Initial dimensions",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dimension_type": {
                                        "type": "string",
                                        "enum": [dt.value for dt in DimensionType],
                                    },
                                    "data": {
                                        "type": "object",
                                        "additionalProperties": {"type": "string"},
                                    },
                                    "completeness_score": {"type": "number"},
                                    "sources": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["dimension_type", "data", "completeness_score"],
                            },
                        },
                    },
                    "required": ["brand_id", "name", "description"],
                },
            ),
            Tool(
                name="update_dimension",
                description="Update a specific dimension on an entity profile",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "profile_id": {"type": "string"},
                        "dimension_id": {"type": "string"},
                        "new_data": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        "new_completeness": {"type": "number"},
                    },
                    "required": ["profile_id", "dimension_id", "new_data"],
                },
            ),
            Tool(
                name="run_gap_analysis",
                description="Analyse entity gaps using AI knowledge data from PULSE",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "profile_id": {"type": "string"},
                        "ai_knowledge": {
                            "type": "object",
                            "description": "Dict mapping dimension type values to known data dicts",
                        },
                    },
                    "required": ["profile_id", "ai_knowledge"],
                },
            ),
            Tool(
                name="generate_json_ld",
                description="Generate JSON-LD structured data for an entity profile",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "profile_id": {"type": "string"},
                    },
                    "required": ["profile_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "create_entity_profile":
            return await _handle_create_profile(arguments)
        elif name == "update_dimension":
            return await _handle_update_dimension(arguments)
        elif name == "run_gap_analysis":
            return await _handle_run_gap_analysis(arguments)
        elif name == "generate_json_ld":
            return await _handle_generate_json_ld(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _handle_create_profile(args: dict[str, Any]) -> list[TextContent]:
        dim_inputs: list[DimensionInput] = []
        for d in args.get("dimensions", []):
            dim_inputs.append(
                DimensionInput(
                    dimension_type=DimensionType(d["dimension_type"]),
                    data=d["data"],
                    completeness_score=d["completeness_score"],
                    sources=tuple(d.get("sources", [])),
                )
            )

        cmd = CreateEntityProfileCommand(repository, event_bus)
        profile = await cmd.execute(
            brand_id=args["brand_id"],
            name=args["name"],
            description=args["description"],
            dimensions=dim_inputs,
        )
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "profile_id": profile.id,
                        "name": profile.name,
                        "health_score": profile.health_score.value,
                        "dimensions_count": len(profile.dimensions),
                    }
                ),
            )
        ]

    async def _handle_update_dimension(args: dict[str, Any]) -> list[TextContent]:
        cmd = UpdateEntityDimensionCommand(repository, event_bus)
        profile = await cmd.execute(
            profile_id=args["profile_id"],
            dimension_id=args["dimension_id"],
            new_data=args["new_data"],
            new_completeness=args.get("new_completeness"),
        )
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "profile_id": profile.id,
                        "health_score": profile.health_score.value,
                    }
                ),
            )
        ]

    async def _handle_run_gap_analysis(args: dict[str, Any]) -> list[TextContent]:
        cmd = RunGapAnalysisCommand(repository, event_bus)
        gaps = await cmd.execute(
            profile_id=args["profile_id"],
            ai_knowledge=args["ai_knowledge"],
        )
        gap_list = [
            {
                "id": g.id,
                "dimension_type": g.dimension_type.value,
                "severity": g.severity.value,
                "description": g.description,
                "recommended_action": g.recommended_action,
            }
            for g in gaps
        ]
        return [TextContent(type="text", text=json.dumps({"gaps": gap_list}))]

    async def _handle_generate_json_ld(args: dict[str, Any]) -> list[TextContent]:
        cmd = GenerateJsonLdCommand(repository)
        documents = await cmd.execute(profile_id=args["profile_id"])
        docs_list = [doc.to_dict() for doc in documents]
        return [TextContent(type="text", text=json.dumps({"documents": docs_list}))]

    # ------------------------------------------------------------------
    # Resources (read operations)
    # ------------------------------------------------------------------

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="graph://profiles/{brand_id}",
                name="Entity Profiles",
                description="All entity profiles for a brand",
                mimeType="application/json",
            ),
            Resource(
                uri="graph://gaps/{brand_id}",
                name="Knowledge Gaps",
                description="Knowledge gaps for a brand, ordered by severity",
                mimeType="application/json",
            ),
            Resource(
                uri="graph://health/{brand_id}",
                name="Entity Health",
                description="Entity health metrics for a brand",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        parts = str(uri).replace("graph://", "").split("/")
        if len(parts) < 2:
            return json.dumps({"error": "Invalid resource URI"})

        resource_type = parts[0]
        brand_id = parts[1]

        if resource_type == "profiles":
            profiles = await repository.list_profiles_for_brand(brand_id)
            return json.dumps(
                [
                    {
                        "id": p.id,
                        "name": p.name,
                        "health_score": p.health_score.value,
                        "dimensions_count": len(p.dimensions),
                    }
                    for p in profiles
                ]
            )
        elif resource_type == "gaps":
            query = GetKnowledgeGapsQuery(repository)
            gaps = await query.execute(brand_id=brand_id)
            return json.dumps(
                [
                    {
                        "id": g.id,
                        "dimension_type": g.dimension_type.value,
                        "severity": g.severity.value,
                        "description": g.description,
                    }
                    for g in gaps
                ]
            )
        elif resource_type == "health":
            profiles = await repository.list_profiles_for_brand(brand_id)
            if not profiles:
                return json.dumps({"error": "No profiles found"})
            query = GetEntityHealthQuery(repository)
            health = await query.execute(profile_id=profiles[0].id)
            return json.dumps(
                {
                    "overall_score": health.overall_score.value,
                    "dimension_scores": {
                        dt.value: s.value for dt, s in health.dimension_scores
                    },
                    "gaps_count": health.gaps_count,
                    "last_audit_at": health.last_audit_at.isoformat(),
                }
            )
        else:
            return json.dumps({"error": f"Unknown resource type: {resource_type}"})

    return server


async def run_graph_mcp_server(
    repository: GraphRepositoryPort,
    event_bus: EventBusPort,
) -> None:
    """Entry point: runs the GRAPH MCP server over stdio."""
    server = create_graph_mcp_server(repository, event_bus)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
