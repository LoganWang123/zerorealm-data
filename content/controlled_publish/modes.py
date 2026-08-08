"""Execution modes and global publish kill switch."""

from __future__ import annotations

import os
from enum import Enum


class ExecutionMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


DEFAULT_EXECUTION_MODE = ExecutionMode.DRY_RUN


def publish_disabled(env: dict[str, str] | None = None) -> bool:
    """Global kill switch. Default TRUE — real side effects always blocked unless explicitly enabled."""
    source = env if env is not None else os.environ
    raw = str(source.get("PUBLISH_DISABLED", "true")).strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def resolve_execution_mode(value: str | ExecutionMode | None) -> ExecutionMode:
    if value is None or value == "":
        return DEFAULT_EXECUTION_MODE
    if isinstance(value, ExecutionMode):
        return value
    key = str(value).strip().upper().replace("-", "_")
    try:
        return ExecutionMode(key)
    except ValueError as exc:
        raise ValueError(f"Unknown execution mode: {value}") from exc
