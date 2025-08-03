"""Fan platform for ThesslaGreen Modbus Integration."""
from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN
from .coordinator import ThesslaGreenCoordinator

SPEED_RANGE = (10, 100)  # 10-100% speed range


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen fans."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # Main fan control based on available manual control
    if "air_flow_rate_manual" in holding_regs:
        entities.append(ThesslaGreenFan(coordinator))
    
    if entities:
        async_add_entities(entities)


class ThesslaGreenFan(CoordinatorEntity, FanEntity):
    """ThesslaGreen fan entity."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_speed_count = 100

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)
        
        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        
        self._attr_name = f"{device_name} Wentylator"
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_fan"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool:
        """Return if the fan is on."""
        # Check if device is on and has active air flow
        device_on = self.coordinator.data.get("on_off_panel_mode", 1)
        if not device_on:
            return False
            
        # Get current intensity based on mode
        mode = self.coordinator.data.get("mode", 0)
        
        if mode == 0:  # Auto mode
            intensity = self.coordinator.data.get("supply_percentage", 0)
        elif mode == 1:  # Manual mode
            intensity = self.coordinator.data.get("air_flow_rate_manual", 0)
        elif mode == 2:  # Temporary mode
            intensity = self.coordinator.data.get("air_flow_rate_temporary", 0)
        else:
            intensity = 0
            
        return intensity > 0

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self.is_on:
            return 0
            
        # Get current intensity based on mode
        mode = self.coordinator.data.get("mode", 0)
        
        if mode == 0:  # Auto mode
            intensity = self.coordinator.data.get("supply_percentage", 0)
        elif mode == 1:  # Manual mode
            intensity = self.coordinator.data.get("air_flow_rate_manual", 0)
        elif mode == 2:  # Temporary mode
            intensity = self.coordinator.data.get("air_flow_rate_temporary", 0)
        else:
            intensity = 0
            
        if intensity == 0:
            return 0
            
        # Ensure intensity is within valid range
        return max(10, min(100, intensity))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        # First ensure device is on
        device_on = self.coordinator.data.get("on_off_panel_mode", 1)
        if not device_on:
            await self.coordinator.async_write_register("on_off_panel_mode", 1)
        
        # Switch to manual mode
        await self.coordinator.async_write_register("mode", 1)
        
        # Set percentage
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            # Default to 30%
            await self.async_set_percentage(30)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        # Turn off the entire device
        await self.coordinator.async_write_register("on_off_panel_mode", 0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return
            
        # Ensure percentage is within valid range
        percentage = max(10, min(100, percentage))
        
        # Set manual mode first
        await self.coordinator.async_write_register("mode", 1)
        
        # Set air flow rate
        success = await self.coordinator.async_write_register("air_flow_rate_manual", percentage)
        
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set fan speed to %s%%", percentage)
