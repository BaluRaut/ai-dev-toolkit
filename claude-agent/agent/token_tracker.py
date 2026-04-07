"""
Token Tracker — Cost & Usage Monitoring for Claude API.

Tracks:
  - Input/output tokens per API call
  - Estimated cost in USD per call and per session
  - Cumulative session statistics
  - Rich formatted cost reports

Pricing (Claude claude-sonnet-4-20250514 as of 2024):
  - Input:  $3.00 per million tokens
  - Output: $15.00 per million tokens
"""

import time
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import ClassVar
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


# ─────────────────────────────────────────────────
# Pricing Data
# ─────────────────────────────────────────────────

# Prices per MILLION tokens (USD)
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    # Add more models as needed
}


# ─────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────

@dataclass
class APICall:
    """Record of a single API call."""
    timestamp: float
    model: str
    mode: str  # "generate_code", "chat", "self_heal", etc.
    input_tokens: int
    output_tokens: int
    duration_seconds: float
    prompt_preview: str = ""  # First 100 chars of prompt

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        pricing = MODEL_PRICING.get(self.model, {"input": 3.00, "output": 15.00})
        input_cost = (self.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    @property
    def cost_display(self) -> str:
        cost = self.cost_usd
        if cost < 0.01:
            return f"${cost:.4f}"
        return f"${cost:.2f}"


@dataclass
class SessionStats:
    """Aggregated stats for the current session."""
    calls: list[APICall] = field(default_factory=list)
    session_start: float = field(default_factory=time.time)

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_cost_display(self) -> str:
        cost = self.total_cost_usd
        if cost < 0.01:
            return f"${cost:.4f}"
        return f"${cost:.2f}"

    @property
    def total_duration(self) -> float:
        return sum(c.duration_seconds for c in self.calls)

    @property
    def avg_cost_per_call(self) -> float:
        if not self.calls:
            return 0.0
        return self.total_cost_usd / len(self.calls)


# ─────────────────────────────────────────────────
# Token Tracker (Singleton)
# ─────────────────────────────────────────────────

class TokenTracker:
    """
    Singleton tracker for all Claude API usage in a session.

    Usage:
        tracker = TokenTracker.instance()
        tracker.record(model, mode, input_tokens, output_tokens, duration)
        tracker.print_last_call()
        tracker.print_session_summary()
    """

    _instance: ClassVar["TokenTracker | None"] = None

    def __init__(self):
        self.stats = SessionStats()
        self._log_file: Path | None = None

    @classmethod
    def instance(cls) -> "TokenTracker":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (useful for testing)."""
        cls._instance = None

    def set_log_file(self, path: str):
        """Enable logging API calls to a JSON file."""
        self._log_file = Path(path)
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        model: str,
        mode: str,
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float,
        prompt_preview: str = "",
    ) -> APICall:
        """
        Record a new API call.

        Returns the APICall record.
        """
        call = APICall(
            timestamp=time.time(),
            model=model,
            mode=mode,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_seconds=duration_seconds,
            prompt_preview=prompt_preview[:100],
        )
        self.stats.calls.append(call)

        # Log to file if configured
        if self._log_file:
            self._append_log(call)

        return call

    def print_last_call(self):
        """Print a compact cost line for the most recent API call."""
        if not self.stats.calls:
            return

        call = self.stats.calls[-1]
        console.print(
            f"[dim]   💰 Cost: {call.cost_display} "
            f"({call.input_tokens:,} in + {call.output_tokens:,} out = {call.total_tokens:,} tokens) "
            f"| ⏱️ {call.duration_seconds:.1f}s "
            f"| Session total: {self.stats.total_cost_display}[/dim]"
        )

    def print_session_summary(self):
        """Print a detailed session summary table."""
        if not self.stats.calls:
            console.print("[dim]No API calls recorded this session.[/dim]")
            return

        # Summary panel
        console.print(Panel(
            f"[bold]💰 Session Cost Report[/bold]\n"
            f"Total API Calls: {self.stats.total_calls}\n"
            f"Total Tokens: {self.stats.total_tokens:,}\n"
            f"Total Cost: [bold yellow]{self.stats.total_cost_display}[/bold yellow]\n"
            f"Total Duration: {self.stats.total_duration:.1f}s\n"
            f"Avg Cost/Call: ${self.stats.avg_cost_per_call:.4f}",
            style="cyan",
            title="📊 Token Tracker",
        ))

        # Detailed table
        table = Table(show_header=True, header_style="bold cyan", title="API Call Log")
        table.add_column("#", justify="center", width=4)
        table.add_column("Mode", width=15)
        table.add_column("Input", justify="right")
        table.add_column("Output", justify="right")
        table.add_column("Total", justify="right")
        table.add_column("Cost", justify="right", style="yellow")
        table.add_column("Duration", justify="right")

        for i, call in enumerate(self.stats.calls, 1):
            table.add_row(
                str(i),
                call.mode,
                f"{call.input_tokens:,}",
                f"{call.output_tokens:,}",
                f"{call.total_tokens:,}",
                call.cost_display,
                f"{call.duration_seconds:.1f}s",
            )

        # Totals row
        table.add_row(
            "",
            "[bold]TOTAL[/bold]",
            f"[bold]{self.stats.total_input_tokens:,}[/bold]",
            f"[bold]{self.stats.total_output_tokens:,}[/bold]",
            f"[bold]{self.stats.total_tokens:,}[/bold]",
            f"[bold yellow]{self.stats.total_cost_display}[/bold yellow]",
            f"[bold]{self.stats.total_duration:.1f}s[/bold]",
        )

        console.print(table)

        # Cost breakdown by mode
        mode_costs: dict[str, float] = {}
        for call in self.stats.calls:
            mode_costs[call.mode] = mode_costs.get(call.mode, 0) + call.cost_usd

        if len(mode_costs) > 1:
            console.print("\n[bold]Cost by Mode:[/bold]")
            for mode, cost in sorted(mode_costs.items(), key=lambda x: -x[1]):
                bar_len = int((cost / self.stats.total_cost_usd) * 30)
                bar = "█" * bar_len + "░" * (30 - bar_len)
                pct = (cost / self.stats.total_cost_usd) * 100
                console.print(f"  {mode:<20} {bar} ${cost:.4f} ({pct:.0f}%)")

    def estimate_cost(self, prompt: str, model: str = "claude-sonnet-4-20250514") -> str:
        """
        Estimate the cost of a prompt before sending it.

        Uses a rough approximation: ~4 chars per token for English.
        Output is estimated at 2x the input tokens (conservative).
        """
        # Rough token estimate: ~4 characters per token
        estimated_input_tokens = len(prompt) // 4
        # Assume output will be ~2x input for code generation
        estimated_output_tokens = estimated_input_tokens * 2

        pricing = MODEL_PRICING.get(model, {"input": 3.00, "output": 15.00})
        input_cost = (estimated_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (estimated_output_tokens / 1_000_000) * pricing["output"]
        total = input_cost + output_cost

        return (
            f"~{estimated_input_tokens:,} input tokens + "
            f"~{estimated_output_tokens:,} output tokens ≈ "
            f"${total:.4f}"
        )

    def _append_log(self, call: APICall):
        """Append a call record to the JSON log file."""
        try:
            records = []
            if self._log_file and self._log_file.exists():
                records = json.loads(self._log_file.read_text())

            records.append({
                "timestamp": call.timestamp,
                "model": call.model,
                "mode": call.mode,
                "input_tokens": call.input_tokens,
                "output_tokens": call.output_tokens,
                "total_tokens": call.total_tokens,
                "cost_usd": call.cost_usd,
                "duration_seconds": call.duration_seconds,
                "prompt_preview": call.prompt_preview,
            })

            if self._log_file:
                self._log_file.write_text(json.dumps(records, indent=2))
        except Exception:
            pass  # Don't crash on log failure
