from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_RTU
from custom_components.thessla_green_modbus.coordinator import (
    lifecycle,
)

from tests.helpers_coordinator import make_coordinator as _make_coordinator


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
    coord.device_client.compute_register_groups = MagicMock()
    coord._test_connection = AsyncMock()
    coord._async_handle_stop = AsyncMock()

    stop_remove = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_listen_once.return_value = stop_remove

    result = await lifecycle.async_setup(coord)

    assert result is True
    coord._prepare_registers_for_setup.assert_called_once()
    coord._warn_missing_device_info.assert_called_once()
    coord.device_client.compute_register_groups.assert_called_once()
    coord._test_connection.assert_called_once()
    coord.hass.bus.async_listen_once.assert_called_once()
    assert coord._stop_listener is stop_remove


# ---------------------------------------------------------------------------
# Removed lifecycle proxies — slice-4 (2026-05-29)
# _ensure_connected, _try_direct_client_connect, _close_client_connection
# were unused coordinator proxies; confirmed absent after cleanup.
# ---------------------------------------------------------------------------


def test_coordinator_no_ensure_connected():
    """_ensure_connected was a one-line forwarder with zero callers; must be gone."""
    coord = _make_coordinator()
    assert not any(
        "_ensure_connected" in cls.__dict__
        for cls in type(coord).__mro__
        if cls.__name__ == "ThesslaGreenModbusCoordinator"
    ), "_ensure_connected still defined on ThesslaGreenModbusCoordinator"
    # DeviceClient uses async_ensure_connected (public name); _ensure_connection proxies it.
    assert callable(coord.device_client.async_ensure_connected)


def test_coordinator_no_try_direct_client_connect():
    """_try_direct_client_connect had zero coordinator-level callers; must be gone."""
    coord = _make_coordinator()
    assert not any(
        "_try_direct_client_connect" in cls.__dict__
        for cls in type(coord).__mro__
        if cls.__name__ == "ThesslaGreenModbusCoordinator"
    ), "_try_direct_client_connect still defined on ThesslaGreenModbusCoordinator"
    # DeviceClient still owns the implementation.
    assert callable(coord.device_client._try_direct_client_connect)


def test_coordinator_no_close_client_connection():
    """_close_client_connection had zero coordinator-level callers; must be gone."""
    coord = _make_coordinator()
    assert not any(
        "_close_client_connection" in cls.__dict__
        for cls in type(coord).__mro__
        if cls.__name__ == "ThesslaGreenModbusCoordinator"
    ), "_close_client_connection still defined on ThesslaGreenModbusCoordinator"
    # DeviceClient still owns the implementation.
    assert callable(coord.device_client._close_client_connection)
