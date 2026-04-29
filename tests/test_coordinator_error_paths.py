"""Coordinator error-path coverage tests split from test_coordinator_coverage.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
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
async def test_test_connection_modbus_io_cancelled_skips():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(side_effect=ModbusIOException("request cancelled"))
    coord._transport = transport
    await coord._test_connection()


@pytest.mark.asyncio
async def test_test_connection_timeout_raises():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock(side_effect=TimeoutError("timed out"))
    with pytest.raises(TimeoutError):
        await coord._test_connection()


@pytest.mark.asyncio
async def test_test_connection_oserror_raises():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock(side_effect=OSError("conn refused"))
    with pytest.raises(OSError):
        await coord._test_connection()


@pytest.mark.asyncio
async def test_test_connection_modbus_io_non_cancelled_raises():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(side_effect=ModbusIOException("register error"))
    coord._transport = transport
    with pytest.raises(ModbusIOException):
        await coord._test_connection()


@pytest.mark.asyncio
async def test_test_connection_transport_none_raises():
    coord = _make_coordinator()
    coord._transport = None
    coord._ensure_connection = AsyncMock()
    with pytest.raises(ConnectionException):
        await coord._test_connection()


@pytest.mark.asyncio
async def test_test_connection_response_none_raises():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(return_value=None)
    coord._transport = transport
    with pytest.raises(ConnectionException):
        await coord._test_connection()


@pytest.mark.asyncio
async def test_test_connection_modbus_exception_raises():
    coord = _make_coordinator()
    coord._ensure_connection = AsyncMock()
    transport = MagicMock()
    transport.is_connected.return_value = True
    transport.read_input_registers = AsyncMock(side_effect=ModbusException("modbus error"))
    coord._transport = transport
    with pytest.raises(ModbusException):
        await coord._test_connection()
