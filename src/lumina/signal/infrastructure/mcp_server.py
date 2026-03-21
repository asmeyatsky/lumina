"""
SIGNAL MCP Server — Model Context Protocol server for the Distribution & Amplification context.

Exposes SIGNAL capabilities as MCP tools and resources so that AI agents
and orchestrators can interact with the bounded context over a standard protocol.

Tools:
- create_distribution_plan: Plan distribution across citation surfaces
- execute_action: Execute a single distribution action
- generate_pr_brief: Generate a PR brief from entity data
- map_surfaces: Map citation surfaces for a brand's vertical

Resources:
- signal://brands/{brand_id}/coverage: Coverage metrics
- signal://plans/{plan_id}: Plan status
- signal://brands/{brand_id}/pr-briefs: PR briefs for a brand
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from lumina.signal.application.commands import (
    CreateDistributionPlanCommand,
    ExecuteDistributionActionCommand,
    GeneratePRBriefCommand,
    MapSurfacesCommand,
)
from lumina.signal.application.queries import (
    GetDistributionCoverageQuery,
    GetPlanStatusQuery,
    GetPRBriefsQuery,
)
from lumina.signal.domain.ports import SignalRepositoryPort
from lumina.shared.ports.event_bus import EventBusPort
from lumina.signal.domain.services import (
    CoverageCalculationService,
    PRBriefGenerationService,
    SurfaceMappingService,
    SurfacePrioritizationService,
)
from lumina.signal.domain.ports import (
    ContentSyndicationPort,
    StructuredDataSubmissionPort,
    WikidataSubmissionPort,
)


def create_signal_mcp_server(
    repository: SignalRepositoryPort,
    event_bus: EventBusPort,
    structured_data_port: StructuredDataSubmissionPort,
    syndication_port: ContentSyndicationPort,
    wikidata_port: WikidataSubmissionPort,
) -> Server:
    """Create and configure the SIGNAL MCP server with all tools and resources.

    Args:
        repository: Persistence port for plans, surfaces, and briefs.
        event_bus: Event bus for publishing domain events.
        structured_data_port: Adapter for search console submissions.
        syndication_port: Adapter for content syndication.
        wikidata_port: Adapter for Wikidata entity management.

    Returns:
        A configured MCP Server ready to be served.
    """
    server = Server("lumina-signal")

    # Domain services (stateless, instantiated once)
    prioritization_service = SurfacePrioritizationService()
    coverage_service = CoverageCalculationService()
    brief_service = PRBriefGenerationService()
    mapping_service = SurfaceMappingService()

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="create_distribution_plan",
                description=(
                    "Create a distribution plan for a brand based on citation surface gaps. "
                    "Prioritizes surfaces by estimated LLM weight and gap severity, then "
                    "generates planned actions for each surface where the brand is absent."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {
                            "type": "string",
                            "description": "Unique identifier for the brand",
                        },
                        "brand_vertical": {
                            "type": "string",
                            "description": "Industry vertical (e.g. technology, healthcare, finance)",
                        },
                    },
                    "required": ["brand_id", "brand_vertical"],
                },
            ),
            Tool(
                name="execute_action",
                description=(
                    "Execute a single distribution action within a plan. Routes the action "
                    "to the appropriate adapter (search console, Wikidata, syndication) and "
                    "updates the plan status."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "plan_id": {
                            "type": "string",
                            "description": "The distribution plan ID",
                        },
                        "action_id": {
                            "type": "string",
                            "description": "The action ID to execute",
                        },
                    },
                    "required": ["plan_id", "action_id"],
                },
            ),
            Tool(
                name="generate_pr_brief",
                description=(
                    "Generate a PR brief for a brand using entity profile data and a "
                    "target narrative angle. Produces headline, key messages, target "
                    "publications, and entity anchors."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_name": {
                            "type": "string",
                            "description": "Display name of the brand",
                        },
                        "entity_data": {
                            "type": "object",
                            "description": "Key-value entity profile data (industry, key_products, etc.)",
                        },
                        "target_narrative": {
                            "type": "string",
                            "description": "The narrative angle for the PR brief",
                        },
                    },
                    "required": ["brand_name", "entity_data", "target_narrative"],
                },
            ),
            Tool(
                name="map_surfaces",
                description=(
                    "Identify and map all relevant citation surfaces for a brand based on "
                    "its industry vertical. Returns recommended surfaces with estimated "
                    "LLM training weights."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "brand_id": {
                            "type": "string",
                            "description": "Unique identifier for the brand",
                        },
                        "brand_vertical": {
                            "type": "string",
                            "description": "Industry vertical (e.g. technology, healthcare, finance)",
                        },
                    },
                    "required": ["brand_id", "brand_vertical"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "create_distribution_plan":
            # First map surfaces, then create plan
            map_cmd = MapSurfacesCommand(
                repository=repository,
                mapping_service=mapping_service,
            )
            surfaces = await map_cmd.execute(
                brand_id=arguments["brand_id"],
                brand_vertical=arguments["brand_vertical"],
            )

            # Identify gaps (all unknown surfaces)
            brand_gaps = [s.id for s in surfaces]

            create_cmd = CreateDistributionPlanCommand(
                repository=repository,
                event_bus=event_bus,
                prioritization_service=prioritization_service,
                coverage_service=coverage_service,
            )
            plan = await create_cmd.execute(
                brand_id=arguments["brand_id"],
                surfaces=surfaces,
                brand_gaps=brand_gaps,
            )

            result = {
                "plan_id": plan.id,
                "brand_id": plan.brand_id.value,
                "target_surfaces": len(plan.target_surfaces),
                "total_actions": len(plan.actions),
                "coverage_score": plan.coverage_score.value,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "execute_action":
            cmd = ExecuteDistributionActionCommand(
                repository=repository,
                event_bus=event_bus,
                structured_data_port=structured_data_port,
                syndication_port=syndication_port,
                wikidata_port=wikidata_port,
            )
            plan = await cmd.execute(
                plan_id=arguments["plan_id"],
                action_id=arguments["action_id"],
            )
            completed = [
                {"id": a.id, "surface_id": a.surface_id, "result_url": a.result_url}
                for a in plan.actions
                if a.id == arguments["action_id"]
            ]
            result = {
                "plan_id": plan.id,
                "action": completed[0] if completed else None,
                "coverage_score": plan.coverage_score.value,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "generate_pr_brief":
            cmd = GeneratePRBriefCommand(
                repository=repository,
                event_bus=event_bus,
                brief_service=brief_service,
            )
            brief = await cmd.execute(
                brand_name=arguments["brand_name"],
                entity_data=arguments["entity_data"],
                target_narrative=arguments["target_narrative"],
            )
            result = {
                "brief_id": brief.id,
                "headline": brief.headline,
                "narrative_angle": brief.narrative_angle,
                "target_publications": list(brief.target_publications),
                "key_messages": list(brief.key_messages),
                "entity_anchors": list(brief.entity_anchors),
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "map_surfaces":
            cmd = MapSurfacesCommand(
                repository=repository,
                mapping_service=mapping_service,
            )
            surfaces = await cmd.execute(
                brand_id=arguments["brand_id"],
                brand_vertical=arguments["brand_vertical"],
            )
            result = [
                {
                    "id": s.id,
                    "name": s.name,
                    "category": s.category.value,
                    "url": s.url.value,
                    "estimated_llm_weight": s.estimated_llm_weight.value,
                }
                for s in surfaces
            ]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="signal://brands/{brand_id}/coverage",
                name="Brand Distribution Coverage",
                description="Current distribution coverage metrics for a brand",
                mimeType="application/json",
            ),
            Resource(
                uri="signal://plans/{plan_id}",
                name="Distribution Plan Status",
                description="Status and progress of a distribution plan",
                mimeType="application/json",
            ),
            Resource(
                uri="signal://brands/{brand_id}/pr-briefs",
                name="Brand PR Briefs",
                description="Generated PR briefs for a brand",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        parts = uri.replace("signal://", "").split("/")

        # signal://brands/{brand_id}/coverage
        if len(parts) == 3 and parts[0] == "brands" and parts[2] == "coverage":
            brand_id = parts[1]
            query = GetDistributionCoverageQuery(
                repository=repository,
                coverage_service=coverage_service,
            )
            coverage = await query.execute(brand_id)
            if coverage is None:
                return json.dumps({"error": "No plans found for brand"})

            result = {
                "brand_id": coverage.brand_id.value,
                "total_surfaces": coverage.total_surfaces,
                "surfaces_with_presence": coverage.surfaces_with_presence,
                "coverage_percentage": coverage.coverage_percentage.value,
                "by_category": {
                    cat.value: pct.value for cat, pct in coverage.by_category
                },
            }
            return json.dumps(result, indent=2)

        # signal://plans/{plan_id}
        elif len(parts) == 2 and parts[0] == "plans":
            plan_id = parts[1]
            query = GetPlanStatusQuery(repository=repository)
            status = await query.execute(plan_id)
            if status is None:
                return json.dumps({"error": "Plan not found"})

            result = {
                "plan_id": status.plan_id,
                "brand_id": status.brand_id,
                "total_actions": status.total_actions,
                "completed_actions": status.completed_actions,
                "failed_actions": status.failed_actions,
                "in_progress_actions": status.in_progress_actions,
                "coverage_score": status.coverage_score,
            }
            return json.dumps(result, indent=2)

        # signal://brands/{brand_id}/pr-briefs
        elif len(parts) == 3 and parts[0] == "brands" and parts[2] == "pr-briefs":
            brand_id = parts[1]
            query = GetPRBriefsQuery(repository=repository)
            briefs = await query.execute(brand_id)
            result = [
                {
                    "id": b.id,
                    "headline": b.headline,
                    "narrative_angle": b.narrative_angle,
                    "target_publications": list(b.target_publications),
                    "key_messages": list(b.key_messages),
                    "entity_anchors": list(b.entity_anchors),
                    "created_at": b.created_at.isoformat(),
                }
                for b in briefs
            ]
            return json.dumps(result, indent=2)

        return json.dumps({"error": f"Unknown resource: {uri}"})

    return server


async def main() -> None:
    """Entry point for running the SIGNAL MCP server over stdio."""
    # In production, these would be injected from a composition root.
    # This main() exists so the server can be launched standalone for testing.
    raise NotImplementedError(
        "SIGNAL MCP server requires infrastructure adapters to be injected. "
        "Use create_signal_mcp_server() from a composition root."
    )
