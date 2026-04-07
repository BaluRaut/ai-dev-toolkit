"""
CI/CD Generator — Creates GitHub Actions workflows.

Generates production-ready CI/CD pipelines that integrate the Claude Agent:
  - PR-based code review (auto-review every PR)
  - Auto-generate tests for changed files
  - Run tests and report results
  - Quality gates (lint, type-check, tests)
"""

from pathlib import Path
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel

console = Console()


# ─────────────────────────────────────────────────
# Workflow Templates
# ─────────────────────────────────────────────────

@dataclass
class WorkflowFile:
    """A single GitHub Actions workflow file."""
    path: str
    content: str
    description: str


def generate_pr_review_workflow() -> WorkflowFile:
    """Generate a GitHub Actions workflow for AI-powered PR review."""
    content = r"""\
# 🤖 AI-Powered PR Review with Claude Agent
# Automatically reviews every PR for bugs, security, and best practices.
#
# Required secrets:
#   ANTHROPIC_API_KEY — Your Anthropic API key

name: "🤖 AI Code Review"

on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - "src/**"
      - "lib/**"
      - "app/**"
      - "components/**"
      - "pages/**"
      - "**/*.ts"
      - "**/*.tsx"
      - "**/*.js"
      - "**/*.jsx"
      - "**/*.py"

permissions:
  contents: read
  pull-requests: write

jobs:
  ai-review:
    name: Claude AI Review
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: 📥 Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for diff

      - name: 🔍 Get changed files
        id: changed
        run: |
          FILES=$(git diff --name-only origin/${{ github.base_ref }}...HEAD -- '*.ts' '*.tsx' '*.js' '*.jsx' '*.py' '*.vue' | head -20)
          echo "files<<EOF" >> $GITHUB_OUTPUT
          echo "$FILES" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
          echo "count=$(echo "$FILES" | grep -c . || true)" >> $GITHUB_OUTPUT

      - name: 🐍 Set up Python
        if: steps.changed.outputs.count > 0
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: 📦 Install Claude Agent
        if: steps.changed.outputs.count > 0
        run: |
          pip install anthropic rich

      - name: 🤖 Run AI Review
        if: steps.changed.outputs.count > 0
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          REVIEW=""
          while IFS= read -r file; do
            [ -z "$file" ] && continue
            echo "📄 Reviewing: $file"
            DIFF=$(git diff origin/${{ github.base_ref }}...HEAD -- "$file")
            CONTENT=$(cat "$file" 2>/dev/null || echo "File not readable")
            
            RESULT=$(python -c "
          import anthropic, sys
          client = anthropic.Anthropic()
          msg = client.messages.create(
              model='claude-sonnet-4-20250514',
              max_tokens=2048,
              messages=[{'role': 'user', 'content': '''Review this code change for bugs, security issues, and improvements.
          Be concise. Use bullet points. Rate severity: 🔴 Critical, 🟡 Warning, 🟢 Good.
          
          File: $file
          
          Diff:
          $DIFF
          
          Full file:
          $CONTENT
          '''}],
          )
          print(msg.content[0].text)
          " 2>&1) || RESULT="⚠️ Review skipped for $file"
            
            REVIEW="$REVIEW
          ### 📄 \`$file\`
          $RESULT
          
          ---
          "
          done <<< "${{ steps.changed.outputs.files }}"
          
          echo "$REVIEW" > /tmp/review.md

      - name: 💬 Post review comment
        if: steps.changed.outputs.count > 0
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            const fs = require('fs');
            const review = fs.readFileSync('/tmp/review.md', 'utf8');
            
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: `## 🤖 Claude AI Code Review\\n\\n${review}\\n\\n---\\n*Powered by [AI Dev Toolkit](https://github.com/BaluRaut/ai-dev-toolkit)*`
            });
"""
    return WorkflowFile(
        path=".github/workflows/ai-review.yml",
        content=content,
        description="AI-powered PR code review using Claude",
    )


