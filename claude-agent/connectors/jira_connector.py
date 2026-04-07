"""
Jira Connector — Fetches ticket details from Jira REST API.

Usage:
    connector = JiraConnector()
    ticket = connector.fetch_ticket("PROJ-123")
    print(ticket.summary)
"""

import requests
from dataclasses import dataclass, field
from config import Config
from rich.console import Console

console = Console()


@dataclass
class JiraTicket:
    """Structured Jira ticket data."""

    key: str = ""
    summary: str = ""
    description: str = ""
    issue_type: str = ""
    status: str = ""
    priority: str = ""
    assignee: str = ""
    acceptance_criteria: str = ""
    labels: list[str] = field(default_factory=list)
    subtasks: list[dict] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Format ticket as context string for Claude prompt."""
        parts = [
            f"## 📋 JIRA TICKET: {self.key}",
            f"**Title:** {self.summary}",
            f"**Type:** {self.issue_type} | **Status:** {self.status} | **Priority:** {self.priority}",
            "",
            f"**Description:**\n{self.description}",
        ]
        if self.acceptance_criteria:
            parts.append(f"\n**Acceptance Criteria:**\n{self.acceptance_criteria}")
        if self.labels:
            parts.append(f"\n**Labels:** {', '.join(self.labels)}")
        if self.subtasks:
            subtask_text = "\n".join(
                f"  - [{s.get('key', '')}] {s.get('summary', '')}"
                for s in self.subtasks
            )
            parts.append(f"\n**Sub-tasks:**\n{subtask_text}")
        if self.comments:
            comment_text = "\n---\n".join(self.comments[-5:])  # Last 5 comments
            parts.append(f"\n**Recent Comments:**\n{comment_text}")
        return "\n".join(parts)


class JiraConnector:
    """Connects to Jira REST API and fetches ticket details."""

    def __init__(self):
        self.base_url = Config.JIRA_BASE_URL.rstrip("/")
        self.auth = (Config.JIRA_EMAIL, Config.JIRA_API_TOKEN)
        self.headers = {"Accept": "application/json"}

    def fetch_ticket(self, ticket_key: str) -> JiraTicket:
        """
        Fetch a Jira ticket by key (e.g., 'PROJ-123').

        Returns a JiraTicket dataclass with all relevant fields.
        """
        console.print(f"[cyan]📋 Fetching Jira ticket: {ticket_key}...[/cyan]")

        url = f"{self.base_url}/rest/api/3/issue/{ticket_key}"

        try:
            response = requests.get(url, auth=self.auth, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            fields = data.get("fields", {})

            ticket = JiraTicket(
                key=data.get("key", ticket_key),
                summary=fields.get("summary", ""),
                description=self._extract_text(fields.get("description")),
                issue_type=fields.get("issuetype", {}).get("name", ""),
                status=fields.get("status", {}).get("name", ""),
                priority=fields.get("priority", {}).get("name", ""),
                assignee=(fields.get("assignee") or {}).get("displayName", "Unassigned"),
                labels=fields.get("labels", []),
                subtasks=[
                    {"key": st.get("key", ""), "summary": st.get("fields", {}).get("summary", "")}
                    for st in fields.get("subtasks", [])
                ],
            )

            # Extract acceptance criteria from description or custom field
            ticket.acceptance_criteria = self._extract_acceptance_criteria(
                ticket.description, fields
            )

            # Fetch comments
            ticket.comments = self._fetch_comments(ticket_key)

            console.print(f"[green]  ✅ Fetched: {ticket.summary}[/green]")
            return ticket

        except requests.exceptions.ConnectionError:
            console.print(f"[red]  ❌ Cannot connect to Jira at {self.base_url}[/red]")
            return JiraTicket(key=ticket_key, summary="(Connection failed)")
        except requests.exceptions.HTTPError as e:
            console.print(f"[red]  ❌ Jira API error: {e.response.status_code}[/red]")
            return JiraTicket(key=ticket_key, summary=f"(HTTP {e.response.status_code})")
        except Exception as e:
            console.print(f"[red]  ❌ Error fetching ticket: {e}[/red]")
            return JiraTicket(key=ticket_key, summary="(Error)")

    def _extract_text(self, adf_content) -> str:
        """
        Extract plain text from Jira's Atlassian Document Format (ADF).
        ADF is the JSON format Jira v3 API uses for rich text.
        """
        if adf_content is None:
            return ""
        if isinstance(adf_content, str):
            return adf_content

        # ADF is a nested JSON structure
        texts = []
        self._walk_adf(adf_content, texts)
        return "\n".join(texts)

    def _walk_adf(self, node: dict, texts: list):
        """Recursively walk ADF nodes and extract text."""
        if not isinstance(node, dict):
            return

        node_type = node.get("type", "")

        # Text node
        if node_type == "text":
            texts.append(node.get("text", ""))

        # Paragraph — add newline after
        if node_type == "paragraph":
            for child in node.get("content", []):
                self._walk_adf(child, texts)
            texts.append("")

        # Heading
        elif node_type == "heading":
            level = node.get("attrs", {}).get("level", 2)
            prefix = "#" * level + " "
            heading_texts = []
            for child in node.get("content", []):
                if child.get("type") == "text":
                    heading_texts.append(child.get("text", ""))
            texts.append(prefix + "".join(heading_texts))

        # List
        elif node_type in ("bulletList", "orderedList"):
            for i, item in enumerate(node.get("content", []), 1):
                prefix = "- " if node_type == "bulletList" else f"{i}. "
                item_texts = []
                for child in item.get("content", []):
                    self._walk_adf(child, item_texts)
                texts.append(prefix + " ".join(item_texts).strip())

        # Code block
        elif node_type == "codeBlock":
            lang = node.get("attrs", {}).get("language", "")
            code_texts = []
            for child in node.get("content", []):
                if child.get("type") == "text":
                    code_texts.append(child.get("text", ""))
            texts.append(f"```{lang}\n{''.join(code_texts)}\n```")

        # Generic content children
        elif "content" in node:
            for child in node.get("content", []):
                self._walk_adf(child, texts)

    def _extract_acceptance_criteria(self, description: str, fields: dict) -> str:
        """
        Try to extract acceptance criteria from:
        1. A custom field (common in Jira setups)
        2. The description text (look for 'Acceptance Criteria' heading)
        """
        # Check common custom field names
        for key, value in fields.items():
            if key.startswith("customfield_") and value:
                text = self._extract_text(value) if isinstance(value, dict) else str(value)
                if "acceptance" in text.lower() or "criteria" in text.lower():
                    return text

        # Extract from description
        if "acceptance criteria" in description.lower():
            idx = description.lower().index("acceptance criteria")
            return description[idx:]

        return ""

    def _fetch_comments(self, ticket_key: str) -> list[str]:
        """Fetch comments for a ticket."""
        url = f"{self.base_url}/rest/api/3/issue/{ticket_key}/comment"
        try:
            response = requests.get(url, auth=self.auth, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            comments = []
            for comment in data.get("comments", []):
                author = comment.get("author", {}).get("displayName", "Unknown")
                body = self._extract_text(comment.get("body"))
                comments.append(f"**{author}:** {body}")
            return comments
        except Exception:
            return []


def create_manual_ticket(
    key: str,
    title: str,
    description: str,
    acceptance_criteria: str = "",
) -> JiraTicket:
    """
    Create a JiraTicket manually (for when you don't have API access).
    Just paste the text from Jira.
    """
    return JiraTicket(
        key=key,
        summary=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        issue_type="Story",
        status="In Progress",
        priority="High",
    )
