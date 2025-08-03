"""Switch platform for ThesslaGreen Modbus Integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen switches."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())

    # Device on/off control
    if "on_off_panel_mode" in holding_regs:
        entities.append(
            ThesslaGreenSwitch(
                coordinator,
                "on_off_panel_mode",
                "Urządzenie włączone",
                "mdi:power",
            )
        )

    # Comfort mode panel
    if "comfort_mode_panel" in holding_regs:
        entities.append(
            ThesslaGreenSwitch(
                coordinator,
                "comfort_mode_panel",
                "Tryb KOMFORT",
                "mdi:home-thermometer",
            )
        )

    # GWC control
    if "gwc_off" in holding_regs:
        entities.append(
            ThesslaGreenSwitch(
                coordinator,
                "gwc_off",
                "GWC dezaktywacja",
                "mdi:heat-pump-off",
                inverted=True,  # 0 = active, 1 = inactive
            )
        )

    # Bypass control
    if "bypass_off" in holding_regs:
        entities.append(
            ThesslaGreenSwitch(
                coordinator,
                "bypass_off",
                "Bypass dezaktywacja",
                "mdi:valve-closed",
                inverted=True,  # 0 = active, 1 = inactive
            )
        )

    if entities:
        _LOGGER.debug("Adding %d switch entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenSwitch(CoordinatorEntity, SwitchEntity):
    """ThesslaGreen switch entity."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        inverted: bool = False,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._inverted = inverted

        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return if the switch is on."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None

        result = bool(value)
        # For inverted switches (like "off" registers), flip the logic
        if self._inverted:
            result = not result

        return result

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        value = 0 if self._inverted else 1
        success = await self.coordinator.async_write_register(self._key, value)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn on %s", self._key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        value = 1 if self._inverted else 0
        success = await self.coordinator.async_write_register(self._key, value)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn off %s", self._key)