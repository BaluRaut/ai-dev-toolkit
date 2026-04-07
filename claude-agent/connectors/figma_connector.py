"""
Figma Connector — Fetches design data and images from Figma API.

Usage:
    connector = FigmaConnector()
    design = connector.fetch_design("file_key", node_id="123:456")
    print(design.to_prompt_context())
"""

import re
import base64
import requests
from dataclasses import dataclass, field
from config import Config
from rich.console import Console

console = Console()


@dataclass
class FigmaDesign:
    """Structured Figma design data."""

    file_key: str = ""
    file_name: str = ""
    node_name: str = ""
    node_id: str = ""
    width: float = 0
    height: float = 0
    components: list[dict] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    fonts: list[str] = field(default_factory=list)
    image_base64: str = ""  # Base64-encoded screenshot for Claude Vision
    image_url: str = ""
    css_properties: list[dict] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Format design data as context string for Claude prompt."""
        parts = [
            f"## 🎨 FIGMA DESIGN: {self.file_name}",
            f"**Frame:** {self.node_name} ({self.width}x{self.height})",
        ]
        if self.components:
            comp_list = "\n".join(
                f"  - **{c['name']}** ({c.get('type', 'FRAME')})"
                for c in self.components[:30]
            )
            parts.append(f"\n**Components Found:**\n{comp_list}")
        if self.colors:
            parts.append(f"\n**Colors Used:** {', '.join(self.colors[:20])}")
        if self.fonts:
            parts.append(f"\n**Fonts Used:** {', '.join(self.fonts)}")
        if self.css_properties:
            css_text = "\n".join(
                f"  {p['name']}: {p['css']}" for p in self.css_properties[:20]
            )
            parts.append(f"\n**CSS Properties:**\n```css\n{css_text}\n```")
        if self.image_base64:
            parts.append("\n**[Design screenshot attached as image]**")
        return "\n".join(parts)


class FigmaConnector:
    """Connects to Figma API and fetches design data."""

    BASE_URL = "https://api.figma.com/v1"

    def __init__(self):
        self.token = Config.FIGMA_ACCESS_TOKEN
        self.headers = {"X-Figma-Token": self.token}

    def fetch_design(
        self, file_key: str, node_id: str | None = None
    ) -> FigmaDesign:
        """
        Fetch design data from a Figma file.

        Args:
            file_key: The Figma file key (from URL: figma.com/file/<KEY>/...)
            node_id:  Optional specific node/frame ID (e.g., "123:456")
        """
        console.print(f"[cyan]🎨 Fetching Figma design: {file_key}...[/cyan]")

        design = FigmaDesign(file_key=file_key)

        try:
            # Step 1: Get file metadata
            file_data = self._get_file(file_key)
            design.file_name = file_data.get("name", "Unknown")

            # Step 2: Get specific node or top-level frames
            if node_id:
                node_data = self._get_node(file_key, node_id)
                nodes = node_data.get("nodes", {})
                if node_id in nodes:
                    node = nodes[node_id].get("document", {})
                    design.node_name = node.get("name", "")
                    design.node_id = node_id
                    bbox = node.get("absoluteBoundingBox", {})
                    design.width = bbox.get("width", 0)
                    design.height = bbox.get("height", 0)
                    # Extract components from this node
                    design.components = self._extract_components(node)
            else:
                # Get first page's frames
                pages = file_data.get("document", {}).get("children", [])
                if pages:
                    first_page = pages[0]
                    design.node_name = first_page.get("name", "Page 1")
                    frames = first_page.get("children", [])
                    design.components = [
                        {
                            "name": f.get("name", ""),
                            "type": f.get("type", "FRAME"),
                            "id": f.get("id", ""),
                        }
                        for f in frames[:20]
                    ]

            # Step 3: Extract colors and fonts from the file
            styles = file_data.get("styles", {})
            design.colors = self._extract_colors(styles, file_data)
            design.fonts = self._extract_fonts(file_data)

            # Step 4: Get screenshot image
            target_node = node_id or self._get_first_frame_id(file_data)
            if target_node:
                image_data = self._get_image(file_key, target_node)
                if image_data:
                    design.image_url = image_data.get("url", "")
                    # Download and encode as base64 for Claude Vision
                    design.image_base64 = self._download_image_base64(
                        design.image_url
                    )

            console.print(
                f"[green]  ✅ Fetched: {design.file_name} — "
                f"{len(design.components)} components found[/green]"
            )
            return design

        except requests.exceptions.HTTPError as e:
            console.print(f"[red]  ❌ Figma API error: {e.response.status_code}[/red]")
            if e.response.status_code == 403:
                console.print("[yellow]  💡 Check your FIGMA_ACCESS_TOKEN[/yellow]")
            return design
        except Exception as e:
            console.print(f"[red]  ❌ Error fetching Figma design: {e}[/red]")
            return design

    @staticmethod
    def parse_figma_url(url: str) -> tuple[str, str | None]:
        """
        Parse a Figma URL to extract file_key and optional node_id.

        Supported URL formats:
            https://www.figma.com/file/ABC123/FileName
            https://www.figma.com/file/ABC123/FileName?node-id=1:2
            https://www.figma.com/design/ABC123/FileName?node-id=1-2
        """
        # Extract file key
        match = re.search(r"figma\.com/(?:file|design)/([a-zA-Z0-9]+)", url)
        file_key = match.group(1) if match else url  # fallback: treat as key

        # Extract node ID
        node_id = None
        node_match = re.search(r"node-id=([^&]+)", url)
        if node_match:
            # Figma URLs use '-' but API uses ':'
            node_id = node_match.group(1).replace("-", ":")

        return file_key, node_id

    def _get_file(self, file_key: str) -> dict:
        """GET /v1/files/:file_key"""
        url = f"{self.BASE_URL}/files/{file_key}"
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def _get_node(self, file_key: str, node_id: str) -> dict:
        """GET /v1/files/:file_key/nodes?ids=:node_id"""
        url = f"{self.BASE_URL}/files/{file_key}/nodes"
        params = {"ids": node_id}
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _get_image(self, file_key: str, node_id: str) -> dict | None:
        """GET /v1/images/:file_key?ids=:node_id — returns rendered image URL."""
        url = f"{self.BASE_URL}/images/{file_key}"
        params = {"ids": node_id, "format": "png", "scale": 2}
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            images = data.get("images", {})
            if node_id in images and images[node_id]:
                return {"url": images[node_id]}
        except Exception:
            pass
        return None

    def _download_image_base64(self, url: str) -> str:
        """Download an image URL and return base64 string."""
        if not url:
            return ""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return base64.b64encode(response.content).decode("utf-8")
        except Exception:
            return ""

    def _extract_components(self, node: dict) -> list[dict]:
        """Recursively extract component names from a Figma node tree."""
        components = []
        self._walk_node(node, components, depth=0, max_depth=4)
        return components

    def _walk_node(self, node: dict, components: list, depth: int, max_depth: int):
        """Walk the Figma node tree."""
        if depth > max_depth or len(components) > 50:
            return
        node_type = node.get("type", "")
        name = node.get("name", "")
        # Skip internal Figma nodes
        if node_type in ("COMPONENT", "INSTANCE", "FRAME", "GROUP", "TEXT", "RECTANGLE"):
            components.append({
                "name": name,
                "type": node_type,
                "id": node.get("id", ""),
            })
        for child in node.get("children", []):
            self._walk_node(child, components, depth + 1, max_depth)

    def _extract_colors(self, styles: dict, file_data: dict) -> list[str]:
        """Extract color hex values from Figma file styles."""
        colors = set()
        # Walk through styles
        for style_id, style in styles.items():
            if style.get("styleType") == "FILL":
                colors.add(style.get("name", f"Color {style_id}"))
        return sorted(colors)[:20]

    def _extract_fonts(self, file_data: dict) -> list[str]:
        """Extract font family names from the Figma file."""
        fonts = set()
        self._walk_for_fonts(file_data.get("document", {}), fonts)
        return sorted(fonts)

    def _walk_for_fonts(self, node: dict, fonts: set, depth: int = 0):
        """Walk tree looking for text style font families."""
        if depth > 5 or len(fonts) > 10:
            return
        style = node.get("style", {})
        if "fontFamily" in style:
            fonts.add(style["fontFamily"])
        for child in node.get("children", []):
            self._walk_for_fonts(child, fonts, depth + 1)

    def _get_first_frame_id(self, file_data: dict) -> str | None:
        """Get the ID of the first top-level frame in the file."""
        pages = file_data.get("document", {}).get("children", [])
        if pages:
            frames = pages[0].get("children", [])
            if frames:
                return frames[0].get("id")
        return None


def create_manual_design(
    description: str,
    colors: list[str] | None = None,
    fonts: list[str] | None = None,
    image_path: str | None = None,
) -> FigmaDesign:
    """
    Create a FigmaDesign manually when you don't have API access.
    Describe the design in text, or provide a local screenshot path.
    """
    design = FigmaDesign(
        file_name="Manual Design",
        node_name=description[:50],
        components=[{"name": "Described in text", "type": "DESCRIPTION"}],
        colors=colors or [],
        fonts=fonts or [],
    )
    # If local image provided, encode it
    if image_path:
        try:
            with open(image_path, "rb") as f:
                design.image_base64 = base64.b64encode(f.read()).decode("utf-8")
            console.print(f"[green]  ✅ Loaded local image: {image_path}[/green]")
        except Exception as e:
            console.print(f"[yellow]  ⚠️ Could not load image: {e}[/yellow]")

    return design
