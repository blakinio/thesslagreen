"""Scan runtime result helpers for scanner orchestration."""

from __future__ import annotations

import logging
import time
from typing import Any

from ..scanner.device_info import DeviceCapabilities, ScannerDeviceInfo

_LOGGER = logging.getLogger(__name__)


def log_missing_registers(missing_registers: dict[str, dict[str, int]]) -> None:
    """Log missing registers summary when expected addresses were not read."""
    if not missing_registers:
        return
    details = []
    for reg_type, regs in missing_registers.items():
        formatted = ", ".join(
            f"{name}={addr}" for name, addr in sorted(regs.items(), key=lambda item: item[1])
        )
        details.append(f"{reg_type}: {formatted}")
    _LOGGER.warning("The following registers were not found during scan: %s", "; ".join(details))


def _collect_expected_optional_addresses(scanner: Any) -> dict[str, list[int]]:
    """Identify failed addresses that belong to expected-optional firmware ranges.

    Input register addresses covered by unsupported ranges with exception code 2
    and end <= 15 are firmware-version metadata registers (version_patch,
    compilation timestamps) that are absent on some firmware versions.
    """
    result: dict[str, list[int]] = {}
    input_failed = scanner.failed_addresses["modbus_exceptions"].get("input_registers", set())
    if not input_failed:
        return result
    unsupported = getattr(scanner, "_unsupported_input_ranges", {})
    firmware_addrs: set[int] = set()
    for (start, end), code in unsupported.items():
        if code == 2 and end <= 15:
            firmware_addrs.update(range(start, end + 1))
    optional_in_failed = sorted(input_failed & firmware_addrs)
    if optional_in_failed:
        result["input_registers"] = optional_in_failed
    return result


def _collect_recovered_batch_failures(scanner: Any) -> dict[str, list[int]]:
    """Identify batch-failed addresses recovered by individual fallback probes.

    After Fix 1 (scan_register_batch discards successful probes from
    modbus_exceptions), any address in batch_failures that is NOT in
    modbus_exceptions was recovered.  These are diagnostic-only and are never
    shown as user-facing Modbus errors.
    """
    batch_failures = scanner.failed_addresses.get("batch_failures", {})
    modbus_exceptions = scanner.failed_addresses.get("modbus_exceptions", {})
    result: dict[str, list[int]] = {}
    for reg_type, batch_addrs in batch_failures.items():
        if not batch_addrs:
            continue
        truly_failed = set(modbus_exceptions.get(reg_type, set()))
        recovered = sorted(set(batch_addrs) - truly_failed)
        if recovered:
            result[reg_type] = recovered
    return result


def _collect_unrecovered_modbus_errors(scanner: Any) -> dict[str, list[dict[str, Any]]]:
    """Build named diagnostic for truly unrecovered Modbus failures.

    Returns {reg_type: [{addr, name}, ...]} where name is the register name
    from the scanner's register map (None for unnamed/raw addresses).
    """
    registers = getattr(scanner, "_registers", {})
    addr_to_name: dict[str, dict[int, str]] = {
        "input_registers": registers.get(4, {}),
        "holding_registers": registers.get(3, {}),
        "coil_registers": registers.get(1, {}),
        "discrete_inputs": registers.get(2, {}),
    }
    result: dict[str, list[dict[str, Any]]] = {}
    for reg_type, addrs in scanner.failed_addresses.get("modbus_exceptions", {}).items():
        if not addrs:
            continue
        name_map = addr_to_name.get(reg_type, {})
        entries = [{"addr": a, "name": name_map.get(a)} for a in sorted(addrs)]
        result[reg_type] = entries
    return result


def build_scan_result(
    scanner: Any,
    *,
    device: ScannerDeviceInfo,
    caps: DeviceCapabilities,
    available_registers: dict[str, set[str]],
    unknown_registers: dict[str, dict[int, Any]],
    scanned_registers: dict[str, int],
    scan_blocks: dict[str, list[tuple[int, int]]],
    missing_registers: dict[str, dict[str, int]],
    scan_started: float,
    raw_registers: dict[int, int],
) -> dict[str, Any]:
    """Assemble canonical scan result payload from runtime state."""
    expected_optional = _collect_expected_optional_addresses(scanner)
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
            "modbus_exceptions": {
                k: sorted(v) for k, v in scanner.failed_addresses["modbus_exceptions"].items() if v
            },
            "invalid_values": {
                k: sorted(v) for k, v in scanner.failed_addresses["invalid_values"].items() if v
            },
            "expected_optional": expected_optional,
            "batch_failures": {
                k: sorted(v)
                for k, v in scanner.failed_addresses.get("batch_failures", {}).items()
                if v
            },
            "deep_scan_raw_failures": {
                k: sorted(v)
                for k, v in scanner.failed_addresses.get("deep_scan_raw_failures", {}).items()
                if v
            },
            "recovered_batch_failures": _collect_recovered_batch_failures(scanner),
            "unrecovered_modbus_errors": _collect_unrecovered_modbus_errors(scanner),
        },
        "scan_mode": "full" if getattr(scanner, "full_register_scan", False) else "named",
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
