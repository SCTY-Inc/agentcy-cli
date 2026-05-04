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

    assert project["name"] == "agentcy-echo"


def test_simulation_dependencies_are_optional_and_pinned():
    project = _project_metadata()["project"]
    dependencies = project["dependencies"]
    simulation_extra = project["optional-dependencies"]["simulation"]

    assert all(not dep.startswith("camel-oasis") for dep in dependencies)
    assert all(not dep.startswith("camel-ai") for dep in dependencies)
    # camel-oasis is vendored in vendor/ and referenced via [tool.uv.sources]
    assert any("camel-oasis==0.2.5" in dep for dep in simulation_extra)
    assert "camel-ai==0.2.78" in simulation_extra


def test_console_script_stays_agentcy_echo_to_app_cli_main():
    project = _project_metadata()["project"]

    assert project["scripts"] == {"agentcy-echo": "app.cli:main"}


def test_wheel_packages_stay_on_app_import_root():
    wheel_target = _project_metadata()["tool"]["hatch"]["build"]["targets"]["wheel"]

    assert wheel_target["packages"] == ["app"]


def test_repo_local_app_import_smoke_and_cli_main_surface():
    app = importlib.import_module("app")
    cli = importlib.import_module("app.cli")

    assert Path(app.__file__).resolve().parent == REPO_ROOT / "app"
    assert callable(cli.main)
