"""Config flow for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import dataclasses
import ipaddress
import logging
import socket
import traceback
from typing import Any, Awaitable, Callable

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import translation
from homeassistant.util.network import is_host_valid

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
    CONF_MAX_REGISTERS_PER_REQUEST,
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
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DOMAIN,
)
from .scanner_core import DeviceCapabilities, ThesslaGreenDeviceScanner
from .modbus_exceptions import (
    ConnectionException,
    ModbusException,
    ModbusIOException,
)

_LOGGER = logging.getLogger(__name__)

# Delay between retries when establishing the connection during the config flow.
# Uses exponential backoff: ``backoff * 2 ** (attempt-1)``.
CONFIG_FLOW_BACKOFF = 0.1


async def _run_with_retry(
    func: "Callable[[], Awaitable[Any]]",
    *,
    retries: int,
    backoff: float,
) -> Any:
    """Execute ``func`` with retry and backoff.

    Retries are attempted for connection and Modbus related exceptions. The
    final exception is raised if all attempts fail.
    """

    for attempt in range(1, retries + 1):
        try:
            return await func()
        except (
            ConnectionException,
            ModbusIOException,
            ModbusException,
            asyncio.TimeoutError,
            OSError,
        ):
            if attempt >= retries:
                raise
            delay = backoff * 2 ** (attempt - 1)
            if delay:
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    _LOGGER.debug("Retry sleep cancelled")
                    raise
    # Should never reach here
    raise RuntimeError("Retry wrapper failed without raising")


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


async def validate_input(
    _hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    slave_id = data[CONF_SLAVE_ID]
    name = data.get(CONF_NAME, DEFAULT_NAME)
    timeout = data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    # Validate port and slave id ranges
    if not 1 <= port <= 65535:
        raise vol.Invalid("invalid_port", path=[CONF_PORT])
    if slave_id < 1:
        raise vol.Invalid("invalid_slave_low", path=[CONF_SLAVE_ID])
    if slave_id > 247:
        raise vol.Invalid("invalid_slave_high", path=[CONF_SLAVE_ID])

    # Validate host is either an IP address or a valid hostname
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not is_host_valid(host):
            raise vol.Invalid("invalid_host", path=[CONF_HOST])

    scanner: ThesslaGreenDeviceScanner | None = None
    try:
        scanner = await _run_with_retry(
            lambda: ThesslaGreenDeviceScanner.create(
                host=host,
                port=port,
                slave_id=slave_id,
                timeout=timeout,
                retry=DEFAULT_RETRY,
                backoff=CONFIG_FLOW_BACKOFF,
                deep_scan=data.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN),
            ),
            retries=DEFAULT_RETRY,
            backoff=CONFIG_FLOW_BACKOFF,
        )

        # Verify connection by reading a few safe registers
        await _run_with_retry(
            lambda: asyncio.wait_for(
                scanner.verify_connection(), timeout=timeout
            ),
            retries=DEFAULT_RETRY,
            backoff=CONFIG_FLOW_BACKOFF,
        )

        # Perform full device scan
        scan_result = await _run_with_retry(
            lambda: asyncio.wait_for(scanner.scan_device(), timeout=timeout),
            retries=DEFAULT_RETRY,
            backoff=CONFIG_FLOW_BACKOFF,
        )

        caps_obj = scan_result.get("capabilities")
        if caps_obj is None:
            raise CannotConnect("invalid_capabilities")

        if isinstance(caps_obj, DeviceCapabilities):
            required_fields = {
                field.name for field in dataclasses.fields(DeviceCapabilities)
            }
            try:
                caps_dict = caps_obj.as_dict()
            except AttributeError as err:  # pragma: no cover - defensive
                _LOGGER.error("Capabilities missing required fields: %s", err)
                raise CannotConnect("invalid_capabilities") from err
            missing = [f for f in required_fields if f not in caps_dict]
            if missing:
                _LOGGER.error(
                    "Capabilities missing required fields: %s", set(missing)
                )
                raise CannotConnect("invalid_capabilities")
        elif isinstance(caps_obj, dict):
            try:
                caps_dict = DeviceCapabilities(**caps_obj).as_dict()
            except (TypeError, ValueError) as exc:
                _LOGGER.error("Error parsing capabilities: %s", exc)
                raise CannotConnect("invalid_capabilities") from exc
        else:
            raise CannotConnect("invalid_capabilities")

        # Store dictionary form of capabilities for serialization
        scan_result["capabilities"] = caps_dict

        if not scan_result:
            raise CannotConnect("Device scan failed - no data received")

        device_info = scan_result.get("device_info", {})

        # Return validated data with device info
        return {
            "title": name,
            "device_info": device_info,
            "scan_result": scan_result,
        }

    except ConnectionException as exc:
        _LOGGER.error("Connection error: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("cannot_connect") from exc
    except ModbusIOException as exc:
        _LOGGER.error("Modbus IO error during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("timeout") from exc
    except asyncio.TimeoutError as exc:
        _LOGGER.error("Timeout during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("timeout") from exc
    except ModbusException as exc:
        _LOGGER.error("Modbus error: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("modbus_error") from exc
    except AttributeError as exc:
        _LOGGER.error("Attribute error during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        # Provide a more helpful message when scanner methods are missing
        raise CannotConnect("missing_method") from exc
    except OSError as exc:
        if isinstance(exc, socket.gaierror):
            _LOGGER.error("DNS resolution failed: %s", exc)
            _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
            raise CannotConnect("dns_failure") from exc
        if isinstance(exc, ConnectionRefusedError):
            _LOGGER.error("Connection refused: %s", exc)
            _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
            raise CannotConnect("connection_refused") from exc
        _LOGGER.error("Unexpected error during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("cannot_connect") from exc
    finally:
        if hasattr(scanner, "close"):
            await scanner.close()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for ThesslaGreen Modbus."""

    VERSION = 2  # Used by Home Assistant to manage config entry migrations  # pragma: no cover

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}
        self._device_info: dict[str, Any] = {}
        self._scan_result: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:  # pragma: no cover
        """Handle the initial step.

        Part of the Home Assistant config flow interface; the framework
        calls this method directly.
        """
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
            except vol.Invalid as err:
                _LOGGER.error(
                    "Invalid input for %s: %s",
                    err.path[0] if err.path else "unknown",
                    err,
                )
                errors[err.path[0] if err.path else CONF_HOST] = (
                    err.error_message
                )
            except (ConnectionException, ModbusException):
                _LOGGER.exception("Modbus communication error")
                errors["base"] = "cannot_connect"
            except ValueError as err:
                _LOGGER.error("Invalid value provided: %s", err)
                errors["base"] = "invalid_input"
            except KeyError as err:
                _LOGGER.error("Missing required data: %s", err)
                errors["base"] = "invalid_input"
            else:
                self._abort_if_unique_id_configured()
                # Show confirmation step with device info
                return await self.async_step_confirm()

        # Show form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
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

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirm step."""
        if user_input is not None:
            # Ensure unique ID is set and not already configured
            unique_host = self._data[CONF_HOST].replace(":", "-")
            await self.async_set_unique_id(
                f"{unique_host}:{self._data[CONF_PORT]}:{self._data[CONF_SLAVE_ID]}"
            )
            self._abort_if_unique_id_configured()
            # Prepare capabilities for persistence
            caps_obj = self._scan_result.get("capabilities")
            if isinstance(caps_obj, dict):
                try:
                    caps_dict = DeviceCapabilities(**caps_obj).as_dict()
                except (TypeError, ValueError):
                    caps_dict = DeviceCapabilities().as_dict()
            elif isinstance(caps_obj, DeviceCapabilities):
                caps_dict = caps_obj.as_dict()
            else:
                caps_dict = DeviceCapabilities().as_dict()

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
                    "capabilities": caps_dict,
                },
                options={
                    CONF_DEEP_SCAN: self._data.get(
                        CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN
                    )
                },
            )

        # Prepare description with device info
        device_name = self._device_info.get("device_name", "Unknown")
        firmware_version = self._device_info.get("firmware", "Unknown")
        serial_number = self._device_info.get("serial_number", "Unknown")

        # Get scan statistics
        available_registers = self._scan_result.get("available_registers", {})
        caps_obj = self._scan_result.get("capabilities")
        if isinstance(caps_obj, dict):
            try:
                caps_data = DeviceCapabilities(**caps_obj)
            except TypeError:
                caps_data = DeviceCapabilities()
        elif isinstance(caps_obj, DeviceCapabilities):
            caps_data = caps_obj
        else:
            caps_data = DeviceCapabilities()

        register_count = self._scan_result.get(
            "register_count",
            sum(len(regs) for regs in available_registers.values()),
        )

        capabilities_list = [
            field.name.replace("_", " ").title()
            for field in dataclasses.fields(DeviceCapabilities)
            if field.type in (bool, "bool") and getattr(caps_data, field.name)
        ]

        scan_success_rate = "100%" if register_count > 0 else "0%"

        language = getattr(
            getattr(self.hass, "config", None), "language", "en"
        )
        translations: dict[str, str] = {}
        try:
            translations = await translation.async_get_translations(
                self.hass, language, "component", [DOMAIN]
            )
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.debug("Translation load failed: %s", err)

        key = (
            "auto_detected_note_success"
            if register_count > 0
            else "auto_detected_note_limited"
        )
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
            "capabilities_list": ", ".join(capabilities_list)
            if capabilities_list
            else "None",
            "auto_detected_note": auto_detected_note,
        }

        return self.async_show_form(
            step_id="confirm",
            description_placeholders=description_placeholders,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:  # pragma: no cover
        """Return the options flow handler.

        Home Assistant looks up this function by name when launching the
        options UI, so it must remain even if unreferenced here.
        """
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ThesslaGreen Modbus."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:  # pragma: no cover
        """Handle options flow.

        This is the entry point for the options dialog and is invoked by
        Home Assistant.
        """

        errors: dict[str, str] = {}
        if user_input is not None:
            max_regs = user_input.get(
                CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
            )
            if max_regs < 1:
                errors[CONF_MAX_REGISTERS_PER_REQUEST] = (
                    "invalid_max_registers_per_request"
                )
            else:
                user_input = dict(user_input)
                user_input[CONF_MAX_REGISTERS_PER_REQUEST] = min(
                    max_regs, DEFAULT_MAX_REGISTERS_PER_REQUEST
                )
                return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        current_timeout = self.config_entry.options.get(
            CONF_TIMEOUT, DEFAULT_TIMEOUT
        )
        current_retry = self.config_entry.options.get(
            CONF_RETRY, DEFAULT_RETRY
        )
        force_full = self.config_entry.options.get(
            CONF_FORCE_FULL_REGISTER_LIST, False
        )
        current_scan_uart = self.config_entry.options.get(
            CONF_SCAN_UART_SETTINGS, DEFAULT_SCAN_UART_SETTINGS
        )
        current_skip_missing = self.config_entry.options.get(
            CONF_SKIP_MISSING_REGISTERS, DEFAULT_SKIP_MISSING_REGISTERS
        )
        current_airflow_unit = self.config_entry.options.get(
            CONF_AIRFLOW_UNIT, DEFAULT_AIRFLOW_UNIT
        )
        current_deep_scan = self.config_entry.options.get(
            CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN
        )
        current_max_registers_per_request = self.config_entry.options.get(
            CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
        )

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
                vol.Optional(
                    CONF_MAX_REGISTERS_PER_REQUEST,
                    default=current_max_registers_per_request,
                    description={"advanced": True},
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=125)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "current_scan_interval": str(current_scan_interval),
                "current_timeout": str(current_timeout),
                "current_retry": str(current_retry),
                "force_full_enabled": "Yes" if force_full else "No",
                "scan_uart_enabled": "Yes" if current_scan_uart else "No",
                "skip_missing_enabled": "Yes" if current_skip_missing else "No",
                "current_airflow_unit": current_airflow_unit,
                "deep_scan_enabled": "Yes" if current_deep_scan else "No",
                "current_max_registers_per_request": str(
                    current_max_registers_per_request
                ),
            },
        )
