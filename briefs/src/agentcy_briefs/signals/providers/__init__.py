"""Signal providers."""
from agentcy_briefs.signals.providers.google_news import fetch_google_news
from agentcy_briefs.signals.providers.web import fetch_web_signals

__all__ = ["fetch_google_news", "fetch_web_signals"]