def generate_test_generation_workflow() -> WorkflowFile:
    """Generate a workflow that auto-generates tests for new/changed files."""
    content = r"""\
# 🧪 Auto-Generate Tests for Changed Files
# When a PR has files without test coverage, this action generates tests
# and commits them to the PR branch.
#
# Required secrets:
#   ANTHROPIC_API_KEY — Your Anthropic API key

name: "🧪 Auto-Generate Tests"

on:
  pull_request:
    types: [opened, synchronize]
    paths:
      - "src/**"
      - "lib/**"
      - "app/**"

permissions:
  contents: write
  pull-requests: write

jobs:
  generate-tests:
    name: Generate Missing Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15

    steps:
      - name: 📥 Checkout PR branch
        uses: actions/checkout@v4
        with:
          ref: ${{ github.head_ref }}
          fetch-depth: 0

      - name: 🔍 Find files without tests
        id: untested
        run: |
          FILES=""
          for file in $(git diff --name-only origin/${{ github.base_ref }}...HEAD -- 'src/**/*.ts' 'src/**/*.tsx' 'lib/**/*.ts'); do
            # Skip test files, stories, configs
            if [[ "$file" =~ \.(test|spec|stories|config|d)\. ]]; then
              continue
            fi
            # Check if a corresponding test file exists
            TEST_FILE="${file%.*}.test.${file##*.}"
            SPEC_FILE="${file%.*}.spec.${file##*.}"
            if [ ! -f "$TEST_FILE" ] && [ ! -f "$SPEC_FILE" ]; then
              FILES="$FILES$file\\n"
            fi
          done
          echo "files<<EOF" >> $GITHUB_OUTPUT
          echo -e "$FILES" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
          COUNT=$(echo -e "$FILES" | grep -c . || true)
          echo "count=$COUNT" >> $GITHUB_OUTPUT
          echo "📊 Found $COUNT files without tests"

      - name: 🐍 Set up Python
        if: steps.untested.outputs.count > 0
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: 📦 Install dependencies
        if: steps.untested.outputs.count > 0
        run: pip install anthropic rich

      - name: 🤖 Generate tests with Claude
        if: steps.untested.outputs.count > 0
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          while IFS= read -r file; do
            [ -z "$file" ] && continue
            echo "🧪 Generating test for: $file"
            
            CONTENT=$(cat "$file")
            TEST_PATH="${file%.*}.test.${file##*.}"
            
            python -c "
          import anthropic
          client = anthropic.Anthropic()
          content = open('$file').read()
          msg = client.messages.create(
              model='claude-sonnet-4-20250514',
              max_tokens=4096,
              messages=[{'role': 'user', 'content': f'''Generate comprehensive unit tests for this file.
          Use Jest + React Testing Library. Include edge cases. Mock external dependencies.
          Output ONLY the test code, no explanations.

          File: $file
          {content}
          '''}],
          )
          test_code = msg.content[0].text
          # Strip markdown code blocks if present
          if test_code.startswith('\`\`\`'):
              lines = test_code.split('\\n')
              test_code = '\\n'.join(lines[1:-1] if lines[-1].strip() == '\`\`\`' else lines[1:])
          with open('$TEST_PATH', 'w') as f:
              f.write(test_code)
          print(f'  ✅ Generated: $TEST_PATH')
          " 2>&1 || echo "  ⚠️ Skipped: $file"
          done <<< "${{ steps.untested.outputs.files }}"

      - name: 📝 Commit generated tests
        if: steps.untested.outputs.count > 0
        run: |
          git config user.name "Claude AI Agent"
          git config user.email "ai-agent@claude.ai"
          git add -A "*.test.*" "*.spec.*"
          if git diff --staged --quiet; then
            echo "No new tests to commit"
          else
            git commit -m "🧪 Auto-generated tests via Claude AI Agent"
            git push
          fi

      - name: 💬 Comment on PR
        if: steps.untested.outputs.count > 0
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: '🧪 **Auto-Generated Tests**\\n\\nClaude AI Agent detected files without test coverage and generated tests automatically. Please review the latest commit.\\n\\n---\\n*Powered by [AI Dev Toolkit](https://github.com/BaluRaut/ai-dev-toolkit)*'
            });
"""
    return WorkflowFile(
        path=".github/workflows/auto-generate-tests.yml",
        content=content,
        description="Auto-generate unit tests for files without coverage",
    )


