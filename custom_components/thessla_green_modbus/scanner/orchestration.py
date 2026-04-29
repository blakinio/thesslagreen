"""Scan orchestration routines extracted from scanner core."""

from __future__ import annotations

import asyncio
import inspect
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
from .io import is_request_cancelled_error

_LOGGER = logging.getLogger(__name__)




def _uses_custom_scan_impl(scanner: Any) -> bool:
    """Return True when scanner.scan is overridden outside scanner.core."""
    scan_method = scanner.scan
    base_scan = getattr(type(scanner), "scan", None)
    return getattr(scan_method, "__func__", None) is not base_scan or getattr(
        base_scan, "__module__", ""
    ) != "custom_components.thessla_green_modbus.scanner.core"


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
        for offset in range(count):
            addr = start + offset
            if offset >= len(input_data):
                if scanner._registers.get(4, {}).get(addr) is None:
                    base = input_data[0] if input_data else start
                    unknown_registers["input_registers"][addr] = int(base) + offset
                continue
            value = input_data[offset]
            reg_name = scanner._registers.get(4, {}).get(addr)
            if reg_name and scanner._is_valid_register_value(reg_name, value):
                names = scanner._alias_names(4, addr)
                if names:
                    scanner.available_registers["input_registers"].update(names)
                else:
                    scanner.available_registers["input_registers"].add(reg_name)
            else:
                unknown_registers["input_registers"][addr] = value
                if reg_name:
                    scanner.failed_addresses["invalid_values"]["input_registers"].add(addr)
                    scanner._log_invalid_value(reg_name, value)

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
        for offset in range(count):
            addr = start + offset
            if offset >= len(holding_data):
                if scanner._registers.get(3, {}).get(addr) is None:
                    base = holding_data[0] if holding_data else start
                    unknown_registers["holding_registers"][addr] = int(base) + offset
                continue
            value = holding_data[offset]
            reg_name = scanner._registers.get(3, {}).get(addr)
            if reg_name and scanner._is_valid_register_value(reg_name, value):
                names = scanner._alias_names(3, addr)
                if names:
                    scanner.available_registers["holding_registers"].update(names)
                else:
                    scanner.available_registers["holding_registers"].add(reg_name)
            else:
                unknown_registers["holding_registers"][addr] = value
                if reg_name:
                    scanner.failed_addresses["invalid_values"]["holding_registers"].add(addr)
                    scanner._log_invalid_value(reg_name, value)

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

    if scanner.full_register_scan:
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

    raw_registers: dict[int, int] = {}
    if scanner.deep_scan:
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
                k: sorted(v) for k, v in scanner.failed_addresses["modbus_exceptions"].items() if v
            },
            "invalid_values": {
                k: sorted(v) for k, v in scanner.failed_addresses["invalid_values"].items() if v
            },
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


async def scan_device(scanner: Any) -> dict[str, Any]:
    """Open the Modbus connection, perform a scan and close the client."""
    scan_method = scanner.scan
    if _uses_custom_scan_impl(scanner):
        try:
            scan_result: Any = scan_method()
            if inspect.isawaitable(scan_result):
                scan_result = await scan_result
            if (
                isinstance(scan_result, tuple)
                and len(scan_result) >= 2
                and isinstance(scan_result[0], ScannerDeviceInfo)
                and isinstance(scan_result[1], DeviceCapabilities)
            ):
                device, caps = scan_result[0], scan_result[1]
                unknown = (
                    scan_result[2]
                    if len(scan_result) > 2 and isinstance(scan_result[2], dict)
                    else {}
                )
                return {
                    "available_registers": {
                        k: sorted(v) for k, v in scanner.available_registers.items()
                    },
                    "device_info": device.as_dict(),
                    "capabilities": caps.as_dict(),
                    "register_count": sum(len(v) for v in scanner.available_registers.values()),
                    "unknown_registers": unknown,
                }
            if isinstance(scan_result, dict):
                return scan_result
            raise TypeError("scan() must return a dict")
        finally:
            await scanner.close()

    if scanner.connection_type == CONNECTION_TYPE_RTU:
        if not scanner.serial_port:
            raise ConnectionException("Serial port not configured")
        parity = SERIAL_PARITY_MAP.get(scanner.parity, SERIAL_PARITY_MAP[DEFAULT_PARITY])
        stop_bits = SERIAL_STOP_BITS_MAP.get(
            scanner.stop_bits, SERIAL_STOP_BITS_MAP[DEFAULT_STOP_BITS]
        )
        rtu_transport_cls = getattr(scanner, "_rtu_transport_cls", RtuModbusTransport)
        scanner._transport = rtu_transport_cls(
            serial_port=scanner.serial_port,
            baudrate=scanner.baud_rate,
            parity=parity,
            stopbits=stop_bits,
            max_retries=scanner.retry,
            base_backoff=scanner.backoff,
            max_backoff=DEFAULT_MAX_BACKOFF,
            timeout=scanner.timeout,
        )
    else:
        mode = scanner._resolved_connection_mode or scanner.connection_mode
        if mode is None or mode == CONNECTION_MODE_AUTO:
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
                        _LOGGER.debug(
                            "Protocol probe non-critical exception (protocol ok): %s", exc
                        )
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
                break
            if scanner._transport is None:
                raise ConnectionException("Auto-detect Modbus transport failed") from last_error
        else:
            scanner._transport = scanner._build_tcp_transport(mode)

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
