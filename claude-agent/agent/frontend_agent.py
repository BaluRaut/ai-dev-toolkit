"""
Frontend Agent — UI/Frontend Developer Agentic Workflows.

Covers:
  1. A11y Healer        — Auto-detect and fix WCAG 2.1 AA accessibility violations
  2. Component Matrix   — Generate full component scaffold with Styled-Components or Ant Design 6
                          (Component.tsx + Component.test.tsx + Component.types.ts + index.ts)
  3. Style Refactor     — Migrate inline styles / plain CSS to Styled-Components or AntD 6

All agents use Claude under the hood and produce files you can review before saving.
"""

from pathlib import Path
from typing import Literal
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from agent.claude_agent import ClaudeAgent, GeneratedFile
from agent.code_generator import CodeGenerator

console = Console()

# ─────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────

FRONTEND_EXTENSIONS = {".tsx", ".jsx", ".ts", ".js", ".html", ".vue", ".svelte"}
STYLE_EXTENSIONS = {".css", ".scss", ".less", ".sass"}

EXCLUDED_DIRS = frozenset({
    "node_modules", "dist", "build", ".next", ".nuxt",
    "__pycache__", ".turbo", "coverage", ".cache", "out",
})

StyleLib = Literal["styled-components", "antd"]

COMPONENT_TYPES = {
    "atom": "Small, single-purpose primitive (Button, Badge, Avatar, Chip, Spinner)",
    "molecule": "Composed of atoms (SearchBar, FormField, PricingCard, UserCard, Toast)",
    "organism": "Complex UI section (Navbar, DataTable, ProfileHeader, PricingTable, Sidebar)",
    "page": "Full route/page component (LoginPage, DashboardPage, SettingsPage, OnboardingPage)",
}


# ─────────────────────────────────────────────────
# Helper: file collector
# ─────────────────────────────────────────────────

def _collect_files(root: Path, extensions: set[str], max_files: int = 200) -> list[Path]:
    """Walk a directory tree and return frontend files, excluding common build dirs."""
    found: list[Path] = []
    for ext in extensions:
        for f in root.rglob(f"*{ext}"):
            if any(part in EXCLUDED_DIRS for part in f.parts):
                continue
            found.append(f)
            if len(found) >= max_files:
                return found
    return found


# ═══════════════════════════════════════════════════════════════
# 1. A11y Healer
# ═══════════════════════════════════════════════════════════════

WCAG_CHECKLIST = """\
WCAG 2.1 AA violations to detect and fix:

IMAGES
  - <img> missing alt attribute
  - <img alt=""> used for a meaningful (non-decorative) image
  - <img role="presentation"> without aria-hidden="true"

INTERACTIVE ELEMENTS
  - <button> or <a> with no text, aria-label, or aria-labelledby
  - Icon-only buttons missing aria-label
  - Links with text "click here" or "read more" (non-descriptive)
  - onClick on non-interactive elements (div, span) without role="button" + tabIndex={0}

FORMS
  - <input>, <select>, <textarea> without associated <label> (via htmlFor + id)
  - Form fields missing aria-describedby for error messages
  - Required fields missing aria-required="true"

ARIA
  - Missing role on landmark containers (use <main>, <nav>, <aside>, <header>, <footer>)
  - aria-live missing on dynamic/loading content regions
  - aria-expanded missing on accordions, dropdowns, disclosure widgets
  - aria-controls referencing non-existent IDs

FOCUS MANAGEMENT
  - Modals/dialogs not trapping focus (add aria-modal="true" + focus trap comment)
  - Skip-navigation link absent on page-level components (add comment if applicable)

COLOUR & CONTRAST (flag as code comment only — do not change colours)
  - Low contrast text on coloured backgrounds

KEYBOARD
  - No onKeyDown/onKeyUp companion to onClick handlers on div/span"""


