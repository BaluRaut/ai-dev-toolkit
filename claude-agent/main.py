#!/usr/bin/env python3
"""
🤖 Claude AI Agent — Main Orchestrator

Connects Jira + Figma + API Docs → Claude → Generated Code

Usage:
    # Full workflow
    python main.py --jira PROJ-123 --figma "https://figma.com/file/abc" --swagger "https://api.com/swagger.json"

    # Just Jira + API
    python main.py --jira PROJ-123 --swagger ./docs/swagger.json

    # Interactive mode
    python main.py --interactive

    # Code review
    python main.py --review src/components/UserProfile.tsx

    # Generate tests
    python main.py --test src/services/userService.ts
"""

import os
import sys
import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from config import Config
from connectors.jira_connector import JiraConnector, create_manual_ticket
from connectors.figma_connector import FigmaConnector, create_manual_design
from connectors.api_docs_parser import ApiDocsParser, create_manual_api_docs
from agent.claude_agent import ClaudeAgent
from agent.code_generator import CodeGenerator
from agent.self_healer import SelfHealer, run_self_healing
from agent.ci_generator import CIGenerator, run_ci_generation
from agent.token_tracker import TokenTracker
from agent.rag_engine import RAGEngine, index_codebase, search_codebase
from agent.frontend_agent import run_a11y_heal, run_component_generate, run_style_refactor
from agent.amplitude_agent import run_amplitude_agent
from agent.i18n_agent import run_i18n_agent, SUPPORTED_LOCALES
from agent.mcp_agent import run_mcp_agent
from connectors.mcp_connector import MCPConnector, parse_server_string, list_presets
from templates.prompt_template import (
    build_full_feature_prompt,
    build_code_review_prompt,
    build_test_generation_prompt,
    build_unit_test_prompt,
    build_playwright_e2e_prompt,
    build_refactor_prompt,
    build_bug_fix_prompt,
)

console = Console()


# ─────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────

BANNER = """
[bold cyan]
╔═══════════════════════════════════════════════════════╗
║          🤖 Claude AI Agent                          ║
║     Jira + Figma + API Docs → Production Code        ║
╚═══════════════════════════════════════════════════════╝
[/bold cyan]"""


