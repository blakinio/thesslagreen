"""Duplicate-handling user-flow tests for config flow."""

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from custom_components.thessla_green_modbus.config_flow import ConfigFlow
from custom_components.thessla_green_modbus.const import (
    CONF_CONNECTION_TYPE,
    CONF_SLAVE_ID,
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
async def test_duplicate_entry_aborts():
    """Attempting to add a duplicate entry should abort the flow."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
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
            "_abort_if_unique_id_configured",
            side_effect=[None, AbortFlow("already_configured")],
        ),
    ):
        await flow.async_step_user(DEFAULT_USER_INPUT)

        with pytest.raises(AbortFlow):
            await flow.async_step_confirm({})

@pytest.mark.asyncio
async def test_user_step_duplicate_entry_aborts_silently(caplog):
    """Duplicate device during user step should abort without logging errors."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
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
            "_abort_if_unique_id_configured",
            side_effect=AbortFlow("already_configured"),
        ),
        caplog.at_level(logging.ERROR),
        pytest.raises(AbortFlow) as err,
    ):
        await flow.async_step_user(DEFAULT_USER_INPUT)

    assert err.value.reason == "already_configured"
    assert not caplog.records

