from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _project_metadata() -> dict:
    with PYPROJECT_PATH.open("rb") as fh:
        return tomllib.load(fh)


def test_root_package_keeps_install_profiles_out_of_default_metadata() -> None:
    project = _project_metadata()["project"]

    assert "optional-dependencies" not in project


def test_root_package_has_readme_metadata() -> None:
    project = _project_metadata()["project"]

    assert project["readme"] == "README.md"
