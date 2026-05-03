"""Coordinator runtime update-state helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])


def begin_update_cycle(coordinator: ThesslaGreenModbusCoordinator) -> dict[str, Any] | None:
    """Prepare runtime state for an update cycle or return cached data when already running."""
    if coordinator._update_in_progress:
        _LOGGER.debug("Data update already running; skipping duplicate task")
        return coordinator.data or {}

    coordinator._update_in_progress = True
    coordinator._failed_registers = set()
    return None


def finish_update_cycle(coordinator: ThesslaGreenModbusCoordinator) -> None:
    """Reset runtime update flag after a cycle completes or fails."""
    coordinator._update_in_progress = False
