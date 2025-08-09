"""POPRAWIONY Config flow for ThesslaGreen Modbus integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
FIX: already_configured error, unique_id logic, validation flow
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_SLAVE_ID, 
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_RETRY,
    CONF_FORCE_FULL_REGISTER_LIST,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRY,
)
from .device_scanner import ThesslaGreenDeviceScanner

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
        vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(int, vol.Range(min=1, max=247)),
        vol.Optional(CONF_NAME, default="ThesslaGreen AirPack"): str,
    }
)

STEP_OPTIONS_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=10, max=300)),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(int, vol.Range(min=5, max=60)),
        vol.Optional(CONF_RETRY, default=DEFAULT_RETRY): vol.All(int, vol.Range(min=1, max=5)),
        vol.Optional(CONF_FORCE_FULL_REGISTER_LIST, default=False): bool,
    }
)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


async def validate_input(hass, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    slave_id = data[CONF_SLAVE_ID]
    
    _LOGGER.debug("Validating connection to %s:%s with slave_id %s", host, port, slave_id)
    
    try:
        # Create device scanner and test connection
        scanner = ThesslaGreenDeviceScanner(
            host=host,
            port=port, 
            slave_id=slave_id,
            timeout=15,  # Longer timeout for validation
            retry=3
        )
        
        # Perform device scan
        scan_result = await scanner.scan_device()
        
        if not scan_result:
            raise CannotConnect("Device scan failed - no response from device")
            
        device_info = scan_result.get("device_info", {})
        available_registers = scan_result.get("available_registers", {})
        
        # Count total found registers
        total_registers = sum(len(regs) for regs in available_registers.values())
        
        if total_registers == 0:
            raise CannotConnect("No valid Modbus registers found")
            
        # Generate capabilities list for display
        capabilities = scan_result.get("capabilities", {})
        capabilities_list = []
        
        if capabilities.get("temperature_sensors"):
            capabilities_list.append("Temperature Sensors")
        if capabilities.get("gwc"):
            capabilities_list.append("GWC")
        if capabilities.get("bypass"):
            capabilities_list.append("Bypass")
        if capabilities.get("heating"):
            capabilities_list.append("Heating")
        if capabilities.get("filter_monitoring"):
            capabilities_list.append("Filter Monitoring")
        if capabilities.get("special_functions"):
            for func in capabilities["special_functions"]:
                capabilities_list.append(func)
                
        # Success rate calculation
        scan_stats = scan_result.get("scan_stats", {})
        success_rate = f"{(scan_stats.get('total_successful', 0) / max(scan_stats.get('total_attempted', 1), 1)) * 100:.1f}%"
        
        validation_result = {
            "title": f"ThesslaGreen {device_info.get('device_name', host)}",
            "device_info": device_info,
            "scan_result": scan_result,
            "validation_details": {
                "host": host,
                "port": port,
                "slave_id": slave_id,
                "device_name": device_info.get("device_name", "AirPack"),
                "firmware_version": device_info.get("firmware_version", "Unknown"),
                "serial_number": device_info.get("serial_number", "Unknown"),
                "register_count": total_registers,
                "scan_success_rate": success_rate,
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
            # POPRAWKA: Sprawdź unique_id przed walidacją
            unique_id = f"{user_input[CONF_HOST]}_{user_input[CONF_SLAVE_ID]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Validate input
            self.validation_result = await validate_input(self.hass, user_input)
            
            # Show confirmation with device details
            return await self.async_step_confirm()
            
        except config_entries.data_entry_flow.AbortFlow:
            # Re-raise abort flow exceptions (already_configured, etc.)
            raise
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
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        current_timeout = self.config_entry.options.get(
            CONF_TIMEOUT, self.config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        )
        current_retry = self.config_entry.options.get(
            CONF_RETRY, self.config_entry.data.get(CONF_RETRY, DEFAULT_RETRY)
        )
        current_force_full = self.config_entry.options.get(
            CONF_FORCE_FULL_REGISTER_LIST, self.config_entry.data.get(CONF_FORCE_FULL_REGISTER_LIST, False)
        )

        # Create options schema with current values
        options_schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current_scan_interval): vol.All(int, vol.Range(min=10, max=300)),
                vol.Optional(CONF_TIMEOUT, default=current_timeout): vol.All(int, vol.Range(min=5, max=60)),
                vol.Optional(CONF_RETRY, default=current_retry): vol.All(int, vol.Range(min=1, max=5)),
                vol.Optional(CONF_FORCE_FULL_REGISTER_LIST, default=current_force_full): bool,
            }
        )

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