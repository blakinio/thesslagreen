"""TCP user-flow tests for config flow."""

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

@pytest.mark.parametrize("invalid_port", [0, 65536])
@pytest.mark.asyncio
async def test_form_user_port_out_of_range(invalid_port: int):
    """Ports outside valid range should highlight the port field."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(dict(DEFAULT_USER_INPUT, **{CONF_PORT: invalid_port}))

    assert result["type"] == "form"
    assert result["errors"] == {CONF_PORT: "invalid_port"}
    create_mock.assert_not_called()

@pytest.mark.parametrize(
    "slave_id,expected_error",
    [(-1, "invalid_slave_low"), (248, "invalid_slave_high")],
)
@pytest.mark.asyncio
async def test_form_user_invalid_slave_id(slave_id: int, expected_error: str):
    """Invalid slave IDs should highlight the slave_id field."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(dict(DEFAULT_USER_INPUT, **{CONF_SLAVE_ID: slave_id}))

    assert result["type"] == "form"
    assert result["errors"] == {CONF_SLAVE_ID: expected_error}
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_form_user_invalid_domain():
    """Test invalid domain names produce a helpful error."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(dict(DEFAULT_USER_INPUT, **{CONF_HOST: "bad host"}))

    assert result["type"] == "form"
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    create_mock.assert_not_called()

@pytest.mark.asyncio
async def test_form_user_invalid_ipv4():
    """Test invalid IPv4 addresses are rejected."""
    flow = ConfigFlow()
    flow.hass = None

    with patch(
        "custom_components.thessla_green_modbus.scanner.core.ThesslaGreenDeviceScanner.create"
    ) as create_mock:
        result = await flow.async_step_user(
            dict(DEFAULT_USER_INPUT, **{CONF_HOST: "256.256.256.256"})
        )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    create_mock.assert_not_called()

