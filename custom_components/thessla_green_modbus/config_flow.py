"""Config flow for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import inspect
import logging
import traceback
from collections.abc import Awaitable, Callable
from importlib import import_module
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from voluptuous import Invalid as VOL_INVALID

from .config_flow_confirm import (
    build_confirmation_placeholders as _build_confirmation_placeholders,
)
from .config_flow_entry import build_unique_id as _build_unique_id_impl
from .config_flow_entry import prepare_entry_payload as _prepare_entry_payload_impl
from .config_flow_errors import classify_os_error as _classify_os_error_impl
from .config_flow_errors import (
    should_log_timeout_traceback as _should_log_timeout_traceback_impl,
)
from .config_flow_network import looks_like_hostname as _looks_like_hostname_impl
from .config_flow_options import denormalize_option as _denormalize_option_impl
from .config_flow_options import normalize_baud_rate as _normalize_baud_rate_impl
from .config_flow_options import normalize_parity as _normalize_parity_impl
from .config_flow_options import normalize_stop_bits as _normalize_stop_bits_impl
from .config_flow_options import strip_translation_prefix as _strip_translation_prefix_impl
from .config_flow_options_form import (
    build_options_defaults as _build_options_defaults,
)
from .config_flow_options_form import (
    build_options_description_placeholders as _build_options_description_placeholders,
)
from .config_flow_options_form import build_options_schema as _build_options_schema
from .config_flow_options_form import (
    build_transport_description as _build_transport_description,
)
from .config_flow_payloads import caps_to_dict as _caps_to_dict_impl
from .config_flow_payloads import normalize_connection_type as _normalize_connection_type_impl
from .config_flow_runtime import TIMEOUT_EXCEPTIONS
from .config_flow_runtime import (
    call_with_optional_timeout as _call_with_optional_timeout_impl,
)
from .config_flow_runtime import (
    is_request_cancelled_error as _is_request_cancelled_error_impl,
)
from .config_flow_runtime import run_with_retry as _run_with_retry_impl
from .config_flow_schema import build_connection_schema as _build_connection_schema_impl
from .config_flow_validation import process_scan_capabilities as _process_scan_capabilities_impl
from .config_flow_validation import validate_rtu_config as _validate_rtu_config_impl
from .config_flow_validation import validate_slave_id as _validate_slave_id_impl
from .config_flow_validation import validate_tcp_config as _validate_tcp_config_impl
from .const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_MODE,
    CONF_DEEP_SCAN,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOP_BITS,
    CONF_TIMEOUT,
    CONNECTION_TYPE_TCP,
    DEFAULT_DEEP_SCAN,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_RETRY,
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

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from homeassistant.components.dhcp import DhcpServiceInfo
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

    class _ConfigFlowBase(config_entries.ConfigFlow):
        def __init_subclass__(cls, *, domain: str, **kwargs: Any) -> None: ...

else:
    _ConfigFlowBase = config_entries.ConfigFlow
    DhcpServiceInfo = Any
    ZeroconfServiceInfo = Any



def _is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Return True when a modbus IO error indicates a cancelled request."""
    return _is_request_cancelled_error_impl(exc)


ThesslaGreenDeviceScanner: Any | None = None
DeviceCapabilities: Any | None = None


async def _load_scanner_module(hass: HomeAssistant) -> Any:
    """Import scanner.core via the HA executor to avoid blocking the event loop."""
    if hass is None or not hasattr(hass, "async_add_executor_job"):
        return import_module("custom_components.thessla_green_modbus.scanner.core")
    return await hass.async_add_executor_job(
        import_module, "custom_components.thessla_green_modbus.scanner.core"
    )


# Delay between retries when establishing the connection during the config flow.
# Uses exponential backoff: ``backoff * 2 ** (attempt-1)``.
CONFIG_FLOW_BACKOFF = 0.1



def _strip_translation_prefix(value: str) -> str:
    """Remove integration/domain prefixes from option strings."""
    return _strip_translation_prefix_impl(value)


def _normalize_baud_rate(value: Any) -> int:
    """Normalize a Modbus baud rate option to an integer."""
    return _normalize_baud_rate_impl(value)


def _normalize_parity(value: Any) -> str:
    """Normalize a Modbus parity option to a canonical string."""
    return _normalize_parity_impl(value)


def _normalize_stop_bits(value: Any) -> int:
    """Normalize a Modbus stop bits option to an integer."""
    return _normalize_stop_bits_impl(value)


def _denormalize_option(prefix: str, value: Any | None) -> Any | None:
    """Convert a normalized option back to its translation key."""
    return _denormalize_option_impl(prefix, value)


