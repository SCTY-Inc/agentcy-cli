"""Persistent workbench session registry."""

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import Config


@dataclass
class WorkbenchSessionState:
    """Persistent session metadata tying project, graph, simulation, and report together."""

    session_id: str
    created_at: str
    updated_at: str
    project_id: Optional[str] = None
    graph_id: Optional[str] = None
    simulation_id: Optional[str] = None
    report_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_id": self.simulation_id,
            "report_id": self.report_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkbenchSessionState":
        return cls(
            session_id=data["session_id"],
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            project_id=data.get("project_id"),
            graph_id=data.get("graph_id"),
            simulation_id=data.get("simulation_id"),
            report_id=data.get("report_id"),
            metadata=data.get("metadata", {}) or {},
        )


class SessionManager:
    """Stores and retrieves workbench sessions from disk."""

    STORAGE_DIR = os.path.join(Config.UPLOAD_FOLDER, "workbench_sessions")

    def __init__(self):
        os.makedirs(self.STORAGE_DIR, exist_ok=True)

    def _session_path(self, session_id: str) -> str:
        return os.path.join(self.STORAGE_DIR, f"{session_id}.json")

    def save(self, state: WorkbenchSessionState) -> WorkbenchSessionState:
        state.updated_at = datetime.now().isoformat()
        path = self._session_path(state.session_id)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return state

    def create(
        self,
        project_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        simulation_id: Optional[str] = None,
        report_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkbenchSessionState:
        now = datetime.now().isoformat()
        state = WorkbenchSessionState(
            session_id=f"wb_{uuid.uuid4().hex[:12]}",
            created_at=now,
            updated_at=now,
            project_id=project_id,
            graph_id=graph_id,
            simulation_id=simulation_id,
            report_id=report_id,
            metadata=metadata or {},
        )
        return self.save(state)

    def get(self, session_id: str) -> Optional[WorkbenchSessionState]:
        path = self._session_path(session_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return WorkbenchSessionState.from_dict(json.load(f))

    def list(self) -> List[WorkbenchSessionState]:
        states: List[WorkbenchSessionState] = []
        if not os.path.exists(self.STORAGE_DIR):
            return states
        for filename in os.listdir(self.STORAGE_DIR):
            if not filename.endswith(".json"):
                continue
            state = self.get(filename[:-5])
            if state:
                states.append(state)
        states.sort(key=lambda s: s.updated_at, reverse=True)
        return states

    def find_latest(
        self,
        project_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        simulation_id: Optional[str] = None,
        report_id: Optional[str] = None,
    ) -> Optional[WorkbenchSessionState]:
        for state in self.list():
            if project_id and state.project_id == project_id:
                return state
            if graph_id and state.graph_id == graph_id:
                return state
            if simulation_id and state.simulation_id == simulation_id:
                return state
            if report_id and state.report_id == report_id:
                return state
        return None

    def get_or_create(
        self,
        project_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        simulation_id: Optional[str] = None,
        report_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkbenchSessionState:
        existing = self.find_latest(
            project_id=project_id,
            graph_id=graph_id,
            simulation_id=simulation_id,
            report_id=report_id,
        )
        if existing:
            changed = False
            if project_id and existing.project_id != project_id:
                existing.project_id = project_id
                changed = True
            if graph_id and existing.graph_id != graph_id:
                existing.graph_id = graph_id
                changed = True
            if simulation_id and existing.simulation_id != simulation_id:
                existing.simulation_id = simulation_id
                changed = True
            if report_id and existing.report_id != report_id:
                existing.report_id = report_id
                changed = True
            if metadata:
                existing.metadata.update(metadata)
                changed = True
            return self.save(existing) if changed else existing
        return self.create(
            project_id=project_id,
            graph_id=graph_id,
            simulation_id=simulation_id,
            report_id=report_id,
            metadata=metadata,
        )

    def attach(
        self,
        session_id: str,
        project_id: Optional[str] = None,
        graph_id: Optional[str] = None,
        simulation_id: Optional[str] = None,
        report_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[WorkbenchSessionState]:
        state = self.get(session_id)
        if state is None:
            return None
        if project_id is not None:
            state.project_id = project_id
        if graph_id is not None:
            state.graph_id = graph_id
        if simulation_id is not None:
            state.simulation_id = simulation_id
        if report_id is not None:
            state.report_id = report_id
        if metadata:
            state.metadata.update(metadata)
        return self.save(state)
