"""
Configuration module — loads environment variables and settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration loaded from .env file."""

    # Anthropic (Claude)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Jira
    JIRA_BASE_URL: str = os.getenv("JIRA_BASE_URL", "")
    JIRA_EMAIL: str = os.getenv("JIRA_EMAIL", "")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")

    # Figma
    FIGMA_ACCESS_TOKEN: str = os.getenv("FIGMA_ACCESS_TOKEN", "")

    # Project
    PROJECT_TECH_STACK: str = os.getenv(
        "PROJECT_TECH_STACK", "React 18, TypeScript, Tailwind CSS"
    )
    PROJECT_FOLDER_STRUCTURE: str = os.getenv(
        "PROJECT_FOLDER_STRUCTURE", "feature-based"
    )
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "./output")

    # Claude model
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MAX_TOKENS: int = 8192

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required config keys."""
        missing = []
        if not cls.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")
        return missing

    @classmethod
    def has_jira(cls) -> bool:
        return all([cls.JIRA_BASE_URL, cls.JIRA_EMAIL, cls.JIRA_API_TOKEN])

    @classmethod
    def has_figma(cls) -> bool:
        return bool(cls.FIGMA_ACCESS_TOKEN)
