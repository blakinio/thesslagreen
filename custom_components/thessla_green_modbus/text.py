"""Text platform for the ThesslaGreen Modbus integration.

Text entities expose writable ASCII-encoded multi-register strings as native
Home Assistant text controls. They are only added for registers that are
detected on the device during the scanning phase.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capability_rules import capability_block_reason
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .mappings import ENTITY_MAPPINGS
from .modbus_exceptions import ConnectionException, ModbusException

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen text entities.

    Home Assistant invokes this during platform setup.
    """
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data

    entities = []
    for register_name, text_def in ENTITY_MAPPINGS["text"].items():
        register_type = text_def["register_type"]
        register_map = coordinator.get_register_map(register_type)
        available = coordinator.available_registers.get(register_type, set())
        force_create = coordinator.force_full_register_list and register_name in register_map

        if reason := capability_block_reason(register_name, coordinator.capabilities):
            _LOGGER.info("Entity skipped due to capability: %s (%s)", register_name, reason)
            continue

        if register_name in available or force_create:
            address = register_map.get(register_name)
            if address is None:
                _LOGGER.warning("No address for text entity: %s, skipping", register_name)
                continue
            entities.append(ThesslaGreenText(coordinator, register_name, address, text_def))

    if entities:
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning("Cancelled while adding text entities, retrying without initial state")
            async_add_entities(entities, False)
            return
        _LOGGER.debug("Created %d text entities", len(entities))


class ThesslaGreenText(ThesslaGreenEntity, TextEntity):
    """Text entity for a writable ASCII multi-register string.

    The coordinator decodes ASCII register sequences to plain Python strings.
    This entity presents the value as a native HA ``text`` control so users
    can read and set the register directly from the UI.
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
        self._attr_translation_key = definition["translation_key"]
        self._attr_icon = definition.get("icon", "mdi:rename")
        self._attr_has_entity_name = True
        self._attr_native_max = definition.get("max_length", 16)

    @property
    def available(self) -> bool:
        """Return True whenever the coordinator is connected."""
        return self._coordinator_connected()

    @property
    def native_value(self) -> str | None:
        """Return the current string value decoded from the register."""
        raw = self.coordinator.data.get(self._register_name)
        if raw is None:
            return None
        return str(raw) if not isinstance(raw, str) else raw

    async def async_set_value(self, value: str) -> None:
        """Write a new string value to the register."""
        try:
            await self._write_register(self._register_name, value)
        except (ModbusException, ConnectionException) as err:
            _LOGGER.error("Error setting %s to %r: %s", self._register_name, value, err)
            return
        except RuntimeError as err:
            _LOGGER.error("Failed to set %s to %r: %s", self._register_name, value, err)
