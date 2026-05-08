"""Rate limiting for social publishing."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.storage import data_dir

# Default rate limits per platform (posts per hour)
DEFAULT_LIMITS = {
    "twitter": 10,
    "linkedin": 5,
    "instagram": 5,
    "facebook": 5,
    "threads": 10,
}


def get_rate_limit_path() -> Path:
    """Get the rate limit state file path."""
    return data_dir() / "rate_limits.json"


def load_rate_state() -> dict[str, Any]:
    """Load rate limit state."""
    path = get_rate_limit_path()

    if not path.exists():
        return {}

    return json.loads(path.read_text())


def save_rate_state(state: dict[str, Any]) -> None:
    """Save rate limit state."""
    path = get_rate_limit_path()
    path.write_text(json.dumps(state, indent=2))


def can_post(platform: str, brand: str | None = None) -> bool:
    """Check if we can post to a platform.

    Args:
        platform: Platform name
        brand: Optional brand for brand-specific limits

    Returns:
        True if posting is allowed
    """
    state = load_rate_state()
    key = f"{platform}:{brand}" if brand else platform

    if key not in state:
        return True

    # Get posts in the last hour
    window_start = utc_now() - timedelta(hours=1)
    posts = state[key].get("posts", [])

    recent_posts = [
        p for p in posts
        if datetime.fromisoformat(p) > window_start
    ]

    limit = DEFAULT_LIMITS.get(platform, 10)
    return len(recent_posts) < limit


def record_post(platform: str, brand: str | None = None) -> None:
    """Record a post for rate limiting.

    Args:
        platform: Platform name
        brand: Optional brand
    """
    state = load_rate_state()
    key = f"{platform}:{brand}" if brand else platform

    if key not in state:
        state[key] = {"posts": []}

    state[key]["posts"].append(utc_now().isoformat())

    # Clean up old entries (keep last 24 hours)
    cutoff = utc_now() - timedelta(hours=24)
    state[key]["posts"] = [
        p for p in state[key]["posts"]
        if datetime.fromisoformat(p) > cutoff
    ]

    save_rate_state(state)


def get_wait_time(platform: str, brand: str | None = None) -> int:
    """Get seconds to wait before posting is allowed.

    Args:
        platform: Platform name
        brand: Optional brand

    Returns:
        Seconds to wait (0 if can post now)
    """
    if can_post(platform, brand):
        return 0

    state = load_rate_state()
    key = f"{platform}:{brand}" if brand else platform

    if key not in state:
        return 0

    window_start = utc_now() - timedelta(hours=1)
    posts = state[key].get("posts", [])

    recent_posts = sorted([
        datetime.fromisoformat(p) for p in posts
        if datetime.fromisoformat(p) > window_start
    ])

    if not recent_posts:
        return 0

    # When will the oldest post fall outside the window?
    oldest = recent_posts[0]
    can_post_at = oldest + timedelta(hours=1)
    wait = (can_post_at - utc_now()).total_seconds()

    return max(0, int(wait))


def get_rate_status() -> dict[str, Any]:
    """Get current rate limit status for all platforms.

    Returns:
        Dict with platform statuses
    """
    state = load_rate_state()
    status = {}

    window_start = utc_now() - timedelta(hours=1)

    for key, data in state.items():
        posts = data.get("posts", [])
        recent = len([p for p in posts if datetime.fromisoformat(p) > window_start])

        platform = key.split(":")[0]
        limit = DEFAULT_LIMITS.get(platform, 10)

        status[key] = {
            "posts_last_hour": recent,
            "limit": limit,
            "available": limit - recent,
            "can_post": recent < limit,
        }

    return status
