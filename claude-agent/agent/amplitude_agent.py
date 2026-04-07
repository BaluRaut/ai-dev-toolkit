"""
Amplitude Analytics Agent — Auto-generates a typed, production-ready analytics integration.

Workflow:
  1. Scans the project's component files for user interactions
     (onClick, onSubmit, useEffect page views, route changes, etc.)
  2. Infers a meaningful event catalog from the scanned code
  3. Uses Claude to generate a complete, typed Amplitude SDK v2 integration:

     src/analytics/events.ts         — Typed AMPLITUDE_EVENTS catalog + EventProperties map
     src/analytics/amplitude.ts      — SDK init, typed track(), identify(), setUserId(), reset()
     src/analytics/useTracking.ts    — React hooks: usePageTracking, useButtonTracking,
                                       useFormTracking, useFeatureTracking
     src/analytics/index.ts          — Barrel export

Supports any React / Next.js / Vite project.
Install: npm install @amplitude/analytics-browser
"""

from pathlib import Path
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from agent.claude_agent import ClaudeAgent
from agent.code_generator import CodeGenerator

console = Console()

# ─────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────

SCAN_EXTENSIONS = {".tsx", ".jsx", ".ts", ".js", ".vue"}

EXCLUDED_DIRS = frozenset({
    "node_modules", "dist", "build", ".next", ".nuxt",
    "__pycache__", ".turbo", "coverage", ".cache", "out",
    "analytics",  # Skip the analytics folder itself to avoid self-referencing
})

# Signals that a file contains meaningful user interaction code worth scanning
INTERACTION_SIGNALS = (
    "onClick", "onSubmit", "onChange", "onBlur",
    "useEffect", "useNavigate", "useRouter",
    "return (", "return(<",
)

# Maximum characters of scanned code to include in the prompt
MAX_SCAN_CHARS = 24_000


# ─────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────

