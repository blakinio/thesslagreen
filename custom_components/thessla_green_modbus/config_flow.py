"""Config flow for ThesslaGreen Modbus integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Autoscan + diagnostyka + enhanced UX
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME, CONF_SCAN_INTERVAL
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
from .device_scanner import ThesslaGreenDeviceScanner  # POPRAWIONE: używamy właściwej nazwy klasy

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST, default="192.168.1.100"): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
})

STEP_CONFIRM_DATA_SCHEMA = vol.Schema({
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
    vol.Optional(CONF_RETRY, default=DEFAULT_RETRY): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
})


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug("Validating connection to %s:%d (slave_id=%d)", 
                 data[CONF_HOST], data[CONF_PORT], data[CONF_SLAVE_ID])
    
    scanner = ThesslaGreenDeviceScanner(  # POPRAWIONE: używamy właściwej nazwy klasy
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        slave_id=data[CONF_SLAVE_ID],
        timeout=data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        retry_count=data.get(CONF_RETRY, DEFAULT_RETRY),
    )

    try:
        # Perform device scan with timeout
        scan_result = await asyncio.wait_for(
            scanner.scan_device(),
            timeout=60  # Max 60 seconds for complete scan
        )
        
        if not scan_result or not scan_result.get("available_registers"):
            raise CannotConnect("No valid registers found during device scan")
        
        # Check if we found minimum required registers
        available_regs = scan_result["available_registers"]
        total_found = sum(len(regs) for regs in available_regs.values())
        
        if total_found < 5:
            raise CannotConnect(f"Only {total_found} registers found - device may not be ThesslaGreen AirPack")
        
        device_info = scan_result.get("device_info", {})
        device_name = device_info.get("device_name", f"ThesslaGreen {data[CONF_HOST]}")
        
        _LOGGER.info("Device validation successful: %s (%d registers, %.1f%% success rate)",
                    device_name, total_found, 
                    scan_result.get("diagnostics", {}).get("success_rate", 0))
        
        return {
            "title": device_name,
            "scan_result": scan_result,
            "device_info": device_info,
        }
        
    except asyncio.TimeoutError:
        _LOGGER.error("Device scan timed out after 60 seconds")
        raise CannotConnect("Device scan timed out - check network connection") from None
        
    except Exception as exc:
        _LOGGER.error("Failed to connect to device: %s", exc, exc_info=True)
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
                validation_result = await validate_input(self.hass, user_input)
                
                # Store scan results for later use
                self._scan_result = validation_result["scan_result"]
                self._device_info = validation_result["device_info"]
                
                _LOGGER.info("Validation successful: %s", validation_result["title"])
                
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
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirmation step with device info display."""
        if user_input is not None:
            # Merge user input with additional options
            final_data = self._user_input.copy()
            final_data.update(user_input)
            
            # Create config entry
            device_name = self._device_info.get("device_name", f"ThesslaGreen {final_data[CONF_HOST]}")
            
            return self.async_create_entry(
                title=device_name,
                data=final_data,
                options={
                    "scan_result": self._scan_result,
                    "device_info": self._device_info,
                }
            )

        # Prepare device information for display
        if not self._scan_result or not self._device_info:
            return self.async_abort(reason="missing_scan_data")

        device_info = self._device_info
        scan_result = self._scan_result
        
        # Calculate statistics for display
        available_regs = scan_result.get("available_registers", {})
        register_count = sum(len(regs) for regs in available_regs.values())
        
        scan_stats = scan_result.get("scan_statistics", {})
        scan_duration = scan_stats.get("scan_duration", 0)
        
        diagnostics = scan_result.get("diagnostics", {})
        success_rate = diagnostics.get("success_rate", 0)
        
        capabilities = scan_result.get("capabilities", {})
        
        # Create capabilities list for display
        capabilities_list = []
        if capabilities.get("temperature_sensors"):
            capabilities_list.append("Temperature Sensors")
        if capabilities.get("flow_sensors"):
            capabilities_list.append("Flow Control")
        if capabilities.get("gwc"):
            capabilities_list.append("GWC System")
        if capabilities.get("bypass"):
            capabilities_list.append("Bypass System")
        if capabilities.get("heating"):
            capabilities_list.append("Heating")
        if capabilities.get("special_functions"):
            capabilities_list.extend(capabilities["special_functions"])
            
        # Format auto-detected note
        auto_detected_note = ""
        if success_rate >= 80:
            auto_detected_note = "✅ **Automatic detection successful** - Only available features will be enabled."
        elif success_rate >= 60:
            auto_detected_note = "⚠️ **Partial detection** - Some features may need manual configuration."
        else:
            auto_detected_note = "❌ **Limited detection** - Manual configuration recommended."

        # Show confirmation form with device details
        return self.async_show_form(
            step_id="confirm",
            data_schema=STEP_CONFIRM_DATA_SCHEMA,
            description_placeholders={
                "host": self._user_input[CONF_HOST],
                "port": str(self._user_input[CONF_PORT]),
                "slave_id": str(self._user_input[CONF_SLAVE_ID]),
                "device_name": device_info.get("device_name", "ThesslaGreen AirPack"),
                "firmware_version": device_info.get("firmware", "Unknown"),
                "serial_number": device_info.get("serial_number", "Unknown"),
                "register_count": str(register_count),
                "scan_success_rate": f"{success_rate:.1f}%",
                "capabilities_count": str(len(capabilities_list)),
                "capabilities_list": ", ".join(capabilities_list[:4]) + ("..." if len(capabilities_list) > 4 else ""),
                "auto_detected_note": auto_detected_note,
            },
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle configuration import from YAML."""
        return await self.async_step_user(import_config)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ThesslaGreenOptionsFlow(config_entry)


class ThesslaGreenOptionsFlow(config_entries.OptionsFlow):
    """Handle ThesslaGreen options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                vol.Optional(
                    CONF_TIMEOUT,
                    default=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Optional(
                    CONF_RETRY,
                    default=self.config_entry.options.get(CONF_RETRY, DEFAULT_RETRY)
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
            }),
        )