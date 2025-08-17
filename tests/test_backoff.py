from unittest.mock import AsyncMock, patch

import pytest

from custom_components.thessla_green_modbus.device_scanner import (
    ThesslaGreenDeviceScanner,
    _read_coil,
    _read_discrete,
    _read_holding,
    _read_input,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ModbusIOException,
)

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "func",
    [_read_input, _read_holding, _read_coil, _read_discrete],
)
async def test_backoff_delay(func):
    scanner = await ThesslaGreenDeviceScanner.create("host", 1234, 10, retry=3, backoff=0.1)
    mock_client = AsyncMock()
    sleep_mock = AsyncMock()
    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ),
        patch("asyncio.sleep", sleep_mock),
    ):
        result = await func(scanner, mock_client, 0x0001, 1)
        assert result is None  # nosec
    assert [call.args[0] for call in sleep_mock.await_args_list] == [0.1, 0.2]  # nosec


@pytest.mark.parametrize(
    "func",
    [_read_input, _read_holding, _read_coil, _read_discrete],
)
async def test_backoff_zero_no_delay(func):
    scanner = await ThesslaGreenDeviceScanner.create("host", 1234, 10, retry=3, backoff=0)
    mock_client = AsyncMock()
    sleep_mock = AsyncMock()
    with (
        patch(
            "custom_components.thessla_green_modbus.device_scanner._call_modbus",
            AsyncMock(side_effect=ModbusIOException("boom")),
        ),
        patch("asyncio.sleep", sleep_mock),
    ):
        result = await func(scanner, mock_client, 0x0001, 1)
        assert result is None  # nosec
    assert sleep_mock.await_args_list == []  # nosec
