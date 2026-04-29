"""Validation error mapping tests for config flow."""

import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from custom_components.thessla_green_modbus.const import CONF_SLAVE_ID
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT


@pytest.mark.asyncio
async def test_validate_input_invalid_domain():
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {CONF_HOST: "bad host", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create") as create_mock, pytest.raises(vol.Invalid) as err):
        await validate_input(None, data)
    assert err.value.error_message == "invalid_host"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_validate_input_invalid_ipv4():
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {CONF_HOST: "256.256.256.256", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create") as create_mock, pytest.raises(vol.Invalid) as err):
        await validate_input(None, data)
    assert err.value.error_message == "invalid_host"
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_validate_input_invalid_ipv6():
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {CONF_HOST: "fe80::1::", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create") as create_mock, pytest.raises(vol.Invalid) as err):
        await validate_input(None, data)
    assert err.value.error_message == "invalid_host"
    create_mock.assert_not_called()


@pytest.mark.parametrize("invalid_port", [0, 65536])
@pytest.mark.asyncio
async def test_validate_input_invalid_port(invalid_port: int):
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: invalid_port, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create") as create_mock, pytest.raises(vol.Invalid) as err):
        await validate_input(None, data)
    assert err.value.error_message == "invalid_port"
    create_mock.assert_not_called()


@pytest.mark.parametrize(("invalid_slave", "err_code"), [(-1, "invalid_slave_low"), (248, "invalid_slave_high")])
@pytest.mark.asyncio
async def test_validate_input_invalid_slave(invalid_slave: int, err_code: str):
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: invalid_slave, CONF_NAME: "Test"}
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create") as create_mock, pytest.raises(vol.Invalid) as err):
        await validate_input(None, data)
    assert err.value.error_message == err_code
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_validate_input_no_data():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = AsyncMock()
    scanner_instance.scan_device.return_value = None
    scanner_instance.verify_connection = AsyncMock()
    scanner_instance.close = AsyncMock()
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect)):
        await validate_input(None, data)
    scanner_instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_modbus_exception():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = AsyncMock()
    scanner_instance.scan_device.side_effect = ModbusException("error")
    scanner_instance.verify_connection = AsyncMock()
    scanner_instance.close = AsyncMock()
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect)):
        await validate_input(None, data)
    scanner_instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_verify_connection_failure():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = SimpleNamespace(verify_connection=AsyncMock(side_effect=ConnectionException("fail")), scan_device=AsyncMock(), close=AsyncMock())
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert err.value.args[0] == "cannot_connect"
    scanner_instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_dns_failure():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {CONF_HOST: "example.com", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(side_effect=socket.gaierror())), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert err.value.args[0] == "dns_failure"


@pytest.mark.asyncio
async def test_validate_input_connection_refused():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(side_effect=ConnectionRefusedError())), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert err.value.args[0] == "connection_refused"
