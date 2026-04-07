"""
i18n / Translations Agent — Extracts hardcoded strings and generates a full
react-i18next v14 multilingual integration.

Workflow:
  1. Scans component files for hardcoded human-readable strings in JSX / templates
  2. Uses Claude to extract, organise, and translate every string into the requested locales
  3. Generates the complete i18n integration:

     public/locales/<lang>/translation.json     — One translation file per locale
     src/i18n.ts                                — react-i18next init (HttpBackend, lazy-load)
     src/@types/i18next.d.ts                    — TypeScript namespace for full t() autocomplete
     src/hooks/useAppTranslation.ts             — Typed convenience hook
     src/components/LanguageSwitcher.tsx        — Ant Design 6 locale-switcher dropdown

Supported locales: en, es, fr, de, ja, zh, pt, ar, ko, hi
Install: npm install react-i18next i18next i18next-http-backend i18next-browser-languagedetector
"""

from pathlib import Path
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from agent.claude_agent import ClaudeAgent
from agent.code_generator import CodeGenerator

console = Console()

# ─────────────────────────────────────────────────
# Supported locales catalogue
# ─────────────────────────────────────────────────

SUPPORTED_LOCALES: dict[str, dict] = {
    "en": {"name": "English",              "rtl": False, "flag": "🇬🇧"},
    "es": {"name": "Spanish",              "rtl": False, "flag": "🇪🇸"},
    "fr": {"name": "French",               "rtl": False, "flag": "🇫🇷"},
    "de": {"name": "German",               "rtl": False, "flag": "🇩🇪"},
    "ja": {"name": "Japanese",             "rtl": False, "flag": "🇯🇵"},
    "zh": {"name": "Chinese (Simplified)", "rtl": False, "flag": "🇨🇳"},
    "pt": {"name": "Portuguese",           "rtl": False, "flag": "🇵🇹"},
    "ar": {"name": "Arabic",               "rtl": True,  "flag": "🇸🇦"},
    "ko": {"name": "Korean",               "rtl": False, "flag": "🇰🇷"},
    "hi": {"name": "Hindi",                "rtl": False, "flag": "🇮🇳"},
}

SCAN_EXTENSIONS = {".tsx", ".jsx", ".ts", ".js", ".vue", ".html", ".svelte"}

EXCLUDED_DIRS = frozenset({
    "node_modules", "dist", "build", ".next", ".nuxt",
    "__pycache__", ".turbo", "coverage", ".cache", "out",
    "locales",  # Skip existing locale files
})

# Signals that a file has user-visible text worth extracting
TEXT_SIGNALS = (
    'return (', '>',  # Any JSX with children
    'placeholder=', 'label=', 'title=', 'aria-label=',
    'tooltip', 'helperText', 'description',
)

MAX_SCAN_CHARS = 28_000


# ─────────────────────────────────────────────────
# Component scanner
# ─────────────────────────────────────────────────

def _scan_for_strings(project_dir: Path, max_files: int = 30) -> str:
    """
    Collect representative component code for Claude's string extraction pass.
    Focuses on JSX-heavy files that are most likely to contain user-visible text.
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
                # Prefer files that contain JSX (> chars, return statements) or label strings
                if (
                    "return (" in code or
                    "placeholder=" in code or
                    "label=" in code or
                    "<h1" in code or "<h2" in code or
                    "<p " in code or ">Error" in code
                ):
                    snippet = code[:3_500]
                    chunks.append(f"\n// ─── {file} ───\n{snippet}")
                    total_chars += len(snippet)
                    collected += 1
            except Exception:
                pass

    if not chunks:
        return "(No frontend files found — Claude will generate a generic comprehensive translation template)"

    return "".join(chunks)[:MAX_SCAN_CHARS]


# ─────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────

def _build_i18n_prompt(
    file_scan: str,
    target_locales: list[str],
    namespace: str,
    default_locale: str,
) -> str:
    locale_lines = "\n".join(
        f"  - {code} : {SUPPORTED_LOCALES.get(code, {}).get('name', code)}"
        f"{'  [RTL language — add dir attribute note in comments]' if SUPPORTED_LOCALES.get(code, {}).get('rtl') else ''}"
        for code in target_locales
    )

    return f"""\
You are a senior i18n engineer specialising in react-i18next v14 and multilingual React/Next.js applications.

