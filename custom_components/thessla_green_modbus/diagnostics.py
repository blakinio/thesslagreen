"""Diagnostics platform for the ThesslaGreen Modbus integration.

Includes the same translated error and status codes as exposed by the ``error_codes`` sensor.
"""

from __future__ import annotations

import copy
import ipaddress
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import translation

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .registers import get_registers_hash

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:  # pragma: no cover
    """Return diagnostics for a config entry.

    Home Assistant calls this coroutine when the diagnostics panel is
    requested; it is part of the integration contract.
    """
    coordinator: ThesslaGreenModbusCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Gather comprehensive diagnostic data from the coordinator
    diagnostics = coordinator.get_diagnostic_data()
    diagnostics.setdefault("registers_hash", get_registers_hash())
    diagnostics.setdefault("capabilities", coordinator.capabilities.as_dict())

    # Supplement diagnostics with coordinator statistics
    diagnostics.setdefault(
        "firmware_version", coordinator.device_info.get("firmware")
    )
    diagnostics.setdefault(
        "total_available_registers",
        sum(len(regs) for regs in coordinator.available_registers.values()),
    )
    diagnostics["last_scan"] = (
        coordinator.last_scan.isoformat() if coordinator.last_scan else None
    )
    diagnostics.setdefault(
        "error_statistics",
        {
            "connection_errors": coordinator.statistics.get("connection_errors", 0),
            "timeout_errors": coordinator.statistics.get("timeout_errors", 0),
        },
    )

    if coordinator.device_scan_result and "raw_registers" in coordinator.device_scan_result:
        diagnostics.setdefault(
            "raw_registers", coordinator.device_scan_result["raw_registers"]
        )

    # Always expose registers that were skipped due to errors and any
    # unknown addresses discovered during the scan. Prefer data from the
    # most recent device scan, but fall back to any cached coordinator
    # values so the information is always present in diagnostics.
    unknown_regs: dict[str, dict[int, Any]] = {}
    failed_addrs: dict[str, dict[str, list[int]]] = {}
    if coordinator.device_scan_result:
        unknown_regs = coordinator.device_scan_result.get("unknown_registers", {})
        failed_addrs = coordinator.device_scan_result.get("failed_addresses", {})
    if not unknown_regs and hasattr(coordinator, "unknown_registers"):
        unknown_regs = coordinator.unknown_registers
    diagnostics.setdefault("unknown_registers", unknown_regs)
    diagnostics.setdefault("failed_addresses", failed_addrs)

    # Add human-readable descriptions for active error/status registers
    translations: dict[str, str] = {}
    try:
        translations = await translation.async_get_translations(
            hass, hass.config.language, f"component.{DOMAIN}"
        )
    except Exception as err:  # pragma: no cover - defensive
        _LOGGER.debug("Translation load failed: %s", err)
    active_errors: dict[str, str] = {}
    if coordinator.data:
        for key, value in coordinator.data.items():
            if value and (key.startswith("e_") or key.startswith("s_")):
                active_errors[key] = translations.get(f"codes.{key}", key)
    if active_errors:
        diagnostics["active_errors"] = active_errors

    # Redact sensitive information
    diagnostics_safe = _redact_sensitive_data(diagnostics)

    _LOGGER.debug("Generated diagnostics for ThesslaGreen device")

    return diagnostics_safe


def _redact_sensitive_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive information from diagnostics."""
    # Create a deep copy to avoid modifying the original data
    safe_data = copy.deepcopy(data)

    def mask_ip(ip_str: str) -> str:
        """Return a redacted representation of an IP address."""
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return ip_str
        if isinstance(ip, ipaddress.IPv4Address):
            parts = ip_str.split(".")
            return f"{parts[0]}.xxx.xxx.{parts[3]}"
        segments = ip.exploded.split(":")
        return ":".join([segments[0]] + ["xxxx"] * 6 + [segments[-1]])

    # Redact sensitive connection information
    if "connection" in safe_data and "host" in safe_data["connection"]:
        safe_data["connection"]["host"] = mask_ip(safe_data["connection"]["host"])

    # Redact serial number if present
    if "device_info" in safe_data and "serial_number" in safe_data["device_info"]:
        serial = safe_data["device_info"]["serial_number"]
        if serial and len(serial) > 4:
            # Show only first and last 2 characters
            safe_data["device_info"]["serial_number"] = f"{serial[:2]}***{serial[-2:]}"

    # Keep error logs but redact any IP addresses in messages
    if "recent_errors" in safe_data:
        for error in safe_data["recent_errors"]:
            if "message" in error:
                # Simple IP redaction
                message = error["message"]
                message = re.sub(
                    r"\b(?:\d{1,3}(?:\.\d{1,3}){3}|[0-9A-Fa-f:]+)\b",
                    lambda m: mask_ip(m.group(0)),
                    message,
                )
                error["message"] = message

    return safe_data
