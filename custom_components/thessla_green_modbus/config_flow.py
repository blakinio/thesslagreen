"""Enhanced config flow for ThesslaGreen Modbus integration.
Kompletna konfiguracja przez UI z auto-detekcją i opcjami zaawansowanymi.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_RETRY,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RETRY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .device_scanner import ThesslaGreenDeviceScanner

_LOGGER = logging.getLogger(__name__)

# Enhanced schema with comprehensive validation and auto-detection
STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
    vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(int, vol.Range(min=1, max=247)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

# Advanced options schema for power users
OPTIONS_SCHEMA = vol.Schema({
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        int, vol.Range(min=10, max=300)
    ),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
        int, vol.Range(min=5, max=60)
    ),
    vol.Optional(CONF_RETRY, default=DEFAULT_RETRY): vol.All(
        int, vol.Range(min=1, max=5)
    ),
    vol.Optional(CONF_FORCE_FULL_REGISTER_LIST, default=False): cv.boolean,
})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect with enhanced auto-detection."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    slave_id = data[CONF_SLAVE_ID]
    timeout = 10  # Use default timeout for validation
    
    _LOGGER.debug("Validating connection to %s:%s (slave_id=%s)", host, port, slave_id)
    
    # Enhanced connection validation with auto-detection
    scanner = ThesslaGreenDeviceScanner(host, port, slave_id, timeout)
    
    try:
        # First attempt with provided slave_id
        device_scan_result = await asyncio.wait_for(scanner.scan_device(), timeout=30.0)
        
        device_info = device_scan_result["device_info"]
        available_registers = device_scan_result["available_registers"]
        capabilities = device_scan_result["capabilities"]
        scan_statistics = device_scan_result["scan_statistics"]
        
        # Check if we got meaningful data
        total_registers = sum(len(regs) for regs in available_registers.values())
        if total_registers == 0:
            raise CannotConnect("No registers found - device may not be compatible")
        
        _LOGGER.info(
            "Validation successful: %d total registers, %.1f%% scan success",
            total_registers, scan_statistics.get("success_rate", 0)
        )
        
        return {
            "title": device_info.get("device_name", f"ThesslaGreen {host}"),
            "device_info": device_info,
            "capabilities": capabilities,
            "register_count": total_registers,
            "scan_success_rate": scan_statistics.get("success_rate", 0),
        }
        
    except asyncio.TimeoutError:
        _LOGGER.warning("Connection timeout to %s:%s (slave_id=%s)", host, port, slave_id)
        
        # Try auto-detection with common slave IDs
        _LOGGER.info("Attempting auto-detection with common slave IDs...")
        common_slave_ids = [1, 10, 247]  # Most common Modbus slave IDs
        
        for test_slave_id in common_slave_ids:
            if test_slave_id == slave_id:
                continue  # Already tried this one
            
            _LOGGER.debug("Trying slave_id=%s", test_slave_id)
            test_scanner = ThesslaGreenDeviceScanner(host, port, test_slave_id, timeout)
            
            try:
                device_scan_result = await asyncio.wait_for(test_scanner.scan_device(), timeout=15.0)
                total_registers = sum(len(regs) for regs in device_scan_result["available_registers"].values())
                
                if total_registers > 0:
                    _LOGGER.info("Auto-detection successful with slave_id=%s", test_slave_id)
                    # Update the data with the working slave_id
                    data[CONF_SLAVE_ID] = test_slave_id
                    
                    device_info = device_scan_result["device_info"]
                    return {
                        "title": device_info.get("device_name", f"ThesslaGreen {host}"),
                        "device_info": device_info,
                        "capabilities": device_scan_result["capabilities"],
                        "register_count": total_registers,
                        "scan_success_rate": device_scan_result["scan_statistics"].get("success_rate", 0),
                        "auto_detected_slave_id": test_slave_id,
                    }
                    
            except Exception:
                continue  # Try next slave_id
        
        raise CannotConnect("Connection timeout - check network and device settings")
        
    except Exception as exc:
        _LOGGER.error("Connection validation failed: %s", exc)
        raise CannotConnect(f"Connection failed: {exc}")


class ThesslaGreenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ThesslaGreen Modbus integration."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovered_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step with enhanced validation and auto-detection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Store discovered info for use in entry creation
                self._discovered_info = info
                
                # Check for existing entries with same host
                await self.async_set_unique_id(f"{user_input[CONF_HOST]}_{user_input[CONF_SLAVE_ID]}")
                self._abort_if_unique_id_configured()
                
                # Show confirmation with discovered device info
                return await self.async_step_confirm()
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "model": "AirPack Home Serie 4",
                "default_port": str(DEFAULT_PORT),
                "default_slave_id": str(DEFAULT_SLAVE_ID),
            },
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm the setup with discovered device information."""
        if user_input is not None:
            # Create the config entry with discovered info
            device_info = self._discovered_info.get("device_info", {})
            
            title = self._discovered_info.get("title", DEFAULT_NAME)
            if "auto_detected_slave_id" in self._discovered_info:
                title += f" (Auto-detected Slave ID: {self._discovered_info['auto_detected_slave_id']})"
            
            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: self._user_input[CONF_HOST],
                    CONF_PORT: self._user_input[CONF_PORT],
                    CONF_SLAVE_ID: self._user_input[CONF_SLAVE_ID],
                    CONF_NAME: self._user_input.get(CONF_NAME, DEFAULT_NAME),
                },
            )

        # Show device information for confirmation
        device_info = self._discovered_info.get("device_info", {})
        capabilities = self._discovered_info.get("capabilities", {})
        register_count = self._discovered_info.get("register_count", 0)
        scan_success_rate = self._discovered_info.get("scan_success_rate", 0)
        
        # Count enabled capabilities
        enabled_capabilities = [k for k, v in capabilities.items() if v]
        
        placeholders = {
            "host": self._user_input[CONF_HOST],
            "port": self._user_input[CONF_PORT],
            "slave_id": self._user_input[CONF_SLAVE_ID],
            "device_name": device_info.get("device_name", "Unknown"),
            "firmware_version": device_info.get("firmware_version", "Unknown"),
            "serial_number": device_info.get("serial_number", "Unknown"),
            "register_count": register_count,
            "scan_success_rate": f"{scan_success_rate:.1f}%",
            "capabilities_count": len(enabled_capabilities),
            "capabilities_list": ", ".join(enabled_capabilities[:5]),  # Show first 5
        }
        
        if "auto_detected_slave_id" in self._discovered_info:
            placeholders["auto_detected_note"] = (
                f"Note: Slave ID was auto-detected as {self._discovered_info['auto_detected_slave_id']} "
                f"instead of the configured {self._user_input[CONF_SLAVE_ID]}"
            )
        else:
            placeholders["auto_detected_note"] = ""

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for ThesslaGreen Modbus integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options with enhanced configuration."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current options with defaults
        current_options = self.config_entry.options
        
        # Enhanced options schema with current values as defaults
        options_schema = vol.Schema({
            vol.Optional(
                CONF_SCAN_INTERVAL, 
                default=current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): vol.All(int, vol.Range(min=10, max=300)),
            vol.Optional(
                CONF_TIMEOUT, 
                default=current_options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            ): vol.All(int, vol.Range(min=5, max=60)),
            vol.Optional(
                CONF_RETRY, 
                default=current_options.get(CONF_RETRY, DEFAULT_RETRY)
            ): vol.All(int, vol.Range(min=1, max=5)),
            vol.Optional(
                CONF_FORCE_FULL_REGISTER_LIST, 
                default=current_options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
            ): cv.boolean,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "current_scan_interval": str(current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                "current_timeout": str(current_options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
                "current_retry": str(current_options.get(CONF_RETRY, DEFAULT_RETRY)),
                "force_full_enabled": "Yes" if current_options.get(CONF_FORCE_FULL_REGISTER_LIST, False) else "No",
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""