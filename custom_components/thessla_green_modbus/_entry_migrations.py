"""Config-entry version migration helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_CONNECTION_MODE,
    CONF_CONNECTION_TYPE,
    CONF_SLAVE_ID,
    CONNECTION_TYPE_TCP,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
)
from .utils import resolve_connection_settings

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__.rsplit(".", maxsplit=1)[0])

async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry.

    Called by Home Assistant during integration upgrades.
    """
    _LOGGER.debug("Migrating ThesslaGreen Modbus from version %s", config_entry.version)

    new_data = {**config_entry.data}
    new_options = {**config_entry.options}

    if config_entry.version == 1:
        _LOGGER.error(
            "ThesslaGreen Modbus: config entry version 1 (pre-2021) is no longer "
            "supported. Please remove and re-add the integration."
        )
        return False

    if config_entry.version == 2:
        if CONF_CONNECTION_TYPE not in new_data:
            new_data[CONF_CONNECTION_TYPE] = DEFAULT_CONNECTION_TYPE
        config_entry.version = 3

    if config_entry.version == 3:
        connection_type = new_data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        connection_mode = new_data.get(CONF_CONNECTION_MODE)
        normalized_type, resolved_mode = resolve_connection_settings(
            connection_type, connection_mode, new_data.get(CONF_PORT, DEFAULT_PORT)
        )
        new_data[CONF_CONNECTION_TYPE] = normalized_type
        if normalized_type == CONNECTION_TYPE_TCP:
            new_data[CONF_CONNECTION_MODE] = resolved_mode
        else:
            new_data.pop(CONF_CONNECTION_MODE, None)
            new_options.pop(CONF_CONNECTION_MODE, None)
        config_entry.version = 4

    host = new_data.get(CONF_HOST)
    port = new_data.get(CONF_PORT, DEFAULT_PORT)
    if CONF_SLAVE_ID in new_data:
        slave_id = new_data[CONF_SLAVE_ID]
    elif "slave_id" in new_data:
        slave_id = new_data["slave_id"]
    elif "unit" in new_data:
        slave_id = new_data["unit"]
    else:
        slave_id = DEFAULT_SLAVE_ID

    unique_host = host.replace(":", "-") if host else host
    new_unique_id = f"{unique_host}:{port}:{slave_id}"

    hass.config_entries.async_update_entry(
        config_entry, data=new_data, options=new_options, unique_id=new_unique_id
    )

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
