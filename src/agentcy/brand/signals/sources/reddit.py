"""Reddit signal source.

Uses Reddit's public JSON API (no auth needed).
Configure subreddits in brand.yml or auto-suggest based on keywords.
"""

from __future__ import annotations

import hashlib
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

from agentcy.brand.signals.schema import Signal, SignalSource, SignalType, Urgency

# Common subreddits by category for auto-suggestion
SUBREDDIT_CATEGORIES = {
    "tech": ["technology", "programming", "startups", "SaaS", "artificial"],
    "marketing": ["marketing", "digital_marketing", "socialmedia", "SEO", "content_marketing"],
    "business": ["business", "smallbusiness", "entrepreneur", "Entrepreneur"],
    "finance": ["finance", "investing", "stocks", "CryptoCurrency", "personalfinance"],
    "healthcare": ["healthcare", "medicine", "HealthIT", "CaregiverSupport"],
    "ecommerce": ["ecommerce", "shopify", "FulfillmentByAmazon", "dropship"],
    "ai": ["MachineLearning", "artificial", "LocalLLaMA", "ChatGPT", "ClaudeAI"],
    "news": ["news", "worldnews", "technology", "business"],
}

# Mapping keywords to subreddit categories
KEYWORD_TO_CATEGORY = {
    "ai": "ai",
    "artificial intelligence": "ai",
    "machine learning": "ai",
    "llm": "ai",
    "chatbot": "ai",
    "marketing": "marketing",
    "advertising": "marketing",
    "seo": "marketing",
    "content": "marketing",
    "social media": "marketing",
    "startup": "tech",
    "saas": "tech",
    "software": "tech",
    "app": "tech",
    "tech": "tech",
    "finance": "finance",
    "investing": "finance",
    "stock": "finance",
    "crypto": "finance",
    "health": "healthcare",
    "medical": "healthcare",
    "caregiver": "healthcare",
    "patient": "healthcare",
    "ecommerce": "ecommerce",
    "shop": "ecommerce",
    "retail": "ecommerce",
}


