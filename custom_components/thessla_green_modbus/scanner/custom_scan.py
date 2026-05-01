"""Custom scan runtime helpers for scanner orchestration."""

from __future__ import annotations

import inspect
from typing import Any

from ..scanner_device_info import DeviceCapabilities, ScannerDeviceInfo


def uses_custom_scan_impl(scanner: Any) -> bool:
    """Return True when scanner.scan is overridden outside scanner.core."""
    scan_method = scanner.scan
    base_scan = getattr(type(scanner), "scan", None)
    return getattr(scan_method, "__func__", None) is not base_scan or getattr(
        base_scan, "__module__", ""
    ) != "custom_components.thessla_green_modbus.scanner.core"


def normalize_custom_scan_result(scanner: Any, scan_result: Any) -> dict[str, Any]:
    """Normalize custom scan return shapes to a scan payload."""
    if (
        isinstance(scan_result, tuple)
        and len(scan_result) >= 2
        and isinstance(scan_result[0], ScannerDeviceInfo)
        and isinstance(scan_result[1], DeviceCapabilities)
    ):
        device, caps = scan_result[0], scan_result[1]
        unknown = scan_result[2] if len(scan_result) > 2 and isinstance(scan_result[2], dict) else {}
        return {
            "available_registers": {k: sorted(v) for k, v in scanner.available_registers.items()},
            "device_info": device.as_dict(),
            "capabilities": caps.as_dict(),
            "register_count": sum(len(v) for v in scanner.available_registers.values()),
            "unknown_registers": unknown,
        }
    if isinstance(scan_result, dict):
        return scan_result
    raise TypeError("scan() must return a dict")


async def run_custom_scan(scanner: Any) -> dict[str, Any]:
    """Run overridden scan implementation and normalize result."""
    scan_result: Any = scanner.scan()
    if inspect.isawaitable(scan_result):
        scan_result = await scan_result
    return normalize_custom_scan_result(scanner, scan_result)
