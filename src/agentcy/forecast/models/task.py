"""
Compatibility shim for task state.

The persistent implementation now lives in app.core.task_manager so task
state follows the workbench/session architecture instead of staying as a
pure in-memory model concern.
"""

from ..core.task_manager import Task, TaskManager, TaskStatus

__all__ = ["Task", "TaskManager", "TaskStatus"]