# ─────────────────────────────────────────────────
# CLI Commands
# ─────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--jira", "-j", help="Jira ticket key (e.g., PROJ-123)")
@click.option("--figma", "-f", help="Figma file URL or file key")
@click.option("--swagger", "-s", help="Swagger/OpenAPI spec URL or file path")
@click.option("--output", "-o", help="Output directory for generated code")
@click.option("--api-filter", help="Filter API endpoints by path (e.g., /users)")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--review", "-r", help="Code review a file")
@click.option("--test", "-t", help="Generate unit tests for a file")
@click.option("--e2e", help="Generate Playwright E2E tests for a file or folder")
@click.option("--unit-test", "unit_test", help="Generate comprehensive unit tests for a file")
@click.option("--fix", help="Fix a bug (paste error message)")
@click.option("--stack", help="Override tech stack (e.g., 'Vue 3, TypeScript, Pinia')")
@click.option("--no-tests", is_flag=True, help="Skip test generation in full workflow")
@click.option("--base-url", default="http://localhost:3000", help="Base URL for E2E tests")
@click.option("--heal", help="Self-healing loop: run tests and auto-fix (path to project)")
@click.option("--heal-framework", default="jest", help="Test framework for --heal (jest, vitest, playwright, pytest)")
@click.option("--heal-retries", default=3, type=int, help="Max retries for self-healing loop")
@click.option("--ci", "generate_ci", is_flag=True, help="Generate GitHub Actions CI/CD workflows")
@click.option("--index", "index_path", help="Index a codebase for RAG search")
@click.option("--search", "search_query", help="Search indexed codebase (use with --index)")
@click.option("--costs", is_flag=True, help="Show session cost summary")
# ── Frontend Agent flags ───────────────────────────────────────────────────
@click.option("--heal-a11y", "heal_a11y", help="Auto-fix WCAG 2.1 AA issues (path to project or file)")
@click.option("--a11y-file", "a11y_file", help="Target a single file for a11y healing (use with --heal-a11y)")
@click.option("--a11y-dry-run", "a11y_dry_run", is_flag=True, help="Preview a11y fixes without writing to disk")
@click.option("--new-component", "new_component", help="Generate a full component matrix (name, e.g. PricingTable)")
@click.option("--component-desc", "component_desc", help="Description for --new-component")
@click.option("--component-type", "component_type", default="molecule", help="atom | molecule | organism | page")
@click.option("--style-lib", "style_lib", default="styled-components", help="styled-components | antd")
@click.option("--refactor-styles", "refactor_styles", help="Migrate inline styles to styled-components/antd (path to project or file)")
@click.option("--refactor-target", "refactor_target", default="styled-components", help="Target library: styled-components | antd")
@click.option("--add-analytics", "add_analytics", help="Generate Amplitude integration (path to project)")
@click.option("--app-name", "app_name", default="My App", help="App name used in generated analytics (use with --add-analytics)")
@click.option("--env-prefix", "env_prefix", default="NEXT_PUBLIC", help="Env-var prefix: NEXT_PUBLIC | VITE")
@click.option("--add-i18n", "add_i18n", help="Generate i18n/translations integration (path to project)")
@click.option("--locales", "locales", default="en,es,fr,de", help="Comma-separated locale codes e.g. en,es,fr,de,ja")
@click.option("--i18n-ns", "i18n_ns", default="translation", help="i18next namespace (default: translation)")
# ── MCP flags ──────────────────────────────────────────────────────────────
@click.option("--mcp", "mcp_server", help="MCP server: named preset (figma|jira|github|filesystem|git|slack|postgres|search) OR stdio command OR http/sse URL")
@click.option("--mcp-task", "mcp_task", help="Task for the MCP agentic loop (use with --mcp)")
@click.option("--mcp-list", "mcp_list", is_flag=True, help="List all tools exposed by the MCP server (use with --mcp)")
@click.option("--mcp-name", "mcp_name", default="server", help="Friendly name for the MCP server (default: server)")
@click.option("--mcp-presets", "mcp_presets", is_flag=True, help="List all built-in MCP server presets (figma, jira, github, …)")
@click.pass_context
def cli(ctx, jira, figma, swagger, output, api_filter, interactive, review, test, e2e, unit_test, fix, stack, no_tests, base_url, heal, heal_framework, heal_retries, generate_ci, index_path, search_query, costs, heal_a11y, a11y_file, a11y_dry_run, new_component, component_desc, component_type, style_lib, refactor_styles, refactor_target, add_analytics, app_name, env_prefix, add_i18n, locales, i18n_ns, mcp_server, mcp_task, mcp_list, mcp_name, mcp_presets):
    """🤖 Claude AI Agent — Generate production code from Jira + Figma + API Docs."""
    console.print(BANNER)

    # Validate config
    missing = Config.validate()
    if missing:
        console.print(f"[red]❌ Missing required config: {', '.join(missing)}[/red]")
        console.print("[yellow]💡 Copy .env.example to .env and fill in your API keys[/yellow]")
        sys.exit(1)

    # If a subcommand is invoked, skip default behavior
    if ctx.invoked_subcommand:
        return

    # Route to appropriate mode
    if costs:
        TokenTracker.instance().print_session_summary()
    elif interactive:
        run_interactive_mode(stack)
    elif review:
        run_code_review(review)
    elif e2e:
        run_playwright_e2e_generation(e2e, base_url)
    elif unit_test:
        run_unit_test_generation(unit_test)
    elif test:
        run_test_generation(test)
    elif fix:
        run_bug_fix(fix)
    elif heal:
        run_heal_mode(heal, heal_framework, heal_retries)
    elif generate_ci:
        run_ci_mode(output or ".")
    elif index_path and search_query:
        run_rag_search(index_path, search_query)
    elif index_path:
        run_rag_index(index_path)
    # ── Frontend Agent routes ──────────────────────────────────────────────
    elif heal_a11y:
        run_a11y_heal_mode(heal_a11y, a11y_file, a11y_dry_run)
    elif new_component:
        run_new_component_mode(new_component, component_desc, component_type, style_lib, output)
    elif refactor_styles:
        run_refactor_styles_mode(refactor_styles, refactor_target, output)
    elif add_analytics:
        run_add_analytics_mode(add_analytics, app_name, env_prefix, output)
    elif add_i18n:
        run_add_i18n_mode(add_i18n, locales, i18n_ns, output)
    # ── MCP route ──────────────────────────────────────────────────────────
    elif mcp_presets:
        list_presets()
    elif mcp_server and mcp_list:
        run_mcp_list_mode(mcp_server, mcp_name)
    elif mcp_server:
        run_mcp_mode(mcp_server, mcp_task, mcp_name)
    elif jira or figma or swagger:
        run_full_workflow(jira, figma, swagger, output, api_filter, stack, include_tests=not no_tests)
    else:
        # No arguments — show help + quick menu
        show_quick_menu()


# ─────────────────────────────────────────────────
# Full Workflow: Jira + Figma + API → Code
# ─────────────────────────────────────────────────

