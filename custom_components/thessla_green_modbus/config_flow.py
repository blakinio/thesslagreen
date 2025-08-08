"""Config flow for ThesslaGreen Modbus integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    CONF_RETRY,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    DEFAULT_SCAN_INTERVAL,
)
from .device_scanner import EnhancedDeviceScanner

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST, default="192.168.1.100"): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
})

STEP_CONFIRM_DATA_SCHEMA = vol.Schema({
    vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
    vol.Optional("timeout", default=DEFAULT_TIMEOUT): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
    vol.Optional("retry", default=DEFAULT_RETRY): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
})


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    scanner = EnhancedDeviceScanner(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        slave_id=data[CONF_SLAVE_ID],
        timeout=data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        retry_count=data.get(CONF_RETRY, DEFAULT_RETRY),
    )

    try:
        scan_result = await scanner.scan_device()
        if not scan_result or not scan_result.get("available_registers"):
            raise CannotConnect("No valid registers found during device scan")
        
        return {
            "title": data[CONF_NAME],
            "scan_result": scan_result,
            "device_info": scan_result.get("device_info", {}),
        }
    except Exception as exc:
        _LOGGER.error("Failed to connect to device: %s", exc)
        raise CannotConnect("Connection failed") from exc


class ThesslaGreenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ThesslaGreen Modbus."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._user_input: dict[str, Any] | None = None
        self._scan_result: dict[str, Any] | None = None
        self._device_info: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                _LOGGER.debug(
                    "Validating connection to %s:%s (slave_id=%s)",
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_SLAVE_ID],
                )
                
                # Store user input for later use
                self._user_input = user_input
                
                # Test connection and scan device
                scanner = EnhancedDeviceScanner(
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    slave_id=user_input[CONF_SLAVE_ID]
                )
                
                scan_result = await scanner.scan_device()
                
                # Check if device was found
                if not scan_result or not scan_result.get("available_registers"):
                    raise CannotConnect("No valid registers found during device scan")
                
                # Store scan results for later use
                self._scan_result = scan_result
                self._device_info = scan_result.get("device_info", {})
                
                _LOGGER.info(
                    "Validation successful: %d total registers, %.1f%% scan success",
                    len(scan_result['available_registers']),
                    scan_result.get('scan_success_rate', 0)
                )
                
                # Check if device is already configured
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]
                slave_id = user_input[CONF_SLAVE_ID]
                
                unique_id = f"{host}_{port}_{slave_id}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                return await self.async_step_confirm()
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as exc:
                _LOGGER.error("Unexpected exception", exc_info=True)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirmation step."""
        if user_input is not None:
            # Combine stored user input with confirmation options
            if self._user_input is None:
                _LOGGER.error("User input not stored properly")
                return self.async_abort(reason="unknown")
                
            final_data = {
                **self._user_input,
                **user_input,
                # Store scan results in config
                "available_registers": self._scan_result.get("available_registers", []) if self._scan_result else [],
                "device_capabilities": self._scan_result.get("device_capabilities", []) if self._scan_result else [],
            }

            return self.async_create_entry(
                title=f"ThesslaGreen ({self._user_input[CONF_HOST]})",
                data={
                    "host": self._user_input[CONF_HOST],
                    "port": self._user_input[CONF_PORT],
                    "slave_id": self._user_input[CONF_SLAVE_ID],
                    "name": self._user_input[CONF_NAME],
                },
                options=user_input,
            )

        # Show device information and configuration options
        device_info = self._device_info or {}
        description_placeholders = {
            "model": device_info.get("model", "ThesslaGreen AirPack"),
            "registers_found": len(self._scan_result.get("available_registers", [])) if self._scan_result else 0,
            "success_rate": f"{self._scan_result.get('scan_success_rate', 0):.1f}%" if self._scan_result else "0%",
        }

        return self.async_show_form(
            step_id="confirm",
            data_schema=STEP_CONFIRM_DATA_SCHEMA,
            description_placeholders=description_placeholders,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ThesslaGreenOptionsFlow(config_entry)


class ThesslaGreenOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ThesslaGreen Modbus."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional(
                "scan_interval",
                default=self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            vol.Optional(
                "timeout",
                default=self.config_entry.options.get("timeout", DEFAULT_TIMEOUT),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
            vol.Optional(
                "retry",
                default=self.config_entry.options.get("retry", DEFAULT_RETRY),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )