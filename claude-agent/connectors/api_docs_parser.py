"""
API Docs Parser — Parses Swagger/OpenAPI specs into structured context.

Supports:
  - Swagger 2.0 JSON
  - OpenAPI 3.0 JSON/YAML
  - Local files or remote URLs
  - Manual endpoint entry

Usage:
    parser = ApiDocsParser()
    api_docs = parser.parse("https://api.example.com/swagger.json")
    print(api_docs.to_prompt_context())
"""

import json
import requests
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from rich.console import Console

console = Console()


@dataclass
class ApiEndpoint:
    """A single API endpoint."""

    method: str = ""
    path: str = ""
    summary: str = ""
    description: str = ""
    parameters: list[dict] = field(default_factory=list)
    request_body: dict = field(default_factory=dict)
    responses: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        """Format endpoint as readable text."""
        parts = [f"### {self.method.upper()} {self.path}"]
        if self.summary:
            parts.append(f"**Summary:** {self.summary}")
        if self.description:
            parts.append(f"**Description:** {self.description}")

        # Parameters (query, path, header)
        if self.parameters:
            param_lines = []
            for p in self.parameters:
                required = " (required)" if p.get("required") else ""
                param_lines.append(
                    f"  - `{p.get('name', '')}` ({p.get('in', 'query')}, "
                    f"{p.get('type', p.get('schema', {}).get('type', 'string'))}){required}"
                )
            parts.append(f"**Parameters:**\n" + "\n".join(param_lines))

        # Request body
        if self.request_body:
            body_json = json.dumps(self.request_body, indent=2)
            parts.append(f"**Request Body:**\n```json\n{body_json}\n```")

        # Responses
        if self.responses:
            for status, resp in self.responses.items():
                desc = resp if isinstance(resp, str) else json.dumps(resp, indent=2)
                parts.append(f"**Response {status}:**\n```json\n{desc}\n```")

        return "\n".join(parts)


@dataclass
class ApiDocs:
    """Parsed API documentation."""

    title: str = ""
    description: str = ""
    base_url: str = ""
    version: str = ""
    endpoints: list[ApiEndpoint] = field(default_factory=list)
    models: dict = field(default_factory=dict)  # Schema definitions

    def to_prompt_context(self) -> str:
        """Format all API docs as context string for Claude prompt."""
        parts = [
            f"## 🔌 API DOCUMENTATION: {self.title}",
            f"**Base URL:** {self.base_url}",
            f"**Version:** {self.version}",
        ]
        if self.description:
            parts.append(f"**Description:** {self.description}")

        parts.append(f"\n**Endpoints ({len(self.endpoints)} total):**\n")
        for endpoint in self.endpoints:
            parts.append(endpoint.to_text())
            parts.append("---")

        # Include data models/schemas
        if self.models:
            parts.append("\n**Data Models:**")
            for name, schema in list(self.models.items())[:20]:
                schema_json = json.dumps(schema, indent=2)
                parts.append(f"\n**{name}:**\n```json\n{schema_json}\n```")

        return "\n".join(parts)

    def filter_endpoints(self, tag: str | None = None, path_contains: str | None = None) -> "ApiDocs":
        """Return a filtered copy with only matching endpoints."""
        filtered = []
        for ep in self.endpoints:
            if tag and tag.lower() not in [t.lower() for t in ep.tags]:
                continue
            if path_contains and path_contains.lower() not in ep.path.lower():
                continue
            filtered.append(ep)

        return ApiDocs(
            title=self.title,
            description=self.description,
            base_url=self.base_url,
            version=self.version,
            endpoints=filtered,
            models=self.models,
        )


class ApiDocsParser:
    """Parses Swagger/OpenAPI specs from URLs or local files."""

    def parse(self, source: str) -> ApiDocs:
        """
        Parse an API spec from a URL or local file path.

        Args:
            source: URL (https://...) or local file path (./swagger.json)
        """
        console.print(f"[cyan]🔌 Parsing API docs: {source}...[/cyan]")

        try:
            raw_data = self._load_source(source)
            api_docs = self._parse_spec(raw_data)
            console.print(
                f"[green]  ✅ Parsed: {api_docs.title} — "
                f"{len(api_docs.endpoints)} endpoints found[/green]"
            )
            return api_docs
        except Exception as e:
            console.print(f"[red]  ❌ Error parsing API docs: {e}[/red]")
            return ApiDocs(title="(Parse Error)", description=str(e))

    def _load_source(self, source: str) -> dict:
        """Load spec from URL or file."""
        if source.startswith("http://") or source.startswith("https://"):
            response = requests.get(source, timeout=15)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "yaml" in content_type or source.endswith((".yaml", ".yml")):
                return yaml.safe_load(response.text)
            return response.json()
        else:
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {source}")
            text = path.read_text()
            if path.suffix in (".yaml", ".yml"):
                return yaml.safe_load(text)
            return json.loads(text)

    def _parse_spec(self, data: dict) -> ApiDocs:
        """Parse either Swagger 2.0 or OpenAPI 3.x format."""
        if data.get("openapi", "").startswith("3"):
            return self._parse_openapi3(data)
        elif data.get("swagger", "").startswith("2"):
            return self._parse_swagger2(data)
        else:
            # Try to parse as OpenAPI 3 anyway
            return self._parse_openapi3(data)

    def _parse_swagger2(self, data: dict) -> ApiDocs:
        """Parse Swagger 2.0 spec."""
        info = data.get("info", {})
        api_docs = ApiDocs(
            title=info.get("title", "API"),
            description=info.get("description", ""),
            base_url=f"{data.get('schemes', ['https'])[0]}://{data.get('host', 'api.example.com')}{data.get('basePath', '')}",
            version=info.get("version", ""),
            models=data.get("definitions", {}),
        )

        for path, methods in data.get("paths", {}).items():
            for method, details in methods.items():
                if method in ("get", "post", "put", "delete", "patch"):
                    endpoint = ApiEndpoint(
                        method=method.upper(),
                        path=path,
                        summary=details.get("summary", ""),
                        description=details.get("description", ""),
                        tags=details.get("tags", []),
                        parameters=details.get("parameters", []),
                    )

                    # Extract request body from parameters
                    for param in details.get("parameters", []):
                        if param.get("in") == "body":
                            schema = param.get("schema", {})
                            endpoint.request_body = self._resolve_schema(schema, data)

                    # Extract responses
                    for status, resp in details.get("responses", {}).items():
                        schema = resp.get("schema", {})
                        resolved = self._resolve_schema(schema, data) if schema else resp.get("description", "")
                        endpoint.responses[status] = resolved

                    api_docs.endpoints.append(endpoint)

        return api_docs

    def _parse_openapi3(self, data: dict) -> ApiDocs:
        """Parse OpenAPI 3.x spec."""
        info = data.get("info", {})
        servers = data.get("servers", [{}])
        api_docs = ApiDocs(
            title=info.get("title", "API"),
            description=info.get("description", ""),
            base_url=servers[0].get("url", "") if servers else "",
            version=info.get("version", ""),
            models=data.get("components", {}).get("schemas", {}),
        )

        for path, methods in data.get("paths", {}).items():
            for method, details in methods.items():
                if method in ("get", "post", "put", "delete", "patch"):
                    endpoint = ApiEndpoint(
                        method=method.upper(),
                        path=path,
                        summary=details.get("summary", ""),
                        description=details.get("description", ""),
                        tags=details.get("tags", []),
                        parameters=details.get("parameters", []),
                    )

                    # Request body
                    req_body = details.get("requestBody", {})
                    if req_body:
                        content = req_body.get("content", {})
                        json_content = content.get("application/json", {})
                        schema = json_content.get("schema", {})
                        endpoint.request_body = self._resolve_schema(schema, data)

                    # Responses
                    for status, resp in details.get("responses", {}).items():
                        content = resp.get("content", {})
                        json_content = content.get("application/json", {})
                        schema = json_content.get("schema", {})
                        if schema:
                            endpoint.responses[status] = self._resolve_schema(schema, data)
                        else:
                            endpoint.responses[status] = resp.get("description", "")

                    api_docs.endpoints.append(endpoint)

        return api_docs

    def _resolve_schema(self, schema: dict, root: dict, depth: int = 0) -> dict:
        """Resolve $ref references in schemas (up to 3 levels deep)."""
        if depth > 3:
            return schema
        if "$ref" in schema:
            ref_path = schema["$ref"].replace("#/", "").split("/")
            resolved = root
            for part in ref_path:
                resolved = resolved.get(part, {})
            return self._resolve_schema(resolved, root, depth + 1)

        result = dict(schema)
        # Resolve nested properties
        if "properties" in result:
            for key, value in result["properties"].items():
                result["properties"][key] = self._resolve_schema(value, root, depth + 1)
        # Resolve array items
        if "items" in result:
            result["items"] = self._resolve_schema(result["items"], root, depth + 1)
        return result


def create_manual_api_docs(endpoints_text: str) -> ApiDocs:
    """
    Create ApiDocs from manually pasted endpoint documentation.
    Just paste raw API docs text and it will be used as-is in the prompt.
    """
    return ApiDocs(
        title="Manual API Documentation",
        description=endpoints_text,
        endpoints=[],
    )
