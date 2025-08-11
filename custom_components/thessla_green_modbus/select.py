# Select entities for the ThesslaGreen Modbus integration
"""Select platform for the ThesslaGreen Modbus integration."""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Select entity definitions
SELECT_DEFINITIONS = {
    "mode": {
        "icon": "mdi:cog",
 codex/replace-hard-coded-strings-with-translation-keys
        "options": ["auto", "manual", "temporary"],
        "values": [0, 1, 2],
=======
        "translation_key": "mode",
        "states": {"auto": 0, "manual": 1, "temporary": 2},
 main
        "register_type": "holding_registers",
    },
    "bypass_mode": {
        "icon": "mdi:pipe-leak",
 codex/replace-hard-coded-strings-with-translation-keys
        "options": ["auto", "open", "closed"],
        "values": [0, 1, 2],
=======
        "translation_key": "bypass_mode",
        "states": {"auto": 0, "open": 1, "closed": 2},
 main
        "register_type": "holding_registers",
    },
    "gwc_mode": {
        "icon": "mdi:pipe",
 codex/replace-hard-coded-strings-with-translation-keys
        "options": ["off", "auto", "forced"],
        "values": [0, 1, 2],
=======
        "translation_key": "gwc_mode",
        "states": {"off": 0, "auto": 1, "forced": 2},
 main
        "register_type": "holding_registers",
    },
    "filter_change": {
        "icon": "mdi:filter-variant",
 codex/replace-hard-coded-strings-with-translation-keys
        "options": ["presostat", "flat_filters", "cleanpad", "cleanpad_pure"],
        "values": [1, 2, 3, 4],
=======
        "translation_key": "filter_change",
        "states": {
            "presostat": 1,
            "flat_filters": 2,
            "cleanpad": 3,
            "cleanpad_pure": 4,
        },
 main
        "register_type": "holding_registers",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen select entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for register_name, select_def in SELECT_DEFINITIONS.items():
        register_type = select_def["register_type"]
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenSelect(coordinator, register_name, select_def))

    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Created %d select entities", len(entities))


class ThesslaGreenSelect(CoordinatorEntity, SelectEntity):
    """Select entity for ThesslaGreen device."""

    def __init__(self, coordinator, register_name, definition):
        super().__init__(coordinator)
        self._register_name = register_name

        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{register_name}"
        self._attr_translation_key = definition["translation_key"]
        self._attr_has_entity_name = True
        self._attr_device_info = coordinator.get_device_info()
        self._attr_icon = definition.get("icon")
        self._states = definition["states"]
        self._reverse_states = {v: k for k, v in self._states.items()}
        self._attr_options = list(self._states.keys())

    @property
    def current_option(self) -> Optional[str]:
        """Return current option."""
        value = self.coordinator.data.get(self._register_name)
        if value is None:
            return None

        return self._reverse_states.get(value)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self._states:
            _LOGGER.error("Invalid option: %s", option)
            return

        value = self._states[option]
        success = await self.coordinator.async_write_register(self._register_name, value)
        if success:
            await self.coordinator.async_request_refresh()
