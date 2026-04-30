"""Test config flow for ThesslaGreen Modbus integration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.config_flow import (
    ConfigFlow,
)
from custom_components.thessla_green_modbus.const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_DEEP_SCAN,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONNECTION_MODE_AUTO,
    CONNECTION_TYPE_TCP,
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
async def test_form_user():
    """Test we get the initial form."""
    flow = ConfigFlow()
    flow.hass = None

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["errors"] == {}
    schema_keys = {
        key.schema if hasattr(key, "schema") else key for key in result["data_schema"].schema
    }
    assert CONF_CONNECTION_TYPE in schema_keys
    assert CONF_CONNECTION_MODE not in schema_keys
    assert CONF_HOST in schema_keys
    assert CONF_SERIAL_PORT not in schema_keys
    assert CONF_BAUD_RATE not in schema_keys
    assert CONF_PARITY not in schema_keys
    assert CONF_STOP_BITS not in schema_keys

@pytest.mark.asyncio
async def test_form_user_invalid_ipv6():
    """Test invalid IPv6 addresses are rejected."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(
            {
                CONF_HOST: "fe80::1::",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_form_user_valid_ipv6():
    """Test IPv6 addresses are accepted."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen fe80::1",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured"
        ),
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "fe80::1",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

@pytest.mark.asyncio
async def test_form_user_valid_domain():
    """Test domain names are accepted."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen example.com",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured"
        ),
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: "example.com",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

@pytest.mark.asyncio
async def test_form_user_success():
    """Test successful configuration with confirm step."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    translations = {
        "auto_detected_note_success": "Auto-detection successful!",
        "auto_detected_note_limited": "Limited auto-detection - some registers may be missing.",
    }

    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {
            "device_name": "ThesslaGreen AirPack",
            "firmware": "1.0",
            "serial_number": "123",
        },
        "scan_result": {
            "device_info": {
                "device_name": "ThesslaGreen AirPack",
                "firmware": "1.0",
                "serial_number": "123",
            },
            "capabilities": {"expansion_module": True},
            "register_count": 5,
        },
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch("custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured"
        ),
        patch(
            "homeassistant.helpers.translation.async_get_translations",
            new=AsyncMock(return_value=translations),
        ),
    ):
        result = await flow.async_step_user(
            dict(DEFAULT_USER_INPUT, **{CONF_DEEP_SCAN: True, CONF_MAX_REGISTERS_PER_REQUEST: 5})
        )
        assert result["type"] == "form"
        assert result["step_id"] == "confirm"
        assert (
            result["description_placeholders"]["auto_detected_note"]
            == translations["auto_detected_note_success"]
        )

        result2 = await flow.async_step_confirm({})

    assert result2["type"] == "create_entry"
    assert result2["title"] == "My Device"
    data = result2["data"]
    assert data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_TCP
    assert data[CONF_CONNECTION_MODE] == CONNECTION_MODE_AUTO
    assert data[CONF_HOST] == DEFAULT_USER_INPUT[CONF_HOST]
    assert data[CONF_PORT] == DEFAULT_USER_INPUT[CONF_PORT]
    assert data["slave_id"] == DEFAULT_USER_INPUT[CONF_SLAVE_ID]
    assert data[CONF_NAME] == DEFAULT_USER_INPUT[CONF_NAME]
    assert isinstance(data["capabilities"], dict)
    assert data["capabilities"]["expansion_module"] is True
    assert result2["options"][CONF_DEEP_SCAN] is True
    assert result2["options"][CONF_MAX_REGISTERS_PER_REQUEST] == 5

@pytest.mark.asyncio
async def test_unique_id_sanitized():
    """Ensure unique ID replaces colons in host with hyphens."""
    flow = ConfigFlow()
    flow.hass = None

    validation_result = {
        "title": "ThesslaGreen fe80::1",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus.config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow."
            "_abort_if_unique_id_configured",
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"
        ) as mock_set_unique_id,
    ):
        await flow.async_step_user(
            {
                CONF_HOST: "fe80::1",
                CONF_PORT: 502,
                "slave_id": 10,
                CONF_NAME: "My Device",
            }
        )

    mock_set_unique_id.assert_called_once_with("fe80--1:502:10")


