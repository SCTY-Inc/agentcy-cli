"""Signal sources for data ingestion."""

from agentcy_briefs.signals.sources.reddit import RedditSource, get_subreddits_for_brand
from agentcy_briefs.signals.sources.reddit_discover import (
    SubredditDiscovery,
    discover_subreddits_for_brand,
)
from agentcy_briefs.signals.sources.rss import RSSSource

__all__ = [
    "RSSSource",
    "RedditSource",
    "get_subreddits_for_brand",
    "SubredditDiscovery",
    "discover_subreddits_for_brand",
]
