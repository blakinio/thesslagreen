"""Focused coordinator error-path tests split from test_coordinator.py."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from pymodbus.exceptions import ConnectionException


@pytest.mark.asyncio
async def test_read_holding_registers_none_client(coordinator, caplog):
    """Return empty data when no Modbus client is present."""
    dc = coordinator.device_client
    dc.client = None
    dc._register_groups = {"holding_registers": [(0, 1)]}

    with caplog.at_level(logging.DEBUG):
        result = await dc._read_holding_registers_optimized()

    assert result == {}
    assert "Modbus client is not connected" in caplog.text


@pytest.mark.asyncio
async def test_read_holding_registers_cancelled_error(coordinator, caplog):
    """Propagate cancellation without logging noise."""
    dc = coordinator.device_client
    dc.client = MagicMock()
    dc._register_groups = {"holding_registers": [(0, 1)]}
    dc._call_modbus = AsyncMock(side_effect=asyncio.CancelledError)

    with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
        await dc._read_holding_registers_optimized()
    assert caplog.text == ""


@pytest.mark.asyncio
async def test_read_input_registers_reconnect_on_error(coordinator):
    """ConnectionException propagates (fails update cycle) and disconnect is triggered."""
    dc = coordinator.device_client
    dc.client = MagicMock()
    dc.client.connected = True
    dc._register_groups = {"input_registers": [(0, 1)]}
    dc._call_modbus = AsyncMock(side_effect=ConnectionException("boom"))
    dc._disconnect = AsyncMock()

    with pytest.raises(ConnectionException):
        await dc._read_input_registers_optimized()

    dc._disconnect.assert_called()
