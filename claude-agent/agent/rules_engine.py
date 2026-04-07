"""
Rules Engine — Loads .aidev.yaml + auto-detects project configs.

Builds a structured rules block that gets injected into every Claude prompt.
Works with legacy codebases: reads existing patterns, tsconfig, eslint, prettier.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from rich.console import Console

console = Console()

# ── Default starter template (written by --init-rules) ─────────────────────
_STARTER_YAML = """\
# .aidev.yaml — Project rules for AI Dev Toolkit
# Docs: https://github.com/BaluRaut/ai-dev-toolkit#-project-rules

project:
  name: "{name}"
  type: "frontend"

stack:
  language: "TypeScript 5"
  framework: "React 18"
  ui_library: "Ant Design 6"
  state: "Zustand"
  data_fetching: "TanStack Query v5"
  styling: "styled-components"
  test_runner: "jest"

rules:
  max_lines_per_file: 150
  max_lines_per_function: 40
  max_lines_per_component: 120
  solid:
    single_responsibility: true
    open_closed: true
    liskov_substitution: true
    interface_segregation: true
    dependency_inversion: true
  naming:
    components: "PascalCase"
    hooks: "camelCase with use prefix"
    constants: "SCREAMING_SNAKE_CASE"
    files:
      components: "PascalCase.tsx"
      tests: "__tests__/[name].test.tsx"
  imports:
    no_default_export: true
    barrel_exports: true
  components:
    pattern: "functional"
    error_boundary: true
    loading_state: true
    empty_state: true
    data_testid: true
  error_handling:
    try_catch: "always on async"
  accessibility:
    standard: "WCAG 2.1 AA"
  testing:
    min_coverage: 80
    mock_strategy: "msw"
    snapshot_tests: false

folder_structure:
  pattern: "feature-based"

legacy:
  has_class_components: false
  migration_mode: false
  typescript_strict: true

custom_rules:
  - "Every file must stay under 150 lines"
  - "Follow SOLID principles strictly"
"""


# ── Data classes ────────────────────────────────────────────────────────────

@dataclass
class DetectedConfig:
    """Auto-detected config from the target project."""

    tsconfig: dict = field(default_factory=dict)
    eslint: dict = field(default_factory=dict)
    prettier: dict = field(default_factory=dict)
    package_json: dict = field(default_factory=dict)
    has_src_folder: bool = False
    existing_test_sample: str = ""
    existing_component_sample: str = ""
    # ── Existing integration detection ───────────────────────────────────
    existing_analytics: dict = field(default_factory=dict)   # {lib, sample_code, event_names}
    existing_i18n: dict = field(default_factory=dict)         # {lib, has_t_calls, namespace, locales}
    detected_style_lib: str = ""                              # "styled-components" | "antd" | "css-modules" | "tailwind" | ""


@dataclass
class ProjectRules:
    """Parsed .aidev.yaml plus auto-detected configs."""

    raw: dict = field(default_factory=dict)
    detected: DetectedConfig = field(default_factory=DetectedConfig)
    source_path: str = ""

    # ── Quick accessors ──────────────────────────────────────────────────────

    @property
    def project_name(self) -> str:
        return self.raw.get("project", {}).get("name", "Untitled")

    @property
    def stack(self) -> dict:
        return self.raw.get("stack", {})

    @property
    def rules(self) -> dict:
        return self.raw.get("rules", {})

    @property
    def legacy(self) -> dict:
        return self.raw.get("legacy", {})

    @property
    def folder_layout(self) -> str:
        fs = self.raw.get("folder_structure", {})
        return fs.get("layout", fs.get("pattern", "feature-based"))

    @property
    def custom_rules(self) -> list[str]:
        return self.raw.get("custom_rules", [])


# ── Loader ──────────────────────────────────────────────────────────────────

def _find_aidev_yaml(start: str) -> str | None:
    """Walk up from *start* looking for .aidev.yaml."""
    current = Path(start).resolve()
    for _ in range(10):  # safety cap
        candidate = current / ".aidev.yaml"
        if candidate.is_file():
            return str(candidate)
        if current.parent == current:
            break
        current = current.parent
    return None


def _read_json_safe(path: str) -> dict:
    """Read a JSON file, return {} on any error."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _read_first_lines(path: str, max_lines: int = 60) -> str:
    """Read the first N lines of a file for pattern-matching."""
    try:
        with open(path, "r") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line)
            return "".join(lines)
    except Exception:
        return ""


