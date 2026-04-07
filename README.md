# 🤖 AI-Powered Development Toolkit

> A complete toolkit for teams to use AI (Claude, Copilot, etc.) across the entire software development lifecycle — from Jira ticket to production code.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

---

## 📦 What's Inside

### 📚 Guides & Playbooks
| Guide | Description |
|-------|-------------|
| [AI Workflow Playbook](AI_WORKFLOW_PLAYBOOK.md) | Complete guide to using AI across Jira → Figma → API Docs → Code → Tests |
| [AI Agents Guide](AI_AGENTS_GUIDE.md) | All AI agents/tools available for dev teams (Copilot, Cursor, Devin, v0, etc.) |
| [Agentic AI Guide](AGENTIC_AI_GUIDE.md) | Deep dive into Agentic AI — how it works, where to use it, time savings |
| [Connect Figma+Jira+API](CONNECT_FIGMA_JIRA_API_TO_AI.md) | Step-by-step guide to feed Figma, Jira, and API docs into AI |

### 🐍 Claude Agent (Python Tool)
| File | Purpose |
|------|---------|
| [claude-agent/](claude-agent/) | Python program that uses Claude API as an agentic coding assistant |
| [main.py](claude-agent/main.py) | CLI orchestrator — run this |
| [connectors/](claude-agent/connectors/) | Jira, Figma, Swagger/OpenAPI connectors |
| [agent/](claude-agent/agent/) | Claude API integration + code file generator |
| [templates/](claude-agent/templates/) | Prompt templates for features, reviews, tests, bug fixes |

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/ai-dev-toolkit.git
cd ai-dev-toolkit
```

### 2. Install Python dependencies
```bash
cd claude-agent
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

### 3. Set up API keys
```bash
cp .env.example .env
# Edit .env with your keys (see below)
```

### 4. Run
```bash
# Interactive mode
python main.py --interactive

# Full workflow: Jira + Figma + API Docs → Code
python main.py --jira PROJ-123 --figma "https://figma.com/file/..." --swagger "https://api.com/swagger.json"

# Code review
python main.py --review src/components/MyComponent.tsx

# Generate tests
python main.py --test src/services/userService.ts

# Just show menu
python main.py
```

---

## 🔑 API Keys Required

| Key | Where to Get |
|-----|-------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) |
| `JIRA_BASE_URL` | Your Jira URL (e.g., `https://company.atlassian.net`) |
| `JIRA_EMAIL` | Your Jira login email |
| `JIRA_API_TOKEN` | [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `FIGMA_ACCESS_TOKEN` | [Figma Developer Tokens](https://www.figma.com/developers/api#access-tokens) |

---

## 🗺️ How It Works

```
┌──────────┐     ┌──────────┐     ┌───────────┐
│  JIRA    │     │  FIGMA   │     │  SWAGGER  │
│  Ticket  │     │  Design  │     │  API Docs │
└────┬─────┘     └────┬─────┘     └─────┬─────┘
     │                │                  │
     │    Python Connectors (auto-fetch) │
     │                │                  │
     └────────────────┼──────────────────┘
                      │
                      ▼
            ┌──────────────────┐
            │   Claude Agent   │
            │  (Anthropic API) │
            └────────┬─────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │   Generated Code       │
        │                        │
        │  ✅ TypeScript types   │
        │  ✅ API services       │
        │  ✅ React components   │
        │  ✅ Custom hooks       │
        │  ✅ Unit tests         │
        │  ✅ Error handling     │
        └────────────────────────┘
```

---

## 🎯 Use Cases

| Mode | Command | Description |
|------|---------|-------------|
| **🚀 Generate Feature** | `--jira --figma --swagger` | Full feature from Jira + Figma + API |
| **🖊️ Interactive** | `--interactive` | Paste context manually |
| **🔍 Code Review** | `--review file.ts` | AI reviews for bugs, security, perf |
| **🧪 Generate Tests** | `--test file.ts` | AI generates comprehensive tests |
| **🐛 Bug Fix** | `--fix "error msg"` | AI debugs and fixes errors |

---

## 🤝 Contributing

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## ⭐ Star this repo if it helped your team!

*Built with AI, for teams using AI. 🤖*
