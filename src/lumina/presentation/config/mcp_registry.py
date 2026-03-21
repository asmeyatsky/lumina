"""
MCP Server Registry Configuration

Architectural Intent:
- Central registry for all LUMINA MCP servers (one per bounded context)
- JSON configuration for server endpoints, transport, and capabilities
- Registry class manages MCP server lifecycle (start/stop/health)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("lumina.mcp_registry")


class MCPTransport(str, Enum):
    """Transport protocol for MCP server communication."""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration for a single MCP server."""

    name: str
    module: str
    transport: MCPTransport
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    tools: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()
    description: str = ""


# Default MCP server configurations for all five LUMINA bounded contexts
DEFAULT_MCP_CONFIGS: tuple[MCPServerConfig, ...] = (
    MCPServerConfig(
        name="lumina-pulse",
        module="lumina.pulse",
        transport=MCPTransport.STDIO,
        command="python",
        args=("-m", "lumina.pulse.infrastructure.mcp_server"),
        tools=(
            "trigger_monitoring_run",
            "get_monitoring_results",
            "create_prompt_battery",
        ),
        resources=(
            "pulse://brands/{brand_id}/citations",
            "pulse://brands/{brand_id}/share-of-voice",
            "pulse://brands/{brand_id}/trends",
        ),
        description="PULSE — Citation monitoring and share-of-voice tracking across AI engines.",
    ),
    MCPServerConfig(
        name="lumina-graph",
        module="lumina.graph",
        transport=MCPTransport.STDIO,
        command="python",
        args=("-m", "lumina.graph.infrastructure.mcp_server"),
        tools=(
            "create_entity_profile",
            "run_gap_analysis",
            "generate_json_ld",
        ),
        resources=(
            "graph://brands/{brand_id}/profile",
            "graph://brands/{brand_id}/gaps",
            "graph://brands/{brand_id}/dimensions",
        ),
        description="GRAPH — Entity intelligence and knowledge graph management.",
    ),
    MCPServerConfig(
        name="lumina-beam",
        module="lumina.beam",
        transport=MCPTransport.STDIO,
        command="python",
        args=("-m", "lumina.beam.infrastructure.mcp_server"),
        tools=(
            "score_content",
            "bulk_audit",
            "run_rag_simulation",
            "generate_rewrites",
        ),
        resources=(
            "beam://assets/{asset_id}/score",
            "beam://brands/{brand_id}/audit-summary",
        ),
        description="BEAM — Content optimisation for AI readability and retrievability.",
    ),
    MCPServerConfig(
        name="lumina-signal",
        module="lumina.signal",
        transport=MCPTransport.STDIO,
        command="python",
        args=("-m", "lumina.signal.infrastructure.mcp_server"),
        tools=(
            "create_distribution_plan",
            "execute_action",
            "generate_pr_brief",
            "map_surfaces",
        ),
        resources=(
            "signal://brands/{brand_id}/coverage",
            "signal://plans/{plan_id}/status",
        ),
        description="SIGNAL — Distribution and surface coverage management.",
    ),
    MCPServerConfig(
        name="lumina-intelligence",
        module="lumina.intelligence",
        transport=MCPTransport.STDIO,
        command="python",
        args=("-m", "lumina.intelligence.infrastructure.mcp_server"),
        tools=(
            "calculate_avs",
            "run_root_cause_analysis",
            "generate_recommendations",
        ),
        resources=(
            "intelligence://brands/{brand_id}/avs",
            "intelligence://brands/{brand_id}/recommendations",
            "intelligence://brands/{brand_id}/trends",
        ),
        description="Intelligence Engine — Unified AVS scoring, root cause analysis, and recommendations.",
    ),
)


def get_mcp_config_json() -> str:
    """Return the MCP server registry as a JSON configuration string.

    This format is compatible with MCP client configuration files
    (e.g. claude_desktop_config.json).
    """
    config: dict[str, Any] = {"mcpServers": {}}
    for server in DEFAULT_MCP_CONFIGS:
        config["mcpServers"][server.name] = {
            "command": server.command,
            "args": list(server.args),
            "env": server.env,
            "transport": server.transport.value,
            "tools": list(server.tools),
            "resources": list(server.resources),
            "description": server.description,
        }
    return json.dumps(config, indent=2)


class MCPRegistry:
    """Registry that manages the lifecycle of all LUMINA MCP servers.

    In production, this starts MCP server processes and monitors their health.
    In development, it provides configuration introspection.
    """

    def __init__(
        self, configs: tuple[MCPServerConfig, ...] = DEFAULT_MCP_CONFIGS
    ) -> None:
        self._configs = {cfg.name: cfg for cfg in configs}
        self._running: dict[str, asyncio.subprocess.Process] = {}

    @property
    def server_names(self) -> list[str]:
        """Return names of all registered MCP servers."""
        return list(self._configs.keys())

    def get_config(self, name: str) -> MCPServerConfig:
        """Get configuration for a specific MCP server.

        Raises:
            KeyError: If the server name is not registered.
        """
        return self._configs[name]

    async def start_server(self, name: str) -> None:
        """Start an MCP server process.

        Args:
            name: The registered name of the MCP server.

        Raises:
            KeyError: If the server name is not registered.
            RuntimeError: If the server is already running.
        """
        if name in self._running:
            raise RuntimeError(f"MCP server '{name}' is already running")

        config = self._configs[name]
        cmd = [config.command, *config.args]

        logger.info("Starting MCP server: %s (command: %s)", name, " ".join(cmd))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**dict(__import__("os").environ), **config.env},
        )
        self._running[name] = process
        logger.info("MCP server '%s' started (PID: %d)", name, process.pid)

    async def stop_server(self, name: str) -> None:
        """Stop a running MCP server process.

        Args:
            name: The registered name of the MCP server.
        """
        process = self._running.pop(name, None)
        if process is None:
            logger.warning("MCP server '%s' is not running", name)
            return

        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("MCP server '%s' did not terminate; killing", name)
            process.kill()
            await process.wait()

        logger.info("MCP server '%s' stopped", name)

    async def start_all(self) -> None:
        """Start all registered MCP servers concurrently."""
        await asyncio.gather(
            *(self.start_server(name) for name in self._configs)
        )

    async def stop_all(self) -> None:
        """Stop all running MCP servers concurrently."""
        names = list(self._running.keys())
        await asyncio.gather(*(self.stop_server(name) for name in names))

    def is_running(self, name: str) -> bool:
        """Check whether a specific MCP server is running."""
        process = self._running.get(name)
        if process is None:
            return False
        return process.returncode is None
