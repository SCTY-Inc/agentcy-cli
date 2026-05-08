"""
Data models module with lazy exports.
"""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "TaskManager": (".task", "TaskManager"),
    "TaskStatus": (".task", "TaskStatus"),
    "Project": (".project", "Project"),
    "ProjectStatus": (".project", "ProjectStatus"),
    "ProjectManager": (".project", "ProjectManager"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
