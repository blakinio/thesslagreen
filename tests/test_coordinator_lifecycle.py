from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
    lifecycle,
)


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_disconnect_acquires_lock():
    coord = _make_coordinator()
    coord._disconnect_locked = AsyncMock()
    await coord._disconnect()
    coord._disconnect_locked.assert_called_once()


@pytest.mark.asyncio
async def test_async_shutdown_calls_disconnect():
    coord = _make_coordinator()
    coord._disconnect = AsyncMock()
    stop_listener_mock = MagicMock()
    coord._stop_listener = stop_listener_mock

    await coord.async_shutdown()

    stop_listener_mock.assert_called_once()
    assert coord._stop_listener is None
    coord._disconnect.assert_called_once()


def test_resolve_setup_endpoint_rtu_uses_serial_fallback():
    coord = _make_coordinator(connection_type=CONNECTION_TYPE_RTU, serial_port="")

    assert lifecycle.resolve_setup_endpoint(coord) == "serial"


@pytest.mark.asyncio
async def test_async_setup_orchestration_registers_stop_listener_once():
    coord = _make_coordinator()
    coord._prepare_registers_for_setup = AsyncMock()
    coord._warn_missing_device_info = MagicMock()
    coord._compute_register_groups = MagicMock()
    coord._test_connection = AsyncMock()
    coord._async_handle_stop = AsyncMock()

    stop_remove = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_listen_once.return_value = stop_remove

    result = await lifecycle.async_setup(coord)

    assert result is True
    coord._prepare_registers_for_setup.assert_called_once()
    coord._warn_missing_device_info.assert_called_once()
    coord._compute_register_groups.assert_called_once()
    coord._test_connection.assert_called_once()
    coord.hass.bus.async_listen_once.assert_called_once()
    assert coord._stop_listener is stop_remove
