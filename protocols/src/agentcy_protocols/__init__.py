"""agentcy-protocols — shared schemas and adapters for the agentcy suite."""

from pathlib import Path

# Root of the protocols package (for resolving schema paths)
_ROOT = Path(__file__).parent.parent.parent

SCHEMAS = {
    "brief.v1": _ROOT / "brief.v1.schema.json",
    "forecast.v1": _ROOT / "forecast.v1.schema.json",
    "run_result.v1": _ROOT / "run_result.v1.schema.json",
    "performance.v1": _ROOT / "performance.v1.schema.json",
    "voice_pack.v1": _ROOT / "voice_pack.v1.schema.json",
}

EXAMPLES = {
    name: _ROOT / "examples" / f"{name}.json"
    for name in SCHEMAS
}

from .adapters import adapt_run_result_to_performance  # noqa: E402
from .llm import LLMError, LLMProvider  # noqa: E402
from .utils import load_json, load_json_optional, write_json  # noqa: E402
from .output import configure as configure_output, emit, emit_error, is_json, is_envelope  # noqa: E402

__all__ = [
    "SCHEMAS",
    "EXAMPLES",
    "adapt_run_result_to_performance",
    "LLMError",
    "LLMProvider",
    "load_json",
    "load_json_optional",
    "write_json",
    "configure_output",
    "emit",
    "emit_error",
    "is_json",
    "is_envelope",
]
