"""Tests for quiet coordinator shutdown/unload during in-flight reads."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymodbus.exceptions import ConnectionException

from tests.helpers_coordinator import make_coordinator as _make_coordinator


async def test_shutdown_flag_initialized_false():
    """_shutting_down is False after coordinator creation."""
    coord = _make_coordinator()
    assert coord._shutting_down is False


async def test_shutdown_flag_set_by_async_shutdown():
    """async_shutdown() sets _shutting_down=True before disconnecting."""
    coord = _make_coordinator()
    coord._disconnect = AsyncMock()
    assert coord._shutting_down is False
    await coord.async_shutdown()
    assert coord._shutting_down is True


async def test_update_returns_current_data_when_shutting_down():
    """async_update_data returns existing data silently when _shutting_down=True."""
    from custom_components.thessla_green_modbus.coordinator.update import async_update_data

    coord = _make_coordinator()
    coord._shutting_down = True
    coord.data = {"sensor": 42}

    result = await async_update_data(coord)
    assert result == {"sensor": 42}


async def test_update_no_error_log_when_shutting_down(caplog):
    """No ERROR is logged when update is skipped due to shutdown."""
    from custom_components.thessla_green_modbus.coordinator.update import async_update_data

    coord = _make_coordinator()
    coord._shutting_down = True
    coord.data = {}

    with caplog.at_level(logging.DEBUG):
        await async_update_data(coord)

    assert not any(r.levelno >= logging.ERROR for r in caplog.records)


async def test_connection_error_during_shutdown_raises_update_failed_not_error(caplog):
    """ConnectionException raised after shutdown flag is set logs at DEBUG, not ERROR."""
    from custom_components.thessla_green_modbus.coordinator.update import async_update_data

    coord = _make_coordinator()
    coord._shutting_down = False  # not yet shutting down when cycle starts
    coord.device_client._update_in_progress = False
    coord.device_client._failed_registers = set()

    async def _shutdown_then_raise(coordinator, start_time):
        coordinator._shutting_down = True  # simulates shutdown happening mid-cycle
        raise ConnectionException("Modbus client is not connected")

    with (
        patch(
            "custom_components.thessla_green_modbus.coordinator.update.run_update_cycle",
            new=_shutdown_then_raise,
        ),
        caplog.at_level(logging.DEBUG),
    ):
        with pytest.raises(UpdateFailed):
            await async_update_data(coord)

    assert not any(r.levelno >= logging.ERROR for r in caplog.records)
    assert any("shutdown" in r.message.lower() for r in caplog.records)


async def test_cancelled_error_during_shutdown_no_error_log(caplog):
    """CancelledError raised after shutdown flag is set does not produce ERROR logs."""
    from custom_components.thessla_green_modbus.coordinator.update import async_update_data

    coord = _make_coordinator()
    coord._shutting_down = False  # not yet shutting down when cycle starts
    coord.device_client._update_in_progress = False
    coord.device_client._failed_registers = set()
    coord._disconnect = AsyncMock()

    async def _shutdown_then_cancel(coordinator, start_time):
        coordinator._shutting_down = True  # simulates shutdown happening mid-cycle
        raise asyncio.CancelledError

    with (
        patch(
            "custom_components.thessla_green_modbus.coordinator.update.run_update_cycle",
            new=_shutdown_then_cancel,
        ),
        caplog.at_level(logging.DEBUG),
    ):
        with pytest.raises(asyncio.CancelledError):
            await async_update_data(coord)

    assert not any(r.levelno >= logging.ERROR for r in caplog.records)


async def test_runtime_connection_failure_calls_handle_update_error():
    """Normal (non-shutdown) ConnectionException is routed through handle_update_error."""
    from custom_components.thessla_green_modbus.coordinator.update import async_update_data

    coord = _make_coordinator()
    coord._shutting_down = False
    coord.device_client._update_in_progress = False
    coord.device_client._failed_registers = set()

    mock_handle = AsyncMock(return_value=UpdateFailed("Error communicating with device: x"))

    with (
        patch(
            "custom_components.thessla_green_modbus.coordinator.update.run_update_cycle",
            AsyncMock(side_effect=ConnectionException("connection refused")),
        ),
        patch(
            "custom_components.thessla_green_modbus.coordinator.update.handle_update_error",
            mock_handle,
        ),
    ):
        with pytest.raises(UpdateFailed):
            await async_update_data(coord)

    mock_handle.assert_called_once()


async def test_shutdown_during_in_flight_read_no_error_logged(caplog):
    """Coordinator shutdown flag set while read is in progress suppresses ERROR log."""
    from custom_components.thessla_green_modbus.coordinator.update import async_update_data

    coord = _make_coordinator()
    coord.device_client._update_in_progress = False
    coord.device_client._failed_registers = set()

    read_started = asyncio.Event()
    shutdown_triggered = asyncio.Event()

    async def slow_update(coordinator, start_time):
        read_started.set()
        await shutdown_triggered.wait()
        raise ConnectionException("Modbus client is not connected")

    with (
        patch(
            "custom_components.thessla_green_modbus.coordinator.update.run_update_cycle",
            new=slow_update,
        ),
        caplog.at_level(logging.DEBUG),
    ):
        task = asyncio.create_task(async_update_data(coord))
        await read_started.wait()

        coord._shutting_down = True
        shutdown_triggered.set()

        with pytest.raises(UpdateFailed):
            await task

    assert not any(r.levelno >= logging.ERROR for r in caplog.records)