def _looks_like_hostname(value: str) -> bool:
    """Basic hostname validation for environments without network helpers."""
    return _looks_like_hostname_impl(value)


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
    return await _run_with_retry_impl(func, retries=retries, backoff=backoff)


async def _call_with_optional_timeout(func: Callable[[], Any], timeout: float) -> Any:
    """Call ``func`` and apply timeout only to awaitable results."""
    return await _call_with_optional_timeout_impl(func, timeout)


def _caps_to_dict(obj: Any) -> dict[str, Any]:
    """Return a JSON-serializable dict from a capabilities object."""
    return _caps_to_dict_impl(obj)


def _normalize_connection_type(data: dict[str, Any]) -> str:
    """Normalize connection_type in data dict and return the canonical type string."""
    return _normalize_connection_type_impl(data)


def _validate_slave_id(data: dict[str, Any]) -> int:
    """Validate and normalise slave_id in data. Returns the integer value."""
    return _validate_slave_id_impl(data)


def _validate_tcp_config(data: dict[str, Any]) -> tuple[str, int]:
    """Validate and normalise TCP fields in data. Returns (host, port)."""
    return _validate_tcp_config_impl(data, looks_like_hostname=_looks_like_hostname)


def _validate_rtu_config(data: dict[str, Any]) -> None:
    """Validate and normalise RTU serial fields in data."""
    _validate_rtu_config_impl(
        data,
        normalize_baud_rate=_normalize_baud_rate,
        normalize_parity=_normalize_parity,
        normalize_stop_bits=_normalize_stop_bits,
    )


