"""Test config flow for ThesslaGreen Modbus integration."""

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.config_flow import (
    CannotConnect,
    ConfigFlow,
    InvalidAuth,
)
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_TYPE,
    CONF_SLAVE_ID,
    CONNECTION_TYPE_TCP,
)
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ConnectionException,
    ModbusException,
)
from homeassistant.const import CONF_HOST, CONF_PORT

CONF_NAME = "name"

DEFAULT_USER_INPUT = {
    CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_SLAVE_ID: 10,
    CONF_NAME: "My Device",
}


class AbortFlow(Exception):
    """Mock AbortFlow to simulate Home Assistant aborts."""

    def __init__(self, reason: str) -> None:  # pragma: no cover - simple container
        super().__init__(reason)
        self.reason = reason


@pytest.mark.asyncio

@pytest.mark.asyncio
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

@pytest.mark.asyncio
async def test_form_user_modbus_exception():
    """Test Modbus communication error during user step."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=ModbusException("error"),
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

@pytest.mark.asyncio
async def test_form_user_connection_exception():
    """Test Modbus connection error during user step."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input",
        side_effect=ConnectionException,
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

@pytest.mark.asyncio
async def test_form_user_attribute_error_scanner():
    """AttributeError during scanning should return missing_method error."""
    flow = ConfigFlow()
    flow.hass = None

    scanner_instance = AsyncMock()
    scanner_instance.scan_device.side_effect = AttributeError
    scanner_instance.close = AsyncMock()

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create",
        AsyncMock(return_value=scanner_instance),
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
    assert result["errors"] == {"base": "missing_method"}

@pytest.mark.asyncio
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

@pytest.mark.asyncio
async def test_form_user_invalid_value():
    """Test we handle invalid value error."""
    flow = ConfigFlow()
    flow.hass = None

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            side_effect=ValueError,
        ),
        patch("custom_components.thessla_green_modbus.config_flow._LOGGER") as logger_mock,
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
    logger_mock.error.assert_called_once()

@pytest.mark.asyncio
async def test_form_user_missing_key():
    """Test we handle missing key error."""
    flow = ConfigFlow()
    flow.hass = None

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            side_effect=KeyError("test"),
        ),
        patch("custom_components.thessla_green_modbus.config_flow._LOGGER") as logger_mock,
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
    logger_mock.error.assert_called_once()

@pytest.mark.asyncio
async def test_form_user_unexpected_exception():
    """Test unexpected exceptions are raised."""
    flow = ConfigFlow()
    flow.hass = None

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            side_effect=RuntimeError,
        ),
        patch("custom_components.thessla_green_modbus.config_flow._LOGGER") as logger_mock,
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

    logger_mock.exception.assert_not_called()

