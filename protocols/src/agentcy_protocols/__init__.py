"""agentcy-protocols — shared schemas and adapters for the agentcy suite."""

from pathlib import Path

_PACKAGE_ROOT = Path(__file__).parent
_SOURCE_ROOT = _PACKAGE_ROOT.parent.parent


def _protocol_file(name: str) -> Path:
    packaged = _PACKAGE_ROOT / "schemas" / name
    if packaged.exists():
        return packaged
    return _SOURCE_ROOT / name


def _example_file(name: str) -> Path:
    packaged = _PACKAGE_ROOT / "examples" / name
    if packaged.exists():
        return packaged
    return _SOURCE_ROOT / "examples" / name

SCHEMAS = {
    "brief.v1": _protocol_file("brief.v1.schema.json"),
    "forecast.v1": _protocol_file("forecast.v1.schema.json"),
    "run_result.v1": _protocol_file("run_result.v1.schema.json"),
    "performance.v1": _protocol_file("performance.v1.schema.json"),
    "voice_pack.v1": _protocol_file("voice_pack.v1.schema.json"),
}

EXAMPLES = {
    name: _example_file(f"{name}.json")
    for name in SCHEMAS
}

from .adapters import adapt_run_result_to_performance  # noqa: E402
from .llm import LLMError, LLMProvider  # noqa: E402
from .output import configure as configure_output  # noqa: E402
from .output import emit, emit_error, is_envelope, is_json  # noqa: E402
from .utils import load_json, load_json_optional, utc_now, utc_now_iso, write_json  # noqa: E402

__all__ = [
    "SCHEMAS",
    "EXAMPLES",
    "adapt_run_result_to_performance",
    "LLMError",
    "LLMProvider",
    "load_json",
    "load_json_optional",
    "write_json",
    "utc_now",
    "utc_now_iso",
    "configure_output",
    "emit",
    "emit_error",
    "is_envelope",
    "is_json",
]
