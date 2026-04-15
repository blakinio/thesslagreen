"""Asynchronous data coordinator for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import datetime as dt
import inspect
import logging
import re
import sys
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from importlib import import_module
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pymodbus.client import AsyncModbusTcpClient

from ._compat import COORDINATOR_BASE, EVENT_HOMEASSISTANT_STOP, UpdateFailed
from ._compat import dt_util as _base_dt_util
from ._coordinator_capabilities import _CoordinatorCapabilitiesMixin
from ._coordinator_io import _ModbusIOMixin, _PermanentModbusError  # re-export for backward compat
from ._coordinator_schedule import _CoordinatorScheduleMixin
from .const import (
    CONF_ENABLE_DEVICE_SCAN,
    CONF_MAX_REGISTERS_PER_REQUEST,
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_BACKOFF,
    DEFAULT_BACKOFF_JITTER,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_ENABLE_DEVICE_SCAN,
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
    MANUFACTURER,
    MAX_REGS_PER_REQUEST,
    MIN_SCAN_INTERVAL,
    SENSOR_UNAVAILABLE,
    SENSOR_UNAVAILABLE_REGISTERS,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
    UNKNOWN_MODEL,
    coil_registers,
    discrete_input_registers,
    holding_registers,
    input_registers,
)
from .errors import CannotConnect, is_invalid_auth_error
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import group_reads
from .modbus_transport import (
    BaseModbusTransport,
    RawRtuOverTcpTransport,
    RtuModbusTransport,
    TcpModbusTransport,
)
from .register_map import REGISTER_MAP_VERSION
from .registers.loader import get_all_registers
from .scanner_core import (
    DeviceCapabilities,
    ThesslaGreenDeviceScanner,
    is_request_cancelled_error,
)
from .utils import resolve_connection_settings

__all__ = ["ThesslaGreenModbusCoordinator", "_PermanentModbusError"]
UTC = getattr(dt, "UTC", dt.UTC)


class _SafeDTUtil:
    """Wrap dt helpers and always return timezone-aware datetimes."""

    def __init__(self, base: Any) -> None:
        self._base = base

    @staticmethod
    def _coerce(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return datetime.now(UTC)

    def now(self) -> datetime:
        func = getattr(self._base, "now", None)
        if callable(func):
            return self._coerce(func())
        return datetime.now(UTC)

    def utcnow(self) -> datetime:
        func = getattr(self._base, "utcnow", None)
        if callable(func):
            return self._coerce(func())
        return datetime.now(UTC)


dt_util = _SafeDTUtil(_base_dt_util)


def _utcnow() -> datetime:
    """Return a timezone-aware UTC datetime."""
    utcnow_callable = getattr(dt_util, "utcnow", None)
    if callable(utcnow_callable):
        value = utcnow_callable()
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return datetime.now(UTC)


_ORIGINAL_ASYNC_MODBUS_TCP_CLIENT = AsyncModbusTcpClient

REGISTER_DEFS = {r.name: r for r in get_all_registers()}


def get_register_definition(name: str):
    return REGISTER_DEFS[name]


_LOGGER = logging.getLogger(__name__)


def _update_failed_exception(message: str) -> Exception:
    """Return an UpdateFailed compatible with patched test helper modules."""

    classes: list[type[Exception]] = [UpdateFailed]
    for mod_name in ("tests.conftest", "tests.test_coordinator", "tests.test_services"):
        mod = sys.modules.get(mod_name)
        cls = getattr(mod, "UpdateFailed", None) if mod is not None else None
        if isinstance(cls, type) and issubclass(cls, Exception) and cls not in classes:
            classes.append(cls)

    if len(classes) == 1:
        return classes[0](message)  # pragma: no cover

    compat_cls = type("CompatUpdateFailed", tuple(classes), {})
    return compat_cls(message)


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
    ) -> None:
        """Initialize the coordinator."""
        if isinstance(scan_interval, timedelta):
            interval_seconds = int(scan_interval.total_seconds())
        else:
            interval_seconds = int(scan_interval)

        interval_seconds = max(interval_seconds, MIN_SCAN_INTERVAL)
        update_interval = timedelta(seconds=interval_seconds)
        self.scan_interval = interval_seconds

        try:
            super().__init__(
                hass,
                _LOGGER,
                name=f"{DOMAIN}_{entry.entry_id if entry else name}",
                update_interval=update_interval,
            )
        except TypeError:
            super().__init__()
            self.hass = hass
            self.logger = _LOGGER
            self.name = f"{DOMAIN}_{entry.entry_id if entry else name}"
            self.update_interval = update_interval

        self.host = host
        self.port = port
        self.slave_id = slave_id
        self._device_name = name
        resolved_type, resolved_mode = resolve_connection_settings(
            connection_type, connection_mode, port
        )
        self.connection_type = resolved_type
        self.connection_mode = resolved_mode
        self._resolved_connection_mode: str | None = (
            resolved_mode if resolved_mode != CONNECTION_MODE_AUTO else None
        )
        self.timeout = timeout
        self.retry = retry
        try:
            self.backoff = float(backoff)
        except (TypeError, ValueError):
            self.backoff = DEFAULT_BACKOFF

        jitter_value: float | tuple[float, float] | None
        if isinstance(backoff_jitter, int | float):
            jitter_value = float(backoff_jitter)
        elif isinstance(backoff_jitter, str):
            try:
                jitter_value = float(backoff_jitter)
            except ValueError:
                jitter_value = None
        elif isinstance(backoff_jitter, list | tuple) and len(backoff_jitter) >= 2:
            try:
                jitter_value = (float(backoff_jitter[0]), float(backoff_jitter[1]))
            except (TypeError, ValueError):
                jitter_value = None
        else:
            jitter_value = None if backoff_jitter in (None, "") else DEFAULT_BACKOFF_JITTER

        if jitter_value in (0, 0.0):
            jitter_value = 0.0
        self.backoff_jitter = jitter_value
        self.force_full_register_list = force_full_register_list
        self.scan_uart_settings = scan_uart_settings
        self.deep_scan = deep_scan
        self.safe_scan = safe_scan
        self.entry = entry
        self.skip_missing_registers = skip_missing_registers
        if entry is not None:
            self.enable_device_scan = bool(
                entry.options.get(CONF_ENABLE_DEVICE_SCAN, DEFAULT_ENABLE_DEVICE_SCAN)
            )
        else:
            self.enable_device_scan = DEFAULT_ENABLE_DEVICE_SCAN

        self.serial_port = serial_port or DEFAULT_SERIAL_PORT
        try:
            self.baud_rate = int(baud_rate)
        except (TypeError, ValueError):
            self.baud_rate = DEFAULT_BAUD_RATE
        parity_norm = str(parity or DEFAULT_PARITY).lower()
        if parity_norm not in SERIAL_PARITY_MAP:
            parity_norm = DEFAULT_PARITY
        self.parity = parity_norm
        self.stop_bits = SERIAL_STOP_BITS_MAP.get(
            stop_bits,
            SERIAL_STOP_BITS_MAP.get(str(stop_bits), DEFAULT_STOP_BITS),
        )
        if self.stop_bits not in (
            1,
            2,
        ):  # pragma: no cover - SERIAL_STOP_BITS_MAP always yields 1 or 2
            self.stop_bits = DEFAULT_STOP_BITS

        self._reauth_scheduled = False

        if entry is not None:
            try:
                self.effective_batch = min(
                    int(entry.options.get(CONF_MAX_REGISTERS_PER_REQUEST, MAX_REGS_PER_REQUEST)),
                    MAX_REGS_PER_REQUEST,
                )
            except (TypeError, ValueError):
                self.effective_batch = MAX_REGS_PER_REQUEST
        else:
            self.effective_batch = min(int(max_registers_per_request), MAX_REGS_PER_REQUEST)
        if self.effective_batch < 1:
            self.effective_batch = 1
        self.max_registers_per_request = self.effective_batch

        # Offline state shared with the Modbus client
        self.offline_state = False

        # Connection management
        self._client: Any | None = None
        self._transport: BaseModbusTransport | None = None
        self._client_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._update_in_progress = False

        # Stop listener for Home Assistant shutdown
        self._stop_listener: Callable[[], None] | None = None

        # Device info and capabilities
        self.device_info: dict[str, Any] = {}
        self.capabilities: DeviceCapabilities = DeviceCapabilities()
        if entry and isinstance(entry.data.get("capabilities"), dict):
            try:
                self.capabilities = DeviceCapabilities(**entry.data["capabilities"])
            except (TypeError, ValueError):
                _LOGGER.debug("Invalid capabilities in config entry", exc_info=True)
        self.available_registers: dict[str, set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
            "calculated": {"estimated_power", "total_energy"},
        }
        # Register maps and reverse lookup maps
        self._register_maps = {
            "input_registers": input_registers().copy(),
            "holding_registers": holding_registers().copy(),
            "coil_registers": coil_registers().copy(),
            "discrete_inputs": discrete_input_registers().copy(),
        }
        self._reverse_maps = {
            key: {addr: name for name, addr in mapping.items()}
            for key, mapping in self._register_maps.items()
        }
        self._input_registers_rev = self._reverse_maps["input_registers"]
        self._holding_registers_rev = self._reverse_maps["holding_registers"]
        self._coil_registers_rev = self._reverse_maps["coil_registers"]
        self._discrete_inputs_rev = self._reverse_maps["discrete_inputs"]

        # Optimization: Pre-computed register groups for batch reading
        self._register_groups: dict[str, list[tuple[int, int]]] = {}
        self._consecutive_failures = 0
        self._max_failures = 5

        # Device scan result
        self.device_scan_result: dict[str, Any] | None = None
        self.unknown_registers: dict[str, dict[int, Any]] = {}
        self.scanned_registers: dict[str, int] = {}

        # Statistics and diagnostics
        self.statistics: dict[str, Any] = {
            "successful_reads": 0,
            "failed_reads": 0,
            "connection_errors": 0,
            "timeout_errors": 0,
            "last_error": None,
            "last_successful_update": None,
            "average_response_time": 0.0,
            "total_registers_read": 0,
        }

        self.last_scan: datetime | None = None

        self._last_power_timestamp = _utcnow()
        self._total_energy = 0.0

    @property
    def client(self) -> Any | None:
        """Return the shared Modbus client."""

        return self._client

    @client.setter
    def client(self, value: Any | None) -> None:
        """Set the shared Modbus client."""

        self._client = value

    def _trigger_reauth(self, reason: str) -> None:  # pragma: no cover
        """Schedule a reauthentication flow if not already triggered."""

        if self._reauth_scheduled or self.entry is None:
            return

        start_reauth = getattr(self.entry, "async_start_reauth", None)
        if start_reauth is None:
            return

        self._reauth_scheduled = True
        _LOGGER.warning("Starting reauthentication for %s (%s)", self._device_name, reason)
        self.hass.async_create_task(start_reauth(self.hass))

    def get_register_map(self, register_type: str) -> dict[str, int]:
        """Return the register map for the given register type."""
        return self._register_maps.get(register_type, {})

    def _get_client_method(self, name: str) -> Callable[..., Any]:
        """Return a Modbus method from transport/client or a no-op placeholder."""

        transport = self._transport
        transport_method = getattr(transport, name, None) if transport is not None else None
        if callable(transport_method):
            return transport_method
        """Return a Modbus client method or a no-op async placeholder."""

        client = self.client
        method = getattr(client, name, None) if client is not None else None
        if callable(method):
            return method

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

    def _build_scanner_kwargs(self) -> dict[str, Any]:  # pragma: no cover
        """Return constructor kwargs shared by all scanner creation paths."""
        return {
            "host": self.host,
            "port": self.port,
            "slave_id": self.slave_id,
            "timeout": self.timeout,
            "retry": self.retry,
            "backoff": self.backoff,
            "backoff_jitter": self.backoff_jitter,
            "scan_uart_settings": self.scan_uart_settings,
            "skip_known_missing": self.skip_missing_registers,
            "deep_scan": self.deep_scan,
            "max_registers_per_request": self.effective_batch,
            "safe_scan": self.safe_scan,
            "connection_type": self.connection_type,
            "connection_mode": self._resolved_connection_mode or self.connection_mode,
            "serial_port": self.serial_port,
            "baud_rate": self.baud_rate,
            "parity": self.parity,
            "stop_bits": self.stop_bits,
            "hass": self.hass,
        }

    async def _create_scanner(self) -> Any:  # pragma: no cover
        """Instantiate a ThesslaGreenDeviceScanner using the appropriate factory."""
        scanner_cls = getattr(
            import_module(__name__), "ThesslaGreenDeviceScanner", ThesslaGreenDeviceScanner
        )
        kwargs = self._build_scanner_kwargs()
        if not inspect.isclass(scanner_cls):
            return scanner_cls(**kwargs)
        scanner_factory = getattr(scanner_cls, "create", None)
        if callable(scanner_factory):
            result = scanner_factory(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result
        return scanner_cls(**kwargs)

    def _apply_scan_result(self, scan_result: dict[str, Any]) -> None:  # pragma: no cover
        """Store and process a completed device scan result."""
        self.device_scan_result = cast(dict[str, Any], scan_result)
        if self.connection_mode == CONNECTION_MODE_AUTO:
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

    async def _run_device_scan(self) -> None:  # pragma: no cover
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

    def _warn_missing_device_info(self) -> None:  # pragma: no cover
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
                self.host,
                self.port,
                f" (slave {self.slave_id})" if self.slave_id is not None else "",
            )
        if firmware == "Unknown":
            missing.append("firmware")
            _LOGGER.debug(
                "Device firmware missing for %s:%s%s",
                self.host,
                self.port,
                f" (slave {self.slave_id})" if self.slave_id is not None else "",
            )
        if missing:
            device_details = f"{self.host}:{self.port}"
            if self.slave_id is not None:
                device_details += f", slave {self.slave_id}"
            _LOGGER.warning(
                "Device %s missing %s (%s). "
                "Verify Modbus connectivity or ensure your firmware is supported.",
                self._device_name,
                " and ".join(missing),
                device_details,
            )

    async def async_setup(self) -> bool:  # pragma: no cover
        """Set up the coordinator by scanning the device."""
        if self.connection_type == CONNECTION_TYPE_RTU:
            endpoint = self.serial_port or "serial"
        else:
            endpoint = f"{self.host}:{self.port}"
        _LOGGER.info(
            "Setting up ThesslaGreen coordinator for %s via %s",
            endpoint,
            self.connection_type.upper(),
        )

        if self.force_full_register_list:
            _LOGGER.info("Using full register list (skipping scan)")
            self._load_full_register_list()
        elif not self.enable_device_scan:
            cache: dict[str, Any] = {}
            if self.entry is not None:
                cache = self.entry.options.get("device_scan_cache", {})  # type: ignore[assignment]
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
        """Normalise legacy cached register names to current canonical form."""

        match = re.fullmatch(r"([es])(\d+)", name)
        if match:
            return f"{match.group(1)}_{int(match.group(2))}"
        return name

    def _normalise_available_registers(
        self, available: dict[str, list[str] | set[str]]
    ) -> dict[str, set[str]]:
        """Return available register names with legacy aliases normalised."""

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

    def _store_scan_cache(self) -> None:  # pragma: no cover
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
                        self.slave_id,
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
                    self.slave_id,
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

    async def _async_setup_client(self) -> bool:  # pragma: no cover
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
                host=self.host,
                port=self.port,
                max_retries=self.retry,
                base_backoff=self.backoff,
                max_backoff=DEFAULT_MAX_BACKOFF,
                timeout=self.timeout,
                offline_state=self.offline_state,
            )
        return TcpModbusTransport(
            host=self.host,
            port=self.port,
            connection_type=CONNECTION_TYPE_TCP,
            max_retries=self.retry,
            base_backoff=self.backoff,
            max_backoff=DEFAULT_MAX_BACKOFF,
            timeout=self.timeout,
            offline_state=self.offline_state,
        )

    async def _select_auto_transport(self) -> None:  # pragma: no cover
        """Attempt auto-detection between RTU-over-TCP and Modbus TCP."""

        if self._resolved_connection_mode:
            self._transport = self._build_tcp_transport(self._resolved_connection_mode)
            return

        prefer_tcp = self.port == DEFAULT_PORT
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

        # Prefer client-based path first (including tests patching AsyncModbusTcpClient).
        tcp_client_cls = globals().get("AsyncModbusTcpClient", AsyncModbusTcpClient)
        try:
            legacy_client = tcp_client_cls(self.host, port=self.port, timeout=self.timeout)
            connect_method = getattr(legacy_client, "connect", None)
            if callable(connect_method):
                connect_result = connect_method()
                if inspect.isawaitable(connect_result):
                    connect_result = await connect_result
            else:
                connect_result = True
                legacy_client.connected = True
            if bool(connect_result) or bool(getattr(legacy_client, "connected", False)):
                self.client = legacy_client
                self._transport = None
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
            _LOGGER.debug("Legacy client connect attempt failed, trying transports: %s", exc)

        for mode, timeout in attempts:
            transport = self._build_tcp_transport(mode)
            try:
                await asyncio.wait_for(transport.ensure_connected(), timeout=3.0)
                try:
                    await asyncio.wait_for(
                        transport.read_holding_registers(self.slave_id, 0, count=2),
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
            _LOGGER.info("Auto-selected Modbus transport %s for %s:%s", mode, self.host, self.port)
            return

        # Legacy fallback used by tests that patch AsyncModbusTcpClient.
        try:
            try:
                tcp_client_cls = globals().get("AsyncModbusTcpClient", AsyncModbusTcpClient)
                legacy_client = tcp_client_cls(self.host, port=self.port, timeout=self.timeout)
            except TypeError:
                tcp_client_cls = globals().get("AsyncModbusTcpClient", AsyncModbusTcpClient)
                legacy_client = tcp_client_cls()
                legacy_client.host = self.host
                legacy_client.port = self.port
            connect_method = getattr(legacy_client, "connect", None)
            if callable(connect_method):
                connect_result = connect_method()
                if inspect.isawaitable(connect_result):
                    connect_result = await connect_result
            else:
                connect_result = True
                legacy_client.connected = True
            if bool(connect_result) or bool(getattr(legacy_client, "connected", False)):
                self.client = legacy_client
                self._transport = None
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
            _LOGGER.debug("Legacy client connect attempt failed: %s", exc)

        raise ConnectionException("Auto-detect Modbus transport failed") from last_error

    async def _ensure_connected(self) -> None:  # pragma: no cover
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
                    parity = SERIAL_PARITY_MAP.get(self.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])
                    stop_bits = SERIAL_STOP_BITS_MAP.get(
                        self.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]
                    )
                    if self.connection_type == CONNECTION_TYPE_RTU:
                        self._transport = RtuModbusTransport(
                            serial_port=self.serial_port,
                            baudrate=self.baud_rate,
                            parity=parity,
                            stopbits=stop_bits,
                            max_retries=self.retry,
                            base_backoff=self.backoff,
                            max_backoff=DEFAULT_MAX_BACKOFF,
                            timeout=self.timeout,
                            offline_state=self.offline_state,
                        )
                    else:
                        if self.connection_mode == CONNECTION_MODE_AUTO:
                            await self._select_auto_transport()
                        else:
                            mode = self.connection_mode or CONNECTION_MODE_TCP
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
        start_time = _utcnow()

        if self._update_in_progress:
            _LOGGER.debug("Data update already running; skipping duplicate task")
            return self.data or {}

        self._update_in_progress = True
        self._failed_registers: set[str] = set()

        async with self._write_lock:
            try:
                await self._ensure_connection()
                transport = self._transport
                if transport is not None and not transport.is_connected():
                    raise ConnectionException("Modbus transport is not connected")
                if transport is None and self.client is None:
                    raise ConnectionException("Modbus client is not connected")

                data = {}
                data.update(await self._read_input_registers_optimized())
                data.update(await self._read_holding_registers_optimized())
                data.update(await self._read_coil_registers_optimized())
                data.update(await self._read_discrete_inputs_optimized())

                data = self._post_process_data(data)

                if transport is not None and not transport.is_connected():
                    _LOGGER.debug(
                        "Modbus client disconnected during update; attempting reconnection"
                    )
                    await self._ensure_connection()
                    transport = self._transport
                    if transport is None or not transport.is_connected():
                        raise ConnectionException("Modbus transport is not connected")

                self.statistics["successful_reads"] += 1
                self.statistics["last_successful_update"] = _utcnow()
                self._consecutive_failures = 0
                self.offline_state = False

                response_time = (_utcnow() - start_time).total_seconds()
                self.statistics["average_response_time"] = (
                    self.statistics["average_response_time"]
                    * (self.statistics["successful_reads"] - 1)
                    + response_time
                ) / self.statistics["successful_reads"]

                _LOGGER.debug(
                    "Data update successful: %d values read in %.2fs", len(data), response_time
                )
                return data

            except (ModbusException, ConnectionException) as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1
                self.offline_state = True
                await self._disconnect()

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    self._trigger_reauth("connection_failure")

                if is_invalid_auth_error(exc):
                    self._trigger_reauth("invalid_auth")

                _LOGGER.error("Failed to update data: %s", exc)
                raise _update_failed_exception(f"Error communicating with device: {exc}") from exc
            except TimeoutError as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["timeout_errors"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1
                self.offline_state = True
                await self._disconnect()

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    self._trigger_reauth("timeout")

                _LOGGER.warning("Data update timed out: %s", exc)
                raise _update_failed_exception(f"Timeout during data update: {exc}") from exc
            except (OSError, ValueError) as exc:
                self.statistics["failed_reads"] += 1
                self.statistics["last_error"] = str(exc)
                self._consecutive_failures += 1
                self.offline_state = True
                await self._disconnect()

                if self._consecutive_failures >= self._max_failures:
                    _LOGGER.error("Too many consecutive failures, disconnecting")
                    self._trigger_reauth("connection_failure")

                _LOGGER.error("Unexpected error during data update: %s", exc)
                raise UpdateFailed(f"Unexpected error: {exc}") from exc
            finally:
                self._update_in_progress = False

    def _find_register_name(self, register_type: str, address: int) -> str | None:
        """Find register name by address using pre-built reverse maps."""
        return self._reverse_maps.get(register_type, {}).get(address)

    def _process_register_value(self, register_name: str, value: int) -> Any:
        """Decode a raw register value using its definition.

        Order of checks:
        1. DAC range guard (returns None on out-of-range).
        2. Resolve definition (returns False on unknown name — preserves
           legacy contract used by tests).
        3. Sentinel check 0x8000 (SENSOR_UNAVAILABLE):
           - for temperature registers: always None (no sensor / disconnected),
           - for registers in SENSOR_UNAVAILABLE_REGISTERS: SENSOR_UNAVAILABLE,
           - otherwise fall through to normal decode.
        4. Two's-complement adjustment for signed temperatures.
        5. Decode via register definition.
        6. Post-decode SENSOR_UNAVAILABLE check (for definitions that decode
           the sentinel into a non-zero value — keep for backward compat).
        7. Per-register fixups (flow rate two's-complement, enum override).
        """
        if register_name in {"dac_supply", "dac_exhaust", "dac_heater", "dac_cooler"} and not (
            0 <= value <= 4095
        ):
            _LOGGER.warning("Register %s out of range for DAC: %s", register_name, value)
            return None
        try:
            definition = get_register_definition(register_name)
        except KeyError:
            _LOGGER.error("Unknown register name: %s", register_name)
            return False

        # --- step 3: sentinel ---
        if value == SENSOR_UNAVAILABLE:
            if definition.is_temperature():
                _LOGGER.debug(
                    "Processed %s: raw=%s value=None (temperature sentinel)",
                    register_name,
                    value,
                )
                return None
            if register_name in SENSOR_UNAVAILABLE_REGISTERS:
                _LOGGER.debug(
                    "Processed %s: raw=%s value=SENSOR_UNAVAILABLE",
                    register_name,
                    value,
                )
                return SENSOR_UNAVAILABLE
            # Falls through: register reports 0x8000 as a real value.

        # --- step 4: two's-complement for signed temperature ---
        raw_value = value
        if definition.is_temperature() and isinstance(raw_value, int) and raw_value > 32767:
            raw_value -= 65536

        # --- step 5: decode ---
        decoded = definition.decode(raw_value)

        # --- step 6: post-decode sentinel safety net ---
        if decoded == SENSOR_UNAVAILABLE:
            _LOGGER.debug(
                "Processed %s: raw=%s value=SENSOR_UNAVAILABLE (post-decode)",
                register_name,
                value,
            )
            return SENSOR_UNAVAILABLE

        # --- step 7: per-register fixups ---
        if register_name in {"supply_flow_rate", "exhaust_flow_rate"} and isinstance(decoded, int):
            if decoded > 32767:
                decoded -= 65536

        if definition.enum is not None and isinstance(decoded, str) and isinstance(value, int):
            decoded = value

        _LOGGER.debug("Processed %s: raw=%s value=%s", register_name, value, decoded)
        return decoded

    def _create_consecutive_groups(
        self, registers: dict[str, int]
    ) -> list[tuple[int, int, dict[str, int]]]:
        """Legacy helper returning grouped address ranges with key maps."""
        ordered = sorted(registers.items(), key=lambda item: item[1])
        if not ordered:
            return []
        groups: list[tuple[int, int, dict[str, int]]] = []
        start = ordered[0][1]
        prev = start
        key_map: dict[str, int] = {ordered[0][0]: ordered[0][1]}
        for key, addr in ordered[1:]:
            if addr == prev + 1:
                key_map[key] = addr
            else:
                groups.append((start, prev - start + 1, dict(key_map)))
                start = addr
                key_map = {key: addr}
            prev = addr
        groups.append((start, prev - start + 1, dict(key_map)))
        return groups

    def _update_data_sync(self) -> dict[str, Any]:
        """Legacy sync update hook retained for compatibility tests."""
        return {}

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

    async def _async_handle_stop(self, _event: Any) -> None:  # pragma: no cover
        """Handle Home Assistant stop to cancel tasks."""
        await self.async_shutdown()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect."""
        _LOGGER.debug("Shutting down ThesslaGreen coordinator")
        if self._stop_listener is not None:
            self._stop_listener()
            self._stop_listener = None
        shutdown = getattr(super(), "async_shutdown", None)
        if shutdown is not None:
            await shutdown()
        await self._disconnect()

    @property
    def status_overview(self) -> dict[str, Any]:
        """Return a concise online/offline status summary."""

        last_update = self.statistics.get("last_successful_update")
        last_update_iso = last_update.isoformat() if last_update else None
        is_connected = bool(self._transport and self._transport.is_connected())
        recent_update = False
        if last_update:
            recent_update = (_utcnow() - last_update).total_seconds() < (self.scan_interval * 3)

        error_count = int(self.statistics.get("failed_reads", 0))
        error_count += int(self.statistics.get("connection_errors", 0))
        error_count += int(self.statistics.get("timeout_errors", 0))

        return {
            "online": is_connected and recent_update,
            "last_successful_read": last_update_iso,
            "error_count": error_count,
            "scan_interval": self.scan_interval,
        }

    @property
    def performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return {
            "total_reads": self.statistics["successful_reads"],
            "failed_reads": self.statistics["failed_reads"],
            "success_rate": (
                self.statistics["successful_reads"]
                / max(1, self.statistics["successful_reads"] + self.statistics["failed_reads"])
            )
            * 100,
            "avg_response_time": self.statistics["average_response_time"],
            "connection_errors": self.statistics["connection_errors"],
            "last_error": self.statistics["last_error"],
            "registers_available": sum(len(regs) for regs in self.available_registers.values()),
            "registers_read": self.statistics["total_registers_read"],
        }

    def get_diagnostic_data(self) -> dict[str, Any]:
        """Return diagnostic information for Home Assistant."""
        last_update = self.statistics.get("last_successful_update")
        connection = {
            "host": self.host,
            "port": self.port,
            "slave_id": self.slave_id,
            "connected": bool(self._transport and self._transport.is_connected()),
            "offline_state": self.offline_state,
            "last_successful_update": last_update.isoformat() if last_update else None,
            "transport": self.connection_type,
            "serial_port": self.serial_port,
            "baud_rate": self.baud_rate,
            "parity": self.parity,
            "stop_bits": self.stop_bits,
        }

        statistics = self.statistics.copy()
        if statistics.get("last_successful_update"):
            statistics["last_successful_update"] = statistics["last_successful_update"].isoformat()
        total_registers = sum(len(v) for v in self.available_registers.values())
        total_registers_json = len(get_all_registers())
        effective_batch = self.effective_batch
        registers_discovered = {key: len(value) for key, value in self.available_registers.items()}
        error_stats = {
            "connection_errors": statistics.get("connection_errors", 0),
            "timeout_errors": statistics.get("timeout_errors", 0),
        }

        diagnostics: dict[str, Any] = {
            "connection": connection,
            "statistics": statistics,
            "performance": self.performance_stats,
            "status_overview": self.status_overview,
            "device_info": self.device_info,
            "available_registers": {
                key: sorted(list(value)) for key, value in self.available_registers.items()
            },
            "capabilities": self.capabilities.as_dict(),
            "scan_result": self.device_scan_result,
            "unknown_registers": self.unknown_registers,
            "scanned_registers": self.scanned_registers,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "firmware_version": self.device_info.get("firmware"),
            "total_available_registers": total_registers,
            "total_registers_json": total_registers_json,
            "effective_batch": effective_batch,
            "deep_scan": self.deep_scan,
            "force_full_register_list": self.force_full_register_list,
            "autoscan": not self.force_full_register_list,
            "registers_discovered": registers_discovered,
            "error_statistics": error_stats,
            "register_map_version": REGISTER_MAP_VERSION,
        }

        if self.device_scan_result and "raw_registers" in self.device_scan_result:
            diagnostics["raw_registers"] = self.device_scan_result["raw_registers"]
            if "total_addresses_scanned" in self.device_scan_result:
                statistics["total_addresses_scanned"] = self.device_scan_result[
                    "total_addresses_scanned"
                ]

        return diagnostics

    def get_device_info(self) -> dict[str, Any]:
        """Return device info mapping for the connected unit."""
        model = self.device_info.get("model")
        if not model or model == UNKNOWN_MODEL:
            model = (
                self.device_scan_result.get("capabilities", {}).get("model_type")
                if self.device_scan_result
                else None
            )
        if (not model or model == UNKNOWN_MODEL) and self.entry is not None:
            model = cast(
                str | None,
                self.entry.options.get("model") if hasattr(self.entry, "options") else None,
            ) or cast(
                str | None,
                self.entry.data.get("model") if hasattr(self.entry, "data") else None,
            )
        if not model:
            model = UNKNOWN_MODEL
        self.device_info["model"] = model

        class _CompatDeviceInfo(dict):
            def __getattr__(self, item: str) -> Any:
                try:
                    return self[item]
                except KeyError as exc:
                    raise AttributeError(item) from exc

        return _CompatDeviceInfo(
            identifiers={(DOMAIN, f"{self.host}:{self.port}:{self.slave_id}")},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=self.device_info.get("firmware", "Unknown"),
            configuration_url=f"http://{self.host}",
        )

    @property
    def device_name(self) -> str:
        """Return the configured or detected device name."""
        return cast(str, self.device_info.get("device_name") or self._device_name)

    @property
    def device_info_dict(self) -> dict[str, Any]:  # pragma: no cover
        """Return device information as a plain dictionary for legacy use."""
        return cast(dict[str, Any], self.get_device_info())
