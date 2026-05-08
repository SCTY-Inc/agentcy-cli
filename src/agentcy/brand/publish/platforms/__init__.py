"""Social platform publishers."""
from typing import Any

# Platform publisher registry
_publishers: dict[str, Any] = {}


def register_publisher(platform: str, publisher: Any) -> None:
    """Register a platform publisher."""
    _publishers[platform] = publisher


def get_publisher(platform: str) -> Any:
    """Get a platform publisher."""
    return _publishers.get(platform)


def list_platforms() -> list[str]:
    """List available platforms."""
    return list(_publishers.keys())


# Import and register publishers
try:
    from agentcy.brand.publish.platforms.twitter import post_tweet
    register_publisher("twitter", post_tweet)
except ImportError:
    pass

try:
    from agentcy.brand.publish.platforms.linkedin import post_linkedin
    register_publisher("linkedin", post_linkedin)
except ImportError:
    pass
