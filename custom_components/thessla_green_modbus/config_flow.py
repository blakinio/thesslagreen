"""Config flow for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from pymodbus.exceptions import ConnectionException, ModbusException

from .const import (
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_RETRY,
    CONF_SCAN_INTERVAL,
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


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


async def validate_input(_hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    slave_id = data[CONF_SLAVE_ID]
    name = data.get(CONF_NAME, DEFAULT_NAME)

    # Try to connect and scan device
    scanner = ThesslaGreenDeviceScanner(
        host=host, port=port, slave_id=slave_id, timeout=10, retry=3
    )

    try:
        scan_result = await scanner.scan_device()

        if not scan_result:
            raise CannotConnect("Device scan failed - no data received")

        device_info = scan_result.get("device_info", {})

        # Return validated data with device info
        return {"title": name, "device_info": device_info, "scan_result": scan_result}

    except ConnectionException as exc:
        _LOGGER.exception("Connection error: %s", exc)
        raise CannotConnect from exc
    except ModbusException as exc:
        _LOGGER.exception("Modbus error: %s", exc)
        raise CannotConnect from exc
    except (OSError, asyncio.TimeoutError) as exc:
        _LOGGER.exception("Unexpected error during device validation: %s", exc)
        raise CannotConnect from exc
    finally:
        await scanner.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ThesslaGreen Modbus."""

    VERSION = 2

    def __init__(self):
        """Initialize config flow."""
        self._data: dict[str, Any] = {}
        self._device_info: dict[str, Any] = {}
        self._scan_result: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate input and get device info
                info = await validate_input(self.hass, user_input)

                # Store data for confirm step
                self._data = user_input
                self._device_info = info.get("device_info", {})
                self._scan_result = info.get("scan_result", {})

                # Set unique ID based on host, port and slave_id
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:{user_input[CONF_SLAVE_ID]}"
                )
                self._abort_if_unique_id_configured()

                # Show confirmation step with device info
                return await self.async_step_confirm()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except (ConnectionException, ModbusException):
                _LOGGER.exception("Modbus communication error")
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=247)
                ),
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the confirm step."""
        if user_input is not None:
            # Create entry with all data
            # Use both 'slave_id' and 'unit' for compatibility
            return self.async_create_entry(
                title=self._data.get(CONF_NAME, DEFAULT_NAME),
                data={
                    CONF_HOST: self._data[CONF_HOST],
                    CONF_PORT: self._data[CONF_PORT],
                    CONF_SLAVE_ID: self._data[CONF_SLAVE_ID],  # Standard key
                    "unit": self._data[CONF_SLAVE_ID],  # Legacy compatibility
                    CONF_NAME: self._data.get(CONF_NAME, DEFAULT_NAME),
                },
            )

        # Prepare description with device info
        device_name = self._device_info.get("device_name", "Unknown")
        firmware_version = self._device_info.get("firmware", "Unknown")
        serial_number = self._device_info.get("serial_number", "Unknown")

        # Get scan statistics
        available_registers = self._scan_result.get("available_registers", {})
        capabilities = self._scan_result.get("capabilities", {})

        register_count = sum(len(regs) for regs in available_registers.values())

        capabilities_list = [k.replace("_", " ").title() for k, v in capabilities.items() if v]

        scan_success_rate = "100%" if register_count > 0 else "0%"

        description_placeholders = {
            "host": self._data[CONF_HOST],
            "port": str(self._data[CONF_PORT]),
            "slave_id": str(self._data[CONF_SLAVE_ID]),
            "device_name": device_name,
            "firmware_version": firmware_version,
            "serial_number": serial_number,
            "register_count": str(register_count),
            "scan_success_rate": scan_success_rate,
            "capabilities_count": str(len(capabilities_list)),
            "capabilities_list": ", ".join(capabilities_list) if capabilities_list else "None",
            "auto_detected_note": (
                "Auto-detection successful!"
                if register_count > 0
                else "Limited auto-detection"
            ),
        }

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=description_placeholders,
        )


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ThesslaGreen Modbus."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle options flow."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        current_timeout = self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        current_retry = self.config_entry.options.get(CONF_RETRY, DEFAULT_RETRY)
        force_full = self.config_entry.options.get(CONF_FORCE_FULL_REGISTER_LIST, False)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current_scan_interval,
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                vol.Optional(
                    CONF_TIMEOUT,
                    default=current_timeout,
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Optional(
                    CONF_RETRY,
                    default=current_retry,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
                vol.Optional(
                    CONF_FORCE_FULL_REGISTER_LIST,
                    default=force_full,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            description_placeholders={
                "current_scan_interval": str(current_scan_interval),
                "current_timeout": str(current_timeout),
                "current_retry": str(current_retry),
                "force_full_enabled": "Yes" if force_full else "No",
            },
        )
