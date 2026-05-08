"""Shared API clients with lazy initialization."""

from __future__ import annotations

import os
from functools import lru_cache


class ClientError(Exception):
    """Error initializing or using client."""

    pass


@lru_cache(maxsize=1)
def get_exa_client():
    """Get or create Exa client (singleton).

    Returns:
        Configured Exa client

    Raises:
        ClientError: If exa-py not installed or API key missing
    """
    try:
        from exa_py import Exa
    except ImportError:
        raise ClientError("exa-py required: pip install exa-py")

    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise ClientError("EXA_API_KEY environment variable required")

    return Exa(api_key=api_key)
