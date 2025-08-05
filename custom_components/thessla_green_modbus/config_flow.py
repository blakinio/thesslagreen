"""Optimized config flow for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
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
    capabilities = device_info.get("capabilities", set())
    
    # Count detected capabilities - NAPRAWKA dla set/dict compatibility
    if isinstance(capabilities, dict):
        active_capabilities = len([k for k, v in capabilities.items() if v])
    elif isinstance(capabilities, set):
        active_capabilities = len(capabilities)
    else:
        active_capabilities = 0
    
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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


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
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Use auto-detected slave_id if different from requested
                if info["detected_slave_id"] != user_input[CONF_SLAVE_ID]:
                    user_input[CONF_SLAVE_ID] = info["detected_slave_id"]
                    _LOGGER.info("Auto-corrected slave_id to %s", info["detected_slave_id"])

                # Set unique ID to prevent duplicates
                unique_id = f"{user_input[CONF_HOST]}_{user_input[CONF_SLAVE_ID]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    description_placeholders={
                        "device_name": info["device_name"],
                        "firmware": info["firmware"],
                        "capabilities": str(info["capabilities_count"]),
                    },
                )
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
                "default_host": "192.168.1.100",
                "default_port": str(DEFAULT_PORT),
                "default_slave_id": str(DEFAULT_SLAVE_ID),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of existing entry - NEW HA 2025.7+ Feature."""
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

    async def async_step_dhcp(self, discovery_info) -> FlowResult:
        """Handle DHCP discovery - NEW HA 2025.7+ Feature."""
        _LOGGER.debug("DHCP discovery: %s", discovery_info)
        
        host = discovery_info.ip
        hostname = discovery_info.hostname
        
        # Check if this looks like a ThesslaGreen device
        if not hostname or "thesslagreen" not in hostname.lower():
            return self.async_abort(reason="not_thesslagreen_device")
        
        # Set unique ID to prevent duplicates
        unique_id = f"{host}_dhcp_discovered"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured({CONF_HOST: host})
        
        # Store discovered info for later use
        self.discovered_info = {
            CONF_HOST: host,
            CONF_PORT: DEFAULT_PORT,
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            "hostname": hostname,
        }
        
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery via DHCP."""
        if user_input is not None:
            return await self.async_step_user(self.discovered_info)

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "host": self.discovered_info[CONF_HOST],
                "hostname": self.discovered_info.get("hostname", "Unknown"),
            },
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
        """Manage the options - ENHANCED with device rescan."""
        if user_input is not None:
            # Check if user requested device rescan
            if user_input.pop("rescan_device", False):
                return await self.async_step_rescan()
            
            return self.async_create_entry(title="", data=user_input)

        current_options = self._config_entry.options
        
        options_schema = vol.Schema({
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
            vol.Optional("rescan_device", default=False): bool,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "device_name": self._config_entry.title,
                "current_scan_interval": str(current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
            },
        )

    async def async_step_rescan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device rescan."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        _LOGGER.info("Starting device rescan for %s", self._config_entry.title)
        
        # Trigger device rescan service
        hass = self.hass
        await hass.services.async_call(
            DOMAIN, "device_rescan", service_data={}, blocking=True
        )

        return self.async_show_form(
            step_id="rescan",
            description_placeholders={
                "device_name": self._config_entry.title,
            },
        )