"""Scan-result validation tests for config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONF_SLAVE_ID
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT


@pytest.mark.asyncio
async def test_validate_input_attribute_error():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = SimpleNamespace(scan_device=AsyncMock(return_value={}), close=AsyncMock())
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert err.value.args[0] == "missing_method"
    scanner_instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_serializes_device_capabilities():
    from custom_components.thessla_green_modbus.config_flow import validate_input
    from custom_components.thessla_green_modbus.scanner.core import DeviceCapabilities

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scan_result = {"device_info": {}, "available_registers": {}, "capabilities": DeviceCapabilities(expansion_module=True)}
    scanner_instance = SimpleNamespace(scan_device=AsyncMock(return_value=scan_result), close=AsyncMock(), verify_connection=AsyncMock())
    with patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)):
        result = await validate_input(None, data)
    caps = result["scan_result"]["capabilities"]
    assert isinstance(caps, dict)
    assert caps["expansion_module"] is True
    scanner_instance.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_invalid_capabilities():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scan_result = {"device_info": {}, "available_registers": {}, "capabilities": []}
    scanner_instance = SimpleNamespace(verify_connection=AsyncMock(), scan_device=AsyncMock(return_value=scan_result), close=AsyncMock())
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert str(err.value) == "invalid_capabilities"


@pytest.mark.asyncio
async def test_validate_input_invalid_scan_result_format():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = SimpleNamespace(verify_connection=AsyncMock(), scan_device=AsyncMock(return_value=[]), close=AsyncMock())
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert str(err.value) == "invalid_format"


@pytest.mark.asyncio
async def test_validate_input_missing_capabilities():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scan_result = {"device_info": {}, "available_registers": {}}
    scanner_instance = SimpleNamespace(verify_connection=AsyncMock(), scan_device=AsyncMock(return_value=scan_result), close=AsyncMock())
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert str(err.value) == "invalid_capabilities"


@pytest.mark.asyncio
async def test_validate_input_scan_device_connection_exception():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = SimpleNamespace(verify_connection=AsyncMock(), scan_device=AsyncMock(side_effect=ConnectionException("fail")), close=AsyncMock())
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert err.value.args[0] == "cannot_connect"


@pytest.mark.asyncio
async def test_validate_input_scan_device_modbus_exception():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = SimpleNamespace(verify_connection=AsyncMock(), scan_device=AsyncMock(side_effect=ModbusException("fail")), close=AsyncMock())
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert err.value.args[0] == "modbus_error"


@pytest.mark.asyncio
async def test_validate_input_scan_device_attribute_error():
    from custom_components.thessla_green_modbus.config_flow import CannotConnect, validate_input
    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = SimpleNamespace(verify_connection=AsyncMock(), scan_device=AsyncMock(side_effect=AttributeError), close=AsyncMock())
    with (patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)), pytest.raises(CannotConnect) as err):
        await validate_input(None, data)
    assert err.value.args[0] == "missing_method"
