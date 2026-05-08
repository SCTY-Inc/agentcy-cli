from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _project_metadata() -> dict:
    with PYPROJECT_PATH.open("rb") as fh:
        return tomllib.load(fh)


def test_root_package_exposes_install_profile_extras() -> None:
    extras = _project_metadata()["project"]["optional-dependencies"]

    assert "persona" in extras
    assert "forecast-simulation" in extras
    assert "brand-all" in extras
    assert "full" in extras


def test_root_package_has_readme_metadata() -> None:
    assert _project_metadata()["project"]["readme"] == "README.md"
