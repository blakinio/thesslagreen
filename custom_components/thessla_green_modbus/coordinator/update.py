"""Coordinator update-cycle helpers extracted from coordinator.py."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import UpdateFailed
from pymodbus.exceptions import ConnectionException, ModbusException

from ..utils import utcnow as _utcnow
from .errors import handle_update_error
from .update_result import apply_success_result
from .update_state import begin_update_cycle, finish_update_cycle

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])


async def run_update_cycle(
    coordinator: ThesslaGreenModbusCoordinator,
    start_time: datetime,
) -> dict[str, Any]:
    """Run a single successful update read cycle and update statistics."""
    await coordinator._ensure_connection()
    transport = coordinator.device_client._transport
    if transport is not None and not transport.is_connected():
        raise ConnectionException("Modbus transport is not connected")
    if transport is None and coordinator.device_client.client is None:
        raise ConnectionException("Modbus client is not connected")

    data = await coordinator.device_client._read_all_register_data()

    if transport is not None and not transport.is_connected():
        _LOGGER.debug("Modbus client disconnected during update; attempting reconnection")
        await coordinator._ensure_connection()
        transport = coordinator.device_client._transport
        if transport is None or not transport.is_connected():
            raise ConnectionException("Modbus transport is not connected")

    return apply_success_result(coordinator, start_time=start_time, data=data)


async def async_update_data(coordinator: ThesslaGreenModbusCoordinator) -> dict[str, Any]:
    """Fetch data from device and handle failures consistently."""
    start_time = _utcnow()

    if getattr(coordinator, "_shutting_down", False):
        _LOGGER.debug("Skipping update cycle: coordinator is shutting down")
        return coordinator.data or {}

    prepared_data = begin_update_cycle(coordinator)
    if prepared_data is not None:
        return prepared_data

    async with coordinator.device_client._write_lock:
        try:
            return await run_update_cycle(coordinator, start_time)

        except asyncio.CancelledError:
            # Don't count cancellation as a failure, but close the transport
            # to avoid leaving it in an inconsistent state mid-read.
            with contextlib.suppress(Exception):
                await coordinator._disconnect()
            if getattr(coordinator, "_shutting_down", False):
                _LOGGER.debug("Update cycle cancelled during coordinator shutdown")
            raise
        except (ModbusException, ConnectionException) as exc:
            if getattr(coordinator, "_shutting_down", False):
                _LOGGER.debug("Connection error during shutdown (expected): %s", exc)
                raise UpdateFailed(str(exc)) from exc
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
            finish_update_cycle(coordinator)
