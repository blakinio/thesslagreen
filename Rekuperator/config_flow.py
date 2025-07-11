"""Config flow for TeslaGreen Modbus Integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_SLAVE_ID, CONF_SLAVE_ID

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
    }
)


class TeslaGreenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TeslaGreen Modbus Integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidHost:
            errors["host"] = "invalid_host"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    try:
        from pymodbus.client import ModbusTcpClient
        
        client = ModbusTcpClient(
            host=data[CONF_HOST],
            port=data[CONF_PORT],
            timeout=5
        )
        
        if not client.connect():
            raise CannotConnect("Cannot connect to Modbus device")
        
        # Test reading a register
        result = client.read_holding_registers(0x0001, 1, slave=data[CONF_SLAVE_ID])
        if result.isError():
            raise CannotConnect("Failed to read from device")
        
        client.close()
        
        return {"title": f"TeslaGreen {data[CONF_HOST]}"}
        
    except Exception as ex:
        raise CannotConnect(f"Connection failed: {ex}") from ex


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