def _process_scan_capabilities(
    scan_result: dict[str, Any],
    capabilities_cls: type,
) -> dict[str, Any]:
    """Extract and validate capabilities from a scan result dict."""
    return _process_scan_capabilities_impl(
        scan_result,
        capabilities_cls=capabilities_cls,
        caps_to_dict=_caps_to_dict,
        logger=_LOGGER,
    )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    connection_type = _normalize_connection_type(data)
    slave_id = _validate_slave_id(data)

    name = data.get(CONF_NAME, DEFAULT_NAME)
    timeout = data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    host = ""
    port = DEFAULT_PORT
    if connection_type == CONNECTION_TYPE_TCP:
        host, port = _validate_tcp_config(data)
    else:
        _validate_rtu_config(data)

    module = await _load_scanner_module(hass)
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
        verify_cb = getattr(scanner, "verify_connection", None)
        if not callable(verify_cb):
            raise AttributeError("verify_connection")

        await _run_with_retry(
            lambda: _call_with_optional_timeout(verify_cb, short_timeout),
            retries=DEFAULT_RETRY,
            backoff=CONFIG_FLOW_BACKOFF,
        )

        # Perform full device scan
        scan_result = await _run_with_retry(
            lambda: _call_with_optional_timeout(scanner.scan_device, timeout),
            retries=DEFAULT_RETRY,
            backoff=CONFIG_FLOW_BACKOFF,
        )

        if not isinstance(scan_result, dict) or not scan_result:
            raise CannotConnect("invalid_format")

        caps_dict = _process_scan_capabilities(scan_result, capabilities_cls)
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
    except TIMEOUT_EXCEPTIONS as exc:
        _LOGGER.warning("Timeout during device validation: %s", exc)
        if _should_log_timeout_traceback_impl(exc):
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
        reason = _classify_os_error_impl(exc)
        if reason == "dns_failure":
            _LOGGER.error("DNS resolution failed: %s", exc)
        elif reason == "connection_refused":
            _LOGGER.error("Connection refused: %s", exc)
        else:
            _LOGGER.error("Unexpected error during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect(reason) from exc
    except CannotConnect:
        raise
    except (ValueError, TypeError, RuntimeError, ImportError) as exc:
        _LOGGER.error("Unexpected error during device validation: %s", exc)
        _LOGGER.debug("Traceback:\n%s", traceback.format_exc())
        raise CannotConnect("cannot_connect") from exc
    finally:
        if scanner is not None and hasattr(scanner, "close"):
            close_result = scanner.close()
            if inspect.isawaitable(close_result):
                await close_result


class ConfigFlow(_ConfigFlowBase, domain=DOMAIN):
    """Handle a config flow for ThesslaGreen Modbus."""

    VERSION = 4

    def __init__(self) -> None:
        """Initialize config flow."""
        self._data: dict[str, Any] = {}
        self._device_info: dict[str, Any] = {}
        self._scan_result: dict[str, Any] = {}
        self._tg_flow_reauth_entry_id: str | None = None
        self._tg_flow_reauth_existing_data: dict[str, Any] = {}
        self._discovered_host: str | None = None

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow user to update host/port/slave_id without removing the entry."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data_updates={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SLAVE_ID: user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=entry.data.get(CONF_HOST, ""),
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=entry.data.get(CONF_PORT, DEFAULT_PORT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                    vol.Required(
                        CONF_SLAVE_ID,
                        default=entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
                }
            ),
        )

    def _build_connection_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        """Return schema for connection details with provided defaults."""
        return _build_connection_schema_impl(
            defaults,
            discovered_host=self._discovered_host,
            modbus_baud_rates=MODBUS_BAUD_RATES,
            modbus_parity=MODBUS_PARITY,
            modbus_stop_bits=MODBUS_STOP_BITS,
        )

    @staticmethod
    def _build_unique_id(data: dict[str, Any]) -> str:
        """Generate a unique identifier for the config entry."""
        return _build_unique_id_impl(data)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the confirm step."""
        module = await _load_scanner_module(self.hass)
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
        return _prepare_entry_payload_impl(self._data, self._scan_result, cap_cls)

    async def _async_show_confirmation(self, cap_cls: Any, step_id: str) -> ConfigFlowResult:
        """Render confirmation step with device details."""
        description_placeholders = await _build_confirmation_placeholders(
            hass=self.hass,
            data=self._data,
            device_info=self._device_info,
            scan_result=self._scan_result,
            cap_cls=cap_cls,
            caps_to_dict=_caps_to_dict,
        )

        return self.async_show_form(
            step_id=step_id,
            description_placeholders=description_placeholders,
        )

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        """Handle DHCP discovery of AirPack device."""
        await self.async_set_unique_id(discovery_info.macaddress.upper())
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        self._discovered_host = discovery_info.ip
        return await self.async_step_user()

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle Zeroconf discovery of AirPack device."""
        await self.async_set_unique_id(discovery_info.host)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
        self._discovered_host = discovery_info.host
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                max_regs = user_input.get(
                    CONF_MAX_REGISTERS_PER_REQUEST, DEFAULT_MAX_REGISTERS_PER_REQUEST
                )
                if not 1 <= max_regs <= MAX_BATCH_REGISTERS:
                    raise VOL_INVALID("max_registers_range", path=[CONF_MAX_REGISTERS_PER_REQUEST])

                info = await validate_input(self.hass, user_input)

                self._data = user_input
                self._device_info = info.get("device_info", {})
                self._scan_result = info.get("scan_result", {})

                await self.async_set_unique_id(self._build_unique_id(user_input))

            except CannotConnect as exc:
                errors["base"] = exc.args[0] if exc.args else "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except VOL_INVALID as err:
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

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                    raise VOL_INVALID("max_registers_range", path=[CONF_MAX_REGISTERS_PER_REQUEST])

                info = await validate_input(self.hass, user_input)
                self._data = user_input
                self._device_info = info.get("device_info", {})
                self._scan_result = info.get("scan_result", {})
                return await self.async_step_reauth_confirm()

            except CannotConnect as exc:
                errors["base"] = exc.args[0] if exc.args else "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except VOL_INVALID as err:
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
    ) -> ConfigFlowResult:
        """Confirm reauthentication details and update the existing entry."""
        module = await _load_scanner_module(self.hass)
        cap_cls = DeviceCapabilities or module.DeviceCapabilities

        if user_input is not None:
            reauth_entry_id = self._tg_flow_reauth_entry_id or getattr(
                self, "_tg_reauth_entry_id", None
            )
            if self.hass is None:
                _LOGGER.error("Cannot complete reauth - missing Home Assistant context")
                return self.async_abort(reason="reauth_failed")
            if reauth_entry_id is None:
                _LOGGER.error("Cannot complete reauth - missing entry id")
                return self.async_abort(reason="reauth_entry_missing")

            entry = self.hass.config_entries.async_get_entry(reauth_entry_id)
            if entry is None:
                _LOGGER.error(
                    "Reauthentication requested for missing entry %s",
                    reauth_entry_id,
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
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow handler."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ThesslaGreen Modbus."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._stored_config_entry = config_entry

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry for this options flow."""
        return self._stored_config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        values = _build_options_defaults(entry_data, entry_options)
        transport_label, transport_details = _build_transport_description(values)
        data_schema = _build_options_schema(values)

        # IMPORTANT: do NOT expose CONF_CONNECTION_MODE here (prevents duplicate GUI fields)

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=_build_options_description_placeholders(
                values,
                transport_label=transport_label,
                transport_details=transport_details,
            ),
        )
