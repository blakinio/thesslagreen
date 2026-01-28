"""Select platform for the ThesslaGreen Modbus integration.

Select entities expose enumerated Modbus registers. They are only added for
registers that are detected on the device during the scanning phase.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .entity_mappings import ENTITY_MAPPINGS
from .modbus_exceptions import ConnectionException, ModbusException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:  # pragma: no cover
    """Set up ThesslaGreen select entities.

    Home Assistant invokes this during platform setup.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    if not coordinator.capabilities_valid:
        _LOGGER.error("Capabilities missing; select setup aborted")
        return

    entities = []
    # Only create selects for registers discovered by ThesslaGreenDeviceScanner.scan_device().
    for register_name, select_def in ENTITY_MAPPINGS["select"].items():
        register_type = select_def["register_type"]
        register_map = coordinator.get_register_map(register_type)
        available = coordinator.available_registers.get(register_type, set())
        if register_name in available:
            address = register_map[register_name]
            entities.append(ThesslaGreenSelect(coordinator, register_name, address, select_def))

    if entities:
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning(
                "Cancelled while adding select entities, retrying without initial state"
            )
            async_add_entities(entities, False)
            return
        _LOGGER.debug("Created %d select entities", len(entities))


class ThesslaGreenSelect(ThesslaGreenEntity, SelectEntity):
    """Select entity for ThesslaGreen device.

    ``_attr_*`` attributes and methods implement the Home Assistant
    ``SelectEntity`` API and may appear unused.
    """

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        address: int,
        definition: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, register_name, address)
        self._register_name = register_name

        self._attr_translation_key = definition["translation_key"]  # pragma: no cover
        self._attr_icon = definition.get("icon")
        self._attr_has_entity_name = True  # pragma: no cover
        self._states = definition["states"]
        self._reverse_states = {v: k for k, v in self._states.items()}
        self._attr_options = list(self._states.keys())  # pragma: no cover

    @property
    def current_option(self) -> str | None:  # pragma: no cover
        """Return current option."""
        value = self.coordinator.data.get(self._register_name)
        if value is None:
            return None

        return self._reverse_states.get(value)

    async def async_select_option(self, option: str) -> None:  # pragma: no cover
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
