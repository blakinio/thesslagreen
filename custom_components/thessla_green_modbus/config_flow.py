"""Config flow for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import dataclasses
import ipaddress
import logging
import socket
import traceback
from collections.abc import Awaitable, Callable
from importlib import import_module
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import translation
from homeassistant.util.network import is_host_valid

from .const import (
    AIRFLOW_UNIT_M3H,
    AIRFLOW_UNIT_PERCENTAGE,
    CONF_AIRFLOW_UNIT,
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_DEEP_SCAN,
    CONF_ENABLE_DEVICE_SCAN,
    CONF_FORCE_FULL_REGISTER_LIST,
    CONF_LOG_LEVEL,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_PARITY,
    CONF_RETRY,
    CONF_SAFE_SCAN,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_UART_SETTINGS,
    CONF_SERIAL_PORT,
    CONF_SKIP_MISSING_REGISTERS,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONF_TIMEOUT,
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    CONNECTION_TYPE_TCP_RTU,
    DEFAULT_AIRFLOW_UNIT,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_DEEP_SCAN,
    DEFAULT_ENABLE_DEVICE_SCAN,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_RETRY,
    DEFAULT_SAFE_SCAN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_SKIP_MISSING_REGISTERS,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOP_BITS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_BATCH_REGISTERS,
    MODBUS_BAUD_RATES,
    MODBUS_PARITY,
    MODBUS_STOP_BITS,
)
from .errors import CannotConnect, InvalidAuth, is_invalid_auth_error
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .utils import resolve_connection_settings

_LOGGER = logging.getLogger(__name__)


def _is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Return True when a modbus IO error indicates a cancelled request."""
    message = str(exc).lower()
    return "request cancelled" in message or "cancelled" in message


ThesslaGreenDeviceScanner: Any | None = None
DeviceCapabilities: Any | None = None

# Delay between retries when establishing the connection during the config flow.
# Uses exponential backoff: ``backoff * 2 ** (attempt-1)``.
CONFIG_FLOW_BACKOFF = 0.1


def _strip_translation_prefix(value: str) -> str:
    """Remove integration/domain prefixes from option strings."""
    if value.startswith(f"{DOMAIN}."):
        value = value.split(".", 1)[1]
    return value


def _normalize_baud_rate(value: Any) -> int:
    """Normalize a Modbus baud rate option to an integer."""
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("invalid_baud_rate")
        return value
    if not isinstance(value, str):
        raise ValueError("invalid_baud_rate")
    option = _strip_translation_prefix(value.strip())
    if option.startswith("modbus_baud_rate_"):
        option = option[len("modbus_baud_rate_") :]
    try:
        baud = int(option)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_baud_rate") from exc
    if baud <= 0:
        raise ValueError("invalid_baud_rate")
    return baud


def _normalize_parity(value: Any) -> str:
    """Normalize a Modbus parity option to a canonical string."""
    if not isinstance(value, str):
        if value is None:
            raise ValueError("invalid_parity")
        value = str(value)
    option = _strip_translation_prefix(value.strip().lower())
    if option.startswith("modbus_parity_"):
        option = option[len("modbus_parity_") :]
    if option not in {"none", "even", "odd"}:
        raise ValueError("invalid_parity")
    return option


def _normalize_stop_bits(value: Any) -> int:
    """Normalize a Modbus stop bits option to an integer."""
    if isinstance(value, int):
        stop_bits = value
    else:
        if not isinstance(value, str):
            raise ValueError("invalid_stop_bits")
        option = _strip_translation_prefix(value.strip())
        if option.startswith("modbus_stop_bits_"):
            option = option[len("modbus_stop_bits_") :]
        try:
            stop_bits = int(option)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_stop_bits") from exc
    if stop_bits not in (1, 2):
        raise ValueError("invalid_stop_bits")
    return stop_bits


def _denormalize_option(prefix: str, value: Any | None) -> Any | None:
    """Convert a normalized option back to its translation key."""
    if value is None:
        return None
    if isinstance(value, str) and value.startswith(f"{DOMAIN}."):
        return value
    return f"{DOMAIN}.{prefix}{value}"


def _looks_like_hostname(value: str) -> bool:
    """Basic hostname validation for environments without network helpers."""
    if not value:
        return False
    if any(char.isspace() for char in value):
        return False
    if value.replace(".", "").isdigit():
        return False
    if value.startswith("-") or value.endswith("-"):
        return False
    return "." in value


