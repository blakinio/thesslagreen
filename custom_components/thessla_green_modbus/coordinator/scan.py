"""Coordinator scan cache/full-list helpers."""

from __future__ import annotations

import logging
import re
from typing import Any

from ..const import DEFAULT_NAME, KNOWN_MISSING_REGISTERS, UNKNOWN_MODEL
from ..scanner_device_info import DeviceCapabilities

_LOGGER = logging.getLogger(__name__)


def load_full_register_list(coordinator: Any) -> None:
    """Load full register list when forced."""
    coordinator.available_registers = {
        key: set(mapping.keys()) for key, mapping in coordinator._register_maps.items()
    }

    coordinator.device_info = {
        "device_name": f"{DEFAULT_NAME} {UNKNOWN_MODEL}",
        "model": UNKNOWN_MODEL,
        "firmware": "Unknown",
        "serial_number": "Unknown",
        "input_registers": set(coordinator._register_maps["input_registers"].keys()),
        "holding_registers": set(coordinator._register_maps["holding_registers"].keys()),
        "coil_registers": set(coordinator._register_maps["coil_registers"].keys()),
        "discrete_inputs": set(coordinator._register_maps["discrete_inputs"].keys()),
    }

    if coordinator.skip_missing_registers:
        for reg_type, names in KNOWN_MISSING_REGISTERS.items():
            coordinator.available_registers[reg_type].difference_update(names)

    _LOGGER.info(
        "Loaded full register list: %d total registers",
        sum(len(regs) for regs in coordinator.available_registers.values()),
    )


def normalise_cached_register_name(name: str) -> str:
    """Normalise cached register names to current canonical form."""
    match = re.fullmatch(r"([es])(\d+)", name)
    if match:
        return f"{match.group(1)}_{int(match.group(2))}"
    return name


def normalise_available_registers(
    coordinator: Any, available: dict[str, list[str] | set[str]]
) -> dict[str, set[str]]:
    """Return available register names in canonical form."""
    normalised: dict[str, set[str]] = {}
    for reg_type, names in available.items():
        if not isinstance(names, list | set):
            continue
        normalised[reg_type] = {normalise_cached_register_name(str(name)) for name in names}
    return normalised


def firmware_lacks_known_missing(firmware: Any) -> bool:
    """Return True for firmwares that do not expose KNOWN_MISSING_REGISTERS."""
    if not isinstance(firmware, str):
        return False
    major = firmware.strip().split(".", 1)[0]
    return major in {"3"}


def apply_scan_cache(coordinator: Any, cache: dict[str, Any]) -> bool:
    """Apply cached scan data if available."""
    available = cache.get("available_registers")
    if not isinstance(available, dict):
        return False

    try:
        normalise_fn = getattr(coordinator, "_normalise_available_registers", None)
        if callable(normalise_fn):
            coordinator.available_registers = normalise_fn(
                {key: value for key, value in available.items() if isinstance(value, (list, set))}
            )
        else:
            coordinator.available_registers = normalise_available_registers(
                coordinator,
                {key: value for key, value in available.items() if isinstance(value, (list, set))},
            )
    except (TypeError, ValueError):
        return False

    device_info = cache.get("device_info")
    coordinator.device_info = device_info if isinstance(device_info, dict) else {}
    caps_obj = cache.get("capabilities")
    if isinstance(caps_obj, dict):
        try:
            coordinator.capabilities = DeviceCapabilities(**caps_obj)
        except (TypeError, ValueError):
            _LOGGER.debug("Invalid cached capabilities", exc_info=True)
    coordinator.device_scan_result = cache

    if (
        coordinator.device_info.get("serial_number")
        and coordinator.device_info["serial_number"] != "Unknown"
    ):
        coordinator.available_registers["input_registers"].add("serial_number")

    if firmware_lacks_known_missing(coordinator.device_info.get("firmware")):
        for reg_type, names in KNOWN_MISSING_REGISTERS.items():
            if reg_type in coordinator.available_registers:
                coordinator.available_registers[reg_type].difference_update(names)

    return True


def store_scan_cache(coordinator: Any) -> None:
    """Store scan results in config entry options."""
    if coordinator.entry is None:
        return

    available = {key: sorted(value) for key, value in coordinator.available_registers.items()}
    cache = {
        "available_registers": available,
        "device_info": coordinator.device_info,
        "capabilities": coordinator.capabilities.as_dict(),
        "firmware": coordinator.device_info.get("firmware"),
    }
    options = dict(coordinator.entry.options)
    options["device_scan_cache"] = cache
    coordinator.hass.config_entries.async_update_entry(coordinator.entry, options=options)
