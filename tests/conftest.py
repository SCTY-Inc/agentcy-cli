"""Isolate dispatcher tests from caller env + module state."""

import os

import pytest

from agentcy import cli

_LEAKY_VARS = (
    "LLM_PROVIDER",
    "CLAUDE_MODEL",
    "AGENTCY_BRIEFS_LLM_PROVIDER",
    "AGENTCY_BRIEFS_LLM_MODEL",
)


@pytest.fixture(autouse=True)
def _reset_overrides(monkeypatch) -> None:
    cli._OVERRIDES.provider = None
    cli._OVERRIDES.model = None
    for var in _LEAKY_VARS:
        if var in os.environ:
            monkeypatch.delenv(var)
