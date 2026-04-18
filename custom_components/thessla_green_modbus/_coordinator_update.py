"""Coordinator update-cycle helpers extracted from coordinator.py."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pymodbus.exceptions import ModbusException

from ._coordinator_io import handle_update_error
from .modbus_exceptions import ConnectionException
from .utils import utcnow as _utcnow

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__.rsplit('.', maxsplit=1)[0])


async def run_update_cycle(
    coordinator: ThesslaGreenModbusCoordinator,
    start_time: datetime,
) -> dict[str, Any]:
    """Run a single successful update read cycle and update statistics."""
    await coordinator._ensure_connection()
    transport = coordinator._transport
    if transport is not None and not transport.is_connected():
        raise ConnectionException("Modbus transport is not connected")
    if transport is None and coordinator.client is None:
        raise ConnectionException("Modbus client is not connected")

    data = await coordinator._read_all_register_data()

    if transport is not None and not transport.is_connected():
        _LOGGER.debug("Modbus client disconnected during update; attempting reconnection")
        await coordinator._ensure_connection()
        transport = coordinator._transport
        if transport is None or not transport.is_connected():
            raise ConnectionException("Modbus transport is not connected")

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


async def async_update_data(coordinator: ThesslaGreenModbusCoordinator) -> dict[str, Any]:
    """Fetch data from device and handle failures consistently."""
    start_time = _utcnow()

    if coordinator._update_in_progress:
        _LOGGER.debug("Data update already running; skipping duplicate task")
        return coordinator.data or {}

    coordinator._update_in_progress = True
    coordinator._failed_registers = set()

    async with coordinator._write_lock:
        try:
            return await run_update_cycle(coordinator, start_time)

        except asyncio.CancelledError:
            # Don't count cancellation as a failure, but close the transport
            # to avoid leaving it in an inconsistent state mid-read.
            with contextlib.suppress(Exception):
                await coordinator._disconnect()
            raise
        except (ModbusException, ConnectionException) as exc:
            raise await handle_update_error(
                coordinator,
                exc,
                reauth_reason="connection_failure",
                message="Error communicating with device",
                check_auth=True,
            ) from exc
        except TimeoutError as exc:
            raise await handle_update_error(
                coordinator,
                exc,
                reauth_reason="timeout",
                message="Timeout during data update",
                log_level=logging.WARNING,
                timeout_error=True,
            ) from exc
        except (OSError, ValueError) as exc:
            raise await handle_update_error(
                coordinator,
                exc,
                reauth_reason="connection_failure",
                message="Unexpected error",
                use_helper=False,
            ) from exc
        finally:
            coordinator._update_in_progress = False
