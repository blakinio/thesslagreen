"""Targeted coverage tests for coordinator.py uncovered lines."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Group A — _utcnow behavior
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Group C — _get_client_method fallback no-op (lines 509-527)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio

async def test_test_connection_modbus_io_cancelled_skips():
    """ModbusIOException with 'cancelled' message is swallowed (lines 1125-1130)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(side_effect=ModbusIOException("request cancelled"))
    coord._transport = transport

    # Should not raise
    await coord._test_connection()

async def test_test_connection_timeout_raises():
    """TimeoutError in _test_connection is re-raised (lines 1136-1138)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock(side_effect=TimeoutError("timed out"))

    with pytest.raises(TimeoutError):
        await coord._test_connection()

async def test_test_connection_oserror_raises():
    """OSError in _test_connection is re-raised (lines 1139-1141)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock(side_effect=OSError("conn refused"))

    with pytest.raises(OSError):
        await coord._test_connection()

async def test_test_connection_modbus_io_non_cancelled_raises():
    """Non-cancelled ModbusIOException is re-raised (lines 1131-1132)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(side_effect=ModbusIOException("register error"))
    coord._transport = transport

    with pytest.raises(ModbusIOException):
        await coord._test_connection()

async def test_test_connection_transport_none_raises():
    """ConnectionException when transport is None after _ensure_connection (line 1095)."""
    coord = _make_coordinator()
    coord._transport = None
    coord._ensure_connection = AsyncMock()  # does nothing, transport stays None

    with pytest.raises(ConnectionException):
        await coord._test_connection()

async def test_test_connection_response_none_raises():
    """ConnectionException when read_input_registers returns None (lines 1105-1106)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(return_value=None)
    coord._transport = transport

    with pytest.raises(ConnectionException):
        await coord._test_connection()

async def test_test_connection_successful():
    """Full successful connection test (lines 1110-1124)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    ok_response = MagicMock()
    ok_response.isError.return_value = False
    ok_response.registers = [100]

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(return_value=ok_response)
    coord._transport = transport

    # Should complete without exception
    await coord._test_connection()

async def test_test_connection_modbus_exception_raises():
    """ModbusException in _test_connection is re-raised (lines 1133-1135)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()

    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(side_effect=ModbusException("modbus error"))
    coord._transport = transport

    with pytest.raises(ModbusException):
        await coord._test_connection()

async def test_async_write_register_modbus_exception_retry():
    """ModbusException during write → disconnect, retry, return False."""
    coord = _make_coordinator()
    coord.retry = 2
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_register = AsyncMock(side_effect=ModbusException("write failed"))
    coord._transport = transport
    coord._disconnect = AsyncMock()

    result = await coord.async_write_register("mode", 1)
    assert result is False
    coord._disconnect.assert_called()

async def test_async_write_register_error_response_retries():
    """Error response on non-last attempt → continues, then fails."""
    coord = _make_coordinator()
    coord.retry = 2
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    error_response = MagicMock()
    error_response.isError.return_value = True
    transport.write_register = AsyncMock(return_value=error_response)
    coord._transport = transport

    result = await coord.async_write_register("mode", 1)
    assert result is False
    assert transport.write_register.call_count == 2  # retried once

async def test_test_connection_transport_not_connected():
    """transport.is_connected() False raises ConnectionException (line 1111)."""
    coord = _make_coordinator()
    transport = MagicMock()
    # All reads succeed but then is_connected() returns False
    transport.read_input_registers = AsyncMock(return_value=MagicMock())
    transport.is_connected.return_value = False
    coord._transport = transport
    coord._ensure_connection = AsyncMock()
    with pytest.raises(ConnectionException):
        await coord._test_connection()

async def test_test_connection_basic_register_response_none():
    """Final read_input_registers returns None raises ConnectionException (line 1122)."""
    coord = _make_coordinator()
    transport = MagicMock()
    # Loop reads return MagicMock, then final read returns None
    transport.read_input_registers = AsyncMock(
        side_effect=[MagicMock(), MagicMock(), MagicMock(), None]
    )
    transport.is_connected.return_value = True
    coord._transport = transport
    coord._ensure_connection = AsyncMock()
    with pytest.raises(ConnectionException):
        await coord._test_connection()

