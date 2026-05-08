"""RSS/Atom feed signal source.

Zero cost, no API keys, no rate limits. Works immediately.
"""

from __future__ import annotations

import hashlib
import logging

import httpx

logger = logging.getLogger(__name__)

from agentcy.brand.signals.schema import Signal, SignalSource, SignalType, Urgency


class RSSSource:
    """Fetch signals from RSS/Atom feeds.

    Usage:
        source = RSSSource()
        signals = await source.fetch(
            brand="acme",
            feeds=["https://news.ycombinator.com/rss"],
            keywords=["AI", "startup"],
        )
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._seen: set[str] = set()  # Deduplication

    async def fetch(
        self,
        brand: str,
        feeds: list[str],
        keywords: list[str] | None = None,
        max_per_feed: int = 20,
    ) -> list[Signal]:
        """Fetch and parse RSS feeds, filter by keywords."""
        signals: list[Signal] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for feed_url in feeds:
                try:
                    items = await self._fetch_feed(client, feed_url)
                    for item in items[:max_per_feed]:
                        signal = self._item_to_signal(item, brand, feed_url)

                        # Deduplication
                        if signal.id in self._seen:
                            continue
                        self._seen.add(signal.id)

                        # Keyword filtering
                        if keywords and not self._matches_keywords(signal, keywords):
                            continue

                        signals.append(signal)
                except (OSError, httpx.HTTPError, ValueError) as e:
                    # Log but don't fail the whole batch
                    logger.warning("RSS fetch error for %s: %s", feed_url, e)

        return signals

    async def _fetch_feed(self, client: httpx.AsyncClient, url: str) -> list[dict]:
        """Fetch and parse a single feed."""
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return self._parse_feed(response.text)

    def _parse_feed(self, xml: str) -> list[dict]:
        """Simple RSS/Atom parser without external deps."""
        items = []

        # Quick and dirty XML parsing for RSS items
        import re

        # Try RSS format first
        item_pattern = re.compile(r'<item>(.*?)</item>', re.DOTALL)
        title_pattern = re.compile(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', re.DOTALL)
        link_pattern = re.compile(r'<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>', re.DOTALL)
        desc_pattern = re.compile(r'<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>', re.DOTALL)
        pubdate_pattern = re.compile(r'<pubDate>(.*?)</pubDate>', re.DOTALL)

        for match in item_pattern.finditer(xml):
            item_xml = match.group(1)

            title_match = title_pattern.search(item_xml)
            link_match = link_pattern.search(item_xml)
            desc_match = desc_pattern.search(item_xml)
            pubdate_match = pubdate_pattern.search(item_xml)

            items.append({
                "title": title_match.group(1).strip() if title_match else "",
                "link": link_match.group(1).strip() if link_match else "",
                "description": desc_match.group(1).strip() if desc_match else "",
                "pubDate": pubdate_match.group(1).strip() if pubdate_match else "",
            })

        # Try Atom format if no RSS items found
        if not items:
            entry_pattern = re.compile(r'<entry>(.*?)</entry>', re.DOTALL)
            atom_link_pattern = re.compile(r'<link[^>]*href=["\']([^"\']+)["\']', re.DOTALL)
            content_pattern = re.compile(r'<(?:content|summary)[^>]*>(.*?)</(?:content|summary)>', re.DOTALL)
            updated_pattern = re.compile(r'<updated>(.*?)</updated>', re.DOTALL)

            for match in entry_pattern.finditer(xml):
                entry_xml = match.group(1)

                title_match = title_pattern.search(entry_xml)
                link_match = atom_link_pattern.search(entry_xml)
                content_match = content_pattern.search(entry_xml)
                updated_match = updated_pattern.search(entry_xml)

                items.append({
                    "title": title_match.group(1).strip() if title_match else "",
                    "link": link_match.group(1).strip() if link_match else "",
                    "description": content_match.group(1).strip() if content_match else "",
                    "pubDate": updated_match.group(1).strip() if updated_match else "",
                })

        return items

    def _item_to_signal(self, item: dict, brand: str, feed_url: str) -> Signal:
        """Convert RSS item to Signal."""

        content_hash = hashlib.sha256(
            (item.get("link", "") + item.get("title", "")).encode()
        ).hexdigest()[:12]

        # Strip HTML tags from description
        import re
        description = re.sub(r'<[^>]+>', '', item.get("description", ""))[:1000]

        return Signal(
            id=content_hash,
            source=SignalSource.NEWS,
            signal_type=SignalType.NEWS,
            brand=brand,
            title=item.get("title", "")[:200],
            content=description,
            url=item.get("link"),
            relevance_score=0.5,  # Will be scored by agent
            urgency=Urgency.MEDIUM,
            metadata={"feed_url": feed_url, "raw_pubdate": item.get("pubDate", "")},
        )

    def _matches_keywords(self, signal: Signal, keywords: list[str]) -> bool:
        """Check if signal matches any keyword."""
        text = f"{signal.title} {signal.content}".lower()
        return any(kw.lower() in text for kw in keywords)


# Default feeds for general tech/business intel
DEFAULT_FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.techmeme.com/feed.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
]
