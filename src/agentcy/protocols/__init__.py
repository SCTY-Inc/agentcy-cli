"""agentcy.protocols — shared schemas and adapters."""

from pathlib import Path

_PKG = Path(__file__).parent

SCHEMAS = {
    "brief.v1": _PKG / "schemas" / "brief.v1.schema.json",
    "forecast.v1": _PKG / "schemas" / "forecast.v1.schema.json",
    "run_result.v1": _PKG / "schemas" / "run_result.v1.schema.json",
    "performance.v1": _PKG / "schemas" / "performance.v1.schema.json",
    "voice_pack.v1": _PKG / "schemas" / "voice_pack.v1.schema.json",
}

EXAMPLES = {
    name: _PKG / "examples" / f"{name}.json"
    for name in SCHEMAS
}

from .adapters import adapt_run_result_to_performance  # noqa: E402
from .llm import LLMError, LLMProvider  # noqa: E402
from .utils import load_json, load_json_optional, parse_llm_json, write_json  # noqa: E402

__all__ = [
    "SCHEMAS",
    "EXAMPLES",
    "adapt_run_result_to_performance",
    "LLMError",
    "LLMProvider",
    "load_json",
    "load_json_optional",
    "parse_llm_json",
    "write_json",
]