def run_full_workflow(
    jira_key: str | None,
    figma_url: str | None,
    swagger_source: str | None,
    output_dir: str | None,
    api_filter: str | None,
    tech_stack: str | None,
    include_tests: bool = True,
):
    """Main workflow: Fetch all context → Send to Claude → Save generated code + tests."""

    console.print(Panel("[bold]📋 Step 1/4: Gathering Context[/bold]", style="cyan"))

    # --- JIRA ---
    jira_context = ""
    if jira_key:
        if Config.has_jira():
            connector = JiraConnector()
            ticket = connector.fetch_ticket(jira_key)
        else:
            console.print("[yellow]⚠️ Jira API not configured. Enter ticket details manually:[/yellow]")
            title = Prompt.ask("  Ticket title")
            description = Prompt.ask("  Description")
            acs = Prompt.ask("  Acceptance criteria (comma-separated)")
            ticket = create_manual_ticket(jira_key, title, description, acs)
        jira_context = ticket.to_prompt_context()

    # --- FIGMA ---
    figma_context = ""
    figma_image = None
    if figma_url:
        if Config.has_figma():
            connector = FigmaConnector()
            file_key, node_id = FigmaConnector.parse_figma_url(figma_url)
            design = connector.fetch_design(file_key, node_id)
            figma_context = design.to_prompt_context()
            figma_image = design.image_base64 if design.image_base64 else None
        else:
            console.print("[yellow]⚠️ Figma API not configured. Enter design details manually:[/yellow]")
            description = Prompt.ask("  Describe the UI design")
            image_path = Prompt.ask("  Local screenshot path (or Enter to skip)", default="")
            design = create_manual_design(
                description,
                image_path=image_path if image_path else None,
            )
            figma_context = design.to_prompt_context()
            figma_image = design.image_base64 if design.image_base64 else None

    # --- API DOCS ---
    api_context = ""
    if swagger_source:
        parser = ApiDocsParser()
        api_docs = parser.parse(swagger_source)
        if api_filter:
            api_docs = api_docs.filter_endpoints(path_contains=api_filter)
            console.print(f"[dim]   Filtered to endpoints containing '{api_filter}': {len(api_docs.endpoints)} endpoints[/dim]")
        api_context = api_docs.to_prompt_context()

    # --- Show Summary ---
    console.print(Panel("[bold]📊 Step 2/4: Context Summary[/bold]", style="cyan"))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Source", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row(
        "📋 Jira",
        "✅" if jira_context else "⏭️ Skipped",
        f"{len(jira_context)} chars" if jira_context else "—",
    )
    table.add_row(
        "🎨 Figma",
        "✅ + 📷" if figma_image else ("✅" if figma_context else "⏭️ Skipped"),
        f"{len(figma_context)} chars" if figma_context else "—",
    )
    table.add_row(
        "🔌 API Docs",
        "✅" if api_context else "⏭️ Skipped",
        f"{len(api_context)} chars" if api_context else "—",
    )
    console.print(table)

    if not any([jira_context, figma_context, api_context]):
        console.print("[red]❌ No context provided. Use --jira, --figma, or --swagger[/red]")
        return

    # --- Build Prompt ---
    console.print(Panel("[bold]🧠 Step 3/4: Sending to Claude Agent[/bold]", style="cyan"))

    stack = tech_stack or Config.PROJECT_TECH_STACK
    prompt = build_full_feature_prompt(
        jira_context=jira_context or "(No Jira ticket provided)",
        figma_context=figma_context or "(No Figma design provided)",
        api_context=api_context or "(No API docs provided)",
        tech_stack=stack,
        include_unit_tests=include_tests,
        include_e2e_tests=include_tests,
    )

    if include_tests:
        console.print("[dim]   🧪 Unit tests: ENABLED[/dim]")
        console.print("[dim]   🎭 Playwright E2E tests: ENABLED[/dim]")
    else:
        console.print("[dim]   ⏭️  Tests: SKIPPED (use without --no-tests to include)[/dim]")

    console.print(f"[dim]   Total prompt size: {len(prompt)} characters[/dim]")

    # --- Send to Claude ---
    agent = ClaudeAgent()
    files = agent.generate_code(prompt, image_base64=figma_image)

    if not files:
        console.print("[red]❌ No files generated. Try refining your inputs.[/red]")
        return

    # --- Save Files ---
    console.print(Panel("[bold]💾 Step 4/4: Saving Generated Code[/bold]", style="cyan"))

    generator = CodeGenerator(output_dir=output_dir)

    # Preview first
    if Confirm.ask("Preview files before saving?", default=True):
        generator.preview_files(files)

    if Confirm.ask("\nSave all files?", default=True):
        saved = generator.save_files(files)
        console.print(f"\n[bold green]🎉 Done! {len(saved)} files generated and saved.[/bold green]")
    else:
        console.print("[yellow]Files not saved.[/yellow]")


# ─────────────────────────────────────────────────
# Interactive Mode
# ─────────────────────────────────────────────────

