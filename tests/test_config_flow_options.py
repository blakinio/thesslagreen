"""Test config flow for ThesslaGreen Modbus integration."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from custom_components.thessla_green_modbus.config_flow import (
    ConfigFlow,
    OptionsFlow,
)
from custom_components.thessla_green_modbus.config_flow_options_form import (
    build_options_form_payload,
)
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_TYPE,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_SLAVE_ID,
    CONNECTION_TYPE_TCP,
    MAX_BATCH_REGISTERS,
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
async def test_config_flow_max_registers_per_request_validated():
    """Config flow validates max registers per request."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace()
    result = await flow.async_step_user()
    schema_keys = {
        key.schema if hasattr(key, "schema") else key for key in result["data_schema"].schema
    }
    assert CONF_MAX_REGISTERS_PER_REQUEST in schema_keys

    validation_result = {"device_info": {}, "scan_result": {}}
    for value in (1, MAX_BATCH_REGISTERS):
        flow = ConfigFlow()
        flow.hass = SimpleNamespace()
        with (
            patch(
                "custom_components.thessla_green_modbus.config_flow.validate_input",
                return_value=validation_result,
            ),
            patch(
                "custom_components.thessla_green_modbus.config_flow.ConfigFlow.async_set_unique_id"
            ),
            patch(
                "custom_components.thessla_green_modbus.config_flow.ConfigFlow._abort_if_unique_id_configured"
            ),
        ):
            result = await flow.async_step_user(
                {
                    CONF_HOST: "192.168.1.100",
                    CONF_PORT: 502,
                    CONF_SLAVE_ID: 10,
                    CONF_MAX_REGISTERS_PER_REQUEST: value,
                }
            )
            assert result["type"] == "form"
            assert result["step_id"] == "confirm"

    flow = ConfigFlow()
    flow.hass = SimpleNamespace()
    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input"
    ) as mock_validate:
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                CONF_SLAVE_ID: 10,
                CONF_MAX_REGISTERS_PER_REQUEST: 0,
            }
        )
        assert result["type"] == "form"
        assert result["errors"][CONF_MAX_REGISTERS_PER_REQUEST] == "max_registers_range"
        mock_validate.assert_not_called()

    flow = ConfigFlow()
    flow.hass = SimpleNamespace()
    with patch(
        "custom_components.thessla_green_modbus.config_flow.validate_input"
    ) as mock_validate:
        result = await flow.async_step_user(
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 502,
                CONF_SLAVE_ID: 10,
                CONF_MAX_REGISTERS_PER_REQUEST: 20,
            }
        )
        assert result["type"] == "form"
        assert result["errors"][CONF_MAX_REGISTERS_PER_REQUEST] == "max_registers_range"
        mock_validate.assert_not_called()

@pytest.mark.asyncio
async def test_options_flow_max_registers_per_request_validation():
    """Options flow validates max registers per request within range."""

@pytest.mark.asyncio
async def test_options_flow_max_registers_per_request_validated():
    """Options flow should validate max registers per request range."""
    config_entry = SimpleNamespace(options={})
    flow = OptionsFlow(config_entry)

    result = await flow.async_step_init()
    schema_keys = {
        key.schema if hasattr(key, "schema") else key for key in result["data_schema"].schema
    }
    assert CONF_MAX_REGISTERS_PER_REQUEST in schema_keys

    # Accept values within range
    for value in (1, MAX_BATCH_REGISTERS):
        flow = OptionsFlow(SimpleNamespace(options={}))
        result = await flow.async_step_init({CONF_MAX_REGISTERS_PER_REQUEST: value})
        assert result["type"] == "create_entry"
        assert result["data"][CONF_MAX_REGISTERS_PER_REQUEST] == value

    # Reject values below range
    flow = OptionsFlow(SimpleNamespace(options={}))
    result = await flow.async_step_init({CONF_MAX_REGISTERS_PER_REQUEST: 0})
    assert result["type"] == "form"
    assert result["errors"][CONF_MAX_REGISTERS_PER_REQUEST] == "max_registers_range"

    # Reject values above range
    flow = OptionsFlow(SimpleNamespace(options={}))
    result = await flow.async_step_init({CONF_MAX_REGISTERS_PER_REQUEST: 20})
    assert result["type"] == "form"
    assert result["errors"][CONF_MAX_REGISTERS_PER_REQUEST] == "max_registers_range"



@pytest.mark.asyncio
async def test_build_options_form_payload_includes_transport_placeholders():
    """Options form payload builder returns schema and placeholders."""
    data_schema, placeholders = build_options_form_payload(
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP, CONF_PORT: 502},
        {},
    )

    schema_keys = {
        key.schema if hasattr(key, "schema") else key for key in data_schema.schema
    }
    assert CONF_MAX_REGISTERS_PER_REQUEST in schema_keys
    assert placeholders["transport_label"] in {"Modbus TCP", "Modbus TCP (Auto)", "Modbus TCP RTU"}
