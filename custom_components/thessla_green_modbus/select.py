"""Select platform for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .modbus_exceptions import ConnectionException, ModbusException

_LOGGER = logging.getLogger(__name__)

# Select entity definitions
SELECT_DEFINITIONS = {
    "mode": {
        "icon": "mdi:cog",
        "translation_key": "mode",
        "states": {"auto": 0, "manual": 1, "temporary": 2},
        "register_type": "holding_registers",
    },
    "bypass_mode": {
        "icon": "mdi:pipe-leak",
        "translation_key": "bypass_mode",
        "states": {"auto": 0, "open": 1, "closed": 2},
        "register_type": "holding_registers",
    },
    "gwc_mode": {
        "icon": "mdi:pipe",
        "translation_key": "gwc_mode",
        "states": {"off": 0, "auto": 1, "forced": 2},
        "register_type": "holding_registers",
    },
    "filter_change": {
        "icon": "mdi:filter-variant",
        "translation_key": "filter_change",
        "states": {
            "presostat": 1,
            "flat_filters": 2,
            "cleanpad": 3,
            "cleanpad_pure": 4,
        },
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


class ThesslaGreenSelect(ThesslaGreenEntity, SelectEntity):
    """Select entity for ThesslaGreen device."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        definition: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, register_name)
        self._attr_device_info = coordinator.get_device_info()
        self._register_name = register_name

        self._attr_translation_key = definition["translation_key"]
        self._attr_icon = definition.get("icon")
        self._attr_has_entity_name = True
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
        try:
            success = await self.coordinator.async_write_register(
                self._register_name, value, refresh=False
            )
        except (ModbusException, ConnectionException) as err:
            _LOGGER.error("Error setting %s to %s: %s", self._register_name, option, err)
            self.hass.helpers.issue.async_create_issue(
                DOMAIN,
                "modbus_write_failed",
                translation_key="modbus_write_failed",
                translation_placeholders={
                    "register": self._register_name,
                    "error": str(err),
                },
            )
            return

        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s to %s", self._register_name, option)
            self.hass.helpers.issue.async_create_issue(
                DOMAIN,
                "modbus_write_failed",
                translation_key="modbus_write_failed",
                translation_placeholders={"register": self._register_name},
            )