class A11yHealer:
    """
    Scans React/Vue/HTML files for WCAG 2.1 AA violations
    and uses Claude to auto-fix every issue in-place.
    """

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.agent = ClaudeAgent()

    def _heal_file(self, file_path: Path) -> GeneratedFile | None:
        """Send one file to Claude for a full accessibility audit + fix."""
        code = file_path.read_text(encoding="utf-8", errors="ignore")

        prompt = f"""\
You are an expert frontend accessibility engineer specialising in WCAG 2.1 AA compliance.

## File to Audit & Fix
Path: {file_path}

```tsx
{code}
```

## WCAG Checklist
{WCAG_CHECKLIST}

## Instructions
1. Scan every line methodically against the checklist above.
2. Fix ALL accessibility violations directly in the code.
3. For every change add a brief inline comment: // a11y: <reason>
4. Do NOT alter logic, state, styling, or any non-accessibility code.
5. If the file is already fully compliant, return it unchanged.

Output the complete corrected file using this exact format:
===FILE: {file_path}===
<full corrected file content>
===END FILE===
"""
        files = self.agent.generate_code(prompt)
        return files[0] if files else None

    def run(
        self,
        target_file: str | None = None,
        dry_run: bool = False,
    ) -> list[GeneratedFile]:
        """
        Heal all frontend files or a single specified file.

        Args:
            target_file: Path to a specific file (optional; scans whole project otherwise)
            dry_run:     Preview changes only — nothing is written to disk
        """
        paths = [Path(target_file)] if target_file else _collect_files(self.project_dir, FRONTEND_EXTENSIONS)

        console.print(Panel(
            f"[bold]♿️  A11y Healer[/bold]\n"
            f"Scanning [cyan]{len(paths)}[/cyan] file(s) for WCAG 2.1 AA violations\n"
            f"Mode: {'🔍 DRY RUN — no files will be written' if dry_run else '🔧 AUTO-FIX'}",
            style="cyan",
        ))

        fixed_files: list[GeneratedFile] = []

        for i, path in enumerate(paths, 1):
            if not path.exists():
                console.print(f"[red]❌ File not found: {path}[/red]")
                continue

            console.print(f"\n  [dim]({i}/{len(paths)}) Auditing:[/dim] {path.name}")
            fixed = self._heal_file(path)

            if not fixed:
                console.print(f"    [red]⚠️  No response for {path.name}[/red]")
                continue

            original = path.read_text(encoding="utf-8", errors="ignore")
            if fixed.content.strip() != original.strip():
                fixed_files.append(fixed)
                console.print(f"    [yellow]⚠️  Issues found and fixed →[/yellow] {path.name}")
            else:
                console.print(f"    [green]✅ Already accessible:[/green] {path.name}")

        if not fixed_files:
            console.print("\n[bold green]🎉 Perfect score — no accessibility violations found![/bold green]")
            return []

        console.print(f"\n[bold]♿️  Fixed issues in [cyan]{len(fixed_files)}[/cyan] file(s)[/bold]")

        generator = CodeGenerator()
        generator.preview_files(fixed_files)

        if not dry_run:
            if Confirm.ask("\nApply all accessibility fixes?", default=True):
                for gf in fixed_files:
                    out = Path(gf.path)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(gf.content, encoding="utf-8")
                console.print(f"\n[bold green]✅ Applied {len(fixed_files)} accessibility fix(es)[/bold green]")
            else:
                console.print("[yellow]Fixes not applied.[/yellow]")
        else:
            console.print("\n[yellow]DRY RUN — remove --dry-run to write fixes to disk[/yellow]")

        return fixed_files


# ═══════════════════════════════════════════════════════════════
# 2. Component Matrix Generator
# ═══════════════════════════════════════════════════════════════