async def _run_with_retry(
    func: Callable[[], Awaitable[Any]],
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
        except asyncio.CancelledError:
            raise
        except ModbusIOException as exc:
            if _is_request_cancelled_error(exc):
                raise TimeoutError("Modbus request cancelled") from exc
            if attempt >= retries:
                raise
            delay = backoff * 2 ** (attempt - 1)
            if delay:
                await asyncio.sleep(delay)
        except (TimeoutError, ConnectionException, ModbusException, OSError):
            if attempt >= retries:
                raise
            delay = backoff * 2 ** (attempt - 1)
            if delay:
                await asyncio.sleep(delay)

    raise RuntimeError("Retry wrapper failed without raising")


def _caps_to_dict(obj: Any) -> dict[str, Any]:
    """Return a JSON-serializable dict from a capabilities object."""
    if dataclasses.is_dataclass(obj):
        if hasattr(obj, "as_dict"):
            data = dict(obj.as_dict())
        else:
            data = dataclasses.asdict(obj)
    elif hasattr(obj, "as_dict"):
        data = obj.as_dict()
    elif isinstance(obj, dict):
        data = dict(obj)
    else:
        data = {k: v for k, v in getattr(obj, "__dict__", {}).items()}

    for key, value in list(data.items()):
        if isinstance(value, set):
            data[key] = sorted(value)
    return data


async def validate_input(hass: HomeAssistant | None, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    if connection_type not in (
        CONNECTION_TYPE_TCP,
        CONNECTION_TYPE_TCP_RTU,
        CONNECTION_TYPE_RTU,
    ):
        raise vol.Invalid("invalid_transport", path=[CONF_CONNECTION_TYPE])

    # Normalize: TCP_RTU is stored as TCP + connection_mode=TCP_RTU
    if connection_type == CONNECTION_TYPE_TCP_RTU:
        data[CONF_CONNECTION_TYPE] = CONNECTION_TYPE_TCP
        data[CONF_CONNECTION_MODE] = CONNECTION_MODE_TCP_RTU
        connection_type = CONNECTION_TYPE_TCP
    elif connection_type == CONNECTION_TYPE_TCP:
        data[CONF_CONNECTION_TYPE] = CONNECTION_TYPE_TCP
        data.pop(CONF_CONNECTION_MODE, None)
        connection_type = CONNECTION_TYPE_TCP
    else:
        data[CONF_CONNECTION_TYPE] = CONNECTION_TYPE_RTU
        data.pop(CONF_CONNECTION_MODE, None)
        connection_type = CONNECTION_TYPE_RTU

    try:
        slave_id = int(data[CONF_SLAVE_ID])
    except (KeyError, TypeError, ValueError) as exc:
        raise vol.Invalid("invalid_slave", path=[CONF_SLAVE_ID]) from exc
    if slave_id < 1:
        raise vol.Invalid("invalid_slave_low", path=[CONF_SLAVE_ID])
    if slave_id > 247:
        raise vol.Invalid("invalid_slave_high", path=[CONF_SLAVE_ID])
    data[CONF_SLAVE_ID] = slave_id

    name = data.get(CONF_NAME, DEFAULT_NAME)
    timeout = data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    host = ""
    port = DEFAULT_PORT

    if connection_type == CONNECTION_TYPE_TCP:
        host = str(data.get(CONF_HOST, "") or "").strip()
        port_raw = data.get(CONF_PORT, DEFAULT_PORT)
        try:
            port = int(port_raw)
        except (TypeError, ValueError) as exc:
            raise vol.Invalid("invalid_port", path=[CONF_PORT]) from exc
        if not host:
            raise vol.Invalid("missing_host", path=[CONF_HOST])
        data[CONF_HOST] = host
        if not 1 <= port <= 65535:
            raise vol.Invalid("invalid_port", path=[CONF_PORT])
        data[CONF_PORT] = port

        # Validate host is either an IP address or a valid hostname
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not _looks_like_hostname(host):
                raise vol.Invalid("invalid_host", path=[CONF_HOST]) from None
            if not is_host_valid(host):
                raise vol.Invalid("invalid_host", path=[CONF_HOST]) from None

        data.pop(CONF_SERIAL_PORT, None)
        data.pop(CONF_BAUD_RATE, None)
        data.pop(CONF_PARITY, None)
        data.pop(CONF_STOP_BITS, None)

    else:
        serial_port = str(data.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT) or "").strip()
        if not serial_port:
            raise vol.Invalid("invalid_serial_port", path=[CONF_SERIAL_PORT])
        data[CONF_SERIAL_PORT] = serial_port

        try:
            baud_rate = _normalize_baud_rate(data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE))
        except ValueError as err:
            raise vol.Invalid("invalid_baud_rate", path=[CONF_BAUD_RATE]) from err
        data[CONF_BAUD_RATE] = baud_rate

        try:
            parity = _normalize_parity(data.get(CONF_PARITY, DEFAULT_PARITY))
        except ValueError as err:
            raise vol.Invalid("invalid_parity", path=[CONF_PARITY]) from err
        data[CONF_PARITY] = parity

        try:
            stop_bits = _normalize_stop_bits(data.get(CONF_STOP_BITS, DEFAULT_STOP_BITS))
        except ValueError as err:
            raise vol.Invalid("invalid_stop_bits", path=[CONF_STOP_BITS]) from err
        data[CONF_STOP_BITS] = stop_bits

        data.pop(CONF_HOST, None)
        data.pop(CONF_PORT, None)

    import_func: Callable[..., Awaitable[Any]]
    import_func = hass.async_add_executor_job if hass else asyncio.to_thread

    module = await import_func(import_module, "custom_components.thessla_green_modbus.scanner_core")
    scanner_cls = ThesslaGreenDeviceScanner or module.ThesslaGreenDeviceScanner
    capabilities_cls = DeviceCapabilities or module.DeviceCapabilities

    scanner: Any | None = None
    try:
        scanner = await _run_with_retry(
            lambda: scanner_cls.create(
                host=host,
                port=port,
                slave_id=slave_id,
                timeout=timeout,
                retry=DEFAULT_RETRY,
                backoff=CONFIG_FLOW_BACKOFF,
                deep_scan=data.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN),
                connection_type=connection_type,
                connection_mode=data.get(CONF_CONNECTION_MODE),
                serial_port=data.get(CONF_SERIAL_PORT),
                baud_rate=data.get(CONF_BAUD_RATE),
                parity=data.get(CONF_PARITY, DEFAULT_PARITY),
                stop_bits=data.get(CONF_STOP_BITS, DEFAULT_STOP_BITS),
                hass=hass,
            ),
            retries=DEFAULT_RETRY,
            backoff=CONFIG_FLOW_BACKOFF,
        )

        short_timeout = max(2, timeout)

        # Verify connection by reading a few safe registers
        await _run_with_retry(
            lambda: asyncio.wait_for(scanner.verify_connection(), timeout=short_timeout),
            retries=DEFAULT_RETRY,
            backoff=CONFIG_FLOW_BACKOFF,
        )

        # Perform full device scan
        scan_result = await _run_with_retry(
            lambda: asyncio.wait_for(scanner.scan_device(), timeout=timeout),
            retries=DEFAULT_RETRY,
            backoff=CONFIG_FLOW_BACKOFF,
        )

        if not isinstance(scan_result, dict) or not scan_result:
            raise CannotConnect("invalid_format")

        caps_obj = scan_result.get("capabilities")
        if caps_obj is None:
            raise CannotConnect("invalid_capabilities")

        if dataclasses.is_dataclass(caps_obj):
            try:
                caps_dict = _caps_to_dict(caps_obj)
            except (TypeError, ValueError, AttributeError) as err:
                _LOGGER.error("Capabilities missing required fields: %s", err)
                raise CannotConnect("invalid_capabilities") from err
            if isinstance(caps_obj, capabilities_cls):
                required_fields = {field.name for field in dataclasses.fields(capabilities_cls)}
                missing = [f for f in required_fields if f not in caps_dict]
                if missing:
                    _LOGGER.error("Capabilities missing required fields: %s", set(missing))
                    raise CannotConnect("invalid_capabilities")
        elif isinstance(caps_obj, dict):
            try:
                caps_dict = _caps_to_dict(capabilities_cls(**caps_obj))
            except (TypeError, ValueError) as exc:
                _LOGGER.error("Error parsing capabilities: %s", exc)
                raise CannotConnect("invalid_capabilities") from exc
        else:
            raise CannotConnect("invalid_capabilities")

        # Store dictionary form of capabilities for serialization
        scan_result["capabilities"] = caps_dict
        device_info = scan_result.get("device_info", {})

        return {
            "title": name,
            "device_info": device_info,
            "scan_result": scan_result,
        }

    except ConnectionException as exc:
        _LOGGER.error("Connection error: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("cannot_connect") from exc
    except asyncio.CancelledError:
        raise
    except ModbusIOException as exc:
        if _is_request_cancelled_error(exc):
            _LOGGER.info("Modbus request cancelled during device validation.")
            raise CannotConnect("timeout") from exc
        _LOGGER.error("Modbus IO error during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("io_error") from exc
    except (TimeoutError, asyncio.TimeoutError) as exc:
        _LOGGER.warning("Timeout during device validation: %s", exc)
        if "modbus request cancelled" not in str(exc).lower():
            _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("timeout") from exc
    except ModbusException as exc:
        _LOGGER.error("Modbus error: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        if is_invalid_auth_error(exc):
            raise InvalidAuth from exc
        raise CannotConnect("modbus_error") from exc
    except AttributeError as exc:
        _LOGGER.error("Attribute error during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
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

    VERSION = 4  # pragma: no cover

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}
        self._device_info: dict[str, Any] = {}
        self._scan_result: dict[str, Any] = {}
        self._tg_flow_reauth_entry_id: str | None = None
        self._tg_flow_reauth_existing_data: dict[str, Any] = {}

    def _build_connection_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        """Return schema for connection details with provided defaults."""
        current_values = defaults or {}

        def _option_default(prefix: str, options: list[Any], value: Any, fallback: Any) -> Any:
            target = value if value not in (None, "") else fallback
            candidate = _denormalize_option(prefix, target)
            if options and candidate in options:
                return candidate
            if options:
                return options[0]
            return target

        connection_default = current_values.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        host_default = current_values.get(CONF_HOST, "")
        port_default = current_values.get(CONF_PORT, DEFAULT_PORT)
        slave_default = current_values.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
        connection_mode_default = current_values.get(CONF_CONNECTION_MODE)

        normalized_type, resolved_mode = resolve_connection_settings(
            connection_default, connection_mode_default, port_default
        )
        if normalized_type == CONNECTION_TYPE_TCP and resolved_mode == CONNECTION_MODE_TCP_RTU:
            connection_default = CONNECTION_TYPE_TCP_RTU
        else:
            connection_default = normalized_type

        serial_port_default = current_values.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT)

        baud_default = _option_default(
            "modbus_baud_rate_",
            MODBUS_BAUD_RATES,
            current_values.get(CONF_BAUD_RATE),
            DEFAULT_BAUD_RATE,
        )
        parity_default = _option_default(
            "modbus_parity_",
            MODBUS_PARITY,
            current_values.get(CONF_PARITY),
            DEFAULT_PARITY,
        )
        stop_bits_default = _option_default(
            "modbus_stop_bits_",
            MODBUS_STOP_BITS,
            current_values.get(CONF_STOP_BITS),
            DEFAULT_STOP_BITS,
        )

        if not MODBUS_BAUD_RATES:
            try:
                baud_default = int(baud_default)
            except (TypeError, ValueError):
                baud_default = DEFAULT_BAUD_RATE
        if not MODBUS_PARITY:
            parity_default = str(parity_default)
        if not MODBUS_STOP_BITS:
            stop_bits_default = str(stop_bits_default)

        baud_validator: Any = (
            vol.In(MODBUS_BAUD_RATES)
            if MODBUS_BAUD_RATES
            else vol.All(vol.Coerce(int), vol.Range(min=1200, max=230400))
        )
        parity_validator: Any = (
            vol.In(MODBUS_PARITY) if MODBUS_PARITY else vol.In(["none", "even", "odd"])
        )
        stop_bits_validator: Any = (
            vol.In(MODBUS_STOP_BITS) if MODBUS_STOP_BITS else vol.In(["1", "2"])
        )

        data_schema: dict[Any, Any] = {
            vol.Required(
                CONF_CONNECTION_TYPE,
                default=connection_default,
                description={
                    "selector": {
                        "select": {
                            "options": [
                                {
                                    "value": CONNECTION_TYPE_TCP,
                                    "label": f"{DOMAIN}.connection_type_tcp",
                                },
                                {
                                    "value": CONNECTION_TYPE_TCP_RTU,
                                    "label": f"{DOMAIN}.connection_type_tcp_rtu",
                                },
                                {
                                    "value": CONNECTION_TYPE_RTU,
                                    "label": f"{DOMAIN}.connection_type_rtu",
                                },
                            ]
                        }
                    }
                },
            ): vol.In({CONNECTION_TYPE_TCP, CONNECTION_TYPE_TCP_RTU, CONNECTION_TYPE_RTU}),
            vol.Required(CONF_SLAVE_ID, default=slave_default): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=247)
            ),
            vol.Optional(CONF_NAME, default=current_values.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Optional(
                CONF_DEEP_SCAN,
                default=current_values.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN),
                description={"advanced": True},
            ): bool,
            vol.Optional(
                CONF_MAX_REGISTERS_PER_REQUEST,
                default=current_values.get(
                    CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
                ),
                description={
                    "selector": {
                        "number": {"min": 1, "max": MAX_BATCH_REGISTERS, "step": 1}
                    }
                },
            ): int,
        }

        if connection_default in (CONNECTION_TYPE_TCP, CONNECTION_TYPE_TCP_RTU):
            data_schema.update(
                {
                    vol.Required(CONF_HOST, default=host_default): str,
                    vol.Required(CONF_PORT, default=port_default): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            )
        else:
            data_schema.update(
                {
                    vol.Required(CONF_SERIAL_PORT, default=serial_port_default): str,
                    vol.Required(CONF_BAUD_RATE, default=baud_default): baud_validator,
                    vol.Required(CONF_PARITY, default=parity_default): parity_validator,
                    vol.Required(CONF_STOP_BITS, default=stop_bits_default): stop_bits_validator,
                }
            )

        return vol.Schema(data_schema)

    @staticmethod
    def _build_unique_id(data: dict[str, Any]) -> str:
        """Generate a unique identifier for the config entry."""
        connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        slave_id = data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)

        if connection_type == CONNECTION_TYPE_RTU:
            serial_port = str(data.get(CONF_SERIAL_PORT, ""))
            identifier = serial_port or "serial"
            sanitized = identifier.replace(":", "-").replace("/", "_")
            return f"{connection_type}:{sanitized}:{slave_id}"

        host = str(data.get(CONF_HOST, ""))
        port = data.get(CONF_PORT, DEFAULT_PORT)
        unique_host = host.replace(":", "-") if host else ""
        return f"{unique_host}:{port}:{slave_id}"

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the confirm step."""
        module = import_module("custom_components.thessla_green_modbus.scanner_core")
        cap_cls = DeviceCapabilities or module.DeviceCapabilities

        if user_input is not None:
            await self.async_set_unique_id(self._build_unique_id(self._data))
            self._abort_if_unique_id_configured()
            entry_data, options = self._prepare_entry_payload(cap_cls)

            return self.async_create_entry(
                title=self._data.get(CONF_NAME, DEFAULT_NAME),
                data=entry_data,
                options=options,
            )

        return await self._async_show_confirmation(cap_cls, "confirm")

    def _prepare_entry_payload(self, cap_cls: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return data and options payloads for the config entry."""
        caps_obj = self._scan_result.get("capabilities")
        if dataclasses.is_dataclass(caps_obj):
            caps_dict = _caps_to_dict(caps_obj)
        elif isinstance(caps_obj, dict):
            try:
                caps_dict = _caps_to_dict(cap_cls(**caps_obj))
            except (TypeError, ValueError):
                caps_dict = _caps_to_dict(cap_cls())
        elif isinstance(caps_obj, cap_cls):
            caps_dict = _caps_to_dict(caps_obj)
        else:
            caps_dict = _caps_to_dict(cap_cls())

        connection_type = self._data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        connection_mode = self._data.get(CONF_CONNECTION_MODE)
        normalized_type, resolved_mode = resolve_connection_settings(
            connection_type, connection_mode, self._data.get(CONF_PORT, DEFAULT_PORT)
        )

        entry_data: dict[str, Any] = {
            CONF_CONNECTION_TYPE: normalized_type,
            CONF_SLAVE_ID: self._data[CONF_SLAVE_ID],
            "unit": self._data[CONF_SLAVE_ID],  # legacy compatibility
            CONF_NAME: self._data.get(CONF_NAME, DEFAULT_NAME),
            "capabilities": caps_dict,
        }

        if normalized_type == CONNECTION_TYPE_TCP:
            entry_data[CONF_HOST] = self._data.get(CONF_HOST, "")
            entry_data[CONF_PORT] = self._data.get(CONF_PORT, DEFAULT_PORT)
            entry_data[CONF_CONNECTION_MODE] = resolved_mode
        else:
            entry_data[CONF_SERIAL_PORT] = self._data.get(CONF_SERIAL_PORT, "")
            entry_data[CONF_BAUD_RATE] = self._data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)
            entry_data[CONF_PARITY] = self._data.get(CONF_PARITY, DEFAULT_PARITY)
            entry_data[CONF_STOP_BITS] = self._data.get(CONF_STOP_BITS, DEFAULT_STOP_BITS)
            if CONF_HOST in self._data:
                entry_data[CONF_HOST] = self._data.get(CONF_HOST, "")
            if CONF_PORT in self._data:
                entry_data[CONF_PORT] = self._data.get(CONF_PORT, DEFAULT_PORT)

        options = {
            CONF_DEEP_SCAN: self._data.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN),
            CONF_MAX_REGISTERS_PER_REQUEST: self._data.get(
                CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
            ),
            CONF_ENABLE_DEVICE_SCAN: self._data.get(
                CONF_ENABLE_DEVICE_SCAN, DEFAULT_ENABLE_DEVICE_SCAN
            ),
            CONF_LOG_LEVEL: DEFAULT_LOG_LEVEL,
        }

        return entry_data, options

    async def _async_show_confirmation(self, cap_cls: Any, step_id: str) -> FlowResult:
        """Render confirmation step with device details."""
        device_name = self._device_info.get("device_name", "Unknown")
        firmware_version = self._device_info.get("firmware", "Unknown")
        serial_number = self._device_info.get("serial_number", "Unknown")

        available_registers = self._scan_result.get("available_registers", {})
        caps_obj = self._scan_result.get("capabilities")
        if dataclasses.is_dataclass(caps_obj):
            try:
                caps_data = cap_cls(**_caps_to_dict(caps_obj))
            except (TypeError, ValueError):
                caps_data = cap_cls()
        elif isinstance(caps_obj, dict):
            try:
                caps_data = cap_cls(**caps_obj)
            except TypeError:
                caps_data = cap_cls()
        elif isinstance(caps_obj, cap_cls):
            caps_data = caps_obj
        else:
            caps_data = cap_cls()

        register_count = self._scan_result.get(
            "register_count",
            sum(len(regs) for regs in available_registers.values()),
        )

        capabilities_list = [
            field.name.replace("_", " ").title()
            for field in dataclasses.fields(cap_cls)
            if field.type in (bool, "bool") and getattr(caps_data, field.name)
        ]

        scan_success_rate = "100%" if register_count > 0 else "0%"

        language = getattr(getattr(self.hass, "config", None), "language", "en")
        translations: dict[str, str] = {}
        try:
            translations = await translation.async_get_translations(
                self.hass, language, "component", [DOMAIN]
            )
        except (OSError, ValueError, HomeAssistantError) as err:  # pragma: no cover
            _LOGGER.debug("Translation load failed: %s", err)
        except Exception as err:  # pragma: no cover
            _LOGGER.exception("Unexpected error loading translations: %s", err)

        key = "auto_detected_note_success" if register_count > 0 else "auto_detected_note_limited"
        auto_detected_note = translations.get(
            f"component.{DOMAIN}.{key}",
            "Auto-detection successful!"
            if register_count > 0
            else "Limited auto-detection - some registers may be missing.",
        )

        connection_type = self._data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        connection_mode = self._data.get(CONF_CONNECTION_MODE)
        normalized_type, resolved_mode = resolve_connection_settings(
            connection_type, connection_mode, self._data.get(CONF_PORT, DEFAULT_PORT)
        )

        if normalized_type == CONNECTION_TYPE_RTU:
            connection_label = self._data.get(CONF_SERIAL_PORT, "Unknown") or "Unknown"
            host_value = self._data.get(CONF_HOST, "-")
            port_value = str(self._data.get(CONF_PORT, DEFAULT_PORT))
            transport_label = translations.get(
                f"component.{DOMAIN}.connection_type_rtu_label", "Modbus RTU"
            )
        elif resolved_mode == CONNECTION_MODE_TCP_RTU:
            host_value = self._data.get(CONF_HOST, "Unknown")
            port_value = str(self._data.get(CONF_PORT, DEFAULT_PORT))
            connection_label = f"{host_value}:{port_value}"
            transport_label = translations.get(
                f"component.{DOMAIN}.connection_type_tcp_rtu_label", "Modbus TCP RTU"
            )
        else:
            host_value = self._data.get(CONF_HOST, "Unknown")
            port_value = str(self._data.get(CONF_PORT, DEFAULT_PORT))
            connection_label = f"{host_value}:{port_value}"
            transport_label = translations.get(
                f"component.{DOMAIN}.connection_mode_auto_label", "Modbus TCP (Auto)"
            )
            if resolved_mode == CONNECTION_MODE_TCP:
                transport_label = translations.get(
                    f"component.{DOMAIN}.connection_type_tcp_label", "Modbus TCP"
                )

        description_placeholders = {
            "host": host_value,
            "port": port_value,
            "endpoint": connection_label,
            "transport": (resolved_mode or normalized_type).upper(),
            "transport_label": transport_label,
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
            step_id=step_id,
            description_placeholders=description_placeholders,
        )

    async def async_step_user(  # pragma: no cover
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                max_regs = user_input.get(
                    CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
                )
                if not 1 <= max_regs <= MAX_BATCH_REGISTERS:
                    raise vol.Invalid("max_registers_range", path=[CONF_MAX_REGISTERS_PER_REQUEST])

                info = await validate_input(self.hass, user_input)

                self._data = user_input
                self._device_info = info.get("device_info", {})
                self._scan_result = info.get("scan_result", {})

                await self.async_set_unique_id(self._build_unique_id(user_input))

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
                errors[err.path[0] if err.path else CONF_HOST] = err.error_message
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
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_connection_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reauthentication by collecting updated connection details."""
        errors: dict[str, str] = {}
        entry = None

        if self.hass is not None:
            entry_id = self.context.get("entry_id")
            if entry_id:
                entry = self.hass.config_entries.async_get_entry(entry_id)

        defaults: dict[str, Any] = {}
        if entry is not None:
            defaults = {**entry.options, **entry.data}

        if self._tg_flow_reauth_entry_id is None:
            self._tg_flow_reauth_entry_id = entry.entry_id if entry else None
            self._tg_flow_reauth_existing_data = defaults
            return self.async_show_form(
                step_id="reauth",
                data_schema=self._build_connection_schema(defaults),
                errors=errors,
            )

        if user_input is not None:
            try:
                max_regs = user_input.get(
                    CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
                )
                if not 1 <= max_regs <= MAX_BATCH_REGISTERS:
                    raise vol.Invalid("max_registers_range", path=[CONF_MAX_REGISTERS_PER_REQUEST])

                info = await validate_input(self.hass, user_input)
                self._data = user_input
                self._device_info = info.get("device_info", {})
                self._scan_result = info.get("scan_result", {})
                return await self.async_step_reauth_confirm()

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
                errors[err.path[0] if err.path else CONF_HOST] = err.error_message
            except (ConnectionException, ModbusException):
                _LOGGER.exception("Modbus communication error")
                errors["base"] = "cannot_connect"
            except ValueError as err:
                _LOGGER.error("Invalid value provided: %s", err)
                errors["base"] = "invalid_input"
            except KeyError as err:
                _LOGGER.error("Missing required data: %s", err)
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="reauth",
            data_schema=self._build_connection_schema(
                user_input or self._tg_flow_reauth_existing_data
            ),
            errors=errors,
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauthentication details and update the existing entry."""
        module = import_module("custom_components.thessla_green_modbus.scanner_core")
        cap_cls = DeviceCapabilities or module.DeviceCapabilities

        if user_input is not None:
            if self.hass is None or self._tg_flow_reauth_entry_id is None:
                _LOGGER.error("Cannot complete reauth - missing Home Assistant context")
                return self.async_abort(reason="reauth_failed")

            entry = self.hass.config_entries.async_get_entry(self._tg_flow_reauth_entry_id)
            if entry is None:
                _LOGGER.error(
                    "Reauthentication requested for missing entry %s",
                    self._tg_flow_reauth_entry_id,
                )
                return self.async_abort(reason="reauth_entry_missing")

            data, options = self._prepare_entry_payload(cap_cls)
            combined_options = dict(entry.options)
            combined_options.update(options)
            self.hass.config_entries.async_update_entry(entry, data=data, options=combined_options)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return await self._async_show_confirmation(cap_cls, "reauth_confirm")

    @staticmethod
    def async_get_options_flow(  # pragma: no cover
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow handler."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ThesslaGreen Modbus."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(  # pragma: no cover
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            max_regs = user_input.get(
                CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
            )
            if not 1 <= max_regs <= MAX_BATCH_REGISTERS:
                errors[CONF_MAX_REGISTERS_PER_REQUEST] = "max_registers_range"
            else:
                # Merge into existing options (do not wipe other keys)
                entry_options = getattr(self.config_entry, "options", {}) or {}
                merged = dict(entry_options)
                merged.update(dict(user_input))
                return self.async_create_entry(title="", data=merged)

        entry_data = getattr(self.config_entry, "data", {}) or {}
        entry_options = getattr(self.config_entry, "options", {}) or {}

        current_scan_interval = entry_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_timeout = entry_options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        current_retry = entry_options.get(CONF_RETRY, DEFAULT_RETRY)
        force_full = entry_options.get(CONF_FORCE_FULL_REGISTER_LIST, False)
        current_scan_uart = entry_options.get(CONF_SCAN_UART_SETTINGS, DEFAULT_SCAN_UART_SETTINGS)
        current_skip_missing = entry_options.get(
            CONF_SKIP_MISSING_REGISTERS, DEFAULT_SKIP_MISSING_REGISTERS
        )
        current_enable_scan = entry_options.get(CONF_ENABLE_DEVICE_SCAN, DEFAULT_ENABLE_DEVICE_SCAN)
        current_airflow_unit = entry_options.get(CONF_AIRFLOW_UNIT, DEFAULT_AIRFLOW_UNIT)
        current_deep_scan = entry_options.get(CONF_DEEP_SCAN, DEFAULT_DEEP_SCAN)
        current_max_registers_per_request = entry_options.get(
            CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
        )
        current_safe_scan = entry_options.get(CONF_SAFE_SCAN, DEFAULT_SAFE_SCAN)
        current_log_level = entry_options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)

        transport = entry_data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        connection_mode = entry_options.get(
            CONF_CONNECTION_MODE, entry_data.get(CONF_CONNECTION_MODE)
        )
        normalized_type, resolved_mode = resolve_connection_settings(
            transport, connection_mode, entry_data.get(CONF_PORT, DEFAULT_PORT)
        )

        if normalized_type == CONNECTION_TYPE_RTU:
            transport_label = "Modbus RTU"
            serial_port = entry_data.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT)
            baud = entry_data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)
            parity = entry_data.get(CONF_PARITY, DEFAULT_PARITY)
            stop_bits = entry_data.get(CONF_STOP_BITS, DEFAULT_STOP_BITS)
            transport_details = (
                " ("
                f"port: {serial_port or 'n/a'}, baud: {baud}, parity: {parity}, "
                f"stop bits: {stop_bits})"
            )
        elif resolved_mode == CONNECTION_MODE_TCP_RTU:
            transport_label = "Modbus TCP RTU"
            transport_details = ""
        else:
            transport_label = "Modbus TCP"
            if resolved_mode == CONNECTION_MODE_AUTO:
                transport_label = "Modbus TCP (Auto)"
            transport_details = ""

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current_scan_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=300)
                ),
                vol.Optional(CONF_TIMEOUT, default=current_timeout): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=60)
                ),
                vol.Optional(CONF_RETRY, default=current_retry): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=5)
                ),
                vol.Optional(CONF_FORCE_FULL_REGISTER_LIST, default=force_full): bool,
                vol.Optional(CONF_ENABLE_DEVICE_SCAN, default=current_enable_scan): bool,
                vol.Optional(
                    CONF_LOG_LEVEL,
                    default=current_log_level,
                    description={
                        "selector": {
                            "select": {
                                "options": [
                                    {"value": level, "label": f"{DOMAIN}.log_level_{level}"}
                                    for level in ("debug", "info", "warning", "error")
                                ]
                            }
                        }
                    },
                ): vol.In({"debug", "info", "warning", "error"}),
                vol.Optional(CONF_SCAN_UART_SETTINGS, default=current_scan_uart): bool,
                vol.Optional(CONF_SKIP_MISSING_REGISTERS, default=current_skip_missing): bool,
                vol.Optional(
                    CONF_SAFE_SCAN, default=current_safe_scan, description={"advanced": True}
                ): bool,
                vol.Optional(CONF_AIRFLOW_UNIT, default=current_airflow_unit): vol.In(
                    [AIRFLOW_UNIT_M3H, AIRFLOW_UNIT_PERCENTAGE]
                ),
                vol.Optional(
                    CONF_DEEP_SCAN, default=current_deep_scan, description={"advanced": True}
                ): bool,
                vol.Optional(
                    CONF_MAX_REGISTERS_PER_REQUEST,
                    default=current_max_registers_per_request,
                    description={
                        "advanced": True,
                        "selector": {"number": {"min": 1, "max": MAX_BATCH_REGISTERS, "step": 1}},
                    },
                ): int,
            }
        )

        # IMPORTANT: do NOT expose CONF_CONNECTION_MODE here (prevents duplicate GUI fields)

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
                "device_scan_enabled": "Yes" if current_enable_scan else "No",
                "current_airflow_unit": current_airflow_unit,
                "deep_scan_enabled": "Yes" if current_deep_scan else "No",
                "current_max_registers_per_request": str(current_max_registers_per_request),
                "safe_scan_enabled": "Yes" if current_safe_scan else "No",
                "current_log_level": current_log_level,
                "transport_label": transport_label,
                "transport_details": transport_details,
            },
        )