def run_interactive_mode(tech_stack: str | None = None):
    """Interactive mode — paste context manually."""
    console.print(Panel("[bold]🖊️ Interactive Mode[/bold]\nPaste your context step by step.", style="cyan"))

    # Jira
    console.print("\n[bold cyan]📋 JIRA TICKET[/bold cyan]")
    console.print("[dim]Paste your Jira ticket text (title, description, ACs). Press Enter twice to finish.[/dim]")
    jira_text = _multiline_input()

    # Figma
    console.print("\n[bold cyan]🎨 FIGMA DESIGN[/bold cyan]")
    console.print("[dim]Describe the design OR enter a local screenshot path. Press Enter twice to finish.[/dim]")
    figma_text = _multiline_input()

    image_path = Prompt.ask(
        "Local screenshot path (or Enter to skip)", default=""
    )
    figma_image = None
    if image_path:
        design = create_manual_design(figma_text, image_path=image_path)
        figma_image = design.image_base64

    # API Docs
    console.print("\n[bold cyan]🔌 API DOCS[/bold cyan]")
    console.print("[dim]Paste your API endpoints (URL, request, response). Press Enter twice to finish.[/dim]")
    api_text = _multiline_input()

    # Tech stack
    stack = tech_stack or Prompt.ask(
        "Tech stack",
        default=Config.PROJECT_TECH_STACK,
    )

    # Extra instructions
    extra = Prompt.ask("Any extra instructions? (or Enter to skip)", default="")

    # Build prompt
    prompt = build_full_feature_prompt(
        jira_context=f"## 📋 JIRA TICKET\n{jira_text}" if jira_text else "(No Jira ticket)",
        figma_context=f"## 🎨 FIGMA DESIGN\n{figma_text}" if figma_text else "(No design)",
        api_context=f"## 🔌 API ENDPOINTS\n{api_text}" if api_text else "(No API docs)",
        tech_stack=stack,
        extra_instructions=extra,
    )

    # Send to Claude
    agent = ClaudeAgent()
    files = agent.generate_code(prompt, image_base64=figma_image)

    if files:
        generator = CodeGenerator()
        generator.preview_files(files)
        if Confirm.ask("\nSave all files?", default=True):
            output_dir = Prompt.ask("Output directory", default=Config.OUTPUT_DIR)
            generator = CodeGenerator(output_dir=output_dir)
            generator.save_files(files)


# ─────────────────────────────────────────────────
# Code Review Mode
# ─────────────────────────────────────────────────

def run_code_review(file_path: str):
    """Review a file for bugs, security, performance."""
    console.print(Panel(f"[bold]🔍 Code Review: {file_path}[/bold]", style="cyan"))

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]❌ File not found: {file_path}[/red]")
        return

    code = path.read_text()
    prompt = build_code_review_prompt(code)

    agent = ClaudeAgent()
    review = agent.chat(prompt)
    console.print(review)


# ─────────────────────────────────────────────────
# Test Generation Mode
# ─────────────────────────────────────────────────

def run_test_generation(file_path: str):
    """Generate tests for a file."""
    console.print(Panel(f"[bold]🧪 Test Generation: {file_path}[/bold]", style="cyan"))

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]❌ File not found: {file_path}[/red]")
        return

    code = path.read_text()
    framework = Prompt.ask("Test framework", default="Jest + React Testing Library")
    prompt = build_test_generation_prompt(code, framework)

    agent = ClaudeAgent()
    files = agent.generate_code(prompt)

    if files:
        generator = CodeGenerator()
        generator.preview_files(files)
        if Confirm.ask("\nSave test files?", default=True):
            generator.save_files(files)


# ─────────────────────────────────────────────────
# Playwright E2E Test Generation Mode
# ─────────────────────────────────────────────────

def run_playwright_e2e_generation(source_path: str, base_url: str = "http://localhost:3000"):
    """Generate Playwright E2E tests for a file or folder."""
    console.print(Panel(f"[bold]🎭 Playwright E2E Test Generation: {source_path}[/bold]", style="cyan"))

    path = Path(source_path)
    if not path.exists():
        console.print(f"[red]❌ Path not found: {source_path}[/red]")
        return

    # Collect source code — single file or folder
    source_files = {}
    if path.is_file():
        source_files[path.name] = path.read_text()
    else:
        for ext in ("*.tsx", "*.ts", "*.jsx", "*.js", "*.vue", "*.py"):
            for f in path.rglob(ext):
                if "node_modules" not in str(f) and "__pycache__" not in str(f):
                    try:
                        source_files[str(f.relative_to(path))] = f.read_text()
                    except Exception:
                        pass

    if not source_files:
        console.print("[red]❌ No source files found.[/red]")
        return

    console.print(f"[dim]   Found {len(source_files)} source files[/dim]")

    combined_source = ""
    for name, content in source_files.items():
        combined_source += f"\n\n// ===FILE: {name}===\n{content}\n// ===END FILE==="

    app_description = Prompt.ask(
        "Briefly describe the app/feature to test",
        default="Web application with standard CRUD features",
    )

    prompt = build_playwright_e2e_prompt(
        source_code=combined_source,
        app_description=app_description,
        base_url=base_url,
    )

    console.print(f"[dim]   Prompt size: {len(prompt)} chars | Base URL: {base_url}[/dim]")

    agent = ClaudeAgent()
    files = agent.generate_code(prompt)

    if files:
        generator = CodeGenerator()
        generator.preview_files(files)
        if Confirm.ask("\nSave E2E test files?", default=True):
            output_dir = Prompt.ask("Output directory", default=Config.OUTPUT_DIR)
            generator = CodeGenerator(output_dir=output_dir)
            saved = generator.save_files(files)
            console.print(f"\n[bold green]🎭 {len(saved)} Playwright E2E test files generated![/bold green]")
    else:
        console.print("[red]❌ No E2E test files generated.[/red]")


