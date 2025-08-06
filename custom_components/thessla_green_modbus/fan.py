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
    if "mode" in holding_regs:
        entities.append(ThesslaGreenFan(coordinator))

    if entities:
        _LOGGER.debug("Adding %d enhanced fan entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenFan(CoordinatorEntity, FanEntity):
    """Enhanced ThesslaGreen fan entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the enhanced fan."""
        super().__init__(coordinator)
        
        # Enhanced device info handling
        device_info = coordinator.data.get("device_info", {}) if coordinator.data else {}
        device_name = device_info.get("device_name", f"ThesslaGreen {coordinator.host}")
        
        self._attr_name = f"{device_name} Ventilation"
        self._attr_icon = "mdi:fan"
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_fan"
        
        # Enhanced fan features for HA 2025.7+
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED |
            FanEntityFeature.PRESET_MODE |
            FanEntityFeature.TURN_ON |
            FanEntityFeature.TURN_OFF
        )
        
        self._attr_preset_modes = PRESET_MODES
        self._attr_speed_count = int_states_in_range(SPEED_RANGE)
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the fan is on."""
        system_power = self.coordinator.data.get("system_on_off")
        if system_power is None:
            return None
        return bool(system_power)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self.is_on:
            return 0
            
        # Get current intensity based on mode
        mode = self.coordinator.data.get("mode", 0)
        
        if mode == 0:  # Auto mode
            intensity = self.coordinator.data.get("supply_percentage")
        elif mode == 1:  # Manual mode
            intensity = self.coordinator.data.get("air_flow_rate_manual")
        elif mode == 2:  # Temporary mode
            intensity = self.coordinator.data.get("air_flow_rate_temporary")
        else:
            intensity = self.coordinator.data.get("supply_percentage", 50)
        
        if intensity is None:
            return None
            
        # Convert ThesslaGreen intensity (10-150%) to HA percentage (0-100%)
        return ranged_value_to_percentage(SPEED_RANGE, intensity)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if not self.is_on:
            return None
            
        # Enhanced preset mode detection based on system state
        mode = self.coordinator.data.get("mode", 0)
        special_mode = self.coordinator.data.get("special_mode", 0)
        intensity = self._get_current_intensity()
        
        # Special function takes precedence
        if special_mode == 5:  # BOOST mode
            return "Boost"
        elif special_mode == 6:  # ECO mode  
            return "Eco"
        elif special_mode == 13:  # NOC (Night) mode
            return "Sleep"
        
        # Auto mode
        if mode == 0:
            return "Auto"
            
        # Manual/Temporary mode - determine by intensity
        if intensity is not None:
            if intensity <= 30:
                return "Sleep"
            elif intensity <= 50:
                return "Eco"
            elif intensity <= 80:
                return "Comfort"
            else:
                return "Boost"
                
        return "Auto"

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return
            
        # Ensure system is on
        if not self.is_on:
            await self.async_turn_on()
        
        # Convert HA percentage to ThesslaGreen intensity
        intensity = int(percentage_to_ranged_value(SPEED_RANGE, percentage))
        
        # Enhanced mode logic for HA 2025.7+
        current_mode = self.coordinator.data.get("mode", 0)
        
        # If in Auto mode, switch to Manual for direct control
        if current_mode == 0:
            _LOGGER.info("Switching from Auto to Manual mode for speed control")
            await self.coordinator.async_write_register("mode", 1)
            
        # Set the appropriate intensity register
        if current_mode == 2:  # Temporary mode
            register_key = "air_flow_rate_temporary"
        else:  # Manual mode (or switching to manual)
            register_key = "air_flow_rate_manual"
            
        success = await self.coordinator.async_write_register(register_key, intensity)
        if success:
            _LOGGER.info("Set fan speed to %d%% (intensity: %d%%)", percentage, intensity)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set fan speed to %d%%", percentage)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        if preset_mode not in PRESET_MODES:
            _LOGGER.error("Invalid preset mode: %s", preset_mode)
            return
            
        # Enhanced preset mode implementation for HA 2025.7+
        preset_configs = {
            "Eco": {"mode": 1, "intensity": 30, "special": 6},      # Manual, 30%, ECO special mode
            "Comfort": {"mode": 1, "intensity": 60, "special": 0}, # Manual, 60%, no special mode
            "Boost": {"mode": 1, "intensity": 100, "special": 5},  # Manual, 100%, BOOST special mode  
            "Sleep": {"mode": 1, "intensity": 20, "special": 13},  # Manual, 20%, Night mode
            "Auto": {"mode": 0, "intensity": None, "special": 0},  # Auto mode, system controlled
        }
        
        config = preset_configs[preset_mode]
        
        # Ensure system is on
        if not self.is_on:
            await self.async_turn_on()
        
        # Set operating mode
        success = await self.coordinator.async_write_register("mode", config["mode"])
        if not success:
            _LOGGER.error("Failed to set operating mode for preset %s", preset_mode)
            return
            
        # Set special mode
        if config["special"] != 0:
            success = await self.coordinator.async_write_register("special_mode", config["special"])
            if not success:
                _LOGGER.warning("Failed to set special mode for preset %s", preset_mode)
        
        # Set intensity if specified
        if config["intensity"] is not None:
            if config["mode"] == 1:  # Manual mode
                success = await self.coordinator.async_write_register("air_flow_rate_manual", config["intensity"])
            elif config["mode"] == 2:  # Temporary mode
                success = await self.coordinator.async_write_register("air_flow_rate_temporary", config["intensity"])
                
            if not success:
                _LOGGER.warning("Failed to set intensity for preset %s", preset_mode)
        
        _LOGGER.info("Set fan preset mode to %s", preset_mode)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        # Turn on system power
        success = await self.coordinator.async_write_register("system_on_off", 1)
        if not success:
            _LOGGER.error("Failed to turn on system power")
            return
            
        _LOGGER.info("Turned on ventilation system")
        
        # Set percentage if specified
        if percentage is not None:
            await self.async_set_percentage(percentage)
        # Set preset mode if specified  
        elif preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        else:
            # Default to Auto mode with moderate intensity
            await self.coordinator.async_write_register("mode", 0)  # Auto mode
            
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        success = await self.coordinator.async_write_register("system_on_off", 0)
        if success:
            _LOGGER.info("Turned off ventilation system")
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn off system power")

    def _get_current_intensity(self) -> int | None:
        """Get current intensity based on operating mode."""
        mode = self.coordinator.data.get("mode", 0)
        
        if mode == 0:  # Auto mode
            return self.coordinator.data.get("supply_percentage")
        elif mode == 1:  # Manual mode
            return self.coordinator.data.get("air_flow_rate_manual")
        elif mode == 2:  # Temporary mode
            return self.coordinator.data.get("air_flow_rate_temporary")
        
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.""" 
        attributes = {}
        
        # Enhanced operating context (HA 2025.7+)
        mode = self.coordinator.data.get("mode")
        if mode is not None:
            attributes["operating_mode"] = OPERATING_MODES.get(mode, f"Mode {mode}")
        
        special_mode = self.coordinator.data.get("special_mode")
        if special_mode is not None and special_mode != 0:
            attributes["special_function"] = SPECIAL_MODES.get(special_mode, f"Function {special_mode}")
        
        # Current intensity in ThesslaGreen units
        intensity = self._get_current_intensity()
        if intensity is not None:
            attributes["current_intensity"] = f"{intensity}%"
        
        # Flow rates
        supply_flow = self.coordinator.data.get("supply_flowrate")
        exhaust_flow = self.coordinator.data.get("exhaust_flowrate")
        if supply_flow is not None:
            attributes["supply_flow_rate"] = f"{supply_flow} m³/h"
        if exhaust_flow is not None:
            attributes["exhaust_flow_rate"] = f"{exhaust_flow} m³/h"
        
        # Enhanced system status (HA 2025.7+)
        heat_recovery_eff = self.coordinator.data.get("heat_recovery_efficiency")
        if heat_recovery_eff is not None:
            attributes["heat_recovery_efficiency"] = f"{heat_recovery_eff}%"
        
        # Temperature information
        outside_temp = self.coordinator.data.get("outside_temperature")
        supply_temp = self.coordinator.data.get("supply_temperature")
        if outside_temp is not None:
            attributes["outside_temperature"] = f"{outside_temp}°C"
        if supply_temp is not None:
            attributes["supply_temperature"] = f"{supply_temp}°C"
            if outside_temp is not None:
                temp_rise = supply_temp - outside_temp
                attributes["temperature_rise"] = f"{temp_rise:.1f}°C"
        
        # System diagnostics
        error_code = self.coordinator.data.get("error_code", 0)
        warning_code = self.coordinator.data.get("warning_code", 0)
        attributes["system_errors"] = error_code != 0
        attributes["system_warnings"] = warning_code != 0
        
        # Enhanced power information (HA 2025.7+)
        power_consumption = self.coordinator.data.get("actual_power_consumption")
        if power_consumption is not None:
            attributes["power_consumption"] = f"{power_consumption} W"
            
            # Power efficiency
            if intensity is not None and intensity > 0:
                efficiency = power_consumption / intensity
                attributes["power_efficiency"] = f"{efficiency:.1f} W/%"
        
        # Operating time information
        operating_hours = self.coordinator.data.get("operating_hours")
        if operating_hours is not None:
            attributes["operating_hours"] = operating_hours
        
        # Filter status
        filter_remaining = self.coordinator.data.get("filter_time_remaining")
        if filter_remaining is not None:
            attributes["filter_days_remaining"] = filter_remaining
            if filter_remaining <= 30:
                attributes["filter_status"] = "replace_soon"
            elif filter_remaining <= 7:
                attributes["filter_status"] = "replace_now"
            else:
                attributes["filter_status"] = "ok"
        
        # Enhanced time remaining for temporary modes (HA 2025.7+)
        if mode == 2:  # Temporary mode
            temp_remaining = self.coordinator.data.get("temporary_time_remaining")
            if temp_remaining is not None:
                attributes["temporary_time_remaining"] = f"{temp_remaining} min"
        
        boost_remaining = self.coordinator.data.get("boost_time_remaining")
        if boost_remaining is not None and boost_remaining > 0:
            attributes["boost_time_remaining"] = f"{boost_remaining} min"
        
        # Add last update timestamp
        if hasattr(self.coordinator, 'last_update_success_time'):
            attributes["last_updated"] = getattr(self.coordinator, 'last_update_success_time', self.coordinator.last_update_success).isoformat()
            
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and 
            "system_on_off" in self.coordinator.data
        )