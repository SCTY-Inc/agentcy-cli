"""
Core task manager.

Pi-style applications keep long-running work observable and persistent.
This task manager stores task state on disk so graph builds, preparation
jobs, and report generation can survive process restarts.
"""

import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from ..config import Config


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Persistent task record."""

    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    progress_detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        status = data.get("status", TaskStatus.PENDING)
        if isinstance(status, str):
            status = TaskStatus(status)

        return cls(
            task_id=data["task_id"],
            task_type=data.get("task_type", "task"),
            status=status,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            progress=data.get("progress", 0),
            message=data.get("message", ""),
            result=data.get("result"),
            error=data.get("error"),
            metadata=data.get("metadata", {}) or {},
            progress_detail=data.get("progress_detail", {}) or {},
        )


class TaskManager:
    """Thread-safe persistent task status manager."""

    STORAGE_DIR = os.path.join(Config.UPLOAD_FOLDER, "tasks")

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks = {}
                    cls._instance._task_lock = threading.Lock()
                    cls._instance._ensure_storage_dir()
        return cls._instance

    def _ensure_storage_dir(self):
        os.makedirs(self.STORAGE_DIR, exist_ok=True)

    def _task_path(self, task_id: str) -> str:
        return os.path.join(self.STORAGE_DIR, f"{task_id}.json")

    def _persist_task(self, task: Task):
        self._ensure_storage_dir()
        path = self._task_path(task.task_id)
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)

    def _load_task_from_disk(self, task_id: str) -> Optional[Task]:
        path = self._task_path(task_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Task.from_dict(data)

    def create_task(self, task_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        task_id = str(uuid.uuid4())
        now = datetime.now()
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        with self._task_lock:
            self._tasks[task_id] = task
            self._persist_task(task)
        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task is not None:
                return task

            task = self._load_task_from_disk(task_id)
            if task is not None:
                self._tasks[task_id] = task
            return task

    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict[str, Any]] = None,
    ):
        with self._task_lock:
            task = self._tasks.get(task_id) or self._load_task_from_disk(task_id)
            if task is None:
                return

            task.updated_at = datetime.now()
            if status is not None:
                task.status = status
            if progress is not None:
                task.progress = progress
            if message is not None:
                task.message = message
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error
            if progress_detail is not None:
                task.progress_detail = progress_detail

            self._tasks[task_id] = task
            self._persist_task(task)

    def complete_task(self, task_id: str, result: Dict[str, Any]):
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message="Task completed",
            result=result,
        )

    def fail_task(self, task_id: str, error: str):
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message="Task failed",
            error=error,
        )

    def list_tasks(self, task_type: Optional[str] = None) -> List[Task]:
        self._ensure_storage_dir()
        tasks: List[Task] = []
        seen = set()

        with self._task_lock:
            for task in self._tasks.values():
                if task_type is None or task.task_type == task_type:
                    tasks.append(task)
                seen.add(task.task_id)

            for filename in os.listdir(self.STORAGE_DIR):
                if not filename.endswith(".json"):
                    continue
                task_id = filename[:-5]
                if task_id in seen:
                    continue
                task = self._load_task_from_disk(task_id)
                if task is None:
                    continue
                self._tasks[task_id] = task
                if task_type is None or task.task_type == task_type:
                    tasks.append(task)

        tasks.sort(key=lambda x: x.created_at, reverse=True)
        return tasks

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        with self._task_lock:
            old_ids = [
                tid
                for tid, task in self._tasks.items()
                if task.created_at < cutoff and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            ]
            for task_id in old_ids:
                self._tasks.pop(task_id, None)
                path = self._task_path(task_id)
                if os.path.exists(path):
                    os.remove(path)

            for filename in os.listdir(self.STORAGE_DIR):
                if not filename.endswith(".json"):
                    continue
                task_id = filename[:-5]
                if task_id in self._tasks:
                    continue
                task = self._load_task_from_disk(task_id)
                if task and task.created_at < cutoff and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    os.remove(self._task_path(task_id))
