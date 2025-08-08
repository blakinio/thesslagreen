"""Config flow for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    CONF_RETRY,
    CONF_FORCE_FULL_REGISTER_LIST,
)
from .device_scanner import ThesslaGreenDeviceScanner

_LOGGER = logging.getLogger(__name__)

# Configuration schemas
STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.Range(min=1, max=247),
    vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

OPTIONS_SCHEMA = vol.Schema({
    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.Range(min=10, max=300),
    vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Range(min=5, max=60),
    vol.Required(CONF_RETRY, default=DEFAULT_RETRY): vol.Range(min=1, max=5),
    vol.Required(CONF_FORCE_FULL_REGISTER_LIST, default=False): cv.boolean,
})


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    slave_id = data[CONF_SLAVE_ID]
    
    _LOGGER.debug("Validating connection to %s:%s (slave_id=%s)", host, port, slave_id)
    
    # Create device scanner for validation
    scanner = ThesslaGreenDeviceScanner(
        host=host,
        port=port,
        slave_id=slave_id,
        timeout=DEFAULT_TIMEOUT,
        retry=DEFAULT_RETRY
    )
    
    try:
        # Perform device scan
        scan_result = await scanner.scan_device()
        
        if not scan_result:
            raise CannotConnect("No valid registers found during device scan")
            
        # Extract validation info
        device_info = scan_result["device_info"]
        available_registers = scan_result["available_registers"]
        capabilities = scan_result["capabilities"]
        
        # Calculate scan statistics
        total_registers = sum(len(regs) for regs in available_registers.values())
        success_rate = scan_result["diagnostics"]["success_rate"]
        
        # Format capabilities for display
        capabilities_list = []
        if capabilities.get("temperature_sensors"):
            capabilities_list.append("Temperature Sensors")
        if capabilities.get("flow_sensors"):
            capabilities_list.append("Flow Control")
        if capabilities.get("gwc"):
            capabilities_list.append("GWC")
        if capabilities.get("bypass"):
            capabilities_list.append("Bypass")
        if capabilities.get("heating"):
            capabilities_list.append("Heating")
        if capabilities.get("air_quality"):
            capabilities_list.append("Air Quality")
        if capabilities.get("scheduling"):
            capabilities_list.append("Scheduling")
            
        # Return validation result with scan details
        validation_result = {
            "title": data[CONF_NAME],
            "device_info": device_info,
            "scan_result": scan_result,
            "validation_details": {
                "host": host,
                "port": port,
                "slave_id": slave_id,
                "device_name": device_info.get("device_name", "ThesslaGreen AirPack"),
                "firmware_version": device_info.get("firmware", "Unknown"),
                "serial_number": device_info.get("serial_number", "Unknown"),
                "register_count": total_registers,
                "scan_success_rate": f"{success_rate:.1f}%",
                "capabilities_count": len(capabilities_list),
                "capabilities_list": ", ".join(capabilities_list[:3]) + ("..." if len(capabilities_list) > 3 else ""),
                "auto_detected_note": "✅ Auto-detected device capabilities - only available functions will be created" if total_registers > 10 else "⚠️ Limited device response - some functions may not be available"
            }
        }
        
        _LOGGER.info("Device validation successful: %s at %s:%s (%d registers found)", 
                    device_info.get("device_name"), host, port, total_registers)
        
        return validation_result
        
    except Exception as exc:
        _LOGGER.error("Failed to connect to device: %s", exc)
        if "connection" in str(exc).lower() or "timeout" in str(exc).lower():
            raise CannotConnect(f"Connection failed: {exc}")
        elif "authentication" in str(exc).lower() or "slave" in str(exc).lower():
            raise InvalidAuth(f"Authentication failed: {exc}")
        else:
            raise CannotConnect(f"Device validation failed: {exc}")


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ThesslaGreen Modbus."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self.validation_result: Optional[Dict[str, Any]] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", 
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "default_port": str(DEFAULT_PORT),
                    "default_slave_id": str(DEFAULT_SLAVE_ID),
                }
            )

        errors = {}

        try:
            # Validate input
            self.validation_result = await validate_input(self.hass, user_input)
            
            # Check if already configured
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}_{user_input[CONF_SLAVE_ID]}")
            self._abort_if_unique_id_configured()

            # Show confirmation with device details
            return await self.async_step_confirm()
            
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception during configuration")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", 
            data_schema=STEP_USER_DATA_SCHEMA, 
            errors=errors,
            description_placeholders={
                "default_port": str(DEFAULT_PORT),
                "default_slave_id": str(DEFAULT_SLAVE_ID),
            }
        )

    async def async_step_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the confirmation step with device details."""
        if user_input is None and self.validation_result:
            details = self.validation_result["validation_details"]
            
            return self.async_show_form(
                step_id="confirm",
                description_placeholders=details
            )

        if self.validation_result:
            # Store scan result in entry data for use by integration
            entry_data = {
                CONF_HOST: self.validation_result["validation_details"]["host"],
                CONF_PORT: self.validation_result["validation_details"]["port"],
                CONF_SLAVE_ID: self.validation_result["validation_details"]["slave_id"],
                CONF_NAME: self.validation_result["title"],
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
                CONF_RETRY: DEFAULT_RETRY,
                CONF_FORCE_FULL_REGISTER_LIST: False,
                # Store device scan results
                "device_info": self.validation_result["device_info"],
                "scan_result": self.validation_result["scan_result"],
            }

            return self.async_create_entry(
                title=self.validation_result["title"], 
                data=entry_data
            )

        return self.async_abort(reason="unknown")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for ThesslaGreen Modbus."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Validate scan interval change - if changed significantly, suggest restart
            current_scan_interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            new_scan_interval = user_input[CONF_SCAN_INTERVAL]
            
            if abs(current_scan_interval - new_scan_interval) > 10:
                _LOGGER.info("Scan interval changed from %ds to %ds - restart recommended for best performance", 
                           current_scan_interval, new_scan_interval)

            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_options = self.config_entry.options
        current_scan_interval = current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_timeout = current_options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT) 
        current_retry = current_options.get(CONF_RETRY, DEFAULT_RETRY)
        current_force_full = current_options.get(CONF_FORCE_FULL_REGISTER_LIST, False)

        # Create schema with current values
        options_schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=current_scan_interval): vol.Range(min=10, max=300),
            vol.Required(CONF_TIMEOUT, default=current_timeout): vol.Range(min=5, max=60),
            vol.Required(CONF_RETRY, default=current_retry): vol.Range(min=1, max=5),
            vol.Required(CONF_FORCE_FULL_REGISTER_LIST, default=current_force_full): cv.boolean,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "current_scan_interval": str(current_scan_interval),
                "current_timeout": str(current_timeout),
                "current_retry": str(current_retry),
                "force_full_enabled": "Yes" if current_force_full else "No",
            }
        )