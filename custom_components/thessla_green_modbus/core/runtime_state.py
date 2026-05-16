"""Runtime state helpers for coordinator register failure tracking."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def mark_registers_failed(
    coordinator: Any,
    names: Iterable[str | None],
) -> None:
    """Record registers that failed to read in current runtime state."""
    failed: set[str] = getattr(coordinator, "_failed_registers", set())
    failed.update(name for name in names if name)
    coordinator._failed_registers = failed


def clear_register_failure(
    coordinator: Any,
    name: str,
) -> None:
    """Remove register from failed list after successful read/write."""
    if hasattr(coordinator, "_failed_registers"):
        coordinator._failed_registers.discard(name)
