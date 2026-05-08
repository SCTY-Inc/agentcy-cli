"""Apify scraper integration."""
from __future__ import annotations

import os
from typing import Any


def get_apify_client():
    """Get Apify client instance."""
    try:
        from apify_client import ApifyClient
    except ImportError:
        raise ImportError("apify-client required. Install with: pip install agentcy-compass[intel]")

    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise ValueError("APIFY_TOKEN environment variable required")

    return ApifyClient(token)


def scrape_posts(
    platform: str,
    handle: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Scrape posts from a social platform.

    Args:
        platform: Platform name (twitter, instagram, etc.)
        handle: Account handle
        limit: Maximum posts to retrieve

    Returns:
        List of post data
    """
    scrapers = {
        "twitter": _scrape_twitter,
        "x": _scrape_twitter,
        "instagram": _scrape_instagram,
        "linkedin": _scrape_linkedin,
    }

    scraper = scrapers.get(platform.lower())
    if not scraper:
        raise ValueError(f"No scraper for platform: {platform}")

    return scraper(handle, limit)


def _scrape_twitter(handle: str, limit: int) -> list[dict[str, Any]]:
    """Scrape Twitter/X posts."""
    client = get_apify_client()

    # Use Twitter scraper actor
    run_input = {
        "handle": [handle.lstrip("@")],
        "maxTweets": limit,
        "mode": "profile",
    }

    # Common Twitter scraper actor ID
    run = client.actor("quacker/twitter-scraper").call(run_input=run_input)

    posts = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        posts.append({
            "platform": "twitter",
            "id": item.get("id"),
            "text": item.get("text", item.get("full_text", "")),
            "created_at": item.get("created_at"),
            "likes": item.get("favorite_count", item.get("likes", 0)),
            "retweets": item.get("retweet_count", item.get("retweets", 0)),
            "replies": item.get("reply_count", item.get("replies", 0)),
            "views": item.get("views", item.get("impressions", 0)),
            "url": item.get("url"),
            "media": item.get("media", []),
        })

    return posts


def _scrape_instagram(handle: str, limit: int) -> list[dict[str, Any]]:
    """Scrape Instagram posts."""
    client = get_apify_client()

    run_input = {
        "username": [handle.lstrip("@")],
        "resultsLimit": limit,
    }

    run = client.actor("apify/instagram-scraper").call(run_input=run_input)

    posts = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        posts.append({
            "platform": "instagram",
            "id": item.get("id"),
            "text": item.get("caption", ""),
            "created_at": item.get("timestamp"),
            "likes": item.get("likesCount", 0),
            "comments": item.get("commentsCount", 0),
            "views": item.get("videoViewCount", 0),
            "url": item.get("url"),
            "media_type": item.get("type"),
        })

    return posts


def _scrape_linkedin(handle: str, limit: int) -> list[dict[str, Any]]:
    """Scrape LinkedIn posts."""
    client = get_apify_client()

    run_input = {
        "urls": [f"https://www.linkedin.com/in/{handle}/"],
        "limitPosts": limit,
    }

    run = client.actor("anchor/linkedin-profile-scraper").call(run_input=run_input)

    posts = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        for post in item.get("posts", []):
            posts.append({
                "platform": "linkedin",
                "id": post.get("urn"),
                "text": post.get("text", ""),
                "created_at": post.get("postedAt"),
                "likes": post.get("numLikes", 0),
                "comments": post.get("numComments", 0),
                "reposts": post.get("numShares", 0),
                "url": post.get("url"),
            })

    return posts
