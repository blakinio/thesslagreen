"""Config flow for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import logging
import traceback
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import translation

from .const import (
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_RETRY,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_UART_SETTINGS,
    CONF_SKIP_MISSING_REGISTERS,
    CONF_SLAVE_ID,
    CONF_TIMEOUT,
    CONF_AIRFLOW_UNIT,
    CONF_DEEP_SCAN,
    AIRFLOW_UNIT_M3H,
    AIRFLOW_UNIT_PERCENTAGE,
    DEFAULT_AIRFLOW_UNIT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RETRY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SKIP_MISSING_REGISTERS,
    DEFAULT_SLAVE_ID,
    DEFAULT_TIMEOUT,
    DEFAULT_DEEP_SCAN,
    DOMAIN,
)
from .device_scanner import ThesslaGreenDeviceScanner
from .modbus_exceptions import ConnectionException, ModbusException

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
    scanner = await ThesslaGreenDeviceScanner.create(
        host=host,
        port=port,
        slave_id=slave_id,
        timeout=DEFAULT_TIMEOUT,
        retry=DEFAULT_RETRY,
        deep_scan=data.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN),
    )

    try:
        scan_result = await scanner.scan_device()

        if not scan_result:
            raise CannotConnect("Device scan failed - no data received")

        device_info = scan_result.get("device_info", {})

        # Return validated data with device info
        return {"title": name, "device_info": device_info, "scan_result": scan_result}

    except ConnectionException as exc:
        _LOGGER.error("Connection error: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect from exc
    except ModbusException as exc:
        _LOGGER.error("Modbus error: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect from exc
    except AttributeError as exc:
        _LOGGER.error("Attribute error during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        # Provide a more helpful message when scanner methods are missing
        raise CannotConnect("missing_method") from exc
    except (OSError, asyncio.TimeoutError) as exc:
        _LOGGER.error("Unexpected error during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect from exc
    finally:
        if hasattr(scanner, "close"):
            await scanner.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for ThesslaGreen Modbus."""

    VERSION = 2

    def __init__(self) -> None:
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
                # Replace colons in host (IPv6) with hyphens to avoid separator conflicts
                unique_host = user_input[CONF_HOST].replace(":", "-")
                await self.async_set_unique_id(
                    f"{unique_host}:{user_input[CONF_PORT]}:{user_input[CONF_SLAVE_ID]}"
                )

            except CannotConnect as exc:
                errors["base"] = exc.args[0] if exc.args else "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except (ConnectionException, ModbusException):
                _LOGGER.exception("Modbus communication error")
                errors["base"] = "cannot_connect"
            except ValueError as err:
                _LOGGER.error("Invalid value provided: %s", err)
                errors["base"] = "invalid_input"
            except KeyError as err:
                _LOGGER.error("Missing required data: %s", err)
                errors["base"] = "invalid_input"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during configuration: %s", err)
                raise
            else:
                self._abort_if_unique_id_configured()
                # Show confirmation step with device info
                return await self.async_step_confirm()

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=247)
                ),
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(
                    CONF_DEEP_SCAN,
                    default=DEFAULT_DEEP_SCAN,
                    description={"advanced": True},
                ): bool,
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
            # Ensure unique ID is set and not already configured
            unique_host = self._data[CONF_HOST].replace(":", "-")
            await self.async_set_unique_id(
                f"{unique_host}:{self._data[CONF_PORT]}:{self._data[CONF_SLAVE_ID]}"
            )
            self._abort_if_unique_id_configured()
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
                options={CONF_DEEP_SCAN: self._data.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN)},
            )

        # Prepare description with device info
        device_name = self._device_info.get("device_name", "Unknown")
        firmware_version = self._device_info.get("firmware", "Unknown")
        serial_number = self._device_info.get("serial_number", "Unknown")

        # Get scan statistics
        available_registers = self._scan_result.get("available_registers", {})
        capabilities = self._scan_result.get("capabilities", {})

        register_count = self._scan_result.get(
            "register_count",
            sum(len(regs) for regs in available_registers.values()),
        )

        capabilities_list = [k.replace("_", " ").title() for k, v in capabilities.items() if v]

        scan_success_rate = "100%" if register_count > 0 else "0%"

        language = getattr(getattr(self.hass, "config", None), "language", "en")
        translations: dict[str, str] = {}
        try:
            translations = await translation.async_get_translations(
                self.hass, language, "component", [DOMAIN]
            )
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.debug("Translation load failed: %s", err)

        key = "auto_detected_note_success" if register_count > 0 else "auto_detected_note_limited"
        auto_detected_note = translations.get(
            f"component.{DOMAIN}.{key}",
            (
                "Auto-detection successful!"
                if register_count > 0
                else "Limited auto-detection - some registers may be missing."
            ),
        )

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
            "auto_detected_note": auto_detected_note,
        }

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=description_placeholders,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return OptionsFlow(config_entry)


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
        current_scan_uart = self.config_entry.options.get(
            CONF_SCAN_UART_SETTINGS, DEFAULT_SCAN_UART_SETTINGS
        )
        current_skip_missing = self.config_entry.options.get(
            CONF_SKIP_MISSING_REGISTERS, DEFAULT_SKIP_MISSING_REGISTERS
        )
        current_airflow_unit = self.config_entry.options.get(
            CONF_AIRFLOW_UNIT, DEFAULT_AIRFLOW_UNIT
        )
        current_deep_scan = self.config_entry.options.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN)

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
                vol.Optional(
                    CONF_SCAN_UART_SETTINGS,
                    default=current_scan_uart,
                ): bool,
                vol.Optional(
                    CONF_SKIP_MISSING_REGISTERS,
                    default=current_skip_missing,
                ): bool,
                vol.Optional(
                    CONF_AIRFLOW_UNIT,
                    default=current_airflow_unit,
                ): vol.In([AIRFLOW_UNIT_M3H, AIRFLOW_UNIT_PERCENTAGE]),
                vol.Optional(
                    CONF_DEEP_SCAN,
                    default=current_deep_scan,
                    description={"advanced": True},
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
                "scan_uart_enabled": "Yes" if current_scan_uart else "No",
                "skip_missing_enabled": "Yes" if current_skip_missing else "No",
                "current_airflow_unit": current_airflow_unit,
                "deep_scan_enabled": "Yes" if current_deep_scan else "No",
            },
        )