## Scanned Component Files
{file_scan}

## Target Locales
{locale_lines}

Default locale: {default_locale}
Namespace: {namespace}

## Your Task

### Step 1 — String Extraction
Scan the component code above. Extract EVERY hardcoded human-readable string:
- Text nodes in JSX: `<p>Hello World</p>`
- Attribute strings: `placeholder="Search..."`, `aria-label="Close modal"`, `title="Settings"`
- Template literals with plain text: `` `Welcome, ${{name}}` ``
- Error / success messages: `"Invalid email address"`, `"Saved successfully"`
- Button labels, headings, descriptions, tooltips, empty states, loading states

### Step 2 — Key Naming
Organise keys into a logical namespace hierarchy (snake_case), for example:
```
common.save / common.cancel / common.loading / common.error
auth.sign_in / auth.sign_in_subtitle / auth.email_placeholder
dashboard.title / dashboard.empty_state / dashboard.table.column_name
form.required_field / form.invalid_email / form.submit
```

### Step 3 — Generate Files

#### File 1: public/locales/{default_locale}/{namespace}.json
Complete English source-of-truth JSON. MUST contain every extracted key.
Use nested objects for namespacing. Use {{{{variableName}}}} for interpolations.

#### Files 2–N: public/locales/<lang>/{namespace}.json  (one per additional locale)
One file per requested locale. Translate every key accurately and naturally.
For Arabic (ar): add a top-level comment noting dir="rtl" for the app layout.
For CJK (ja, zh, ko): use appropriate formal register.

#### File N+1: src/i18n.ts
react-i18next v14 + i18next-http-backend setup:
```typescript
import i18n from 'i18next'
import {{ initReactI18next }} from 'react-i18next'
import Backend from 'i18next-http-backend'
import LanguageDetector from 'i18next-browser-languagedetector'

i18n
  .use(Backend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({{
    fallbackLng: '{default_locale}',
    supportedLngs: {target_locales},
    ns: ['{namespace}'],
    defaultNS: '{namespace}',
    backend: {{
      loadPath: '/locales/{{{{lng}}}}/{namespace}.json',
    }},
    interpolation: {{
      escapeValue: false,  // React already escapes
    }},
    detection: {{
      order: ['localStorage', 'navigator', 'htmlTag'],
      caches: ['localStorage'],
    }},
  }})

export default i18n
```

#### File N+2: src/@types/i18next.d.ts
TypeScript declaration file extending i18next DefaultResources with the FULL key structure
from the English translation JSON. This enables t('auth.sign_in') autocomplete everywhere.
```typescript
import type enTranslation from '../../public/locales/en/{namespace}.json'

declare module 'i18next' {{
  interface CustomTypeOptions {{
    defaultNS: '{namespace}'
    resources: {{
      {namespace}: typeof enTranslation
    }}
  }}
}}
```

#### File N+3: src/hooks/useAppTranslation.ts
```typescript
import {{ useTranslation }} from 'react-i18next'

export function useAppTranslation() {{
  const {{ t, i18n }} = useTranslation('{namespace}')
  return {{
    t,
    i18n,
    currentLanguage: i18n.language,
    changeLanguage: (lng: string) => i18n.changeLanguage(lng),
    isRTL: ['ar', 'he', 'fa'].includes(i18n.language),
  }}
}}
```

#### File N+4: src/components/LanguageSwitcher.tsx
Ant Design 6 `Select` component for switching locale at runtime:
- Lists all {len(target_locales)} supported locales with their native names and flag emojis
- Calls `i18n.changeLanguage(value)` on selection
- Persists choice to localStorage (i18next-browser-languagedetector handles this automatically)
- Accessible: proper label, aria-label
- Compact size, works in both light and dark themes via ConfigProvider

