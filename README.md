# 🤖 AI-Powered Development Toolkit

> A complete **agentic AI toolkit** for teams to ship features using AI across the entire SDLC — from Jira ticket to production code, with auto-generated tests, self-healing loops, CI/CD pipelines, and codebase-aware RAG search.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Claude API](https://img.shields.io/badge/Claude-Sonnet%204-blueviolet)](https://anthropic.com)

---

## 🧠 What Makes This Different

This isn't just a code generator. It's an **agentic system** with 4 unique capabilities:

| Feature | What It Does |
|---------|-------------|
| 🔄 **Self-Healing Loop** | Runs tests after generation → if tests fail → Claude auto-fixes → repeats until ALL tests pass |
| ⚙️ **CI/CD Generator** | Generates GitHub Actions workflows that auto-review PRs and generate missing tests |
| 💰 **Cost Tracker** | Real-time token counting and cost estimation for every Claude API call |
| 📚 **RAG Search** | Index your entire codebase into ChromaDB vectors → semantic search for relevant context |

---

## 📦 What's Inside

### 📚 Guides & Playbooks
| Guide | Description |
|-------|-------------|
| [AI Workflow Playbook](AI_WORKFLOW_PLAYBOOK.md) | Complete guide: Jira → Figma → API Docs → Code → Tests |
| [AI Agents Guide](AI_AGENTS_GUIDE.md) | All AI agents/tools for dev teams (Copilot, Cursor, Devin, v0, etc.) |
| [Agentic AI Guide](AGENTIC_AI_GUIDE.md) | Deep dive into Agentic AI — how it works, time savings |
| [Connect Figma+Jira+API](CONNECT_FIGMA_JIRA_API_TO_AI.md) | Step-by-step guide to feed Figma, Jira, and API docs into AI |

### 🐍 Claude Agent (Python Tool)
| Module | Purpose |
|--------|---------|
| `main.py` | CLI orchestrator with 13 modes |
| `connectors/` | Jira, Figma, Swagger/OpenAPI auto-fetchers |
| `agent/claude_agent.py` | Claude API integration with streaming + vision + **token tracking** |
| `agent/self_healer.py` | 🔄 **Self-healing test loop** — run → fail → fix → repeat |
| `agent/ci_generator.py` | ⚙️ **GitHub Actions generator** — AI review, auto-tests, quality gate |
| `agent/token_tracker.py` | 💰 **Cost monitoring** — per-call and session-wide cost tracking |
| `agent/rag_engine.py` | 📚 **RAG engine** — ChromaDB vector search over your codebase |
| `agent/code_generator.py` | File writer with preview |
| `templates/` | Prompt templates for features, reviews, tests, E2E, bug fixes |

---

## 🚀 Quick Start

### 1. Clone & install
```bash
git clone https://github.com/BaluRaut/ai-dev-toolkit.git
cd ai-dev-toolkit/claude-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set up API keys
```bash
cp .env.example .env
# Edit .env — only ANTHROPIC_API_KEY is required
```

### 3. Run
```bash
python main.py                # Interactive menu
python main.py --interactive  # Step-by-step guided mode
```

### 4. ⚡ Set up the `aidev` alias (recommended)

So you never have to type `python main.py` again — run this **once**:

```bash
# zsh (macOS default)
echo 'alias aidev="(cd /path/to/ai-dev-toolkit/claude-agent && source ../.venv/bin/activate && python main.py)"' >> ~/.zshrc
source ~/.zshrc

# bash
echo 'alias aidev="(cd /path/to/ai-dev-toolkit/claude-agent && source ../.venv/bin/activate && python main.py)"' >> ~/.bashrc
source ~/.bashrc
```

Now from **any directory** in your terminal:

```bash
aidev --jira PROJ-123 --figma https://figma.com/file/abc
aidev --review src/components/CheckoutForm.tsx
aidev --mcp figma --mcp-task "Extract design tokens"
aidev --costs
```

> The alias runs in a subshell `( )` so your current working directory is never changed.

---

## 🎯 All Modes

| Mode | Command | Description |
|------|---------|-------------|
| 🚀 **Generate Feature** | `aidev --jira PROJ-123 --figma <url> --swagger <url>` | Full feature from Jira + Figma + API → Code + Tests |
| 🖊️ **Interactive** | `aidev --interactive` | Paste context manually, step by step |
| 🔍 **Code Review** | `aidev --review src/file.tsx` | AI reviews for bugs, security, performance |
| 🧪 **Unit Tests** | `aidev --unit-test src/file.ts` | Generate Jest + RTL tests with MSW mocking |
| 🎭 **E2E Tests** | `aidev --e2e src/components/` | Generate Playwright E2E tests (Page Object Model) |
| 🐛 **Bug Fix** | `aidev --fix "error message"` | AI debugs and fixes errors |
| 🔄 **Self-Heal** | `aidev --heal ./project --heal-framework jest` | Run tests → auto-fix failures → repeat |
| ⚙️ **CI/CD** | `aidev --ci` | Generate GitHub Actions workflows |
| 📚 **Index** | `aidev --index ./src` | Index codebase into ChromaDB vectors |
| 🔍 **RAG Search** | `aidev --index ./src --search "auth logic"` | Semantic search across codebase |
| 💰 **Costs** | `aidev --costs` | Show session token usage and costs |
| ⏭️ **No Tests** | `aidev --jira PROJ-123 --no-tests` | Generate feature without tests |

> **Tip:** All commands above use the `aidev` alias. Without it, prefix every command with `python main.py` from the `claude-agent/` directory.

---

## 🔄 Self-Healing Loop — The Game Changer

The agent doesn't just generate code — it **verifies its own work**:

```
┌─────────────────┐
│  Generate Code   │
│  + Tests         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│   Run Tests     │────►│  Tests Pass? ✅  │──► Done!
└────────┬────────┘     └──────────────────┘
         │ ❌ Fail
         ▼
┌─────────────────┐
│  Send errors    │
│  back to Claude │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Claude fixes   │
│  the code       │──── Repeat (max 3 retries)
└─────────────────┘
```

```bash
# Self-heal a project using Jest
aidev --heal ./my-react-app --heal-framework jest

# Self-heal with Playwright
aidev --heal ./my-app --heal-framework playwright --heal-retries 5

# Self-heal Python tests
aidev --heal ./my-api --heal-framework pytest
```

---

## ⚙️ CI/CD — GitHub Actions Integration

Auto-generate production-ready workflows:

```bash
aidev --ci
```

Generates 3 workflow files:
| Workflow | File | What It Does |
|----------|------|-------------|
| 🔍 AI Review | `.github/workflows/ai-review.yml` | Claude reviews every PR automatically |
| 🧪 Auto Tests | `.github/workflows/auto-generate-tests.yml` | Generates tests for files without coverage |
| 🛡️ Quality Gate | `.github/workflows/quality-gate.yml` | Lint + TypeCheck + Tests + Coverage report |

> ⚠️ Add `ANTHROPIC_API_KEY` to your GitHub repo Secrets for AI workflows.

---

## 💰 Cost Tracking

Every Claude API call is tracked automatically:

```
   💰 Cost: $0.0234 (1,523 in + 3,891 out = 5,414 tokens) | ⏱️ 12.3s | Session total: $0.0891
```

```bash
# View detailed session summary
aidev --costs
```

Shows a full breakdown: per-call costs, total session cost, cost by mode, token counts.

---

## 📚 RAG Search — Codebase-Aware AI

For large projects, index your codebase so the agent finds context automatically:

```bash
# Step 1: Index your codebase
aidev --index ./src

# Step 2: Search semantically
aidev --index ./src --search "user authentication middleware"

# The agent finds the most relevant code and can use it as context for Claude
```

Uses ChromaDB for vector embeddings. Supports 25+ file types. Skips `node_modules`, `.git`, etc.

---

## 🔑 API Keys

| Key | Required | Where to Get |
|-----|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ Yes | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| `JIRA_BASE_URL` | Optional | Your Jira URL |
| `JIRA_EMAIL` | Optional | Your Jira login email |
| `JIRA_API_TOKEN` | Optional | [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `FIGMA_ACCESS_TOKEN` | Optional | [Figma Developer Tokens](https://www.figma.com/developers/api#access-tokens) |

---

## 🗺️ Architecture

```
┌──────────┐     ┌──────────┐     ┌───────────┐
│  JIRA    │     │  FIGMA   │     │  SWAGGER  │
│  Ticket  │     │  Design  │     │  API Docs │
└────┬─────┘     └────┬─────┘     └─────┬─────┘
     │                │                  │
     └────────────────┼──────────────────┘
                      │
              Python Connectors
                      │
                      ▼
            ┌──────────────────┐
            │   Claude Agent   │◄──── 📚 RAG Context
            │  (Anthropic API) │◄──── 💰 Token Tracker
            └────────┬─────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   Generated Output     │
        │                        │
        │  ✅ TypeScript types   │
        │  ✅ API services       │
        │  ✅ React components   │
        │  ✅ Custom hooks       │
        │  ✅ Unit tests (Jest)  │
        │  ✅ E2E tests (PW)    │
        │  ✅ Error handling     │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │  🔄 Self-Healing Loop  │
        │  Run → Fail → Fix →   │
        │  Repeat until ✅       │
        └────────────────────────┘
```

---

## 🤝 Contributing

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push and open a Pull Request

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## ⭐ Star this repo if it helped your team!

*Built with AI, for teams using AI. 🤖*