async def test_async_write_register_multi_reg_chunk_error_last_attempt():
    """Multi-reg chunk error on last attempt → False (lines 2068-2076)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 2
    mock_def.function = 3
    mock_def.address = 100
    err_resp = MagicMock()
    err_resp.isError.return_value = True
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_registers = AsyncMock(return_value=err_resp)
    coord._transport = transport
    coord.retry = 1
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", [1, 2])
    assert result is False

async def test_async_write_register_timeout_last_attempt():
    """TimeoutError on last attempt → False."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_register = AsyncMock(side_effect=TimeoutError("write timeout"))
    coord._transport = transport
    coord._disconnect = AsyncMock()
    coord.retry = 1
    result = await coord.async_write_register("mode", 1)
    assert result is False

async def test_async_write_register_timeout_with_retry():
    """TimeoutError then success (line 2150 continue)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport.write_register = AsyncMock(side_effect=[TimeoutError("write timeout"), ok_resp])
    coord._transport = transport
    coord._disconnect = AsyncMock()
    coord.async_request_refresh = AsyncMock()
    coord.retry = 2
    result = await coord.async_write_register("mode", 1)
    assert result is True

async def test_async_write_register_oserror():
    """OSError in write → False (lines 2151-2154)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_register = AsyncMock(side_effect=OSError("io error"))
    coord._transport = transport
    coord._disconnect = AsyncMock()
    result = await coord.async_write_register("mode", 1)
    assert result is False

async def test_async_write_registers_batch_error_last_attempt():
    """Batch error on last attempt → False (lines 2253-2258)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    err_resp = MagicMock()
    err_resp.isError.return_value = True
    client.write_registers = AsyncMock(return_value=err_resp)
    coord.client = client
    coord._disconnect = AsyncMock()
    coord.retry = 1
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False

async def test_async_write_registers_modbus_exception():
    """ModbusException → disconnect + False (lines 2270-2284)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    client.write_registers = AsyncMock(side_effect=ModbusException("write error"))
    coord.client = client
    coord._disconnect = AsyncMock()
    coord.retry = 1
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False

async def test_async_write_registers_timeout_error():
    """TimeoutError → False (lines 2285-2301)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    client.write_registers = AsyncMock(side_effect=TimeoutError("timeout"))
    coord.client = client
    coord._disconnect = AsyncMock()
    coord.retry = 1
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False

async def test_async_write_registers_oserror():
    """OSError → False (lines 2302-2305)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    client.write_registers = AsyncMock(side_effect=OSError("io error"))
    coord.client = client
    coord._disconnect = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is False

async def test_async_write_register_multi_reg_chunk_error_retry():
    """Multi-reg chunk error retried → success (lines 2075-2076)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    mock_def = MagicMock()
    mock_def.length = 2
    mock_def.function = 3
    mock_def.address = 100
    err_resp = MagicMock()
    err_resp.isError.return_value = True
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.write_registers = AsyncMock(side_effect=[err_resp, ok_resp])
    coord._transport = transport
    coord.retry = 2
    coord.async_request_refresh = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.get_register_definition",
        return_value=mock_def,
    ):
        result = await coord.async_write_register("some_reg", [1, 2])
    assert result is True

async def test_async_write_registers_modbus_exception_retry():
    """ModbusException with retry → retries (lines 2279-2284)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    client.write_registers = AsyncMock(side_effect=[ModbusException("write error"), ok_resp])
    coord.client = client
    coord._disconnect = AsyncMock()
    coord.retry = 2
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is True

async def test_async_write_registers_timeout_with_transport():
    """TimeoutError with transport disconnects (line 2287)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    transport.write_registers = AsyncMock(side_effect=[TimeoutError("timeout"), ok_resp])
    coord._transport = transport
    coord._disconnect = AsyncMock()
    coord.retry = 2
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is True

async def test_async_write_registers_timeout_continue():
    """TimeoutError continue on non-last attempt (line 2301)."""
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    coord._transport = None
    client = MagicMock()
    ok_resp = MagicMock()
    ok_resp.isError.return_value = False
    client.write_registers = AsyncMock(side_effect=[TimeoutError("timeout"), ok_resp])
    coord.client = client
    coord._disconnect = AsyncMock()
    coord.retry = 2
    coord.async_request_refresh = AsyncMock()
    result = await coord.async_write_registers(100, [1, 2])
    assert result is True
