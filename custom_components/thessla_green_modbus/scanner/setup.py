"""Connection/setup routines for the scanner runtime."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException

from ..const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_MODE_TCP,
    CONNECTION_MODE_TCP_RTU,
    CONNECTION_TYPE_RTU,
    CONNECTION_TYPE_TCP,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_PARITY,
    DEFAULT_STOP_BITS,
    HOLDING_BATCH_BOUNDARIES,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
)
from ..registers.read_planner import group_reads as _group_reads
from ..scanner.helpers import MAX_BATCH_REGISTERS, SAFE_REGISTERS
from ..scanner.register_maps import REGISTER_DEFINITIONS
from ..transport.base import BaseModbusTransport
from ..transport.rtu import RtuModbusTransport
from ..transport.tcp import TcpModbusTransport
from ..transport.tcp_rtu import RawRtuOverTcpTransport
from ..utils import default_connection_mode
from . import state as _state
from .io import is_request_cancelled_error
from .io_runtime import attach_pymodbus_client_module
from .register_map_runtime import async_ensure_register_maps, initial_register_hash

_LOGGER = logging.getLogger(__name__)


def normalize_effective_batch(
    max_registers_per_request: Any,
    *,
    max_batch: int,
) -> int:
    """Clamp *max_registers_per_request* to the valid [1, max_batch] range.

    Returns *max_batch* when the value cannot be converted to an integer.
    """
    try:
        effective = min(int(max_registers_per_request), max_batch)
    except (TypeError, ValueError):
        effective = max_batch
    return max(1, effective)


def normalize_backoff_jitter(
    backoff_jitter: float | tuple[float, float] | list[float] | str | None,
) -> float | tuple[float, float] | None:
    """Normalize supported jitter inputs to float/tuple/None."""
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
    return jitter


def apply_scanner_params(
    scanner: Any,
    *,
    host: str,
    port: int,
    slave_id: int,
    timeout: int,
    retry: int,
    backoff: float,
    backoff_jitter: float | tuple[float, float] | None,
    verbose_invalid_values: bool,
    scan_uart_settings: bool,
    skip_known_missing: bool,
    deep_scan: bool,
    full_register_scan: bool,
    safe_scan: bool,
    max_registers_per_request: int,
    delay_between_requests_ms: int = 0,
    connection_type: str,
    connection_mode: str | None,
    serial_port: str,
    baud_rate: int,
    parity: str,
    stop_bits: int,
    hass: Any | None,
) -> None:
    """Assign all scalar parameters and connection state to a scanner instance."""
    scanner.host = host
    scanner.port = port
    scanner.slave_id = slave_id
    scanner.timeout = timeout
    scanner.retry = retry
    try:
        scanner.backoff = float(backoff)
    except (TypeError, ValueError):
        scanner.backoff = 0.0
    scanner.backoff_jitter = normalize_backoff_jitter(backoff_jitter)
    scanner.verbose_invalid_values = verbose_invalid_values
    scanner.scan_uart_settings = scan_uart_settings
    scanner.skip_known_missing = skip_known_missing
    scanner.deep_scan = deep_scan
    scanner.full_register_scan = full_register_scan
    scanner.safe_scan = safe_scan
    scanner.effective_batch = normalize_effective_batch(
        max_registers_per_request, max_batch=MAX_BATCH_REGISTERS
    )
    scanner.max_registers_per_request = scanner.effective_batch
    scanner.delay_between_requests_ms = max(0, int(delay_between_requests_ms))

    resolved_type, resolved_mode, resolved_fixed_mode = _state.resolve_connection_configuration(
        connection_type, connection_mode, port
    )
    _state.apply_connection_state(
        scanner,
        _state.build_connection_state(
            connection_type=resolved_type,
            connection_mode=resolved_mode,
            resolved_connection_mode=resolved_fixed_mode,
            serial_port=serial_port,
            baud_rate=baud_rate,
            parity=parity,
            stop_bits=stop_bits,
        ),
    )
    scanner._hass = hass


def initialize_runtime_collections(scanner: Any, capabilities_cls: Any) -> None:
    """Initialize mutable runtime collections for scanner state."""
    scanner.available_registers = {
        "input_registers": set(),
        "holding_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
    }
    scanner.capabilities = capabilities_cls()

    scanner._registers = {}
    scanner._register_ranges = {}
    scanner._names_by_address = {4: {}, 3: {}, 1: {}, 2: {}}

    scanner._holding_failures = {}
    scanner._failed_holding = set()
    scanner._input_failures = {}
    scanner._failed_input = set()
    scanner._input_skip_log_ranges = set()

    scanner._unsupported_input_ranges = {}
    scanner._unsupported_holding_ranges = {}

    scanner._client = None
    scanner._transport = None
    scanner._reported_invalid = set()
    scanner.failed_addresses = {
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
    scanner._sensor_unavailable_checks = {}


def populate_known_missing_addresses(scanner: Any) -> None:
    """Pre-compute addresses of known missing registers for batch grouping."""
    scanner._known_missing_addresses = set()


def update_known_missing_addresses(
    scanner: Any,
    *,
    known_missing_registers: dict[str, set[str]],
    input_registers: dict[str, int],
    holding_registers: dict[str, int],
    coil_registers: dict[str, int],
    discrete_input_registers: dict[str, int],
    multi_register_sizes: dict[str, int],
) -> None:
    """Populate cached missing register addresses from known missing list."""
    scanner._known_missing_addresses.clear()
    register_mappings = {
        "input_registers": input_registers,
        "holding_registers": holding_registers,
        "coil_registers": coil_registers,
        "discrete_inputs": discrete_input_registers,
    }
    for reg_type, names in known_missing_registers.items():
        mapping = register_mappings[reg_type]
        for name in names:
            if (addr := mapping.get(name)) is None:
                continue
            size = multi_register_sizes.get(name, 1)
            scanner._known_missing_addresses.update(range(addr, addr + size))


async def async_setup_register_maps(scanner: Any) -> None:
    """Asynchronously load register definitions and build address/name maps."""
    await async_ensure_register_maps(initial_register_hash(), scanner._hass)
    loaded = await scanner._load_registers()
    if isinstance(loaded, tuple):
        scanner._registers = loaded[0]
        scanner._register_ranges = (
            loaded[1] if len(loaded) > 1 and isinstance(loaded[1], dict) else {}
        )
    else:
        scanner._registers = loaded
        scanner._register_ranges = {}


def _collect_safe_register_addresses(
    safe_registers: list[tuple[int, str]],
    register_definitions: dict[str, Any],
) -> tuple[list[int], list[int]]:
    safe_input: list[int] = []
    safe_holding: list[int] = []
    for func, name in safe_registers:
        reg = register_definitions.get(name)
        if reg is None:
            continue
        if func == 4:
            safe_input.append(reg.address)
        else:
            safe_holding.append(reg.address)
    return safe_input, safe_holding


async def _probe_safe_registers(
    scanner: Any,
    transport: Any,
    safe_input: list[int],
    safe_holding: list[int],
    holding_batch_boundaries: frozenset[int],
    group_reads: Any,
) -> None:
    for start, count in group_reads(safe_input, max_block_size=scanner.effective_batch):
        _LOGGER.debug(
            "verify_connection: read_input_registers start=%s count=%s",
            start,
            count,
        )
        await transport.read_input_registers(scanner.slave_id, start, count=count)

    for start, count in group_reads(
        safe_holding,
        max_block_size=scanner.effective_batch,
        boundaries=holding_batch_boundaries,
    ):
        _LOGGER.debug(
            "verify_connection: read_holding_registers start=%s count=%s",
            start,
            count,
        )
        await transport.read_holding_registers(scanner.slave_id, start, count=count)


def _store_resolved_mode(scanner: Any, mode_name: str | None) -> None:
    if mode_name is not None:
        if scanner.connection_mode == CONNECTION_MODE_AUTO:
            _LOGGER.info(
                "verify_connection: auto-selected Modbus transport %s for %s:%s",
                mode_name,
                scanner.host,
                scanner.port,
            )
        scanner._resolved_connection_mode = mode_name


async def _attempt_single_verification(
    scanner: Any,
    mode_name: str | None,
    transport: Any,
    timeout: float,
    safe_input: list[int],
    safe_holding: list[int],
    holding_batch_boundaries: frozenset[int],
    group_reads: Any,
    closed_transports: set[int],
) -> None:
    """Connect one transport/mode and probe safe registers; raises on failure."""
    try:
        _LOGGER.info(
            "verify_connection: connecting to %s:%s (mode=%s, timeout=%s)",
            scanner.host,
            scanner.port,
            mode_name or scanner.connection_type,
            timeout,
        )
        await asyncio.wait_for(transport.ensure_connected(), timeout=timeout)
        await _probe_safe_registers(
            scanner, transport, safe_input, safe_holding, holding_batch_boundaries, group_reads
        )
        _store_resolved_mode(scanner, mode_name)
    finally:
        await close_verification_transport_once(transport, closed_transports)


async def verify_connection(
    scanner: Any,
    *,
    safe_registers: list[tuple[int, str]] = SAFE_REGISTERS,
    register_definitions: dict[str, Any] = REGISTER_DEFINITIONS,
    holding_batch_boundaries: frozenset[int] = HOLDING_BATCH_BOUNDARIES,
    group_reads: Any = _group_reads,
    rtu_transport_cls: Any = RtuModbusTransport,
) -> None:
    """Verify basic Modbus connectivity by reading a few safe registers."""
    safe_input, safe_holding = _collect_safe_register_addresses(
        safe_registers, register_definitions
    )

    attempts = build_verification_attempts(
        scanner,
        rtu_transport_cls=rtu_transport_cls,
    )

    last_error: Exception | None = None
    closed_transports: set[int] = set()
    for mode_name, transport, timeout in attempts:
        try:
            await _attempt_single_verification(
                scanner,
                mode_name,
                transport,
                timeout,
                safe_input,
                safe_holding,
                holding_batch_boundaries,
                group_reads,
                closed_transports,
            )
            return
        except asyncio.CancelledError:
            raise
        except (
            ModbusIOException,
            TimeoutError,
            ConnectionException,
            ModbusException,
            OSError,
        ) as exc:
            last_error = classify_verify_connection_exception(exc)

    if last_error:
        raise last_error


def build_tcp_transport(
    scanner: Any,
    mode: str,
    *,
    timeout_override: float | None = None,
) -> BaseModbusTransport:
    """Build TCP transport implementation for the selected connection mode."""
    timeout = scanner.timeout if timeout_override is None else timeout_override
    if mode == CONNECTION_MODE_TCP_RTU:
        return RawRtuOverTcpTransport(
            host=scanner.host,
            port=scanner.port,
            max_retries=scanner.retry,
            base_backoff=scanner.backoff,
            max_backoff=DEFAULT_MAX_BACKOFF,
            timeout=timeout,
        )
    return TcpModbusTransport(
        host=scanner.host,
        port=scanner.port,
        connection_type=CONNECTION_TYPE_TCP,
        max_retries=scanner.retry,
        base_backoff=scanner.backoff,
        max_backoff=DEFAULT_MAX_BACKOFF,
        timeout=timeout,
    )


def build_auto_tcp_attempts(scanner: Any) -> list[tuple[str, BaseModbusTransport, float]]:
    """Build AUTO-mode transport attempts ordered by likely protocol.

    Standard Modbus TCP is tried first; tcp_rtu (raw RTU framing over a TCP
    socket) is the fallback.  The previous port-based heuristic that put
    tcp_rtu first on non-standard ports caused a config-flow timeout when the
    device actually speaks standard TCP: the tcp_rtu probe consumed its full
    per-attempt timeout before the TCP attempt could complete.
    """
    rtu_timeout = min(max(scanner.timeout, 2.0), 5.0)
    tcp_timeout = min(max(scanner.timeout, 5.0), 10.0)
    mode_order = [CONNECTION_MODE_TCP, CONNECTION_MODE_TCP_RTU]
    attempts: list[tuple[str, BaseModbusTransport, float]] = []
    for mode in mode_order:
        timeout = rtu_timeout if mode == CONNECTION_MODE_TCP_RTU else tcp_timeout
        if hasattr(scanner, "_build_tcp_transport"):
            transport = scanner._build_tcp_transport(mode, timeout_override=timeout)
        else:
            transport = build_tcp_transport(scanner, mode, timeout_override=timeout)
        attempts.append((mode, transport, timeout))
    return attempts


def build_verification_attempts(
    scanner: Any,
    *,
    rtu_transport_cls: Any = RtuModbusTransport,
) -> list[tuple[str | None, BaseModbusTransport, float]]:
    """Build ordered transport attempts for verify_connection."""
    attempts: list[tuple[str | None, BaseModbusTransport, float]] = []
    if scanner.connection_type == CONNECTION_TYPE_RTU:
        if not scanner.serial_port:
            raise ConnectionException("Serial port not configured")
        parity = SERIAL_PARITY_MAP.get(scanner.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])
        stop_bits = SERIAL_STOP_BITS_MAP.get(
            scanner.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]
        )
        attempts.append(
            (
                None,
                rtu_transport_cls(
                    serial_port=scanner.serial_port,
                    baudrate=scanner.baud_rate,
                    parity=parity,
                    stopbits=stop_bits,
                    max_retries=scanner.retry,
                    base_backoff=scanner.backoff,
                    max_backoff=DEFAULT_MAX_BACKOFF,
                    timeout=scanner.timeout,
                ),
                scanner.timeout,
            )
        )
        return attempts

    if scanner.connection_mode == CONNECTION_MODE_AUTO:
        if hasattr(scanner, "_build_auto_tcp_attempts"):
            return list(scanner._build_auto_tcp_attempts())
        return list(build_auto_tcp_attempts(scanner))

    mode = scanner.connection_mode or default_connection_mode(scanner.port)
    if hasattr(scanner, "_build_tcp_transport"):
        attempts.append((mode, scanner._build_tcp_transport(mode), scanner.timeout))
    else:
        attempts.append((mode, build_tcp_transport(scanner, mode), scanner.timeout))
    return attempts


def classify_verify_connection_exception(exc: Exception) -> Exception:
    """Normalize verify-connection exceptions while preserving behavior."""
    if isinstance(exc, ModbusIOException) and is_request_cancelled_error(exc):
        _LOGGER.info("Modbus request cancelled during verify_connection.")
        raise TimeoutError("Modbus request cancelled") from exc
    if isinstance(exc, TimeoutError):
        _LOGGER.warning("Timeout during verify_connection: %s", exc)
    return exc


async def close_verification_transport_once(
    transport: BaseModbusTransport,
    closed_transports: set[int],
) -> None:
    """Close verify_connection transport once, supporting sync/async close()."""
    try:
        transport_id = id(transport)
        if transport_id in closed_transports:
            return
        close_result = transport.close()
        if inspect.isawaitable(close_result):
            await close_result
        closed_transports.add(transport_id)
    except (OSError, ConnectionException, ModbusIOException):
        _LOGGER.warning("Error closing Modbus transport during verify_connection", exc_info=True)


async def async_close_connection(scanner: Any, async_maybe_await_close_fn: Any) -> None:
    """Close scanner transport/client while swallowing expected network errors."""
    if scanner._transport is not None:
        try:
            await scanner._transport.close()
        except (OSError, ConnectionException, ModbusIOException):
            _LOGGER.debug("Error closing Modbus transport", exc_info=True)
        finally:
            scanner._transport = None

    client = scanner._client
    if client is None:
        return

    try:
        await async_maybe_await_close_fn(client)
    except (OSError, ConnectionException, ModbusIOException):
        _LOGGER.debug("Error closing Modbus client", exc_info=True)
    finally:
        scanner._client = None


async def async_create_scanner_instance(
    scanner_cls: Any,
    *,
    host: str,
    port: int,
    slave_id: int,
    timeout: int,
    retry: int,
    backoff: float,
    backoff_jitter: float | tuple[float, float] | None,
    verbose_invalid_values: bool,
    scan_uart_settings: bool,
    skip_known_missing: bool,
    deep_scan: bool,
    full_register_scan: bool,
    max_registers_per_request: int,
    safe_scan: bool,
    delay_between_requests_ms: int = 0,
    connection_type: str,
    connection_mode: str | None,
    serial_port: str,
    baud_rate: int,
    parity: str,
    stop_bits: int,
    hass: Any | None,
) -> Any:
    """Create and initialize scanner instance with bound read helper methods."""
    attach_pymodbus_client_module()
    await async_ensure_register_maps(initial_register_hash(), hass)
    scanner = scanner_cls(
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
        delay_between_requests_ms,
        connection_type,
        connection_mode,
        serial_port,
        baud_rate,
        parity,
        stop_bits,
        hass=hass,
        registers_ready=True,
    )
    await scanner._async_setup()
    scanner._read_holding = scanner_cls._read_holding.__get__(scanner, scanner_cls)
    scanner._read_coil = scanner_cls._read_coil.__get__(scanner, scanner_cls)
    scanner._read_discrete = scanner_cls._read_discrete.__get__(scanner, scanner_cls)
    return scanner