def _build_component_prompt(
    component_name: str,
    component_type: str,
    description: str,
    style_lib: StyleLib,
    props_hint: str,
) -> str:
    """Build the Claude prompt for generating a full component matrix."""

    style_guide = {
        "styled-components": """\
Use styled-components v6:
- ALL styles must use `styled.xxx` tagged template literals — zero inline style={{}} objects
- Use ThemeProvider-compatible design tokens: `${({ theme }) => theme.colors.primary}`
- Export every styled primitive from the same .tsx file (no separate .styles.ts)
- Use the `css` helper for conditional / responsive styles
- Prefer `styled(ExistingComponent)` over wrapping in a new div""",
        "antd": """\
Use Ant Design 6:
- Import all UI primitives from 'antd' (Button, Form, Input, Select, Table, Card, Tag, Badge…)
- Use `ConfigProvider` theme tokens for any custom colour/spacing
- Use `Space`, `Flex`, and `Row/Col` for layout — no raw CSS grid
- Use `Typography.Title/Text/Paragraph` for all text
- Prefer antd component props (size, type, variant, shape, status) over custom CSS
- Only add custom CSS (via styled-components thin wrapper) when antd props are insufficient""",
    }[style_lib]

    return f"""\
You are a senior React 18 / TypeScript 5 frontend engineer.

## Component to Build
Name        : {component_name}
Type        : {component_type} — {COMPONENT_TYPES.get(component_type, component_type)}
Description : {description}
{f"Props hint  : {props_hint}" if props_hint else ""}

## Tech Stack
- React 18 + TypeScript 5 (strict mode)
- {style_lib.replace("-", " ").title()}

## Style Guide
{style_guide}

## Files to Generate — EXACTLY THESE FOUR

### 1. src/components/{component_name}/{component_name}.tsx
- Strongly typed props using the interface from {component_name}.types.ts
- Fully accessible: correct aria-* attributes, roles, labels, keyboard handlers
- Responsive layout (mobile-first)
- Production quality — NOT a placeholder or skeleton
- Realistic data/labels matching the component description

### 2. src/components/{component_name}/{component_name}.test.tsx
- Vitest + React Testing Library (describe / it / expect)
- vi.mock() for any external imports (router, api calls, i18n, analytics)
- Minimum 6 meaningful test cases:
    • renders without crashing
    • renders all required prop variants
    • user interactions (click, type, submit)
    • accessible via getByRole / getByLabelText
    • shows loading / empty / error states (if applicable)
    • snapshot test for visual regression

### 3. src/components/{component_name}/{component_name}.types.ts
- All exported TypeScript interfaces and enums
- JSDoc comment on every property

### 4. src/components/{component_name}/index.ts
- Barrel export: component, prop types, any sub-components

Use ===FILE: <path>=== / ===END FILE=== markers for every file.
"""


class ComponentMatrixGenerator:
    """
    Generates a full component matrix (4 files) using Styled-Components or Ant Design 6.
    No Storybook.
    """

    def __init__(self):
        self.agent = ClaudeAgent()

    def run(
        self,
        component_name: str,
        description: str,
        style_lib: StyleLib = "styled-components",
        component_type: str = "molecule",
        props_hint: str = "",
        output_dir: str = ".",
    ) -> None:
        console.print(Panel(
            f"[bold]🧩 Component Matrix Generator[/bold]\n"
            f"  Component : [cyan]{component_name}[/cyan]\n"
            f"  Type      : {component_type}   |   Style: [cyan]{style_lib}[/cyan]\n"
            f"  Files     : {component_name}.tsx  ·  {component_name}.test.tsx  ·  "
            f"{component_name}.types.ts  ·  index.ts",
            style="cyan",
        ))

        prompt = _build_component_prompt(
            component_name=component_name,
            component_type=component_type,
            description=description,
            style_lib=style_lib,
            props_hint=props_hint,
        )

        files = self.agent.generate_code(prompt)
        if not files:
            console.print("[red]❌ No files generated.[/red]")
            return

        generator = CodeGenerator(output_dir=output_dir)
        generator.preview_files(files)

        if Confirm.ask("\nSave all component files?", default=True):
            saved = generator.save_files(files)
            console.print(f"\n[bold green]✅ Generated {len(saved)} file(s) for {component_name}[/bold green]")
            for s in saved:
                console.print(f"  [dim]📄 {s}[/dim]")
        else:
            console.print("[yellow]Files not saved.[/yellow]")


# ═══════════════════════════════════════════════════════════════
# 3. Style Refactor Agent
# ═══════════════════════════════════════════════════════════════

def _build_refactor_prompt(file_path: str, code: str, target: StyleLib) -> str:
    target_guidance = {
        "styled-components": """\
Migrate ALL inline `style={{...}}` objects and any plain className CSS references to
styled-components v6 tagged template literals within the same .tsx / .jsx file.
- Create a `const S = { ... }` namespace of styled primitives at the bottom of the file
- Reference them as `<S.Container>`, `<S.Title>` etc. in the JSX
- Zero `style={{...}}` objects must remain after the migration""",
        "antd": """\
Migrate ALL inline `style={{...}}` objects to equivalent Ant Design 6 component props
(size, type, variant, style tokens, Space / Flex layout).
- Replace hand-rolled layouts with `Space` / `Flex` / `Row + Col` from antd
- Replace custom text elements with `Typography.Title / Text / Paragraph`
- Replace custom buttons with `Button` from antd (type="primary" etc.)
- Only keep a `style={{...}}` if there is absolutely no antd prop equivalent""",
    }[target]

    return f"""\
You are a senior React/TypeScript engineer specialising in UI library migrations.

## File to Refactor
Path: {file_path}

```tsx
{code}
```

## Migration Target
{target_guidance}

## Strict Rules
- Preserve ALL logic, state, hooks, and event handlers exactly — do not refactor them
- Preserve all accessibility attributes (aria-*, role, tabIndex, htmlFor)
- Preserve all data-testid attributes
- Output must compile: valid TypeScript, no missing imports
- Add a brief inline comment `// refactored: {target}` next to changed blocks

Output the complete refactored file:
===FILE: {file_path}===
<full refactored content>
===END FILE===
"""


