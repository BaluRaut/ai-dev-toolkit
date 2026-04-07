"""
RAG Engine — Codebase Context via Vector Search.

Uses ChromaDB to index the entire codebase into vector embeddings,
enabling semantic search for relevant code context.

Flow:
  1. Index: Walk the codebase → chunk files → embed with a local model → store in ChromaDB
  2. Query: Given a natural language query → find most relevant code chunks
  3. Context: Return the top-k chunks as context for Claude prompts

This allows the agent to work on HUGE codebases without manually specifying files.
"""

import os
import hashlib
import time
from pathlib import Path
from dataclasses import dataclass, field
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

console = Console()


# ─────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────

@dataclass
class CodeChunk:
    """A chunk of code from the codebase."""
    file_path: str
    content: str
    start_line: int
    end_line: int
    language: str = ""

    @property
    def id(self) -> str:
        """Deterministic ID based on file path and line range."""
        raw = f"{self.file_path}:{self.start_line}-{self.end_line}"
        return hashlib.md5(raw.encode()).hexdigest()

    @property
    def metadata(self) -> dict:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "char_count": len(self.content),
        }


@dataclass
class SearchResult:
    """A search result with relevance score."""
    chunk: CodeChunk
    score: float  # Lower = more relevant (distance)
    rank: int = 0

    @property
    def relevance_display(self) -> str:
        # Convert distance to a percentage (lower distance = higher relevance)
        pct = max(0, (1 - self.score) * 100)
        return f"{pct:.0f}%"


@dataclass
class IndexStats:
    """Statistics about the indexed codebase."""
    total_files: int = 0
    total_chunks: int = 0
    total_chars: int = 0
    languages: dict = field(default_factory=dict)
    index_time_seconds: float = 0.0
    skipped_files: int = 0


# ─────────────────────────────────────────────────
# File Chunker
# ─────────────────────────────────────────────────

# Extensions to index
INDEXABLE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".vue", ".svelte",
    ".css", ".scss", ".less", ".html",
    ".json", ".yaml", ".yml", ".toml",
    ".md", ".mdx",
    ".sql", ".graphql", ".gql",
    ".java", ".kt", ".go", ".rs", ".rb", ".php", ".cs",
    ".sh", ".bash", ".zsh",
}

# Directories to always skip
SKIP_DIRS = {
    "node_modules", ".git", ".next", ".nuxt", "dist", "build",
    "__pycache__", ".venv", "venv", "env", ".env",
    ".tox", ".mypy_cache", ".pytest_cache",
    "coverage", ".nyc_output",
    "vendor", "target", "bin", "obj",
    ".chromadb",  # Don't index our own DB
}

LANGUAGE_MAP = {
    ".ts": "typescript", ".tsx": "typescriptreact",
    ".js": "javascript", ".jsx": "javascriptreact",
    ".py": "python", ".vue": "vue", ".svelte": "svelte",
    ".css": "css", ".scss": "scss", ".less": "less",
    ".html": "html", ".json": "json",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".md": "markdown", ".mdx": "markdown",
    ".sql": "sql", ".graphql": "graphql",
    ".java": "java", ".kt": "kotlin", ".go": "go",
    ".rs": "rust", ".rb": "ruby", ".php": "php",
    ".cs": "csharp", ".sh": "shell",
}


