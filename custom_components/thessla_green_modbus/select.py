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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capability_rules import capability_block_reason
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity
from .mappings import ENTITY_MAPPINGS
from .modbus_exceptions import ConnectionException, ModbusException
from .schedule_helpers import SETTING_SCHEDULE_PREFIXES
from .utils import BCD_TIME_PREFIXES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:  # pragma: no cover - defensive
    """Set up ThesslaGreen select entities.

    Home Assistant invokes this during platform setup.
    """
    coordinator: ThesslaGreenModbusCoordinator = config_entry.runtime_data

    entities = []
    # Only create selects for registers discovered by
    # ThesslaGreenDeviceScanner.scan_device() or all known registers when
    # ``force_full_register_list`` is enabled.
    for register_name, select_def in ENTITY_MAPPINGS["select"].items():
        register_type = select_def["register_type"]
        register_map = coordinator.get_register_map(register_type)
        available = coordinator.available_registers.get(register_type, set())
        force_create = coordinator.force_full_register_list and register_name in register_map
        if reason := capability_block_reason(register_name, coordinator.capabilities):
            _LOGGER.info("Entity skipped due to capability: %s (%s)", register_name, reason)
            continue
        if register_name in available or force_create:
            address = register_map.get(register_name)
            if address is None:
                _LOGGER.warning("No address for select: %s, skipping", register_name)
                continue
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

        self._attr_translation_key = definition["translation_key"]  # pragma: no cover - defensive
        self._attr_icon = definition.get("icon")
        self._attr_has_entity_name = True  # pragma: no cover - defensive
        self._states = definition["states"]
        self._reverse_states = {v: k for k, v in self._states.items()}
        self._attr_options = list(self._states.keys())  # pragma: no cover - defensive

    @property
    def available(self) -> bool:  # pragma: no cover - defensive
        """Return if entity is available.

        Time-based schedule selects (BCD time registers) are considered
        available whenever the coordinator is connected, even when no time
        value is currently stored.  This lets users configure a slot that
        the device reports as «not set» (e.g. BCD sentinel 0xFFFF) without
        the entity disappearing as «unavailable».
        """
        if self._register_name.startswith(BCD_TIME_PREFIXES + SETTING_SCHEDULE_PREFIXES):
            return self.coordinator.last_update_success and not getattr(
                self.coordinator, "offline_state", False
            )
        return super().available

    @property
    def current_option(self) -> str | None:  # pragma: no cover - defensive
        """Return current option."""
        value = self.coordinator.data.get(self._register_name)
        if value is None:
            return None

        # AATT registers (setting_summer_*, setting_winter_*) decode to a
        # dict with "airflow_pct" and "temp_c" keys.  The select entity only
        # cares about the airflow percentage.
        if isinstance(value, dict):
            value = value.get("airflow_pct")
            if value is None:
                return None

        return self._reverse_states.get(value)

    async def async_select_option(self, option: str) -> None:  # pragma: no cover - defensive
        """Change the selected option."""
        if option not in self._states:
            msg = f"Invalid option for {self._register_name}: {option}"
            _LOGGER.error(msg)
            raise HomeAssistantError(msg)

        value = self._states[option]
        try:
            success = await self.coordinator.async_write_register(
                self._register_name, value, refresh=False
            )
        except (ModbusException, ConnectionException) as err:
            msg = f"Error setting {self._register_name} to {option}: {err}"
            _LOGGER.error(msg)
            raise HomeAssistantError(msg) from err

        if success:
            await self.coordinator.async_request_refresh()
        else:
            msg = f"Failed to set {self._register_name} to {option}"
            _LOGGER.error(msg)
            raise HomeAssistantError(msg)
