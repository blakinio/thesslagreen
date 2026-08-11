"""Home Assistant device-registry identity migration helpers."""

from __future__ import annotations

import logging
from collections.abc import Collection
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator.diagnostics import _stable_device_identifier

if TYPE_CHECKING:  # pragma: no cover
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _belongs_to_entry(device: Any, entry_id: str) -> bool:
    """Return whether a device belongs to the config entry across supported HA APIs."""
    if getattr(device, "config_entry_id", None) == entry_id:
        return True
    config_entries: Collection[str] = getattr(device, "config_entries", set())
    try:
        return entry_id in config_entries
    except TypeError:
        return False


def migrate_device_identifier(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: Any,
) -> None:
    """Replace mutable endpoint identity with a stable device-registry identifier.

    Older releases keyed the AirPack device by ``host:port:slave``. That makes a
    legitimate host/port reconfigure look like a new physical device. Migrate
    that identifier before entity platforms register their current DeviceInfo.
    """
    dc = coordinator.device_client
    stable_identifier = _stable_device_identifier(coordinator)

    # ``endpoint:...`` exists only as a deterministic fallback for isolated
    # helpers/tests. It is not a stable physical-device identity, so it must
    # never rewrite the Home Assistant device registry.
    if stable_identifier.startswith("endpoint:"):
        return

    registry = dr.async_get(hass)
    stable = (DOMAIN, stable_identifier)
    legacy = (DOMAIN, f"{dc.config.host}:{dc.config.port}:{dc.config.slave_id}")

    stable_device = registry.async_get_device(identifiers={stable})
    legacy_device = registry.async_get_device(identifiers={legacy})
    device = stable_device or legacy_device
    if device is None or not _belongs_to_entry(device, entry.entry_id):
        return

    current_identifiers = set(getattr(device, "identifiers", set()))
    desired_identifiers = {
        identifier for identifier in current_identifiers if identifier[0] != DOMAIN
    }
    desired_identifiers.add(stable)
    if current_identifiers == desired_identifiers:
        return

    registry.async_update_device(device.id, new_identifiers=desired_identifiers)
    _LOGGER.info(
        "Migrated ThesslaGreen device registry identity to stable identifier for entry %s",
        entry.entry_id,
    )
