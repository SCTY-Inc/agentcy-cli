"""Reddit subreddit discovery.

Find relevant subreddits based on:
1. Keyword search via Reddit's search API
2. LLM analysis of brand/industry context
3. Subreddit metadata scoring (subscribers, activity)
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agentcy.brand.core.config import utc_now

logger = logging.getLogger(__name__)

from agentcy.brand.core.llm import complete_json


@dataclass
class SubredditInfo:
    """Discovered subreddit with metadata."""
    name: str
    title: str
    description: str
    subscribers: int
    active_users: int
    created_utc: float
    is_nsfw: bool
    relevance_score: float = 0.0
    discovery_method: str = ""


class SubredditDiscovery:
    """Discover relevant subreddits for a brand.

    Usage:
        discovery = SubredditDiscovery()

        # Search-based discovery
        subs = discovery.search("artificial intelligence startup")

        # LLM-based discovery (analyzes brand context)
        subs = discovery.discover_for_brand(
            brand_name="Acme AI",
            industry="B2B SaaS",
            keywords=["AI", "automation", "enterprise"],
            target_audience="CTOs and engineering leaders"
        )

        # Get subreddit details
        info = discovery.get_subreddit_info("MachineLearning")
    """

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.user_agent = "brandOS-Discovery/1.0"

    def search(self, query: str, limit: int = 25) -> list[SubredditInfo]:
        """Search for subreddits matching a query."""
        url = f"https://www.reddit.com/subreddits/search.json?q={urllib.parse.quote(query)}&limit={limit}"

        try:
            data = self._fetch_json(url)
            children = data.get("data", {}).get("children", [])

            results = []
            for child in children:
                sub = child.get("data", {})
                if sub.get("over18", False):  # Skip NSFW
                    continue

                info = SubredditInfo(
                    name=sub.get("display_name", ""),
                    title=sub.get("title", ""),
                    description=sub.get("public_description", "")[:500],
                    subscribers=sub.get("subscribers", 0),
                    active_users=sub.get("accounts_active", 0),
                    created_utc=sub.get("created_utc", 0),
                    is_nsfw=sub.get("over18", False),
                    discovery_method="search",
                )
                results.append(info)

            # Sort by subscribers (proxy for relevance)
            results.sort(key=lambda x: x.subscribers, reverse=True)
            return results

        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning("Subreddit search error: %s", e)
            return []

    def get_subreddit_info(self, name: str) -> SubredditInfo | None:
        """Get detailed info about a specific subreddit."""
        url = f"https://www.reddit.com/r/{name}/about.json"

        try:
            data = self._fetch_json(url)
            sub = data.get("data", {})

            return SubredditInfo(
                name=sub.get("display_name", name),
                title=sub.get("title", ""),
                description=sub.get("public_description", "")[:500],
                subscribers=sub.get("subscribers", 0),
                active_users=sub.get("accounts_active", 0),
                created_utc=sub.get("created_utc", 0),
                is_nsfw=sub.get("over18", False),
                discovery_method="direct",
            )
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning("Subreddit info error for r/%s: %s", name, e)
            return None

    def get_trending(self, limit: int = 10) -> list[SubredditInfo]:
        """Get currently popular/trending subreddits."""
        url = f"https://www.reddit.com/subreddits/popular.json?limit={limit}"

        try:
            data = self._fetch_json(url)
            children = data.get("data", {}).get("children", [])

            results = []
            for child in children:
                sub = child.get("data", {})
                if sub.get("over18", False):
                    continue

                info = SubredditInfo(
                    name=sub.get("display_name", ""),
                    title=sub.get("title", ""),
                    description=sub.get("public_description", "")[:500],
                    subscribers=sub.get("subscribers", 0),
                    active_users=sub.get("accounts_active", 0),
                    created_utc=sub.get("created_utc", 0),
                    is_nsfw=sub.get("over18", False),
                    discovery_method="trending",
                )
                results.append(info)

            return results
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning("Trending fetch error: %s", e)
            return []

    def discover_for_brand(
        self,
        brand_name: str,
        industry: str | None = None,
        keywords: list[str] | None = None,
        target_audience: str | None = None,
        use_llm: bool = True,
    ) -> list[SubredditInfo]:
        """Discover subreddits relevant to a brand.

        Combines:
        1. Keyword search (from brand keywords)
        2. LLM suggestions (understands industry context)
        3. Metadata scoring (filters low-quality/inactive)
        """
        discovered: dict[str, SubredditInfo] = {}

        # 1. Search-based discovery from keywords
        search_terms = keywords or []
        if industry:
            search_terms.append(industry)

        for term in search_terms[:5]:  # Limit searches
            results = self.search(term, limit=10)
            for sub in results:
                if sub.name not in discovered:
                    discovered[sub.name] = sub

        # 2. LLM-based discovery
        if use_llm and (industry or keywords or target_audience):
            llm_suggestions = self._llm_suggest(
                brand_name=brand_name,
                industry=industry,
                keywords=keywords,
                target_audience=target_audience,
            )

            for sub_name in llm_suggestions:
                if sub_name not in discovered:
                    info = self.get_subreddit_info(sub_name)
                    if info:
                        info.discovery_method = "llm"
                        discovered[sub_name] = info

        # 3. Score and filter
        results = list(discovered.values())
        for sub in results:
            sub.relevance_score = self._score_subreddit(sub, keywords or [])

        # Filter: minimum subscribers, not dead
        results = [
            s for s in results
            if s.subscribers >= 1000 and s.active_users >= 10
        ]

        # Sort by relevance
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results[:20]  # Top 20

    def _llm_suggest(
        self,
        brand_name: str,
        industry: str | None,
        keywords: list[str] | None,
        target_audience: str | None,
    ) -> list[str]:
        """Use LLM to suggest relevant subreddits."""
        context = f"Brand: {brand_name}"
        if industry:
            context += f"\nIndustry: {industry}"
        if keywords:
            context += f"\nKeywords: {', '.join(keywords)}"
        if target_audience:
            context += f"\nTarget audience: {target_audience}"

        prompt = f"""Given this brand context:

