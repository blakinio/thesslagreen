"""Config-entry identity migration helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ._config_flow.entry import build_stable_unique_id
from .const import DOMAIN

if TYPE_CHECKING:  # pragma: no cover
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def migrate_config_entry_unique_id(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: Any,
) -> bool:
    """Move a legacy endpoint-derived config-entry ID to stable device identity.

    The serial is only trusted after the coordinator has successfully connected
    and completed its initial refresh.  Avoid changing the entry when the
    device does not expose a usable serial, and never claim a stable ID already
    owned by another config entry.
    """
    device_info = getattr(getattr(coordinator, "device_client", None), "device_info", {}) or {}
    if not isinstance(device_info, dict):
        return False

    stable_unique_id = build_stable_unique_id(device_info)
    if stable_unique_id is None or getattr(entry, "unique_id", None) == stable_unique_id:
        return False

    existing = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, stable_unique_id)
    if existing is not None and getattr(existing, "entry_id", None) != entry.entry_id:
        _LOGGER.warning(
            "Not migrating ThesslaGreen config-entry identity for %s: stable identifier %s "
            "is already used by entry %s",
            entry.entry_id,
            stable_unique_id,
            getattr(existing, "entry_id", "unknown"),
        )
        return False

    hass.config_entries.async_update_entry(entry, unique_id=stable_unique_id)
    _LOGGER.info(
        "Migrated ThesslaGreen config-entry identity to stable device identifier for entry %s",
        entry.entry_id,
    )
    return True