# ─────────────────────────────────────────────────
# Unit Test Generation Mode (enhanced)
# ─────────────────────────────────────────────────

def run_unit_test_generation(file_path: str):
    """Generate comprehensive unit tests (Jest + RTL) for a file."""
    console.print(Panel(f"[bold]🧪 Unit Test Generation: {file_path}[/bold]", style="cyan"))

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]❌ File not found: {file_path}[/red]")
        return

    code = path.read_text()
    framework = Prompt.ask("Test framework", default="Jest + React Testing Library")

    prompt = build_unit_test_prompt(
        source_code=code,
        file_name=path.name,
        test_framework=framework,
    )

    console.print(f"[dim]   Framework: {framework} | Prompt size: {len(prompt)} chars[/dim]")

    agent = ClaudeAgent()
    files = agent.generate_code(prompt)

    if files:
        generator = CodeGenerator()
        generator.preview_files(files)
        if Confirm.ask("\nSave unit test files?", default=True):
            output_dir = Prompt.ask("Output directory", default=Config.OUTPUT_DIR)
            generator = CodeGenerator(output_dir=output_dir)
            saved = generator.save_files(files)
            console.print(f"\n[bold green]🧪 {len(saved)} unit test files generated![/bold green]")
    else:
        console.print("[red]❌ No unit test files generated.[/red]")


# ─────────────────────────────────────────────────
# Bug Fix Mode
# ─────────────────────────────────────────────────

def run_bug_fix(error_input: str):
    """Debug and fix a bug."""
    console.print(Panel("[bold]🐛 Bug Fix Mode[/bold]", style="cyan"))

    # Check if error_input is a file path
    if os.path.exists(error_input):
        code = Path(error_input).read_text()
        error_message = Prompt.ask("Paste the error message")
    else:
        error_message = error_input
        console.print("[dim]Paste the relevant code (press Enter twice to finish):[/dim]")
        code = _multiline_input()

    prompt = build_bug_fix_prompt(error_message, code)

    agent = ClaudeAgent()
    result = agent.chat(prompt)
    console.print(result)


# ─────────────────────────────────────────────────
# Self-Healing Mode
# ─────────────────────────────────────────────────

def run_heal_mode(project_dir: str, framework: str = "jest", max_retries: int = 3):
    """Run tests → if fail → Claude fixes → repeat until pass."""
    console.print(Panel(
        f"[bold]🔄 Self-Healing Mode[/bold]\n"
        f"Project: {project_dir}\n"
        f"Framework: {framework} | Max retries: {max_retries}",
        style="cyan",
    ))

    test_path = Prompt.ask("Specific test file (or Enter for all)", default="")
    test_path = test_path if test_path else None

    success = run_self_healing(
        project_dir=project_dir,
        framework=framework,
        test_path=test_path,
        max_retries=max_retries,
    )

    if success:
        console.print("\n[bold green]🎉 All tests passing! Self-healing complete.[/bold green]")
    else:
        console.print("\n[bold red]❌ Tests still failing after max retries.[/bold red]")
        console.print("[dim]   💡 Try increasing --heal-retries or manually reviewing the errors[/dim]")


# ─────────────────────────────────────────────────
# CI/CD Generation Mode
# ─────────────────────────────────────────────────

def run_ci_mode(project_dir: str):
    """Generate GitHub Actions CI/CD workflows."""
    console.print(Panel("[bold]⚙️ CI/CD Generator[/bold]", style="cyan"))

    console.print("  Select workflows to generate:")
    console.print("  [bold]1[/bold]. 🔍 AI Code Review (reviews every PR with Claude)")
    console.print("  [bold]2[/bold]. 🧪 Auto-Generate Tests (adds tests for untested files)")
    console.print("  [bold]3[/bold]. 🛡️ Quality Gate (lint + type-check + tests)")
    console.print("  [bold]4[/bold]. 📦 All of the above")

    choice = Prompt.ask("Choice", choices=["1", "2", "3", "4"], default="4")

    workflow_map = {
        "1": ["review"],
        "2": ["tests"],
        "3": ["quality"],
        "4": ["review", "tests", "quality"],
    }

    run_ci_generation(project_dir, workflow_map[choice])


# ─────────────────────────────────────────────────
# RAG Index & Search Modes
# ─────────────────────────────────────────────────