def _detect_project_configs(project_root: str) -> DetectedConfig:
    """Auto-detect tsconfig, eslint, prettier, package.json, and sample files."""
    root = Path(project_root)
    detected = DetectedConfig()

    # tsconfig
    for name in ("tsconfig.json", "tsconfig.app.json"):
        p = root / name
        if p.is_file():
            detected.tsconfig = _read_json_safe(str(p))
            break

    # eslint
    for name in (".eslintrc.json", ".eslintrc.js", ".eslintrc.yml", "eslint.config.js", "eslint.config.mjs"):
        p = root / name
        if p.is_file():
            if name.endswith(".json"):
                detected.eslint = _read_json_safe(str(p))
            else:
                detected.eslint = {"_file": str(p), "_note": "Non-JSON ESLint config detected"}
            break

    # prettier
    for name in (".prettierrc", ".prettierrc.json", "prettier.config.js"):
        p = root / name
        if p.is_file():
            if name.endswith((".json", ".prettierrc")):
                detected.prettier = _read_json_safe(str(p))
            else:
                detected.prettier = {"_file": str(p)}
            break

    # package.json
    pkg = root / "package.json"
    if pkg.is_file():
        full = _read_json_safe(str(pkg))
        # Keep only what matters for prompts
        detected.package_json = {
            "name": full.get("name", ""),
            "dependencies": list((full.get("dependencies") or {}).keys()),
            "devDependencies": list((full.get("devDependencies") or {}).keys()),
        }

    # src folder
    detected.has_src_folder = (root / "src").is_dir()

    # Sample existing test (for style-matching)
    test_dirs = [root / "src" / "__tests__", root / "tests", root / "test"]
    for td in test_dirs:
        if td.is_dir():
            for f in sorted(td.iterdir()):
                if f.suffix in (".ts", ".tsx") and f.name.endswith((".test.ts", ".test.tsx")):
                    detected.existing_test_sample = _read_first_lines(str(f), 60)
                    break
            if detected.existing_test_sample:
                break

    # Sample existing component
    comp_dirs = [root / "src" / "components", root / "src" / "features"]
    for cd in comp_dirs:
        if cd.is_dir():
            for f in sorted(cd.rglob("*.tsx")):
                if not f.name.startswith("__") and not f.name.endswith(".test.tsx"):
                    detected.existing_component_sample = _read_first_lines(str(f), 60)
                    break
            if detected.existing_component_sample:
                break

    # ── Existing analytics detection ─────────────────────────────────────
    all_deps = set(detected.package_json.get("dependencies", [])) | set(detected.package_json.get("devDependencies", []))
    analytics_info: dict = {}
    if "@amplitude/analytics-browser" in all_deps:
        analytics_info["lib"] = "amplitude"
    elif "mixpanel-browser" in all_deps:
        analytics_info["lib"] = "mixpanel"
    elif "@segment/analytics-next" in all_deps:
        analytics_info["lib"] = "segment"
    elif "react-ga4" in all_deps or "@google-analytics/data" in all_deps:
        analytics_info["lib"] = "google-analytics"

    if analytics_info:
        # Find existing analytics code sample
        analytics_dirs = [
            root / "src" / "analytics", root / "src" / "lib" / "analytics",
            root / "src" / "utils" / "analytics", root / "src" / "tracking",
        ]
        for ad in analytics_dirs:
            if ad.is_dir():
                for f in sorted(ad.iterdir()):
                    if f.suffix in (".ts", ".tsx", ".js"):
                        sample = _read_first_lines(str(f), 80)
                        if sample:
                            analytics_info["sample_code"] = sample
                            analytics_info["sample_file"] = str(f.relative_to(root))
                            break
                if analytics_info.get("sample_code"):
                    break
        detected.existing_analytics = analytics_info

    # ── Existing i18n detection ──────────────────────────────────────────
    i18n_info: dict = {}
    if "react-i18next" in all_deps or "i18next" in all_deps:
        i18n_info["lib"] = "react-i18next"
    elif "next-intl" in all_deps:
        i18n_info["lib"] = "next-intl"
    elif "react-intl" in all_deps or "@formatjs/intl" in all_deps:
        i18n_info["lib"] = "react-intl"

    if i18n_info:
        # Check for existing locale files
        locale_dirs = [root / "public" / "locales", root / "src" / "locales", root / "locales"]
        for ld in locale_dirs:
            if ld.is_dir():
                locales = [d.name for d in ld.iterdir() if d.is_dir() and len(d.name) <= 5]
                if locales:
                    i18n_info["locales"] = locales
                    i18n_info["locale_dir"] = str(ld.relative_to(root))
                    # Read the primary locale file to detect namespace + existing keys
                    en_dir = ld / "en"
                    if en_dir.is_dir():
                        for f in sorted(en_dir.iterdir()):
                            if f.suffix == ".json":
                                i18n_info["namespace"] = f.stem
                                sample = _read_first_lines(str(f), 40)
                                if sample:
                                    i18n_info["existing_keys_sample"] = sample
                                break
                break
        # Check if components already use t() calls
        for ext in ("*.tsx", "*.jsx"):
            for f in (root / "src").rglob(ext) if (root / "src").is_dir() else []:
                try:
                    code = f.read_text(encoding="utf-8", errors="ignore")[:2000]
                    if "useTranslation" in code or 't("' in code or "t('" in code:
                        i18n_info["has_t_calls"] = True
                        break
                except Exception:
                    pass
        detected.existing_i18n = i18n_info

    # ── Existing style library detection ─────────────────────────────────
    if "styled-components" in all_deps:
        detected.detected_style_lib = "styled-components"
    elif "antd" in all_deps and "styled-components" not in all_deps:
        detected.detected_style_lib = "antd"
    elif "tailwindcss" in all_deps:
        detected.detected_style_lib = "tailwind"
    else:
        # Check for CSS modules usage
        for ext in ("*.module.css", "*.module.scss"):
            if any((root / "src").rglob(ext)) if (root / "src").is_dir() else False:
                detected.detected_style_lib = "css-modules"
                break

    return detected


