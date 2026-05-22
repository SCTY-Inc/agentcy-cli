"""Shared pytest setup for repository-wide tests."""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("DSPY_CACHEDIR", str(Path(tempfile.gettempdir()) / "agentcy-dspy-cache"))
