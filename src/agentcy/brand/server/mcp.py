"""MCP server surface.

This module is intentionally explicit that MCP is not wired into the current
repo build.
"""
from __future__ import annotations


def create_mcp_server():
    """Raise for the unimplemented MCP integration."""
    raise NotImplementedError("MCP server is not implemented in this build")
