"""Select platform for ThesslaGreen Modbus Integration."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    OPERATING_MODES,
    SEASON_MODES,
    SPECIAL_MODES,
    GWC_MODES,
    BYPASS_MODES,
    COMFORT_MODES,
)
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen select entities."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())

    # Operating mode
    if "mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "mode",
                "Tryb pracy",
                list(OPERATING_MODES.values()),
                "mdi:cog",
            )
        )

    # Season mode
    if "season_mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "season_mode",
                "Sezon",
                list(SEASON_MODES.values()),
                "mdi:weather-sunny",
            )
        )

    # Special functions
    if "special_mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "special_mode",
                "Funkcja specjalna",
                list(SPECIAL_MODES.values()),
                "mdi:star",
            )
        )

    # GWC mode
    if "gwc_mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "gwc_mode",
                "Tryb GWC",
                list(GWC_MODES.values()),
                "mdi:heat-pump",
            )
        )

    # Bypass mode
    if "bypass_mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "bypass_mode",
                "Tryb Bypass",
                list(BYPASS_MODES.values()),
                "mdi:valve",
            )
        )

    # Comfort mode
    if "comfort_mode" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "comfort_mode",
                "Tryb KOMFORT",
                list(COMFORT_MODES.values()),
                "mdi:home-thermometer",
            )
        )

    if entities:
        _LOGGER.debug("Adding %d select entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenSelect(CoordinatorEntity, SelectEntity):
    """ThesslaGreen select entity."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        options: list[str],
        icon: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_options = options
        self._attr_icon = icon

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
    def current_option(self) -> str | None:
        """Return current option."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None

        if self._key == "mode":
            return OPERATING_MODES.get(value, "Unknown")
        elif self._key == "season_mode":
            return SEASON_MODES.get(value, "Unknown")
        elif self._key == "special_mode":
            return SPECIAL_MODES.get(value, "Unknown")
        elif self._key == "gwc_mode":
            return GWC_MODES.get(value, "Unknown")
        elif self._key == "bypass_mode":
            return BYPASS_MODES.get(value, "Unknown")
        elif self._key == "comfort_mode":
            return COMFORT_MODES.get(value, "Unknown")

        return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        value_map = {}
        
        if self._key == "mode":
            value_map = {v: k for k, v in OPERATING_MODES.items()}
        elif self._key == "season_mode":
            value_map = {v: k for k, v in SEASON_MODES.items()}
        elif self._key == "special_mode":
            value_map = {v: k for k, v in SPECIAL_MODES.items()}
        elif self._key == "gwc_mode":
            # GWC mode jest read-only, nie można go ustawiać
            _LOGGER.warning("Cannot set read-only GWC mode")
            return
        elif self._key == "bypass_mode":
            # Bypass mode jest read-only, nie można go ustawiać
            _LOGGER.warning("Cannot set read-only bypass mode")
            return
        elif self._key == "comfort_mode":
            # Comfort mode jest read-only, nie można go ustawiać
            _LOGGER.warning("Cannot set read-only comfort mode")
            return

        if option in value_map:
            success = await self.coordinator.async_write_register(self._key, value_map[option])
            if success:
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to set %s to %s", self._key, option)
