"""Facebook publishing — requires Meta Graph API integration."""
from __future__ import annotations

from typing import Any


def post_facebook(
    content: str,
    page_id: str | None = None,
    credentials: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": "Facebook publisher not implemented. Requires Meta Graph API integration.",
    }