def chunk_file(file_path: Path, chunk_size: int = 80, overlap: int = 10) -> list[CodeChunk]:
    """
    Split a file into overlapping chunks of `chunk_size` lines.

    Args:
        file_path: Path to the source file
        chunk_size: Number of lines per chunk
        overlap: Number of overlapping lines between chunks
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    lines = content.split("\n")
    if not lines or len(content.strip()) == 0:
        return []

    ext = file_path.suffix.lower()
    language = LANGUAGE_MAP.get(ext, "")

    # Small files: single chunk
    if len(lines) <= chunk_size:
        return [CodeChunk(
            file_path=str(file_path),
            content=content,
            start_line=1,
            end_line=len(lines),
            language=language,
        )]

    # Larger files: overlapping chunks
    chunks = []
    step = chunk_size - overlap
    for start in range(0, len(lines), step):
        end = min(start + chunk_size, len(lines))
        chunk_lines = lines[start:end]
        chunk_content = "\n".join(chunk_lines)

        if chunk_content.strip():  # Skip empty chunks
            chunks.append(CodeChunk(
                file_path=str(file_path),
                content=chunk_content,
                start_line=start + 1,
                end_line=end,
                language=language,
            ))

        if end >= len(lines):
            break

    return chunks


def walk_codebase(root: str) -> list[Path]:
    """Walk the codebase and return all indexable files."""
    root_path = Path(root)
    files = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Skip excluded directories (modify in-place to prevent descent)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

        for filename in filenames:
            ext = Path(filename).suffix.lower()
            if ext in INDEXABLE_EXTENSIONS:
                full_path = Path(dirpath) / filename
                # Skip very large files (> 500KB)
                try:
                    if full_path.stat().st_size <= 500_000:
                        files.append(full_path)
                except OSError:
                    pass

    return files


# ─────────────────────────────────────────────────
# RAG Engine (ChromaDB)
# ─────────────────────────────────────────────────

class RAGEngine:
    """
    Vector-based codebase search using ChromaDB.

    Index your codebase once, then query semantically:
        engine = RAGEngine("/path/to/project")
        engine.index()
        results = engine.search("user authentication logic")
    """

    def __init__(self, project_dir: str, db_path: str | None = None):
        self.project_dir = Path(project_dir)
        self.db_path = db_path or str(self.project_dir / ".chromadb")
        self.collection_name = "codebase"
        self._client = None
        self._collection = None
        self.last_stats: IndexStats | None = None

    def _get_client(self):
        """Lazy-init ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=self.db_path)
            except ImportError:
                console.print("[red]❌ ChromaDB not installed. Run: pip install chromadb[/red]")
                raise
        return self._client

    def _get_collection(self):
        """Get or create the ChromaDB collection."""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def index(self, chunk_size: int = 80, overlap: int = 10) -> IndexStats:
        """
        Index the entire codebase into ChromaDB.

        Args:
            chunk_size: Lines per chunk
            overlap: Overlapping lines between chunks

        Returns:
            IndexStats with details about what was indexed
        """
        console.print(Panel(
            f"[bold]📚 Indexing Codebase[/bold]\n"
            f"Project: {self.project_dir}\n"
            f"DB: {self.db_path}",
            style="cyan",
        ))

        start_time = time.time()
        stats = IndexStats()

        # Walk codebase
        files = walk_codebase(str(self.project_dir))
        stats.total_files = len(files)

        if not files:
            console.print("[yellow]⚠️ No indexable files found[/yellow]")
            return stats

        console.print(f"[dim]   Found {len(files)} files to index[/dim]")

        # Clear existing collection for fresh index
        collection = self._get_collection()
        try:
            client = self._get_client()
            client.delete_collection(self.collection_name)
            self._collection = None
            collection = self._get_collection()
        except Exception:
            pass

        # Chunk all files
        all_chunks: list[CodeChunk] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}[/cyan]"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Chunking files...", total=len(files))

            for file_path in files:
                chunks = chunk_file(file_path, chunk_size, overlap)
                if chunks:
                    # Use relative paths for cleaner display
                    try:
                        rel = file_path.relative_to(self.project_dir)
                        for chunk in chunks:
                            chunk.file_path = str(rel)
                    except ValueError:
                        pass

                    all_chunks.extend(chunks)

                    # Track language stats
                    lang = chunks[0].language or "unknown"
                    stats.languages[lang] = stats.languages.get(lang, 0) + 1
                else:
                    stats.skipped_files += 1

                progress.advance(task)

        stats.total_chunks = len(all_chunks)
        stats.total_chars = sum(len(c.content) for c in all_chunks)

        if not all_chunks:
            console.print("[yellow]⚠️ No chunks created from files[/yellow]")
            return stats

        # Add to ChromaDB in batches (ChromaDB limit: 5461 per batch)
        batch_size = 500
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}[/cyan]"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Embedding & storing...", total=len(all_chunks))

            for i in range(0, len(all_chunks), batch_size):
                batch = all_chunks[i:i + batch_size]
                collection.add(
                    ids=[c.id for c in batch],
                    documents=[c.content for c in batch],
                    metadatas=[c.metadata for c in batch],
                )
                progress.advance(task, len(batch))

        stats.index_time_seconds = time.time() - start_time
        self.last_stats = stats

        # Print summary
        self._print_index_summary(stats)

        return stats

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """
        Search the indexed codebase for relevant code.

        Args:
            query: Natural language query (e.g., "user authentication logic")
            top_k: Number of results to return

        Returns:
            List of SearchResult sorted by relevance
        """
        collection = self._get_collection()

        if collection.count() == 0:
            console.print("[yellow]⚠️ Codebase not indexed yet. Run: python main.py --index[/yellow]")
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results and results["documents"]:
            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )):
                chunk = CodeChunk(
                    file_path=meta.get("file_path", "unknown"),
                    content=doc,
                    start_line=meta.get("start_line", 0),
                    end_line=meta.get("end_line", 0),
                    language=meta.get("language", ""),
                )
                search_results.append(SearchResult(
                    chunk=chunk,
                    score=dist,
                    rank=i + 1,
                ))

        return search_results

    def search_for_prompt(self, query: str, top_k: int = 5) -> str:
        """
        Search and format results as prompt context.

        Returns a formatted string ready to inject into a Claude prompt.
        """
        results = self.search(query, top_k)

        if not results:
            return "(No relevant code found in codebase index)"

        sections = []
        sections.append(f"## 🔍 Relevant Codebase Context (top {len(results)} matches)\n")

        for r in results:
            sections.append(
                f"### {r.chunk.file_path} (lines {r.chunk.start_line}-{r.chunk.end_line}) "
                f"— relevance: {r.relevance_display}\n"
                f"```{r.chunk.language}\n"
                f"{r.chunk.content}\n"
                f"```\n"
            )

        return "\n".join(sections)

    def print_search_results(self, results: list[SearchResult]):
        """Pretty-print search results."""
        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan", title="🔍 Search Results")
        table.add_column("#", justify="center", width=4)
        table.add_column("File", style="bold")
        table.add_column("Lines", justify="center")
        table.add_column("Language")
        table.add_column("Relevance", justify="center")
        table.add_column("Preview")

        for r in results:
            preview = r.chunk.content[:80].replace("\n", " ").strip()
            if len(r.chunk.content) > 80:
                preview += "..."

            table.add_row(
                str(r.rank),
                r.chunk.file_path,
                f"{r.chunk.start_line}-{r.chunk.end_line}",
                r.chunk.language,
                r.relevance_display,
                preview,
            )

        console.print(table)

    def get_collection_stats(self) -> dict:
        """Get stats about the current index."""
        try:
            collection = self._get_collection()
            return {
                "total_chunks": collection.count(),
                "db_path": self.db_path,
                "project_dir": str(self.project_dir),
            }
        except Exception:
            return {"total_chunks": 0, "db_path": self.db_path}

    def _print_index_summary(self, stats: IndexStats):
        """Print a formatted summary of the indexing."""
        console.print(Panel(
            f"[bold green]✅ Indexing Complete[/bold green]\n\n"
            f"📁 Files indexed: {stats.total_files}\n"
            f"📦 Chunks created: {stats.total_chunks}\n"
            f"📝 Total characters: {stats.total_chars:,}\n"
            f"⏱️ Time: {stats.index_time_seconds:.1f}s\n"
            f"⏭️ Skipped: {stats.skipped_files} files",
            style="green",
            title="📚 Index Summary",
        ))

        if stats.languages:
            console.print("\n[bold]Languages indexed:[/bold]")
            for lang, count in sorted(stats.languages.items(), key=lambda x: -x[1]):
                console.print(f"  {lang}: {count} files")


# ─────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────

def index_codebase(project_dir: str) -> IndexStats:
    """Index a codebase for RAG search."""
    engine = RAGEngine(project_dir)
    return engine.index()


def search_codebase(project_dir: str, query: str, top_k: int = 5) -> list[SearchResult]:
    """Search an indexed codebase."""
    engine = RAGEngine(project_dir)
    results = engine.search(query, top_k)
    engine.print_search_results(results)
    return results
