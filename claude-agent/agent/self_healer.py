"""
Self-Healing Test Loop — The "Agentic Verification" Engine.

After generating code + tests, this module:
  1. Runs the test suite (Jest, Playwright, pytest, etc.)
  2. Captures test failures + error output
  3. Sends failures back to Claude for automatic fixing
  4. Repeats until ALL tests pass (or max retries)

This is the key differentiator: the agent doesn't stop at generation —
it verifies its own work and iterates until correct.
"""

import subprocess
import time
from pathlib import Path
from dataclasses import dataclass, field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from agent.claude_agent import ClaudeAgent, GeneratedFile
from agent.code_generator import CodeGenerator

console = Console()


# ─────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────

@dataclass
class TestResult:
    """Result of a single test run."""
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    failed_tests: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def summary(self) -> str:
        if self.passed:
            return "✅ All tests passed"
        return f"❌ {len(self.failed_tests)} test(s) failed"


@dataclass
class HealingAttempt:
    """Record of one healing iteration."""
    iteration: int
    test_result: TestResult
    fix_applied: bool = False
    files_changed: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────
# Test Runners
# ─────────────────────────────────────────────────

class TestRunner:
    """Runs test commands and parses output."""

    # Supported test frameworks and their commands
    FRAMEWORKS = {
        "jest": {
            "cmd": ["npx", "jest", "--no-coverage", "--verbose", "--forceExit"],
            "install_check": "npx jest --version",
        },
        "vitest": {
            "cmd": ["npx", "vitest", "run", "--reporter=verbose"],
            "install_check": "npx vitest --version",
        },
        "playwright": {
            "cmd": ["npx", "playwright", "test", "--reporter=line"],
            "install_check": "npx playwright --version",
        },
        "pytest": {
            "cmd": ["python", "-m", "pytest", "-v", "--tb=short"],
            "install_check": "python -m pytest --version",
        },
    }

    def __init__(self, project_dir: str, framework: str = "jest"):
        self.project_dir = Path(project_dir)
        self.framework = framework.lower()

    def run(self, test_path: str | None = None, timeout: int = 120) -> TestResult:
        """
        Run the test suite and return structured results.

        Args:
            test_path: Specific test file or pattern (optional)
            timeout: Maximum seconds to wait
        """
        config = self.FRAMEWORKS.get(self.framework)
        if not config:
            console.print(f"[red]❌ Unknown framework: {self.framework}[/red]")
            console.print(f"[dim]   Supported: {', '.join(self.FRAMEWORKS.keys())}[/dim]")
            return TestResult(passed=False, exit_code=-1, stdout="", stderr=f"Unknown framework: {self.framework}")

        cmd = list(config["cmd"])
        if test_path:
            cmd.append(test_path)

        console.print(f"[dim]   Running: {' '.join(cmd)}[/dim]")
        console.print(f"[dim]   Working dir: {self.project_dir}[/dim]")

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._get_env(),
            )

            duration = time.time() - start_time
            passed = result.returncode == 0
            failed_tests = self._parse_failures(result.stdout + result.stderr)

            return TestResult(
                passed=passed,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                failed_tests=failed_tests,
                duration_seconds=duration,
            )

        except subprocess.TimeoutExpired:
            return TestResult(
                passed=False,
                exit_code=-1,
                stdout="",
                stderr=f"Test execution timed out after {timeout}s",
                duration_seconds=timeout,
            )
        except FileNotFoundError:
            return TestResult(
                passed=False,
                exit_code=-1,
                stdout="",
                stderr=f"Command not found. Is {self.framework} installed?",
            )

    def _get_env(self) -> dict:
        """Get environment variables for test execution."""
        import os
        env = os.environ.copy()
        env["CI"] = "true"  # Suppress interactive prompts
        env["NODE_ENV"] = "test"
        return env

    def _parse_failures(self, output: str) -> list[str]:
        """Extract failed test names from output."""
        failures = []
        lines = output.split("\n")

        for i, line in enumerate(lines):
            # Jest / Vitest patterns
            if "FAIL " in line:
                failures.append(line.strip())
            elif "✕" in line or "×" in line or "✗" in line:
                failures.append(line.strip())
            # Playwright patterns
            elif "failed" in line.lower() and ("test" in line.lower() or ".spec" in line.lower()):
                failures.append(line.strip())
            # Pytest patterns
            elif line.strip().startswith("FAILED "):
                failures.append(line.strip())
            # Generic error patterns
            elif "Error:" in line and i > 0:
                context = lines[max(0, i - 1):i + 2]
                failures.append(" | ".join(l.strip() for l in context if l.strip()))

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for f in failures:
            if f not in seen:
                seen.add(f)
                unique.append(f)

        return unique[:20]  # Cap at 20 to avoid huge prompts


