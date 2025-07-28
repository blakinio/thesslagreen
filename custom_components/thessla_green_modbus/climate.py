"""Climate platform for TeslaGreen Modbus Integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TeslaGreenCoordinator
from .entity import TeslaGreenEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TeslaGreen climate."""
    coordinator: TeslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TeslaGreenClimate(coordinator)])


class TeslaGreenClimate(TeslaGreenEntity, ClimateEntity):
    """TeslaGreen climate entity."""

    _attr_name = "Rekuperator"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.FAN_ONLY, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
    )
    _attr_fan_modes = ["Low", "Medium", "High", "Auto"]
    _attr_min_temp = 10
    _attr_max_temp = 30

    def __init__(self, coordinator: TeslaGreenCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, "climate")

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self.coordinator.data.get("temp_supply")

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        target = self.coordinator.data.get("target_temperature")
        return target / 10.0 if target is not None else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        mode = self.coordinator.data.get("mode_selection", 0)
        if mode == 0:
            return HVACMode.OFF
        elif mode == 1:
            return HVACMode.FAN_ONLY
        else:
            return HVACMode.AUTO

    @property
    def fan_mode(self) -> str:
        """Return current fan mode."""
        speed = self.coordinator.data.get("fan_speed_setting", 0)
        if speed <= 25:
            return "Low"
        elif speed <= 50:
            return "Medium"
        elif speed <= 75:
            return "High"
        else:
            return "Auto"

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            # Convert to register value (multiply by 10)
            value = int(temperature * 10)
            await self.coordinator.async_write_register("target_temperature", value)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        mode_map = {
            HVACMode.OFF: 0,
            HVACMode.FAN_ONLY: 1,
            HVACMode.AUTO: 2,
        }
        if hvac_mode in mode_map:
            await self.coordinator.async_write_register("mode_selection", mode_map[hvac_mode])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        speed_map = {
            "Low": 25,
            "Medium": 50,
            "High": 75,
            "Auto": 100,
        }
        if fan_mode in speed_map:
            await self.coordinator.async_write_register("fan_speed_setting", speed_map[fan_mode])
