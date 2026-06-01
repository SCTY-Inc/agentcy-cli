"""Social platform publishers."""
from collections.abc import Callable
from typing import Any

# Publisher callable: (content, credentials, media_paths) -> result dict
Publisher = Callable[..., dict[str, Any]]

# Platform publisher registry
_publishers: dict[str, Publisher] = {}


def register_publisher(platform: str, publisher: Publisher) -> None:
    """Register a platform publisher."""
    _publishers[platform] = publisher


def get_publisher(platform: str) -> Publisher | None:
    """Get a platform publisher."""
    return _publishers.get(platform)


def list_platforms() -> list[str]:
    """List available platforms."""
    return list(_publishers.keys())


# Import and register publishers
try:
    from agentcy_briefs.publish.platforms.twitter import post_tweet
    register_publisher("twitter", post_tweet)
except ImportError:
    pass

try:
    from agentcy_briefs.publish.platforms.linkedin import post_linkedin
    register_publisher("linkedin", post_linkedin)
except ImportError:
    pass
