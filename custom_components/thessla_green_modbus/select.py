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
        "options": ["auto", "manual", "temporary"],
        "values": [0, 1, 2],
        "register_type": "holding_registers",
    },
    "bypass_mode": {
        "icon": "mdi:pipe-leak",
        "options": ["auto", "open", "closed"],
        "values": [0, 1, 2],
        "register_type": "holding_registers",
    },
    "gwc_mode": {
        "icon": "mdi:pipe",
        "options": ["off", "auto", "forced"],
        "values": [0, 1, 2],
        "register_type": "holding_registers",
    },
    "filter_change": {
        "icon": "mdi:filter-variant",
        "options": ["presostat", "flat_filters", "cleanpad", "cleanpad_pure"],
        "values": [1, 2, 3, 4],
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
        self._definition = definition

        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{register_name}"
        self._attr_translation_key = register_name
        self._attr_has_entity_name = True
        self._attr_device_info = coordinator.get_device_info()
        self._attr_icon = definition.get("icon")
        self._attr_options = definition["options"]

    @property
    def current_option(self) -> Optional[str]:
        """Return current option."""
        value = self.coordinator.data.get(self._register_name)
        if value is None:
            return None

        try:
            index = self._definition["values"].index(value)
            return self._definition["options"][index]
        except (ValueError, IndexError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            index = self._definition["options"].index(option)
            value = self._definition["values"][index]
            success = await self.coordinator.async_write_register(self._register_name, value)
            if success:
                await self.coordinator.async_request_refresh()
        except ValueError:
            _LOGGER.error("Invalid option: %s", option)