def load_rules(target_path: str) -> ProjectRules:
    """
    Load project rules from .aidev.yaml (searching upward from target_path)
    and auto-detect existing project configs.

    Parameters
    ----------
    target_path : str
        The file or directory the user pointed the agent at (e.g. --review src/Button.tsx).

    Returns
    -------
    ProjectRules with .raw (yaml dict), .detected (auto-discovered configs), .source_path.
    """
    yaml_path = _find_aidev_yaml(target_path)

    raw: dict = {}
    if yaml_path:
        try:
            with open(yaml_path, "r") as f:
                raw = yaml.safe_load(f) or {}
            console.print(f"  [dim]📋 Loaded rules from {yaml_path}[/dim]")
        except Exception as e:
            console.print(f"  [yellow]⚠ Failed to parse .aidev.yaml: {e}[/yellow]")

    # Determine project root for auto-detection
    if yaml_path:
        project_root = str(Path(yaml_path).parent)
    else:
        p = Path(target_path)
        project_root = str(p if p.is_dir() else p.parent)

    detected = _detect_project_configs(project_root)

    return ProjectRules(raw=raw, detected=detected, source_path=yaml_path or "")


# ── Prompt builder ──────────────────────────────────────────────────────────

def build_rules_prompt(rules: ProjectRules) -> str:
    """
    Convert ProjectRules into a structured text block for injection into
    every Claude prompt — before the task-specific instructions.

    Returns empty string if no rules are configured.
    """
    if not rules.raw and not rules.detected.package_json:
        return ""

    sections: list[str] = []
    sections.append("# ⚙️ PROJECT RULES — YOU MUST FOLLOW THESE")
    sections.append("The following rules are set by the engineering team. Follow them exactly.\n")

    # ── Stack ────────────────────────────────────────────────────────────────
    stack = rules.stack
    if stack:
        lines = [f"- **{k.replace('_', ' ').title()}:** {v}" for k, v in stack.items() if v]
        if lines:
            sections.append("## Tech Stack\n" + "\n".join(lines))

    # ── File limits ──────────────────────────────────────────────────────────
    r = rules.rules
    limits = []
    if r.get("max_lines_per_file"):
        limits.append(f"- **Max lines per file:** {r['max_lines_per_file']} — split into sub-modules if exceeded")
    if r.get("max_lines_per_function"):
        limits.append(f"- **Max lines per function:** {r['max_lines_per_function']} — extract helpers above this")
    if r.get("max_lines_per_component"):
        limits.append(f"- **Max lines per component:** {r['max_lines_per_component']} — split into sub-components")
    if limits:
        sections.append("## File Length Limits\n" + "\n".join(limits))

    # ── SOLID ────────────────────────────────────────────────────────────────
    solid = r.get("solid", {})
    if solid:
        active = [k.replace("_", " ").title() for k, v in solid.items() if v]
        if active:
            sections.append(
                "## SOLID Principles — ENFORCED\n"
                + "\n".join(f"- ✅ **{p}**" for p in active)
                + "\n- Every file must have ONE clear responsibility."
                + "\n- Prefer composition over inheritance."
                + "\n- Depend on interfaces/types, not concrete implementations."
            )

    # ── Naming ───────────────────────────────────────────────────────────────
    naming = r.get("naming", {})
    if naming:
        lines = []
        for key in ("components", "hooks", "services", "types", "constants"):
            if naming.get(key):
                lines.append(f"- **{key.title()}:** `{naming[key]}`")
        files = naming.get("files", {})
        for key, pattern in files.items():
            lines.append(f"- **{key} files:** `{pattern}`")
        if lines:
            sections.append("## Naming Conventions\n" + "\n".join(lines))

    # ── Import rules ─────────────────────────────────────────────────────────
    imports = r.get("imports", {})
    if imports:
        lines = []
        if imports.get("no_default_export"):
            lines.append("- **NO default exports** — always use named exports (tree-shakable)")
        if imports.get("barrel_exports"):
            lines.append("- **Barrel exports** — every folder gets an index.ts re-export")
        order = imports.get("order")
        if order:
            lines.append("- **Import order:** " + " → ".join(order))
        if lines:
            sections.append("## Import Rules\n" + "\n".join(lines))

    # ── Component rules ──────────────────────────────────────────────────────
    comp = r.get("components", {})
    if comp:
        lines = []
        if comp.get("pattern"):
            lines.append(f"- **Pattern:** {comp['pattern']} components only")
        if comp.get("error_boundary"):
            lines.append("- Every route-level component MUST have an ErrorBoundary")
        if comp.get("loading_state"):
            lines.append("- Every data-fetching component MUST show a loading state")
        if comp.get("empty_state"):
            lines.append("- Every list/table MUST handle the empty-data case")
        if comp.get("data_testid"):
            lines.append("- Every interactive element MUST have a `data-testid` attribute")
        if lines:
            sections.append("## Component Rules\n" + "\n".join(lines))

    # ── Error handling ───────────────────────────────────────────────────────
    err = r.get("error_handling", {})
    if err:
        lines = []
        if err.get("try_catch"):
            lines.append(f"- **try/catch:** {err['try_catch']}")
        if err.get("user_facing_messages"):
            lines.append("- NEVER show raw error objects to users")
        if err.get("retry_strategy"):
            lines.append(f"- **Retry strategy:** {err['retry_strategy']}")
        if lines:
            sections.append("## Error Handling\n" + "\n".join(lines))

    # ── Accessibility ────────────────────────────────────────────────────────
    a11y = r.get("accessibility", {})
    if a11y:
        lines = [f"- **Standard:** {a11y.get('standard', 'WCAG 2.1 AA')}"]
        for key in ("aria_labels", "keyboard_nav", "focus_management", "screen_reader"):
            if a11y.get(key):
                lines.append(f"- ✅ {key.replace('_', ' ').title()}")
        if a11y.get("color_contrast"):
            lines.append(f"- **Min contrast ratio:** {a11y['color_contrast']}")
        sections.append("## Accessibility\n" + "\n".join(lines))

    # ── Testing ──────────────────────────────────────────────────────────────
    test = r.get("testing", {})
    if test:
        lines = []
        if test.get("min_coverage"):
            lines.append(f"- **Min coverage:** {test['min_coverage']}%")
        if test.get("mock_strategy"):
            lines.append(f"- **Mock strategy:** {test['mock_strategy']}")
        if test.get("snapshot_tests") is False:
            lines.append("- ❌ NO snapshot tests (fragile, hard to review)")
        if test.get("test_user_events"):
            lines.append("- Use `@testing-library/user-event`, not `fireEvent`")
        if lines:
            sections.append("## Testing Rules\n" + "\n".join(lines))

    # ── Folder structure ─────────────────────────────────────────────────────
    layout = rules.folder_layout
    if layout and len(layout) > 20:  # has a tree diagram
        sections.append(f"## Folder Structure — FOLLOW THIS LAYOUT\n```\n{layout.strip()}\n```")

    # ── Legacy codebase flags ────────────────────────────────────────────────
    leg = rules.legacy
    if leg:
        active_flags = []
        if leg.get("has_class_components"):
            active_flags.append("- ⚠️ **Class components exist** — do NOT refactor them unless asked")
        if leg.get("has_redux_legacy"):
            active_flags.append("- ⚠️ **Legacy Redux** — use connect()/mapStateToProps, not hooks")
        if leg.get("has_enzyme_tests"):
            active_flags.append("- ⚠️ **Enzyme tests exist** — match existing Enzyme patterns")
        if leg.get("has_css_modules"):
            active_flags.append("- ⚠️ **CSS Modules** — use .module.css, not styled-components")
        if leg.get("has_cra"):
            active_flags.append("- ⚠️ **Create React App** — no Vite-only features")
        if leg.get("migration_mode"):
            active_flags.append("- ⚠️ **Migration mode** — backward-compatible code only, no breaking changes")
        if not leg.get("typescript_strict", True):
            active_flags.append("- ⚠️ **TypeScript non-strict** — `any` is tolerated in legacy files")
        if active_flags:
            sections.append("## Legacy Codebase Flags\n" + "\n".join(active_flags))

    # ── Custom rules (free text) ─────────────────────────────────────────────
    custom = rules.custom_rules
    if custom:
        numbered = [f"{i+1}. {rule}" for i, rule in enumerate(custom)]
        sections.append("## Team-Specific Rules — MUST FOLLOW\n" + "\n".join(numbered))

    # ── Auto-detected configs ────────────────────────────────────────────────
    det = rules.detected
    detected_lines = []

    if det.tsconfig:
        co = det.tsconfig.get("compilerOptions", {})
        if co.get("strict"):
            detected_lines.append("- **tsconfig:** strict mode enabled")
        if co.get("paths"):
            aliases = ", ".join(co["paths"].keys())
            detected_lines.append(f"- **Path aliases:** {aliases}")

    if det.prettier:
        p = det.prettier
        parts = []
        if "semi" in p:
            parts.append(f"semi={p['semi']}")
        if "singleQuote" in p:
            parts.append(f"singleQuote={p['singleQuote']}")
        if "tabWidth" in p:
            parts.append(f"tabWidth={p['tabWidth']}")
        if "printWidth" in p:
            parts.append(f"printWidth={p['printWidth']}")
        if parts:
            detected_lines.append(f"- **Prettier:** {', '.join(parts)}")

    if det.package_json.get("dependencies"):
        deps = det.package_json["dependencies"]
        detected_lines.append(f"- **Installed packages:** {', '.join(deps[:20])}")

    if det.detected_style_lib:
        detected_lines.append(f"- **Style library in use:** {det.detected_style_lib} — MATCH THIS, do not introduce a different one")

    if det.existing_analytics:
        lib = det.existing_analytics.get("lib", "unknown")
        detected_lines.append(f"- **Existing analytics:** {lib} — REUSE the existing setup, do not create a new one from scratch")

    if det.existing_i18n:
        lib = det.existing_i18n.get("lib", "unknown")
        locales = det.existing_i18n.get("locales", [])
        detected_lines.append(f"- **Existing i18n:** {lib} — project already uses t() calls, EXTEND don't replace")
        if locales:
            detected_lines.append(f"- **Existing locales:** {', '.join(locales)}")

    if detected_lines:
        sections.append("## Auto-Detected Project Config\n" + "\n".join(detected_lines))

    # ── Sample existing patterns ─────────────────────────────────────────────
    if det.existing_test_sample:
        sections.append(
            "## Existing Test Pattern — MATCH THIS STYLE\n"
            f"```typescript\n{det.existing_test_sample.strip()}\n```"
        )
    if det.existing_component_sample:
        sections.append(
            "## Existing Component Pattern — MATCH THIS STYLE\n"
            f"```typescript\n{det.existing_component_sample.strip()}\n```"
        )

    if det.existing_analytics.get("sample_code"):
        sections.append(
            f"## Existing Analytics Pattern ({det.existing_analytics.get('lib', 'unknown')}) — REUSE THIS\n"
            f"File: `{det.existing_analytics.get('sample_file', '')}`\n"
            f"```typescript\n{det.existing_analytics['sample_code'].strip()}\n```"
        )

    if det.existing_i18n.get("existing_keys_sample"):
        sections.append(
            f"## Existing i18n Keys ({det.existing_i18n.get('lib', 'unknown')}) — EXTEND THIS\n"
            f"```json\n{det.existing_i18n['existing_keys_sample'].strip()}\n```"
        )

    return "\n\n".join(sections) + "\n\n---\n\n"


# ── Init command ────────────────────────────────────────────────────────────

def init_rules_file(target_dir: str) -> str:
    """
    Write a starter .aidev.yaml in the target directory.

    Returns the path of the created file.
    """
    out = Path(target_dir) / ".aidev.yaml"
    name = Path(target_dir).name or "My Project"
    content = _STARTER_YAML.format(name=name)
    out.write_text(content)
    return str(out)
