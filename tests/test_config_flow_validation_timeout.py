"""Timeout/retry/cancellation validation tests."""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONF_SLAVE_ID
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusIOException,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT


@pytest.mark.asyncio
async def test_validate_input_retries_transient_failures():
    from custom_components.thessla_green_modbus.config_flow import validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scan_result = {"device_info": {}, "available_registers": {}, "capabilities": DeviceCapabilities()}
    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(side_effect=[ConnectionException("fail"), None]),
        scan_device=AsyncMock(side_effect=[ConnectionException("fail"), scan_result]),
        close=AsyncMock(),
    )
    create_mock = AsyncMock(side_effect=[ConnectionException("fail"), scanner_instance])
    sleep_mock = AsyncMock()
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", create_mock), patch("asyncio.sleep", sleep_mock)):
        result = await validate_input(None, data)

    assert result["scan_result"] == scan_result
    assert create_mock.await_count == 2
    assert scanner_instance.verify_connection.await_count == 2
    assert scanner_instance.scan_device.await_count == 2
    assert [call.args[0] for call in sleep_mock.await_args_list] == [0.1, 0.1, 0.1]


@pytest.mark.parametrize("exc,err_key", [(asyncio.TimeoutError, "timeout"), (ModbusIOException, "io_error")])
@pytest.mark.asyncio
async def test_validate_input_timeout_errors(exc, err_key):
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(side_effect=exc),
        scan_device=AsyncMock(return_value={"capabilities": DeviceCapabilities()}),
        close=AsyncMock(),
    )
    with (
        patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)),
        patch("asyncio.sleep", AsyncMock()),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == err_key
    scanner_instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_cancelled_timeout_suppresses_traceback(caplog):
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(side_effect=TimeoutError("Modbus request cancelled")),
        scan_device=AsyncMock(return_value={"capabilities": DeviceCapabilities()}),
        close=AsyncMock(),
    )
    with (
        patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.DEBUG),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "timeout"
    assert "Timeout during device validation: Modbus request cancelled" in caplog.text
    assert "Traceback:" not in caplog.text


@pytest.mark.asyncio
async def test_validate_input_cancelled_modbus_io_suppresses_traceback(caplog):
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = SimpleNamespace(
        verify_connection=AsyncMock(side_effect=ModbusIOException("Request cancelled outside pymodbus.")),
        scan_device=AsyncMock(return_value={"capabilities": DeviceCapabilities()}),
        close=AsyncMock(),
    )
    with (
        patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)),
        patch("asyncio.sleep", AsyncMock()),
        caplog.at_level(logging.DEBUG),
        pytest.raises(CannotConnect) as err,
    ):
        await validate_input(None, data)

    assert err.value.args[0] == "timeout"
    assert "Timeout during device validation: Modbus request cancelled" in caplog.text
    assert "Traceback:" not in caplog.text
