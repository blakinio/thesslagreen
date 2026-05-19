"""Diagnostic helpers for ``ThesslaGreenModbusCoordinator``."""

from __future__ import annotations

from typing import Any, cast

from ..const import DOMAIN, MANUFACTURER, UNKNOWN_MODEL
from ..register_map import REGISTER_MAP_VERSION
from ..registers.loader import get_all_registers
from ..utils import utcnow


def status_overview(coordinator: Any) -> dict[str, Any]:
    """Return a concise online/offline status summary."""
    last_update = coordinator.device_client.statistics.get("last_successful_update")
    last_update_iso = last_update.isoformat() if last_update else None
    is_connected = bool(coordinator.device_client._transport and coordinator.device_client._transport.is_connected())
    recent_update = False
    if last_update:
        recent_update = (utcnow() - last_update).total_seconds() < (coordinator.scan_interval * 3)

    error_count = int(coordinator.device_client.statistics.get("failed_reads", 0))
    error_count += int(coordinator.device_client.statistics.get("connection_errors", 0))
    error_count += int(coordinator.device_client.statistics.get("timeout_errors", 0))

    return {
        "online": is_connected and recent_update,
        "last_successful_read": last_update_iso,
        "error_count": error_count,
        "scan_interval": coordinator.scan_interval,
    }


def performance_stats(coordinator: Any) -> dict[str, Any]:
    """Return performance statistics."""
    return {
        "total_reads": coordinator.device_client.statistics["successful_reads"],
        "failed_reads": coordinator.device_client.statistics["failed_reads"],
        "success_rate": (
            coordinator.device_client.statistics["successful_reads"]
            / max(
                1,
                coordinator.device_client.statistics["successful_reads"] + coordinator.device_client.statistics["failed_reads"],
            )
        )
        * 100,
        "avg_response_time": coordinator.device_client.statistics["average_response_time"],
        "connection_errors": coordinator.device_client.statistics["connection_errors"],
        "last_error": coordinator.device_client.statistics["last_error"],
        "registers_available": sum(len(regs) for regs in coordinator.device_client.available_registers.values()),
        "registers_read": coordinator.device_client.statistics["total_registers_read"],
    }


def get_diagnostic_data(coordinator: Any) -> dict[str, Any]:
    """Return diagnostic information for Home Assistant."""
    last_update = coordinator.device_client.statistics.get("last_successful_update")
    connection = {
        "host": coordinator.config.host,
        "port": coordinator.config.port,
        "slave_id": coordinator.config.slave_id,
        "connected": bool(coordinator.device_client._transport and coordinator.device_client._transport.is_connected()),
        "offline_state": coordinator.device_client.offline_state,
        "last_successful_update": last_update.isoformat() if last_update else None,
        "transport": coordinator.config.connection_type,
        "serial_port": coordinator.config.serial_port,
        "baud_rate": coordinator.config.baud_rate,
        "parity": coordinator.config.parity,
        "stop_bits": coordinator.config.stop_bits,
    }

    statistics = coordinator.device_client.statistics.copy()
    if statistics.get("last_successful_update"):
        statistics["last_successful_update"] = statistics["last_successful_update"].isoformat()
    total_registers = sum(len(v) for v in coordinator.device_client.available_registers.values())
    total_registers_json = len(get_all_registers())
    registers_discovered = {
        key: len(value) for key, value in coordinator.device_client.available_registers.items()
    }
    error_stats = {
        "connection_errors": statistics.get("connection_errors", 0),
        "timeout_errors": statistics.get("timeout_errors", 0),
    }

    diagnostics: dict[str, Any] = {
        "connection": connection,
        "statistics": statistics,
        "performance": performance_stats(coordinator),
        "status_overview": status_overview(coordinator),
        "device_info": coordinator.device_client.device_info,
        "available_registers": {
            key: sorted(list(value)) for key, value in coordinator.device_client.available_registers.items()
        },
        "capabilities": coordinator.device_client.capabilities.as_dict(),
        "scan_result": coordinator.device_client.device_scan_result,
        "unknown_registers": coordinator.device_client.unknown_registers,
        "scanned_registers": coordinator.device_client.scanned_registers,
        "last_scan": coordinator.device_client.last_scan.isoformat() if coordinator.device_client.last_scan else None,
        "firmware_version": coordinator.device_client.device_info.get("firmware"),
        "total_available_registers": total_registers,
        "total_registers_json": total_registers_json,
        "effective_batch": coordinator.device_client.effective_batch,
        "deep_scan": coordinator.device_client.deep_scan,
        "force_full_register_list": coordinator.device_client.force_full_register_list,
        "autoscan": not coordinator.device_client.force_full_register_list,
        "registers_discovered": registers_discovered,
        "error_statistics": error_stats,
        "register_map_version": REGISTER_MAP_VERSION,
    }

    if coordinator.device_client.device_scan_result and "raw_registers" in coordinator.device_client.device_scan_result:
        diagnostics["raw_registers"] = coordinator.device_client.device_scan_result["raw_registers"]
        if "total_addresses_scanned" in coordinator.device_client.device_scan_result:
            statistics["total_addresses_scanned"] = coordinator.device_client.device_scan_result[
                "total_addresses_scanned"
            ]

    return diagnostics


def _resolve_sw_version(coordinator: Any) -> str:
    """Build a human-readable sw_version string.

    Prefers the firmware string from the device scan result.  When that is
    absent or 'Unknown', falls back to assembling a version string from the
    version_major / version_minor / cf_version registers that were read from
    the device.  Format: ``<major>.<minor> CF<cf>`` (e.g. ``3.11 CF13``).
    """
    firmware = coordinator.device_client.device_info.get("firmware", "Unknown")
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
    model = coordinator.device_client.device_info.get("model")
    if not model or model == UNKNOWN_MODEL:
        model = (
            coordinator.device_client.device_scan_result.get("capabilities", {}).get("model_type")
            if coordinator.device_client.device_scan_result
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
    coordinator.device_client.device_info["model"] = model

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
                f"{coordinator.config.host}:{coordinator.config.port}:{coordinator.config.slave_id}",
            )
        },
        name=device_name(coordinator),
        manufacturer=MANUFACTURER,
        model=model,
        sw_version=_resolve_sw_version(coordinator),
        configuration_url=f"http://{coordinator.config.host}",
    )


def device_name(coordinator: Any) -> str:
    """Return the configured or detected device name."""
    return cast(str, coordinator.device_client.device_info.get("device_name") or coordinator.device_client._device_name)
