"""Time platform for the ThesslaGreen Modbus integration.

Time entities expose writable BCD-encoded HHMM registers as native
Home Assistant time controls (HH:MM). They are only added for registers
that are detected on the device during the scanning phase.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import time as dt_time
from typing import Any

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capability_rules import capability_block_reason
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
    """Set up ThesslaGreen time entities.

    Home Assistant invokes this during platform setup.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for register_name, time_def in ENTITY_MAPPINGS["time"].items():
        register_type = time_def["register_type"]
        register_map = coordinator.get_register_map(register_type)
        available = coordinator.available_registers.get(register_type, set())
        force_create = coordinator.force_full_register_list and register_name in register_map

        if reason := capability_block_reason(register_name, coordinator.capabilities):
            _LOGGER.info("Entity skipped due to capability: %s (%s)", register_name, reason)
            continue

        if register_name in available or force_create:
            address = register_map[register_name]
            entities.append(ThesslaGreenTime(coordinator, register_name, address, time_def))

    if entities:
        try:
            async_add_entities(entities, True)
        except asyncio.CancelledError:
            _LOGGER.warning(
                "Cancelled while adding time entities, retrying without initial state"
            )
            async_add_entities(entities, False)
            return
        _LOGGER.debug("Created %d time entities", len(entities))


class ThesslaGreenTime(ThesslaGreenEntity, TimeEntity):
    """Time entity for a writable BCD HHMM register.

    The coordinator decodes BCD HHMM register values to ``"HH:MM"`` strings.
    This entity presents the value as a native HA ``time`` control so users
    can set the register directly from the UI without manual encoding.
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
        self._attr_icon = definition.get("icon", "mdi:clock-outline")
        self._attr_has_entity_name = True  # pragma: no cover

    @property
    def available(self) -> bool:  # pragma: no cover
        """Return True whenever the coordinator is connected.

        BCD time registers may legitimately return None (unset / sentinel
        0xFFFF), so we keep the entity available to allow the user to set
        an initial value.
        """
        return (
            self.coordinator.last_update_success
            and not getattr(self.coordinator, "offline_state", False)
        )

    @property
    def native_value(self) -> dt_time | None:  # pragma: no cover
        """Return the current time value decoded from the register."""
        raw = self.coordinator.data.get(self._register_name)
        if raw is None:
            # Sentinel 0xFFFF means the slot is not configured on the device.
            # Returning dt_time(0, 0) keeps the HA frontend input interactive
            # so users can set an initial value (unknown-state inputs are
            # read-only in the HA lovelace UI).
            return dt_time(0, 0)
        if isinstance(raw, str) and ":" in raw:
            try:
                hours, minutes = (int(x) for x in raw.split(":"))
                return dt_time(hours, minutes)
            except (ValueError, TypeError):
                return dt_time(0, 0)
        if isinstance(raw, int):
            try:
                return dt_time(raw // 60, raw % 60)
            except (ValueError, TypeError):
                return dt_time(0, 0)
        return dt_time(0, 0)

    async def async_set_value(self, value: dt_time) -> None:  # pragma: no cover
        """Set a new time value.

        The loader's ``encode`` method for BCD time registers accepts an
        ``"HH:MM"`` string and converts it to the packed HHMM integer before
        writing to the device.
        """
        time_str = f"{value.hour:02d}:{value.minute:02d}"
        try:
            success = await self.coordinator.async_write_register(
                self._register_name, time_str, refresh=False
            )
        except (ModbusException, ConnectionException) as err:
            _LOGGER.error("Error setting %s to %s: %s", self._register_name, time_str, err)
            return

        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s to %s", self._register_name, time_str)
