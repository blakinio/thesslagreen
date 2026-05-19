"""Coordinator scan cache/full-list helpers."""

from __future__ import annotations

import logging
from typing import Any

from ..const import CONNECTION_MODE_AUTO, DEFAULT_NAME, KNOWN_MISSING_REGISTERS, UNKNOWN_MODEL
from ..core.scan_helpers import normalise_available_registers
from ..scanner.device_info import DeviceCapabilities

_LOGGER = logging.getLogger(__name__)


def get_scan_cache_from_entry(entry: Any) -> dict[str, Any]:
    """Return cached scan payload from config entry options."""
    if entry is None:
        return {}
    raw_cache = entry.options.get("device_scan_cache", {})
    return raw_cache if isinstance(raw_cache, dict) else {}


def load_full_register_list(coordinator: Any) -> None:
    """Load full register list when forced."""
    coordinator.device_client.available_registers = {
        key: set(mapping.keys())
        for key, mapping in coordinator.device_client._register_maps.items()
    }

    coordinator.device_client.device_info = {
        "device_name": f"{DEFAULT_NAME} {UNKNOWN_MODEL}",
        "model": UNKNOWN_MODEL,
        "firmware": "Unknown",
        "serial_number": "Unknown",
        "input_registers": set(coordinator.device_client._register_maps["input_registers"].keys()),
        "holding_registers": set(
            coordinator.device_client._register_maps["holding_registers"].keys()
        ),
        "coil_registers": set(coordinator.device_client._register_maps["coil_registers"].keys()),
        "discrete_inputs": set(coordinator.device_client._register_maps["discrete_inputs"].keys()),
    }

    if coordinator.device_client.skip_missing_registers:
        for reg_type, names in KNOWN_MISSING_REGISTERS.items():
            coordinator.device_client.available_registers[reg_type].difference_update(names)

    _LOGGER.info(
        "Loaded full register list: %d total registers",
        sum(len(regs) for regs in coordinator.device_client.available_registers.values()),
    )


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
            coordinator.device_client.available_registers = normalise_fn(
                {key: value for key, value in available.items() if isinstance(value, (list, set))}
            )
        else:
            coordinator.device_client.available_registers = normalise_available_registers(
                coordinator,
                {key: value for key, value in available.items() if isinstance(value, (list, set))},
            )
    except (TypeError, ValueError):
        return False

    device_info = cache.get("device_info")
    coordinator.device_client.device_info = device_info if isinstance(device_info, dict) else {}
    caps_obj = cache.get("capabilities")
    if isinstance(caps_obj, dict):
        try:
            coordinator.device_client.capabilities = DeviceCapabilities(**caps_obj)
        except (TypeError, ValueError):
            _LOGGER.debug("Invalid cached capabilities", exc_info=True)
    coordinator.device_client.device_scan_result = cache

    if getattr(coordinator.device_client.config, "connection_mode", None) == CONNECTION_MODE_AUTO:
        if resolved := cache.get("resolved_connection_mode"):
            coordinator.device_client._resolved_connection_mode = resolved

    if (
        coordinator.device_client.device_info.get("serial_number")
        and coordinator.device_client.device_info["serial_number"] != "Unknown"
    ):
        coordinator.device_client.available_registers["input_registers"].add("serial_number")

    if firmware_lacks_known_missing(coordinator.device_client.device_info.get("firmware")):
        for reg_type, names in KNOWN_MISSING_REGISTERS.items():
            if reg_type in coordinator.device_client.available_registers:
                coordinator.device_client.available_registers[reg_type].difference_update(names)

    return True


def store_scan_cache(coordinator: Any) -> None:
    """Store scan results in config entry options."""
    if coordinator.entry is None:
        return

    available = {
        key: sorted(value) for key, value in coordinator.device_client.available_registers.items()
    }
    cache = {
        "available_registers": available,
        "device_info": coordinator.device_client.device_info,
        "capabilities": coordinator.device_client.capabilities.as_dict(),
        "firmware": coordinator.device_client.device_info.get("firmware"),
        "resolved_connection_mode": coordinator.device_client._resolved_connection_mode,
    }
    options = dict(coordinator.entry.options)
    options["device_scan_cache"] = cache
    coordinator.hass.config_entries.async_update_entry(coordinator.entry, options=options)


def consume_config_flow_scan_cache(coordinator: Any) -> dict[str, Any]:
    """Read and clear the one-time config-flow scan cache from entry options.

    Returns the cache dict if present and valid, otherwise empty dict.
    Removes the key so subsequent HA restarts perform a fresh device scan.
    """
    entry = coordinator.entry
    if entry is None:
        return {}
    cache = entry.options.get("config_flow_scan_cache", {})
    if not isinstance(cache, dict) or not cache:
        return {}
    options = {k: v for k, v in entry.options.items() if k != "config_flow_scan_cache"}
    coordinator.hass.config_entries.async_update_entry(entry, options=options)
    return cache


async def prepare_registers_for_setup(coordinator: Any) -> None:
    """Prepare register availability from full list, cache, or device scan."""
    if coordinator.device_client.force_full_register_list:
        _LOGGER.info("Using full register list (skipping scan)")
        coordinator._load_full_register_list()
        return

    if not coordinator.enable_device_scan:
        cache = coordinator._get_scan_cache_from_entry()
        if cache and coordinator._apply_scan_cache(cache):
            _LOGGER.info("Using cached device scan results")
            return
        _LOGGER.info("Device scan disabled; falling back to full register list")
        coordinator._load_full_register_list()
        return

    cache = coordinator._consume_config_flow_scan_cache()
    if cache and coordinator._apply_scan_cache(cache):
        _LOGGER.info("Using config-flow scan cache")
        return

    _LOGGER.info("Scanning device for available registers")
    await coordinator._run_device_scan()
