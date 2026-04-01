"""Device scanner for ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import collections.abc
import inspect
import logging
import importlib
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

try:  # pragma: no cover - optional during isolated tests
    from .registers.loader import (
        async_get_all_registers,
        async_registers_sha256,
        get_all_registers,
        get_registers_path,
        registers_sha256,
    )
except (ImportError, AttributeError):  # pragma: no cover - fallback when stubs incomplete

    async def async_get_all_registers(*_args, **_kwargs):
        return []

    async def async_registers_sha256(*_args, **_kwargs) -> str:
        return ""

    def get_all_registers(*_args, **_kwargs):
        return []

    def get_registers_path(*_args, **_kwargs) -> Path:
        return Path(".")

    def registers_sha256(*_args, **_kwargs) -> str:
        return ""



_LOGGER = logging.getLogger(__name__)

try:
    _pymodbus = importlib.import_module("pymodbus")
    _pymodbus_client = importlib.import_module("pymodbus.client")
    if not hasattr(_pymodbus, "client"):
        setattr(_pymodbus, "client", _pymodbus_client)  # pragma: no cover
except Exception as _exc:  # pragma: no cover
    _LOGGER.debug("Could not attach pymodbus.client submodule: %s", _exc)

from . import modbus_helpers as _mh
from .capability_rules import CAPABILITY_PATTERNS
from .const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_BAUD_RATE,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_UART_SETTINGS,
    DEFAULT_SERIAL_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_STOP_BITS,
    KNOWN_MISSING_REGISTERS,
    SENSOR_UNAVAILABLE,
    SENSOR_UNAVAILABLE_REGISTERS,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
    UNKNOWN_MODEL,
)
from .modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from .modbus_helpers import (
    _call_modbus,
    async_maybe_await_close,
    chunk_register_range,
)
from .modbus_helpers import group_reads as _group_reads
from .modbus_transport import (
    BaseModbusTransport,
    RawRtuOverTcpTransport,
    RtuModbusTransport,
    TcpModbusTransport,
)
from .scanner_helpers import (
    MAX_BATCH_REGISTERS,
    REGISTER_ALLOWED_VALUES,
    SAFE_REGISTERS,
    UART_OPTIONAL_REGS,
    _format_register_value,
)
from .utils import (
    BCD_TIME_PREFIXES,
    decode_bcd_time,
    default_connection_mode,
    resolve_connection_settings,
)

try:  # pragma: no cover - network transport always required
    from pymodbus.client import AsyncModbusTcpClient
except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover - fatal
    raise ImportError("pymodbus AsyncModbusTcpClient is required") from exc

if TYPE_CHECKING:  # pragma: no cover - typing helper only
    from pymodbus.client import AsyncModbusSerialClient as AsyncModbusSerialClientType
else:
    AsyncModbusSerialClientType = Any


def _ensure_pymodbus_client_module() -> None:
    """Ensure `pymodbus.client` is importable and attached to `pymodbus`."""
    try:
        pymodbus_mod = importlib.import_module("pymodbus")
        client_mod = importlib.import_module("pymodbus.client")
    except Exception:
        return
    if not hasattr(pymodbus_mod, "client"):
        setattr(pymodbus_mod, "client", client_mod)
    if hasattr(client_mod, "AsyncModbusTcpClient") and not hasattr(client_mod, "ModbusTcpClient"):
        setattr(client_mod, "ModbusTcpClient", getattr(client_mod, "AsyncModbusTcpClient"))


# Register definition caches - populated lazily
REGISTER_DEFINITIONS: dict[str, Any] = {}
INPUT_REGISTERS: dict[str, int] = {}
HOLDING_REGISTERS: dict[str, int] = {}
COIL_REGISTERS: dict[str, int] = {}


def is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Return True when a modbus IO error indicates a cancelled request."""

    message = str(exc).lower()
    return "request cancelled outside pymodbus" in message or "cancelled" in message


async def _maybe_retry_yield(backoff: float, attempt: int, retry: int) -> None:
    """Yield control between retries to allow cancellation to propagate."""

    if attempt >= retry or backoff > 0:
        return

    await asyncio.sleep(0)


async def _call_modbus_compat(
    func: Any,
    slave_id: int,
    address: int,
    *,
    count: int,
    attempt: int,
    retry: int,
    timeout: int,
    backoff: float,
    backoff_jitter: float | tuple[float, float] | None,
    apply_backoff: bool = True,
) -> Any:
    """Call `_call_modbus` with rich kwargs, fallback to minimal mock signatures."""

    try:
        return await _call_modbus(
            func,
            slave_id,
            address,
            count=count,
            attempt=attempt,
            max_attempts=retry,
            timeout=timeout,
            backoff=0.0,
            backoff_jitter=None,
            apply_backoff=False,
        )
    except TypeError as exc:
        if "unexpected keyword" not in str(exc):
            raise
        return await _call_modbus(func, slave_id, address, count=count)


async def _sleep_retry_backoff(
    *, backoff: float, backoff_jitter: float | tuple[float, float] | None, attempt: int, retry: int
) -> None:
    """Sleep between retries using modbus_helpers timing semantics."""
    if attempt >= retry:
        return
    delay = _mh._calculate_backoff_delay(base=backoff, attempt=attempt + 1, jitter=backoff_jitter)
    if delay > 0:
        await asyncio.sleep(delay)
    else:
        await _maybe_retry_yield(backoff=backoff, attempt=attempt, retry=retry)



DISCRETE_INPUT_REGISTERS: dict[str, int] = {}
MULTI_REGISTER_SIZES: dict[str, int] = {}
REGISTER_HASH: str | None = None


def _build_register_maps_from(regs: list[Any], register_hash: str) -> None:
    """Populate register lookup maps from provided register definitions."""
    global REGISTER_HASH
    REGISTER_HASH = register_hash

    REGISTER_DEFINITIONS.clear()
    REGISTER_DEFINITIONS.update({r.name: r for r in regs})

    INPUT_REGISTERS.clear()
    INPUT_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == 4}
    )

    HOLDING_REGISTERS.clear()
    HOLDING_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == 3}
    )

    COIL_REGISTERS.clear()
    COIL_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == 1}
    )

    DISCRETE_INPUT_REGISTERS.clear()
    DISCRETE_INPUT_REGISTERS.update(
        {name: reg.address for name, reg in REGISTER_DEFINITIONS.items() if reg.function == 2}
    )

    MULTI_REGISTER_SIZES.clear()
    MULTI_REGISTER_SIZES.update(
        {
            name: reg.length
            for name, reg in REGISTER_DEFINITIONS.items()
            if reg.function == 3 and reg.length > 1
        }
    )


def _build_register_maps() -> None:
    """Populate register lookup maps from current register definitions."""
    regs = get_all_registers()
    register_hash = registers_sha256(get_registers_path())
    _build_register_maps_from(regs, register_hash)


async def _async_build_register_maps(hass: Any | None) -> None:
    """Populate register lookup maps from current definitions asynchronously."""
    register_hash = await async_registers_sha256(hass, get_registers_path())
    regs = await async_get_all_registers(hass)
    _build_register_maps_from(regs, register_hash)


# Ensure register lookup maps are available before use
def _ensure_register_maps() -> None:
    """Ensure register lookup maps are populated."""
    current_hash = registers_sha256(get_registers_path())
    if not REGISTER_DEFINITIONS or current_hash != REGISTER_HASH:
        _build_register_maps()


async def _async_ensure_register_maps(hass: Any | None) -> None:
    """Ensure register lookup maps are populated without blocking the event loop."""
    register_hash = await async_registers_sha256(hass, get_registers_path())
    if not REGISTER_DEFINITIONS or register_hash != REGISTER_HASH:
        await _async_build_register_maps(hass)


async def async_ensure_register_maps(hass: Any | None = None) -> None:
    """Ensure register lookup maps are populated without blocking the event loop."""
    await _async_ensure_register_maps(hass)


@dataclass(slots=True)
class ScannerDeviceInfo(collections.abc.Mapping):  # pragma: no cover
    """Basic identifying information about a ThesslaGreen unit.

    The attributes are populated dynamically and accessed via ``as_dict`` in
    diagnostics; they therefore appear unused in static analysis.

    Attributes:
        device_name: User configured name reported by the unit.
        model: Reported model name used to identify the device type.
        firmware: Firmware version string for compatibility checks.
        serial_number: Unique hardware identifier for the unit.
    """

    device_name: str = "Unknown"
    model: str = UNKNOWN_MODEL
    firmware: str = "Unknown"
    serial_number: str = "Unknown"
    firmware_available: bool = True  # pragma: no cover
    capabilities: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def items(self):
        return self.as_dict().items()

    def keys(self):
        return self.as_dict().keys()

    def values(self):
        return self.as_dict().values()

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self):
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


# Attributes of this dataclass are read dynamically at runtime to determine
# which features the device exposes; static analysis may therefore mark them
# as unused even though they are relied upon.
@dataclass(slots=True)
class DeviceCapabilities(collections.abc.Mapping):  # pragma: no cover
    """Feature flags and sensor availability detected on the device.

    Although capabilities are typically determined once during the initial scan,
    the dataclass caches the result of :meth:`as_dict` for efficiency. Any
    attribute assignment will clear this cache so subsequent calls reflect the
    new values. The capability sets are mutable; modify them via assignment to
    trigger cache invalidation.
    """

    basic_control: bool = False
    temperature_sensors: set[str] = field(default_factory=set)  # Names of temperature sensors
    flow_sensors: set[str] = field(
        default_factory=set
    )  # Airflow sensor identifiers  # pragma: no cover
    special_functions: set[str] = field(
        default_factory=set
    )  # Optional feature flags  # pragma: no cover
    expansion_module: bool = False  # pragma: no cover
    constant_flow: bool = False  # pragma: no cover
    gwc_system: bool = False  # pragma: no cover
    bypass_system: bool = False  # pragma: no cover
    heating_system: bool = False  # pragma: no cover
    cooling_system: bool = False  # pragma: no cover
    air_quality: bool = False  # pragma: no cover
    weekly_schedule: bool = False  # pragma: no cover
    sensor_outside_temperature: bool = False  # pragma: no cover
    sensor_supply_temperature: bool = False  # pragma: no cover
    sensor_exhaust_temperature: bool = False  # pragma: no cover
    sensor_fpx_temperature: bool = False  # pragma: no cover
    sensor_duct_supply_temperature: bool = False  # pragma: no cover
    sensor_gwc_temperature: bool = False  # pragma: no cover
    sensor_ambient_temperature: bool = False  # pragma: no cover
    sensor_heating_temperature: bool = False  # pragma: no cover
    temperature_sensors_count: int = 0  # pragma: no cover
    _as_dict_cache: dict[str, Any] | None = field(init=False, repr=False, default=None)

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: D401 - simple cache invalidation
        """Set attribute and invalidate cached ``as_dict`` result."""
        if name != "_as_dict_cache" and getattr(self, "_as_dict_cache", None) is not None:
            object.__setattr__(self, "_as_dict_cache", None)
        object.__setattr__(self, name, value)

    def as_dict(self) -> dict[str, Any]:
        """Return capabilities as a dictionary with set values sorted.

        The result is cached on first call to avoid repeated ``dataclasses.asdict``
        invocations when capabilities are accessed multiple times.
        """

        if self._as_dict_cache is None:
            data = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
            for key, value in data.items():
                if isinstance(value, set):
                    data[key] = sorted(value)
            object.__setattr__(self, "_as_dict_cache", data)
        return self._as_dict_cache

    def items(self):
        return self.as_dict().items()

    def keys(self):
        return self.as_dict().keys()

    def values(self):
        return self.as_dict().values()

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self):
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


