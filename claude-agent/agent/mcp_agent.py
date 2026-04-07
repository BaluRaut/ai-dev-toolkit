"""
MCP Agent — Agentic loop: Claude ↔ MCP tools.

Given one or more MCP servers, the agent:
  1. Connects to each server and discovers available tools
  2. Sends the user task + tool schemas to Claude
  3. Claude decides which tools to call
  4. Calls those tools via the MCP servers
  5. Feeds results back to Claude
  6. Repeats until Claude emits a final text response

Supports stdio, SSE, and Streamable HTTP MCP transports.

Usage:
    from agent.mcp_agent import run_mcp_agent
    from connectors.mcp_connector import MCPServerConfig

    result = run_mcp_agent(
        task="Read src/app.tsx and list all exported components",
        servers=[
            MCPServerConfig(
                name="filesystem",
                type="stdio",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "."],
            )
        ],
    )
    print(result.final_answer)
"""

import asyncio
import json
from dataclasses import dataclass, field

import anthropic
from rich.console import Console
from rich.panel import Panel

from config import Config
from agent.token_tracker import TokenTracker
from connectors.mcp_connector import MCPConnector, MCPServerConfig, MCPTool

console = Console()

MAX_ITERATIONS = 20   # hard cap on agentic loop turns


# ─────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────

@dataclass
class MCPRunResult:
    """Summary of a completed MCP agentic run."""

    final_answer: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def summary(self) -> str:
        return (
            f"Iterations: {self.iterations} | "
            f"Tool calls: {len(self.tool_calls)} | "
            f"Tokens: {self.input_tokens + self.output_tokens:,} "
            f"(in {self.input_tokens:,} / out {self.output_tokens:,})"
        )


# ─────────────────────────────────────────────────
# MCPAgent
# ─────────────────────────────────────────────────