Use ===FILE: <path>=== / ===END FILE=== markers for every single file.
All TypeScript must be strict-mode compatible.
"""


# ─────────────────────────────────────────────────
# I18nAgent
# ─────────────────────────────────────────────────

class I18nAgent:
    """
    Scans a frontend project for hardcoded strings and generates a complete
    react-i18next v14 multilingual integration with typed keys.
    """

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.agent = ClaudeAgent()

    def run(
        self,
        target_locales: list[str],
        output_dir: str = ".",
        namespace: str = "translation",
        default_locale: str = "en",
    ) -> None:
        """
        Generate i18n files for the given locales.

        Args:
            target_locales:  List of locale codes e.g. ['en','es','fr','de']
            output_dir:      Root directory where generated files will be saved
            namespace:       i18next namespace (default: 'translation')
            default_locale:  Source-of-truth locale (default: 'en')
        """
        # Validate locales
        valid = [lc for lc in target_locales if lc in SUPPORTED_LOCALES]
        unknown = [lc for lc in target_locales if lc not in SUPPORTED_LOCALES]
        if unknown:
            console.print(f"[yellow]⚠️  Unknown locale codes skipped: {', '.join(unknown)}[/yellow]")
        if not valid:
            console.print("[red]❌ No valid locales specified.[/red]")
            return

        # Ensure default locale is in the list
        if default_locale not in valid:
            valid.insert(0, default_locale)

        # Display locale table
        table = Table(show_header=True, header_style="bold cyan", title="Selected Locales")
        table.add_column("Code", style="bold")
        table.add_column("Language")
        table.add_column("Dir")
        table.add_column("File")

        for code in valid:
            info = SUPPORTED_LOCALES[code]
            table.add_row(
                code,
                f"{info['flag']} {info['name']}",
                "RTL ←" if info["rtl"] else "LTR →",
                f"public/locales/{code}/{namespace}.json",
            )

        console.print(Panel(
            f"[bold]🌍 i18n / Translations Agent[/bold]\n"
            f"  Locales   : [cyan]{', '.join(valid)}[/cyan]\n"
            f"  Namespace : [cyan]{namespace}[/cyan]\n"
            f"  Default   : [cyan]{default_locale}[/cyan]",
            style="cyan",
        ))
        console.print(table)

        # Scan codebase for strings
        console.print("\n[dim]🔍 Scanning components for hardcoded strings...[/dim]")
        scan = _scan_for_strings(self.project_dir)
        console.print(f"[dim]   Context collected: {len(scan):,} chars[/dim]")

        # Build and send prompt
        prompt = _build_i18n_prompt(
            file_scan=scan,
            target_locales=valid,
            namespace=namespace,
            default_locale=default_locale,
        )

        files = self.agent.generate_code(prompt)
        if not files:
            console.print("[red]❌ No files generated.[/red]")
            return

        # Preview + save
        generator = CodeGenerator(output_dir=output_dir)
        generator.preview_files(files)

        if Confirm.ask("\nSave all translation files?", default=True):
            saved = generator.save_files(files)
            console.print(f"\n[bold green]✅ Generated {len(saved)} i18n file(s)[/bold green]")
            for s in saved:
                console.print(f"  [dim]📄 {s}[/dim]")

            # Post-install guidance
            console.print()
            console.print(Panel(
                "[bold cyan]📦 Next Steps[/bold cyan]\n\n"
                "1. Install dependencies:\n"
                "   [dim]npm install react-i18next i18next i18next-http-backend i18next-browser-languagedetector[/dim]\n\n"
                "2. Import i18n in your entry point:\n"
                "   [dim]// src/main.tsx  OR  src/app/layout.tsx[/dim]\n"
                "   [dim]import './i18n'[/dim]\n\n"
                "3. Use the typed hook in components:\n"
                "   [dim]const {{ t }} = useAppTranslation()[/dim]\n"
                "   [dim]<h1>{{t('dashboard.title')}}</h1>[/dim]\n\n"
                "4. Drop <LanguageSwitcher /> anywhere in your navbar\n\n"
                "5. For Next.js App Router, wrap with Suspense:\n"
                "   [dim]<Suspense fallback={{<Loading />}}><YourPage /></Suspense>[/dim]",
                style="cyan",
            ))
        else:
            console.print("[yellow]Files not saved.[/yellow]")


# ─────────────────────────────────────────────────
# Public run helper (called from main.py)
# ─────────────────────────────────────────────────

def run_i18n_agent(
    project_dir: str,
    locales: list[str],
    output_dir: str = ".",
    namespace: str = "translation",
    default_locale: str = "en",
) -> None:
    """Entry point for --add-i18n CLI flag."""
    agent = I18nAgent(project_dir)
    agent.run(
        target_locales=locales,
        output_dir=output_dir,
        namespace=namespace,
        default_locale=default_locale,
    )
