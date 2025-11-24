"""Tests for cancellation handling in register read helpers."""

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException
from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "method",
    ["_read_input", "_read_holding", "_read_coil", "_read_discrete"],
)
async def test_read_cancellation_during_sleep(method, caplog):
    """Cancellation during retry sleep propagates without error logging."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ),
        patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)),
        caplog.at_level(logging.DEBUG),
    ):
        func = getattr(scanner, method)
        with pytest.raises(asyncio.CancelledError):
            await func(mock_client, 0x0001, 1)

    assert not any(record.levelno >= logging.ERROR for record in caplog.records)
