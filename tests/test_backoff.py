from unittest.mock import AsyncMock, patch

import pytest

from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ModbusIOException,
)

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "func, expected",
    [
        (ThesslaGreenDeviceScanner._read_input, [0.1, 0.2]),
        (ThesslaGreenDeviceScanner._read_holding, [0.1, 0.2]),
        (ThesslaGreenDeviceScanner._read_coil, [0.1, 0.2]),
        (ThesslaGreenDeviceScanner._read_discrete, [0.1, 0.2]),
    ],
)
async def test_backoff_delay(func, expected):
    scanner = await ThesslaGreenDeviceScanner.create("host", 1234, 10, retry=3, backoff=0.1)
    mock_client = AsyncMock()
    sleep_mock = AsyncMock()
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ),
        patch("asyncio.sleep", sleep_mock),
    ):
        result = await func(scanner, mock_client, 0x0001, 1)
        assert result is None  # nosec
    assert [call.args[0] for call in sleep_mock.await_args_list] == expected  # nosec


@pytest.mark.parametrize(
    "func, expected",
    [
        (ThesslaGreenDeviceScanner._read_input, [0, 0]),
        (ThesslaGreenDeviceScanner._read_holding, [0, 0]),
        (ThesslaGreenDeviceScanner._read_coil, [0, 0]),
        (ThesslaGreenDeviceScanner._read_discrete, [0, 0]),
    ],
)
async def test_backoff_zero_no_delay(func, expected):
    scanner = await ThesslaGreenDeviceScanner.create("host", 1234, 10, retry=3, backoff=0)
    mock_client = AsyncMock()
    sleep_mock = AsyncMock()
    with (
        patch(
            "custom_components.thessla_green_modbus.scanner_core._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ),
        patch("asyncio.sleep", sleep_mock),
    ):
        result = await func(scanner, mock_client, 0x0001, 1)
        assert result is None  # nosec
    assert [call.args[0] for call in sleep_mock.await_args_list] == expected  # nosec
