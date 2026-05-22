"""YouTube publishing — requires YouTube Data API integration."""
from __future__ import annotations

from typing import Any


def upload_youtube(
    video_path: str,
    title: str,
    description: str,
    credentials: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": "YouTube publisher not implemented. Requires YouTube Data API integration.",
    }
