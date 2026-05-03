"""Scan orchestration routines extracted from scanner core."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ..const import (
    CONNECTION_MODE_AUTO,
    CONNECTION_TYPE_RTU,
    DEFAULT_MAX_BACKOFF,
    DEFAULT_PARITY,
    DEFAULT_STOP_BITS,
    SERIAL_PARITY_MAP,
    SERIAL_STOP_BITS_MAP,
)
from ..modbus_exceptions import ConnectionException, ModbusException, ModbusIOException
from ..modbus_helpers import group_reads as _group_reads
from ..modbus_transport import RtuModbusTransport
from ..scanner_device_info import DeviceCapabilities, ScannerDeviceInfo
from . import custom_scan as scanner_custom_scan
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


def _build_scan_result(scanner: Any, *, device: ScannerDeviceInfo, caps: DeviceCapabilities, available_registers: dict[str, set[str]], unknown_registers: dict[str, dict[int, Any]], scanned_registers: dict[str, int], scan_blocks: dict[str, list[tuple[int, int]]], missing_registers: dict[str, dict[str, int]], scan_started: float, raw_registers: dict[int, int]) -> dict[str, Any]:
    """Assemble the scan result payload."""
    result: dict[str, Any] = {
        "available_registers": available_registers,
        "device_info": device.as_dict(),
        "capabilities": caps.as_dict(),
        "register_count": sum(len(v) for v in available_registers.values()),
        "scan_blocks": scan_blocks,
        "unknown_registers": unknown_registers,
        "scanned_registers": scanned_registers,
        "missing_registers": missing_registers,
        "failed_addresses": {
            "modbus_exceptions": {k: sorted(v) for k, v in scanner.failed_addresses["modbus_exceptions"].items() if v},
            "invalid_values": {k: sorted(v) for k, v in scanner.failed_addresses["invalid_values"].items() if v},
        },
        "resolved_connection_mode": scanner._resolved_connection_mode,
        "scan_stats": {
            "total_attempts": sum(scanned_registers.values()),
            "successful_reads": sum(len(v) for v in available_registers.values()),
            "scan_duration": max(0.0001, time.monotonic() - scan_started),
        },
    }
    if scanner.deep_scan:
        result["raw_registers"] = raw_registers
        result["total_addresses_scanned"] = len(raw_registers)
    return result


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
    for start, count in _group_reads(range(input_max + 1), max_block_size=scanner.effective_batch):
        scanned_registers["input_registers"] += count
        input_data = (
            await scanner._read_input(scanner._client, start, count, skip_cache=True)
            if scanner._client is not None
            else await scanner._read_input(None, start, count, skip_cache=True)
        )
        if input_data is None:
            scanner.failed_addresses["modbus_exceptions"]["input_registers"].update(
                range(start, start + count)
            )
            continue
        apply_word_register_block(
            scanner,
            function=4,
            register_group="input_registers",
            start=start,
            count=count,
            data=input_data,
            unknown_registers=unknown_registers,
        )

    for start, count in _group_reads(
        range(holding_max + 1), max_block_size=scanner.effective_batch
    ):
        scanned_registers["holding_registers"] += count
        holding_data = (
            await scanner._read_holding(scanner._client, start, count, skip_cache=True)
            if scanner._client is not None
            else await scanner._read_holding(None, start, count, skip_cache=True)
        )
        if holding_data is None:
            scanner.failed_addresses["modbus_exceptions"]["holding_registers"].update(
                range(start, start + count)
            )
            continue
        apply_word_register_block(
            scanner,
            function=3,
            register_group="holding_registers",
            start=start,
            count=count,
            data=holding_data,
            unknown_registers=unknown_registers,
        )

    for start, count in _group_reads(range(coil_max + 1), max_block_size=scanner.effective_batch):
        scanned_registers["coil_registers"] += count
        coil_data = (
            await scanner._read_coil(scanner._client, start, count)
            if scanner._client is not None
            else await scanner._read_coil(start, count)
        )
        if coil_data is None:
            scanner.failed_addresses["modbus_exceptions"]["coil_registers"].update(
                range(start, start + count)
            )
            continue
        for offset, value in enumerate(coil_data):
            addr = start + offset
            if (reg_name := scanner._registers.get(1, {}).get(addr)) is not None:
                names = scanner._alias_names(1, addr)
                if names:
                    scanner.available_registers["coil_registers"].update(names)
                else:
                    scanner.available_registers["coil_registers"].add(reg_name)
            else:
                unknown_registers["coil_registers"][addr] = value

    for start, count in _group_reads(
        range(discrete_max + 1), max_block_size=scanner.effective_batch
    ):
        scanned_registers["discrete_inputs"] += count
        discrete_data = (
            await scanner._read_discrete(scanner._client, start, count)
            if scanner._client is not None
            else await scanner._read_discrete(start, count)
        )
        if discrete_data is None:
            scanner.failed_addresses["modbus_exceptions"]["discrete_inputs"].update(
                range(start, start + count)
            )
            continue
        for offset, value in enumerate(discrete_data):
            addr = start + offset
            if (reg_name := scanner._registers.get(2, {}).get(addr)) is not None:
                names = scanner._alias_names(2, addr)
                if names:
                    scanner.available_registers["discrete_inputs"].update(names)
                else:
                    scanner.available_registers["discrete_inputs"].add(reg_name)
            else:
                unknown_registers["discrete_inputs"][addr] = value


async def scan(scanner: Any) -> dict[str, Any]:
    """Perform the actual register scan using an established connection."""
    scan_started = time.monotonic()
    transport = scanner._transport
    if transport is None:
        if scanner._client is None:
            raise ConnectionException("Transport not connected")
    elif not transport.is_connected() and scanner._client is None:
        raise ConnectionException("Transport not connected")

    device = ScannerDeviceInfo()

    info_regs = await scanner._read_input_block(0, 30) or []
    await scanner._scan_firmware_info(info_regs, device)
    await scanner._scan_device_identity(info_regs, device)

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

    if missing_registers:
        details = []
        for reg_type, regs in missing_registers.items():
            formatted = ", ".join(
                f"{name}={addr}" for name, addr in sorted(regs.items(), key=lambda item: item[1])
            )
            details.append(f"{reg_type}: {formatted}")
        _LOGGER.warning(
            "The following registers were not found during scan: %s", "; ".join(details)
        )

    available_registers = {key: set(value) for key, value in scanner.available_registers.items()}
    return _build_scan_result(
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
