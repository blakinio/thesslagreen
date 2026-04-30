"""Update-cycle result shaping helpers for coordinator refreshes."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..utils import utcnow as _utcnow

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])


def apply_success_result(
    coordinator: ThesslaGreenModbusCoordinator,
    *,
    start_time: datetime,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Apply successful update-cycle side effects and return payload."""
    coordinator.statistics["successful_reads"] += 1
    coordinator.statistics["last_successful_update"] = _utcnow()
    coordinator._consecutive_failures = 0
    coordinator.offline_state = False

    response_time = (_utcnow() - start_time).total_seconds()
    coordinator.statistics["average_response_time"] = (
        coordinator.statistics["average_response_time"]
        * (coordinator.statistics["successful_reads"] - 1)
        + response_time
    ) / coordinator.statistics["successful_reads"]

    _LOGGER.debug("Data update successful: %d values read in %.2fs", len(data), response_time)
    return data
