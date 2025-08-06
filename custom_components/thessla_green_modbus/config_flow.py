"""Enhanced config flow for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
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
    CONF_FORCE_FULL_REGISTER_LIST,
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

# Enhanced schema with better validation and auto-detection support
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
    vol.Optional(CONF_FORCE_FULL_REGISTER_LIST, default=False): cv.boolean,
})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect - ENHANCED VERSION."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    requested_slave_id = data[CONF_SLAVE_ID]

    _LOGGER.info("Validating connection to %s:%s (requested slave_id=%s)", host, port, requested_slave_id)
    
    # Enhanced connection validation with auto-detection of slave ID
    detected_slave_id = None
    device_info = None
    
    # Try common slave IDs if the requested one fails
    slave_ids_to_try = [requested_slave_id, 1, 10, 247] if requested_slave_id not in [1, 10, 247] else [requested_slave_id]
    
    for slave_id in slave_ids_to_try:
        scanner = ThesslaGreenDeviceScanner(host, port, slave_id)
        
        try:
            _LOGGER.debug("Trying slave_id=%s", slave_id)
            device_info = await asyncio.wait_for(
                scanner.scan_device(), 
                timeout=30.0  # 30 second timeout for each attempt
            )
            
            if device_info and device_info.get("device_info"):
                detected_slave_id = slave_id
                _LOGGER.info("Successfully connected with slave_id=%s", slave_id)
                break
                
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout connecting with slave_id=%s", slave_id)
            continue
        except Exception as exc:
            _LOGGER.debug("Failed to connect with slave_id=%s: %s", slave_id, exc)
            continue
    
    if not device_info or not detected_slave_id:
        raise CannotConnect("Could not connect to device with any common slave ID (1, 10, 247)")
    
    # Extract device information for better user experience
    device_data = device_info.get("device_info", {})
    device_name = device_data.get("device_name", "ThesslaGreen")
    firmware = device_data.get("firmware", "Unknown")
    capabilities = device_info.get("capabilities", {})
    
    # Count detected capabilities
    active_capabilities = len([k for k, v in capabilities.items() if v])
    
    _LOGGER.info(
        "Device validation successful: %s (firmware %s, %d capabilities, slave_id=%s)",
        device_name, firmware, active_capabilities, detected_slave_id
    )
    
    # Enhanced title with device info
    title = f"{device_name} ({host})"
    if firmware != "Unknown":
        title += f" - FW {firmware}"
        
    return {
        "title": title,
        "device_info": device_info,
        "detected_slave_id": detected_slave_id,  # Auto-detected slave ID
        "capabilities_count": active_capabilities,
        "firmware": firmware,
        "device_name": device_name,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ThesslaGreen Modbus - HA 2025.7+ Compatible."""

    VERSION = 2  # Increased version for enhanced features

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_info: dict[str, Any] = {}
        self._detected_slave_id: int | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - ENHANCED with auto-detection."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "default_port": str(DEFAULT_PORT),
                    "default_slave_id": str(DEFAULT_SLAVE_ID),
                },
            )

        errors = {}

        try:
            # Enhanced validation with detailed error handling
            info = await validate_input(self.hass, user_input)
            
            # Store discovered information for better user experience
            self.discovered_info = info
            self._detected_slave_id = info["detected_slave_id"]
            
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception during validation")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user", 
                data_schema=STEP_USER_DATA_SCHEMA, 
                errors=errors,
                description_placeholders={
                    "default_port": str(DEFAULT_PORT),
                    "default_slave_id": str(DEFAULT_SLAVE_ID),
                },
            )

        # Enhanced unique ID with auto-detected slave ID
        unique_id = f"{user_input[CONF_HOST]}_{self._detected_slave_id}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Enhanced config entry data with discovered information
        config_data = {
            CONF_HOST: user_input[CONF_HOST],
            CONF_PORT: user_input[CONF_PORT],
            CONF_SLAVE_ID: self._detected_slave_id,  # Use auto-detected slave ID
            CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
        }

        return self.async_create_entry(
            title=self.discovered_info["title"], 
            data=config_data,
            description=f"Detected {self.discovered_info['capabilities_count']} capabilities"
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow - ENHANCED with more options."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Enhanced options flow handler - HA 2025.7+ Compatible."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the enhanced options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Enhanced options schema with current values
        current_options = self.config_entry.options
        
        schema = vol.Schema({
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
            data_schema=schema,
            description_placeholders={
                "device_name": self.config_entry.data.get(CONF_NAME, "ThesslaGreen"),
                "host": self.config_entry.data[CONF_HOST],
                "current_scan_interval": str(current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                "current_timeout": str(current_options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
                "current_retry": str(current_options.get(CONF_RETRY, DEFAULT_RETRY)),
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""