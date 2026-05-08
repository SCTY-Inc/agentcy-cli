from __future__ import annotations

from pathlib import Path
from typing import Any

from agentcy.protocols.adapters.run_result_to_performance_v1 import adapt_from_paths

_PKG = Path(__file__).resolve().parent
_PROTOCOLS = _PKG.parent / "protocols"
CANONICAL_RUN_RESULT_PATH = _PROTOCOLS / "examples" / "run_result.v1.published.json"
CANONICAL_SIDECAR_PATH = (
    _PROTOCOLS / "tests" / "fixtures" / "run_result_to_performance_v1" / "sidecar.rich.json"
)


def adapt_canonical_run_result_to_performance(
    sidecar_path: Path | str = CANONICAL_SIDECAR_PATH,
    *,
    run_result_path: Path | str = CANONICAL_RUN_RESULT_PATH,
) -> dict[str, Any]:
    return adapt_from_paths(Path(sidecar_path), Path(run_result_path))
