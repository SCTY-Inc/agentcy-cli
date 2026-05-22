"""Replicate/Kling video generation — not yet integrated."""
from __future__ import annotations

from typing import Any


def generate_with_replicate(
    prompt: str,
    duration: int = 5,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": "Replicate provider not implemented",
    }