class RedditSource:
    """Fetch signals from Reddit subreddits.

    Usage:
        source = RedditSource()

        # With explicit subreddits
        signals = await source.fetch(
            brand="acme",
            subreddits=["startups", "SaaS"],
        )

        # Auto-suggest based on keywords
        subreddits = source.suggest_subreddits(["AI", "startup", "marketing"])
        signals = await source.fetch(brand="acme", subreddits=subreddits)
    """

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.user_agent = "brandOS-Signal-Fetcher/1.0"
        self._seen: set[str] = set()

    def suggest_subreddits(self, keywords: list[str], max_per_category: int = 2) -> list[str]:
        """Suggest relevant subreddits based on brand keywords."""
        categories_found: set[str] = set()

        for keyword in keywords:
            kw_lower = keyword.lower()
            for kw_pattern, category in KEYWORD_TO_CATEGORY.items():
                if kw_pattern in kw_lower:
                    categories_found.add(category)

        # Default to tech + news if no matches
        if not categories_found:
            categories_found = {"tech", "news"}

        subreddits: list[str] = []
        for category in categories_found:
            subs = SUBREDDIT_CATEGORIES.get(category, [])
            subreddits.extend(subs[:max_per_category])

        return list(set(subreddits))  # Dedupe

    async def fetch(
        self,
        brand: str,
        subreddits: list[str],
        keywords: list[str] | None = None,
        limit_per_sub: int = 25,
        min_score: int = 5,
    ) -> list[Signal]:
        """Fetch posts from subreddits and convert to signals."""
        signals: list[Signal] = []

        for subreddit in subreddits:
            try:
                posts = self._fetch_subreddit(subreddit, limit_per_sub)

                for post in posts:
                    # Filter by score
                    if post.get("score", 0) < min_score:
                        continue

                    signal = self._post_to_signal(post, brand, subreddit)

                    # Deduplication
                    if signal.id in self._seen:
                        continue
                    self._seen.add(signal.id)

                    # Keyword filtering
                    if keywords and not self._matches_keywords(signal, keywords):
                        continue

                    signals.append(signal)

            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.warning("Reddit fetch error for r/%s: %s", subreddit, e)

        return signals

    def _fetch_subreddit(self, subreddit: str, limit: int = 25) -> list[dict]:
        """Fetch posts from a subreddit using public JSON API."""
        url = f"https://www.reddit.com/r/{subreddit}/.json?limit={limit}"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent}
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            data = json.loads(response.read().decode())

        children = data.get("data", {}).get("children", [])
        return [child.get("data", {}) for child in children]

    def _post_to_signal(self, post: dict, brand: str, subreddit: str) -> Signal:
        """Convert Reddit post to Signal."""
        post_id = post.get("id", "")
        content_hash = hashlib.sha256(post_id.encode()).hexdigest()[:12]

        title = post.get("title", "")
        selftext = post.get("selftext", "")[:1000]
        content = f"{title}\n\n{selftext}".strip() if selftext else title

        # Determine urgency based on score and comments
        score = post.get("score", 0)
        comments = post.get("num_comments", 0)

        urgency = Urgency.LOW
        if score > 1000 or comments > 100:
            urgency = Urgency.HIGH
        elif score > 100 or comments > 20:
            urgency = Urgency.MEDIUM

        # Determine signal type
        signal_type = SignalType.MENTION
        flair = (post.get("link_flair_text") or "").lower()
        if "news" in flair or "announcement" in flair:
            signal_type = SignalType.NEWS
        elif "discussion" in flair:
            signal_type = SignalType.TREND

        return Signal(
            id=content_hash,
            source=SignalSource.SOCIAL_REDDIT,
            signal_type=signal_type,
            brand=brand,
            title=title[:200],
            content=content,
            url=f"https://reddit.com{post.get('permalink', '')}",
            relevance_score=min(1.0, score / 1000),  # Normalize score
            urgency=urgency,
            metadata={
                "subreddit": subreddit,
                "author": post.get("author", "[deleted]"),
                "score": score,
                "num_comments": comments,
                "flair": post.get("link_flair_text"),
                "created_utc": post.get("created_utc"),
                "is_self": post.get("is_self", False),
            },
        )

    def _matches_keywords(self, signal: Signal, keywords: list[str]) -> bool:
        """Check if signal matches any keyword."""
        text = f"{signal.title} {signal.content}".lower()
        return any(kw.lower() in text for kw in keywords)


def get_subreddits_for_brand(brand_config: dict, use_discovery: bool = True) -> list[str]:
    """Get subreddits from brand config, discovery, or fallback.

    Priority:
    1. brand_config["subreddits"] - explicit list
    2. Discovery API (search + LLM) - if industry/keywords set
    3. Keyword-based suggestion - simple fallback
    """
    # Explicit subreddits always take priority
    explicit = brand_config.get("subreddits", [])
    if explicit:
        return explicit

    # Try discovery if we have enough context
    if use_discovery:
        has_context = (
            brand_config.get("industry")
            or brand_config.get("keywords")
            or brand_config.get("target_audience")
        )
        if has_context:
            try:
                from agentcy.brand.signals.sources.reddit_discover import (
                    discover_subreddits_for_brand,
                )
                discovered = discover_subreddits_for_brand(brand_config)
                if discovered:
                    return discovered[:10]  # Limit to top 10
            except (ImportError, OSError, RuntimeError) as e:
                logger.warning("Subreddit discovery failed: %s", e)

    # Fallback: simple keyword-based suggestion
    keywords = brand_config.get("keywords", [])
    if keywords:
        source = RedditSource()
        return source.suggest_subreddits(keywords)

    # Default
    return ["technology", "business", "startups"]
