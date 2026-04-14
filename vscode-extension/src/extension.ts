import * as vscode from "vscode";
import { spawn } from "child_process";
import * as path from "path";
import * as fs from "fs";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Resolve the claude-agent/ directory from settings or workspace. */
function getAgentPath(): string {
  const cfg = vscode.workspace.getConfiguration("aidev");
  const explicit = cfg.get<string>("agentPath") || "";
  if (explicit && fs.existsSync(explicit)) return explicit;

  const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!ws) throw new Error("No workspace folder open.");

  // Try common layouts
  const candidates = [
    path.join(ws, "claude-agent"),
    path.join(ws, "ai-dev-toolkit", "claude-agent"),
    ws,
  ];
  for (const c of candidates) {
    if (fs.existsSync(path.join(c, "main.py"))) return c;
  }
  throw new Error(
    'Cannot find claude-agent/main.py. Set "aidev.agentPath" in VS Code settings.'
  );
}

/** Resolve the venv Python executable. */
function getPythonPath(agentDir: string): string {
  const cfg = vscode.workspace.getConfiguration("aidev");
  const explicit = cfg.get<string>("pythonPath") || "";
  if (explicit && fs.existsSync(explicit)) return explicit;

  // Look for .venv one level up (ai-dev-toolkit/.venv) or inside agentDir
  const candidates = [
    path.join(agentDir, "..", ".venv", "bin", "python"),
    path.join(agentDir, ".venv", "bin", "python"),
    path.join(agentDir, "..", ".venv", "bin", "python3"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return "python3"; // fall back to system python
}

/** Path of the currently active editor file. */
function activeFile(): string {
  return vscode.window.activeTextEditor?.document.uri.fsPath ?? "";
}

/** Path of the active file's directory. */
function activeDir(): string {
  const f = activeFile();
  return f ? path.dirname(f) : vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? ".";
}

/** Workspace root. */
function workspaceRoot(): string {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? ".";
}

// ─────────────────────────────────────────────────────────────────────────────
// Core runner — spawns python main.py and streams output as markdown
// ─────────────────────────────────────────────────────────────────────────────

function runAgent(
  args: string[],
  stream: vscode.ChatResponseStream,
  token: vscode.CancellationToken
): Promise<void> {
  return new Promise((resolve, reject) => {
    let agentDir: string;
    let pythonBin: string;

    try {
      agentDir = getAgentPath();
      pythonBin = getPythonPath(agentDir);
    } catch (e: any) {
      stream.markdown(`\n> ⚠️ **Setup issue:** ${e.message}\n`);
      stream.markdown(
        `\nSet \`aidev.agentPath\` in **VS Code Settings** to the absolute path of your \`claude-agent/\` directory.\n`
      );
      return resolve();
    }

    const cmd = [path.join(agentDir, "main.py"), ...args];
    stream.markdown(`\`\`\`\n${pythonBin} main.py ${args.join(" ")}\n\`\`\`\n\n`);

    const proc = spawn(pythonBin, cmd, {
      cwd: agentDir,
      env: { ...process.env },
    });

    let buffer = "";

    const flush = () => {
      if (buffer.trim()) {
        stream.markdown(buffer);
        buffer = "";
      }
    };

    proc.stdout.on("data", (chunk: Buffer) => {
      buffer += chunk.toString();
      // Stream line-by-line for a live feel
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      stream.markdown(lines.join("\n") + (lines.length ? "\n" : ""));
    });

    proc.stderr.on("data", (chunk: Buffer) => {
      const text = chunk.toString();
      // Suppress noisy venv activation messages; show real errors
      if (!text.includes("activate") && !text.includes("WARNING")) {
        stream.markdown(`> ⚠️ ${text}\n`);
      }
    });

    proc.on("close", (code) => {
      flush();
      if (code !== 0) {
        stream.markdown(`\n> ❌ Process exited with code ${code}\n`);
      }
      resolve();
    });

    proc.on("error", (err) => {
      stream.markdown(`\n> ❌ Failed to start process: ${err.message}\n`);
      resolve();
    });

    token.onCancellationRequested(() => {
      proc.kill();
      stream.markdown("\n> 🛑 Cancelled.\n");
      resolve();
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Natural-language intent parser
// ─────────────────────────────────────────────────────────────────────────────

interface Intent {
  command: string;
  args: string[];
  explanation: string;
}

function parseIntent(prompt: string, activeFilePath: string): Intent {
  const p = prompt.toLowerCase().trim();
  const file = activeFilePath;
  const dir = file ? path.dirname(file) : workspaceRoot();
  const src = path.join(workspaceRoot(), "src");
  const cfg = vscode.workspace.getConfiguration("aidev");
  const framework = cfg.get<string>("defaultTestFramework") || "jest";
  const baseUrl = cfg.get<string>("defaultBaseUrl") || "http://localhost:3000";

  // ── review / audit ────────────────────────────────────────────────────────
  if (/review|audit|check|look at|analyse|analyze|what.s wrong/.test(p)) {
    const target = file || src;
    return {
      command: "review",
      args: ["--review", target],
      explanation: `🔍 Reviewing **${path.basename(target)}** for bugs, security issues, and code quality…`,
    };
  }

  // ── unit tests ────────────────────────────────────────────────────────────
  if (/unit test|jest|rtl|react testing|generate test/.test(p) && !/e2e|playwright/.test(p)) {
    const target = file || src;
    return {
      command: "test",
      args: ["--unit-test", target],
      explanation: `🧪 Generating Jest + RTL unit tests for **${path.basename(target)}**…`,
    };
  }

  // ── e2e tests ─────────────────────────────────────────────────────────────
  if (/e2e|playwright|end.to.end|browser test/.test(p)) {
    const target = file || src;
    return {
      command: "e2e",
      args: ["--e2e", target, "--base-url", baseUrl],
      explanation: `🎭 Generating Playwright E2E tests for **${path.basename(target)}**…`,
    };
  }

  // ── fix / debug ───────────────────────────────────────────────────────────
  if (/fix|debug|error|bug|crash|broken|failing|exception|TypeError|ReferenceError/.test(p)) {
    // Try to extract error text after "fix" / "error:"
    const errorMatch = prompt.match(/(?:fix|error[:\s]+|debug[:\s]+)(.*)/i);
    const errorArg = errorMatch ? errorMatch[1].trim() : (file || "this error");
    return {
      command: "fix",
      args: ["--fix", errorArg],
      explanation: `🐛 Diagnosing and fixing: **${errorArg.slice(0, 60)}**…`,
    };
  }

  // ── self-heal ─────────────────────────────────────────────────────────────
  if (/heal|self.heal|fix.*test|test.*fail|ci.*fail/.test(p)) {
    return {
      command: "heal",
      args: ["--heal", workspaceRoot(), "--heal-framework", framework, "--heal-retries", "3"],
      explanation: `🔄 Running self-healing loop with **${framework}** — run → fix → repeat…`,
    };
  }

  // ── accessibility ─────────────────────────────────────────────────────────
  if (/a11y|accessibility|wcag|aria|screen reader/.test(p)) {
    const dryRun = /dry.?run|preview|show|what would/.test(p);
    const args = ["--heal-a11y", dir];
    if (dryRun) args.push("--a11y-dry-run");
    return {
      command: "a11y",
      args,
      explanation: `♿ ${dryRun ? "Previewing" : "Fixing"} accessibility violations in **${path.basename(dir)}**…`,
    };
  }

  // ── ci/cd ─────────────────────────────────────────────────────────────────
  if (/ci|cd|pipeline|github action|workflow/.test(p)) {
    return {
      command: "ci",
      args: ["--ci", "--output", workspaceRoot()],
      explanation: `⚙️ Generating GitHub Actions CI/CD workflows…`,
    };
  }

  // ── rag index ─────────────────────────────────────────────────────────────
  if (/index|embed|vector|rag/.test(p) && !/search/.test(p)) {
    return {
      command: "index",
      args: ["--index", src],
      explanation: `📚 Indexing codebase into local ChromaDB vector store…`,
    };
  }

  // ── rag search ────────────────────────────────────────────────────────────
  if (/search|find|where is|semantic/.test(p)) {
    const searchMatch = prompt.match(/(?:search|find|where is|for)[:\s]+(.*)/i);
    const query = searchMatch ? searchMatch[1].trim() : prompt;
    return {
      command: "search",
      args: ["--index", src, "--search", query],
      explanation: `🔍 Searching codebase for: **${query}**…`,
    };
  }

  // ── analytics ─────────────────────────────────────────────────────────────
  if (/analytic|amplitude|track|event|funnel/.test(p)) {
    return {
      command: "analytics",
      args: ["--add-analytics", src, "--app-name", "My App"],
      explanation: `📊 Adding Amplitude SDK v2 analytics to your app…`,
    };
  }

  // ── i18n ──────────────────────────────────────────────────────────────────
  if (/i18n|internationaliz|translation|locale|multilingual|rtl/.test(p)) {
    const localeMatch = prompt.match(/locales?\s*[=:]\s*([\w,]+)/i);
    const locales = localeMatch ? localeMatch[1] : "en,es,fr,de";
    return {
      command: "i18n",
      args: ["--add-i18n", src, "--locales", locales],
      explanation: `🌍 Adding react-i18next with locales: **${locales}**…`,
    };
  }

  // ── costs ─────────────────────────────────────────────────────────────────
  if (/cost|token|spend|usage|bill/.test(p)) {
    return {
      command: "costs",
      args: ["--costs"],
      explanation: `💰 Fetching session token usage and cost breakdown…`,
    };
  }

  // ── mcp ───────────────────────────────────────────────────────────────────
  if (/mcp|figma|jira|github|postgres|slack|filesystem/.test(p)) {
    const serverMatch = p.match(/\b(figma|jira|confluence|github|filesystem|git|slack|postgres|search)\b/);
    const server = serverMatch ? serverMatch[1] : "filesystem";
    return {
      command: "mcp",
      args: ["--mcp", server, "--mcp-task", prompt],
      explanation: `🔌 Running MCP agent on **${server}**: ${prompt.slice(0, 60)}…`,
    };
  }

  // ── full workflow ─────────────────────────────────────────────────────────
  if (/jira|ticket|feature|generate|build|create component/.test(p)) {
    const jiraMatch = prompt.match(/\b([A-Z]+-\d+)\b/);
    if (jiraMatch) {
      return {
        command: "jira",
        args: ["--jira", jiraMatch[1]],
        explanation: `🚀 Running full workflow for Jira ticket **${jiraMatch[1]}**…`,
      };
    }
  }

  // ── interactive fallback ──────────────────────────────────────────────────
  return {
    command: "interactive",
    args: ["--interactive"],
    explanation: `🖊️ Launching interactive mode — you'll be prompted for context in the terminal…`,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Help text
// ─────────────────────────────────────────────────────────────────────────────

const HELP_TEXT = `
## 🤖 AI Dev Toolkit — \`@aidev\` commands

| Slash command | What it does |
|---|---|
| \`@aidev /review\` | Review the active file for bugs & security |
| \`@aidev /test\` | Generate Jest + RTL unit tests |
| \`@aidev /e2e\` | Generate Playwright E2E tests |
| \`@aidev /fix <error>\` | Debug and fix an error or stack trace |
| \`@aidev /heal\` | Self-heal failing CI tests (run → fix → repeat) |
| \`@aidev /a11y\` | Fix WCAG 2.1 AA accessibility violations |
| \`@aidev /ci\` | Generate GitHub Actions CI/CD pipelines |
| \`@aidev /index\` | Index codebase into local RAG vector store |
| \`@aidev /search <query>\` | Semantic search across your codebase |
| \`@aidev /analytics\` | Add Amplitude SDK v2 analytics |
| \`@aidev /i18n\` | Add react-i18next internationalisation |
| \`@aidev /costs\` | Show session token usage and costs |
| \`@aidev /mcp <server> <task>\` | Run an MCP agentic task |

**Or just speak naturally:**

> \`@aidev review this file\`
> \`@aidev the tests are failing in CI, fix them\`
> \`@aidev find all usages of useUserPermissions\`
> \`@aidev add analytics to my app\`
> \`@aidev PROJ-123\`

**Keyboard shortcuts:**
- \`⌘ Shift R\` — Review active file
- \`⌘ Shift T\` — Generate unit tests

**Right-click any .ts/.tsx file** for the AI Dev context menu.
`;

// ─────────────────────────────────────────────────────────────────────────────
// Extension activation
// ─────────────────────────────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext) {
  // ── Chat participant ───────────────────────────────────────────────────────
  const participant = vscode.chat.createChatParticipant(
    "aidev.agent",
    async (
      request: vscode.ChatRequest,
      _ctx: vscode.ChatContext,
      stream: vscode.ChatResponseStream,
      token: vscode.CancellationToken
    ) => {
      const cmd = request.command;
      const prompt = request.prompt.trim();
      const file = activeFile();

      // /help or empty prompt
      if (cmd === "help" || (!cmd && !prompt)) {
        stream.markdown(HELP_TEXT);
        return;
      }

      // Slash commands with explicit routing
      if (cmd) {
        switch (cmd) {
          case "review":
            stream.markdown(`🔍 Reviewing **${path.basename(file || "project")}**…\n\n`);
            await runAgent(["--review", file || workspaceRoot()], stream, token);
            break;

          case "test":
            stream.markdown(`🧪 Generating unit tests for **${path.basename(file || "src")}**…\n\n`);
            await runAgent(["--unit-test", file || path.join(workspaceRoot(), "src")], stream, token);
            break;

          case "e2e": {
            const cfg = vscode.workspace.getConfiguration("aidev");
            const baseUrl = cfg.get<string>("defaultBaseUrl") || "http://localhost:3000";
            stream.markdown(`🎭 Generating E2E tests for **${path.basename(file || "src")}**…\n\n`);
            await runAgent(["--e2e", file || path.join(workspaceRoot(), "src"), "--base-url", baseUrl], stream, token);
            break;
          }

          case "fix":
            stream.markdown(`🐛 Diagnosing: **${prompt || file}**…\n\n`);
            await runAgent(["--fix", prompt || file], stream, token);
            break;

          case "heal": {
            const cfg = vscode.workspace.getConfiguration("aidev");
            const framework = cfg.get<string>("defaultTestFramework") || "jest";
            stream.markdown(`🔄 Self-healing with **${framework}**…\n\n`);
            await runAgent(["--heal", workspaceRoot(), "--heal-framework", framework, "--heal-retries", "3"], stream, token);
            break;
          }

          case "a11y": {
            const dryRun = /dry.?run|preview/.test(prompt);
            stream.markdown(`♿ ${dryRun ? "Previewing" : "Fixing"} accessibility violations…\n\n`);
            const args = ["--heal-a11y", file ? path.dirname(file) : workspaceRoot()];
            if (dryRun) args.push("--a11y-dry-run");
            await runAgent(args, stream, token);
            break;
          }

          case "ci":
            stream.markdown(`⚙️ Generating CI/CD pipelines…\n\n`);
            await runAgent(["--ci", "--output", workspaceRoot()], stream, token);
            break;

          case "index":
            stream.markdown(`📚 Indexing codebase…\n\n`);
            await runAgent(["--index", path.join(workspaceRoot(), "src")], stream, token);
            break;

          case "search":
            stream.markdown(`🔍 Searching for: **${prompt}**…\n\n`);
            await runAgent(["--index", path.join(workspaceRoot(), "src"), "--search", prompt], stream, token);
            break;

          case "analytics":
            stream.markdown(`📊 Adding Amplitude analytics…\n\n`);
            await runAgent(["--add-analytics", path.join(workspaceRoot(), "src"), "--app-name", prompt || "My App"], stream, token);
            break;

          case "i18n": {
            const localeMatch = prompt.match(/[\w,]+/);
            const locales = localeMatch ? localeMatch[0] : "en,es,fr,de";
            stream.markdown(`🌍 Adding i18n with locales: **${locales}**…\n\n`);
            await runAgent(["--add-i18n", path.join(workspaceRoot(), "src"), "--locales", locales], stream, token);
            break;
          }

          case "costs":
            stream.markdown(`💰 Session cost breakdown:\n\n`);
            await runAgent(["--costs"], stream, token);
            break;

          case "mcp": {
            const parts = prompt.split(/\s+/);
            const server = parts[0] || "filesystem";
            const task = parts.slice(1).join(" ") || "list available tools";
            stream.markdown(`🔌 MCP agent on **${server}**: ${task.slice(0, 60)}…\n\n`);
            await runAgent(["--mcp", server, "--mcp-task", task], stream, token);
            break;
          }

          default:
            stream.markdown(HELP_TEXT);
        }
        return;
      }

      // Natural language routing
      const intent = parseIntent(prompt, file);
      stream.markdown(`${intent.explanation}\n\n`);
      await runAgent(intent.args, stream, token);
    }
  );

  participant.iconPath = vscode.Uri.joinPath(context.extensionUri, "media", "icon.png");

  // ── Register palette / context-menu commands ──────────────────────────────
  const reg = (id: string, fn: () => Promise<void>) =>
    context.subscriptions.push(vscode.commands.registerCommand(id, fn));

  reg("aidev.reviewFile", async () => {
    const file = activeFile();
    if (!file) return vscode.window.showWarningMessage("Open a file first.");
    vscode.window.showInformationMessage(`AI Dev: reviewing ${path.basename(file)}…`);
    const term = vscode.window.createTerminal("AI Dev — Review");
    const agentDir = getAgentPath();
    const py = getPythonPath(agentDir);
    term.sendText(`${py} "${path.join(agentDir, "main.py")}" --review "${file}"`);
    term.show();
  });

  reg("aidev.generateTests", async () => {
    const file = activeFile();
    if (!file) return vscode.window.showWarningMessage("Open a file first.");
    vscode.window.showInformationMessage(`AI Dev: generating tests for ${path.basename(file)}…`);
    const term = vscode.window.createTerminal("AI Dev — Tests");
    const agentDir = getAgentPath();
    const py = getPythonPath(agentDir);
    term.sendText(`${py} "${path.join(agentDir, "main.py")}" --unit-test "${file}"`);
    term.show();
  });

  reg("aidev.generateE2E", async () => {
    const file = activeFile();
    if (!file) return vscode.window.showWarningMessage("Open a file first.");
    const agentDir = getAgentPath();
    const py = getPythonPath(agentDir);
    const term = vscode.window.createTerminal("AI Dev — E2E");
    term.sendText(`${py} "${path.join(agentDir, "main.py")}" --e2e "${file}" --base-url http://localhost:3000`);
    term.show();
  });

  reg("aidev.fixError", async () => {
    const msg = await vscode.window.showInputBox({ prompt: "Paste the error message or stack trace" });
    if (!msg) return;
    const agentDir = getAgentPath();
    const py = getPythonPath(agentDir);
    const term = vscode.window.createTerminal("AI Dev — Fix");
    term.sendText(`${py} "${path.join(agentDir, "main.py")}" --fix "${msg.replace(/"/g, '\\"')}"`);
    term.show();
  });

  reg("aidev.healTests", async () => {
    const cfg = vscode.workspace.getConfiguration("aidev");
    const framework = cfg.get<string>("defaultTestFramework") || "jest";
    const agentDir = getAgentPath();
    const py = getPythonPath(agentDir);
    const term = vscode.window.createTerminal("AI Dev — Heal");
    term.sendText(`${py} "${path.join(agentDir, "main.py")}" --heal "${workspaceRoot()}" --heal-framework ${framework} --heal-retries 3`);
    term.show();
  });

  reg("aidev.healA11y", async () => {
    const dir = activeFile() ? path.dirname(activeFile()) : workspaceRoot();
    const agentDir = getAgentPath();
    const py = getPythonPath(agentDir);
    const term = vscode.window.createTerminal("AI Dev — A11y");
    term.sendText(`${py} "${path.join(agentDir, "main.py")}" --heal-a11y "${dir}"`);
    term.show();
  });

  reg("aidev.showCosts", async () => {
    const agentDir = getAgentPath();
    const py = getPythonPath(agentDir);
    const term = vscode.window.createTerminal("AI Dev — Costs");
    term.sendText(`${py} "${path.join(agentDir, "main.py")}" --costs`);
    term.show();
  });

  context.subscriptions.push(participant);
}

export function deactivate() {}
