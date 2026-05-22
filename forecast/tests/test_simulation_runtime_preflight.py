from agentcy_forecast.utils.oasis_llm import get_simulation_runtime_error, get_simulation_runtime_preflight


class _Version:
    def __init__(self, major: int, minor: int):
        self.major = major
        self.minor = minor


def test_simulation_runtime_accepts_python_311_when_camel_import_succeeds():
    assert (
        get_simulation_runtime_error(
            version_info=_Version(3, 11),
            camel_import_error=None,
            oasis_import_error=None,
        )
        is None
    )


def test_simulation_runtime_rejects_python_312_before_import_checks():
    message = get_simulation_runtime_error(
        version_info=_Version(3, 12),
        camel_import_error=ImportError("camel missing"),
        oasis_import_error=ImportError("oasis missing"),
    )

    assert message is not None
    assert "Python 3.11" in message
    assert "Python 3.12" in message
    assert "make install-forecast-simulation" in message


def test_simulation_runtime_reports_missing_optional_dependencies_on_python_311():
    message = get_simulation_runtime_error(
        version_info=_Version(3, 11),
        camel_import_error=ImportError("camel missing"),
        oasis_import_error=None,
    )

    assert message is not None
    assert "Optional simulation dependencies are not installed" in message
    assert "make install-forecast-simulation" in message


def test_simulation_runtime_requires_oasis_import_too():
    preflight = get_simulation_runtime_preflight(
        version_info=_Version(3, 11),
        camel_import_error=None,
        oasis_import_error=ImportError("No module named 'oasis'"),
    )

    assert preflight["ready"] is False
    assert preflight["dependencies"]["ready"] is False
    assert "oasis" in preflight["dependencies"]["missing_import"]
    assert "oasis" in preflight["dependencies"]["oasis_import_error"]
