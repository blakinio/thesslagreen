"""Config-entry version migration helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_SLAVE_ID,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry.

    Called by Home Assistant during integration upgrades.
    """
    _LOGGER.debug("Migrating ThesslaGreen Modbus from version %s", config_entry.version)

    if config_entry.version in (1, 2, 3):
        _LOGGER.error(
            "ThesslaGreen Modbus: config entry version %s (pre-2023) is no longer "
            "supported. Please remove and re-add the integration.",
            config_entry.version,
        )
        return False

    new_data = {**config_entry.data}
    new_options = {**config_entry.options}

    host = new_data.get(CONF_HOST)
    port = new_data.get(CONF_PORT, DEFAULT_PORT)
    if CONF_SLAVE_ID in new_data:
        slave_id = new_data[CONF_SLAVE_ID]
    elif "slave_id" in new_data:
        slave_id = new_data["slave_id"]
    else:
        slave_id = DEFAULT_SLAVE_ID

    unique_host = host.replace(":", "-") if host else host
    new_unique_id = f"{unique_host}:{port}:{slave_id}"

    hass.config_entries.async_update_entry(
        config_entry, data=new_data, options=new_options, unique_id=new_unique_id
    )

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
