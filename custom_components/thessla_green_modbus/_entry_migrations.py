"""Config-entry version migration helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle legacy config-entry schema versions.

    Versions 1-3 predate the supported entry schema and require the integration
    to be removed and re-added. Version 4 is the current schema; stable device
    identity is migrated after a successful initial refresh, when the device
    serial is actually available, rather than deriving identity from an
    endpoint here.
    """
    _LOGGER.debug("Migrating ThesslaGreen Modbus from version %s", config_entry.version)

    if config_entry.version in (1, 2, 3):
        _LOGGER.error(
            "ThesslaGreen Modbus: config entry version %s (pre-2023) is no longer "
            "supported. Please remove and re-add the integration.",
            config_entry.version,
        )
        return False

    # Home Assistant normally calls this hook only when an entry version is
    # older than ConfigFlow.VERSION. Keep current/newer versions as a safe no-op
    # for direct calls and tests; never recreate endpoint-derived unique IDs.
    return True
