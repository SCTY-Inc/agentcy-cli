"""Shared API clients with lazy initialization."""

from __future__ import annotations

import os
from functools import lru_cache


class ClientError(Exception):
    """Error initializing or using client."""

    pass


@lru_cache(maxsize=1)
def get_exa_client():
    """Singleton Exa client; raises ClientError if exa-py missing or EXA_API_KEY unset."""
    try:
        from exa_py import Exa
    except ImportError:
        raise ClientError("exa-py required: pip install exa-py")

    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise ClientError("EXA_API_KEY environment variable required")

    return Exa(api_key=api_key)
