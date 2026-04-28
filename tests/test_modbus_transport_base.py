# mypy: ignore-errors
"""Tests for base/common Modbus transport behavior."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONNECTION_TYPE_TCP
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)
from custom_components.thessla_green_modbus.modbus_transport import TcpModbusTransport


def _make_tcp(connection_type=CONNECTION_TYPE_TCP, **kwargs):
    defaults = dict(
        host="127.0.0.1",
        port=502,
        connection_type=connection_type,
        max_retries=1,
        base_backoff=0.0,
        max_backoff=0.0,
        timeout=1.0,
    )
    defaults.update(kwargs)
    return TcpModbusTransport(**defaults)


@pytest.mark.asyncio
async def test_execute_timeout_error():
    """_execute sets offline_state=True and re-raises TimeoutError."""
    t = _make_tcp()

    async def raises_timeout():
        raise TimeoutError("timeout")

    with patch.object(t, "_reset_connection", new=AsyncMock()), pytest.raises(TimeoutError):
        await t._execute(raises_timeout)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_modbus_io_exception():
    """_execute sets offline_state=True and re-raises ModbusIOException."""
    t = _make_tcp()

    async def raises_io():
        raise ModbusIOException("io error")

    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with pytest.raises(ModbusIOException):
            await t._execute(raises_io)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_connection_exception():
    """_execute sets offline_state=True and re-raises ConnectionException."""
    t = _make_tcp()

    async def raises_conn():
        raise ConnectionException("conn error")

    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with pytest.raises(ConnectionException):
            await t._execute(raises_conn)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_os_error():
    """_execute handles OSError the same as ConnectionException."""
    t = _make_tcp()

    async def raises_os():
        raise OSError("os error")

    with patch.object(t, "_reset_connection", new=AsyncMock()), pytest.raises(OSError):
        await t._execute(raises_os)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_modbus_exception():
    """_execute sets offline_state=True and re-raises ModbusException."""
    t = _make_tcp()

    async def raises_modbus():
        raise ModbusException("modbus err")

    with patch.object(t, "_reset_connection", new=AsyncMock()), pytest.raises(ModbusException):
        await t._execute(raises_modbus)

    assert t.offline_state is True


@pytest.mark.asyncio
async def test_execute_cancelled_error():
    """_execute handles CancelledError and re-raises."""
    t = _make_tcp()

    async def raises_cancelled():
        raise asyncio.CancelledError()

    with patch.object(t, "_reset_connection", new=AsyncMock()):
        with pytest.raises(asyncio.CancelledError):
            await t._execute(raises_cancelled)

    assert t.offline_state is True
