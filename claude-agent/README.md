# 🤖 Claude AI Agent — Jira + Figma + API Docs → Code Generator

A Python program that uses **Claude (Anthropic API)** as an agentic AI to:
1. Fetch your **Jira ticket** details automatically
2. Fetch your **Figma design** data and screenshots
3. Parse your **API/Swagger docs**
4. Combine everything → Send to Claude → **Generate production-ready code**

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd claude-agent
pip install -r requirements.txt
```

### 2. Setup API Keys
```bash
cp .env.example .env
# Edit .env with your actual keys
```

### 3. Run the Agent
```bash
# Full workflow: Jira + Figma + API Docs → Code
python main.py --jira PROJ-123 --figma "https://www.figma.com/file/abc123/MyDesign" --swagger "https://api.example.com/swagger.json"

# Only Jira + API Docs
python main.py --jira PROJ-123 --swagger "https://api.example.com/swagger.json"

# Interactive mode (paste context manually)
python main.py --interactive
```

### 4. ⚡ Set up the `aidev` alias — never type `python main.py` again

Run **once** in your terminal:

```bash
# zsh (macOS default)
echo 'alias aidev="(cd $(pwd) && source ../.venv/bin/activate && python main.py)"' >> ~/.zshrc
source ~/.zshrc

# bash
echo 'alias aidev="(cd $(pwd) && source ../.venv/bin/activate && python main.py)"' >> ~/.bashrc
source ~/.bashrc

# Verify
type aidev
```

Now from **any directory**:

```bash
aidev --jira PROJ-123 --figma "https://www.figma.com/file/abc123" --swagger "https://api.example.com/swagger.json"
aidev --review src/components/UserCard.tsx
aidev --fix "TypeError: Cannot read property of undefined"
aidev --heal ./ --heal-framework jest
aidev --mcp figma --mcp-task "Extract all design tokens"
aidev --costs
```

> The alias wraps the command in `( )` so your working directory never changes.

## 📁 Project Structure
```
claude-agent/
├── main.py                  # Main orchestrator — run this
├── config.py                # Configuration & environment variables
├── connectors/
│   ├── __init__.py
│   ├── jira_connector.py    # Fetches Jira ticket details
│   ├── figma_connector.py   # Fetches Figma design data & images
│   └── api_docs_parser.py   # Parses Swagger/OpenAPI specs
├── agent/
│   ├── __init__.py
│   ├── claude_agent.py      # Claude API interaction & agent logic
│   └── code_generator.py    # Generates & saves code files
├── templates/
│   └── prompt_template.py   # Prompt templates for Claude
├── output/                  # Generated code goes here
├── requirements.txt
├── .env.example
└── README.md
```

## 🔑 Required API Keys
| Key | Where to Get |
|-----|-------------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys |
| `JIRA_BASE_URL` | Your Jira instance URL |
| `JIRA_EMAIL` | Your Jira login email |
| `JIRA_API_TOKEN` | https://id.atlassian.com/manage-profile/security/api-tokens |
| `FIGMA_ACCESS_TOKEN` | https://www.figma.com/developers/api#access-tokens |
