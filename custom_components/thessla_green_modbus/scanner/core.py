"""Device scanner for ThesslaGreen Modbus integration."""

from __future__ import annotations

import importlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict as _dataclasses_asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pymodbus.client import AsyncModbusTcpClient

from .. import modbus_helpers as _mh
from .. import scanner_register_maps as _register_maps
from ..const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
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
    HOLDING_BATCH_BOUNDARIES,
    KNOWN_MISSING_REGISTERS,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
)
from ..modbus_exceptions import ConnectionException, ModbusIOException
from ..modbus_helpers import (
    _call_modbus,
    async_maybe_await_close,
)
from ..modbus_helpers import group_reads as _group_reads
from ..modbus_transport import (
    BaseModbusTransport,
    RawRtuOverTcpTransport,
    RtuModbusTransport,
    TcpModbusTransport,
)
from ..scanner_device_info import DeviceCapabilities, ScannerDeviceInfo
from ..scanner_helpers import (
    MAX_BATCH_REGISTERS,
)
from ..scanner_helpers import (
    SAFE_REGISTERS as _SAFE_REGISTERS,
)
from ..scanner_register_maps import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
    MULTI_REGISTER_SIZES,
)
from ..utils import (
    resolve_connection_settings,
)
from . import capabilities as scanner_capabilities
from . import firmware as scanner_firmware
from . import io as _scanner_io_impl
from . import io as scanner_domain_io
from . import orchestration as scanner_orchestration
from . import registers as scanner_registers
from . import setup as scanner_setup

try:  # pragma: no cover - optional during isolated tests
    from ..registers.loader import (
        async_get_all_registers,
        async_registers_sha256,
        get_all_registers,
        get_registers_path,
        registers_sha256,
    )
except (ImportError, AttributeError):  # pragma: no cover - fallback when stubs incomplete

    async def async_get_all_registers(
        hass: Any | None, json_path: Path | str | None = None
    ) -> list[RegisterDef]:
        return []

    async def async_registers_sha256(hass: Any | None, json_path: Path | str) -> str:
        return ""

    def get_all_registers(json_path: Path | str | None = None) -> list[RegisterDef]:
        return []

    def get_registers_path() -> Path:
        return Path(".")

    def registers_sha256(json_path: Path | str) -> str:
        return ""


asdict = _dataclasses_asdict  # re-exported for test monkeypatching

_LOGGER = logging.getLogger(__name__)
REGISTER_DEFINITIONS = _register_maps.REGISTER_DEFINITIONS
SAFE_REGISTERS = _SAFE_REGISTERS

try:
    _pymodbus: Any = importlib.import_module("pymodbus")
    _pymodbus_client: Any = importlib.import_module("pymodbus.client")
    if not hasattr(_pymodbus, "client"):
        _pymodbus.client = _pymodbus_client  # pragma: no cover - defensive
except (ImportError, AttributeError) as _exc:  # pragma: no cover - defensive
    _LOGGER.debug("Could not attach pymodbus.client submodule: %s", _exc)

if TYPE_CHECKING:  # pragma: no cover - typing helper only
    from pymodbus.client import AsyncModbusSerialClient as AsyncModbusSerialClientType

    from ..registers.loader import RegisterDef
else:
    AsyncModbusSerialClientType = Any


def _ensure_pymodbus_client_module() -> None:
    """Ensure `pymodbus.client` is importable and attached to `pymodbus`."""
    _scanner_io_impl.ensure_pymodbus_client_module()


# Register definition caches - populated lazily


def is_request_cancelled_error(exc: ModbusIOException) -> bool:
    """Return True when a modbus IO error indicates a cancelled request."""
    return bool(_scanner_io_impl.is_request_cancelled_error(exc))


async def _maybe_retry_yield(backoff: float, attempt: int, retry: int) -> None:
    """Yield control between retries to allow cancellation to propagate."""
    await _scanner_io_impl._maybe_retry_yield(backoff=backoff, attempt=attempt, retry=retry)


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
    return await _scanner_io_impl._call_modbus_compat_fn(
        _call_modbus,
        func,
        slave_id,
        address,
        count=count,
        attempt=attempt,
        retry=retry,
        timeout=timeout,
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        apply_backoff=apply_backoff,
    )


async def _sleep_retry_backoff(
    *, backoff: float, backoff_jitter: float | tuple[float, float] | None, attempt: int, retry: int
) -> None:
    """Sleep between retries using modbus_helpers timing semantics."""
    await _scanner_io_impl._sleep_retry_backoff_fn(
        calculate_backoff_delay=lambda base, at, jitter: _mh._calculate_backoff_delay(
            base=base, attempt=at, jitter=jitter
        ),
        backoff=backoff,
        backoff_jitter=backoff_jitter,
        attempt=attempt,
        retry=retry,
    )