def run_rag_index(project_dir: str):
    """Index a codebase for vector search."""
    console.print(Panel(f"[bold]📚 Indexing Codebase: {project_dir}[/bold]", style="cyan"))
    stats = index_codebase(project_dir)
    if stats.total_chunks > 0:
        console.print(f"\n[bold green]✅ Indexed {stats.total_chunks} chunks from {stats.total_files} files[/bold green]")
        console.print("[dim]   💡 Now search with: python main.py --index <path> --search \"your query\"[/dim]")


def run_rag_search(project_dir: str, query: str):
    """Search the indexed codebase."""
    console.print(Panel(f"[bold]🔍 Searching: \"{query}\"[/bold]", style="cyan"))

    engine = RAGEngine(project_dir)
    stats = engine.get_collection_stats()

    if stats["total_chunks"] == 0:
        console.print("[yellow]⚠️ Codebase not indexed. Indexing now...[/yellow]")
        engine.index()

    results = engine.search(query, top_k=10)
    engine.print_search_results(results)

    # Offer to use results as context for Claude
    if results and Confirm.ask("\nUse these results as context for Claude?", default=False):
        context = engine.search_for_prompt(query)
        instruction = Prompt.ask("What should Claude do with this code?")

        full_prompt = f"""{context}

## Your Task
{instruction}

Generate production-ready code. Use ===FILE: path=== and ===END FILE=== markers.
"""
        agent = ClaudeAgent()
        files = agent.generate_code(full_prompt)

        if files:
            generator = CodeGenerator()
            generator.preview_files(files)
            if Confirm.ask("\nSave files?", default=True):
                output_dir = Prompt.ask("Output directory", default=Config.OUTPUT_DIR)
                generator = CodeGenerator(output_dir=output_dir)
                generator.save_files(files)


# ─────────────────────────────────────────────────
# ♿️  A11y Heal Mode
# ─────────────────────────────────────────────────

def run_a11y_heal_mode(
    project_dir: str,
    target_file: str | None = None,
    dry_run: bool = False,
):
    """Scan + auto-fix WCAG 2.1 AA accessibility violations."""
    console.print(Panel(
        f"[bold]♿️  A11y Healer[/bold]\n"
        f"Project : {project_dir}\n"
        f"Mode    : {'DRY RUN' if dry_run else 'AUTO-FIX'}",
        style="cyan",
    ))
    if not target_file:
        target_file = Prompt.ask(
            "  Target a specific file? (or press Enter to scan whole project)",
            default="",
        ) or None
    run_a11y_heal(project_dir, target_file=target_file, dry_run=dry_run)


# ─────────────────────────────────────────────────
# 🧩  Component Matrix Generator Mode
# ─────────────────────────────────────────────────

def run_new_component_mode(
    component_name: str,
    description: str | None,
    component_type: str = "molecule",
    style_lib: str = "styled-components",
    output_dir: str | None = None,
):
    """Generate a full component matrix: TSX + Tests + Types + Barrel."""
    console.print(Panel(
        f"[bold]🧩 Component Matrix Generator[/bold]\n"
        f"Component : {component_name}  |  Type: {component_type}  |  Style: {style_lib}",
        style="cyan",
    ))

    if not description:
        description = Prompt.ask(f"  Describe the {component_name} component")

    props_hint = Prompt.ask("  Any specific props / variants? (or press Enter to skip)", default="")
    out = output_dir or Prompt.ask("  Output directory", default=".")

    run_component_generate(
        component_name=component_name,
        description=description,
        style_lib=style_lib,
        component_type=component_type,
        output_dir=out,
        props_hint=props_hint,
    )


# ─────────────────────────────────────────────────
# 🧹  Style Refactor Mode
# ─────────────────────────────────────────────────

def run_refactor_styles_mode(
    project_dir: str,
    target_lib: str = "styled-components",
    output_dir: str | None = None,
):
    """Migrate inline styles to styled-components or Ant Design 6."""
    console.print(Panel(
        f"[bold]🧹 Style Refactor Agent[/bold]\n"
        f"Project : {project_dir}  |  Target: {target_lib}",
        style="cyan",
    ))
    single_file = Prompt.ask(
        "  Target a specific file? (or press Enter to scan whole project)",
        default="",
    ) or None
    run_style_refactor(project_dir, target=target_lib, file=single_file, output_dir=output_dir)


# ─────────────────────────────────────────────────
# 📊  Amplitude Analytics Mode
# ─────────────────────────────────────────────────

def run_add_analytics_mode(
    project_dir: str,
    app_name: str = "My App",
    env_prefix: str = "NEXT_PUBLIC",
    output_dir: str | None = None,
):
    """Scan project and generate a full typed Amplitude analytics integration."""
    console.print(Panel(
        f"[bold]📊 Amplitude Analytics Agent[/bold]\n"
        f"Project : {project_dir}",
        style="cyan",
    ))

    if app_name == "My App":
        app_name = Prompt.ask("  App name", default="My App")
    env_prefix = Prompt.ask(
        "  Env prefix (NEXT_PUBLIC for Next.js, VITE for Vite)",
        default=env_prefix,
    )
    analytics_dir = Prompt.ask("  Analytics output directory", default="src/analytics")
    out = output_dir or Prompt.ask("  Root output directory", default=".")

    run_amplitude_agent(
        project_dir=project_dir,
        app_name=app_name,
        output_dir=out,
        analytics_dir=analytics_dir,
        env_prefix=env_prefix,
    )


