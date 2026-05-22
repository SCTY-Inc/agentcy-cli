import importlib
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _project_metadata() -> dict:
    with PYPROJECT_PATH.open("rb") as fh:
        return tomllib.load(fh)


def test_distribution_name_stays_agentcy_echo():
    project = _project_metadata()["project"]

    assert project["name"] == "agentcy-forecast"


def test_simulation_dependencies_are_optional_and_pinned():
    project = _project_metadata()["project"]
    dependencies = project["dependencies"]
    simulation_requirements = (REPO_ROOT / "requirements-simulation.txt").read_text(
        encoding="utf-8"
    )
    simulation_lock = (REPO_ROOT / "requirements-simulation.lock").read_text(
        encoding="utf-8"
    )

    assert all(not dep.startswith("camel-oasis") for dep in dependencies)
    assert all(not dep.startswith("camel-ai") for dep in dependencies)
    assert "optional-dependencies" not in project
    assert "vendor/camel_oasis-0.2.5-py3-none-any.whl" in simulation_requirements
    assert "camel-ai==0.2.78" in simulation_requirements
    assert "rich==" in simulation_lock
    assert "typer==" in simulation_lock


def test_console_script_stays_agentcy_echo_to_app_cli_main():
    project = _project_metadata()["project"]

    assert project["scripts"] == {"agentcy-forecast": "agentcy_forecast.cli:main"}


def test_wheel_packages_stay_on_agentcy_forecast_import_root():
    wheel_target = _project_metadata()["tool"]["hatch"]["build"]["targets"]["wheel"]

    assert wheel_target["packages"] == ["agentcy_forecast"]


def test_repo_local_agentcy_forecast_import_smoke_and_cli_main_surface():
    pkg = importlib.import_module("agentcy_forecast")
    cli = importlib.import_module("agentcy_forecast.cli")

    assert Path(pkg.__file__).resolve().parent == REPO_ROOT / "agentcy_forecast"
    assert callable(cli.main)
