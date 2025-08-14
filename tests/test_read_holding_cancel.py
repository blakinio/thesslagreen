"""Tests for cancellation handling in _read_holding."""

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.thessla_green_modbus.device_scanner import (
    ThesslaGreenDeviceScanner,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ModbusIOException,
)

pytestmark = pytest.mark.asyncio


async def test_read_holding_cancellation_during_sleep(caplog):
    """Cancellation during retry sleep propagates without error logging."""
    scanner = await ThesslaGreenDeviceScanner.create("192.168.3.17", 8899, 10)
    mock_client = AsyncMock()

    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ),
        patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)),
        caplog.at_level(logging.DEBUG),
    ):
        with pytest.raises(asyncio.CancelledError):
            await scanner._read_holding(mock_client, 0x0001, 1)

    assert not any(record.levelno >= logging.ERROR for record in caplog.records)

