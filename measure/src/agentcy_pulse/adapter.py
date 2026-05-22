from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CANONICAL_RUN_RESULT_PATH = ROOT / "protocols" / "examples" / "run_result.v1.published.json"
CANONICAL_SIDECAR_PATH = (
    ROOT
    / "protocols"
    / "tests"
    / "fixtures"
    / "run_result_to_performance_v1"
    / "sidecar.rich.json"
)


def _load_family_adapter():
    module_path = ROOT / "protocols" / "adapters" / "run_result_to_performance_v1.py"
    spec = importlib.util.spec_from_file_location(
        "family_run_result_to_performance_v1",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load family adapter from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def adapt_canonical_run_result_to_performance(
    sidecar_path: Path | str = CANONICAL_SIDECAR_PATH,
    *,
    run_result_path: Path | str = CANONICAL_RUN_RESULT_PATH,
) -> dict[str, Any]:
    return _load_family_adapter().adapt_from_paths(Path(sidecar_path), Path(run_result_path))
