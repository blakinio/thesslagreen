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

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@pytest.mark.asyncio
async def test_duplicate_connection_entry_aborts_during_user_step():
    """A device without serial identity is deduplicated by connection data."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow._async_abort_entries_match",
            side_effect=AbortFlow("already_configured"),
        ),
        pytest.raises(AbortFlow) as err,
    ):
        await flow.async_step_user(DEFAULT_USER_INPUT)

    assert err.value.reason == "already_configured"


@pytest.mark.asyncio
async def test_user_step_duplicate_entry_aborts_silently(caplog):
    """Duplicate device during user step aborts without logging an error."""
    flow = ConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language="en"))
    validation_result = {
        "title": "ThesslaGreen 192.168.1.100",
        "device_info": {},
        "scan_result": {},
    }

    with (
        patch(
            "custom_components.thessla_green_modbus._config_flow.validate_input",
            return_value=validation_result,
        ),
        patch(
            "custom_components.thessla_green_modbus.config_flow.ConfigFlow._async_abort_entries_match",
            side_effect=AbortFlow("already_configured"),
        ),
        caplog.at_level(logging.ERROR),
        pytest.raises(AbortFlow) as err,
    ):
        await flow.async_step_user(DEFAULT_USER_INPUT)

    assert err.value.reason == "already_configured"
    assert not caplog.records
