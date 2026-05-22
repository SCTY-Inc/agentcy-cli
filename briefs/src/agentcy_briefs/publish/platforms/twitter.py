"""Twitter/X publishing."""
from __future__ import annotations

import os
from typing import Any


def post_tweet(
    content: str,
    credentials: dict[str, str] | None = None,
    media_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Post a tweet.

    Args:
        content: Tweet text
        credentials: OAuth credentials (or use env vars)
        media_paths: Optional media file paths

    Returns:
        Result dict with tweet_id or error
    """
    # Get credentials from env if not provided
    if credentials is None:
        credentials = {
            "consumer_key": os.getenv("TWITTER_CONSUMER_KEY"),
            "consumer_secret": os.getenv("TWITTER_CONSUMER_SECRET"),
            "access_token": os.getenv("TWITTER_ACCESS_TOKEN"),
            "access_token_secret": os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
        }

    # Validate credentials
    if not all(credentials.values()):
        return {
            "success": False,
            "error": "Missing Twitter credentials. Set TWITTER_* env vars.",
        }

    try:
        import tweepy
    except ImportError:
        return {
            "success": False,
            "error": "tweepy required. Install with: pip install tweepy",
        }

    try:
        client = tweepy.Client(
            consumer_key=credentials["consumer_key"],
            consumer_secret=credentials["consumer_secret"],
            access_token=credentials["access_token"],
            access_token_secret=credentials["access_token_secret"],
        )

        response = client.create_tweet(text=content)

        return {
            "success": True,
            "tweet_id": response.data["id"],
            "url": f"https://twitter.com/i/web/status/{response.data['id']}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def validate_credentials() -> bool:
    """Check if Twitter credentials are configured."""
    required = [
        "TWITTER_CONSUMER_KEY",
        "TWITTER_CONSUMER_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET",
    ]
    return all(os.getenv(key) for key in required)
