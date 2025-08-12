"""Test config flow for ThesslaGreen Modbus integration."""
import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT

CONF_NAME = "name"

from custom_components.thessla_green_modbus.config_flow import (
    ConfigFlow,
    CannotConnect,
    InvalidAuth,
)


pytestmark = pytest.mark.asyncio


async def test_form_user():
    """Test we get the initial form."""
    flow = ConfigFlow()
    flow.hass = None

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["errors"] == {}


async def test_form_user_success():
    """Test successful configuration with confirm step."""
    flow = ConfigFlow()
    flow.hass = None

    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {"device_name": "ThesslaGreen AirPack", "firmware": "1.0", "serial_number": "123"},
        "scan_result": {
            "device_info": {"device_name": "ThesslaGreen AirPack", "firmware": "1.0", "serial_number": "123"},
            "capabilities": {"fan": True},
            "register_count": 5,
        },
    }

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        return_value=validation_result,
    ), patch(
        "custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"
    ), patch(
        "custom_components.thessla_green_modbus.config_flow.ConfigFlow._abort_if_unique_id_configured"
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result2 = await flow.async_step_confirm({})
    assert result2["type"] == "create_entry"
    assert result2["title"] == "My Device"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        "unit": 10,
        CONF_NAME: "My Device",
    }


async def test_form_user_cannot_connect():
    """Test we handle cannot connect error."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_user_invalid_auth():
    """Test we handle invalid auth error."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_user_invalid_value():
    """Test we handle invalid value error."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=ValueError,
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_input"}


async def test_form_user_missing_key():
    """Test we handle missing key error."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=KeyError("test"),
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_input"}


async def test_form_user_unexpected_exception():
    """Test unexpected exceptions are raised."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=RuntimeError,
    ):
        with pytest.raises(RuntimeError):
            await flow.async_step_user(
                {
                    CONF_HOST: "192.168.1.100",
                    CONF_PORT: 502,
                    "slave_id": 10,
                    CONF_NAME: "My Device",
                }
            )


async def test_validate_input_success():
    """Test validate_input with successful connection."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    hass = None
    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    with patch(
        "custom_components.thessla_green_modbus.config_flow.ThesslaGreenDeviceScanner"
    ) as mock_scanner_cls:
        scanner_instance = AsyncMock()
        scanner_instance.scan_device.return_value = {
            "available_registers": {},
            "device_info": {
                "device_name": "ThesslaGreen AirPack",
                "firmware": "1.0",
                "serial_number": "123",
            },
            "capabilities": {},
        }
        mock_scanner_cls.return_value = scanner_instance
        result = await validate_input(hass, data)
        scanner_instance.close.assert_awaited_once()

    assert result["title"] == "Test"
    assert "device_info" in result


async def test_validate_input_no_data():
    """Test validate_input with no device data."""
    from custom_components.thessla_green_modbus.config_flow import validate_input

    hass = None
    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 502,
        "slave_id": 10,
        CONF_NAME: "Test",
    }

    with patch(
        "custom_components.thessla_green_modbus.device_scanner.ThesslaGreenDeviceScanner.scan_device",
        return_value=None,
    ):
        with pytest.raises(CannotConnect):
            await validate_input(hass, data)