# Register-map compatibility wrappers kept in scanner_core for existing tests/imports.
REGISTER_HASH = _register_maps.REGISTER_HASH


def _sync_register_hash_from_maps() -> None:
    """Synchronize locally re-exported register hash from scanner_register_maps."""
    global REGISTER_HASH
    REGISTER_HASH = _register_maps.REGISTER_HASH


def _build_register_maps_from(regs: list[Any], register_hash: str) -> None:
    """Populate register lookup maps from provided register definitions."""
    _register_maps._build_register_maps_from(regs, register_hash)
    _sync_register_hash_from_maps()


def _build_register_maps() -> None:
    """Populate register lookup maps from current register definitions."""
    _register_maps._build_register_maps()
    _sync_register_hash_from_maps()


async def _async_build_register_maps(hass: Any | None) -> None:
    """Populate register lookup maps from current definitions asynchronously."""
    await _register_maps._async_build_register_maps(hass)
    _sync_register_hash_from_maps()


def _ensure_register_maps() -> None:
    """Ensure register lookup maps are populated."""
    _register_maps.REGISTER_HASH = REGISTER_HASH
    _register_maps._ensure_register_maps()
    _sync_register_hash_from_maps()


async def _async_ensure_register_maps(hass: Any | None) -> None:
    """Ensure register lookup maps are populated without blocking the event loop."""
    _register_maps.REGISTER_HASH = REGISTER_HASH
    await _register_maps._async_ensure_register_maps(hass)
    _sync_register_hash_from_maps()


async def async_ensure_register_maps(hass: Any | None = None) -> None:
    """Ensure register lookup maps are populated without blocking the event loop."""
    await _async_ensure_register_maps(hass)


