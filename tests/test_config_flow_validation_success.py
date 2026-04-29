"""Success-path config-flow validation tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.const import CONF_SLAVE_ID
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT


@pytest.mark.asyncio
async def test_validate_input_success():
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = AsyncMock()
    scanner_instance.scan_device.return_value = {
        "available_registers": {},
        "device_info": {"device_name": "ThesslaGreen AirPack", "firmware": "1.0", "serial_number": "123"},
        "capabilities": {},
    }
    scanner_instance.verify_connection = AsyncMock()
    with patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)):
        result = await validate_input(None, data)

    assert result["title"] == "Test"
    assert "device_info" in result
    scanner_instance.verify_connection.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_valid_ipv6():
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {CONF_HOST: "fe80::1", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = AsyncMock()
    scanner_instance.scan_device.return_value = {"available_registers": {}, "device_info": {}, "capabilities": {}}
    scanner_instance.verify_connection = AsyncMock()
    scanner_instance.close = AsyncMock()

    with patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)):
        result = await validate_input(None, data)

    assert result["title"] == "Test"
    scanner_instance.verify_connection.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_valid_domain():
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {CONF_HOST: "example.com", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scanner_instance = AsyncMock()
    scanner_instance.scan_device.return_value = {"available_registers": {}, "device_info": {}, "capabilities": {}}
    scanner_instance.verify_connection = AsyncMock()
    scanner_instance.close = AsyncMock()

    with patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)):
        result = await validate_input(None, data)

    assert result["title"] == "Test"
    scanner_instance.verify_connection.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_input_uses_scan_device_and_closes():
    from custom_components.thessla_green_modbus.config_flow import validate_input

    data = {CONF_HOST: "192.168.1.100", CONF_PORT: 502, CONF_SLAVE_ID: 10, CONF_NAME: "Test"}
    scan_result = {"device_info": {"device_name": "Device"}, "available_registers": {}, "capabilities": {}}
    scanner_instance = SimpleNamespace(
        scan_device=AsyncMock(return_value=scan_result),
        close=AsyncMock(),
        verify_connection=AsyncMock(),
    )

    with patch("custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create", AsyncMock(return_value=scanner_instance)):
        result = await validate_input(None, data)

    assert isinstance(result["scan_result"], dict)
    assert isinstance(result["scan_result"].get("capabilities"), dict)
    scanner_instance.verify_connection.assert_awaited_once()
    scanner_instance.scan_device.assert_awaited_once()
    scanner_instance.close.assert_awaited_once()