def _build_amplitude_prompt(
    component_scan: str,
    app_name: str,
    analytics_dir: str,
    env_var_prefix: str,
    rules_text: str = "",
    existing_analytics: dict | None = None,
) -> str:
    rules_block = f"{rules_text}\n" if rules_text else ""

    # Build existing analytics context
    existing_block = ""
    if existing_analytics:
        lib = existing_analytics.get("lib", "")
        sample = existing_analytics.get("sample_code", "")
        sample_file = existing_analytics.get("sample_file", "")
        existing_block = f"""
## ⚠️ EXISTING ANALYTICS SETUP DETECTED
Library: {lib}
{f'File: {sample_file}' if sample_file else ''}
{f'''Existing analytics code (REUSE this pattern):
```typescript
{sample}
```''' if sample else ''}

**Rules for extending existing analytics:**
- Do NOT generate a new amplitude.ts init file if one already exists
- Do NOT create a new event catalog from scratch — EXTEND the existing one
- Match the existing naming convention for events (e.g., SCREAMING_SNAKE vs camelCase)
- Reuse existing track()/identify() wrapper signatures
- Only add NEW events inferred from the scanned components
- Import from the EXISTING analytics path, not a new one
"""

    return f"""\
{rules_block}You are a senior frontend engineer specialising in product analytics and Amplitude SDK v2 (Browser SDK) integration.
{existing_block}

## Application
Name: {app_name}
Analytics output directory: {analytics_dir}

## Scanned Component Code (representative sample)
{component_scan}

## Your Task
1. Read the component code and infer ALL meaningful user interactions that should be tracked:
   - Page views / route changes
   - Button / CTA clicks
   - Form starts, submissions, and errors
   - Feature usage (tabs, filters, toggles, modal opens)
   - Authentication events (sign-up, login, logout)
   - Errors and retries
   - Any other meaningful engagement events visible in the scanned code

2. Generate a complete, production-ready Amplitude integration.

## Files to Generate

### 1. {analytics_dir}/events.ts
Strongly-typed event catalog:

```typescript
// Pattern to follow — generate real events from the scanned code, NOT just examples
export const AMPLITUDE_EVENTS = {{
  PAGE_VIEWED:        'Page Viewed',
  BUTTON_CLICKED:     'Button Clicked',
  // ... all inferred events
}} as const;

export type AmplitudeEventName = typeof AMPLITUDE_EVENTS[keyof typeof AMPLITUDE_EVENTS];

/** Typed property shapes per event. Every event MUST have an entry. */
export interface EventProperties {{
  [AMPLITUDE_EVENTS.PAGE_VIEWED]:    {{ page_name: string; referrer?: string }};
  [AMPLITUDE_EVENTS.BUTTON_CLICKED]: {{ button_label: string; location: string; variant?: string }};
  // ... all inferred events with their typed properties
}}
```

### 2. {analytics_dir}/amplitude.ts
Full Amplitude SDK v2 initialisation + typed wrapper:
- `import * as amplitude from '@amplitude/analytics-browser'`
- `initAmplitude()` — reads `{env_var_prefix}_AMPLITUDE_API_KEY` from env, sets up session replay config, enables autocapture for page views
- `track<E extends AmplitudeEventName>(event: E, properties: EventProperties[E]): void` — typed wrapper around `amplitude.track()`
- `identify(userId: string, traits?: Record<string, unknown>): void` — sets user identity
- `setUserId(userId: string): void` — shorthand
- `resetUser(): void` — call on logout: `amplitude.reset()`
- `getSessionId(): number | undefined` — expose for support use cases
- Export everything as named exports (no default export)

### 3. {analytics_dir}/useTracking.ts
Four React hooks — all typed, all zero-dependency beyond React + the events module:

```typescript
// usePageTracking — fires PAGE_VIEWED on mount and when pageName changes
export function usePageTracking(pageName: string, properties?: Record<string, unknown>): void

// useButtonTracking — returns a memoised handler
export function useButtonTracking(location: string): {{
  trackClick: (label: string, extra?: Partial<EventProperties[typeof AMPLITUDE_EVENTS.BUTTON_CLICKED]>) => void
}}

// useFormTracking — tracks FORM_STARTED (first field focus), FORM_SUBMITTED, FORM_ERROR
export function useFormTracking(formName: string): {{
  onFieldFocus: () => void
  onSubmit: (extra?: Record<string, unknown>) => void
  onError: (errorMessage: string) => void
}}

// useFeatureTracking — generic hook for tracking feature interactions
export function useFeatureTracking(featureName: string): {{
  trackUsed: (action: string, extra?: Record<string, unknown>) => void
}}
```

### 4. {analytics_dir}/index.ts
Barrel export — re-export everything from events.ts, amplitude.ts, and useTracking.ts.

Use ===FILE: <path>=== / ===END FILE=== markers for every file.
All code must be TypeScript 5 strict-mode compatible and compile without errors.
"""


# ─────────────────────────────────────────────────
# Component scanner
# ─────────────────────────────────────────────────

def _scan_components(project_dir: Path, max_files: int = 25) -> str:
    """
    Walk the project, find component files that contain interaction signals,
    and return a combined string (capped at MAX_SCAN_CHARS) for Claude context.
    """
    chunks: list[str] = []
    total_chars = 0
    collected = 0

    for ext in SCAN_EXTENSIONS:
        for file in project_dir.rglob(f"*{ext}"):
            if any(part in EXCLUDED_DIRS for part in file.parts):
                continue
            if collected >= max_files or total_chars >= MAX_SCAN_CHARS:
                break
            try:
                code = file.read_text(encoding="utf-8", errors="ignore")
                if any(signal in code for signal in INTERACTION_SIGNALS):
                    snippet = code[:3_000]  # Cap per-file to avoid one giant file dominating
                    chunks.append(f"\n// ─── {file} ───\n{snippet}")
                    total_chars += len(snippet)
                    collected += 1
            except Exception:
                pass

    if not chunks:
        return "(No component files found in project — Claude will generate a comprehensive generic template)"

    return "".join(chunks)[:MAX_SCAN_CHARS]


# ─────────────────────────────────────────────────
# AmplitudeAgent
# ─────────────────────────────────────────────────

