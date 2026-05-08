"""Generic web signal provider."""
from __future__ import annotations

from typing import Any

import httpx

from agentcy.brand.core.config import utc_now


def fetch_web_signals(
    urls: list[str],
    extract_links: bool = True,
) -> list[dict[str, Any]]:
    """Fetch signals from web URLs.

    Args:
        urls: List of URLs to fetch
        extract_links: Whether to extract links from pages

    Returns:
        List of signal dicts
    """
    signals = []

    with httpx.Client(timeout=30) as client:
        for url in urls:
            try:
                response = client.get(url)
                response.raise_for_status()

                signal = {
                    "source": "web",
                    "url": url,
                    "fetched_at": utc_now().isoformat(),
                    "status_code": response.status_code,
                }

                # Extract title
                title = _extract_title(response.text)
                if title:
                    signal["headline"] = title

                # Extract links if requested
                if extract_links:
                    links = _extract_links(response.text, url)
                    signal["links"] = links[:10]  # Limit links

                signals.append(signal)

            except httpx.HTTPError:
                continue

    return signals


def _extract_title(html: str) -> str | None:
    """Extract page title from HTML."""
    import re

    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        import html as html_module
        return html_module.unescape(match.group(1)).strip()
    return None


def _extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    """Extract links from HTML."""
    import re
    from urllib.parse import urljoin

    links = []
    pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'

    for match in re.finditer(pattern, html, re.IGNORECASE | re.DOTALL):
        href = match.group(1)
        text = re.sub(r"<[^>]+>", "", match.group(2)).strip()

        # Resolve relative URLs
        full_url = urljoin(base_url, href)

        # Skip anchors and javascript
        if full_url.startswith(("http://", "https://")):
            links.append({
                "url": full_url,
                "text": text[:100] if text else "",
            })

    return links