class MCPAgent:
    """
    Agentic Claude ↔ MCP tools loop.

    On each turn:
      - Calls Claude with the current messages + all available MCP tool schemas
      - If Claude calls a tool, routes the call to the right MCP server
      - Appends the tool result and loops
      - Stops when Claude produces a final `end_turn` response
    """

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.connector = MCPConnector()
        self.tracker = TokenTracker.instance()

    async def run(
        self,
        task: str,
        servers: list[MCPServerConfig],
        system_prompt: str | None = None,
        verbose: bool = True,
    ) -> MCPRunResult:
        """
        Execute an agentic task using the provided MCP servers.

        Args:
            task:          Natural-language task for Claude to complete.
            servers:       List of MCP server configs to connect to.
            system_prompt: Optional system prompt override.
            verbose:       If True, print tool call details to console.

        Returns:
            MCPRunResult with final_answer, tool_calls, iteration count, tokens.
        """
        result = MCPRunResult()

        # ── Step 1: gather tools from all servers ─────────────────────────
        all_tools: list[MCPTool] = []
        server_map: dict[str, MCPServerConfig] = {}

        for config in servers:
            console.print(
                f"[cyan]🔌 MCP server [bold]{config.name}[/bold]: "
                f"{config.to_display()}[/cyan]"
            )
            try:
                tools = await self.connector.list_tools(config)
                all_tools.extend(tools)
                server_map[config.name] = config
                names = ", ".join(t.name for t in tools) or "(none)"
                console.print(
                    f"[green]   ✅ {len(tools)} tool(s): {names}[/green]"
                )
            except Exception as exc:
                console.print(f"[red]   ❌ Connection failed: {exc}[/red]")

        if not all_tools:
            console.print(
                "[yellow]⚠️  No MCP tools available — "
                "Claude will answer from knowledge only.[/yellow]"
            )

        # ── Step 2: build Claude tool schema + routing map ────────────────
        claude_tools = [t.to_claude_tool() for t in all_tools]

        # Qualified name (server__tool) → (server_config, real_tool_name)
        tool_route: dict[str, tuple[MCPServerConfig, str]] = {
            (f"{t.server_name}__{t.name}" if t.server_name else t.name): (
                server_map[t.server_name],
                t.name,
            )
            for t in all_tools
            if t.server_name in server_map
        }

        # ── Step 3: agentic loop ──────────────────────────────────────────
        system = system_prompt or (
            "You are an expert software engineer with access to MCP tools. "
            "Use the tools to complete the task precisely and thoroughly. "
            "When you have gathered enough information, provide a clear, "
            "well-structured final answer."
        )

        messages: list[dict] = [{"role": "user", "content": task}]

        console.print(Panel(
            f"[bold]🤖 MCP Agentic Loop[/bold]\n"
            f"[dim]Task   :[/dim]  {task[:140]}{'…' if len(task) > 140 else ''}\n"
            f"[dim]Servers:[/dim]  {', '.join(s.name for s in servers) or '(none)'}\n"
            f"[dim]Tools  :[/dim]  {len(claude_tools)}",
            style="cyan",
        ))

        for iteration in range(MAX_ITERATIONS):
            result.iterations = iteration + 1

            response = self.client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=Config.CLAUDE_MAX_TOKENS,
                system=system,
                tools=claude_tools or [],
                messages=messages,
            )

            # Track token usage
            result.input_tokens += response.usage.input_tokens
            result.output_tokens += response.usage.output_tokens
            self.tracker.add(response.usage.input_tokens, response.usage.output_tokens)

            # ── Final answer ──────────────────────────────────────────────
            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        result.final_answer = block.text
                console.print(
                    f"\n[green]✅ Task complete "
                    f"({iteration + 1} iteration(s), "
                    f"{len(result.tool_calls)} tool call(s))[/green]"
                )
                console.print(
                    Panel(result.final_answer, title="Claude's Answer", style="green")
                )
                break

            if response.stop_reason != "tool_use":
                console.print(
                    f"[yellow]⚠️ Unexpected stop reason: {response.stop_reason}[/yellow]"
                )
                break

            # ── Tool calls ────────────────────────────────────────────────
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if not hasattr(block, "type") or block.type != "tool_use":
                    continue

                tool_name: str = block.name
                tool_input: dict = block.input or {}

                if verbose:
                    console.print(
                        f"\n[bold yellow]🔧 Tool:[/bold yellow] "
                        f"[cyan]{tool_name}[/cyan]"
                    )
                    if tool_input:
                        snippet = json.dumps(tool_input, indent=2)[:400]
                        console.print(f"[dim]   {snippet}[/dim]")

                result.tool_calls.append({"tool": tool_name, "input": tool_input})

                # Route → correct MCP server
                if tool_name in tool_route:
                    server_cfg, real_name = tool_route[tool_name]
                    try:
                        output = await self.connector.call_tool(
                            server_cfg, real_name, tool_input
                        )
                        if verbose:
                            preview = output[:400]
                            console.print(
                                f"[dim]   ↩ {preview}"
                                f"{'…' if len(output) > 400 else ''}[/dim]"
                            )
                    except Exception as exc:
                        output = f"Tool error ({real_name}): {exc}"
                        console.print(f"[red]   ❌ {output}[/red]")
                else:
                    output = f"Unknown tool: {tool_name}"
                    console.print(f"[red]   ❌ {output}[/red]")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })

            messages.append({"role": "user", "content": tool_results})

        else:
            console.print(
                f"[yellow]⚠️ Reached max iterations ({MAX_ITERATIONS})[/yellow]"
            )

        return result


# ─────────────────────────────────────────────────
# Sync wrapper (for Click CLI)
# ─────────────────────────────────────────────────

def run_mcp_agent(
    task: str,
    servers: list[MCPServerConfig],
    system_prompt: str | None = None,
    verbose: bool = True,
) -> MCPRunResult:
    """
    Synchronous entry point for running the MCP agent from Click CLI handlers.

    Args:
        task:          Natural-language task for Claude to complete.
        servers:       List of MCPServerConfig objects.
        system_prompt: Optional system prompt override.
        verbose:       Print tool call details (default True).

    Returns:
        MCPRunResult
    """
    agent = MCPAgent()
    return asyncio.run(agent.run(task, servers, system_prompt, verbose))
