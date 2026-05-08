"""Google News signal provider."""
from __future__ import annotations

from typing import Any

import httpx

from agentcy.brand.core.config import utc_now


def fetch_google_news(
    query: str,
    limit: int = 20,
    language: str = "en",
    country: str = "US",
) -> list[dict[str, Any]]:
    """Fetch signals from Google News RSS.

    Args:
        query: Search query
        limit: Max results
        language: Language code
        country: Country code

    Returns:
        List of signal dicts
    """
    from urllib.parse import quote

    # Google News RSS URL
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl={language}-{country}&gl={country}&ceid={country}:{language}"

    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(url)
            response.raise_for_status()
            xml_content = response.text
    except httpx.HTTPError as e:
        return []

    # Parse RSS XML
    signals = _parse_rss(xml_content, limit)

    return signals


def _parse_rss(xml_content: str, limit: int) -> list[dict[str, Any]]:
    """Parse RSS XML content."""
    import re

    signals = []

    # Simple XML parsing without external deps
    items = re.findall(r"<item>(.*?)</item>", xml_content, re.DOTALL)

    for item in items[:limit]:
        title_match = re.search(r"<title>(.*?)</title>", item)
        link_match = re.search(r"<link>(.*?)</link>", item)
        pubdate_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
        source_match = re.search(r"<source.*?>(.*?)</source>", item)

        signal = {
            "source": "google_news",
            "headline": _clean_html(title_match.group(1)) if title_match else "",
            "url": link_match.group(1) if link_match else "",
            "published_at": pubdate_match.group(1) if pubdate_match else "",
            "publisher": source_match.group(1) if source_match else "",
            "fetched_at": utc_now().isoformat(),
        }

        if signal["headline"]:
            signals.append(signal)

    return signals


def _clean_html(text: str) -> str:
    """Remove HTML entities and tags."""
    import html
    import re

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
