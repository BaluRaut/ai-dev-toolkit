"""
Code Generator — Saves generated files to disk.
"""

import os
from pathlib import Path
from agent.claude_agent import GeneratedFile
from config import Config
from rich.console import Console

console = Console()


class CodeGenerator:
    """Saves generated code files to the output directory."""

    def __init__(self, output_dir: str | None = None):
        self.output_dir = Path(output_dir or Config.OUTPUT_DIR)

    def save_files(self, files: list[GeneratedFile]) -> list[str]:
        """
        Save all generated files to disk.

        Returns list of saved file paths.
        """
        saved_paths = []

        console.print(f"\n[bold cyan]💾 Saving {len(files)} files to: {self.output_dir}[/bold cyan]")

        for gen_file in files:
            try:
                file_path = self.output_dir / gen_file.path
                # Create directory tree
                file_path.parent.mkdir(parents=True, exist_ok=True)
                # Write file
                file_path.write_text(gen_file.content)
                saved_paths.append(str(file_path))
                console.print(f"  [green]✅ {gen_file.path}[/green]")
            except Exception as e:
                console.print(f"  [red]❌ {gen_file.path}: {e}[/red]")

        console.print(f"\n[bold green]🎉 Saved {len(saved_paths)}/{len(files)} files![/bold green]")
        console.print(f"[dim]   Output directory: {self.output_dir.resolve()}[/dim]")
        return saved_paths

    def preview_files(self, files: list[GeneratedFile]):
        """Print a preview of generated files (first 20 lines each)."""
        for gen_file in files:
            console.print(f"\n[bold]━━━ 📄 {gen_file.path} ━━━[/bold]")
            lines = gen_file.content.split("\n")
            preview_lines = lines[:20]
            for line in preview_lines:
                console.print(f"  {line}")
            if len(lines) > 20:
                console.print(f"  [dim]... ({len(lines) - 20} more lines)[/dim]")

    def list_output_files(self) -> list[str]:
        """List all files in the output directory."""
        if not self.output_dir.exists():
            return []
        return [
            str(p.relative_to(self.output_dir))
            for p in self.output_dir.rglob("*")
            if p.is_file()
        ]

    def clean_output(self):
        """Remove all files from the output directory."""
        import shutil
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
            console.print(f"[yellow]🗑️ Cleaned output directory: {self.output_dir}[/yellow]")
