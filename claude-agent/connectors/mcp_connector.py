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

    # Use a named preset (pulls credentials from Config/.env automatically)
    config = build_preset("figma")    # uses FIGMA_ACCESS_TOKEN
    config = build_preset("jira")     # uses JIRA_BASE_URL + JIRA_EMAIL + JIRA_API_TOKEN
    config = build_preset("github")   # uses GITHUB_TOKEN
"""

import asyncio
import json
import os
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

# ─────────────────────────────────────────────────
# Known MCP server presets
# ─────────────────────────────────────────────────

# Each entry: (command, args_template, env_vars_needed, description)
# env_vars_needed: list of (env_key, description) pairs — values are
# pulled from os.environ at build time so they come from .env via Config.

_PRESET_REGISTRY: dict[str, dict] = {
    # ── Figma ──────────────────────────────────────────────────────────────
    "figma": {
        "command": "npx",
        "args": ["-y", "figma-mcp"],
        "env_keys": {"FIGMA_API_KEY": "FIGMA_ACCESS_TOKEN"},  # map preset key → .env key
        "description": "Official Figma MCP — read files, components, variables, dev-mode inspect",
        "install": "npx -y figma-mcp  (requires FIGMA_ACCESS_TOKEN in .env)",
        "docs": "https://github.com/figma/mcp",
    },
    # ── Jira / Atlassian ───────────────────────────────────────────────────
    "jira": {
        "command": "uvx",
        "args": ["mcp-atlassian"],
        "env_keys": {
            "JIRA_URL": "JIRA_BASE_URL",
            "JIRA_USERNAME": "JIRA_EMAIL",
            "JIRA_API_TOKEN": "JIRA_API_TOKEN",
        },
        "description": "mcp-atlassian — Jira issues, projects, sprints, search (JQL)",
        "install": "uvx mcp-atlassian  (requires JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN in .env)",
        "docs": "https://github.com/sooperset/mcp-atlassian",
    },
    # ── Confluence (same package as Jira) ──────────────────────────────────
    "confluence": {
        "command": "uvx",
        "args": ["mcp-atlassian", "--confluence-only"],
        "env_keys": {
            "CONFLUENCE_URL": "JIRA_BASE_URL",
            "CONFLUENCE_USERNAME": "JIRA_EMAIL",
            "CONFLUENCE_API_TOKEN": "JIRA_API_TOKEN",
        },
        "description": "mcp-atlassian (Confluence only) — pages, spaces, search",
        "install": "uvx mcp-atlassian  (shares Atlassian credentials with jira preset)",
        "docs": "https://github.com/sooperset/mcp-atlassian",
    },
    # ── GitHub ─────────────────────────────────────────────────────────────
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env_keys": {"GITHUB_PERSONAL_ACCESS_TOKEN": "GITHUB_TOKEN"},
        "description": "Official GitHub MCP — repos, issues, PRs, code search",
        "install": "npx -y @modelcontextprotocol/server-github  (requires GITHUB_TOKEN in .env)",
        "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/github",
    },
    # ── Filesystem (local files) ───────────────────────────────────────────
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "env_keys": {},
        "description": "Official filesystem MCP — read/write/list local files",
        "install": "npx -y @modelcontextprotocol/server-filesystem .",
        "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
    },
    # ── Git ────────────────────────────────────────────────────────────────
    "git": {
        "command": "uvx",
        "args": ["mcp-server-git", "--repo", "."],
        "env_keys": {},
        "description": "Official Git MCP — log, diff, blame, branch, commit",
        "install": "uvx mcp-server-git --repo .",
        "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/git",
    },
    # ── Slack ──────────────────────────────────────────────────────────────
    "slack": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env_keys": {
            "SLACK_BOT_TOKEN": "SLACK_BOT_TOKEN",
            "SLACK_TEAM_ID": "SLACK_TEAM_ID",
        },
        "description": "Official Slack MCP — channels, messages, users",
        "install": "npx -y @modelcontextprotocol/server-slack  (requires SLACK_BOT_TOKEN, SLACK_TEAM_ID)",
        "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/slack",
    },
    # ── Postgres ───────────────────────────────────────────────────────────
    "postgres": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres", "${DATABASE_URL}"],
        "env_keys": {"DATABASE_URL": "DATABASE_URL"},
        "description": "Official Postgres MCP — query, schema inspect, tables",
        "install": "npx -y @modelcontextprotocol/server-postgres  (requires DATABASE_URL in .env)",
        "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/postgres",
        "_url_arg": True,  # DATABASE_URL is interpolated into args
    },
    # ── Brave Search ──────────────────────────────────────────────────────
    "search": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env_keys": {"BRAVE_API_KEY": "BRAVE_API_KEY"},
        "description": "Official Brave Search MCP — web + local search",
        "install": "npx -y @modelcontextprotocol/server-brave-search  (requires BRAVE_API_KEY)",
        "docs": "https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search",
    },
}


def build_preset(preset_name: str, extra_env: dict[str, str] | None = None) -> MCPServerConfig:
    """
    Build an MCPServerConfig from a named preset.

    Credentials are automatically pulled from environment variables
    (already loaded from .env by Config).  Pass extra_env to override
    individual values.

    Args:
        preset_name:  One of: figma, jira, confluence, github,
                      filesystem, git, slack, postgres, search
        extra_env:    Optional overrides for env vars.

    Returns:
        MCPServerConfig ready to pass to MCPConnector or run_mcp_agent.

    Raises:
        ValueError: if the preset name is not recognised.
    """
    key = preset_name.lower().strip()
    if key not in _PRESET_REGISTRY:
        available = ", ".join(sorted(_PRESET_REGISTRY))
        raise ValueError(
            f"Unknown MCP preset '{preset_name}'. "
            f"Available: {available}\n"
            f"Or pass a full server string: 'npx -y ...' / 'http://...'"
        )

    entry = _PRESET_REGISTRY[key]

    # Build env dict: map preset env key → value from os.environ (sourced from .env)
    env: dict[str, str] = {}
    for preset_key, env_key in entry["env_keys"].items():
        value = (extra_env or {}).get(preset_key) or os.environ.get(env_key, "")
        if value:
            env[preset_key] = value

    # Interpolate ${DATABASE_URL} style placeholders in args
    args = [
        os.environ.get(a.lstrip("${}").rstrip("}"), a) if a.startswith("${") else a
        for a in entry["args"]
    ]

    return MCPServerConfig(
        name=key,
        type="stdio",
        command=entry["command"],
        args=args,
        env=env,
    )


def list_presets() -> None:
    """Pretty-print all available MCP presets to the console."""
    table = Table(title="🔌 Built-in MCP Server Presets", show_lines=True)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Install / Command", style="dim")
    for name, entry in _PRESET_REGISTRY.items():
        table.add_row(name, entry["description"], entry["install"])
    console.print(table)


def parse_server_string(server_str: str, name: str = "server") -> MCPServerConfig:
    """
    Parse a compact server string (or named preset) into an MCPServerConfig.

    Named presets (auto-inject credentials from .env):
        "figma"       → npx -y figma-mcp          (FIGMA_ACCESS_TOKEN)
        "jira"        → uvx mcp-atlassian           (JIRA_* vars)
        "confluence"  → uvx mcp-atlassian           (JIRA_* vars)
        "github"      → npx -y ...server-github     (GITHUB_TOKEN)
        "filesystem"  → npx -y ...server-filesystem .
        "git"         → uvx mcp-server-git --repo .
        "slack"       → npx -y ...server-slack      (SLACK_* vars)
        "postgres"    → npx -y ...server-postgres   (DATABASE_URL)
        "search"      → npx -y ...server-brave-search (BRAVE_API_KEY)

    Explicit strings:
        stdio:  "npx -y @modelcontextprotocol/server-filesystem ."
                "uvx mcp-server-git --repo ."
                "python -m my_mcp_server"
        SSE:    "http://localhost:8080/sse"
        HTTP:   "http://localhost:8080/mcp"
    """
    s = server_str.strip()

    # ── Named preset ──────────────────────────────────────────────────────
    if s.lower() in _PRESET_REGISTRY:
        cfg = build_preset(s.lower())
        if name != "server":          # caller supplied an explicit name override
            cfg.name = name
        return cfg

    # ── HTTP / SSE URL ────────────────────────────────────────────────────
    if s.startswith(("http://", "https://")):
        transport = "sse" if ("/sse" in s) else "http"
        return MCPServerConfig(name=name, type=transport, url=s)

    # ── Stdio command string ──────────────────────────────────────────────
    parts = s.split()
    if not parts:
        raise ValueError("Empty MCP server string")
    return MCPServerConfig(name=name, type="stdio", command=parts[0], args=parts[1:])
