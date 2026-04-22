"""Asynchronous data coordinator for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as _dt_util
from pymodbus.client import AsyncModbusTcpClient

from ._coordinator_capabilities import _CoordinatorCapabilitiesMixin
from ._coordinator_io import (
    _ModbusIOMixin,
    _PermanentModbusError,
)
from ._coordinator_register_processing import (
    find_register_name as _find_register_name_impl,
)
from ._coordinator_register_processing import (
    process_register_value as _process_register_value_impl,
)
from ._coordinator_schedule import _CoordinatorScheduleMixin
from ._coordinator_update import async_update_data as _async_update_data_impl
from .const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_BACKOFF,
    DEFAULT_BACKOFF_JITTER,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_MAX_REGISTERS_PER_REQUEST,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_STOP_BITS,
    DOMAIN,
    HOLDING_BATCH_BOUNDARIES,
    KNOWN_MISSING_REGISTERS,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
    UNKNOWN_MODEL,
    input_registers,
)
from .coordinator_config import normalize_scan_interval as _normalize_scan_interval_impl
from .coordinator_diagnostics import (
    device_name as _device_name_impl,
)
from .coordinator_diagnostics import (
    get_device_info as _get_device_info_impl,
)
from .coordinator_diagnostics import (
    get_diagnostic_data as _get_diagnostic_data_impl,
)
from .coordinator_diagnostics import (
    performance_stats as _performance_stats_impl,
)
from .coordinator_diagnostics import (
    status_overview as _status_overview_impl,
)
from .coordinator_models import CoordinatorConfig
from .coordinator_runtime import normalize_backoff as _normalize_backoff_impl
from .coordinator_runtime import parse_backoff_jitter as _parse_backoff_jitter_impl
from .coordinator_state import (
    initialize_runtime_state as _initialize_runtime_state_impl,
)
from .coordinator_state import normalize_serial_settings as _normalize_serial_settings_impl
from .coordinator_state import resolve_effective_batch as _resolve_effective_batch_impl
from .errors import CannotConnect
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import group_reads
from .modbus_transport import (
    BaseModbusTransport,
    RawRtuOverTcpTransport,
    RtuModbusTransport,
    TcpModbusTransport,
)
from .register_defs_cache import get_register_definitions
from .registers.loader import RegisterDef
from .scanner import (
    DeviceCapabilities,
    ThesslaGreenDeviceScanner,
    is_request_cancelled_error,
)
from .utils import resolve_connection_settings

__all__ = [
    "CoordinatorConfig",
    "ThesslaGreenModbusCoordinator",
    "_PermanentModbusError",
]


COORDINATOR_BASE = DataUpdateCoordinator[dict[str, Any]]
dt_util = _dt_util


def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    from .utils import utcnow as _utils_utcnow
    return _utils_utcnow()


_ORIGINAL_ASYNC_MODBUS_TCP_CLIENT = AsyncModbusTcpClient

def get_register_definition(name: str) -> RegisterDef:
    return get_register_definitions()[name]


_LOGGER = logging.getLogger(__name__)

class ThesslaGreenModbusCoordinator(
    _ModbusIOMixin,
    _CoordinatorCapabilitiesMixin,
    _CoordinatorScheduleMixin,
    COORDINATOR_BASE,
):
    """Optimized data coordinator for ThesslaGreen Modbus device."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: CoordinatorConfig,
        *,
        entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the coordinator."""
        cfg = config

        host = cfg.host
        port = cfg.port
        slave_id = cfg.slave_id
        name = cfg.name
        scan_interval = cfg.scan_interval
        timeout = cfg.timeout
        retry = cfg.retry
        backoff = cfg.backoff
        backoff_jitter = cfg.backoff_jitter
        force_full_register_list = cfg.force_full_register_list
        scan_uart_settings = cfg.scan_uart_settings
        deep_scan = cfg.deep_scan
        safe_scan = cfg.safe_scan
        max_registers_per_request = cfg.max_registers_per_request
        skip_missing_registers = cfg.skip_missing_registers
        connection_type = cfg.connection_type
        connection_mode = cfg.connection_mode
        serial_port = cfg.serial_port
        baud_rate = cfg.baud_rate
        parity = cfg.parity
        stop_bits = cfg.stop_bits

        interval_seconds = _normalize_scan_interval_impl(scan_interval)
        update_interval = timedelta(seconds=interval_seconds)
        self.scan_interval = interval_seconds

        try:
            super().__init__(
                hass,
                _LOGGER,
                config_entry=entry,
                name=f"{DOMAIN}_{entry.entry_id if entry else name}",
                update_interval=update_interval,
            )
        except TypeError:
            super().__init__(
                hass,
                _LOGGER,
                name=f"{DOMAIN}_{entry.entry_id if entry else name}",
                update_interval=update_interval,
            )
        self.hass = hass

        resolved_type, resolved_mode = resolve_connection_settings(
            connection_type, connection_mode, port
        )
        normalized_serial_port, normalized_baud_rate, parity_norm, normalized_stop_bits = (
            _normalize_serial_settings_impl(serial_port, baud_rate, parity, stop_bits)
        )

        self._device_name = name
        self.config = CoordinatorConfig(
            host=host,
            port=port,
            slave_id=slave_id,
            name=name,
            scan_interval=self.scan_interval,
            timeout=timeout,
            retry=retry,
            backoff=backoff,
            backoff_jitter=backoff_jitter,
            force_full_register_list=force_full_register_list,
            scan_uart_settings=scan_uart_settings,
            deep_scan=deep_scan,
            safe_scan=safe_scan,
            max_registers_per_request=max_registers_per_request,
            skip_missing_registers=skip_missing_registers,
            connection_type=resolved_type,
            connection_mode=resolved_mode,
            serial_port=normalized_serial_port,
            baud_rate=normalized_baud_rate,
            parity=parity_norm,
            stop_bits=normalized_stop_bits,
        )
        self._resolved_connection_mode: str | None = (
            resolved_mode if resolved_mode != CONNECTION_MODE_AUTO else None
        )
        self.timeout = timeout
        self.retry = retry
        self.backoff = _normalize_backoff_impl(backoff)

        self.backoff_jitter = self._parse_backoff_jitter(backoff_jitter)
        self.force_full_register_list = force_full_register_list
        self.scan_uart_settings = scan_uart_settings
        self.deep_scan = deep_scan
        self.safe_scan = safe_scan
        self.entry = entry
        self.skip_missing_registers = skip_missing_registers

        self.effective_batch = _resolve_effective_batch_impl(entry, max_registers_per_request)
        self.max_registers_per_request = self.effective_batch

        self.config.max_registers_per_request = self.max_registers_per_request
        self.config.backoff = self.backoff
        self.config.backoff_jitter = self.backoff_jitter

        _initialize_runtime_state_impl(self, entry=entry)

    @property
    def host(self) -> str:
        """Host accessor backed by CoordinatorConfig."""
        return self.config.host

    @host.setter
    def host(self, value: str) -> None:
        self.config.host = value

    @property
    def port(self) -> int:
        """Port accessor backed by CoordinatorConfig."""
        return self.config.port

    @port.setter
    def port(self, value: int) -> None:
        self.config.port = value

    @property
    def slave_id(self) -> int:
        """Slave ID accessor backed by CoordinatorConfig."""
        return self.config.slave_id

    @slave_id.setter
    def slave_id(self, value: int) -> None:
        self.config.slave_id = value

    @property
    def connection_type(self) -> str:
        """Connection type accessor backed by CoordinatorConfig."""
        return self.config.connection_type

    @connection_type.setter
    def connection_type(self, value: str) -> None:
        self.config.connection_type = value

    @property
    def connection_mode(self) -> str | None:
        """Connection mode accessor backed by CoordinatorConfig."""
        return self.config.connection_mode

    @connection_mode.setter
    def connection_mode(self, value: str | None) -> None:
        self.config.connection_mode = value

    @property
    def serial_port(self) -> str:
        """Serial port accessor backed by CoordinatorConfig."""
        return self.config.serial_port

    @serial_port.setter
    def serial_port(self, value: str) -> None:
        self.config.serial_port = value

    @property
    def baud_rate(self) -> int:
        """Baud rate accessor backed by CoordinatorConfig."""
        return self.config.baud_rate

    @baud_rate.setter
    def baud_rate(self, value: int) -> None:
        self.config.baud_rate = value

    @property
    def parity(self) -> str:
        """Parity accessor backed by CoordinatorConfig."""
        return self.config.parity

    @parity.setter
    def parity(self, value: str) -> None:
        self.config.parity = value

    @property
    def stop_bits(self) -> int:
        """Stop bits accessor backed by CoordinatorConfig."""
        return self.config.stop_bits

    @stop_bits.setter
    def stop_bits(self, value: int) -> None:
        self.config.stop_bits = value

    @classmethod
    def from_params(
        cls,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        name: str = DEFAULT_NAME,
        scan_interval: timedelta | int = DEFAULT_SCAN_INTERVAL,
        timeout: int = 10,
        retry: int = 3,
        backoff: float = DEFAULT_BACKOFF,
        backoff_jitter: float | tuple[float, float] | None = DEFAULT_BACKOFF_JITTER,
        force_full_register_list: bool = False,
        scan_uart_settings: bool = DEFAULT_SCAN_UART_SETTINGS,
        deep_scan: bool = False,
        safe_scan: bool = False,
        max_registers_per_request: int = DEFAULT_MAX_REGISTERS_PER_REQUEST,
        entry: ConfigEntry | None = None,
        skip_missing_registers: bool = False,
        connection_type: str = DEFAULT_CONNECTION_TYPE,
        connection_mode: str | None = None,
        serial_port: str = DEFAULT_SERIAL_PORT,
        baud_rate: int = DEFAULT_BAUD_RATE,
        parity: str = DEFAULT_PARITY,
        stop_bits: int = DEFAULT_STOP_BITS,
    ) -> ThesslaGreenModbusCoordinator:
        """Construct coordinator from explicit parameters."""
        return cls(
            hass=hass,
            config=CoordinatorConfig(
                host=host,
                port=port,
                slave_id=slave_id,
                name=name,
                scan_interval=scan_interval,
                timeout=timeout,
                retry=retry,
                backoff=backoff,
                backoff_jitter=backoff_jitter,
                force_full_register_list=force_full_register_list,
                scan_uart_settings=scan_uart_settings,
                deep_scan=deep_scan,
                safe_scan=safe_scan,
                max_registers_per_request=max_registers_per_request,
                skip_missing_registers=skip_missing_registers,
                connection_type=connection_type,
                connection_mode=connection_mode,
                serial_port=serial_port,
                baud_rate=baud_rate,
                parity=parity,
                stop_bits=stop_bits,
            ),
            entry=entry,
        )

    @staticmethod
    def _parse_backoff_jitter(
        value: float | int | str | tuple[float, float] | list[float] | None,
    ) -> float | tuple[float, float] | None:
        """Normalize backoff_jitter input to None, float, or (float, float)."""
        return _parse_backoff_jitter_impl(value)

    def _trigger_reauth(self, reason: str) -> None:
        """Schedule a reauthentication flow if not already triggered."""

        if self._reauth_scheduled or self.entry is None:
            return

        self._reauth_scheduled = True
        _LOGGER.warning("Starting reauthentication for %s (%s)", self._device_name, reason)
        self.hass.async_create_task(self.entry.async_start_reauth(self.hass))

    def get_register_map(self, register_type: str) -> dict[str, int]:
        """Return the register map for the given register type."""
        return self._register_maps.get(register_type, {})

    def _get_client_method(self, name: str) -> Callable[..., Any]:
        """Return a Modbus method from transport/client or a no-op placeholder."""

        transport = self._transport
        transport_method = getattr(transport, name, None) if transport is not None else None
        if callable(transport_method):
            return cast(Callable[..., Any], transport_method)
        """Return a Modbus client method or a no-op async placeholder."""

        client = self.client
        method = getattr(client, name, None) if client is not None else None
        if callable(method):
            return cast(Callable[..., Any], method)

        async def _missing_method(*_args: Any, **_kwargs: Any) -> Any:
            return None

        _missing_method.__name__ = name
        return _missing_method

    async def _read_coils_transport(
        self,
        _slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        if not self.client:
            raise ConnectionException("Modbus client is not connected")
        return await self._call_modbus(
            self.client.read_coils,
            address,
            count=count,
            attempt=attempt,
        )

    async def _read_discrete_inputs_transport(
        self,
        _slave_id: int,
        address: int,
        *,
        count: int,
        attempt: int = 1,
    ) -> Any:
        if not self.client:
            raise ConnectionException("Modbus client is not connected")
        return await self._call_modbus(
            self.client.read_discrete_inputs,
            address,
            count=count,
            attempt=attempt,
        )

    def _build_scanner_kwargs(self) -> dict[str, Any]:
        """Return constructor kwargs shared by all scanner creation paths."""
        return {
            "host": self.config.host,
            "port": self.config.port,
            "slave_id": self.config.slave_id,
            "timeout": self.timeout,
            "retry": self.retry,
            "backoff": self.backoff,
            "backoff_jitter": self.backoff_jitter,
            "scan_uart_settings": self.scan_uart_settings,
            "skip_known_missing": self.skip_missing_registers,
            "deep_scan": self.deep_scan,
            "max_registers_per_request": self.effective_batch,
            "safe_scan": self.safe_scan,
            "connection_type": self.config.connection_type,
            "connection_mode": self._resolved_connection_mode or self.config.connection_mode,
            "serial_port": self.config.serial_port,
            "baud_rate": self.config.baud_rate,
            "parity": self.config.parity,
            "stop_bits": self.config.stop_bits,
            "hass": self.hass,
        }

    async def _create_scanner(self) -> Any:
        """Instantiate a ThesslaGreenDeviceScanner using its create() factory."""
        kwargs = self._build_scanner_kwargs()
        return await ThesslaGreenDeviceScanner.create(**kwargs)

    def _apply_scan_result(self, scan_result: dict[str, Any]) -> None:
        """Store and process a completed device scan result."""
        self.device_scan_result = scan_result
        if self.config.connection_mode == CONNECTION_MODE_AUTO:
            if resolved := self.device_scan_result.get("resolved_connection_mode"):
                self._resolved_connection_mode = resolved
        self.last_scan = _utcnow()

        scan_registers = self.device_scan_result.get("available_registers", {})
        self.available_registers = self._normalise_available_registers(
            {
                "input_registers": scan_registers.get("input_registers", []),
                "holding_registers": scan_registers.get("holding_registers", []),
                "coil_registers": scan_registers.get("coil_registers", []),
                "discrete_inputs": scan_registers.get("discrete_inputs", []),
            }
        )
        if self.skip_missing_registers:
            for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                self.available_registers[reg_type].difference_update(names)

        self.device_info = self.device_scan_result.get("device_info", {})
        self.device_info.setdefault("device_name", self._device_name)

        if self.device_info.get("serial_number") and self.device_info["serial_number"] != "Unknown":
            self.available_registers["input_registers"].add("serial_number")

        caps_obj = self.device_scan_result.get("capabilities")
        if isinstance(caps_obj, DeviceCapabilities):
            self.capabilities = caps_obj
        elif isinstance(caps_obj, dict):
            self.capabilities = DeviceCapabilities(**caps_obj)
        elif caps_obj is None:
            self.capabilities = DeviceCapabilities()
        else:
            _LOGGER.error(
                "Invalid capabilities format: expected dict, got %s",
                type(caps_obj).__name__,
            )
            raise CannotConnect("invalid_capabilities")

        self.unknown_registers = self.device_scan_result.get("unknown_registers", {})
        self.scanned_registers = self.device_scan_result.get("scanned_registers", {})
        self._store_scan_cache()

        _LOGGER.info(
            "Device scan completed: %d registers found, model: %s, firmware: %s",
            self.device_scan_result.get("register_count", 0),
            self.device_info.get("model", UNKNOWN_MODEL),
            self.device_info.get("firmware", "Unknown"),
        )

    async def _run_device_scan(self) -> None:
        """Run a full device scan and apply the result."""
        _LOGGER.info("Scanning device for available registers...")
        scanner = None
        try:
            scanner = await self._create_scanner()
            scan_result = scanner.scan_device()
            if inspect.isawaitable(scan_result):
                scan_result = await scan_result
            self._apply_scan_result(scan_result)
        except asyncio.CancelledError:
            _LOGGER.warning("Device scan cancelled")
            raise
        except (ModbusException, ConnectionException) as exc:
            _LOGGER.exception("Device scan failed: %s", exc)
            raise
        except TimeoutError as exc:
            _LOGGER.warning("Device scan timed out: %s", exc)
            raise
        except (OSError, ValueError) as exc:
            _LOGGER.exception("Unexpected error during device scan: %s", exc)
            raise
        finally:
            if scanner is not None:
                close_result = scanner.close()
                if inspect.isawaitable(close_result):
                    await close_result

    def _warn_missing_device_info(self) -> None:
        """Log warnings when model or firmware could not be identified."""
        model = self.device_info.get("model", UNKNOWN_MODEL)
        firmware = self.device_info.get("firmware", "Unknown")
        if model != UNKNOWN_MODEL and firmware != "Unknown":
            return
        missing: list[str] = []
        if model == "Unknown":
            missing.append("model")
            _LOGGER.debug(
                "Device model missing for %s:%s%s",
                self.config.host,
                self.config.port,
                f" (slave {self.config.slave_id})" if self.config.slave_id is not None else "",
            )
        if firmware == "Unknown":
            missing.append("firmware")
            _LOGGER.debug(
                "Device firmware missing for %s:%s%s",
                self.config.host,
                self.config.port,
                f" (slave {self.config.slave_id})" if self.config.slave_id is not None else "",
            )
        if missing:
            device_details = f"{self.config.host}:{self.config.port}"
            if self.config.slave_id is not None:
                device_details += f", slave {self.config.slave_id}"
            _LOGGER.warning(
                "Device %s missing %s (%s). "
                "Verify Modbus connectivity or ensure your firmware is supported.",
                self._device_name,
                " and ".join(missing),
                device_details,
            )

    async def async_setup(self) -> bool:
        """Set up the coordinator by scanning the device."""
        if self.config.connection_type == CONNECTION_TYPE_RTU:
            endpoint = self.config.serial_port or "serial"
        else:
            endpoint = f"{self.config.host}:{self.config.port}"
        _LOGGER.info(
            "Setting up ThesslaGreen coordinator for %s via %s",
            endpoint,
            self.config.connection_type.upper(),
        )

        if self.force_full_register_list:
            _LOGGER.info("Using full register list (skipping scan)")
            self._load_full_register_list()
        elif not self.enable_device_scan:
            cache: dict[str, Any] = {}
            if self.entry is not None:
                raw_cache = self.entry.options.get("device_scan_cache", {})
                if isinstance(raw_cache, dict):
                    cache = raw_cache
            if cache and self._apply_scan_cache(cache):
                _LOGGER.info("Using cached device scan results")
            else:
                _LOGGER.info("Device scan disabled; falling back to full register list")
                self._load_full_register_list()
        else:
            await self._run_device_scan()

        self._warn_missing_device_info()

        # Pre-compute register groups for batch reading
        self._compute_register_groups()

        # Test initial connection
        await self._test_connection()

        # Ensure we clean up tasks when Home Assistant stops
        if self._stop_listener is None and hasattr(self.hass, "bus"):
            self._stop_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self._async_handle_stop
            )

        return True

    def _load_full_register_list(self) -> None:
        """Load full register list when forced."""
        self.available_registers = {
            key: set(mapping.keys()) for key, mapping in self._register_maps.items()
        }

        self.device_info = {
            "device_name": f"{DEFAULT_NAME} {UNKNOWN_MODEL}",
            "model": UNKNOWN_MODEL,
            "firmware": "Unknown",
            "serial_number": "Unknown",
            "input_registers": set(self._register_maps["input_registers"].keys()),
            "holding_registers": set(self._register_maps["holding_registers"].keys()),
            "coil_registers": set(self._register_maps["coil_registers"].keys()),
            "discrete_inputs": set(self._register_maps["discrete_inputs"].keys()),
        }

        if self.skip_missing_registers:
            for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                self.available_registers[reg_type].difference_update(names)

        _LOGGER.info(
            "Loaded full register list: %d total registers",
            sum(len(regs) for regs in self.available_registers.values()),
        )

    @staticmethod
    def _normalise_cached_register_name(name: str) -> str:
        """Normalise cached register names to current canonical form."""

        match = re.fullmatch(r"([es])(\d+)", name)
        if match:
            return f"{match.group(1)}_{int(match.group(2))}"
        return name

    def _normalise_available_registers(
        self, available: dict[str, list[str] | set[str]]
    ) -> dict[str, set[str]]:
        """Return available register names in canonical form."""

        normalised: dict[str, set[str]] = {}
        for reg_type, names in available.items():
            if not isinstance(names, list | set):
                continue
            normalised[reg_type] = {
                self._normalise_cached_register_name(str(name)) for name in names
            }
        return normalised

    def _apply_scan_cache(self, cache: dict[str, Any]) -> bool:
        """Apply cached scan data if available."""

        available = cache.get("available_registers")
        if not isinstance(available, dict):
            return False

        try:
            self.available_registers = self._normalise_available_registers(
                {
                    key: value
                    for key, value in available.items()
                    if isinstance(value, (list, set))
                }
            )
        except (TypeError, ValueError):
            return False

        device_info = cache.get("device_info")
        self.device_info = device_info if isinstance(device_info, dict) else {}
        caps_obj = cache.get("capabilities")
        if isinstance(caps_obj, dict):
            try:
                self.capabilities = DeviceCapabilities(**caps_obj)
            except (TypeError, ValueError):
                _LOGGER.debug("Invalid cached capabilities", exc_info=True)
        self.device_scan_result = cache

        if self.device_info.get("serial_number") and self.device_info["serial_number"] != "Unknown":
            self.available_registers["input_registers"].add("serial_number")

        # Only strip KNOWN_MISSING_REGISTERS for firmwares that actually lack
        # those registers (currently FW 3.11 / EC2 family). Stripping
        # unconditionally would corrupt caches built on newer firmwares where
        # the registers are present, until the next full scan.
        if self._firmware_lacks_known_missing(self.device_info.get("firmware")):
            for reg_type, names in KNOWN_MISSING_REGISTERS.items():
                if reg_type in self.available_registers:
                    self.available_registers[reg_type].difference_update(names)

        return True

    @staticmethod
    def _firmware_lacks_known_missing(firmware: Any) -> bool:
        """Return True for firmwares that do not expose KNOWN_MISSING_REGISTERS.

        Currently matches FW 3.x / EC2. Extend this when new affected
        firmwares are identified, or invert the check by adding an explicit
        FW allowlist in const.py.
        """
        if not isinstance(firmware, str):
            return False
        major = firmware.strip().split(".", 1)[0]
        return major in {"3"}

    def _store_scan_cache(self) -> None:
        """Store scan results in config entry options."""

        if self.entry is None:
            return

        available = {key: sorted(value) for key, value in self.available_registers.items()}
        cache = {
            "available_registers": available,
            "device_info": self.device_info,
            "capabilities": self.capabilities.as_dict(),
            "firmware": self.device_info.get("firmware"),
        }
        options = dict(self.entry.options)
        options["device_scan_cache"] = cache
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    def _compute_register_groups(self) -> None:
        """Pre-compute register groups for optimized batch reading."""
        self._register_groups.clear()

        for key, names in self.available_registers.items():
            if not names:
                continue

            # Build list of raw addresses taking register length into account
            mapping = self._register_maps[key]
            if self.safe_scan:
                groups: list[tuple[int, int]] = []
                for reg in names:
                    addr = mapping.get(reg)
                    if addr is None:
                        continue
                    try:
                        definition = get_register_definition(reg)
                        length = max(1, definition.length)
                    except (KeyError, AttributeError, TypeError) as err:
                        _LOGGER.debug("Missing definition for %s: %s", reg, err)
                        length = 1
                    except (
                        ValueError,
                        OSError,
                        RuntimeError,
                    ) as err:  # pragma: no cover - unexpected
                        _LOGGER.exception(
                            "Unexpected error getting definition for %s: %s",
                            reg,
                            err,
                        )
                        length = 1
                    groups.append((addr, min(length, self.effective_batch)))
                self._register_groups[key] = groups
                continue

            addresses: list[int] = []
            for reg in names:
                addr = mapping.get(reg)
                if addr is None:
                    continue
                try:
                    definition = get_register_definition(reg)
                    length = max(1, definition.length)
                except (KeyError, AttributeError, TypeError) as err:
                    _LOGGER.debug("Missing definition for %s: %s", reg, err)
                    length = 1
                except (ValueError, OSError, RuntimeError) as err:  # pragma: no cover - unexpected
                    _LOGGER.exception(
                        "Unexpected error getting definition for %s: %s",
                        reg,
                        err,
                    )
                    length = 1
                addresses.extend(range(addr, addr + length))

            boundaries = HOLDING_BATCH_BOUNDARIES if key == "holding_registers" else None
            self._register_groups[key] = group_reads(
                addresses,
                max_block_size=self.effective_batch,
                boundaries=boundaries,
            )

        _LOGGER.debug(
            "Pre-computed register groups: %s",
            {k: len(v) for k, v in self._register_groups.items()},
        )

    def _mark_registers_failed(self, names: Iterable[str | None]) -> None:
        """Record registers that failed to read."""
        failed: set[str] = getattr(self, "_failed_registers", set())
        failed.update(name for name in names if name)
        self._failed_registers = failed

    def _clear_register_failure(self, name: str) -> None:
        """Remove register from failed list on successful read."""
        if hasattr(self, "_failed_registers"):
            self._failed_registers.discard(name)

    async def _test_connection(self) -> None:
        """Test initial connection to the device."""
        async with self._write_lock:
            try:
                await self._ensure_connection()

                transport = self._transport
                if transport is None:
                    raise ConnectionException("Modbus transport is not connected")

                test_addresses = list(input_registers().values())[:3]

                for addr in test_addresses:
                    response = await transport.read_input_registers(
                        self.config.slave_id,
                        addr,
                        count=1,
                    )
                    if response is None:
                        raise ConnectionException(f"Cannot read register {addr}")
                    # Modbus error responses (e.g. exception code 2 — Illegal Data
                    # Address) still prove bidirectional communication with the device.

                if transport is not None and not transport.is_connected():
                    raise ConnectionException("Modbus transport is not connected")
                # Try to read a basic register to verify communication. "count" must
                # always be passed as a keyword argument to ``_call_modbus`` to avoid
                # issues with keyword-only parameters in pymodbus.
                count = 1
                response = await transport.read_input_registers(
                    self.config.slave_id,
                    0,
                    count=count,
                )
                if response is None:
                    raise ConnectionException("Cannot read basic register")
                # Modbus error response still proves the device is reachable.
                _LOGGER.debug("Connection test successful")
            except ModbusIOException as exc:
                if is_request_cancelled_error(exc):
                    _LOGGER.warning("Connection test skipped — device busy after scan: %s", exc)
                    return  # Non-fatal: scan already proved the device is reachable
                _LOGGER.exception("Connection test failed: %s", exc)
                raise
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.exception("Connection test failed: %s", exc)
                raise
            except TimeoutError as exc:
                _LOGGER.warning("Connection test timed out: %s", exc)
                raise
            except OSError as exc:
                _LOGGER.exception("Unexpected error during connection test: %s", exc)
                raise

    async def _async_setup_client(self) -> bool:
        """Set up the Modbus client if needed.

        Although only invoked in tests within this repository, this helper
        mirrors the logic executed during Home Assistant start-up. It returns
        ``True`` on success and ``False`` on failure.
        """
        try:
            await self._ensure_connection()
            return True
        except (ModbusException, ConnectionException) as exc:
            _LOGGER.exception("Failed to set up Modbus client: %s", exc)
            return False
        except TimeoutError as exc:
            _LOGGER.warning("Setting up Modbus client timed out: %s", exc)
            return False
        except OSError as exc:
            _LOGGER.exception("Unexpected error setting up Modbus client: %s", exc)
            return False

    async def _ensure_connection(self) -> None:
        """Ensure Modbus connection is established."""

        await self._ensure_connected()

    def _build_tcp_transport(
        self,
        mode: str,
    ) -> BaseModbusTransport:
        if mode == CONNECTION_MODE_TCP_RTU:
            return RawRtuOverTcpTransport(
                host=self.config.host,
                port=self.config.port,
                max_retries=self.retry,
                base_backoff=self.backoff,
                max_backoff=DEFAULT_MAX_BACKOFF,
                timeout=self.timeout,
                offline_state=self.offline_state,
            )
        return TcpModbusTransport(
            host=self.config.host,
            port=self.config.port,
            connection_type=CONNECTION_TYPE_TCP,
            max_retries=self.retry,
            base_backoff=self.backoff,
            max_backoff=DEFAULT_MAX_BACKOFF,
            timeout=self.timeout,
            offline_state=self.offline_state,
        )

    async def _try_direct_client_connect(self, *, allow_parameterless_ctor: bool) -> bool:
        """Try connecting via AsyncModbusTcpClient and store the connected client."""
        tcp_client_cls = globals().get("AsyncModbusTcpClient", AsyncModbusTcpClient)

        if allow_parameterless_ctor:
            try:
                direct_client = tcp_client_cls(
                    self.config.host,
                    port=self.config.port,
                    timeout=self.timeout,
                )
            except TypeError:
                direct_client = tcp_client_cls()
                direct_client.host = self.config.host
                direct_client.port = self.config.port
        else:
            direct_client = tcp_client_cls(
                self.config.host,
                port=self.config.port,
                timeout=self.timeout,
            )

        connect_method = getattr(direct_client, "connect", None)
        if callable(connect_method):
            connect_result = connect_method()
            if inspect.isawaitable(connect_result):
                connect_result = await connect_result
        else:
            connect_result = True
            direct_client.connected = True

        if bool(connect_result) or bool(getattr(direct_client, "connected", False)):
            self.client = direct_client
            self._transport = None
            return True
        return False

    async def _select_auto_transport(self) -> None:
        """Attempt auto-detection between RTU-over-TCP and Modbus TCP."""

        if self._resolved_connection_mode:
            self._transport = self._build_tcp_transport(self._resolved_connection_mode)
            return

        prefer_tcp = self.config.port == DEFAULT_PORT
        mode_order = (
            [CONNECTION_MODE_TCP, CONNECTION_MODE_TCP_RTU]
            if prefer_tcp
            else [
                CONNECTION_MODE_TCP_RTU,
                CONNECTION_MODE_TCP,
            ]
        )
        attempts: list[tuple[str, float]] = []
        for mode in mode_order:
            timeout = 5.0 if mode == CONNECTION_MODE_TCP_RTU else min(max(self.timeout, 5.0), 10.0)
            attempts.append((mode, timeout))
        last_error: Exception | None = None

        # Prefer client-based path first.
        try:
            if await self._try_direct_client_connect(allow_parameterless_ctor=True):
                return
        except (
            ModbusException,
            ConnectionException,
            ModbusIOException,
            TimeoutError,
            OSError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            _LOGGER.debug("Direct client connect attempt failed, trying transports: %s", exc)

        for mode, timeout in attempts:
            transport = self._build_tcp_transport(mode)
            try:
                await asyncio.wait_for(transport.ensure_connected(), timeout=3.0)
                try:
                    await asyncio.wait_for(
                        transport.read_holding_registers(self.config.slave_id, 0, count=2),
                        timeout=timeout,
                    )
                except (ModbusIOException, ConnectionException):
                    raise  # timeout / no connection = wrong protocol, reject transport
                except ModbusException as exc:
                    _LOGGER.debug("Protocol probe: Modbus error code = valid protocol (%s)", exc)
            except (
                ModbusException,
                ConnectionException,
                ModbusIOException,
                TimeoutError,
                OSError,
                TypeError,
                ValueError,
                AttributeError,
            ) as exc:  # pragma: no cover - network dependent
                last_error = exc
                await transport.close()
                continue
            self._transport = transport
            self._resolved_connection_mode = mode
            _LOGGER.info("Auto-selected Modbus transport %s for %s:%s", mode, self.config.host, self.config.port)
            return

        raise ConnectionException("Auto-detect Modbus transport failed") from last_error

    async def _ensure_connected(self) -> None:
        """Ensure Modbus connection is established using the shared client."""

        async with self._client_lock:
            if self._transport is not None and self._transport.is_connected():
                return
            if self._transport is None and self.client is not None:
                if bool(getattr(self.client, "connected", False)):
                    return
                connect_method = getattr(self.client, "connect", None)
                if callable(connect_method):
                    connect_result = connect_method()
                    if inspect.isawaitable(connect_result):
                        connect_result = await connect_result
                    if bool(connect_result) or bool(getattr(self.client, "connected", False)):
                        self.client.connected = True
                        return
            if self._transport is not None or self.client is not None:
                await self._disconnect_locked()

            try:
                if self._transport is None:
                    parity = SERIAL_PARITY_MAP.get(self.config.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])
                    stop_bits = SERIAL_STOP_BITS_MAP.get(
                        self.config.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]
                    )
                    if self.config.connection_type == CONNECTION_TYPE_RTU:
                        self._transport = RtuModbusTransport(
                            serial_port=self.config.serial_port,
                            baudrate=self.config.baud_rate,
                            parity=parity,
                            stopbits=stop_bits,
                            max_retries=self.retry,
                            base_backoff=self.backoff,
                            max_backoff=DEFAULT_MAX_BACKOFF,
                            timeout=self.timeout,
                            offline_state=self.offline_state,
                        )
                    else:
                        if self.config.connection_mode == CONNECTION_MODE_AUTO:
                            await self._select_auto_transport()
                        else:
                            mode = self.config.connection_mode or CONNECTION_MODE_TCP
                            self._transport = self._build_tcp_transport(mode)

                if self._transport is not None:
                    await self._transport.ensure_connected()
                    self.client = getattr(self._transport, "client", None)
                    if not self._transport.is_connected():
                        raise ConnectionException("Modbus transport is not connected")
                elif self.client is None:
                    raise ConnectionException("Modbus transport is not available")
                _LOGGER.debug("Modbus connection established")
                self.offline_state = False
            except (ModbusException, ConnectionException) as exc:
                self.statistics["connection_errors"] += 1
                self.offline_state = True
                _LOGGER.exception("Failed to establish connection: %s", exc)
                raise
            except TimeoutError as exc:
                self.statistics["connection_errors"] += 1
                self.offline_state = True
                _LOGGER.warning("Connection attempt timed out: %s", exc)
                raise
            except OSError as exc:
                self.statistics["connection_errors"] += 1
                self.offline_state = True
                _LOGGER.exception("Unexpected error establishing connection: %s", exc)
                raise

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device with optimized batch reading.

        This method overrides ``DataUpdateCoordinator._async_update_data``
        and is called by Home Assistant to refresh entity state.
        """
        return await _async_update_data_impl(self)

    def _find_register_name(self, register_type: str, address: int) -> str | None:
        """Find register name by address using pre-built reverse maps."""
        return _find_register_name_impl(self._reverse_maps, register_type, address)

    def _process_register_value(self, register_name: str, value: int) -> Any:
        """Decode a raw register value via dedicated register-processing helpers."""
        return _process_register_value_impl(register_name, value)

    async def _disconnect_locked(self) -> None:
        """Disconnect from Modbus device without acquiring locks."""

        if self._transport is not None:
            try:
                await self._transport.close()
            except (ModbusException, ConnectionException):
                _LOGGER.debug("Error disconnecting", exc_info=True)
            except OSError:
                _LOGGER.exception("Unexpected error disconnecting")
        elif self.client is not None:
            try:
                close = getattr(self.client, "close", None)
                if callable(close):
                    if inspect.iscoroutinefunction(close):
                        await close()
                    else:
                        result = close()
                        if inspect.isawaitable(result):
                            await result
            except (ModbusException, ConnectionException):
                _LOGGER.debug("Error disconnecting", exc_info=True)
            except OSError:
                _LOGGER.exception("Unexpected error disconnecting")

        self.client = None
        self.offline_state = True
        _LOGGER.debug("Disconnected from Modbus device")

    async def _disconnect(self) -> None:
        """Disconnect from Modbus device."""

        async with self._client_lock:
            await self._disconnect_locked()

    async def _async_handle_stop(self, _event: Any) -> None:
        """Handle Home Assistant stop to cancel tasks."""
        await self.async_shutdown()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
        if self._stop_listener is not None:
            self._stop_listener()
            self._stop_listener = None
        super_shutdown = getattr(super(), "async_shutdown", None)
        if callable(super_shutdown):
            result = super_shutdown()
            if inspect.isawaitable(result):
                await result
        await self._disconnect()

    @property
    def status_overview(self) -> dict[str, Any]:
        """Return a concise online/offline status summary."""
        return _status_overview_impl(self)

    @property
    def performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return _performance_stats_impl(self)

    def get_diagnostic_data(self) -> dict[str, Any]:
        """Return diagnostic information for Home Assistant."""
        return _get_diagnostic_data_impl(self)

    def get_device_info(self) -> dict[str, Any]:
        """Return device info mapping for the connected unit."""
        return _get_device_info_impl(self)


    @property
    def device_name(self) -> str:
        """Return the configured or detected device name."""
        return _device_name_impl(self)
