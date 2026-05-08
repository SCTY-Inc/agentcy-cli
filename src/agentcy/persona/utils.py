"""Utility functions for prsna."""

from __future__ import annotations

# Re-export from the shared protocol layer.  The canonical implementation
# handles markdown code-block fences and bare-object extraction in addition
# to plain ``json.loads``, so persona callers get a strictly better parser
# for free.
from agentcy.protocols.utils import parse_llm_json  # noqa: F401
