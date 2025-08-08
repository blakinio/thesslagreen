"""Enhanced fan platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN, OPERATING_MODES, SPECIAL_MODES
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)

# Enhanced fan speed mapping for HA 2025.7+
SPEED_RANGE = (10, 150)  # ThesslaGreen intensity range: 10-150%
PRESET_MODES = ["Eco", "Comfort", "Boost", "Sleep", "Auto"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up enhanced fan platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # Check if basic fan control is available
    if "mode" in holding_regs or "mode_old" in holding_regs:
        entities.append(ThesslaGreenFan(coordinator))

    if entities:
        _LOGGER.debug("Adding %d enhanced fan entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenFan(CoordinatorEntity, FanEntity):
    """Enhanced ThesslaGreen fan entity - HA 2025.7+ Compatible."""
    
    _attr_has_entity_name = True  # ✅ FIX: Enable entity naming

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the enhanced fan."""
        super().__init__(coordinator)
        
        self._attr_name = "Ventilation Fan"
        self._attr_translation_key = "fan"
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.','_')}_{coordinator.slave_id}_fan"
        
        # Enhanced supported features for HA 2025.7+
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED |
            FanEntityFeature.PRESET_MODE |
            FanEntityFeature.TURN_ON |
            FanEntityFeature.TURN_OFF
        )
        
        # Preset modes
        self._attr_preset_modes = PRESET_MODES
        
        # Enhanced device info
        device_info = coordinator.device_scan_result.get("device_info", {}) if hasattr(coordinator, 'device_scan_result') else {}
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": f"ThesslaGreen AirPack ({coordinator.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        # Check device status
        device_on = self.coordinator.data.get("device_status_smart", False)
        if not device_on:
            return False
        
        # Check if intensity is greater than 0
        mode = self.coordinator.data.get("mode")
        if mode is None:
            mode = self.coordinator.data.get("mode_old", 1)
        
        if mode == 1:  # Manual
            intensity = self.coordinator.data.get("air_flow_rate_manual")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_1", 0)
        elif mode == 2:  # Temporary
            intensity = self.coordinator.data.get("air_flow_rate_temporary")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_2", 0)
        else:  # Auto
            intensity = self.coordinator.data.get("air_flow_rate_auto")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_3", 0)
        
        return intensity > 0

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        mode = self.coordinator.data.get("mode")
        if mode is None:
            mode = self.coordinator.data.get("mode_old", 1)
        
        if mode == 1:  # Manual
            intensity = self.coordinator.data.get("air_flow_rate_manual")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_1")
        elif mode == 2:  # Temporary
            intensity = self.coordinator.data.get("air_flow_rate_temporary")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_2")
        else:  # Auto
            intensity = self.coordinator.data.get("air_flow_rate_auto")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_3")
        
        if intensity is not None:
            # Convert ThesslaGreen intensity (10-150%) to HA percentage (0-100%)
            return ranged_value_to_percentage(SPEED_RANGE, intensity)
        
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        intensity = None
        mode = self.coordinator.data.get("mode", 1)
        
        if mode == 1:  # Manual
            intensity = self.coordinator.data.get("air_flow_rate_manual")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_1")
        else:
            intensity = self.coordinator.data.get("air_flow_rate_auto")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_3")
        
        if intensity is not None:
            if intensity <= 20:
                return "Sleep"
            elif intensity <= 30:
                return "Eco"
            elif intensity <= 50:
                return "Comfort"
            elif intensity >= 80:
                return "Boost"
        
        if mode == 0:
            return "Auto"
        
        return None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        # Ensure device is on
        if "on_off_panel_mode" in self.coordinator.available_registers.get("holding_registers", set()):
            await self.coordinator.async_write_register("on_off_panel_mode", 1)
        
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            # Default to 50% in manual mode
            await self.coordinator.async_write_register("mode", 1)
            await self.coordinator.async_write_register("air_flow_rate_manual", 50)
        
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        # Use device on/off if available
        if "on_off_panel_mode" in self.coordinator.available_registers.get("holding_registers", set()):
            await self.coordinator.async_write_register("on_off_panel_mode", 0)
        else:
            # Set intensity to 0 as fallback
            mode = self.coordinator.data.get("mode", 1)
            
            if mode == 0:  # Auto
                register = "air_flow_rate_auto"
                if register not in self.coordinator.available_registers.get("holding_registers", set()):
                    register = "intensity_3"
            elif mode == 2:  # Temporary
                register = "air_flow_rate_temporary"
                if register not in self.coordinator.available_registers.get("holding_registers", set()):
                    register = "intensity_2"
            else:  # Manual
                register = "air_flow_rate_manual"
                if register not in self.coordinator.available_registers.get("holding_registers", set()):
                    register = "intensity_1"
            
            await self.coordinator.async_write_register(register, 0)
        
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        # Convert HA percentage (0-100%) to ThesslaGreen intensity (10-150%)
        intensity = percentage_to_ranged_value(SPEED_RANGE, percentage)
        
        # Set to manual mode and apply intensity
        await self.coordinator.async_write_register("mode", 1)
        
        register = "air_flow_rate_manual"
        if register not in self.coordinator.available_registers.get("holding_registers", set()):
            register = "intensity_1"
        
        await self.coordinator.async_write_register(register, int(intensity))
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        preset_intensities = {
            "Sleep": 20,
            "Eco": 30,
            "Comfort": 50,
            "Boost": 80,
            "Auto": None,
        }
        
        if preset_mode == "Auto":
            # Set to auto mode
            mode_reg = "mode"
            if mode_reg not in self.coordinator.available_registers.get("holding_registers", set()):
                mode_reg = "mode_old"
            await self.coordinator.async_write_register(mode_reg, 0)
        elif preset_mode in preset_intensities:
            # Set to manual mode with specific intensity
            await self.coordinator.async_write_register("mode", 1)
            
            intensity = preset_intensities[preset_mode]
            if intensity:
                register = "air_flow_rate_manual"
                if register not in self.coordinator.available_registers.get("holding_registers", set()):
                    register = "intensity_1"
                
                await self.coordinator.async_write_register(register, intensity)
        
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "last_update": getattr(self.coordinator, 'last_update_success_time', self.coordinator.last_update_success),
        }
        
        # Add supply and exhaust percentages
        supply_pct = self.coordinator.data.get("supply_percentage")
        if supply_pct is not None:
            attributes["supply_fan_percentage"] = supply_pct
        
        exhaust_pct = self.coordinator.data.get("exhaust_percentage")
        if exhaust_pct is not None:
            attributes["exhaust_fan_percentage"] = exhaust_pct
        
        # Add flow rates
        supply_flow = self.coordinator.data.get("supply_flowrate")
        if supply_flow is not None:
            attributes["supply_flow_rate"] = f"{supply_flow} m³/h"
        
        exhaust_flow = self.coordinator.data.get("exhaust_flowrate")
        if exhaust_flow is not None:
            attributes["exhaust_flow_rate"] = f"{exhaust_flow} m³/h"
        
        # Add operating mode
        mode = self.coordinator.data.get("mode")
        if mode is not None and mode in OPERATING_MODES:
            attributes["operating_mode"] = OPERATING_MODES[mode]
        
        # Add special function
        special = self.coordinator.data.get("special_mode", 0)
        if special in SPECIAL_MODES:
            attributes["special_function"] = SPECIAL_MODES[special]
        
        # Add all intensity levels for debugging
        for i in range(1, 11):
            intensity_key = f"intensity_{i}"
            if intensity_key in self.coordinator.data:
                attributes[f"intensity_level_{i}"] = self.coordinator.data[intensity_key]
        
        return attributes