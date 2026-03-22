"""
LUMINA Module Bridge — routes ORBIT tool calls to bounded-context MCP servers

Architectural Intent:
- Adapter implementing ModuleBridgePort
- Aggregates tool definitions from all LUMINA modules into a single registry
- Routes tool calls to the appropriate module's application layer
- Decouples ORBIT from individual module internals
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Awaitable

from lumina.orbit.domain.value_objects import ModuleTarget, ToolDefinition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static tool registry — mirrors what each module's MCP server exposes
# ---------------------------------------------------------------------------

LUMINA_TOOL_REGISTRY: tuple[ToolDefinition, ...] = (
    # PULSE tools
    ToolDefinition(
        module=ModuleTarget.PULSE,
        name="run_monitoring",
        description=(
            "Run AI engine monitoring for a brand. Queries Claude, GPT-4o, Gemini, "
            "and Perplexity with prompt batteries and extracts citations, sentiment, "
            "and share-of-voice data."
        ),
        input_schema=(
            ("brand_id", "string", "The brand to monitor", True),
            ("battery_id", "string", "Prompt battery to use (optional)", False),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.PULSE,
        name="create_prompt_battery",
        description=(
            "Create a prompt battery — a set of queries to systematically test "
            "how AI engines respond about a brand."
        ),
        input_schema=(
            ("brand_id", "string", "The brand this battery is for", True),
            ("name", "string", "Battery name", True),
            ("prompts", "array", "List of prompt strings", True),
        ),
    ),
    # GRAPH tools
    ToolDefinition(
        module=ModuleTarget.GRAPH,
        name="create_entity_profile",
        description=(
            "Create a new entity profile for a brand with optional initial dimensions "
            "across 8 knowledge categories."
        ),
        input_schema=(
            ("brand_id", "string", "The brand identifier", True),
            ("entity_name", "string", "Display name of the entity", True),
            ("dimensions", "array", "Initial dimension data", False),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.GRAPH,
        name="update_dimension",
        description="Update a specific dimension of an entity profile.",
        input_schema=(
            ("entity_id", "string", "The entity profile ID", True),
            ("dimension_type", "string", "Dimension category", True),
            ("claims", "array", "Knowledge claims for this dimension", True),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.GRAPH,
        name="run_gap_analysis",
        description=(
            "Run entity knowledge gap analysis — compare what AI engines know "
            "about the brand against the desired entity profile."
        ),
        input_schema=(
            ("entity_id", "string", "The entity profile ID", True),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.GRAPH,
        name="generate_json_ld",
        description="Generate JSON-LD structured data from an entity profile.",
        input_schema=(
            ("entity_id", "string", "The entity profile ID", True),
        ),
    ),
    # BEAM tools
    ToolDefinition(
        module=ModuleTarget.BEAM,
        name="score_content",
        description=(
            "Score content for AI retrieval survivability using the 6-factor GEO model: "
            "entity density, answer shape, fact citability, RAG survivability, "
            "semantic authority, and freshness."
        ),
        input_schema=(
            ("brand_id", "string", "The brand this content belongs to", True),
            ("content", "string", "The content text to score", True),
            ("url", "string", "Source URL (optional)", False),
            ("content_type", "string", "Type: article, landing_page, etc.", False),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.BEAM,
        name="run_rag_simulation",
        description=(
            "Simulate how a RAG pipeline would chunk, embed, and retrieve this content."
        ),
        input_schema=(
            ("asset_id", "string", "The content asset ID", True),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.BEAM,
        name="generate_rewrites",
        description="Generate AI-optimised rewrite suggestions for content.",
        input_schema=(
            ("asset_id", "string", "The content asset ID", True),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.BEAM,
        name="bulk_audit",
        description="Audit multiple content assets for a brand in bulk.",
        input_schema=(
            ("brand_id", "string", "The brand to audit", True),
            ("urls", "array", "List of URLs to audit", True),
        ),
    ),
    # SIGNAL tools
    ToolDefinition(
        module=ModuleTarget.SIGNAL,
        name="create_distribution_plan",
        description="Plan content distribution across AI-crawled citation surfaces.",
        input_schema=(
            ("brand_id", "string", "The brand to distribute for", True),
            ("content_ids", "array", "Content asset IDs to distribute", True),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.SIGNAL,
        name="execute_action",
        description="Execute a single distribution action from a plan.",
        input_schema=(
            ("plan_id", "string", "The distribution plan ID", True),
            ("action_id", "string", "The action to execute", True),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.SIGNAL,
        name="generate_pr_brief",
        description="Generate a PR brief for AI visibility amplification.",
        input_schema=(
            ("brand_id", "string", "The brand", True),
            ("entity_id", "string", "Entity profile ID for context", True),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.SIGNAL,
        name="map_surfaces",
        description="Map citation surfaces relevant to a brand's vertical.",
        input_schema=(
            ("brand_id", "string", "The brand", True),
            ("vertical", "string", "Industry vertical", False),
        ),
    ),
    # INTELLIGENCE tools
    ToolDefinition(
        module=ModuleTarget.INTELLIGENCE,
        name="calculate_avs",
        description=(
            "Calculate the AI Visibility Score by fetching scores from all four "
            "LUMINA modules and computing a weighted composite."
        ),
        input_schema=(
            ("brand_id", "string", "The brand to score", True),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.INTELLIGENCE,
        name="run_root_cause_analysis",
        description="Analyse why the AVS changed by comparing module scores.",
        input_schema=(
            ("brand_id", "string", "The brand", True),
            ("current_scores", "object", "Current module scores", True),
            ("previous_scores", "object", "Previous module scores", True),
            ("external_signals", "array", "External context signals", False),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.INTELLIGENCE,
        name="generate_recommendations",
        description="Generate prioritised recommendations to improve the AVS.",
        input_schema=(
            ("brand_id", "string", "The brand", True),
            ("gaps", "array", "Knowledge gaps from GRAPH", False),
            ("content_scores", "array", "Content scores from BEAM", False),
            ("coverage", "object", "Distribution coverage from SIGNAL", False),
        ),
    ),
    # AGENCY tools
    ToolDefinition(
        module=ModuleTarget.AGENCY,
        name="onboard_client",
        description="Onboard a new client brand into the agency white-label platform.",
        input_schema=(
            ("agency_id", "string", "The agency ID", True),
            ("brand_name", "string", "Client brand name", True),
            ("brand_id", "string", "Brand identifier", True),
        ),
    ),
    ToolDefinition(
        module=ModuleTarget.AGENCY,
        name="generate_report",
        description="Generate a white-labelled client report.",
        input_schema=(
            ("agency_id", "string", "The agency ID", True),
            ("client_brand_id", "string", "Client brand ID", True),
            ("report_type", "string", "Type: weekly, monthly, quarterly", False),
        ),
    ),
)


class ModuleBridge:
    """Adapter that routes ORBIT tool calls to LUMINA module handlers.

    In development, uses registered handler callables. In production,
    this would call MCP server endpoints or in-process application commands.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Awaitable[str]]] = {}

    def register_handler(
        self,
        module: ModuleTarget,
        tool_name: str,
        handler: Callable[..., Awaitable[str]],
    ) -> None:
        """Register a handler for a specific module tool."""
        key = f"{module.value}__{tool_name}"
        self._handlers[key] = handler

    async def call_tool(
        self,
        module: ModuleTarget,
        tool_name: str,
        arguments: dict[str, object],
    ) -> str:
        """Route a tool call to the appropriate module handler."""
        key = f"{module.value}__{tool_name}"
        handler = self._handlers.get(key)

        if handler is None:
            logger.warning("No handler registered for %s", key)
            return json.dumps({
                "status": "not_implemented",
                "module": module.value,
                "tool": tool_name,
                "message": f"Tool {key} has no registered handler",
            })

        try:
            result = await handler(**arguments)
            return result
        except Exception as exc:
            logger.error("Tool %s failed: %s", key, exc)
            raise

    async def list_tools(self) -> tuple[ToolDefinition, ...]:
        """Return all available tools from the static registry."""
        return LUMINA_TOOL_REGISTRY
