"""Optimized config flow for ThesslaGreen Modbus integration."""
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

# Enhanced schema with better validation
STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
    vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(int, vol.Range(min=1, max=247)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

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
})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect - OPTIMIZED VERSION."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    slave_id = data[CONF_SLAVE_ID]

    _LOGGER.info("Validating connection to %s:%s (slave_id=%s)", host, port, slave_id)
    
    scanner = ThesslaGreenDeviceScanner(host, port, slave_id)
    
    try:
        # OPTIMIZATION: Test connection with timeout
        device_info = await asyncio.wait_for(
            scanner.scan_device(), 
            timeout=30.0  # 30 second timeout for initial scan
        )
        
        if not device_info:
            raise CannotConnect("Device scan returned no data")
        
        # Extract device information for better user experience
        device_name = device_info.get("device_info", {}).get("device_name", "ThesslaGreen")
        firmware = device_info.get("device_info", {}).get("firmware", "Unknown")
        capabilities = device_info.get("capabilities", {})
        
        # Count detected capabilities
        active_capabilities = len([k for k, v in capabilities.items() if v])
        
        _LOGGER.info(
            "Successfully validated device: %s (firmware %s, %d capabilities)",
            device_name, firmware, active_capabilities
        )
        
        # Enhanced title with device info
        title = f"{device_name} ({host})"
        if firmware != "Unknown":
            title += f" - FW {firmware}"
            
        return {
            "title": title,
            "device_info": device_info,
            "detected_slave_id": scanner.slave_id,  # May be auto-detected
            "capabilities_count": active_capabilities,
        }
        
    except asyncio.TimeoutError as exc:
        _LOGGER.error("Connection timeout to %s:%s", host, port)
        raise CannotConnect("Connection timeout - device may be unreachable") from exc
    except Exception as exc:
        _LOGGER.exception("Unexpected exception during device validation")
        raise CannotConnect(f"Connection failed: {exc}") from exc


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ThesslaGreen Modbus - OPTIMIZED VERSION."""

    VERSION = 2  # Increased version for enhanced features

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_info: dict[str, Any] = {}
        self._detected_slave_id: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - ENHANCED."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # OPTIMIZATION: Update slave ID if auto-detected
                detected_slave_id = info.get("detected_slave_id")
                if detected_slave_id and detected_slave_id != user_input[CONF_SLAVE_ID]:
                    _LOGGER.info(
                        "Auto-detected slave ID %d (user provided %d)",
                        detected_slave_id, user_input[CONF_SLAVE_ID]
                    )
                    user_input[CONF_SLAVE_ID] = detected_slave_id
                    self._detected_slave_id = detected_slave_id
                
                # Create unique ID based on host and detected slave_id
                unique_id = f"{user_input[CONF_HOST]}_{user_input[CONF_SLAVE_ID]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                # Store additional info for later use
                self.discovered_info = info
                
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    description_placeholders={
                        "capabilities": str(info.get("capabilities_count", 0)),
                        "firmware": info.get("device_info", {}).get("firmware", "Unknown"),
                    },
                )
                
            except CannotConnect as exc:
                errors["base"] = "cannot_connect"
                description_placeholders["error_detail"] = str(exc)
                _LOGGER.warning("Cannot connect: %s", exc)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Enhanced form with better user guidance
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "default_port": str(DEFAULT_PORT),
                "default_slave_id": str(DEFAULT_SLAVE_ID),
                "auto_detect_note": "Slave ID will be auto-detected if the default doesn't work",
                **description_placeholders,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Update the config entry
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data=user_input,
                    reason="reconfigure_successful",
                )
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during reconfiguration")
                errors["base"] = "unknown"

        # Pre-fill form with current values
        config_entry = self._get_reconfigure_entry()
        suggested_values = config_entry.data.copy()
        
        reconfigure_schema = vol.Schema({
            vol.Required(CONF_HOST, default=suggested_values.get(CONF_HOST)): cv.string,
            vol.Optional(CONF_PORT, default=suggested_values.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                int, vol.Range(min=1, max=65535)
            ),
            vol.Optional(CONF_SLAVE_ID, default=suggested_values.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)): vol.All(
                int, vol.Range(min=1, max=247)
            ),
        })

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=reconfigure_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for ThesslaGreen Modbus - ENHANCED."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - ENHANCED."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Validate scan interval doesn't conflict with device capabilities
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            timeout = user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            
            if scan_interval < timeout + 5:
                errors[CONF_SCAN_INTERVAL] = "scan_interval_too_short"
            else:
                return self.async_create_entry(title="", data=user_input)

        # Enhanced options schema with current values as defaults
        current_options = self._config_entry.options
        
        enhanced_options_schema = vol.Schema({
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(int, vol.Range(min=10, max=300)),
            vol.Optional(
                CONF_TIMEOUT,
                default=current_options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): vol.All(int, vol.Range(min=5, max=60)),
            vol.Optional(
                CONF_RETRY,
                default=current_options.get(CONF_RETRY, DEFAULT_RETRY),
            ): vol.All(int, vol.Range(min=1, max=5)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=enhanced_options_schema,
            errors=errors,
            description_placeholders={
                "current_scan_interval": str(current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                "recommended_scan_interval": "30 seconds for most setups",
                "performance_note": "Lower scan intervals provide faster updates but may impact performance",
            },
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle advanced options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Advanced options for power users
        advanced_schema = vol.Schema({
            vol.Optional("enable_debug_logging", default=False): bool,
            vol.Optional("register_scan_on_startup", default=True): bool,
            vol.Optional("adaptive_polling", default=True): bool,
        })

        return self.async_show_form(
            step_id="advanced",
            data_schema=advanced_schema,
            description_placeholders={
                "debug_warning": "Debug logging may generate large log files",
                "adaptive_polling_info": "Adjusts polling based on device response times",
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class DeviceNotSupported(HomeAssistantError):
    """Error to indicate device is not supported."""