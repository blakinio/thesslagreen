"""Diagnostics platform for the ThesslaGreen Modbus integration.

Includes the same translated error and status codes as exposed by the ``error_codes`` sensor.
"""

from __future__ import annotations

import asyncio
import copy
import ipaddress
import logging
import re
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import translation

from .const import CONFIG_FLOW_VERSION_SCALE, DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .registers.cache import registers_sha256
from .registers.loader import get_all_registers, get_registers_path

_LOGGER = logging.getLogger(__name__)


def _setdefault_bulk(target: dict[str, Any], defaults: dict[str, Any]) -> None:
    """Apply dict defaults without overwriting existing values."""
    for key, value in defaults.items():
        target.setdefault(key, value)


async def _run_executor_job(hass: HomeAssistant, func: Callable[..., Any], *args: Any) -> Any:
    """Run a callable using HA executor when available, fallback inline in tests."""

    if hasattr(hass, "async_add_executor_job"):
        return await hass.async_add_executor_job(func, *args)
    return func(*args)


def _detect_data_anomalies(data: dict[str, Any]) -> list[str]:
    """Return best-effort diagnostics insights based on current coordinator data."""

    anomalies: list[str] = []

    supply_air_flow = data.get("supply_air_flow")
    exhaust_air_flow = data.get("exhaust_air_flow")
    cf_version = data.get("cf_version")
    supply_flow_rate = data.get("supply_flow_rate")
    exhaust_flow_rate = data.get("exhaust_flow_rate")

    if (
        isinstance(supply_air_flow, int)
        and isinstance(exhaust_air_flow, int)
        and isinstance(cf_version, int)
        and supply_air_flow == exhaust_air_flow == cf_version
        and cf_version >= CONFIG_FLOW_VERSION_SCALE
        and isinstance(supply_flow_rate, int)
        and isinstance(exhaust_flow_rate, int)
        and supply_flow_rate < 1000
        and exhaust_flow_rate < 1000
    ):
        anomalies.append("mirrored_airflow_register_values")

    return anomalies


def _coordinator_defaults(coordinator: ThesslaGreenModbusCoordinator) -> dict[str, Any]:
    """Build diagnostics defaults derived from coordinator state."""
    return {
        "effective_batch": coordinator.effective_batch,
        "capabilities": coordinator.capabilities.as_dict(),
        "firmware_version": coordinator.device_info.get("firmware"),
        "total_available_registers": sum(
            len(regs) for regs in coordinator.available_registers.values()
        ),
        "registers_discovered": {
            key: len(val) for key, val in coordinator.available_registers.items()
        },
        "status_overview": getattr(coordinator, "status_overview", None),
        "autoscan": not coordinator.force_full_register_list,
        "force_full": coordinator.force_full_register_list,
        "force_full_register_list": coordinator.force_full_register_list,
        "deep_scan": coordinator.deep_scan,
        "error_statistics": {
            "connection_errors": coordinator.statistics.get("connection_errors", 0),
            "timeout_errors": coordinator.statistics.get("timeout_errors", 0),
        },
        "last_scan": coordinator.last_scan.isoformat() if coordinator.last_scan else None,
    }


def _extract_scan_registers(
    coordinator: ThesslaGreenModbusCoordinator,
) -> tuple[dict[str, dict[int, Any]], dict[str, dict[str, list[int]]]]:
    """Extract unknown/failed scan register results with fallback behavior."""
    unknown_regs: dict[str, dict[int, Any]] = {}
    failed_addrs: dict[str, dict[str, list[int]]] = {}
    if coordinator.device_scan_result:
        unknown_regs = coordinator.device_scan_result.get("unknown_registers", {})
        failed_addrs = coordinator.device_scan_result.get("failed_addresses", {})
    if not unknown_regs and hasattr(coordinator, "unknown_registers"):
        unknown_regs = coordinator.unknown_registers
    return unknown_regs, failed_addrs


async def _load_translations(hass: HomeAssistant) -> dict[str, str]:
    """Load translation mapping used to describe status/error registers."""
    try:
        return await translation.async_get_translations(
            hass, hass.config.language, f"component.{DOMAIN}"
        )
    except (OSError, ValueError, HomeAssistantError, RuntimeError) as err:
        _LOGGER.debug("Translation load failed: %s", err)
    except BaseException as err:  # pragma: no cover
        if isinstance(err, KeyboardInterrupt | SystemExit | asyncio.CancelledError):
            raise
        _LOGGER.debug("Translation load failed unexpectedly: %s", err)
    return {}


def _build_active_errors(data: dict[str, Any], translations: dict[str, str]) -> dict[str, str]:
    """Build active translated error/status keys from coordinator data."""
    active_errors: dict[str, str] = {}
    for key, value in data.items():
        if value and (key.startswith("e_") or key.startswith("s_")):
            active_errors[key] = translations.get(f"codes.{key}", key)
    return active_errors


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: ThesslaGreenModbusCoordinator = entry.runtime_data

    diagnostics = coordinator.get_diagnostic_data()
    _setdefault_bulk(diagnostics, _coordinator_defaults(coordinator))
    _setdefault_bulk(
        diagnostics,
        {
            "registers_hash": await _run_executor_job(
                hass, registers_sha256, get_registers_path()
            ),
            "total_registers_json": await _run_executor_job(
                hass, lambda: len(get_all_registers())
            ),
        },
    )

    if coordinator.device_scan_result and "raw_registers" in coordinator.device_scan_result:
        diagnostics.setdefault("raw_registers", coordinator.device_scan_result["raw_registers"])

    unknown_regs, failed_addrs = _extract_scan_registers(coordinator)
    diagnostics.setdefault("unknown_registers", unknown_regs)
    diagnostics.setdefault("failed_addresses", failed_addrs)

    if coordinator.data:
        active_errors = _build_active_errors(coordinator.data, await _load_translations(hass))
        if active_errors:
            diagnostics["active_errors"] = active_errors

        anomalies = _detect_data_anomalies(coordinator.data)
        if anomalies:
            diagnostics["anomalies"] = anomalies

    diagnostics_safe = _redact_sensitive_data(diagnostics)
    _LOGGER.debug("Generated diagnostics for ThesslaGreen device")
    return diagnostics_safe


def _redact_sensitive_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive information from diagnostics."""
    safe_data = copy.deepcopy(data)

    def mask_ip(ip_str: str) -> str:
        try:
            ip_str_clean = ip_str.split("%", 1)[0]
            ip = ipaddress.ip_address(ip_str_clean)
        except ValueError:
            return ip_str
        if isinstance(ip, ipaddress.IPv4Address):
            parts = ip_str_clean.split(".")
            return f"{parts[0]}.xxx.xxx.{parts[3]}"
        segments = ip.exploded.split(":")
        return ":".join([segments[0]] + ["xxxx"] * 6 + [segments[-1]])

    if "connection" in safe_data and "host" in safe_data["connection"]:
        safe_data["connection"]["host"] = mask_ip(safe_data["connection"]["host"])

    if "device_info" in safe_data and "serial_number" in safe_data["device_info"]:
        serial = safe_data["device_info"]["serial_number"]
        if serial and len(serial) > 4:
            safe_data["device_info"]["serial_number"] = f"{serial[:2]}***{serial[-2:]}"

    if "recent_errors" in safe_data:
        for error in safe_data["recent_errors"]:
            if "message" in error:
                message = error["message"]
                message = re.sub(
                    r"\b(?:\d{1,3}(?:\.\d{1,3}){3}|[0-9A-Fa-f:]+)\b",
                    lambda m: mask_ip(m.group(0)),
                    message,
                )
                error["message"] = message

    return safe_data
