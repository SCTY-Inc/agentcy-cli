"""Instagram publishing (placeholder)."""
from __future__ import annotations

from typing import Any


def post_instagram(
    content: str,
    image_url: str | None = None,
    credentials: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Post to Instagram.

    Note: Instagram API requires a business account and Facebook integration.
    This is a placeholder - implement with Meta Graph API.

    Args:
        content: Caption text
        image_url: Image URL (required for Instagram)
        credentials: API credentials

    Returns:
        Result dict
    """
    return {
        "success": False,
        "error": "Instagram publisher not implemented. Requires Meta Graph API integration.",
    }