def generate_quality_gate_workflow() -> WorkflowFile:
    """Generate a comprehensive quality gate workflow."""
    content = """\
# 🛡️ Quality Gate — Lint + Type Check + Tests
# Runs on every PR and push to main.

name: "🛡️ Quality Gate"

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

permissions:
  contents: read
  pull-requests: write
  checks: write

jobs:
  quality:
    name: Quality Checks
    runs-on: ubuntu-latest
    timeout-minutes: 15

    strategy:
      matrix:
        node-version: [18, 20]

    steps:
      - name: 📥 Checkout
        uses: actions/checkout@v4

      - name: 📦 Setup Node.js ${{ matrix.node-version }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: "npm"

      - name: 📥 Install dependencies
        run: npm ci

      - name: 🔍 Lint
        run: npm run lint --if-present
        continue-on-error: false

      - name: 📝 Type Check
        run: npx tsc --noEmit --pretty
        continue-on-error: false

      - name: 🧪 Unit Tests
        run: npx jest --coverage --ci --reporters=default
        continue-on-error: false

      - name: 🎭 Playwright E2E Tests
        run: |
          npx playwright install --with-deps chromium
          npx playwright test --reporter=line
        continue-on-error: true

      - name: 📊 Upload Coverage
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-node${{ matrix.node-version }}
          path: coverage/

      - name: 📊 Coverage Summary
        if: always() && github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            const fs = require('fs');
            try {
              const summary = JSON.parse(fs.readFileSync('coverage/coverage-summary.json', 'utf8'));
              const total = summary.total;
              const body = `## 📊 Test Coverage Report
              
            | Metric | Coverage |
            |--------|----------|
            | Statements | ${total.statements.pct}% |
            | Branches | ${total.branches.pct}% |
            | Functions | ${total.functions.pct}% |
            | Lines | ${total.lines.pct}% |
            
            ---
            *Node.js ${{ matrix.node-version }}*`;
              
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body
              });
            } catch(e) {
              console.log('No coverage summary found');
            }
"""
    return WorkflowFile(
        path=".github/workflows/quality-gate.yml",
        content=content,
        description="Quality gate with lint, type check, and tests",
    )


# ─────────────────────────────────────────────────
# Generator
# ─────────────────────────────────────────────────

class CIGenerator:
    """Generates GitHub Actions CI/CD workflows."""

    AVAILABLE_WORKFLOWS = {
        "review": ("🔍 AI Code Review", generate_pr_review_workflow),
        "tests": ("🧪 Auto-Generate Tests", generate_test_generation_workflow),
        "quality": ("🛡️ Quality Gate", generate_quality_gate_workflow),
    }

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)

    def generate(self, workflows: list[str] | None = None) -> list[WorkflowFile]:
        """
        Generate specified workflows (or all if none specified).

        Args:
            workflows: List of workflow keys ('review', 'tests', 'quality')
                       If None, generates all.

        Returns:
            List of WorkflowFile objects
        """
        selected = workflows or list(self.AVAILABLE_WORKFLOWS.keys())
        generated = []

        for key in selected:
            if key not in self.AVAILABLE_WORKFLOWS:
                console.print(f"[yellow]⚠️ Unknown workflow: {key}[/yellow]")
                continue

            name, generator_fn = self.AVAILABLE_WORKFLOWS[key]
            workflow = generator_fn()
            generated.append(workflow)

        return generated

    def save(self, workflows: list[WorkflowFile]) -> list[str]:
        """Save workflow files to disk."""
        saved = []

        for wf in workflows:
            path = self.project_dir / wf.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(wf.content)
            saved.append(str(path))
            console.print(f"  [green]✅ {wf.path}[/green] — {wf.description}")

        return saved

    def preview(self, workflows: list[WorkflowFile]):
        """Preview generated workflows."""
        for wf in workflows:
            console.print(f"\n[bold]━━━ 📄 {wf.path} ━━━[/bold]")
            console.print(f"[dim]{wf.description}[/dim]\n")
            lines = wf.content.split("\n")
            for line in lines[:30]:
                console.print(f"  {line}")
            if len(lines) > 30:
                console.print(f"  [dim]... ({len(lines) - 30} more lines)[/dim]")


# ─────────────────────────────────────────────────
# Convenience Function
# ─────────────────────────────────────────────────

def run_ci_generation(
    project_dir: str,
    workflows: list[str] | None = None,
) -> list[str]:
    """
    Generate and save GitHub Actions workflows.

    Args:
        project_dir: Project root (where .github/ should be created)
        workflows: Which workflows to generate (default: all)

    Returns:
        List of saved file paths
    """
    console.print(Panel("[bold]⚙️ GitHub Actions CI/CD Generator[/bold]", style="cyan"))

    generator = CIGenerator(project_dir)
    workflow_files = generator.generate(workflows)

    if not workflow_files:
        console.print("[red]❌ No workflows generated[/red]")
        return []

    console.print(f"\n[bold]Generated {len(workflow_files)} workflow(s):[/bold]")
    generator.preview(workflow_files)

    saved = generator.save(workflow_files)
    console.print(f"\n[bold green]🎉 {len(saved)} CI/CD workflows created![/bold green]")
    console.print("[dim]   💡 Don't forget to add ANTHROPIC_API_KEY to GitHub repo secrets[/dim]")

    return saved
