"""Threads publishing — requires Meta Threads API integration."""
from __future__ import annotations

from typing import Any


def post_threads(
    content: str,
    credentials: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": "Threads publisher not implemented. Requires Meta Threads API integration.",
    }
