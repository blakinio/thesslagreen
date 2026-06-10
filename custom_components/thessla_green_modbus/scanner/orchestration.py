"""Scan orchestration routines extracted from scanner core."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException

from ..const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_TYPE_RTU,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_PARITY,
    DEFAULT_STOP_BITS,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
)
from ..registers.read_planner import group_reads as _group_reads
from ..scanner.device_info import ScannerDeviceInfo
from ..transport.rtu import RtuModbusTransport
from . import custom_scan as scanner_custom_scan
from . import scan_runtime
from .full_scan_phase import apply_word_register_block
from .io import is_request_cancelled_error

_LOGGER = logging.getLogger(__name__)


def _initialize_scan_tracking() -> tuple[dict[str, dict[int, Any]], dict[str, int]]:
    """Create scan containers for unknown and scanned registers."""
    return (
        {
            "input_registers": {},
            "holding_registers": {},
            "coil_registers": {},
            "discrete_inputs": {},
        },
        {
            "input_registers": 0,
            "holding_registers": 0,
            "coil_registers": 0,
            "discrete_inputs": 0,
        },
    )


def _should_run_full_scan(scanner: Any) -> bool:
    """Select full vs named scan mode."""
    return bool(scanner.full_register_scan)


async def _accumulate_raw_registers(scanner: Any) -> dict[int, int]:
    """Collect raw input registers for deep scan mode."""
    raw_registers: dict[int, int] = {}
    if not scanner.deep_scan:
        return raw_registers
    for start, count in scanner._group_registers_for_batch_read(list(range(287))):
        data = (
            await scanner._read_input(scanner._client, start, count)
            if scanner._client is not None
            else await scanner._read_input(None, start, count)
        )
        if data is None:
            continue
        for offset, value in enumerate(data):
            raw_registers[start + offset] = value
    return raw_registers


async def _auto_detect_tcp_transport(scanner: Any) -> None:
    """Attempt TCP mode probes and keep first successful transport."""
    last_error: Exception | None = None
    for selected_mode, transport, timeout in scanner._build_auto_tcp_attempts():
        try:
            await asyncio.wait_for(transport.ensure_connected(), timeout=timeout)
            try:
                await transport.read_input_registers(scanner.slave_id, 0, count=2)
            except TimeoutError:
                raise
            except ModbusIOException as exc:
                if is_request_cancelled_error(exc):
                    raise TimeoutError(str(exc)) from exc
            except (
                ModbusException,
                ConnectionException,
                OSError,
                TypeError,
                ValueError,
                AttributeError,
            ) as exc:
                _LOGGER.debug("Protocol probe non-critical exception (protocol ok): %s", exc)
        except (TimeoutError, ConnectionException, ModbusException, OSError) as exc:
            last_error = exc
            await transport.close()
            continue
        scanner._transport = transport
        scanner._resolved_connection_mode = selected_mode
        _LOGGER.info(
            "scan_device: auto-selected Modbus transport %s for %s:%s",
            selected_mode,
            scanner.host,
            scanner.port,
        )
        return
    raise ConnectionException("Auto-detect Modbus transport failed") from last_error


def _create_rtu_transport(scanner: Any) -> Any:
    """Create RTU transport from scanner serial configuration."""
    parity = SERIAL_PARITY_MAP.get(scanner.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])
    stop_bits = SERIAL_STOP_BITS_MAP.get(scanner.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS])
    rtu_transport_cls = getattr(scanner, "_rtu_transport_cls", RtuModbusTransport)
    return rtu_transport_cls(
        serial_port=scanner.serial_port,
        baudrate=scanner.baud_rate,
        parity=parity,
        stopbits=stop_bits,
        max_retries=scanner.retry,
        base_backoff=scanner.backoff,
        max_backoff=DEFAULT_MAX_BACKOFF,
        timeout=scanner.timeout,
    )


async def _prepare_scan_transport(scanner: Any) -> None:
    """Prepare scanner transport according to connection strategy."""
    if scanner.connection_type == CONNECTION_TYPE_RTU:
        if not scanner.serial_port:
            raise ConnectionException("Serial port not configured")
        scanner._transport = _create_rtu_transport(scanner)
        return
    mode = scanner._resolved_connection_mode or scanner.connection_mode
    if mode is None or mode == CONNECTION_MODE_AUTO:
        await _auto_detect_tcp_transport(scanner)
        return
    scanner._transport = scanner._build_tcp_transport(mode)


async def _run_word_phase(
    scanner: Any,
    max_addr: int,
    scan_key: str,
    func: int,
    read_fn: Any,
    unknown_registers: dict[str, dict[int, Any]],
    scanned_registers: dict[str, int],
) -> None:
    delay_ms = getattr(scanner, "delay_between_requests_ms", 0)
    for start, count in _group_reads(range(max_addr + 1), max_block_size=scanner.effective_batch):
        _LOGGER.debug("Scanning %s: %d-%d", scan_key.replace("_", " "), start, start + count - 1)
        scanned_registers[scan_key] += count
        data = await read_fn(start, count)
        if data is None:
            # Full scan: raw batch failures go to batch_failures (diagnostic), not modbus_exceptions
            scanner.failed_addresses["batch_failures"][scan_key].update(range(start, start + count))
        else:
            apply_word_register_block(
                scanner,
                function=func,
                register_group=scan_key,
                start=start,
                count=count,
                data=data,
                unknown_registers=unknown_registers,
            )
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)


async def _run_bit_phase(
    scanner: Any,
    max_addr: int,
    scan_key: str,
    function: int,
    read_fn: Any,
    unknown_registers: dict[str, dict[int, Any]],
    scanned_registers: dict[str, int],
) -> None:
    delay_ms = getattr(scanner, "delay_between_requests_ms", 0)
    for start, count in _group_reads(range(max_addr + 1), max_block_size=scanner.effective_batch):
        _LOGGER.debug("Scanning %s: %d-%d", scan_key.replace("_", " "), start, start + count - 1)
        scanned_registers[scan_key] += count
        data = await read_fn(start, count)
        if data is None:
            # Full scan: raw batch failures go to batch_failures (diagnostic), not modbus_exceptions
            scanner.failed_addresses["batch_failures"][scan_key].update(range(start, start + count))
        else:
            for offset, value in enumerate(data):
                addr = start + offset
                if (reg_name := scanner._registers.get(function, {}).get(addr)) is not None:
                    names = scanner._alias_names(function, addr)
                    if names:
                        scanner.available_registers[scan_key].update(names)
                    else:
                        scanner.available_registers[scan_key].add(reg_name)
                else:
                    unknown_registers[scan_key][addr] = value
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)


async def run_full_scan(
    scanner: Any,
    input_max: int,
    holding_max: int,
    coil_max: int,
    discrete_max: int,
    unknown_registers: dict[str, dict[int, Any]],
    scanned_registers: dict[str, int],
) -> None:
    """Scan all registers up to max known address (full_register_scan mode)."""
    delay_ms = getattr(scanner, "delay_between_requests_ms", 0)
    batch = scanner.effective_batch
    _LOGGER.info(
        "Full scan started: batch=%d, delay=%dms, input_max=%d, holding_max=%d",
        batch,
        delay_ms,
        input_max,
        holding_max,
    )
    await _run_word_phase(
        scanner,
        input_max,
        "input_registers",
        4,
        lambda start, count: scanner._read_input(
            scanner._client if scanner._client is not None else None, start, count, skip_cache=True
        ),
        unknown_registers,
        scanned_registers,
    )
    _LOGGER.info(
        "Full scan input registers done: scanned=%d, batch_failures=%d",
        scanned_registers.get("input_registers", 0),
        len(scanner.failed_addresses["batch_failures"]["input_registers"]),
    )
    await _run_word_phase(
        scanner,
        holding_max,
        "holding_registers",
        3,
        lambda start, count: scanner._read_holding(
            scanner._client if scanner._client is not None else None, start, count, skip_cache=True
        ),
        unknown_registers,
        scanned_registers,
    )
    _LOGGER.info(
        "Full scan holding registers done: scanned=%d, batch_failures=%d",
        scanned_registers.get("holding_registers", 0),
        len(scanner.failed_addresses["batch_failures"]["holding_registers"]),
    )

    await _run_bit_phase(
        scanner,
        coil_max,
        "coil_registers",
        1,
        lambda start, count: (
            scanner._read_coil(scanner._client, start, count)
            if scanner._client is not None
            else scanner._read_coil(start, count)
        ),
        unknown_registers,
        scanned_registers,
    )
    await _run_bit_phase(
        scanner,
        discrete_max,
        "discrete_inputs",
        2,
        lambda start, count: (
            scanner._read_discrete(scanner._client, start, count)
            if scanner._client is not None
            else scanner._read_discrete(start, count)
        ),
        unknown_registers,
        scanned_registers,
    )
    total_scanned = sum(scanned_registers.values())
    total_batch_failures = sum(len(v) for v in scanner.failed_addresses["batch_failures"].values())
    _LOGGER.info(
        "Full scan completed: scanned=%d, batch_failures=%d, unknown=%d",
        total_scanned,
        total_batch_failures,
        sum(len(v) for v in unknown_registers.values()),
    )


def _check_scan_transport_ready(scanner: Any) -> None:
    """Raise ConnectionException if no usable transport or client is available."""
    transport = scanner._transport
    if transport is None:
        if scanner._client is None:
            raise ConnectionException("Transport not connected")
    elif scanner._client is None and not transport.is_connected():
        raise ConnectionException("Transport not connected")


async def _collect_scan_device_info(scanner: Any, device: ScannerDeviceInfo) -> None:
    """Read firmware and identity registers and populate device info."""
    info_regs = await scanner._read_input_block(0, 30) or []
    await scanner._scan_firmware_info(info_regs, device)
    await scanner._scan_device_identity(info_regs, device)


async def _finalize_scan_output(
    scanner: Any,
    device: ScannerDeviceInfo,
    caps: Any,
    input_registers: Any,
    holding_registers: Any,
    coil_registers: Any,
    discrete_registers: Any,
    input_max: int,
    holding_max: int,
    coil_max: int,
    discrete_max: int,
    unknown_registers: dict[str, dict[int, Any]],
    scanned_registers: dict[str, int],
    scan_started: float,
) -> dict[str, Any]:
    """Compute scan blocks, collect missing registers, and build the result dict."""
    scan_blocks = scanner._compute_scan_blocks(
        input_registers,
        holding_registers,
        coil_registers,
        discrete_registers,
        input_max,
        holding_max,
        coil_max,
        discrete_max,
    )
    scanner._log_skipped_ranges()

    raw_registers = await _accumulate_raw_registers(scanner)

    missing_registers = scanner._collect_missing_registers(
        input_registers, holding_registers, coil_registers, discrete_registers
    )
    scan_runtime.log_missing_registers(missing_registers)

    available_registers = {key: set(value) for key, value in scanner.available_registers.items()}
    return scan_runtime.build_scan_result(
        scanner,
        device=device,
        caps=caps,
        available_registers=available_registers,
        unknown_registers=unknown_registers,
        scanned_registers=scanned_registers,
        scan_blocks=scan_blocks,
        missing_registers=missing_registers,
        scan_started=scan_started,
        raw_registers=raw_registers,
    )


async def scan(scanner: Any) -> dict[str, Any]:
    """Perform the actual register scan using an established connection."""
    scan_started = time.monotonic()
    _check_scan_transport_ready(scanner)

    device = ScannerDeviceInfo()
    await _collect_scan_device_info(scanner, device)

    (
        input_registers,
        holding_registers,
        coil_registers,
        discrete_registers,
        input_max,
        holding_max,
        coil_max,
        discrete_max,
    ) = scanner._select_scan_registers()

    unknown_registers, scanned_registers = _initialize_scan_tracking()

    if _should_run_full_scan(scanner):
        await scanner._run_full_scan(
            input_max,
            holding_max,
            coil_max,
            discrete_max,
            unknown_registers,
            scanned_registers,
        )
    else:
        await scanner._run_named_scan(
            input_registers, holding_registers, coil_registers, discrete_registers
        )

    caps = scanner._analyze_capabilities()
    scanner.capabilities = caps
    device.capabilities = [
        key for key, val in caps.as_dict().items() if isinstance(val, bool) and val
    ]
    _LOGGER.info("Detected %d capabilities", len(device.capabilities))

    return await _finalize_scan_output(
        scanner,
        device,
        caps,
        input_registers,
        holding_registers,
        coil_registers,
        discrete_registers,
        input_max,
        holding_max,
        coil_max,
        discrete_max,
        unknown_registers,
        scanned_registers,
        scan_started,
    )


async def scan_device(scanner: Any) -> dict[str, Any]:
    """Open the Modbus connection, perform a scan and close the client."""
    if scanner_custom_scan.uses_custom_scan_impl(scanner):
        try:
            return await scanner_custom_scan.run_custom_scan(scanner)
        finally:
            await scanner.close()
    await _prepare_scan_transport(scanner)

    try:
        await asyncio.wait_for(scanner._transport.ensure_connected(), timeout=scanner.timeout)
        scanner._client = getattr(scanner._transport, "client", None)
    except (TimeoutError, ConnectionException, ModbusException, OSError) as exc:
        await scanner.close()
        raise ConnectionException(f"Failed to connect to {scanner.host}:{scanner.port}") from exc

    try:
        scan_data = await scanner.scan()
        if not isinstance(scan_data, dict):
            raise TypeError("scan() must return a dict")
        return scan_data
    finally:
        await scanner.close()
