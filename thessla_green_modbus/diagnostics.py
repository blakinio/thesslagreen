"""Diagnostics support for TeslaGreen Modbus Integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TeslaGreenCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: TeslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "domain": entry.domain,
        },
        "data": {
            "host": entry.data.get("host", "REDACTED"),
            "port": entry.data.get("port"),
            "slave_id": entry.data.get("slave_id"),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
            "update_interval": coordinator.update_interval.total_seconds(),
            "data_keys": list(coordinator.data.keys()) if coordinator.data else [],
        },
        "device_data": coordinator.data if coordinator.data else {},
    }