{context}

Suggest 10-15 Reddit subreddits that would be valuable for monitoring:
- Industry discussions
- Target audience communities
- Competitor/alternative discussions
- Related technology or trends

Return JSON: {{"subreddits": ["subreddit1", "subreddit2", ...]}}

Only include real, active subreddits. No r/ prefix."""

        result = complete_json(
            prompt=prompt,
            system="You are an expert at finding relevant online communities for market research.",
            default={"subreddits": []},
        )

        return result.get("subreddits", [])

    def _score_subreddit(self, sub: SubredditInfo, keywords: list[str]) -> float:
        """Score subreddit relevance."""
        score = 0.0

        # Subscriber score (log scale)
        if sub.subscribers > 0:
            import math
            score += min(0.3, math.log10(sub.subscribers) / 20)

        # Activity score
        if sub.active_users > 0:
            score += min(0.2, sub.active_users / 5000)

        # Keyword match in description
        desc_lower = (sub.description + " " + sub.title).lower()
        keyword_matches = sum(1 for kw in keywords if kw.lower() in desc_lower)
        score += min(0.3, keyword_matches * 0.1)

        # Discovery method bonus
        if sub.discovery_method == "llm":
            score += 0.1  # LLM suggestions are contextual

        # Age bonus (established communities)
        if sub.created_utc > 0:
            age_years = (utc_now().timestamp() - sub.created_utc) / (365 * 24 * 3600)
            if age_years > 2:
                score += 0.1

        return min(1.0, score)

    def _fetch_json(self, url: str) -> dict:
        """Fetch JSON from URL."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent}
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode())


def discover_subreddits_for_brand(brand_config: dict) -> list[str]:
    """Convenience function to discover subreddits from brand config.

    Uses brand.yml fields:
    - name: Brand name
    - industry: Industry/sector
    - keywords: Monitoring keywords
    - target_audience: Who the brand targets
    """
    discovery = SubredditDiscovery()

    results = discovery.discover_for_brand(
        brand_name=brand_config.get("name", "Unknown"),
        industry=brand_config.get("industry"),
        keywords=brand_config.get("keywords", []),
        target_audience=brand_config.get("target_audience"),
        use_llm=True,
    )

    return [s.name for s in results]
