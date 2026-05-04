"""Scan runtime result helpers for scanner orchestration."""

from __future__ import annotations

import logging
import time
from typing import Any

from ..scanner_device_info import DeviceCapabilities, ScannerDeviceInfo

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
