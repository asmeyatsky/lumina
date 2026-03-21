"""
BEAM MCP Server — Model Context Protocol server for the BEAM bounded context

Architectural Intent:
- One MCP server per bounded context
- Exposes BEAM capabilities as MCP tools and resources
- Tools: score_content, run_rag_simulation, generate_rewrites, bulk_audit
- Resources: beam://assets/{asset_id}/score, beam://brands/{brand_id}/audit-summary
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool

from lumina.beam.application.commands import (
    BulkAuditCommand,
    GenerateRewritesCommand,
    RunRAGSimulationCommand,
    ScoreContentCommand,
)
from lumina.beam.application.queries import (
    GetAuditSummaryQuery,
    GetContentScoreQuery,
)
from lumina.beam.domain.ports import BeamRepositoryPort, ContentCrawlerPort
from lumina.beam.domain.services import GEOScoringService, RAGSimulationService, RewriteService
from lumina.beam.domain.value_objects import ContentType
from lumina.shared.ports.event_bus import EventBusPort


class BeamMCPServer:
    """MCP server exposing BEAM scoring and optimisation capabilities.

    Provides tools for content scoring, RAG simulation, rewrite generation,
    and bulk auditing. Also exposes resources for reading scores and summaries.
    """

    def __init__(
        self,
        repository: BeamRepositoryPort,
        crawler: ContentCrawlerPort,
        event_bus: EventBusPort,
    ) -> None:
        self._repository = repository
        self._crawler = crawler
        self._event_bus = event_bus
        self._scoring_service = GEOScoringService()
        self._simulation_service = RAGSimulationService()
        self._rewrite_service = RewriteService()
        self._server = Server("beam")
        self._register_tools()
        self._register_resources()

    @property
    def server(self) -> Server:
        """Return the underlying MCP Server instance."""
        return self._server

    def _register_tools(self) -> None:
        """Register all BEAM tools with the MCP server."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="score_content",
                    description=(
                        "Score a content asset for AI visibility using the 6-factor GEO model. "
                        "Accepts a URL to crawl or raw content text."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "brand_id": {
                                "type": "string",
                                "description": "The brand identifier",
                            },
                            "url": {
                                "type": "string",
                                "description": "URL to crawl and score",
                            },
                            "raw_content": {
                                "type": "string",
                                "description": "Raw content text to score (alternative to URL)",
                            },
                            "title": {
                                "type": "string",
                                "description": "Content title (auto-extracted if URL provided)",
                            },
                            "content_type": {
                                "type": "string",
                                "enum": [ct.value for ct in ContentType],
                                "description": "Type of content asset",
                            },
                            "brand_entities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Entity names for density scoring",
                            },
                        },
                        "required": ["brand_id"],
                    },
                ),
                Tool(
                    name="run_rag_simulation",
                    description=(
                        "Simulate RAG retrieval on a content asset to assess "
                        "how well facts survive the chunking and retrieval process."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "asset_id": {
                                "type": "string",
                                "description": "The content asset to simulate",
                            },
                            "query": {
                                "type": "string",
                                "description": "The query to simulate retrieval for",
                            },
                            "chunk_size": {
                                "type": "integer",
                                "description": "Target tokens per chunk (default: 512)",
                            },
                        },
                        "required": ["asset_id", "query"],
                    },
                ),
                Tool(
                    name="generate_rewrites",
                    description=(
                        "Generate rewrite suggestions to improve the GEO score "
                        "of a scored content asset."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "asset_id": {
                                "type": "string",
                                "description": "The scored content asset",
                            },
                        },
                        "required": ["asset_id"],
                    },
                ),
                Tool(
                    name="bulk_audit",
                    description=(
                        "Score multiple URLs in parallel for a brand's content estate audit."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "brand_id": {
                                "type": "string",
                                "description": "The brand identifier",
                            },
                            "urls": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "URLs to crawl and score",
                            },
                            "brand_entities": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Entity names for density scoring",
                            },
                        },
                        "required": ["brand_id", "urls"],
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            if name == "score_content":
                return await self._handle_score_content(arguments)
            elif name == "run_rag_simulation":
                return await self._handle_rag_simulation(arguments)
            elif name == "generate_rewrites":
                return await self._handle_generate_rewrites(arguments)
            elif name == "bulk_audit":
                return await self._handle_bulk_audit(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

    def _register_resources(self) -> None:
        """Register all BEAM resources with the MCP server."""

        @self._server.list_resources()
        async def list_resources() -> list[Resource]:
            return [
                Resource(
                    uri="beam://assets/{asset_id}/score",
                    name="Content Asset GEO Score",
                    description="GEO score for a specific content asset",
                    mimeType="application/json",
                ),
                Resource(
                    uri="beam://brands/{brand_id}/audit-summary",
                    name="Brand Audit Summary",
                    description="Audit summary for a brand's content estate",
                    mimeType="application/json",
                ),
            ]

        @self._server.read_resource()
        async def read_resource(uri: str) -> str:
            if "/score" in uri and "assets/" in uri:
                asset_id = uri.split("assets/")[1].split("/")[0]
                return await self._read_asset_score(asset_id)
            elif "/audit-summary" in uri and "brands/" in uri:
                brand_id = uri.split("brands/")[1].split("/")[0]
                return await self._read_audit_summary(brand_id)
            return json.dumps({"error": f"Unknown resource: {uri}"})

    async def _handle_score_content(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Handle the score_content tool call."""
        cmd = ScoreContentCommand(
            repository=self._repository,
            crawler=self._crawler,
            event_bus=self._event_bus,
            scoring_service=self._scoring_service,
        )

        content_type = ContentType.WEB_PAGE
        if "content_type" in arguments:
            content_type = ContentType(arguments["content_type"])

        result = await cmd.execute(
            brand_id=arguments["brand_id"],
            url=arguments.get("url"),
            raw_content=arguments.get("raw_content"),
            title=arguments.get("title"),
            content_type=content_type,
            brand_entities=arguments.get("brand_entities"),
        )

        response = {
            "asset_id": result.asset.id,
            "title": result.asset.title,
            "overall_score": result.geo_score.overall.value,
            "factors": {
                "entity_density": result.geo_score.entity_density.value,
                "answer_shape": result.geo_score.answer_shape.value,
                "fact_citability": result.geo_score.fact_citability.value,
                "rag_survivability": result.geo_score.rag_survivability.value,
                "semantic_authority": result.geo_score.semantic_authority.value,
                "freshness_signals": result.geo_score.freshness_signals.value,
            },
        }
        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _handle_rag_simulation(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Handle the run_rag_simulation tool call."""
        cmd = RunRAGSimulationCommand(
            repository=self._repository,
            event_bus=self._event_bus,
            simulation_service=self._simulation_service,
        )

        result = await cmd.execute(
            asset_id=arguments["asset_id"],
            query=arguments["query"],
            chunk_size=arguments.get("chunk_size", 512),
        )

        response = {
            "asset_id": result.asset_id,
            "total_chunks": len(result.chunks),
            "survivability_score": result.survivability_score.value,
            "survived_facts": len(result.survived_facts),
            "lost_facts": len(result.lost_facts),
            "lost_fact_details": list(result.lost_facts),
        }
        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _handle_generate_rewrites(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Handle the generate_rewrites tool call."""
        cmd = GenerateRewritesCommand(
            repository=self._repository,
            event_bus=self._event_bus,
            rewrite_service=self._rewrite_service,
        )

        asset = await cmd.execute(asset_id=arguments["asset_id"])

        suggestions = [
            {
                "id": s.id,
                "factor": s.factor.value,
                "original": s.original_text,
                "suggested": s.suggested_text,
                "expected_impact": s.expected_impact.value,
                "rationale": s.rationale,
            }
            for s in asset.suggestions
        ]

        response = {
            "asset_id": asset.id,
            "total_suggestions": len(suggestions),
            "suggestions": suggestions,
        }
        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _handle_bulk_audit(
        self, arguments: dict[str, Any]
    ) -> list[TextContent]:
        """Handle the bulk_audit tool call."""
        cmd = BulkAuditCommand(
            repository=self._repository,
            crawler=self._crawler,
            event_bus=self._event_bus,
            scoring_service=self._scoring_service,
        )

        results = await cmd.execute(
            brand_id=arguments["brand_id"],
            urls=arguments["urls"],
            brand_entities=arguments.get("brand_entities"),
        )

        response = {
            "brand_id": arguments["brand_id"],
            "total_scored": len(results),
            "total_requested": len(arguments["urls"]),
            "assets": [
                {
                    "asset_id": r.asset.id,
                    "url": r.asset.url.value,
                    "title": r.asset.title,
                    "overall_score": r.geo_score.overall.value,
                }
                for r in results
            ],
        }

        if results:
            scores = [r.geo_score.overall.value for r in results]
            response["avg_score"] = round(sum(scores) / len(scores), 2)

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    async def _read_asset_score(self, asset_id: str) -> str:
        """Read the GEO score resource for an asset."""
        query = GetContentScoreQuery(repository=self._repository)
        score = await query.execute(asset_id)

        if score is None:
            return json.dumps({"error": f"No score found for asset {asset_id}"})

        return json.dumps(
            {
                "asset_id": asset_id,
                "overall": score.overall.value,
                "entity_density": score.entity_density.value,
                "answer_shape": score.answer_shape.value,
                "fact_citability": score.fact_citability.value,
                "rag_survivability": score.rag_survivability.value,
                "semantic_authority": score.semantic_authority.value,
                "freshness_signals": score.freshness_signals.value,
            },
            indent=2,
        )

    async def _read_audit_summary(self, brand_id: str) -> str:
        """Read the audit summary resource for a brand."""
        query = GetAuditSummaryQuery(repository=self._repository)
        summary = await query.execute(brand_id)

        return json.dumps(
            {
                "brand_id": brand_id,
                "total_assets": summary.total_assets,
                "avg_geo_score": summary.avg_geo_score.value,
                "assets_below_threshold": summary.assets_below_threshold,
                "top_improvement_opportunities": list(
                    summary.top_improvement_opportunities
                ),
            },
            indent=2,
        )