class AmplitudeAgent:
    """
    Scans a React/Next.js/Vite project for user interactions and generates
    a fully-typed Amplitude SDK v2 analytics integration.
    """

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.agent = ClaudeAgent()

    def run(
        self,
        app_name: str,
        output_dir: str = ".",
        analytics_dir: str = "src/analytics",
        env_prefix: str = "NEXT_PUBLIC",
        rules_text: str = "",
        existing_analytics: dict | None = None,
    ) -> None:
        """
        Generate the full Amplitude integration.

        Args:
            app_name:            Human-readable application name
            output_dir:          Root directory where generated files will be saved
            analytics_dir:       Relative path for analytics files
            env_prefix:          Env var prefix: NEXT_PUBLIC (Next.js) or VITE (Vite)
            rules_text:          Project rules block to prepend to prompt
            existing_analytics:  Auto-detected existing analytics setup info
        """
        console.print(Panel(
            f"[bold]📊 Amplitude Analytics Agent[/bold]\n"
            f"  App         : [cyan]{app_name}[/cyan]\n"
            f"  Output dir  : [cyan]{analytics_dir}[/cyan]\n"
            f"  Env prefix  : [cyan]{env_prefix}_AMPLITUDE_API_KEY[/cyan]",
            style="cyan",
        ))

        console.print("[dim]🔍 Scanning project for user interaction patterns...[/dim]")
        scan = _scan_components(self.project_dir)
        console.print(f"[dim]   Context collected: {len(scan):,} chars[/dim]")

        prompt = _build_amplitude_prompt(
            component_scan=scan,
            app_name=app_name,
            analytics_dir=analytics_dir,
            env_var_prefix=env_prefix,
            rules_text=rules_text,
            existing_analytics=existing_analytics,
        )

        files = self.agent.generate_code(prompt)
        if not files:
            console.print("[red]❌ No files generated.[/red]")
            return

        generator = CodeGenerator(output_dir=output_dir)
        generator.preview_files(files)

        if Confirm.ask("\nSave all Amplitude analytics files?", default=True):
            saved = generator.save_files(files)
            console.print(f"\n[bold green]✅ Generated {len(saved)} analytics file(s)[/bold green]")
            for s in saved:
                console.print(f"  [dim]📄 {s}[/dim]")

            # Post-install instructions
            console.print()
            console.print(Panel(
                "[bold cyan]📦 Next Steps[/bold cyan]\n\n"
                "1. Install the Amplitude SDK:\n"
                "   [dim]npm install @amplitude/analytics-browser[/dim]\n\n"
                "2. Add your API key to .env:\n"
                f"   [dim]{env_prefix}_AMPLITUDE_API_KEY=your_api_key_here[/dim]\n\n"
                "3. Call initAmplitude() in your app entry point:\n"
                "   [dim]// src/main.tsx or src/app/layout.tsx[/dim]\n"
                "   [dim]import {{ initAmplitude }} from './analytics'[/dim]\n"
                "   [dim]initAmplitude()[/dim]\n\n"
                "4. Use hooks in your components:\n"
                "   [dim]const {{ trackClick }} = useButtonTracking('HeroSection')[/dim]\n"
                "   [dim]usePageTracking('Dashboard')",
                style="cyan",
            ))
        else:
            console.print("[yellow]Files not saved.[/yellow]")


# ─────────────────────────────────────────────────
# Public run helper (called from main.py)
# ─────────────────────────────────────────────────

def run_amplitude_agent(
    project_dir: str,
    app_name: str,
    output_dir: str = ".",
    analytics_dir: str = "src/analytics",
    env_prefix: str = "NEXT_PUBLIC",
    rules_text: str = "",
    existing_analytics: dict | None = None,
) -> None:
    """Entry point for --add-analytics CLI flag."""
    agent = AmplitudeAgent(project_dir)
    agent.run(
        app_name=app_name,
        output_dir=output_dir,
        analytics_dir=analytics_dir,
        env_prefix=env_prefix,
        rules_text=rules_text,
        existing_analytics=existing_analytics,
    )
