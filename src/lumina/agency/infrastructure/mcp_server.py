"""
Agency MCP Server

Architectural Intent:
- Exposes Agency capabilities as an MCP (Model Context Protocol) server
- Tools map to application-layer commands
- Resources provide read-only access to agency domain state
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

from lumina.shared.ports.event_bus import EventBusPort

from lumina.agency.application.commands import (
    BulkGenerateReportsCommand,
    ConfigureWhiteLabelCommand,
    GenerateClientReportCommand,
    OnboardClientCommand,
)
from lumina.agency.application.queries import (
    GetClientDetailQuery,
    GetPortfolioOverviewQuery,
    ListClientReportsQuery,
)
from lumina.agency.domain.entities import MonitoringConfig
from lumina.agency.domain.ports import AgencyRepositoryPort
from lumina.agency.domain.value_objects import ReportType


def create_agency_mcp_server(
    repository: AgencyRepositoryPort,
    event_bus: EventBusPort,
) -> Server:
    """Create and configure the Agency MCP server.

    Args:
        repository: The Agency repository adapter.
        event_bus: The event bus adapter.

    Returns:
        A configured MCP Server instance.
    """
    server = Server("lumina-agency")

    # --- Tool definitions ---

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="onboard_client",
                description=(
                    "Onboard a new client brand under an agency. Validates plan limits "
                    "and sets up monitoring configuration."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agency_id": {
                            "type": "string",
                            "description": "The agency identifier.",
                        },
                        "brand_name": {
                            "type": "string",
                            "description": "The client brand name.",
                        },
                        "industry_vertical": {
                            "type": "string",
                            "description": "The industry vertical.",
                        },
                        "competitors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Competitor brand names.",
                        },
                    },
                    "required": ["agency_id", "brand_name"],
                },
            ),
            Tool(
                name="configure_white_label",
                description=(
                    "Configure white-label branding for an agency including logo, "
                    "colours, custom domain, and email settings."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agency_id": {
                            "type": "string",
                            "description": "The agency identifier.",
                        },
                        "company_name": {
                            "type": "string",
                            "description": "Display name for branding.",
                        },
                        "logo_url": {
                            "type": "string",
                            "description": "URL to the agency logo.",
                        },
                        "primary_color": {
                            "type": "string",
                            "description": "Primary brand colour (hex).",
                        },
                        "secondary_color": {
                            "type": "string",
                            "description": "Secondary brand colour (hex).",
                        },
                        "accent_color": {
                            "type": "string",
                            "description": "Accent colour (hex).",
                        },
                        "custom_domain": {
                            "type": "string",
                            "description": "Custom domain for white-label portal.",
                        },
                        "powered_by_visible": {
                            "type": "boolean",
                            "description": "Whether to show 'Powered by LUMINA'.",
                        },
                    },
                    "required": ["agency_id", "company_name", "logo_url"],
                },
            ),
            Tool(
                name="generate_report",
                description=(
                    "Generate a branded report for a specific client brand. "
                    "Supports weekly summary, monthly review, quarterly analysis, and custom types."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agency_id": {
                            "type": "string",
                            "description": "The agency identifier.",
                        },
                        "client_brand_id": {
                            "type": "string",
                            "description": "The client brand identifier.",
                        },
                        "report_type": {
                            "type": "string",
                            "enum": [rt.value for rt in ReportType],
                            "description": "The type of report to generate.",
                        },
                    },
                    "required": ["agency_id", "client_brand_id"],
                },
            ),
            Tool(
                name="bulk_generate_reports",
                description=(
                    "Generate reports for all active clients of an agency in parallel. "
                    "Produces one report per active client brand."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agency_id": {
                            "type": "string",
                            "description": "The agency identifier.",
                        },
                        "report_type": {
                            "type": "string",
                            "enum": [rt.value for rt in ReportType],
                            "description": "The type of report to generate.",
                        },
                    },
                    "required": ["agency_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "onboard_client":
            command = OnboardClientCommand(
                repository=repository,
                event_bus=event_bus,
            )
            client = await command.execute(
                agency_id=arguments["agency_id"],
                brand_name=arguments["brand_name"],
                industry_vertical=arguments.get("industry_vertical", ""),
                competitors=tuple(arguments.get("competitors", [])),
            )
            result = {
                "client_id": client.id,
                "agency_id": client.agency_id,
                "brand_name": client.brand_name,
                "industry_vertical": client.industry_vertical,
                "created_at": client.created_at.isoformat(),
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "configure_white_label":
            command = ConfigureWhiteLabelCommand(
                repository=repository,
                event_bus=event_bus,
            )
            config = await command.execute(
                agency_id=arguments["agency_id"],
                company_name=arguments["company_name"],
                logo_url=arguments["logo_url"],
                primary_color=arguments.get("primary_color", "#000000"),
                secondary_color=arguments.get("secondary_color", "#ffffff"),
                accent_color=arguments.get("accent_color", "#0066cc"),
                custom_domain=arguments.get("custom_domain"),
                powered_by_visible=arguments.get("powered_by_visible", True),
            )
            result = {
                "config_id": config.id,
                "agency_id": config.agency_id,
                "company_name": config.company_name,
                "custom_domain": config.custom_domain,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "generate_report":
            report_type = ReportType(
                arguments.get("report_type", "weekly_summary")
            )
            command = GenerateClientReportCommand(
                repository=repository,
                event_bus=event_bus,
            )
            report = await command.execute(
                agency_id=arguments["agency_id"],
                client_brand_id=arguments["client_brand_id"],
                report_type=report_type,
            )
            result = {
                "report_id": report.id,
                "agency_id": report.agency_id,
                "client_brand_id": report.client_brand_id,
                "report_type": report.report_type.value,
                "title": report.title,
                "generated_at": report.generated_at.isoformat(),
                "pdf_url": report.pdf_url,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "bulk_generate_reports":
            report_type = ReportType(
                arguments.get("report_type", "weekly_summary")
            )
            command = BulkGenerateReportsCommand(
                repository=repository,
                event_bus=event_bus,
            )
            reports = await command.execute(
                agency_id=arguments["agency_id"],
                report_type=report_type,
            )
            result = {
                "agency_id": arguments["agency_id"],
                "reports_generated": len(reports),
                "report_type": report_type.value,
                "reports": [
                    {
                        "report_id": r.id,
                        "client_brand_id": r.client_brand_id,
                        "title": r.title,
                    }
                    for r in reports
                ],
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        raise ValueError(f"Unknown tool: {name}")

    # --- Resource definitions ---

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="agency://portfolio",
                name="Agency Portfolio",
                description="Overview of all client brands managed by the agency.",
                mimeType="application/json",
            ),
            Resource(
                uri="agency://clients/{client_id}",
                name="Client Brand Detail",
                description="Detailed information about a specific client brand.",
                mimeType="application/json",
            ),
            Resource(
                uri="agency://reports/{report_id}",
                name="Client Report",
                description="A generated report for a client brand.",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        parts = str(uri).split("/")
        # agency://portfolio -> ['agency:', '', 'portfolio']
        # agency://clients/{id} -> ['agency:', '', 'clients', '{id}']
        # agency://reports/{id} -> ['agency:', '', 'reports', '{id}']

        if len(parts) >= 3 and parts[2] == "portfolio":
            # Return empty portfolio summary — caller provides agency_id context
            result = {
                "message": "Use the GetPortfolioOverviewQuery with an agency_id to fetch portfolio data.",
            }
            return json.dumps(result, indent=2)

        elif len(parts) >= 4 and parts[2] == "clients":
            client_id = parts[3]
            query = GetClientDetailQuery(repository=repository)
            client = await query.execute(client_id)
            result = {
                "client_id": client.id,
                "agency_id": client.agency_id,
                "brand_name": client.brand_name,
                "industry_vertical": client.industry_vertical,
                "competitors": list(client.competitors),
                "is_active": client.is_active,
                "created_at": client.created_at.isoformat(),
            }
            return json.dumps(result, indent=2)

        elif len(parts) >= 4 and parts[2] == "reports":
            report_id = parts[3]
            # Reports are accessed via list queries; individual lookup
            # would require a get_report_by_id method on the repository.
            result = {
                "report_id": report_id,
                "message": "Use ListClientReportsQuery to fetch reports for a client brand.",
            }
            return json.dumps(result, indent=2)

        raise ValueError(f"Unknown resource URI: {uri}")

    return server


async def run_agency_mcp_server(
    repository: AgencyRepositoryPort,
    event_bus: EventBusPort,
) -> None:
    """Start the Agency MCP server over stdio."""
    server = create_agency_mcp_server(repository, event_bus)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
