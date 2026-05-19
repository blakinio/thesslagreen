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
    coordinator.device_client.statistics["successful_reads"] += 1
    coordinator.device_client.statistics["last_successful_update"] = _utcnow()
    coordinator.device_client._consecutive_failures = 0
    coordinator.device_client.offline_state = False

    response_time = (_utcnow() - start_time).total_seconds()
    coordinator.device_client.statistics["average_response_time"] = (
        coordinator.device_client.statistics["average_response_time"]
        * (coordinator.device_client.statistics["successful_reads"] - 1)
        + response_time
    ) / coordinator.device_client.statistics["successful_reads"]

    _LOGGER.debug("Data update successful: %d values read in %.2fs", len(data), response_time)
    return data
