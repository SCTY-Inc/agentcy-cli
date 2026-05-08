"""
Configuration management.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv


def _load_environment() -> None:
    project_root_env = os.path.join(os.path.dirname(__file__), "../.env")
    if os.path.exists(project_root_env):
        load_dotenv(project_root_env, override=True)
        return

    load_dotenv(override=True)


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_path(default_path: str, env_name: str) -> str:
    raw_value = os.environ.get(env_name, default_path)
    return os.path.abspath(raw_value)


_load_environment()


class Config:
    """Application configuration."""

    DEBUG = _get_bool_env("DEBUG", False)

    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "claude-cli").strip().lower()
    CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "").strip() or None

    DATA_DIR = _resolve_path(os.path.join(os.path.dirname(__file__), "../data/graphs"), "DATA_DIR")

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "../uploads"))
    ALLOWED_EXTENSIONS = {"pdf", "md", "txt", "markdown"}

    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get("OASIS_DEFAULT_MAX_ROUNDS", "10"))
    OASIS_SIMULATION_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../uploads/simulations"))

    OASIS_TWITTER_ACTIONS = [
        "CREATE_POST", "LIKE_POST", "REPOST", "FOLLOW", "DO_NOTHING", "QUOTE_POST",
    ]
    OASIS_REDDIT_ACTIONS = [
        "LIKE_POST", "DISLIKE_POST", "CREATE_POST", "CREATE_COMMENT",
        "LIKE_COMMENT", "DISLIKE_COMMENT", "SEARCH_POSTS", "SEARCH_USER",
        "TREND", "REFRESH", "DO_NOTHING", "FOLLOW", "MUTE",
    ]

    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get("REPORT_AGENT_MAX_TOOL_CALLS", "5"))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get("REPORT_AGENT_MAX_REFLECTION_ROUNDS", "2"))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get("REPORT_AGENT_TEMPERATURE", "0.5"))

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration."""
        errors: list[str] = []

        if cls.LLM_PROVIDER not in ("claude-cli", "codex-cli"):
            errors.append(f"LLM_PROVIDER must be 'claude-cli' or 'codex-cli', got '{cls.LLM_PROVIDER}'")

        return errors