# Ensure register lookup maps are available before use


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
        self._register_ranges: dict[str, tuple[float | None, float | None]] = {}
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
            self._registers = loaded[0]
            self._register_ranges = (
                loaded[1] if len(loaded) > 1 and isinstance(loaded[1], dict) else {}
            )
        else:
            self._registers = loaded
            self._register_ranges = {}
        self._names_by_address = {
            4: self._build_names_by_address(
                {name: addr for addr, name in self._registers.get(4, {}).items()} or INPUT_REGISTERS
            ),
            3: self._build_names_by_address(
                {name: addr for addr, name in self._registers.get(3, {}).items()}
                or HOLDING_REGISTERS
            ),
            1: self._build_names_by_address(
                {name: addr for addr, name in self._registers.get(1, {}).items()} or COIL_REGISTERS
            ),
            2: self._build_names_by_address(
                {name: addr for addr, name in self._registers.get(2, {}).items()}
                or DISCRETE_INPUT_REGISTERS
            ),
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
        mode_order = (
            [CONNECTION_MODE_TCP, CONNECTION_MODE_TCP_RTU]
            if prefer_tcp
            else [
                CONNECTION_MODE_TCP_RTU,
                CONNECTION_MODE_TCP,
            ]
        )
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

        await scanner_setup.verify_connection(
            self,
            safe_registers=SAFE_REGISTERS,
            register_definitions=REGISTER_DEFINITIONS,
            holding_batch_boundaries=HOLDING_BATCH_BOUNDARIES,
            group_reads=_group_reads,
            rtu_transport_cls=RtuModbusTransport,
        )

    def _is_valid_register_value(self, name: str, value: int) -> bool:
        """Validate a register value against known constraints."""
        return scanner_capabilities.is_valid_register_value(self, name, value)

    def _analyze_capabilities(self) -> DeviceCapabilities:
        """Derive device capabilities from discovered registers."""
        return scanner_capabilities.analyze_capabilities(self)

    def _group_registers_for_batch_read(
        self,
        addresses: list[int],
        *,
        max_gap: int = 1,
        max_batch: int | None = None,
        boundaries: frozenset[int] | None = None,
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
        groups = _group_reads(addresses, max_block_size=max_batch, boundaries=boundaries)

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

    async def _scan_firmware_info(self, info_regs: list[int], device: ScannerDeviceInfo) -> None:
        """Parse firmware version from info_regs and update device."""
        await scanner_firmware.scan_firmware_info(self, info_regs, device)

    async def _scan_device_identity(self, info_regs: list[int], device: ScannerDeviceInfo) -> None:
        """Parse serial number and device name from registers into device."""
        await scanner_firmware.scan_device_identity(self, info_regs, device)

    def _select_scan_registers(
        self,
    ) -> tuple[dict[int, str], dict[int, str], dict[int, str], dict[int, str], int, int, int, int]:
        """Select which registers to scan and compute address ranges."""
        input_max = max(self._registers.get(4, {}).keys(), default=-1)
        holding_max = max(self._registers.get(3, {}).keys(), default=-1)
        coil_max = max(self._registers.get(1, {}).keys(), default=-1)
        discrete_max = max(self._registers.get(2, {}).keys(), default=-1)
        if self.full_register_scan:
            input_registers = self._registers.get(4, {}) or {
                addr: name for name, addr in INPUT_REGISTERS.items()
            }
            holding_registers = self._registers.get(3, {}) or {
                addr: name for name, addr in HOLDING_REGISTERS.items()
            }
            coil_registers = self._registers.get(1, {}) or {
                addr: name for name, addr in COIL_REGISTERS.items()
            }
            discrete_registers = self._registers.get(2, {}) or {
                addr: name for name, addr in DISCRETE_INPUT_REGISTERS.items()
            }
        else:
            global_input = {addr: name for name, addr in INPUT_REGISTERS.items()}
            global_holding = {addr: name for name, addr in HOLDING_REGISTERS.items()}
            global_coil = {addr: name for name, addr in COIL_REGISTERS.items()}
            global_discrete = {addr: name for name, addr in DISCRETE_INPUT_REGISTERS.items()}

            loaded_input = self._registers.get(4, {})
            loaded_holding = self._registers.get(3, {})
            loaded_coil = self._registers.get(1, {})
            loaded_discrete = self._registers.get(2, {})

            input_registers = (
                loaded_input
                if loaded_input and (not global_input or len(loaded_input) <= len(global_input))
                else global_input
            )
            holding_registers = (
                loaded_holding
                if loaded_holding
                and (not global_holding or len(loaded_holding) <= len(global_holding))
                else global_holding
            )
            coil_registers = (
                loaded_coil
                if loaded_coil and (not global_coil or len(loaded_coil) <= len(global_coil))
                else global_coil
            )
            discrete_registers = (
                loaded_discrete
                if loaded_discrete
                and (not global_discrete or len(loaded_discrete) <= len(global_discrete))
                else global_discrete
            )

        return (
            input_registers,
            holding_registers,
            coil_registers,
            discrete_registers,
            input_max,
            holding_max,
            coil_max,
            discrete_max,
        )

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
        await scanner_orchestration.run_full_scan(
            self,
            input_max,
            holding_max,
            coil_max,
            discrete_max,
            unknown_registers,
            scanned_registers,
        )

    async def _scan_register_batch(
        self,
        reg_type: str,
        addr_to_names: dict[int, set[str]],
        addresses: list[int],
        read_fn: Callable[..., Awaitable[list[int] | None]],
        *,
        boundaries: frozenset[int] | None = None,
    ) -> None:
        """Read a batch of registers of one FC type, with per-address fallback."""
        await scanner_registers.scan_register_batch(
            self,
            reg_type,
            addr_to_names,
            addresses,
            read_fn,
            boundaries=boundaries,
        )

    async def _scan_named_input(self, input_registers: dict[int, str]) -> None:
        """Scan FC04 input registers in batches."""
        await scanner_registers.scan_named_input(self, input_registers)

    async def _scan_named_holding(self, holding_registers: dict[int, str]) -> None:
        """Scan FC03 holding registers in batches, handling multi-word registers."""
        await scanner_registers.scan_named_holding(self, holding_registers)

    async def _scan_named_coil(self, coil_registers: dict[int, str]) -> None:
        """Scan FC01 coil registers in batches."""
        await scanner_registers.scan_named_coil(self, coil_registers)

    async def _scan_named_discrete(self, discrete_registers: dict[int, str]) -> None:
        """Scan FC02 discrete input registers in batches."""
        await scanner_registers.scan_named_discrete(self, discrete_registers)

    async def _run_named_scan(
        self,
        input_registers: dict[int, str],
        holding_registers: dict[int, str],
        coil_registers: dict[int, str],
        discrete_registers: dict[int, str],
    ) -> None:
        """Scan only named/known registers (normal scan mode)."""
        await scanner_registers.run_named_scan(
            self,
            input_registers,
            holding_registers,
            coil_registers,
            discrete_registers,
        )

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
        return scanner_registers.compute_scan_blocks(
            self,
            input_registers,
            holding_registers,
            coil_registers,
            discrete_registers,
            input_max,
            holding_max,
            coil_max,
            discrete_max,
        )

    def _collect_missing_registers(
        self,
        input_registers: dict[int, str],
        holding_registers: dict[int, str],
        coil_registers: dict[int, str],
        discrete_registers: dict[int, str],
    ) -> dict[str, dict[str, int]]:
        """Return registers that were expected but not found during scan."""
        return scanner_registers.collect_missing_registers(
            self,
            input_registers,
            holding_registers,
            coil_registers,
            discrete_registers,
        )

    async def scan(self) -> dict[str, Any]:  # pragma: no cover - defensive
        """Perform the actual register scan using an established connection."""
        return await scanner_orchestration.scan(self)

    async def scan_device(self) -> dict[str, Any]:
        """Open the Modbus connection, perform a scan and close the client."""
        self._rtu_transport_cls = RtuModbusTransport
        return await scanner_orchestration.scan_device(self)

    async def _load_registers(
        self,
    ) -> tuple[
        dict[int, dict[int, str]],
        dict[str, tuple[float | None, float | None]],
    ]:
        """Load Modbus register definitions and value ranges."""
        return await scanner_registers.load_registers(self, async_get_all_registers)

    def _log_skipped_ranges(self) -> None:
        """Log summary of ranges skipped due to Modbus exceptions."""
        scanner_registers.log_skipped_ranges(self)

    def _filter_unsupported_addresses(self, reg_type: str, addrs: set[int]) -> set[int]:
        """Return failed addresses that are not already covered by unsupported spans."""
        return scanner_capabilities.filter_unsupported_addresses(self, reg_type, addrs)

    def _log_invalid_value(self, name: str, raw: int) -> None:
        """Log a register value that failed validation."""
        scanner_capabilities.log_invalid_value(self, name, raw)

    def _mark_input_supported(self, address: int) -> None:
        """Remove address from cached unsupported input ranges after success."""
        scanner_capabilities.mark_input_supported(self, address)

    def _mark_holding_supported(self, address: int) -> None:
        """Remove address from cached unsupported holding ranges after success."""
        scanner_capabilities.mark_holding_supported(self, address)

    def _mark_holding_unsupported(self, start: int, end: int, code: int) -> None:
        """Track unsupported holding register range without overlaps."""
        scanner_capabilities.mark_holding_unsupported(self, start, end, code)

    def _mark_input_unsupported(self, start: int, end: int, code: int | None) -> None:
        """Cache unsupported input register range, merging overlaps."""
        scanner_capabilities.mark_input_unsupported(self, start, end, code)

    def _unpack_read_args(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None,
    ) -> tuple[AsyncModbusTcpClient | AsyncModbusSerialClientType | None, int, int]:
        """Unpack the overloaded (client, address, count) / (address, count) signatures."""
        return scanner_domain_io.unpack_read_args(self, client_or_address, address_or_count, count)

    def _resolve_transport_and_client(
        self,
        client: AsyncModbusTcpClient | AsyncModbusSerialClientType | None,
    ) -> tuple[Any, Any]:
        """Return (transport, client) ready for reads. Raises if neither available."""
        return scanner_domain_io.resolve_transport_and_client(self, client)

    def _track_input_failure(self, count: int, address: int) -> None:
        """Increment the failure counter for an input register (only for single-reg reads)."""
        scanner_domain_io.track_input_failure(self, count, address)

    def _track_holding_failure(self, count: int, address: int) -> None:
        """Increment the failure counter for a holding register (only for single-reg reads)."""
        scanner_domain_io.track_holding_failure(self, count, address)

    async def _read_input(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        """Read input registers with retry and backoff."""
        return await scanner_domain_io.read_input(
            self,
            client_or_address,
            address_or_count,
            count,
            skip_cache=skip_cache,
        )

    async def _read_register_block(
        self,
        read_fn: Any,
        client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        """Read a contiguous register block in MAX-sized chunks using read_fn."""
        return await scanner_domain_io.read_register_block(
            self,
            read_fn,
            client_or_start,
            start_or_count,
            count,
        )

    async def _read_input_block(
        self,
        client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        """Read a contiguous input register block in MAX-sized chunks."""
        return await self._read_register_block(
            self._read_input, client_or_start, start_or_count, count
        )

    async def _read_holding_block(
        self,
        client_or_start: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        start_or_count: int,
        count: int | None = None,
    ) -> list[int] | None:
        """Read a contiguous holding register block in MAX-sized chunks."""
        return await self._read_register_block(
            self._read_holding, client_or_start, start_or_count, count
        )

    async def _read_holding(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
        *,
        skip_cache: bool = False,
    ) -> list[int] | None:
        """Read holding registers with retry, backoff and failure tracking."""
        return await scanner_domain_io.read_holding(
            self,
            client_or_address,
            address_or_count,
            count,
            skip_cache=skip_cache,
        )

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
        return await scanner_domain_io.read_bit_registers(
            self,
            method_name,
            failed_key,
            type_name,
            client_or_address,
            address_or_count,
            count,
        )

    async def _read_coil(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        """Read coil registers with retry and backoff."""
        return await scanner_domain_io.read_coil(self, client_or_address, address_or_count, count)

    async def _read_discrete(
        self,
        client_or_address: AsyncModbusTcpClient | AsyncModbusSerialClientType | int,
        address_or_count: int,
        count: int | None = None,
    ) -> list[bool] | None:
        """Read discrete input registers with retry and backoff."""
        return await scanner_domain_io.read_discrete(self, client_or_address, address_or_count, count)
