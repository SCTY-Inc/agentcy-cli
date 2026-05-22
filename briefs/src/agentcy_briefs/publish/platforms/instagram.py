"""Instagram publishing — requires Meta Graph API + business account."""
from __future__ import annotations

from typing import Any


def post_instagram(
    content: str,
    image_url: str | None = None,
    credentials: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": "Instagram publisher not implemented. Requires Meta Graph API integration.",
    }
