"""Twitter/X publishing via xurl."""
from __future__ import annotations

import json
import subprocess
from typing import Any


def post_tweet(
    content: str,
    credentials: dict[str, str] | None = None,
    media_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Post a tweet via xurl.

    Args:
        content: Tweet text
        credentials: Ignored (xurl manages auth via ~/.xurl)
        media_paths: Optional media file paths

    Returns:
        Result dict with tweet_id or error
    """
    app = "givecare"
    if credentials and credentials.get("app"):
        app = credentials["app"]

    try:
        media_ids = []
        for path in media_paths or []:
            result = subprocess.run(
                ["xurl", "--app", app, "media", "upload", path],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return {"success": False, "error": f"Media upload failed: {result.stderr}"}
            data = json.loads(result.stdout)
            mid = data.get("media_id_string") or str(data.get("media_id", ""))
            if not mid:
                return {"success": False, "error": f"No media_id in response: {result.stdout}"}
            media_ids.append(mid)

        body: dict[str, Any] = {"text": content}
        if media_ids:
            body["media"] = {"media_ids": media_ids}

        result = subprocess.run(
            [
                "xurl", "--app", app, "--auth", "oauth1",
                "-X", "POST", "-d", json.dumps(body), "/2/tweets",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"success": False, "error": f"Tweet failed: {result.stderr}"}

        resp = json.loads(result.stdout)
        if "errors" in resp:
            return {"success": False, "error": resp["errors"][0].get("detail", str(resp["errors"]))}

        tweet_id = resp.get("data", {}).get("id")
        if not tweet_id:
            return {"success": False, "error": f"No tweet ID in response: {result.stdout}"}

        return {
            "success": True,
            "tweet_id": tweet_id,
            "url": f"https://x.com/i/status/{tweet_id}",
        }

    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        return {"success": False, "error": str(e)}


def validate_credentials() -> bool:
    """Check if xurl is configured with an app."""
    try:
        result = subprocess.run(
            ["xurl", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0 and "oauth1" in result.stdout
    except (OSError, subprocess.SubprocessError):
        return False
