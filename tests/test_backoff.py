from unittest.mock import AsyncMock, patch

import pytest

from custom_components.thessla_green_modbus.modbus_exceptions import ModbusIOException
from custom_components.thessla_green_modbus.scanner_core import ThesslaGreenDeviceScanner

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "method,address,count,primary_attr,fallback_attr,expected",
    [
        (
            ThesslaGreenDeviceScanner._read_input,
            0x0001,
            1,
            "read_input_registers",
            "read_holding_registers",
            [0.1, 0.2],
        ),
        (
            ThesslaGreenDeviceScanner._read_holding,
            0x0001,
            1,
            "read_holding_registers",
            None,
            [0.1, 0.2],
        ),
        (
            ThesslaGreenDeviceScanner._read_coil,
            0x0000,
            1,
            "read_coils",
            None,
            [0.1, 0.2],
        ),
        (
            ThesslaGreenDeviceScanner._read_discrete,
            0x0000,
            1,
            "read_discrete_inputs",
            None,
            [0.1, 0.2],
        ),
    ],
)
async def test_backoff_delay(method, address, count, primary_attr, fallback_attr, expected):
    """Scanner helpers honour exponential backoff via _call_modbus."""

    scanner = await ThesslaGreenDeviceScanner.create("host", 1234, 10, retry=3, backoff=0.1)
    mock_client = AsyncMock()
    setattr(mock_client, primary_attr, AsyncMock(side_effect=ModbusIOException("boom")))
    if fallback_attr is not None:
        setattr(mock_client, fallback_attr, AsyncMock(side_effect=ModbusIOException("boom")))

    sleep_mock = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.modbus_helpers.asyncio.sleep",
        sleep_mock,
    ):
        result = await method(scanner, mock_client, address, count)
        assert result is None  # nosec

    assert [call.args[0] for call in sleep_mock.await_args_list] == expected  # nosec


@pytest.mark.parametrize(
    "method,address,count,primary_attr,fallback_attr",
    [
        (
            ThesslaGreenDeviceScanner._read_input,
            0x0001,
            1,
            "read_input_registers",
            "read_holding_registers",
        ),
        (
            ThesslaGreenDeviceScanner._read_holding,
            0x0001,
            1,
            "read_holding_registers",
            None,
        ),
        (
            ThesslaGreenDeviceScanner._read_coil,
            0x0000,
            1,
            "read_coils",
            None,
        ),
        (
            ThesslaGreenDeviceScanner._read_discrete,
            0x0000,
            1,
            "read_discrete_inputs",
            None,
        ),
    ],
)
async def test_backoff_zero_no_delay(method, address, count, primary_attr, fallback_attr):
    """When backoff is zero, the helper should not sleep between attempts."""

    scanner = await ThesslaGreenDeviceScanner.create("host", 1234, 10, retry=3, backoff=0)
    mock_client = AsyncMock()
    setattr(mock_client, primary_attr, AsyncMock(side_effect=ModbusIOException("boom")))
    if fallback_attr is not None:
        setattr(mock_client, fallback_attr, AsyncMock(side_effect=ModbusIOException("boom")))

    sleep_mock = AsyncMock()
    with patch(
        "custom_components.thessla_green_modbus.modbus_helpers.asyncio.sleep",
        sleep_mock,
    ):
        result = await method(scanner, mock_client, address, count)
        assert result is None  # nosec

    assert sleep_mock.await_args_list == []  # nosec


async def test_backoff_with_jitter():
    """Backoff jitter adds a random component to the delay."""

    scanner = await ThesslaGreenDeviceScanner.create(
        "host", 1234, 10, retry=3, backoff=0.1, backoff_jitter=0.05
    )
    mock_client = AsyncMock()
    mock_client.read_holding_registers = AsyncMock(side_effect=ModbusIOException("boom"))

    sleep_mock = AsyncMock()
    with (
        patch(
            "custom_components.thessla_green_modbus.modbus_helpers.random.uniform",
            side_effect=[0.05, 0.05],
        ),
        patch(
            "custom_components.thessla_green_modbus.modbus_helpers.asyncio.sleep",
            sleep_mock,
        ),
    ):
        result = await scanner._read_holding(mock_client, 0x0001, 1)
        assert result is None  # nosec

    delays = [call.args[0] for call in sleep_mock.await_args_list]
    assert delays == pytest.approx([0.15, 0.25])
