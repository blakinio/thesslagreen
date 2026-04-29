"""Split coordinator coverage tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
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
async def test_disconnect_locked_with_transport_oserror():
    """OSError on transport.close() is caught silently (lines 2376-2377)."""
    coord = _make_coordinator()
    transport = MagicMock()
    transport.close = AsyncMock(side_effect=OSError("io error"))
    coord._transport = transport

    # Should not raise
    await coord._disconnect_locked()
    assert coord.client is None


@pytest.mark.asyncio
async def test_disconnect_locked_with_client_oserror():
    """OSError on client.close() is caught silently (lines 2388-2391)."""
    coord = _make_coordinator()
    coord._transport = None
    client = MagicMock()
    client.close = AsyncMock(side_effect=OSError("io error"))
    coord.client = client

    await coord._disconnect_locked()
    assert coord.client is None


@pytest.mark.asyncio
async def test_disconnect_locked_with_client_sync_close_awaitable():
    """Sync client.close() result that is awaitable is awaited (lines 2385-2387)."""
    coord = _make_coordinator()
    coord._transport = None
    client = MagicMock()

    async def _close_coro():
        return None

    # close is not a coroutinefunction itself, but returns an awaitable
    client.close = MagicMock(return_value=_close_coro())
    coord.client = client

    await coord._disconnect_locked()
    assert coord.client is None






# ---------------------------------------------------------------------------
# Group T — status_overview / performance_stats / get_diagnostic_data (2419-2522)
# ---------------------------------------------------------------------------
















# ---------------------------------------------------------------------------
# Additional coverage: __init__ branches (lines 289-294, 371-399)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_locked_transport_modbus_exception():
    """ModbusException during transport.close() → debug log (line 2375)."""
    coord = _make_coordinator()
    transport = MagicMock()
    transport.close = AsyncMock(side_effect=ModbusException("close error"))
    coord._transport = transport
    # Should not raise
    await coord._disconnect_locked()
    transport.close.assert_awaited_once()
    assert coord._transport is transport
    assert coord.client is None


@pytest.mark.asyncio
async def test_disconnect_locked_client_connection_exception():
    """ConnectionException during client.close() → debug log (line 2389)."""
    coord = _make_coordinator()
    coord._transport = None
    client = MagicMock()
    client.close = MagicMock(side_effect=ConnectionException("close error"))
    coord.client = client
    await coord._disconnect_locked()
    assert coord.client is None


@pytest.mark.asyncio
async def test_async_write_register_transport_not_connected():
    """transport.is_connected()=False raises (line 1979)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = False
    coord._transport = transport
    result = await coord.async_write_register("mode", 1)
    assert result is False


@pytest.mark.asyncio
async def test_async_write_registers_transport_not_connected():
    """transport not connected → False (line 2196)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = False
    coord._transport = transport
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False


@pytest.mark.asyncio
async def test_async_write_registers_no_transport_no_client():
    """No transport, no client → False (line 2198)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    coord.client = None
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False


