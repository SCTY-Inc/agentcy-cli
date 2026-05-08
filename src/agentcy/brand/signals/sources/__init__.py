"""Signal sources for data ingestion."""

from agentcy.brand.signals.sources.rss import RSSSource
from agentcy.brand.signals.sources.reddit import RedditSource, get_subreddits_for_brand
from agentcy.brand.signals.sources.reddit_discover import SubredditDiscovery, discover_subreddits_for_brand

__all__ = [
    "RSSSource",
    "RedditSource",
    "get_subreddits_for_brand",
    "SubredditDiscovery",
    "discover_subreddits_for_brand",
]
