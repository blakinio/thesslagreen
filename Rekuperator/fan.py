"""Fan platform for TeslaGreen Modbus Integration."""
from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN
from .coordinator import TeslaGreenCoordinator
from .entity import TeslaGreenEntity

SPEED_RANGE = (1, 4)  # 4 speed levels


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TeslaGreen fans."""
    coordinator: TeslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TeslaGreenFan(coordinator)])


class TeslaGreenFan(TeslaGreenEntity, FanEntity):
    """TeslaGreen fan entity."""

    _attr_name = "Wentylator"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = ["Auto", "Night", "Boost", "Away"]
    _attr_speed_count = 4

    def __init__(self, coordinator: TeslaGreenCoordinator) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, "fan")

    @property
    def is_on(self) -> bool:
        """Return if the fan is on."""
        speed = self.coordinator.data.get("fan_speed_setting", 0)
        return speed > 0

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        speed = self.coordinator.data.get("fan_speed_setting", 0)
        if speed == 0:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, speed)

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        mode = self.coordinator.data.get("mode_selection", 0)
        preset_map = {
            0: None,  # Off
            1: "Auto",
            2: "Night",
            3: "Boost",
            4: "Away",
        }
        return preset_map.get(mode)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        elif percentage:
            await self.async_set_percentage(percentage)
        else:
            # Default to medium speed
            await self.async_set_percentage(50)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.async_write_register("fan_speed_setting", 0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
        else:
            speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            await self.coordinator.async_write_register("fan_speed_setting", speed)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        preset_map = {
            "Auto": 1,
            "Night": 2,
            "Boost": 3,
            "Away": 4,
        }
        if preset_mode in preset_map:
            await self.coordinator.async_write_register("mode_selection", preset_map[preset_mode])
