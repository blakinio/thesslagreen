"""Config flow for the ThesslaGreen Modbus integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    CONF_SLAVE_ID,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_RETRY,
    CONF_FORCE_FULL_REGISTER_LIST,
)
from .device_scanner import scan_thessla_green_device

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


# Schema for user input step
USER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
    vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

# Schema for options flow
OPTIONS_SCHEMA = vol.Schema({
    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
    vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
    vol.Required(CONF_RETRY, default=DEFAULT_RETRY): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
    vol.Required(CONF_FORCE_FULL_REGISTER_LIST, default=False): cv.boolean,
})


class ThesslaGreenModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ThesslaGreen Modbus."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_info: Optional[Dict[str, Any]] = None
        self._user_input: Optional[Dict[str, Any]] = None

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate input
            host = user_input[CONF_HOST].strip()
            user_input[CONF_HOST] = host
            user_input[CONF_NAME] = user_input[CONF_NAME].strip()
            port = user_input[CONF_PORT]
            slave_id = user_input[CONF_SLAVE_ID]

            # Check if already configured
            await self.async_set_unique_id(f"{host}_{port}_{slave_id}")
            self._abort_if_unique_id_configured()

            # Test connection using helper validation
            try:
                validation_result = await validate_input(self.hass, user_input)

                self._discovered_info = validation_result["scan_result"]
                self._user_input = user_input

                _LOGGER.info(
                    "Device scan successful: %s, firmware %s, %d registers found",
                    self._discovered_info["device_info"].get("device_name"),
                    self._discovered_info["device_info"].get("firmware"),
                    self._discovered_info.get("register_count")
                )

                return await self.async_step_confirm()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("Unexpected error while validating input for %s:%s: %s", host, port, exc)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
            description_placeholders={
                "default_port": str(DEFAULT_PORT),
                "default_slave_id": str(DEFAULT_SLAVE_ID),
            },
        )

    async def async_step_confirm(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the confirmation step with device information."""
        if user_input is not None:
            # Create entry with scanned information
            return self.async_create_entry(
                title=self._user_input[CONF_NAME],
                data=self._user_input,
                options={
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_RETRY: DEFAULT_RETRY,
                    CONF_FORCE_FULL_REGISTER_LIST: False,
                },
            )

        # Prepare device info for display
        device_info = self._discovered_info["device_info"]
        capabilities = self._discovered_info["capabilities"]
        
        # Create capabilities summary
        active_capabilities = [
            key.replace("_", " ").title() 
            for key, value in capabilities.items() 
            if value is True and not key.startswith("sensor_")
        ]
        
        # Calculate scan success rate
        total_possible = 200  # Approximate total registers
        found_registers = self._discovered_info["register_count"]
        scan_success_rate = f"{(found_registers / total_possible * 100):.1f}%"
        
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "host": self._user_input[CONF_HOST],
                "port": str(self._user_input[CONF_PORT]),
                "slave_id": str(self._user_input[CONF_SLAVE_ID]),
                "device_name": device_info.get("device_name", "Unknown"),
                "firmware_version": device_info.get("firmware", "Unknown"),
                "serial_number": device_info.get("serial_number", "Unknown"),
                "register_count": str(found_registers),
                "scan_success_rate": scan_success_rate,
                "capabilities_count": str(len(active_capabilities)),
                "capabilities_list": ", ".join(active_capabilities[:5]),  # Show first 5
                "auto_detected_note": "✅ Auto-detection enabled - only available functions will be loaded",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> ThesslaGreenModbusOptionsFlow:
        """Get the options flow for this handler."""
        return ThesslaGreenModbusOptionsFlow(config_entry)


class ConfigFlow(ThesslaGreenModbusConfigFlow):
    """Legacy alias for compatibility."""
    pass


class ThesslaGreenModbusOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ThesslaGreen Modbus."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_scan_interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_timeout = self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        current_retry = self.config_entry.options.get(CONF_RETRY, DEFAULT_RETRY)
        current_force_full = self.config_entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)

        # Create dynamic schema with current values
        options_schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=current_scan_interval): vol.All(
                vol.Coerce(int), vol.Range(min=10, max=300)
            ),
            vol.Required(CONF_TIMEOUT, default=current_timeout): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=60)
            ),
            vol.Required(CONF_RETRY, default=current_retry): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=5)
            ),
            vol.Required(CONF_FORCE_FULL_REGISTER_LIST, default=current_force_full): cv.boolean,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "current_scan_interval": str(current_scan_interval),
                "current_timeout": str(current_timeout),
                "current_retry": str(current_retry),
                "force_full_enabled": "Tak" if current_force_full else "Nie",
            },
        )


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from USER_SCHEMA with values provided by the user.
    """
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    slave_id = data[CONF_SLAVE_ID]

    try:
        # Test connection by scanning device
        scan_result = await scan_thessla_green_device(host, port, slave_id, timeout=10)
        return {
            "title": data[CONF_NAME],
            "device_info": scan_result["device_info"],
            "scan_result": scan_result,
        }
    except Exception as exc:
        _LOGGER.error("Validation failed for %s:%s: %s", host, port, exc)
        error_msg = str(exc).lower()
        
        if "timeout" in error_msg or "connection" in error_msg:
            raise CannotConnect(f"Cannot connect to device at {host}:{port}") from exc
        elif "slave" in error_msg or "invalid" in error_msg or "auth" in error_msg:
            raise InvalidAuth(
                f"Invalid slave ID {slave_id} for device at {host}:{port}"
            ) from exc
        else:
            raise CannotConnect(f"Unknown connection error: {exc}") from exc
