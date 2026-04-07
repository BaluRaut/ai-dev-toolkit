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
@click.pass_context
def cli(ctx, jira, figma, swagger, output, api_filter, interactive, review, test, e2e, unit_test, fix, stack, no_tests, base_url):
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
    if interactive:
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
# Quick Menu (no args)
# ─────────────────────────────────────────────────

def show_quick_menu():
    """Show interactive menu when no arguments provided."""
    console.print(Panel("[bold]What would you like to do?[/bold]", style="cyan"))

    options = {
        "1": ("🚀 Generate feature (Jira + Figma + API → Code + Tests)", "interactive"),
        "2": ("🔍 Review code", "review"),
        "3": ("🧪 Generate unit tests", "test"),
        "4": ("🎭 Generate Playwright E2E tests", "e2e"),
        "5": ("🐛 Fix a bug", "fix"),
        "6": ("📋 Fetch Jira ticket only", "jira"),
        "7": ("🎨 Fetch Figma design only", "figma"),
        "8": ("🔌 Parse API docs only", "api"),
    }

    for key, (label, _) in options.items():
        console.print(f"  [bold]{key}[/bold]. {label}")

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
    elif mode == "fix":
        error = Prompt.ask("Paste error message or file path")
        run_bug_fix(error)
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
