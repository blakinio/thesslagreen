"""Diagnostic helpers for ``ThesslaGreenModbusCoordinator``."""

from __future__ import annotations

from typing import Any, cast

from ..const import DOMAIN, MANUFACTURER, UNKNOWN_MODEL
from ..register_map import REGISTER_MAP_VERSION
from ..registers.loader import get_all_registers
from ..utils import utcnow


def status_overview(coordinator: Any) -> dict[str, Any]:
    """Return a concise online/offline status summary."""
    dc = coordinator.device_client
    last_update = dc.statistics.get("last_successful_update")
    last_update_iso = last_update.isoformat() if last_update else None
    is_connected = bool(dc._transport and dc._transport.is_connected())
    recent_update = False
    if last_update:
        recent_update = (utcnow() - last_update).total_seconds() < (coordinator.scan_interval * 3)

    error_count = int(dc.statistics.get("failed_reads", 0))
    error_count += int(dc.statistics.get("connection_errors", 0))
    error_count += int(dc.statistics.get("timeout_errors", 0))

    return {
        "online": is_connected and recent_update,
        "last_successful_read": last_update_iso,
        "error_count": error_count,
        "scan_interval": coordinator.scan_interval,
    }


def performance_stats(coordinator: Any) -> dict[str, Any]:
    """Return performance statistics."""
    dc = coordinator.device_client
    return {
        "total_reads": dc.statistics["successful_reads"],
        "failed_reads": dc.statistics["failed_reads"],
        "success_rate": (
            dc.statistics["successful_reads"]
            / max(
                1,
                dc.statistics["successful_reads"] + dc.statistics["failed_reads"],
            )
        )
        * 100,
        "avg_response_time": dc.statistics["average_response_time"],
        "connection_errors": dc.statistics["connection_errors"],
        "last_error": dc.statistics["last_error"],
        "registers_available": sum(len(regs) for regs in dc.available_registers.values()),
        "registers_read": dc.statistics["total_registers_read"],
    }


def get_diagnostic_data(coordinator: Any) -> dict[str, Any]:
    """Return diagnostic information for Home Assistant."""
    dc = coordinator.device_client
    last_update = dc.statistics.get("last_successful_update")
    connection = {
        "host": dc.config.host,
        "port": dc.config.port,
        "slave_id": dc.config.slave_id,
        "connected": bool(dc._transport and dc._transport.is_connected()),
        "offline_state": dc.offline_state,
        "last_successful_update": last_update.isoformat() if last_update else None,
        "transport": dc.config.connection_type,
        "serial_port": dc.config.serial_port,
        "baud_rate": dc.config.baud_rate,
        "parity": dc.config.parity,
        "stop_bits": dc.config.stop_bits,
    }

    statistics = dc.statistics.copy()
    if statistics.get("last_successful_update"):
        statistics["last_successful_update"] = statistics["last_successful_update"].isoformat()
    total_registers = sum(len(v) for v in dc.available_registers.values())
    total_registers_json = len(get_all_registers())
    registers_discovered = {key: len(value) for key, value in dc.available_registers.items()}
    error_stats = {
        "connection_errors": statistics.get("connection_errors", 0),
        "timeout_errors": statistics.get("timeout_errors", 0),
    }

    diagnostics: dict[str, Any] = {
        "connection": connection,
        "statistics": statistics,
        "performance": performance_stats(coordinator),
        "status_overview": status_overview(coordinator),
        "device_info": dc.device_info,
        "available_registers": {
            key: sorted(list(value)) for key, value in dc.available_registers.items()
        },
        "capabilities": dc.capabilities.as_dict(),
        "scan_result": dc.device_scan_result,
        "unknown_registers": dc.unknown_registers,
        "scanned_registers": dc.scanned_registers,
        "last_scan": dc.last_scan.isoformat() if dc.last_scan else None,
        "firmware_version": dc.device_info.get("firmware"),
        "total_available_registers": total_registers,
        "total_registers_json": total_registers_json,
        "effective_batch": dc.effective_batch,
        "deep_scan": dc.deep_scan,
        "force_full_register_list": dc.force_full_register_list,
        "autoscan": not dc.force_full_register_list,
        "registers_discovered": registers_discovered,
        "error_statistics": error_stats,
        "register_map_version": REGISTER_MAP_VERSION,
    }

    if dc.device_scan_result and "raw_registers" in dc.device_scan_result:
        diagnostics["raw_registers"] = dc.device_scan_result["raw_registers"]
        if "total_addresses_scanned" in dc.device_scan_result:
            statistics["total_addresses_scanned"] = dc.device_scan_result["total_addresses_scanned"]

    return diagnostics


def _resolve_sw_version(coordinator: Any) -> str:
    """Build a human-readable sw_version string.

    Prefers the firmware string from the device scan result.  When that is
    absent or 'Unknown', falls back to assembling a version string from the
    version_major / version_minor / cf_version registers that were read from
    the device.  Format: ``<major>.<minor> CF<cf>`` (e.g. ``3.11 CF13``).
    """
    dc = coordinator.device_client
    firmware = dc.device_info.get("firmware", "Unknown")
    if firmware and firmware != "Unknown":
        return firmware

    data: dict[str, Any] = getattr(coordinator, "data", {}) or {}
    major = data.get("version_major")
    minor = data.get("version_minor")
    cf = data.get("cf_version")

    parts: list[str] = []
    if major is not None and minor is not None:
        parts.append(f"{int(major)}.{int(minor)}")
    elif major is not None:
        parts.append(str(int(major)))

    if cf is not None:
        parts.append(f"CF{int(cf)}")

    return " ".join(parts) if parts else "Unknown"


def get_device_info(coordinator: Any) -> dict[str, Any]:
    """Return device info mapping for the connected unit."""
    dc = coordinator.device_client
    model = dc.device_info.get("model")
    if not model or model == UNKNOWN_MODEL:
        model = (
            dc.device_scan_result.get("capabilities", {}).get("model_type")
            if dc.device_scan_result
            else None
        )
    if (not model or model == UNKNOWN_MODEL) and coordinator.entry is not None:
        model = cast(
            str | None,
            coordinator.entry.options.get("model")
            if hasattr(coordinator.entry, "options")
            else None,
        ) or cast(
            str | None,
            coordinator.entry.data.get("model") if hasattr(coordinator.entry, "data") else None,
        )
    if not model:
        model = UNKNOWN_MODEL
    dc.device_info["model"] = model

    class _CompatDeviceInfo(dict):
        def __getattr__(self, item: str) -> Any:
            try:
                return self[item]
            except KeyError as exc:
                raise AttributeError(item) from exc

    return _CompatDeviceInfo(
        identifiers={
            (
                DOMAIN,
                f"{dc.config.host}:{dc.config.port}:{dc.config.slave_id}",
            )
        },
        name=device_name(coordinator),
        manufacturer=MANUFACTURER,
        model=model,
        sw_version=_resolve_sw_version(coordinator),
        configuration_url=f"http://{dc.config.host}",
    )


def device_name(coordinator: Any) -> str:
    """Return the configured or detected device name."""
    dc = coordinator.device_client
    return cast(
        str,
        dc.device_info.get("device_name") or dc._device_name,
    )
