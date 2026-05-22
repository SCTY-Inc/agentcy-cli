"""LinkedIn publishing."""
from __future__ import annotations

import os
from typing import Any

import httpx


def post_linkedin(
    content: str,
    credentials: dict[str, str] | None = None,
    visibility: str = "PUBLIC",
) -> dict[str, Any]:
    """Post to LinkedIn.

    Args:
        content: Post text
        credentials: OAuth credentials (or use env vars)
        visibility: Post visibility (PUBLIC, CONNECTIONS)

    Returns:
        Result dict with post_id or error
    """
    # Get credentials from env if not provided
    access_token = credentials.get("access_token") if credentials else os.getenv("LINKEDIN_ACCESS_TOKEN")
    person_id = credentials.get("person_id") if credentials else os.getenv("LINKEDIN_PERSON_ID")

    if not access_token:
        return {
            "success": False,
            "error": "Missing LINKEDIN_ACCESS_TOKEN",
        }

    if not person_id:
        return {
            "success": False,
            "error": "Missing LINKEDIN_PERSON_ID",
        }

    try:
        # LinkedIn API endpoint
        url = "https://api.linkedin.com/v2/ugcPosts"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        payload = {
            "author": f"urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": content,
                    },
                    "shareMediaCategory": "NONE",
                },
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": visibility,
            },
        }

        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()

            return {
                "success": True,
                "post_id": data.get("id"),
            }

    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": str(e),
        }


def validate_credentials() -> bool:
    """Check if LinkedIn credentials are configured."""
    return bool(os.getenv("LINKEDIN_ACCESS_TOKEN") and os.getenv("LINKEDIN_PERSON_ID"))
