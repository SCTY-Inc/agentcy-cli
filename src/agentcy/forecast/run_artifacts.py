"""Persistent run manifests and artifact helpers for the agent-first CLI."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from .config import Config


def _now() -> str:
    return datetime.now().isoformat()


class RunStore:
    """File-backed storage for immutable run artifacts."""

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = os.path.abspath(root_dir or os.path.join(Config.UPLOAD_FOLDER, "runs"))
        os.makedirs(self.root_dir, exist_ok=True)

    def run_dir(self, run_id: str) -> str:
        return os.path.join(self.root_dir, run_id)

    def manifest_path(self, run_id: str) -> str:
        return os.path.join(self.run_dir(run_id), "manifest.json")

    def create(
        self,
        requirement: str,
        source_files: Iterable[str],
        project_name: str = "Unnamed Project",
        brief_path: str | None = None,
        imported_lineage: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        run_dir = self.run_dir(run_id)
        os.makedirs(run_dir, exist_ok=True)
        for rel_path in (
            "input/source_files",
            "graph",
            "simulation",
            "report",
            "visuals",
            "logs",
        ):
            os.makedirs(os.path.join(run_dir, rel_path), exist_ok=True)

        manifest = {
            "run_id": run_id,
            "status": "created",
            "project_name": project_name,
            "requirement": requirement,
            "source_files": [os.path.abspath(path) for path in source_files],
            "brief_path": os.path.abspath(brief_path) if brief_path else None,
            "imported_lineage": dict(imported_lineage or {}),
            "project_id": None,
            "graph_id": None,
            "simulation_id": None,
            "report_id": None,
            "graph_build_task_id": None,
            "prepare_task_id": None,
            "report_task_id": None,
            "task_progress": 0,
            "task_message": "",
            "artifacts": {},
            "created_at": _now(),
            "updated_at": _now(),
            "error": None,
        }
        self.save(manifest)
        return manifest

    def save(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        manifest = dict(manifest)
        manifest["updated_at"] = _now()
        path = self.manifest_path(manifest["run_id"])
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return manifest

    def load(self, run_id: str) -> Dict[str, Any]:
        path = self.manifest_path(run_id)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Run not found: {run_id}")
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def update(self, run_id: str, **changes: Any) -> Dict[str, Any]:
        manifest = self.load(run_id)
        manifest.update(changes)
        return self.save(manifest)

    def list(self, limit: int = 20) -> List[Dict[str, Any]]:
        manifests: List[Dict[str, Any]] = []
        for item in os.listdir(self.root_dir):
            path = self.manifest_path(item)
            if not os.path.exists(path):
                continue
            try:
                manifests.append(self.load(item))
            except (OSError, json.JSONDecodeError):
                continue
        manifests.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return manifests[:limit]

    def write_json(self, run_id: str, rel_path: str, payload: Any) -> str:
        output_path = os.path.join(self.run_dir(run_id), rel_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return output_path

    def write_text(self, run_id: str, rel_path: str, content: str) -> str:
        output_path = os.path.join(self.run_dir(run_id), rel_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return output_path

    def copy_file(self, run_id: str, source_path: str, rel_path: str) -> Optional[str]:
        if not os.path.exists(source_path):
            return None
        output_path = os.path.join(self.run_dir(run_id), rel_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy2(source_path, output_path)
        return output_path

    def copy_tree(self, run_id: str, source_dir: str, rel_dir: str) -> Optional[str]:
        if not os.path.exists(source_dir):
            return None
        output_dir = os.path.join(self.run_dir(run_id), rel_dir)
        os.makedirs(output_dir, exist_ok=True)
        for entry in os.listdir(source_dir):
            src = os.path.join(source_dir, entry)
            dst = os.path.join(output_dir, entry)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        return output_dir

    def freeze_source_files(self, run_id: str, source_files: Iterable[str]) -> List[str]:
        copied: List[str] = []
        for index, source_path in enumerate(source_files, start=1):
            absolute = os.path.abspath(source_path)
            if not os.path.exists(absolute):
                continue
            basename = os.path.basename(absolute)
            rel_path = os.path.join("input", "source_files", f"{index:02d}_{basename}")
            output = self.copy_file(run_id, absolute, rel_path)
            if output:
                copied.append(output)
        return copied

    def record_artifact(self, run_id: str, key: str, rel_path: str) -> Dict[str, Any]:
        manifest = self.load(run_id)
        artifacts = dict(manifest.get("artifacts", {}))
        artifacts[key] = rel_path
        manifest["artifacts"] = artifacts
        return self.save(manifest)