class ThesslaGreenDeviceScanner:
    """Device scanner for ThesslaGreen AirPack Home - compatible with pymodbus 3.5.*+"""

    def __init__(
        self,
        host: str,
        port: int,
        slave_id: int = DEFAULT_SLAVE_ID,
        timeout: int = 10,
        retry: int = 3,
        backoff: float = 0,
        backoff_jitter: float | tuple[float, float] | None = None,
        verbose_invalid_values: bool = False,
        scan_uart_settings: bool = DEFAULT_SCAN_UART_SETTINGS,
        skip_known_missing: bool = False,
        deep_scan: bool = False,
        full_register_scan: bool = False,
        safe_scan: bool = False,
        max_registers_per_request: int = MAX_BATCH_REGISTERS,
        connection_type: str = DEFAULT_CONNECTION_TYPE,
        connection_mode: str | None = None,
        serial_port: str = DEFAULT_SERIAL_PORT,
        baud_rate: int = DEFAULT_BAUD_RATE,
        parity: str = DEFAULT_PARITY,
        stop_bits: int = DEFAULT_STOP_BITS,
        *,
        hass: Any | None = None,
        registers_ready: bool = False,
    ) -> None:
        """Initialize device scanner with consistent parameter names.

        ``max_registers_per_request`` is clamped to the safe Modbus range of
        1-16 registers per request.
        """
        if not registers_ready:
            _ensure_register_maps()
        # Avoid sticky logger levels from previous tests/services.
        _LOGGER.setLevel(logging.DEBUG)
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.retry = retry
        try:
            self.backoff = float(backoff)
        except (TypeError, ValueError):
            self.backoff = 0.0
        if isinstance(backoff_jitter, int | float):
            jitter: float | tuple[float, float] | None = float(backoff_jitter)
        elif isinstance(backoff_jitter, str):
            try:
                jitter = float(backoff_jitter)
            except ValueError:
                jitter = None
        elif isinstance(backoff_jitter, list | tuple) and len(backoff_jitter) >= 2:
            try:
                jitter = (float(backoff_jitter[0]), float(backoff_jitter[1]))
            except (TypeError, ValueError):
                jitter = None
        else:
            jitter = None
        if jitter in (0, 0.0):
            jitter = 0.0
        self.backoff_jitter = jitter
        self.verbose_invalid_values = verbose_invalid_values
        self.scan_uart_settings = scan_uart_settings
        self.skip_known_missing = skip_known_missing
        self.deep_scan = deep_scan
        self.full_register_scan = full_register_scan
        self.safe_scan = safe_scan
        try:
            self.effective_batch = min(int(max_registers_per_request), MAX_BATCH_REGISTERS)
        except (TypeError, ValueError):
            self.effective_batch = MAX_BATCH_REGISTERS
        if self.effective_batch < 1:
            self.effective_batch = 1
        self.max_registers_per_request = self.effective_batch

        resolved_type, resolved_mode = resolve_connection_settings(
            connection_type, connection_mode, port
        )
        self.connection_type = resolved_type
        self.connection_mode = resolved_mode
        self._resolved_connection_mode: str | None = (
            resolved_mode if resolved_mode != CONNECTION_MODE_AUTO else None
        )
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
        if self.stop_bits not in (1, 2):
            self.stop_bits = DEFAULT_STOP_BITS
        self._hass = hass

        # Available registers storage
        self.available_registers: dict[str, set[str]] = {
            "input_registers": set(),
            "holding_registers": set(),
            "coil_registers": set(),
            "discrete_inputs": set(),
        }

        # Detected device capabilities
        self.capabilities: DeviceCapabilities = DeviceCapabilities()

        # Placeholder for register map and value ranges loaded asynchronously
        self._registers: dict[int, dict[int, str]] = {}
        self._register_ranges: dict[str, tuple[int | None, int | None]] = {}
        self._names_by_address: dict[int, dict[int, set[str]]] = {4: {}, 3: {}, 1: {}, 2: {}}

        # Track holding registers that consistently fail to respond so we
        # can avoid retrying them repeatedly during scanning. The value is
        # a failure counter per register address.
        self._holding_failures: dict[int, int] = {}
        # Cache holding registers that have exceeded retry attempts
        self._failed_holding: set[int] = set()

        # Track input registers that consistently fail to respond so we can
        # avoid retrying them repeatedly during scanning
        self._input_failures: dict[int, int] = {}
        self._failed_input: set[int] = set()
        # Track ranges that have already been logged as skipped in the current scan
        self._input_skip_log_ranges: set[tuple[int, int]] = set()

        # Cache register ranges that returned Modbus exception codes 2-4 so
        # they can be skipped on subsequent reads without additional warnings
        self._unsupported_input_ranges: dict[tuple[int, int], int] = {}
        self._unsupported_holding_ranges: dict[tuple[int, int], int] = {}

        # Keep track of the Modbus client/transport so it can be closed later
        self._client: AsyncModbusTcpClient | AsyncModbusSerialClientType | None = None
        self._transport: BaseModbusTransport | None = None

        # Track registers for which invalid values have been reported
        self._reported_invalid: set[str] = set()

        # Collect addresses skipped due to Modbus errors or invalid values
        self.failed_addresses: dict[str, dict[str, set[int]]] = {
            "modbus_exceptions": {
                "input_registers": set(),
                "holding_registers": set(),
                "coil_registers": set(),
                "discrete_inputs": set(),
            },
            "invalid_values": {
                "input_registers": set(),
                "holding_registers": set(),
            },
        }
        self._sensor_unavailable_checks: dict[str, int] = {}

        self._populate_known_missing_addresses()

    def _populate_known_missing_addresses(self) -> None:
        """Pre-compute addresses of known missing registers for batch grouping."""
        self._known_missing_addresses: set[int] = set()
        self._update_known_missing_addresses()

    def _update_known_missing_addresses(self) -> None:
        """Populate cached missing register addresses from known missing list."""

        self._known_missing_addresses.clear()
        for reg_type, names in KNOWN_MISSING_REGISTERS.items():
            mapping = {
                "input_registers": INPUT_REGISTERS,
                "holding_registers": HOLDING_REGISTERS,
                "coil_registers": COIL_REGISTERS,
                "discrete_inputs": DISCRETE_INPUT_REGISTERS,
            }[reg_type]
            for name in names:
                if (addr := mapping.get(name)) is None:
                    continue
                size = MULTI_REGISTER_SIZES.get(name, 1)
                self._known_missing_addresses.update(range(addr, addr + size))

    async def _async_setup(self) -> None:
        """Asynchronously load register definitions."""

        await _async_ensure_register_maps(self._hass)
        loaded = await self._load_registers()
        if isinstance(loaded, tuple):
            self._registers = cast(dict[int, dict[int, str]], loaded[0])
            self._register_ranges = cast(dict[str, tuple[int | None, int | None]], loaded[1]) if len(loaded) > 1 and isinstance(loaded[1], dict) else {}
        else:
            self._registers = cast(dict[int, dict[int, str]], loaded)
            self._register_ranges = {}
        self._names_by_address = {
            4: self._build_names_by_address({name: addr for addr, name in self._registers.get(4, {}).items()} or INPUT_REGISTERS),
            3: self._build_names_by_address({name: addr for addr, name in self._registers.get(3, {}).items()} or HOLDING_REGISTERS),
            1: self._build_names_by_address({name: addr for addr, name in self._registers.get(1, {}).items()} or COIL_REGISTERS),
            2: self._build_names_by_address({name: addr for addr, name in self._registers.get(2, {}).items()} or DISCRETE_INPUT_REGISTERS),
        }
        self._update_known_missing_addresses()

    @staticmethod
    def _build_names_by_address(mapping: dict[str, int]) -> dict[int, set[str]]:
        """Create address->name aliases map from name->address mapping."""

        by_address: dict[int, set[str]] = {}
        for name, addr in mapping.items():
            by_address.setdefault(addr, set()).add(name)
        return by_address

    def _alias_names(self, function: int, address: int) -> set[str]:
        """Return all register names sharing the same function/address pair."""

        return self._names_by_address.get(function, {}).get(address, set())

    @classmethod
    async def create(
        cls,
        host: str,
        port: int,
        slave_id: int = DEFAULT_SLAVE_ID,
        timeout: int = 10,
        retry: int = 3,
        backoff: float = 0,
        backoff_jitter: float | tuple[float, float] | None = None,
        verbose_invalid_values: bool = False,
        scan_uart_settings: bool = DEFAULT_SCAN_UART_SETTINGS,
        skip_known_missing: bool = False,
        deep_scan: bool = False,
        full_register_scan: bool = False,
        max_registers_per_request: int = MAX_BATCH_REGISTERS,
        safe_scan: bool = False,
        connection_type: str = DEFAULT_CONNECTION_TYPE,
        connection_mode: str | None = None,
        serial_port: str = DEFAULT_SERIAL_PORT,
        baud_rate: int = DEFAULT_BAUD_RATE,
        parity: str = DEFAULT_PARITY,
        stop_bits: int = DEFAULT_STOP_BITS,
        hass: Any | None = None,
    ) -> ThesslaGreenDeviceScanner:
        """Factory to create an initialized scanner instance."""
        _ensure_pymodbus_client_module()
        await async_ensure_register_maps(hass)
        self = cls(
            host,
            port,
            slave_id,
            timeout,
            retry,
            backoff,
            backoff_jitter,
            verbose_invalid_values,
            scan_uart_settings,
            skip_known_missing,
            deep_scan,
            full_register_scan,
            safe_scan,
            max_registers_per_request,
            connection_type,
            connection_mode,
            serial_port,
            baud_rate,
            parity,
            stop_bits,
            hass=hass,
            registers_ready=True,
        )
        await self._async_setup()

        # Ensure low-level register read helpers are attached to the instance
        # so tests and callers can patch them as needed.
        self._read_holding = cls._read_holding.__get__(self, cls)  # type: ignore[method-assign]
        self._read_coil = cls._read_coil.__get__(self, cls)  # type: ignore[method-assign]
        self._read_discrete = cls._read_discrete.__get__(self, cls)  # type: ignore[method-assign]

        return self

    async def close(self) -> None:
        """Close the underlying Modbus client connection."""

        if self._transport is not None:
            try:
                await self._transport.close()
            except (OSError, ConnectionException, ModbusIOException):
                _LOGGER.debug("Error closing Modbus transport", exc_info=True)
            finally:
                self._transport = None

        client = self._client
        if client is None:
            return

        try:
            await async_maybe_await_close(client)
        except (OSError, ConnectionException, ModbusIOException):
            _LOGGER.debug("Error closing Modbus client", exc_info=True)
        finally:
            self._client = None

    def _build_tcp_transport(
        self,
        mode: str,
        *,
        timeout_override: float | None = None,
    ) -> BaseModbusTransport:
        timeout = self.timeout if timeout_override is None else timeout_override
        if mode == CONNECTION_MODE_TCP_RTU:
            return RawRtuOverTcpTransport(
                host=self.host,
                port=self.port,
                max_retries=self.retry,
                base_backoff=self.backoff,
                max_backoff=DEFAULT_MAX_BACKOFF,
                timeout=timeout,
            )
        return TcpModbusTransport(
            host=self.host,
            port=self.port,
            connection_type=CONNECTION_TYPE_TCP,
            max_retries=self.retry,
            base_backoff=self.backoff,
            max_backoff=DEFAULT_MAX_BACKOFF,
            timeout=timeout,
        )

    def _build_auto_tcp_attempts(self) -> list[tuple[str, BaseModbusTransport, float]]:
        rtu_timeout = min(max(self.timeout, 2.0), 5.0)
        tcp_timeout = min(max(self.timeout, 5.0), 10.0)
        prefer_tcp = self.port == DEFAULT_PORT
        mode_order = [CONNECTION_MODE_TCP, CONNECTION_MODE_TCP_RTU] if prefer_tcp else [
            CONNECTION_MODE_TCP_RTU,
            CONNECTION_MODE_TCP,
        ]
        attempts: list[tuple[str, BaseModbusTransport, float]] = []
        for mode in mode_order:
            timeout = rtu_timeout if mode == CONNECTION_MODE_TCP_RTU else tcp_timeout
            attempts.append(
                (
                    mode,
                    self._build_tcp_transport(mode, timeout_override=timeout),
                    timeout,
                )
            )
        return attempts

    async def verify_connection(self) -> None:
        """Verify basic Modbus connectivity by reading a few safe registers.

        A handful of well-known registers are read from the device to confirm
        that the TCP connection and Modbus protocol are functioning. Any
        failure will raise a ``ModbusException`` or ``ConnectionException`` so
        callers can surface an appropriate error to the user.
        """

        safe_input: list[int] = []
        safe_holding: list[int] = []
        for func, name in SAFE_REGISTERS:
            reg = REGISTER_DEFINITIONS.get(name)
            if reg is None:
                continue
            if func == 4:
                safe_input.append(reg.address)
            else:
                safe_holding.append(reg.address)

        attempts: list[tuple[str | None, BaseModbusTransport, float]] = []
        if self.connection_type == CONNECTION_TYPE_RTU:
            if not self.serial_port:
                raise ConnectionException("Serial port not configured")
            parity = SERIAL_PARITY_MAP.get(self.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])
            stop_bits = SERIAL_STOP_BITS_MAP.get(
                self.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]
            )
            attempts.append(
                (
                    None,
                    RtuModbusTransport(
                        serial_port=self.serial_port,
                        baudrate=self.baud_rate,
                        parity=parity,
                        stopbits=stop_bits,
                        max_retries=self.retry,
                        base_backoff=self.backoff,
                        max_backoff=DEFAULT_MAX_BACKOFF,
                        timeout=self.timeout,
                    ),
                    self.timeout,
                )
            )
        elif self.connection_mode == CONNECTION_MODE_AUTO:
            attempts.extend(self._build_auto_tcp_attempts())
        else:
            mode = self.connection_mode or default_connection_mode(self.port)
            attempts.append((mode, self._build_tcp_transport(mode), self.timeout))

        last_error: Exception | None = None
        closed_transports: set[int] = set()
        for mode, transport, timeout in attempts:
            try:
                _LOGGER.info(
                    "verify_connection: connecting to %s:%s (mode=%s, timeout=%s)",
                    self.host,
                    self.port,
                    mode or self.connection_type,
                    timeout,
                )
                await asyncio.wait_for(transport.ensure_connected(), timeout=timeout)

                for start, count in _group_reads(safe_input, max_block_size=self.effective_batch):
                    _LOGGER.debug(
                        "verify_connection: read_input_registers start=%s count=%s",
                        start,
                        count,
                    )
                    await transport.read_input_registers(
                        self.slave_id,
                        start,
                        count=count,
                    )

                for start, count in _group_reads(safe_holding, max_block_size=self.effective_batch):
                    _LOGGER.debug(
                        "verify_connection: read_holding_registers start=%s count=%s",
                        start,
                        count,
                    )
                    await transport.read_holding_registers(
                        self.slave_id,
                        start,
                        count=count,
                    )
                if mode is not None:
                    if self.connection_mode == CONNECTION_MODE_AUTO:
                        _LOGGER.info(
                            "verify_connection: auto-selected Modbus transport %s for %s:%s",
                            mode,
                            self.host,
                            self.port,
                        )
                    self._resolved_connection_mode = mode
                return
            except asyncio.CancelledError:
                raise
            except ModbusIOException as exc:
                last_error = exc
                if is_request_cancelled_error(exc):
                    _LOGGER.info("Modbus request cancelled during verify_connection.")
                    raise TimeoutError("Modbus request cancelled") from exc
            except TimeoutError as exc:
                last_error = exc
                _LOGGER.warning("Timeout during verify_connection: %s", exc)
            except (ConnectionException, ModbusException, OSError) as exc:
                last_error = exc
            finally:
                try:
                    transport_id = id(transport)
                    if transport_id not in closed_transports:
                        close_result = transport.close()
                        if inspect.isawaitable(close_result):
                            await close_result
                        closed_transports.add(transport_id)
                except (OSError, ConnectionException, ModbusIOException):
                    _LOGGER.debug(
                        "Error closing Modbus transport during verify_connection", exc_info=True
                    )

        if last_error:
            raise last_error

    def _is_valid_register_value(self, name: str, value: int) -> bool:
        """Validate a register value against known constraints.

        This check is intentionally lightweight – it ensures that obvious
        placeholder values (like ``SENSOR_UNAVAILABLE``) and values outside the
        ranges defined in the register metadata are ignored.  The method mirrors
        behaviour expected by the tests but does not aim to provide exhaustive
        validation of every register.
        """

        if value == 65535:
            return False

        # Registers in SENSOR_UNAVAILABLE_REGISTERS return 0x8000 when a sensor
        # is not physically connected. The register itself EXISTS and must produce
        # an entity (shown as "unavailable" in HA). Only EC2 responses mean the
        # register is truly absent. Accept 0x8000 here — coordinator and sensor.py
        # already handle it correctly via the SENSOR_UNAVAILABLE sentinel.
        if name in SENSOR_UNAVAILABLE_REGISTERS and value == SENSOR_UNAVAILABLE:
            return True

        if "temperature" in name and value == SENSOR_UNAVAILABLE:
            return True

        allowed = REGISTER_ALLOWED_VALUES.get(name)
        if allowed is not None and value not in allowed:
            return False

        if name.startswith(BCD_TIME_PREFIXES) and name != "schedule_start_time":
            if decode_bcd_time(value) is None:
                return False

        if range_vals := self._register_ranges.get(name):
            min_val, max_val = range_vals
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False

        return True

    def _analyze_capabilities(self) -> DeviceCapabilities:
        """Derive device capabilities from discovered registers."""

        caps = DeviceCapabilities()
        inputs = self.available_registers["input_registers"]
        holdings = self.available_registers["holding_registers"]
        coils = self.available_registers["coil_registers"]
        discretes = self.available_registers["discrete_inputs"]

        # Temperature sensors
        temp_map = {
            "sensor_outside_temperature": "outside_temperature",
            "sensor_supply_temperature": "supply_temperature",
            "sensor_exhaust_temperature": "exhaust_temperature",
            "sensor_fpx_temperature": "fpx_temperature",
            "sensor_duct_supply_temperature": "duct_supply_temperature",
            "sensor_gwc_temperature": "gwc_temperature",
            "sensor_ambient_temperature": "ambient_temperature",
            "sensor_heating_temperature": "heating_temperature",
        }
        for attr, reg in temp_map.items():
            if reg in inputs:
                setattr(caps, attr, True)
                caps.temperature_sensors.add(reg)

        caps.temperature_sensors_count = len(caps.temperature_sensors)  # pragma: no cover

        # Expansion module and GWC detection via discrete inputs/coils
        if "expansion" in discretes:
            caps.expansion_module = True  # pragma: no cover
        if "gwc" in coils or "gwc_temperature" in inputs:
            caps.gwc_system = True  # pragma: no cover

        if "bypass" in coils:
            caps.bypass_system = True  # pragma: no cover
        if any(reg.startswith("schedule_") for reg in holdings):
            caps.weekly_schedule = True  # pragma: no cover

        if "on_off_panel_mode" in holdings:
            caps.basic_control = True  # pragma: no cover

        if any(
            reg in inputs
            for reg in [
                "constant_flow_active",
                "supply_flow_rate",
                "supply_air_flow",
                "cf_version",
            ]
        ):
            caps.constant_flow = True  # pragma: no cover

        # Generic capability detection based on register name patterns
        all_registers = inputs | holdings | coils | discretes
        for attr, patterns in CAPABILITY_PATTERNS.items():
            if getattr(caps, attr):
                continue
            if any(pat in reg for reg in all_registers for pat in patterns):
                setattr(caps, attr, True)

        return caps

    def _group_registers_for_batch_read(
        self, addresses: list[int], *, max_gap: int = 1, max_batch: int | None = None
    ) -> list[tuple[int, int]]:
        """Group consecutive register addresses for efficient batch reads.

        ``max_gap`` is retained for backward compatibility with older callers
        even though the helper no longer uses it directly.  The implementation
        delegates grouping to the shared ``group_reads`` helper so that the
        scanner benefits from the same optimisation logic used elsewhere in the
        project.  Any registers that have previously been marked as missing are
        split into their own single-register groups to avoid unnecessary
        failures when reading surrounding ranges.
        """

        if not addresses:
            return []

        # ``max_gap`` is unused but kept for API compatibility
        _ = max_gap

        if max_batch is None:
            max_batch = self.effective_batch

        if self.safe_scan:
            return [(addr, 1) for addr in sorted(set(addresses))]

        # First, compute contiguous blocks using the generic ``group_reads``
        # helper.  ``max_gap`` is kept for API compatibility but is not
        # required when using ``group_reads`` which already splits on gaps.
        groups = _group_reads(addresses, max_block_size=max_batch)

        if not self._known_missing_addresses:
            return groups

        # Known missing registers are isolated into their own single-register
        # groups so that a failure to read them does not prevent the surrounding
        # valid registers from being read.  Each batch produced by group_reads
        # is split individually at the missing addresses so that the max_batch
        # window boundaries are preserved.
        result: list[tuple[int, int]] = []
        for start, length in groups:
            current = start
            for addr in range(start, start + length):
                if addr in self._known_missing_addresses:
                    if addr > current:
                        result.append((current, addr - current))
                    result.append((addr, 1))
                    current = addr + 1
            if current < start + length:
                result.append((current, start + length - current))
        return result

    async def _scan_firmware_info(
        self, info_regs: list[int], device: "ScannerDeviceInfo"
    ) -> None:
        """Parse firmware version from info_regs and update device."""
        major: int | None = None
        minor: int | None = None
        patch: int | None = None
        firmware_err: Exception | None = None

        for name in ("version_major", "version_minor", "version_patch"):
            idx = INPUT_REGISTERS.get(name)
            if idx is not None and len(info_regs) > idx:
                try:
                    value = info_regs[idx]
                except (TypeError, ValueError, IndexError) as exc:  # pragma: no cover - best effort
                    firmware_err = exc
                    continue
                except Exception as exc:  # pragma: no cover - unexpected
                    _LOGGER.exception("Unexpected firmware value error for %s: %s", name, exc)
                    firmware_err = exc
                    continue
                if name == "version_major":
                    major = value
                elif name == "version_minor":
                    minor = value
                else:
                    patch = value

        # Some devices reject larger blocks around register 0 but still allow
        # individual reads of the firmware registers. Retry missing values as
        # single-register probes while bypassing failed-range caching.
        if None in (major, minor, patch):
            fallback_results: dict[str, int] = {}
            for name in ("version_major", "version_minor", "version_patch"):
                current = (
                    major if name == "version_major" else minor if name == "version_minor" else patch
                )
                if current is not None:
                    continue
                probe = None
                try:
                    addr = INPUT_REGISTERS.get(name)
                    if addr is None:
                        continue
                    try:
                        probe = await self._read_input(self._client, addr, 1, skip_cache=True) if self._client is not None else await self._read_input(addr, 1, skip_cache=True)
                    except TypeError:
                        probe = await self._read_input(addr, 1, skip_cache=True)
                except (TypeError, ValueError, IndexError) as exc:  # pragma: no cover - best effort
                    firmware_err = exc
                    continue
                except Exception as exc:  # pragma: no cover - unexpected
                    _LOGGER.exception("Unexpected firmware probe error for %s: %s", name, exc)
                    firmware_err = exc
                    continue
                if probe:
                    fallback_results[name] = probe[0]
            major = fallback_results.get("version_major", major)
            minor = fallback_results.get("version_minor", minor)
            patch = fallback_results.get("version_patch", patch)

        missing_regs: list[str] = []
        if None in (major, minor, patch):
            for name, value in (("version_major", major), ("version_minor", minor), ("version_patch", patch)):
                if value is None and name in INPUT_REGISTERS:
                    missing_regs.append(f"{name} ({INPUT_REGISTERS[name]})")

        if None not in (major, minor, patch):
            device.firmware = f"{major}.{minor}.{patch}"
        else:
            details: list[str] = []
            if missing_regs:
                details.append("missing " + ", ".join(missing_regs))
            if firmware_err is not None:
                details.append(str(firmware_err))  # pragma: no cover
            msg = "Failed to read firmware version registers"
            if details:
                msg += ": " + "; ".join(details)
            _LOGGER.warning(msg)
            device.firmware_available = False  # pragma: no cover

    async def _scan_device_identity(
        self, info_regs: list[int], device: "ScannerDeviceInfo"
    ) -> None:
        """Parse serial number and device name from registers into device."""
        try:
            start = INPUT_REGISTERS["serial_number"]
            parts = info_regs[
                start : start + REGISTER_DEFINITIONS["serial_number"].length
            ]  # noqa: E203
            if parts:
                device.serial_number = "".join(f"{p:04X}" for p in parts)
        except (KeyError, IndexError, TypeError, ValueError) as err:  # pragma: no cover
            _LOGGER.debug("Failed to parse serial number: %s", err)
        except Exception as err:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected error parsing serial number: %s", err)
        try:
            start = HOLDING_REGISTERS["device_name"]
            name_regs = (
                await self._read_holding_block(
                    start, REGISTER_DEFINITIONS["device_name"].length
                )
                or []
            )
            if name_regs:
                name_bytes = bytearray()
                for reg in name_regs:
                    name_bytes.append((reg >> 8) & 255)
                    name_bytes.append(reg & 255)
                device.device_name = name_bytes.decode("ascii", errors="replace").rstrip("\x00")
        except (KeyError, IndexError, TypeError, ValueError) as err:  # pragma: no cover
            _LOGGER.debug("Failed to parse device name: %s", err)
        except Exception as err:  # pragma: no cover - unexpected
            _LOGGER.exception("Unexpected error parsing device name: %s", err)
    def _select_scan_registers(
        self,
    ) -> tuple[dict[int, str], dict[int, str], dict[int, str], dict[int, str], int, int, int, int]:
        """Select which registers to scan and compute address ranges."""
        input_max = max(self._registers.get(4, {}).keys(), default=-1)
        holding_max = max(self._registers.get(3, {}).keys(), default=-1)
        coil_max = max(self._registers.get(1, {}).keys(), default=-1)
        discrete_max = max(self._registers.get(2, {}).keys(), default=-1)
        if self.full_register_scan:
            input_registers = self._registers.get(4, {}) or {addr: name for name, addr in INPUT_REGISTERS.items()}
            holding_registers = self._registers.get(3, {}) or {addr: name for name, addr in HOLDING_REGISTERS.items()}
            coil_registers = self._registers.get(1, {}) or {addr: name for name, addr in COIL_REGISTERS.items()}
            discrete_registers = self._registers.get(2, {}) or {addr: name for name, addr in DISCRETE_INPUT_REGISTERS.items()}
        else:
            global_input = {addr: name for name, addr in INPUT_REGISTERS.items()}
            global_holding = {addr: name for name, addr in HOLDING_REGISTERS.items()}
            global_coil = {addr: name for name, addr in COIL_REGISTERS.items()}
            global_discrete = {addr: name for name, addr in DISCRETE_INPUT_REGISTERS.items()}

            loaded_input = self._registers.get(4, {})
            loaded_holding = self._registers.get(3, {})
            loaded_coil = self._registers.get(1, {})
            loaded_discrete = self._registers.get(2, {})

            input_registers = loaded_input if loaded_input and (not global_input or len(loaded_input) <= len(global_input)) else global_input
            holding_registers = loaded_holding if loaded_holding and (not global_holding or len(loaded_holding) <= len(global_holding)) else global_holding
            coil_registers = loaded_coil if loaded_coil and (not global_coil or len(loaded_coil) <= len(global_coil)) else global_coil
            discrete_registers = loaded_discrete if loaded_discrete and (not global_discrete or len(loaded_discrete) <= len(global_discrete)) else global_discrete

        return input_registers, holding_registers, coil_registers, discrete_registers, input_max, holding_max, coil_max, discrete_max

    async def _run_full_scan(
        self,
        input_max: int,
        holding_max: int,
        coil_max: int,
        discrete_max: int,
        unknown_registers: dict[str, dict[int, Any]],
        scanned_registers: dict[str, int],
    ) -> None:
        """Scan all registers up to max known address (full_register_scan mode)."""
        for start, count in _group_reads(
            range(input_max + 1), max_block_size=self.effective_batch
        ):
            scanned_registers["input_registers"] += count
            input_data = await self._read_input(self._client, start, count, skip_cache=True) if self._client is not None else await self._read_input(None, start, count, skip_cache=True)
            if input_data is None:
                self.failed_addresses["modbus_exceptions"]["input_registers"].update(
                    range(start, start + count)
                )
                continue
            for offset in range(count):
                addr = start + offset
                if offset >= len(input_data):
                    if self._registers.get(4, {}).get(addr) is None:
                        base = input_data[0] if input_data else start
                        unknown_registers["input_registers"][addr] = int(base) + offset
                    continue
                value = input_data[offset]
                reg_name = self._registers.get(4, {}).get(addr)
                if reg_name and self._is_valid_register_value(reg_name, value):
                    names = self._alias_names(4, addr)
                    if names:
                        self.available_registers["input_registers"].update(names)
                    else:
                        self.available_registers["input_registers"].add(reg_name)
                else:
                    unknown_registers["input_registers"][addr] = value
                    if reg_name:
                        self.failed_addresses["invalid_values"]["input_registers"].add(addr)
                        self._log_invalid_value(reg_name, value)

        for start, count in _group_reads(
            range(holding_max + 1), max_block_size=self.effective_batch
        ):
            scanned_registers["holding_registers"] += count
            holding_data = await self._read_holding(self._client, start, count, skip_cache=True) if self._client is not None else await self._read_holding(None, start, count, skip_cache=True)
            if holding_data is None:
                self.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                    range(start, start + count)
                )
                continue
            for offset in range(count):
                addr = start + offset
                if offset >= len(holding_data):
                    if self._registers.get(3, {}).get(addr) is None:
                        base = holding_data[0] if holding_data else start
                        unknown_registers["holding_registers"][addr] = int(base) + offset
                    continue
                value = holding_data[offset]
                reg_name = self._registers.get(3, {}).get(addr)
                if reg_name and self._is_valid_register_value(reg_name, value):
                    names = self._alias_names(3, addr)
                    if names:
                        self.available_registers["holding_registers"].update(names)
                    else:
                        self.available_registers["holding_registers"].add(reg_name)
                else:
                    unknown_registers["holding_registers"][addr] = value
                    if reg_name:
                        self.failed_addresses["invalid_values"]["holding_registers"].add(addr)
                        self._log_invalid_value(reg_name, value)

        for start, count in _group_reads(
            range(coil_max + 1), max_block_size=self.effective_batch
        ):
            scanned_registers["coil_registers"] += count
            coil_data = await self._read_coil(self._client, start, count) if self._client is not None else await self._read_coil(start, count)
            if coil_data is None:
                self.failed_addresses["modbus_exceptions"]["coil_registers"].update(
                    range(start, start + count)
                )
                continue
            for offset, value in enumerate(coil_data):
                addr = start + offset
                if (reg_name := self._registers.get(1, {}).get(addr)) is not None:
                    names = self._alias_names(1, addr)
                    if names:
                        self.available_registers["coil_registers"].update(names)
                    else:
                        self.available_registers["coil_registers"].add(reg_name)
                else:
                    unknown_registers["coil_registers"][addr] = value

        for start, count in _group_reads(
            range(discrete_max + 1), max_block_size=self.effective_batch
        ):
            scanned_registers["discrete_inputs"] += count
            discrete_data = await self._read_discrete(self._client, start, count) if self._client is not None else await self._read_discrete(start, count)
            if discrete_data is None:
                self.failed_addresses["modbus_exceptions"]["discrete_inputs"].update(
                    range(start, start + count)
                )
                continue
            for offset, value in enumerate(discrete_data):
                addr = start + offset
                if (reg_name := self._registers.get(2, {}).get(addr)) is not None:
                    names = self._alias_names(2, addr)
                    if names:
                        self.available_registers["discrete_inputs"].update(names)
                    else:
                        self.available_registers["discrete_inputs"].add(reg_name)
                else:
                    unknown_registers["discrete_inputs"][addr] = value

    async def _scan_register_batch(
        self,
        reg_type: str,
        addr_to_names: dict[int, set[str]],
        addresses: list[int],
        read_fn,
    ) -> None:
        """Read a batch of registers of one FC type, with per-address fallback."""
        for start, count in self._group_registers_for_batch_read(addresses):
            try:
                data = await read_fn(start, count)
            except TypeError:
                data = None

            if data is None:
                self.failed_addresses["modbus_exceptions"][reg_type].update(
                    range(start, start + count)
                )
                _LOGGER.debug(
                    "%s batch read %d-%d failed; probing individually",
                    reg_type, start, start + count - 1,
                )
                for addr in range(start, start + count):
                    reg_names = addr_to_names.get(addr)
                    if not reg_names:
                        continue
                    try:
                        probe = await read_fn(addr, 1, skip_cache=True)
                    except TypeError:
                        probe = None
                    if not probe:
                        _LOGGER.warning("Failed to read %s register %d", reg_type, addr)
                        continue
                    value = probe[0]
                    if any(self._is_valid_register_value(n, value) for n in reg_names):
                        self.available_registers[reg_type].update(reg_names)
                    else:
                        self.failed_addresses["invalid_values"][reg_type].add(addr)
                        self._log_invalid_value(sorted(reg_names)[0], value)
                continue

            for offset, value in enumerate(data):
                addr = start + offset
                if reg_names := addr_to_names.get(addr):
                    if any(self._is_valid_register_value(n, value) for n in reg_names):
                        self.available_registers[reg_type].update(reg_names)
                    else:
                        self.failed_addresses["invalid_values"][reg_type].add(addr)
                        self._log_invalid_value(sorted(reg_names)[0], value)

    async def _scan_named_input(self, input_registers: dict[int, str]) -> None:
        """Scan FC04 input registers in batches."""
        addr_to_names: dict[int, set[str]] = {}
        addresses: list[int] = []
        for addr, name in input_registers.items():
            if name in KNOWN_MISSING_REGISTERS.get("input_registers", set()):
                continue
            addr_to_names.setdefault(addr, set()).add(name)
            addresses.append(addr)

        async def _read(start: int, count: int, *, skip_cache: bool = False):
            try:
                return await self._read_input(self._client, start, count, skip_cache=skip_cache) if self._client is not None else await self._read_input(start, count, skip_cache=skip_cache)
            except TypeError:
                return await self._read_input(start, count, skip_cache=skip_cache)

        await self._scan_register_batch("input_registers", addr_to_names, addresses, _read)

    async def _scan_named_holding(self, holding_registers: dict[int, str]) -> None:
        """Scan FC03 holding registers in batches, handling multi-word registers."""
        holding_info: dict[int, tuple[set[str], int]] = {}
        holding_addresses: list[int] = []
        for addr, name in holding_registers.items():
            if not self.scan_uart_settings and addr in UART_OPTIONAL_REGS:
                continue
            if name in KNOWN_MISSING_REGISTERS.get("holding_registers", set()):
                continue
            size = MULTI_REGISTER_SIZES.get(name, 1)
            if addr in holding_info:
                names, _ = holding_info[addr]  # pragma: no cover
                names.add(name)  # pragma: no cover
            else:
                holding_info[addr] = ({name}, size)
            holding_addresses.extend(range(addr, addr + size))

        addr_to_names = {addr: names for addr, (names, _) in holding_info.items()}

        async def _read(start: int, count: int, *, skip_cache: bool = False):
            try:
                return await self._read_holding(self._client, start, count, skip_cache=skip_cache) if self._client is not None else await self._read_holding(start, count, skip_cache=skip_cache)
            except TypeError:
                return await self._read_holding(start, count, skip_cache=skip_cache)

        await self._scan_register_batch("holding_registers", addr_to_names, holding_addresses, _read)

        # Expose error/alarm registers that didn't explicitly fail
        failed_addrs = self.failed_addresses["modbus_exceptions"]["holding_registers"]
        for addr, name in holding_registers.items():
            if name.startswith(("e_", "s_")) or name in {"alarm", "error"}:
                if addr not in failed_addrs:
                    self.available_registers["holding_registers"].add(name)

    async def _scan_named_coil(self, coil_registers: dict[int, str]) -> None:
        """Scan FC01 coil registers in batches."""
        addr_to_names: dict[int, set[str]] = {}
        addresses: list[int] = []
        for addr, name in coil_registers.items():
            if name in KNOWN_MISSING_REGISTERS.get("coil_registers", set()):
                continue
            addr_to_names.setdefault(addr, set()).add(name)
            addresses.append(addr)

        for start, count in self._group_registers_for_batch_read(addresses):
            coil_data = await self._read_coil(self._client, start, count) if self._client is not None else await self._read_coil(start, count)
            if coil_data is None:
                self.failed_addresses["modbus_exceptions"]["coil_registers"].update(
                    range(start, start + count)
                )
                for addr in range(start, start + count):
                    if addr not in addr_to_names:
                        continue  # pragma: no cover
                    probe = await self._read_coil(self._client, addr, 1) if self._client is not None else await self._read_coil(None, addr, 1)
                    if probe and probe[0] is not None:
                        self.available_registers["coil_registers"].update(addr_to_names[addr])
                continue
            for offset, value in enumerate(coil_data):
                addr = start + offset
                if addr in addr_to_names and value is not None:
                    self.available_registers["coil_registers"].update(addr_to_names[addr])

    async def _scan_named_discrete(self, discrete_registers: dict[int, str]) -> None:
        """Scan FC02 discrete input registers in batches."""
        addr_to_names: dict[int, set[str]] = {}
        addresses: list[int] = []
        for addr, name in discrete_registers.items():
            if name in KNOWN_MISSING_REGISTERS.get("discrete_inputs", set()):
                continue
            addr_to_names.setdefault(addr, set()).add(name)
            addresses.append(addr)

        for start, count in self._group_registers_for_batch_read(addresses):
            discrete_data = await self._read_discrete(self._client, start, count) if self._client is not None else await self._read_discrete(start, count)
            if discrete_data is None:
                self.failed_addresses["modbus_exceptions"]["discrete_inputs"].update(
                    range(start, start + count)
                )
                for addr in range(start, start + count):
                    if addr not in addr_to_names:
                        continue  # pragma: no cover
                    probe = await self._read_discrete(self._client, addr, 1) if self._client is not None else await self._read_discrete(None, addr, 1)
                    if probe and probe[0] is not None:
                        self.available_registers["discrete_inputs"].update(addr_to_names[addr])
                continue
            for offset, value in enumerate(discrete_data):
                addr = start + offset
                if addr in addr_to_names and value is not None:
                    self.available_registers["discrete_inputs"].update(addr_to_names[addr])

    async def _run_named_scan(
        self,
        input_registers: dict[int, str],
        holding_registers: dict[int, str],
        coil_registers: dict[int, str],
        discrete_registers: dict[int, str],
    ) -> None:
        """Scan only named/known registers (normal scan mode)."""
        await self._scan_named_input(input_registers)
        await self._scan_named_holding(holding_registers)
        await self._scan_named_coil(coil_registers)
        await self._scan_named_discrete(discrete_registers)

    def _compute_scan_blocks(
        self,
        input_registers: dict[int, str],
        holding_registers: dict[int, str],
        coil_registers: dict[int, str],
        discrete_registers: dict[int, str],
        input_max: int,
        holding_max: int,
        coil_max: int,
        discrete_max: int,
    ) -> dict[str, tuple[int | None, int | None]]:
        """Build scan_blocks dict describing the address range that was scanned."""
        if self.full_register_scan:
            return {
                "input_registers": (
                    0 if input_max >= 0 else None,
                    input_max if input_max >= 0 else None,
                ),
                "holding_registers": (
                    0 if holding_max >= 0 else None,
                    holding_max if holding_max >= 0 else None,
                ),
                "coil_registers": (
                    0 if coil_max >= 0 else None,
                    coil_max if coil_max >= 0 else None,
                ),
                "discrete_inputs": (
                    0 if discrete_max >= 0 else None,
                    discrete_max if discrete_max >= 0 else None,
                ),
            }
        return {
            "input_registers": (
                (min(input_registers.keys()), max(input_registers.keys()))
                if input_registers
                else (None, None)
            ),
            "holding_registers": (
                (min(holding_registers.keys()), max(holding_registers.keys()))
                if holding_registers
                else (None, None)
            ),
            "coil_registers": (
                (min(coil_registers.keys()), max(coil_registers.keys()))
                if coil_registers
                else (None, None)
            ),
            "discrete_inputs": (
                (min(discrete_registers.keys()), max(discrete_registers.keys()))
                if discrete_registers
                else (None, None)
            ),
        }

    def _collect_missing_registers(
        self,
        input_registers: dict[int, str],
        holding_registers: dict[int, str],
        coil_registers: dict[int, str],
        discrete_registers: dict[int, str],
    ) -> dict[str, dict[str, int]]:
        """Return registers that were expected but not found during scan."""
        register_maps = {
            "input_registers": {name: addr for addr, name in input_registers.items()},
            "holding_registers": {name: addr for addr, name in holding_registers.items()},
            "coil_registers": {name: addr for addr, name in coil_registers.items()},
            "discrete_inputs": {name: addr for addr, name in discrete_registers.items()},
        }
        missing_registers: dict[str, dict[str, int]] = {}
        for reg_type, mapping in register_maps.items():
            missing: dict[str, int] = {}
            for name, addr in mapping.items():
                if name in KNOWN_MISSING_REGISTERS.get(reg_type, set()):
                    continue
                if name not in self.available_registers[reg_type]:
                    missing[name] = addr
            if missing:
                missing_registers[reg_type] = missing
        return missing_registers

    async def scan(self) -> dict[str, Any]:  # pragma: no cover
        """Perform the actual register scan using an established connection."""
        scan_started = time.monotonic()
        transport = self._transport
        if transport is None:
            if self._client is None:
                raise ConnectionException("Transport not connected")
        elif not transport.is_connected() and self._client is None:
            raise ConnectionException("Transport not connected")

        device = ScannerDeviceInfo()

        # Basic firmware/serial information
        info_regs = await self._read_input_block(0, 30) or []

        await self._scan_firmware_info(info_regs, device)
        await self._scan_device_identity(info_regs, device)

        (
            input_registers,
            holding_registers,
            coil_registers,
            discrete_registers,
            input_max,
            holding_max,
            coil_max,
            discrete_max,
        ) = self._select_scan_registers()

        unknown_registers: dict[str, dict[int, Any]] = {
            "input_registers": {},
            "holding_registers": {},
            "coil_registers": {},
            "discrete_inputs": {},
        }
        scanned_registers: dict[str, int] = {
            "input_registers": 0,
            "holding_registers": 0,
            "coil_registers": 0,
            "discrete_inputs": 0,
        }

        if self.full_register_scan:
            await self._run_full_scan(
                input_max, holding_max, coil_max, discrete_max,
                unknown_registers, scanned_registers,
            )
        else:
            await self._run_named_scan(
                input_registers, holding_registers, coil_registers, discrete_registers
            )

        caps = self._analyze_capabilities()
        self.capabilities = caps
        device.capabilities = [
            key for key, val in caps.as_dict().items() if isinstance(val, bool) and val
        ]
        _LOGGER.info("Detected %d capabilities", len(device.capabilities))

        scan_blocks = self._compute_scan_blocks(
            input_registers, holding_registers, coil_registers, discrete_registers,
            input_max, holding_max, coil_max, discrete_max,
        )
        self._log_skipped_ranges()

        raw_registers: dict[int, int] = {}
        if self.deep_scan:
            for start, count in self._group_registers_for_batch_read(list(range(287))):
                data = await self._read_input(self._client, start, count) if self._client is not None else await self._read_input(None, start, count)
                if data is None:
                    continue
                for offset, value in enumerate(data):
                    raw_registers[start + offset] = value

        missing_registers = self._collect_missing_registers(
            input_registers, holding_registers, coil_registers, discrete_registers
        )

        if missing_registers:
            details = []
            for reg_type, regs in missing_registers.items():
                formatted = ", ".join(
                    f"{name}={addr}"
                    for name, addr in sorted(regs.items(), key=lambda item: item[1])
                )
                details.append(f"{reg_type}: {formatted}")
            _LOGGER.warning(
                "The following registers were not found during scan: %s", "; ".join(details)
            )

        available_registers = {
            key: set(value) for key, value in self.available_registers.items()
        }

        result = {
            "available_registers": available_registers,
            "device_info": device.as_dict(),
            "capabilities": caps.as_dict(),
            "register_count": sum(len(v) for v in available_registers.values()),
            "scan_blocks": scan_blocks,
            "unknown_registers": unknown_registers,
            "scanned_registers": scanned_registers,
            "missing_registers": missing_registers,
            "failed_addresses": {
                "modbus_exceptions": {
                    k: sorted(v) for k, v in self.failed_addresses["modbus_exceptions"].items() if v
                },
                "invalid_values": {
                    k: sorted(v) for k, v in self.failed_addresses["invalid_values"].items() if v
                },
            },
            "resolved_connection_mode": self._resolved_connection_mode,
            "scan_stats": {
                "total_attempts": sum(scanned_registers.values()),
                "successful_reads": sum(len(v) for v in available_registers.values()),
                "scan_duration": max(0.0001, time.monotonic() - scan_started),
            },
        }
        if self.deep_scan:
            result["raw_registers"] = raw_registers
            result["total_addresses_scanned"] = len(raw_registers)

        return result

    async def scan_device(self) -> dict[str, Any]:
        """Open the Modbus connection, perform a scan and close the client."""
        scan_method = getattr(self, "scan")
        if getattr(scan_method, "__func__", None) is not ThesslaGreenDeviceScanner.scan:
            try:
                result = scan_method()
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, tuple) and len(result) >= 2 and isinstance(result[0], ScannerDeviceInfo) and isinstance(result[1], DeviceCapabilities):
                    device, caps = result[0], result[1]
                    unknown = result[2] if len(result) > 2 and isinstance(result[2], dict) else {}
                    return {
                        "available_registers": {k: sorted(v) for k, v in self.available_registers.items()},
                        "device_info": device.as_dict(),
                        "capabilities": caps.as_dict(),
                        "register_count": sum(len(v) for v in self.available_registers.values()),
                        "unknown_registers": unknown,
                    }
                return cast(dict[str, Any], result)
            finally:
                await self.close()

        if self.connection_type == CONNECTION_TYPE_RTU:
            if not self.serial_port:
                raise ConnectionException("Serial port not configured")
            parity = SERIAL_PARITY_MAP.get(self.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])
            stop_bits = SERIAL_STOP_BITS_MAP.get(
                self.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]
            )
            self._transport = RtuModbusTransport(
                serial_port=self.serial_port,
                baudrate=self.baud_rate,
                parity=parity,
                stopbits=stop_bits,
                max_retries=self.retry,
                base_backoff=self.backoff,
                max_backoff=DEFAULT_MAX_BACKOFF,
                timeout=self.timeout,
            )
        else:
            mode = self._resolved_connection_mode or self.connection_mode
            if mode is None or mode == CONNECTION_MODE_AUTO:
                last_error: Exception | None = None
                for selected_mode, transport, timeout in self._build_auto_tcp_attempts():
                    try:
                        await asyncio.wait_for(transport.ensure_connected(), timeout=timeout)
                        # Protocol probe: verify actual Modbus protocol works, not just
                        # the TCP socket. A TCP_RTU transport can open a TCP connection to any
                        # device, but reads will time out if the device speaks Modbus TCP instead
                        # of RTU-over-TCP. This mirrors verify_connection: TimeoutError means
                        # wrong protocol; any other outcome (even a Modbus exception code) means
                        # the device responded in the expected protocol.
                        try:
                            await transport.read_input_registers(self.slave_id, 0, count=2)
                        except TimeoutError:
                            raise
                        except ModbusIOException as exc:
                            if is_request_cancelled_error(exc):
                                raise TimeoutError(str(exc)) from exc
                            # Other Modbus exceptions (error codes) confirm protocol is working
                        except Exception as exc:
                            _LOGGER.debug("Protocol probe non-critical exception (protocol ok): %s", exc)
                    except (TimeoutError, ConnectionException, ModbusException, OSError) as exc:
                        last_error = exc
                        await transport.close()
                        continue
                    self._transport = transport
                    self._resolved_connection_mode = selected_mode
                    _LOGGER.info(
                        "scan_device: auto-selected Modbus transport %s for %s:%s",
                        selected_mode,
                        self.host,
                        self.port,
                    )
                    break
                if self._transport is None:
                    raise ConnectionException(
                        "Auto-detect Modbus transport failed"
                    ) from last_error
            else:
                self._transport = self._build_tcp_transport(mode)

        try:
            await asyncio.wait_for(self._transport.ensure_connected(), timeout=self.timeout)
            self._client = getattr(self._transport, "client", None)
        except (TimeoutError, ConnectionException, ModbusException, OSError) as exc:
            await self.close()
            raise ConnectionException(f"Failed to connect to {self.host}:{self.port}") from exc

        try:
            result = await self.scan()
            if not isinstance(result, dict):
                raise TypeError("scan() must return a dict")
            return result
        finally:
            await self.close()

    async def _load_registers(
        self,
    ) -> tuple[
        dict[int, dict[int, str]],
        dict[str, tuple[int | None, int | None]],
    ]:
        """Load Modbus register definitions and value ranges."""
        register_map: dict[int, dict[int, str]] = {3: {}, 4: {}, 1: {}, 2: {}}
        register_ranges: dict[str, tuple[int | None, int | None]] = {}
        for reg in await async_get_all_registers(self._hass):
            if not reg.name:
                continue
            register_map[reg.function][reg.address] = reg.name
            if reg.min is not None or reg.max is not None:
                register_ranges[reg.name] = (reg.min, reg.max)
        return register_map, register_ranges

    def _log_skipped_ranges(self) -> None:
        """Log summary of ranges skipped due to Modbus exceptions."""
        if self._unsupported_input_ranges:
            ranges = ", ".join(
                f"{start}-{end} (exception code {code})"
                for (start, end), code in sorted(self._unsupported_input_ranges.items())
            )
            _LOGGER.warning("Skipping unsupported input registers %s", ranges)
        if self._unsupported_holding_ranges:
            ranges = ", ".join(
                f"{start}-{end} (exception code {code})"
                for (start, end), code in sorted(self._unsupported_holding_ranges.items())
            )
            _LOGGER.warning("Skipping unsupported holding registers %s", ranges)

        # Build addr->name reverse maps from module-level register dicts
        _addr_to_name: dict[str, dict[int, str]] = {
            "input_registers": {addr: name for name, addr in INPUT_REGISTERS.items()},
            "holding_registers": {addr: name for name, addr in HOLDING_REGISTERS.items()},
            "coil_registers": {addr: name for name, addr in COIL_REGISTERS.items()},
            "discrete_inputs": {addr: name for name, addr in DISCRETE_INPUT_REGISTERS.items()},
        }

        for reg_type, addrs in self.failed_addresses["modbus_exceptions"].items():
            filtered = self._filter_unsupported_addresses(reg_type, addrs)
            if not filtered:
                continue
            # Exclude addresses successfully recovered via individual probe fallback
            reverse_map = _addr_to_name.get(reg_type, {})
            available = self.available_registers.get(reg_type, set())
            truly_failed = {
                addr for addr in filtered
                if reverse_map.get(addr) not in available
            }
            if truly_failed:
                decimals = ", ".join(str(addr) for addr in sorted(truly_failed))
                _LOGGER.warning("Failed to read %s at %s", reg_type, decimals)
            elif filtered:
                # Batch failed but individual probe recovered all — log at debug only
                decimals = ", ".join(str(addr) for addr in sorted(filtered))
                _LOGGER.debug(
                    "Batch read failed for %s at %s but individual probes succeeded",
                    reg_type, decimals,
                )

        for reg_type, addrs in self.failed_addresses["invalid_values"].items():
            if addrs:
                decimals = ", ".join(str(addr) for addr in sorted(addrs))
                _LOGGER.debug("Invalid values for %s at %s", reg_type, decimals)

    def _filter_unsupported_addresses(self, reg_type: str, addrs: set[int]) -> set[int]:
        """Return failed addresses that are not already covered by unsupported spans."""

        if reg_type == "input_registers":
            ranges = self._unsupported_input_ranges
        elif reg_type == "holding_registers":
            ranges = self._unsupported_holding_ranges
        else:
            return set(addrs)

        if not ranges:
            return set(addrs)

        return {
            addr
            for addr in addrs
            if not any(start <= addr <= end for start, end in ranges)
        }

    def _log_invalid_value(self, name: str, raw: int) -> None:
        """Log a register value that failed validation."""
        if name in self._reported_invalid:
            if not self.verbose_invalid_values:
                return
            level = logging.DEBUG
        else:
            level = logging.INFO if self.verbose_invalid_values else logging.DEBUG
            self._reported_invalid.add(name)
        decoded = _format_register_value(name, raw)
        _LOGGER.log(level, "Invalid value for %s: raw=%d decoded=%s", name, raw, decoded)

    def _mark_input_supported(self, address: int) -> None:
        """Remove address from cached unsupported input ranges after success."""
        self._failed_input.discard(address)
        for (start, end), code in list(self._unsupported_input_ranges.items()):
            if start <= address <= end:
                del self._unsupported_input_ranges[(start, end)]
                if start <= address - 1:
                    self._unsupported_input_ranges[(start, address - 1)] = code
                if address + 1 <= end:
                    self._unsupported_input_ranges[(address + 1, end)] = code

    def _mark_holding_supported(self, address: int) -> None:
        """Remove address from cached unsupported holding ranges after success."""
        self._failed_holding.discard(address)
        for (start, end), code in list(self._unsupported_holding_ranges.items()):
            if start <= address <= end:
                del self._unsupported_holding_ranges[(start, end)]
                if start <= address - 1:
                    self._unsupported_holding_ranges[(start, address - 1)] = code
                if address + 1 <= end:
                    self._unsupported_holding_ranges[(address + 1, end)] = code

    def _mark_holding_unsupported(self, start: int, end: int, code: int) -> None:
        """Track unsupported holding register range without overlaps."""
        for (exist_start, exist_end), exist_code in list(self._unsupported_holding_ranges.items()):
            if exist_end < start or exist_start > end:
                continue
            del self._unsupported_holding_ranges[(exist_start, exist_end)]
            if exist_start < start:
                self._unsupported_holding_ranges[(exist_start, start - 1)] = exist_code
            if end < exist_end:
                self._unsupported_holding_ranges[(end + 1, exist_end)] = exist_code
        self._unsupported_holding_ranges[(start, end)] = code

    def _mark_input_unsupported(self, start: int, end: int, code: int | None) -> None:
        """Cache unsupported input register range, merging overlaps."""

        for (old_start, old_end), _ in list(self._unsupported_input_ranges.items()):
            if end < old_start or start > old_end:
                continue
            del self._unsupported_input_ranges[(old_start, old_end)]
            start = min(start, old_start)
            end = max(end, old_end)

        self._unsupported_input_ranges[(start, end)] = code or 0

    def _unpack_read_args(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None,
    ) -> tuple[AsyncModbusTcpClient | AsyncModbusSerialClientType | None, int, int]:
        """Unpack the overloaded (client, address, count) / (address, count) signatures."""
        if count is None or isinstance(client_or_address, int):
            return None, int(client_or_address), address_or_count
        return client_or_address, address_or_count, count  # type: ignore[return-value]

    def _resolve_transport_and_client(
        self,
        client: AsyncModbusTcpClient | AsyncModbusSerialClientType | None,
    ) -> tuple[Any, Any]:
        """Return (transport, client) ready for reads. Raises if neither available."""
        transport = self._transport if client is None else None
        if client is None and transport is None:
            client = self._client
        if client is None and transport is None:
            raise ConnectionException("Modbus transport is not connected")
        return transport, client

    def _track_input_failure(self, count: int, address: int) -> None:
        """Increment the failure counter for an input register (only for single-reg reads)."""
        if count != 1:
            return
        failures = self._input_failures.get(address, 0) + 1
        self._input_failures[address] = failures
        if failures >= self.retry and address not in self._failed_input:
            self._failed_input.add(address)
            self.failed_addresses["modbus_exceptions"]["input_registers"].add(address)
            _LOGGER.warning("Device does not expose register %d", address)

    def _track_holding_failure(self, count: int, address: int) -> None:
        """Increment the failure counter for a holding register (only for single-reg reads)."""
        if count != 1:
            return
        failures = self._holding_failures.get(address, 0) + 1
        self._holding_failures[address] = failures
        if failures >= self.retry and address not in self._failed_holding:
            self._failed_holding.add(address)
            self.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)
            _LOGGER.warning("Device does not expose register %d", address)

    async def _read_input(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        """Read input registers with retry and backoff.

        ``skip_cache`` is used when probing individual registers after a block
        read failed. When ``True`` the cached set of failed registers is not
        checked, allowing each register to be queried once before being cached
        as missing.
        """
        client, address, count = self._unpack_read_args(client_or_address, address_or_count, count)
        start = address
        end = address + count - 1

        if not skip_cache:
            for skip_start, skip_end in self._unsupported_input_ranges:
                if skip_start <= start and end <= skip_end:
                    self.failed_addresses["modbus_exceptions"]["input_registers"].update(
                        range(start, end + 1)
                    )
                    return None
        if not skip_cache and any(reg in self._failed_input for reg in range(start, end + 1)):
            first = next(reg for reg in range(start, end + 1) if reg in self._failed_input)
            skip_start = skip_end = first
            while skip_start - 1 in self._failed_input:
                skip_start -= 1
            while skip_end + 1 in self._failed_input:
                skip_end += 1
            if (skip_start, skip_end) not in self._input_skip_log_ranges:
                _LOGGER.debug(
                    "Skipping cached failed input registers %d-%d",
                    skip_start,
                    skip_end,
                )
                self._input_skip_log_ranges.add((skip_start, skip_end))
            self.failed_addresses["modbus_exceptions"]["input_registers"].update(
                range(skip_start, skip_end + 1)
            )
            return None

        transport, client = self._resolve_transport_and_client(client)

        attempted_reads = 0
        aborted_transiently = False
        for attempt in range(1, self.retry + 1):
            attempted_reads = attempt
            try:
                if transport is not None:
                    response = await transport.read_input_registers(
                        self.slave_id,
                        address,
                        count=count,
                    )
                else:
                    response = await _call_modbus_compat(
                        client.read_input_registers,
                        self.slave_id,
                        address,
                        count=count,
                        attempt=attempt,
                        retry=self.retry,
                        timeout=self.timeout,
                        backoff=self.backoff,
                        backoff_jitter=self.backoff_jitter,
                    )
                if response is not None:
                    if response.isError():
                        code = getattr(response, "exception_code", None)
                        _LOGGER.warning("Exception code %s while reading holding registers %d-%d", code, start, end)
                        self._failed_input.update(range(start, end + 1))
                        self._mark_input_unsupported(start, end, code)
                        self.failed_addresses["modbus_exceptions"]["input_registers"].update(
                            range(start, end + 1)
                        )
                        return None
                    if skip_cache and count == 1:
                        self._mark_input_supported(address)
                    registers = cast(list[int], response.registers)
                    _LOGGER.debug(
                        "Read input registers %d-%d: %s",
                        start,
                        end,
                        registers,
                    )
                    return registers
                _LOGGER.debug(
                    "Attempt %d failed to read input %d: %s",
                    attempt,
                    address,
                    response,
                )
            except ModbusIOException as exc:
                _LOGGER.debug(
                    "Modbus IO error reading input registers %d-%d on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
                if is_request_cancelled_error(exc):
                    aborted_transiently = True
                    break  # Treat cancellation like a timeout — stop retrying
                self._track_input_failure(count, address)
            except TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading input registers %d-%d on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
                aborted_transiently = True
                break
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading input %d on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Failed to read input registers %d-%d on attempt %d: %s",
                    start,
                    end,
                    attempt,
                    exc,
                    exc_info=True,
                )
                self._track_input_failure(count, address)

            await _sleep_retry_backoff(backoff=self.backoff, backoff_jitter=self.backoff_jitter, attempt=attempt, retry=self.retry)

        if aborted_transiently:
            _LOGGER.warning(
                "Aborted reading input registers %d-%d after %d/%d attempts due to timeout/cancellation",
                start,
                end,
                attempted_reads,
                self.retry,
            )
            return None

        self.failed_addresses["modbus_exceptions"]["input_registers"].update(range(start, end + 1))
        _LOGGER.error(
            "Failed to read input registers %d-%d after %d retries",
            start,
            end,
            self.retry,
        )
        return None

    async def _read_register_block(
        self,
        read_fn: Any,
        client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        """Read a contiguous register block in MAX-sized chunks using read_fn."""
        if count is None:
            start = int(client_or_start)
            count = start_or_count
            client: AsyncModbusTcpClient | AsyncModbusSerialClientType | None = None
        elif isinstance(client_or_start, int):
            start = client_or_start
            count = start_or_count
            client = None
        else:
            client = client_or_start
            start = start_or_count

        results: list[int] = []
        active_client = client or self._client
        for chunk_start, chunk_count in chunk_register_range(start, count, self.effective_batch):
            block = await (
                read_fn(chunk_start, chunk_count)
                if active_client is None
                else read_fn(active_client, chunk_start, chunk_count)
            )
            if block is None:
                return None
            results.extend(block)
        return results

    async def _read_input_block(
        self,
        client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        """Read a contiguous input register block in MAX-sized chunks."""
        return await self._read_register_block(self._read_input, client_or_start, start_or_count, count)

    async def _read_holding_block(
        self,
        client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        """Read a contiguous holding register block in MAX-sized chunks."""
        return await self._read_register_block(self._read_holding, client_or_start, start_or_count, count)

    async def _read_holding(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        """Read holding registers with retry, backoff and failure tracking.

        ``skip_cache`` is used when probing individual registers after a block
        read failed. When ``True`` the cached sets of unsupported ranges and
        failed registers are ignored, allowing each register to be queried
        once before being cached again.
        """
        client, address, count = self._unpack_read_args(client_or_address, address_or_count, count)
        start = address
        end = address + count - 1

        if not skip_cache:
            for skip_start, skip_end in self._unsupported_holding_ranges:
                if skip_start <= start and end <= skip_end:
                    self.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                        range(start, end + 1)
                    )
                    return None

            if address in self._failed_holding:
                _LOGGER.debug("Skipping cached failed holding register %d", address)
                self.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)
                return None

        failures = self._holding_failures.get(address, 0)
        if failures >= self.retry:
            _LOGGER.warning("Skipping unsupported holding register %d", address)
            self.failed_addresses["modbus_exceptions"]["holding_registers"].add(address)
            return None

        transport, client = self._resolve_transport_and_client(client)

        attempted_reads = 0
        aborted_transiently = False
        for attempt in range(1, self.retry + 1):
            attempted_reads = attempt
            try:
                if transport is not None:
                    response = await transport.read_holding_registers(
                        self.slave_id,
                        address,
                        count=count,
                    )
                else:
                    response = await _call_modbus_compat(
                        client.read_holding_registers,
                        self.slave_id,
                        address,
                        count=count,
                        attempt=attempt,
                        retry=self.retry,
                        timeout=self.timeout,
                        backoff=self.backoff,
                        backoff_jitter=self.backoff_jitter,
                    )
                if response is not None:
                    if response.isError():
                        code = getattr(response, "exception_code", None)
                        _LOGGER.warning("Exception code %s while reading holding registers %d-%d", code, start, end)
                        if code == 2:
                            self._failed_holding.update(range(start, end + 1))
                            self._mark_holding_unsupported(start, end, code)
                            self.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                                range(start, end + 1)
                            )
                            return None
                        if count == 1:
                            failures = self._holding_failures.get(address, 0) + 1
                            self._holding_failures[address] = failures
                            if failures >= self.retry:
                                self._failed_holding.update(range(start, end + 1))
                                self._mark_holding_unsupported(start, end, code or 0)
                                self.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                                    range(start, end + 1)
                                )
                                return None
                        continue
                    if skip_cache and count == 1:
                        self._mark_holding_supported(address)
                    if address in self._holding_failures:
                        del self._holding_failures[address]
                    registers = cast(list[int], response.registers)
                    _LOGGER.debug(
                        "Read holding registers %d-%d: %s",
                        start,
                        end,
                        registers,
                    )
                    return registers
            except TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading holding %d (attempt %d/%d): %s",
                    address,
                    attempt,
                    self.retry,
                    exc,
                    exc_info=True,
                )
                self._track_holding_failure(count, address)
                aborted_transiently = True
            except ModbusIOException as exc:
                if is_request_cancelled_error(exc):
                    _LOGGER.debug(
                        "Cancelled reading holding registers %d-%d on attempt %d/%d: %s",
                        start,
                        end,
                        attempt,
                        self.retry,
                        exc,
                    )
                    aborted_transiently = True
                    break
                _LOGGER.debug(
                    "Failed to read holding %d (attempt %d/%d): %s",
                    address,
                    attempt,
                    self.retry,
                    exc,
                    exc_info=True,
                )
                self._track_holding_failure(count, address)
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Failed to read holding %d (attempt %d/%d): %s",
                    address,
                    attempt,
                    self.retry,
                    exc,
                    exc_info=True,
                )
                self._track_holding_failure(count, address)
            except asyncio.CancelledError:
                _LOGGER.debug(
                    "Cancelled reading holding %d on attempt %d/%d",
                    address,
                    attempt,
                    self.retry,
                )
                raise
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading holding %d on attempt %d: %s",
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            await _sleep_retry_backoff(backoff=self.backoff, backoff_jitter=self.backoff_jitter, attempt=attempt, retry=self.retry)

        if aborted_transiently:
            _LOGGER.warning(
                "Aborted reading holding registers %d-%d after %d/%d attempts due to timeout/cancellation",
                start,
                end,
                attempted_reads,
                self.retry,
            )
            _LOGGER.error(
                "Failed to read holding registers %d-%d after %d retries",
                start,
                end,
                self.retry,
            )
            return None

        _LOGGER.error(
            "Failed to read holding registers %d-%d after %d retries",
            start,
            end,
            self.retry,
        )
        self.failed_addresses["modbus_exceptions"]["holding_registers"].update(
            range(start, end + 1)
        )
        return None

    async def _read_bit_registers(
        self,
        method_name: str,
        failed_key: str,
        type_name: str,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        """Shared implementation for coil and discrete input reads with retry and backoff."""
        if count is None:
            address = int(client_or_address)
            count = address_or_count
            client = self._client
        elif isinstance(client_or_address, int):
            address = client_or_address
            count = address_or_count
            client = self._client
        else:
            client = client_or_address
            address = address_or_count

        if client is None:
            raise ConnectionException("Modbus client is not connected")
        # Refresh client from transport in case transport reconnected since scan start
        if client is self._client and self._transport is not None:
            fresh = getattr(self._transport, "client", None)
            if fresh is not None:
                client = fresh
        for attempt in range(1, self.retry + 1):
            try:
                response: Any = await _call_modbus_compat(
                    getattr(client, method_name),
                    self.slave_id,
                    address,
                    count=count,
                    attempt=attempt,
                    retry=self.retry,
                    timeout=self.timeout,
                    backoff=self.backoff,
                    backoff_jitter=self.backoff_jitter,
                )
                if response is not None and not response.isError():
                    bits = cast(list[bool], response.bits[:count])
                    _LOGGER.debug(
                        "Read %s registers %d-%d: %s",
                        type_name,
                        address,
                        address + count - 1,
                        bits,
                    )
                    return bits
            except TimeoutError as exc:
                _LOGGER.warning(
                    "Timeout reading %s %d on attempt %d: %s",
                    type_name,
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
            except (ModbusException, ConnectionException) as exc:
                _LOGGER.debug(
                    "Failed to read %s %d on attempt %d: %s",
                    type_name,
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                if self._transport is not None:
                    try:
                        await self._transport.ensure_connected()
                        transport_client = getattr(self._transport, "client", None)
                        if transport_client is not None:
                            client = transport_client
                            self._client = transport_client
                    except Exception as exc:
                        _LOGGER.debug("Transport client refresh failed during %s read: %s", type_name, exc)
            except asyncio.CancelledError:
                _LOGGER.debug(
                    "Cancelled reading %s %d on attempt %d",
                    type_name,
                    address,
                    attempt,
                )
                raise
            except OSError as exc:
                _LOGGER.error(
                    "Unexpected error reading %s %d on attempt %d: %s",
                    type_name,
                    address,
                    attempt,
                    exc,
                    exc_info=True,
                )
                break

            await _sleep_retry_backoff(backoff=self.backoff, backoff_jitter=self.backoff_jitter, attempt=attempt, retry=self.retry)

        self.failed_addresses["modbus_exceptions"][failed_key].update(
            range(address, address + count)
        )
        _LOGGER.error(
            "Failed to read %s registers %d-%d after %d retries",
            type_name,
            address,
            address + count - 1,
            self.retry,
        )
        return None

    async def _read_coil(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        """Read coil registers with retry and backoff."""
        return await self._read_bit_registers(
            "read_coils", "coil_registers", "coil",
            client_or_address, address_or_count, count,
        )

    async def _read_discrete(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        """Read discrete input registers with retry and backoff."""
        return await self._read_bit_registers(
            "read_discrete_inputs", "discrete_inputs", "discrete",
            client_or_address, address_or_count, count,
        )