# ─────────────────────────────────────────────────
# 🌍  i18n / Translations Mode
# ─────────────────────────────────────────────────

def run_add_i18n_mode(
    project_dir: str,
    locales_str: str = "en,es,fr,de",
    namespace: str = "translation",
    output_dir: str | None = None,
):
    """Extract strings and generate a full react-i18next multilingual integration."""
    console.print(Panel(
        f"[bold]🌍 i18n / Translations Agent[/bold]\n"
        f"Project : {project_dir}",
        style="cyan",
    ))

    # Show supported locales as a hint
    locale_hint = "  Available: " + ", ".join(
        f"{code} ({info['name']})" for code, info in list(SUPPORTED_LOCALES.items())
    )
    console.print(f"[dim]{locale_hint}[/dim]")

    locales_input = Prompt.ask(
        "  Comma-separated locale codes",
        default=locales_str,
    )
    locales = [lc.strip() for lc in locales_input.split(",") if lc.strip()]

    ns = Prompt.ask("  i18next namespace", default=namespace)
    out = output_dir or Prompt.ask("  Root output directory", default=".")

    run_i18n_agent(
        project_dir=project_dir,
        locales=locales,
        output_dir=out,
        namespace=ns,
    )


# ─────────────────────────────────────────────────
# 🔌  MCP (Model Context Protocol) Mode
# ─────────────────────────────────────────────────

def run_mcp_mode(
    server_str: str,
    task: str | None = None,
    server_name: str = "server",
) -> None:
    """Connect to an MCP server and run an agentic task."""
    from connectors.mcp_connector import parse_server_string

    config = parse_server_string(server_str, name=server_name)

    console.print(Panel(
        f"[bold]🔌 MCP Agentic Loop[/bold]\n"
        f"Server : [cyan]{server_str}[/cyan]\n"
        f"Name   : {server_name}",
        style="cyan",
    ))

    if not task:
        task = Prompt.ask(
            "Task for Claude (e.g. 'List all React components in src/')",
        )

    run_mcp_agent(task=task, servers=[config])


def run_mcp_list_mode(server_str: str, server_name: str = "server") -> None:
    """List all tools exposed by an MCP server."""
    import asyncio
    from connectors.mcp_connector import MCPConnector, parse_server_string

    config = parse_server_string(server_str, name=server_name)
    connector = MCPConnector()

    console.print(f"[cyan]🔌 Connecting to [bold]{server_name}[/bold]: {server_str}…[/cyan]")

    async def _list():
        tools = await connector.list_tools(config)
        connector.print_tools(tools, server_name)
        try:
            resources = await connector.list_resources(config)
            if resources:
                connector.print_resources(resources, server_name)
        except Exception:
            pass  # Not all servers expose resources

    asyncio.run(_list())


# ─────────────────────────────────────────────────
# Quick Menu (no args)
# ─────────────────────────────────────────────────

