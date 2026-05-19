"""Focused coordinator error-path tests split from test_coordinator.py."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from pymodbus.exceptions import ConnectionException


@pytest.mark.asyncio
async def test_read_holding_registers_none_client(coordinator, caplog):
    """Return empty data when no Modbus client is present."""
    coordinator.device_client.client = None
    coordinator.device_client._register_groups = {"holding_registers": [(0, 1)]}

    with caplog.at_level(logging.DEBUG):
        result = await coordinator._read_holding_registers_optimized()

    assert result == {}
    assert "Modbus client is not connected" in caplog.text


@pytest.mark.asyncio
async def test_read_holding_registers_cancelled_error(coordinator, caplog):
    """Propagate cancellation without logging noise."""
    coordinator.device_client.client = MagicMock()
    coordinator.device_client._register_groups = {"holding_registers": [(0, 1)]}
    coordinator._call_modbus = AsyncMock(side_effect=asyncio.CancelledError)

    with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
        await coordinator._read_holding_registers_optimized()
    assert caplog.text == ""


@pytest.mark.asyncio
async def test_read_input_registers_reconnect_on_error(coordinator):
    """ConnectionException propagates (fails update cycle) and disconnect is triggered."""
    coordinator.device_client.client = MagicMock()
    coordinator.device_client.client.connected = True
    coordinator.device_client._register_groups = {"input_registers": [(0, 1)]}
    coordinator._call_modbus = AsyncMock(side_effect=ConnectionException("boom"))
    coordinator._disconnect = AsyncMock()

    with pytest.raises(ConnectionException):
        await coordinator._read_input_registers_optimized()

    coordinator._disconnect.assert_called()
