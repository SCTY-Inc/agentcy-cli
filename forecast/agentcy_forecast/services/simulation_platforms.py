"""Shared platform validation helpers for simulation APIs and services."""

from __future__ import annotations

from typing import Iterable, Optional


CONTENT_PLATFORMS = ("twitter", "reddit")
RUN_PLATFORMS = CONTENT_PLATFORMS + ("parallel",)


def _normalize_platform(
    value: Optional[str],
    *,
    allowed: Iterable[str],
    label: str,
    default: Optional[str] = None,
    allow_none: bool = False,
) -> Optional[str]:
    if value is None:
        if allow_none:
            return None
        if default is not None:
            return default
        raise ValueError(f"{label} is required")

    candidate = str(value).strip().lower()
    if not candidate:
        if allow_none:
            return None
        if default is not None:
            return default
        raise ValueError(f"{label} is required")

    allowed_values = tuple(allowed)
    if candidate not in allowed_values:
        allowed_text = "/".join(allowed_values)
        raise ValueError(f"Invalid {label}: {value}. Expected one of: {allowed_text}")

    return candidate


def normalize_content_platform(
    value: Optional[str],
    *,
    default: Optional[str] = None,
    allow_none: bool = False,
    label: str = "platform",
) -> Optional[str]:
    return _normalize_platform(
        value,
        allowed=CONTENT_PLATFORMS,
        label=label,
        default=default,
        allow_none=allow_none,
    )


def normalize_run_platform(value: Optional[str], *, default: str = "parallel") -> str:
    return _normalize_platform(
        value,
        allowed=RUN_PLATFORMS,
        label="platform",
        default=default,
        allow_none=False,
    )