def show_quick_menu():
    """Show interactive menu when no arguments provided."""
    console.print(Panel("[bold]What would you like to do?[/bold]", style="cyan"))

    options = {
        "1":  ("\U0001f680 Generate feature (Jira + Figma + API \u2192 Code + Tests)", "interactive"),
        "2":  ("\U0001f50d Review code",                                           "review"),
        "3":  ("\U0001f9ea Generate unit tests",                                   "test"),
        "4":  ("\U0001f3ad Generate Playwright E2E tests",                         "e2e"),
        "5":  ("\U0001f504 Self-healing loop (run tests \u2192 auto-fix)",              "heal"),
        "6":  ("\u2699\ufe0f  Generate CI/CD workflows (GitHub Actions)",            "ci"),
        "7":  ("\U0001f4da Index codebase for RAG search",                         "index"),
        "8":  ("\U0001f50d Search codebase (RAG)",                                 "search"),
        "9":  ("\U0001f41b Fix a bug",                                             "fix"),
        "10": ("\U0001f4b0 Show session costs",                                     "costs"),
        "11": ("\U0001f4cb Fetch Jira ticket only",                                "jira"),
        "12": ("\U0001f3a8 Fetch Figma design only",                               "figma"),
        "13": ("\U0001f50c Parse API docs only",                                   "api"),
        # ── Frontend Agent ───────────────────────────────────────────────────
        "14": ("\u267f\ufe0f  A11y Healer \u2014 auto-fix WCAG 2.1 AA violations",        "a11y"),
        "15": ("\U0001f9e9 New component (Styled-Components / AntD 6)",            "component"),
        "16": ("\U0001f9f9 Refactor inline styles \u2192 Styled-Components / AntD 6",  "refactor"),
        "17": ("\U0001f4ca Generate Amplitude analytics integration",              "analytics"),
        "18": ("\U0001f30d Generate i18n / Translations (react-i18next)",          "i18n"),
        # \u2500\u2500 MCP \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        "19": ("\U0001f50c MCP agent \u2014 Claude + Model Context Protocol tools",      "mcp"),
    }

    for key, (label, _) in options.items():
        console.print(f"  [bold]{key:>2}[/bold]. {label}")

    choice = Prompt.ask("\nChoice", choices=list(options.keys()), default="1")
    _, mode = options[choice]

    if mode == "interactive":
        run_interactive_mode()
    elif mode == "review":
        file_path = Prompt.ask("File to review")
        run_code_review(file_path)
    elif mode == "test":
        file_path = Prompt.ask("File to generate unit tests for")
        run_unit_test_generation(file_path)
    elif mode == "e2e":
        source = Prompt.ask("File or folder to generate E2E tests for")
        base_url = Prompt.ask("Base URL", default="http://localhost:3000")
        run_playwright_e2e_generation(source, base_url)
    elif mode == "heal":
        project = Prompt.ask("Project directory", default=".")
        framework = Prompt.ask("Test framework", default="jest")
        run_heal_mode(project, framework)
    elif mode == "ci":
        project = Prompt.ask("Project directory", default=".")
        run_ci_mode(project)
    elif mode == "index":
        project = Prompt.ask("Project directory to index")
        run_rag_index(project)
    elif mode == "search":
        project = Prompt.ask("Indexed project directory")
        query = Prompt.ask("Search query")
        run_rag_search(project, query)
    elif mode == "fix":
        error = Prompt.ask("Paste error message or file path")
        run_bug_fix(error)
    elif mode == "costs":
        TokenTracker.instance().print_session_summary()
    elif mode == "jira":
        key = Prompt.ask("Jira ticket key (e.g., PROJ-123)")
        if Config.has_jira():
            connector = JiraConnector()
            ticket = connector.fetch_ticket(key)
            console.print(ticket.to_prompt_context())
        else:
            console.print("[yellow]Jira not configured. Add keys to .env[/yellow]")
    elif mode == "figma":
        url = Prompt.ask("Figma URL")
        if Config.has_figma():
            connector = FigmaConnector()
            file_key, node_id = FigmaConnector.parse_figma_url(url)
            design = connector.fetch_design(file_key, node_id)
            console.print(design.to_prompt_context())
        else:
            console.print("[yellow]Figma not configured. Add token to .env[/yellow]")
    elif mode == "api":
        source = Prompt.ask("Swagger URL or file path")
        parser = ApiDocsParser()
        api_docs = parser.parse(source)
        console.print(api_docs.to_prompt_context())
    # ── Frontend Agent menu handlers ────────────────────────────────────────
    elif mode == "a11y":
        project = Prompt.ask("Project directory (or path to a single file)", default=".")
        dry = Confirm.ask("Dry run (preview only)?", default=False)
        run_a11y_heal_mode(project, dry_run=dry)
    elif mode == "component":
        name = Prompt.ask("Component name (PascalCase, e.g. PricingTable)")
        desc = Prompt.ask("Describe the component")
        ctype = Prompt.ask("Type", choices=["atom", "molecule", "organism", "page"], default="molecule")
        lib = Prompt.ask("Style library", choices=["styled-components", "antd"], default="styled-components")
        out = Prompt.ask("Output directory", default=".")
        run_new_component_mode(name, desc, component_type=ctype, style_lib=lib, output_dir=out)
    elif mode == "refactor":
        project = Prompt.ask("Project directory (or single file)", default=".")
        lib = Prompt.ask("Target library", choices=["styled-components", "antd"], default="styled-components")
        run_refactor_styles_mode(project, target_lib=lib)
    elif mode == "analytics":
        project = Prompt.ask("Project directory", default=".")
        run_add_analytics_mode(project)
    elif mode == "i18n":
        project = Prompt.ask("Project directory", default=".")
        run_add_i18n_mode(project)
    # ── MCP menu handler ─────────────────────────────────────────────────
    elif mode == "mcp":
        server = Prompt.ask(
            "MCP server  (stdio: 'npx -y @modelcontextprotocol/server-filesystem .'  "
            "or SSE: 'http://localhost:8080/sse')"
        )
        name = Prompt.ask("Server name", default="server")
        list_only = Confirm.ask("List tools only (no task)?", default=False)
        if list_only:
            run_mcp_list_mode(server, name)
        else:
            task = Prompt.ask("Task for Claude")
            run_mcp_mode(server, task, name)


# ─────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────

def _multiline_input() -> str:
    """Read multi-line input until two consecutive empty lines."""
    lines = []
    empty_count = 0
    while True:
        try:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
                lines.append(line)
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break
    return "\n".join(lines).strip()


# ─────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