class StyleRefactorAgent:
    """
    Scans a project (or a single file) for inline styles and migrates them
    to either Styled-Components v6 or Ant Design 6.
    """

    def __init__(self, project_dir: str, target: StyleLib = "styled-components"):
        self.project_dir = Path(project_dir)
        self.target = target
        self.agent = ClaudeAgent()

    @staticmethod
    def _has_inline_styles(code: str) -> bool:
        return "style={{" in code or 'style="' in code

    def _collect_targets(self, target_file: str | None) -> list[Path]:
        if target_file:
            return [Path(target_file)]
        all_files = _collect_files(self.project_dir, {".tsx", ".jsx", ".ts", ".js"})
        result = []
        for f in all_files:
            try:
                if self._has_inline_styles(f.read_text(encoding="utf-8", errors="ignore")):
                    result.append(f)
            except Exception:
                pass
        return result

    def run(self, target_file: str | None = None, output_dir: str | None = None) -> None:
        paths = self._collect_targets(target_file)

        console.print(Panel(
            f"[bold]🧹 Style Refactor Agent[/bold]\n"
            f"  Target library : [cyan]{self.target}[/cyan]\n"
            f"  Files to process: [cyan]{len(paths)}[/cyan]",
            style="cyan",
        ))

        if not paths:
            console.print("[green]✅ No inline styles found — nothing to refactor![/green]")
            return

        # Show summary table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("File")
        table.add_column("Size")
        for p in paths[:20]:
            table.add_row(str(p.relative_to(self.project_dir)), f"{p.stat().st_size // 1024} KB")
        if len(paths) > 20:
            table.add_row(f"... and {len(paths) - 20} more", "")
        console.print(table)

        if not Confirm.ask(f"\nRefactor {len(paths)} file(s) to {self.target}?", default=True):
            console.print("[yellow]Cancelled.[/yellow]")
            return

        refactored: list[GeneratedFile] = []
        for i, path in enumerate(paths, 1):
            console.print(f"\n  [dim]({i}/{len(paths)}) Refactoring:[/dim] {path.name}")
            code = path.read_text(encoding="utf-8", errors="ignore")
            prompt = _build_refactor_prompt(str(path), code, self.target)
            files = self.agent.generate_code(prompt)
            if files:
                refactored.extend(files)
                console.print(f"    [green]✅ Done[/green]")
            else:
                console.print(f"    [red]❌ No output[/red]")

        if not refactored:
            console.print("[red]❌ No refactored output received.[/red]")
            return

        generator = CodeGenerator(output_dir=output_dir)
        generator.preview_files(refactored)

        if Confirm.ask("\nSave refactored files?", default=True):
            saved = generator.save_files(refactored)
            console.print(f"\n[bold green]✅ Refactored {len(saved)} file(s) → {self.target}[/bold green]")
        else:
            console.print("[yellow]Files not saved.[/yellow]")


# ─────────────────────────────────────────────────
# Public run helpers (called from main.py)
# ─────────────────────────────────────────────────

def run_a11y_heal(
    project_dir: str,
    target_file: str | None = None,
    dry_run: bool = False,
) -> None:
    """Entry point for --heal-a11y CLI flag."""
    healer = A11yHealer(project_dir)
    healer.run(target_file=target_file, dry_run=dry_run)


def run_component_generate(
    component_name: str,
    description: str,
    style_lib: str = "styled-components",
    component_type: str = "molecule",
    output_dir: str = ".",
    props_hint: str = "",
) -> None:
    """Entry point for --new-component CLI flag."""
    gen = ComponentMatrixGenerator()
    gen.run(
        component_name=component_name,
        description=description,
        style_lib=style_lib,  # type: ignore[arg-type]
        component_type=component_type,
        output_dir=output_dir,
        props_hint=props_hint,
    )


def run_style_refactor(
    project_dir: str,
    target: str = "styled-components",
    file: str | None = None,
    output_dir: str | None = None,
) -> None:
    """Entry point for --refactor-styles CLI flag."""
    agent = StyleRefactorAgent(project_dir, target=target)  # type: ignore[arg-type]
    agent.run(target_file=file, output_dir=output_dir)