# ─────────────────────────────────────────────────
# Self-Healing Engine
# ─────────────────────────────────────────────────

class SelfHealer:
    """
    The Self-Healing Agent Loop:

    1. Run tests
    2. If tests fail → send error output to Claude
    3. Claude generates fixes
    4. Apply fixes
    5. Run tests again
    6. Repeat until pass OR max retries
    """

    def __init__(
        self,
        project_dir: str,
        framework: str = "jest",
        max_retries: int = 3,
        output_dir: str | None = None,
    ):
        self.project_dir = Path(project_dir)
        self.framework = framework
        self.max_retries = max_retries
        self.output_dir = output_dir
        self.runner = TestRunner(project_dir, framework)
        self.agent = ClaudeAgent()
        self.attempts: list[HealingAttempt] = []

    def heal(self, test_path: str | None = None) -> bool:
        """
        Run the self-healing loop.

        Returns True if all tests eventually pass.
        """
        console.print(Panel(
            f"[bold]🔄 Self-Healing Loop[/bold]\n"
            f"Framework: {self.framework} | Max retries: {self.max_retries}\n"
            f"Project: {self.project_dir}",
            style="cyan",
        ))

        for iteration in range(1, self.max_retries + 1):
            console.print(f"\n[bold cyan]━━━ Iteration {iteration}/{self.max_retries} ━━━[/bold cyan]")

            # Step 1: Run tests
            console.print("[bold]🧪 Running tests...[/bold]")
            result = self.runner.run(test_path)

            attempt = HealingAttempt(iteration=iteration, test_result=result)

            # Step 2: Check if passed
            if result.passed:
                console.print(f"\n[bold green]✅ All tests passed on iteration {iteration}![/bold green]")
                console.print(f"[dim]   Duration: {result.duration_seconds:.1f}s[/dim]")
                attempt.fix_applied = False
                self.attempts.append(attempt)
                self._print_summary()
                return True

            # Step 3: Show failures
            console.print(f"[yellow]⚠️ Tests failed (exit code: {result.exit_code})[/yellow]")
            if result.failed_tests:
                for ft in result.failed_tests[:5]:
                    console.print(f"  [red]  • {ft}[/red]")

            if iteration == self.max_retries:
                console.print(f"\n[red]❌ Max retries ({self.max_retries}) reached. Tests still failing.[/red]")
                self.attempts.append(attempt)
                self._print_summary()
                return False

            # Step 4: Ask Claude to fix
            console.print(f"\n[bold cyan]🤖 Asking Claude to fix (attempt {iteration})...[/bold cyan]")

            fix_prompt = self._build_fix_prompt(result)
            files = self.agent.generate_code(fix_prompt)

            if files:
                # Step 5: Apply fixes
                generator = CodeGenerator(output_dir=self.output_dir or str(self.project_dir))
                saved = generator.save_files(files)
                attempt.fix_applied = True
                attempt.files_changed = [f.path for f in files]
                console.print(f"[green]   Applied fixes to {len(saved)} files[/green]")
            else:
                console.print("[yellow]   Claude couldn't generate fixes. Retrying...[/yellow]")
                attempt.fix_applied = False

            self.attempts.append(attempt)

        self._print_summary()
        return False

    def _build_fix_prompt(self, result: TestResult) -> str:
        """Build a prompt asking Claude to fix test failures."""

        # Read relevant source files for context
        source_context = self._gather_source_context(result)

        # Truncate output to avoid token limits
        max_output = 3000
        stdout_truncated = result.stdout[-max_output:] if len(result.stdout) > max_output else result.stdout
        stderr_truncated = result.stderr[-max_output:] if len(result.stderr) > max_output else result.stderr

        return f"""# 🔧 SELF-HEALING: Fix Failing Tests

You are part of an automated self-healing loop. Tests were generated but are failing.
Your job: fix EITHER the implementation code OR the test code (whichever has the bug).

## Test Framework
{self.framework}

## Failed Tests
{chr(10).join(f'- {ft}' for ft in result.failed_tests)}

## Test Output (stdout)
```
{stdout_truncated}
```

## Test Errors (stderr)
```
{stderr_truncated}
```

## Source Files Context
{source_context}

## Rules
1. ONLY output the files that need to change — don't regenerate everything
2. If the test expectation is wrong, fix the TEST
3. If the implementation has a bug, fix the IMPLEMENTATION
4. Keep changes minimal and focused
5. Make sure imports are correct
6. Use ===FILE: path=== and ===END FILE=== markers for each file

Fix the failing tests now.
"""

    def _gather_source_context(self, result: TestResult) -> str:
        """Read source files mentioned in test errors for context."""
        context_parts = []
        mentioned_files = set()

        # Extract file paths from error output
        combined = result.stdout + result.stderr
        for line in combined.split("\n"):
            # Match common patterns: src/xxx.ts, ./components/xxx.tsx, etc.
            import re
            paths = re.findall(r'(?:src|components|pages|lib|utils|hooks|services|tests?|__tests__|e2e)[/\\]\S+\.\w+', line)
            for p in paths:
                clean = p.split(":")[0].split("(")[0].strip("'\"")
                mentioned_files.add(clean)

        # Read up to 5 relevant files
        for rel_path in list(mentioned_files)[:5]:
            full_path = self.project_dir / rel_path
            if full_path.exists() and full_path.is_file():
                try:
                    content = full_path.read_text()
                    if len(content) > 3000:
                        content = content[:3000] + "\n// ... (truncated)"
                    context_parts.append(f"### {rel_path}\n```\n{content}\n```")
                except Exception:
                    pass

        return "\n\n".join(context_parts) if context_parts else "(No source files could be read)"

    def _print_summary(self):
        """Print a summary table of all healing attempts."""
        console.print("\n")
        table = Table(title="🔄 Self-Healing Summary", show_header=True, header_style="bold cyan")
        table.add_column("Iteration", justify="center")
        table.add_column("Status")
        table.add_column("Duration")
        table.add_column("Files Fixed")
        table.add_column("Failures")

        for a in self.attempts:
            status = "[green]✅ Passed[/green]" if a.test_result.passed else "[red]❌ Failed[/red]"
            duration = f"{a.test_result.duration_seconds:.1f}s"
            files = ", ".join(a.files_changed[:3]) if a.files_changed else "—"
            failures = str(len(a.test_result.failed_tests)) if not a.test_result.passed else "0"

            table.add_row(str(a.iteration), status, duration, files, failures)

        console.print(table)


# ─────────────────────────────────────────────────
# Convenience Function
# ─────────────────────────────────────────────────

def run_self_healing(
    project_dir: str,
    framework: str = "jest",
    test_path: str | None = None,
    max_retries: int = 3,
    output_dir: str | None = None,
) -> bool:
    """
    Convenience function to run the self-healing loop.

    Args:
        project_dir: Root of the project with package.json / pyproject.toml
        framework: Test framework (jest, vitest, playwright, pytest)
        test_path: Specific test file to run (optional)
        max_retries: Max Claude fix attempts
        output_dir: Where to save fixed files (defaults to project_dir)

    Returns:
        True if tests eventually pass
    """
    healer = SelfHealer(
        project_dir=project_dir,
        framework=framework,
        max_retries=max_retries,
        output_dir=output_dir,
    )
    return healer.heal(test_path)
