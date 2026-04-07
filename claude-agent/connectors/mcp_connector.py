"""
MCP Connector — Integrates Model Context Protocol (MCP) servers into the Claude agent.

Supports:
  - stdio MCP servers  (local processes: npx, uvx, python -m …)
  - SSE MCP servers    (HTTP Server-Sent Events)
  - Streamable HTTP MCP servers

Usage:
    connector = MCPConnector()

    # Stdio server (local process)
    config = MCPServerConfig(
        name="filesystem",
        type="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "."],
    )
    tools    = asyncio.run(connector.list_tools(config))
    result   = asyncio.run(connector.call_tool(config, "read_file", {"path": "src/app.tsx"}))

    # SSE server
    config = MCPServerConfig(name="myserver", type="sse", url="http://localhost:8080/sse")
    tools  = asyncio.run(connector.list_tools(config))

    # Pretty-print tools
    connector.print_tools(tools, "filesystem")
"""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


# ─────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────

@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    name: str
    type: str = "stdio"                            # stdio | sse | http
    command: str = ""                              # stdio: executable (npx, uvx, python …)
    args: list[str] = field(default_factory=list)  # stdio: argument list
    url: str = ""                                  # sse/http: server URL
    env: dict[str, str] = field(default_factory=dict)  # extra env vars for stdio

    def to_display(self) -> str:
        """Human-readable connection string."""
        if self.type == "stdio":
            return f"{self.command} {' '.join(self.args)}".strip()
        return self.url


@dataclass
class MCPTool:
    """A single tool exposed by an MCP server."""

    name: str
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    server_name: str = ""

    def to_claude_tool(self) -> dict:
        """Convert to the Anthropic Claude API tool format."""
        # Prefix with server name so multiple servers can expose same-named tools
        qualified = f"{self.server_name}__{self.name}" if self.server_name else self.name
        return {
            "name": qualified,
            "description": self.description or "(no description)",
            "input_schema": self.input_schema or {"type": "object", "properties": {}},
        }


@dataclass
class MCPResource:
    """A resource exposed by an MCP server."""

    uri: str
    name: str = ""
    description: str = ""
    mime_type: str = ""


# ─────────────────────────────────────────────────
# MCPConnector
# ─────────────────────────────────────────────────

class MCPConnector:
    """
    Manages connections to one or more MCP servers.

    Opens per-call sessions (lightweight: each call re-connects) for
    stdio, SSE, and Streamable HTTP transports.

    Requires: pip install mcp>=1.0.0
    """

    # ── Dependency check ──────────────────────────────────────────────────

    @staticmethod
    def _ensure_mcp() -> None:
        try:
            import mcp  # noqa: F401
        except ImportError:
            console.print(
                "[red]❌ The [bold]mcp[/bold] package is not installed.\n"
                "   Run: [bold]pip install mcp>=1.0.0[/bold][/red]"
            )
            raise

    # ── Session context managers ──────────────────────────────────────────

    @asynccontextmanager
    async def _stdio_session(self, config: MCPServerConfig):
        """Open a stdio MCP session."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env or None,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    @asynccontextmanager
    async def _sse_session(self, config: MCPServerConfig):
        """Open a Server-Sent Events MCP session."""
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async with sse_client(config.url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    @asynccontextmanager
    async def _http_session(self, config: MCPServerConfig):
        """Open a Streamable HTTP MCP session."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(config.url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    @asynccontextmanager
    async def open(self, config: MCPServerConfig):
        """Open the appropriate session type from an MCPServerConfig."""
        self._ensure_mcp()
        if config.type == "stdio":
            async with self._stdio_session(config) as s:
                yield s
        elif config.type == "sse":
            async with self._sse_session(config) as s:
                yield s
        elif config.type == "http":
            async with self._http_session(config) as s:
                yield s
        else:
            raise ValueError(f"Unknown MCP server type: '{config.type}'. Use stdio | sse | http")

    # ── Tool operations ───────────────────────────────────────────────────

    async def list_tools(self, config: MCPServerConfig) -> list[MCPTool]:
        """Return all tools available on the server."""
        async with self.open(config) as session:
            result = await session.list_tools()
            return [
                MCPTool(
                    name=t.name,
                    description=t.description or "",
                    input_schema=getattr(t, "inputSchema", {}) or {},
                    server_name=config.name,
                )
                for t in result.tools
            ]

    async def call_tool(
        self,
        config: MCPServerConfig,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Call a tool on the server. Returns the text result."""
        async with self.open(config) as session:
            result = await session.call_tool(tool_name, arguments)
            return "\n".join(
                block.text if hasattr(block, "text") else str(block)
                for block in result.content
            )

    # ── Resource operations ───────────────────────────────────────────────

    async def list_resources(self, config: MCPServerConfig) -> list[MCPResource]:
        """Return all resources available on the server."""
        async with self.open(config) as session:
            result = await session.list_resources()
            return [
                MCPResource(
                    uri=r.uri,
                    name=r.name or "",
                    description=r.description or "",
                    mime_type=r.mimeType or "",
                )
                for r in result.resources
            ]

    async def read_resource(self, config: MCPServerConfig, uri: str) -> str:
        """Read a resource by URI. Returns text content."""
        async with self.open(config) as session:
            result = await session.read_resource(uri)
            return "\n".join(
                block.text if hasattr(block, "text") else str(block)
                for block in result.contents
            )

    # ── Pretty-print helpers ──────────────────────────────────────────────

    def print_tools(self, tools: list[MCPTool], server_name: str = "") -> None:
        title = f"🔧 MCP Tools — {server_name}" if server_name else "🔧 MCP Tools"
        table = Table(title=title, show_lines=True)
        table.add_column("Tool", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        for t in tools:
            table.add_row(t.name, t.description or "—")
        console.print(table)

    def print_resources(self, resources: list[MCPResource], server_name: str = "") -> None:
        title = f"📦 MCP Resources — {server_name}" if server_name else "📦 MCP Resources"
        table = Table(title=title, show_lines=True)
        table.add_column("URI", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("MIME", style="dim")
        for r in resources:
            table.add_row(r.uri, r.name or "—", r.mime_type or "—")
        console.print(table)


# ─────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────

def parse_server_string(server_str: str, name: str = "server") -> MCPServerConfig:
    """
    Parse a compact server string into an MCPServerConfig.

    Examples
    --------
    stdio:
        "npx -y @modelcontextprotocol/server-filesystem ."
        "uvx mcp-server-git --repo ."
        "python -m my_mcp_server"

    SSE (HTTP):
        "http://localhost:8080/sse"
        "https://my-mcp.example.com/sse"

    Streamable HTTP:
        "http://localhost:8080/mcp"
    """
    s = server_str.strip()
    if s.startswith(("http://", "https://")):
        transport = "sse" if ("/sse" in s) else "http"
        return MCPServerConfig(name=name, type=transport, url=s)
    # Treat as stdio command
    parts = s.split()
    if not parts:
        raise ValueError("Empty MCP server string")
    return MCPServerConfig(name=name, type="stdio", command=parts[0], args=parts[1:])
