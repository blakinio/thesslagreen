"""RTU/TCP-RTU user-flow tests for config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from custom_components.thessla_green_modbus.config_flow import ConfigFlow
from custom_components.thessla_green_modbus.const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
    DEFAULT_BAUD_RATE,
    DEFAULT_PARITY,
    DEFAULT_STOP_BITS,
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

@pytest.mark.asyncio
async def test_form_user_rtu_requires_serial_port():
    """Modbus RTU requires a serial port path."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(
            dict(
                DEFAULT_USER_INPUT,
                **{
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
                    CONF_SERIAL_PORT: "",
                },
            )
        )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_SERIAL_PORT: "invalid_serial_port"}
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_form_user_rtu_invalid_baud_rate():
    """Invalid RTU baud rate should be rejected."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(
            dict(
                DEFAULT_USER_INPUT,
                **{
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
                    CONF_SERIAL_PORT: "/dev/ttyUSB0",
                    CONF_BAUD_RATE: "invalid",
                },
            )
        )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_BAUD_RATE: "invalid_baud_rate"}
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_form_user_rtu_success_creates_serial_entry():
    """RTU configuration should persist serial settings."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen Serial",
        "device_info": {"device_name": "Serial", "firmware": "1.0", "serial_number": "ABC"},
        "scan_result": {
            "device_info": {"device_name": "Serial", "firmware": "1.0", "serial_number": "ABC"},
            "capabilities": {"basic_control": True},
            "register_count": 3,
        },
    }

    user_input = dict(
        DEFAULT_USER_INPUT,
        **{
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_RTU,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
            CONF_PARITY: DEFAULT_PARITY,
            CONF_STOP_BITS: DEFAULT_STOP_BITS,
        },
    )

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
    ):
        result = await flow.async_step_user(user_input)
        assert result["type"] == "form"
        result2 = await flow.async_step_confirm({})

    data = result2["data"]
    assert data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_RTU
    assert data[CONF_SERIAL_PORT] == "/dev/ttyUSB0"
    assert data[CONF_BAUD_RATE] == DEFAULT_BAUD_RATE
    assert data[CONF_PARITY] == DEFAULT_PARITY
    assert data[CONF_STOP_BITS] == DEFAULT_STOP_BITS
    # Host/port remain available for diagnostics when provided
    assert data.get(CONF_HOST) == DEFAULT_USER_INPUT[CONF_HOST]
    assert data.get(CONF_PORT) == DEFAULT_USER_INPUT[CONF_PORT]

@pytest.mark.asyncio
async def test_form_user_tcp_rtu_success_creates_tcp_rtu_entry():
    """TCP RTU configuration should normalize to TCP with TCP RTU mode."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen TCP RTU",
        "device_info": {"device_name": "TCP RTU", "firmware": "1.0", "serial_number": "XYZ"},
        "scan_result": {
            "device_info": {"device_name": "TCP RTU", "firmware": "1.0", "serial_number": "XYZ"},
            "capabilities": {"basic_control": True},
            "register_count": 2,
        },
    }

    user_input = dict(
        DEFAULT_USER_INPUT,
        **{
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP_RTU,
        },
    )

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
        result = await flow.async_step_user(user_input)
        assert result["type"] == "form"
        result2 = await flow.async_step_confirm({})

    data = result2["data"]
    assert data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_TCP
    assert data[CONF_CONNECTION_MODE] == CONNECTION_MODE_TCP_RTU
    assert data[CONF_HOST] == DEFAULT_USER_INPUT[CONF_HOST]
    assert data[CONF_PORT] == DEFAULT_USER_INPUT[CONF_PORT]

