"""Helpers for applying scanner results to coordinator runtime state."""

from __future__ import annotations

from typing import Any


def apply_scan_result(
    coordinator: Any,
    scan_result: dict[str, Any],
    *,
    connection_mode_auto: str,
    known_missing_registers: dict[str, set[str]],
    device_capabilities_cls: type,
    cannot_connect_exc: type[Exception],
    now_fn,
    logger,
    unknown_model: str,
) -> None:
    """Store and process a completed device scan result."""

    coordinator.device_scan_result = scan_result
    if coordinator.config.connection_mode == connection_mode_auto:
        if resolved := coordinator.device_scan_result.get("resolved_connection_mode"):
            coordinator._resolved_connection_mode = resolved
    coordinator.last_scan = now_fn()

    scan_registers = coordinator.device_scan_result.get("available_registers", {})
    coordinator.available_registers = coordinator._normalise_available_registers(
        {
            "input_registers": scan_registers.get("input_registers", []),
            "holding_registers": scan_registers.get("holding_registers", []),
            "coil_registers": scan_registers.get("coil_registers", []),
            "discrete_inputs": scan_registers.get("discrete_inputs", []),
        }
    )
    if coordinator.skip_missing_registers:
        for reg_type, names in known_missing_registers.items():
            coordinator.available_registers[reg_type].difference_update(names)

    coordinator.device_info = coordinator.device_scan_result.get("device_info", {})
    coordinator.device_info.setdefault("device_name", coordinator._device_name)

    if (
        coordinator.device_info.get("serial_number")
        and coordinator.device_info["serial_number"] != "Unknown"
    ):
        coordinator.available_registers["input_registers"].add("serial_number")

    caps_obj = coordinator.device_scan_result.get("capabilities")
    if isinstance(caps_obj, device_capabilities_cls):
        coordinator.capabilities = caps_obj
    elif isinstance(caps_obj, dict):
        coordinator.capabilities = device_capabilities_cls(**caps_obj)
    elif caps_obj is None:
        coordinator.capabilities = device_capabilities_cls()
    else:
        logger.error(
            "Invalid capabilities format: expected dict, got %s",
            type(caps_obj).__name__,
        )
        raise cannot_connect_exc("invalid_capabilities")

    coordinator.unknown_registers = coordinator.device_scan_result.get("unknown_registers", {})
    coordinator.scanned_registers = coordinator.device_scan_result.get("scanned_registers", {})
    coordinator._store_scan_cache()

    logger.info(
        "Device scan completed: %d registers found, model: %s, firmware: %s",
        coordinator.device_scan_result.get("register_count", 0),
        coordinator.device_info.get("model", unknown_model),
        coordinator.device_info.get("firmware", "Unknown"),
    )
