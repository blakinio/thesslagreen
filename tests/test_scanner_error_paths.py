"""Scanner error-path and cleanup coverage tests."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.scanner.core import ThesslaGreenDeviceScanner


def _make_ok_response(registers):
    resp = MagicMock()
    resp.isError.return_value = False
    resp.registers = list(registers)
    return resp


async def _make_scanner(**kwargs):
    return await ThesslaGreenDeviceScanner.create("192.168.1.1", 502, 1, **kwargs)


def _make_transport(*, raises_on_close=None, ensure_side_effect=None, input_response=None, holding_response=None):
    t = MagicMock()
    t.close = AsyncMock(side_effect=raises_on_close) if raises_on_close else AsyncMock()
    t.ensure_connected = AsyncMock(side_effect=ensure_side_effect) if ensure_side_effect else AsyncMock()
    t.read_input_registers = AsyncMock(return_value=input_response or _make_ok_response([1]))
    t.read_holding_registers = AsyncMock(return_value=holding_response or _make_ok_response([1]))
    t.is_connected = MagicMock(return_value=True)
    return t


@pytest.mark.asyncio
async def test_close_transport_raises_oserror():
    """Lines 686-687: OSError from transport.close() is caught and logged."""
    scanner = await _make_scanner()
    scanner._transport = _make_transport(raises_on_close=OSError("boom"))
    # Should not raise
    await scanner.close()
    assert scanner._transport is None


@pytest.mark.asyncio
async def test_close_transport_raises_connection_exception():
    """Lines 686-687: ConnectionException from transport.close() is caught."""
    scanner = await _make_scanner()
    scanner._transport = _make_transport(raises_on_close=ConnectionException("err"))
    await scanner.close()
    assert scanner._transport is None


@pytest.mark.asyncio
async def test_close_client_raises_oserror():
    """Lines 697-698: OSError from client.close() is caught and logged."""
    scanner = await _make_scanner()
    scanner._transport = None
    mock_client = MagicMock()
    mock_client.close = MagicMock(side_effect=OSError("client boom"))
    scanner._client = mock_client
    await scanner.close()
    assert scanner._client is None


@pytest.mark.asyncio
async def test_close_client_raises_modbus_io_exception():
    """Lines 697-698: ModbusIOException from client.close() is caught."""
    scanner = await _make_scanner()
    scanner._transport = None
    mock_client = MagicMock()
    mock_client.close = MagicMock(side_effect=ModbusIOException("io err"))
    scanner._client = mock_client
    await scanner.close()
    assert scanner._client is None


@pytest.mark.asyncio
async def test_verify_connection_safe_holding_registers():
    """Lines 824-829: safe_holding is non-empty when date_time is in REGISTER_DEFINITIONS."""
    from custom_components.thessla_green_modbus.scanner.core import REGISTER_DEFINITIONS

    scanner = await _make_scanner()
    # date_time is a holding register in SAFE_REGISTERS
    if "date_time" not in REGISTER_DEFINITIONS:
        pytest.skip("date_time not in REGISTER_DEFINITIONS")

    fake_transport = _make_transport()
    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        await scanner.verify_connection()

    fake_transport.read_holding_registers.assert_called()


@pytest.mark.asyncio
async def test_verify_connection_cancelled_error_reraises():
    """Line 845: asyncio.CancelledError is re-raised."""
    scanner = await _make_scanner()
    fake_transport = _make_transport(ensure_side_effect=asyncio.CancelledError())
    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with pytest.raises(asyncio.CancelledError):
            await scanner.verify_connection()


@pytest.mark.asyncio
async def test_verify_connection_modbus_io_cancelled_raises_timeout():
    """Lines 847-850: ModbusIOException with 'cancelled' raises TimeoutError."""
    scanner = await _make_scanner()
    exc = ModbusIOException("Request cancelled outside pymodbus")
    fake_transport = _make_transport(ensure_side_effect=exc)
    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with pytest.raises(TimeoutError):
            await scanner.verify_connection()


@pytest.mark.asyncio
async def test_verify_connection_timeout_error_logs_warning(caplog):
    """Lines 852-853: TimeoutError logs a warning."""
    scanner = await _make_scanner()
    fake_transport = _make_transport(ensure_side_effect=TimeoutError("timed out"))

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with caplog.at_level(logging.WARNING):
            with pytest.raises(TimeoutError):
                await scanner.verify_connection()

    assert "Timeout during verify_connection" in caplog.text


@pytest.mark.asyncio
async def test_verify_connection_transport_close_exception_in_finally(caplog):
    """Lines 862-865: Exception during transport.close() in finally is logged."""
    scanner = await _make_scanner()
    fake_transport = MagicMock()
    fake_transport.ensure_connected = AsyncMock(side_effect=ConnectionException("fail"))
    fake_transport.close = MagicMock(side_effect=OSError("close fail"))

    with patch.object(scanner, "_build_tcp_transport", return_value=fake_transport):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises((ConnectionException, Exception)):
                await scanner.verify_connection()

    assert "Error closing Modbus transport during verify_connection" in caplog.text


