"""Generic web scraping utilities."""
from __future__ import annotations

from typing import Any

import httpx


def fetch_url(url: str, timeout: int = 30) -> str:
    """Fetch content from a URL.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Response text
    """
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def parse_html(html: str) -> Any:
    """Parse HTML content.

    Requires: beautifulsoup4 optional dependency
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("beautifulsoup4 required. Install with: pip install agentcy-compass[intel]")

    return BeautifulSoup(html, "html.parser")


def extract_text(html: str) -> str:
    """Extract text content from HTML."""
    soup = parse_html(html)
    return soup.get_text(separator="\n", strip=True)


def extract_links(html: str, base_url: str | None = None) -> list[dict[str, str]]:
    """Extract links from HTML.

    Args:
        html: HTML content
        base_url: Base URL for resolving relative links

    Returns:
        List of dicts with 'href' and 'text' keys
    """
    from urllib.parse import urljoin

    soup = parse_html(html)
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if base_url:
            href = urljoin(base_url, href)

        links.append({
            "href": href,
            "text": a.get_text(strip=True),
        })

    return links
