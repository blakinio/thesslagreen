"""Enhanced climate platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.climate.const import (
    PRESET_ACTIVITY,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_SLEEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    COMFORT_MODES,
    DOMAIN,
    OPERATING_MODES,
    SPECIAL_MODES,
)
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)

# Enhanced preset modes for ThesslaGreen (HA 2025.7+ Compatible)
THESSLA_PRESET_MODES = {
    PRESET_ECO: {"intensity": 30, "mode": 1},
    PRESET_COMFORT: {"intensity": 50, "mode": 1},
    PRESET_BOOST: {"intensity": 80, "mode": 2},
    PRESET_SLEEP: {"intensity": 20, "mode": 1},
    PRESET_AWAY: {"intensity": 10, "mode": 1},
    PRESET_HOME: {"intensity": 50, "mode": 0},
    PRESET_ACTIVITY: {"intensity": 70, "mode": 0},
    "party": {"intensity": 90, "mode": 2},
    "fireplace": {"intensity": 100, "special": "KOMINEK"},
    "kitchen": {"intensity": 80, "special": "OKAP"},
    "airing": {"intensity": 100, "special": "WIETRZENIE"},
}

ALL_PRESET_MODES = list(THESSLA_PRESET_MODES.keys())


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up enhanced climate platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Check if basic mode control is available
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    if "mode" in holding_regs or "mode_old" in holding_regs:
        entities.append(ThesslaGreenClimate(coordinator))
    
    if entities:
        _LOGGER.debug("Adding %d enhanced climate entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenClimate(CoordinatorEntity, ClimateEntity):
    """Enhanced ThesslaGreen climate entity with preset modes - HA 2025.7+ Compatible."""
    
    _attr_has_entity_name = True  # ✅ FIX: Enable entity naming

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the enhanced climate entity."""
        super().__init__(coordinator)
        
        # Enhanced device info handling
        device_info = coordinator.device_scan_result.get("device_info", {}) if hasattr(coordinator, 'device_scan_result') else {}
        device_name = device_info.get("device_name", f"ThesslaGreen AirPack")
        
        self._attr_name = "Climate Control"
        self._attr_translation_key = "climate"
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.','_')}_{coordinator.slave_id}_climate"
        
        # Enhanced supported features for HA 2025.7+
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.FAN_MODE | 
            ClimateEntityFeature.PRESET_MODE |
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF
        )
        
        # Enhanced HVAC modes
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.FAN_ONLY]
        
        # Enhanced preset modes with custom ThesslaGreen functions
        self._attr_preset_modes = ALL_PRESET_MODES
        
        # Enhanced fan modes based on intensity levels
        self._attr_fan_modes = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%", "Auto"]
        
        # Enhanced temperature settings
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_min_temp = 15.0
        self._attr_max_temp = 45.0
        self._attr_target_temperature_step = 0.5
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": f"ThesslaGreen AirPack ({coordinator.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation mode."""
        # Try both old and new register names
        mode = self.coordinator.data.get("mode")
        if mode is None:
            mode = self.coordinator.data.get("mode_old")
        
        if mode is None:
            return None
        
        # Check if device is on
        device_on = self.coordinator.data.get("device_status_smart", False)
        if not device_on:
            return HVACMode.OFF
        
        # Map ThesslaGreen modes to HVAC modes
        if mode == 0:  # Auto
            return HVACMode.AUTO
        elif mode in [1, 2]:  # Manual, Temporary
            return HVACMode.FAN_ONLY
        else:
            return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # Use exhaust temperature as room temperature indicator
        temp = self.coordinator.data.get("exhaust_temperature")
        if temp is not None:
            return temp  # Already converted in coordinator
        
        # Fallback to extract temperature
        temp = self.coordinator.data.get("extract_temperature")
        if temp is not None:
            return temp
        
        # Fallback to ambient temperature
        temp = self.coordinator.data.get("ambient_temperature")
        if temp is not None:
            return temp
        
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        # Use comfort temperature based on current mode
        comfort_mode = self.coordinator.data.get("comfort_mode", 0)
        
        if comfort_mode == 1:  # Heating
            temp = self.coordinator.data.get("comfort_temperature_heating")
        elif comfort_mode == 2:  # Cooling
            temp = self.coordinator.data.get("comfort_temperature_cooling")
        else:
            # Use supply temperature setpoint
            mode = self.coordinator.data.get("mode", 1)
            if mode == 1:  # Manual
                temp = self.coordinator.data.get("supply_temperature_manual")
            elif mode == 2:  # Temporary
                temp = self.coordinator.data.get("supply_temperature_temporary")
            else:
                temp = self.coordinator.data.get("required_temp")
        
        if temp is not None:
            # Convert from 0.1°C units if needed
            if temp > 100:
                return temp / 10.0
            return float(temp)
        
        return 22.0  # Default

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        mode = self.coordinator.data.get("mode")
        if mode is None:
            mode = self.coordinator.data.get("mode_old")
        
        if mode == 0:  # Auto
            return "Auto"
        
        # Get current intensity based on mode
        if mode == 1:  # Manual
            intensity = self.coordinator.data.get("air_flow_rate_manual")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_1")
        elif mode == 2:  # Temporary
            intensity = self.coordinator.data.get("air_flow_rate_temporary")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_2")
        else:
            intensity = self.coordinator.data.get("air_flow_rate_auto")
            if intensity is None:
                intensity = self.coordinator.data.get("intensity_3")
        
        if intensity is not None:
            # Round to nearest 10%
            rounded = round(intensity / 10) * 10
            return f"{rounded}%"
        
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        # Check special modes first
        special_mode = self.coordinator.data.get("special_mode")
        if special_mode is None:
            special_mode = self.coordinator.data.get("special_mode_old")
        
        if special_mode == 1:
            return "kitchen"
        elif special_mode == 2:
            return "fireplace"
        elif special_mode == 3:
            return "airing"
        
        # Check intensity-based presets
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
                return PRESET_SLEEP
            elif intensity <= 30:
                return PRESET_ECO
            elif intensity <= 50:
                return PRESET_COMFORT
            elif intensity >= 80:
                return PRESET_BOOST
        
        return PRESET_NONE

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        
        # Determine which temperature register to write
        comfort_mode = self.coordinator.data.get("comfort_mode", 0)
        
        if comfort_mode == 1:  # Heating
            register = "comfort_temperature_heating"
        elif comfort_mode == 2:  # Cooling
            register = "comfort_temperature_cooling"
        else:
            # Use supply temperature based on mode
            mode = self.coordinator.data.get("mode", 1)
            if mode == 2:  # Temporary
                register = "supply_temperature_temporary"
            else:  # Manual or Auto
                register = "supply_temperature_manual"
        
        # Convert to device units (0.1°C)
        value = int(temperature * 10)
        
        success = await self.coordinator.async_write_register(register, value)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            # Turn off by setting minimal intensity
            await self.coordinator.async_write_register("air_flow_rate_manual", 0)
            # Or use device on/off if available
            if "on_off_panel_mode" in self.coordinator.available_registers.get("holding_registers", set()):
                await self.coordinator.async_write_register("on_off_panel_mode", 0)
        elif hvac_mode == HVACMode.AUTO:
            await self.coordinator.async_write_register("mode", 0)
            # Ensure device is on
            if "on_off_panel_mode" in self.coordinator.available_registers.get("holding_registers", set()):
                await self.coordinator.async_write_register("on_off_panel_mode", 1)
        elif hvac_mode == HVACMode.FAN_ONLY:
            await self.coordinator.async_write_register("mode", 1)
            # Ensure device is on
            if "on_off_panel_mode" in self.coordinator.available_registers.get("holding_registers", set()):
                await self.coordinator.async_write_register("on_off_panel_mode", 1)
        
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode == "Auto":
            await self.coordinator.async_write_register("mode", 0)
        else:
            # Extract percentage and set intensity
            try:
                intensity = int(fan_mode.rstrip("%"))
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
                
                await self.coordinator.async_write_register(register, intensity)
                await self.coordinator.async_request_refresh()
            except ValueError:
                _LOGGER.error("Invalid fan mode: %s", fan_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in THESSLA_PRESET_MODES:
            _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            return
        
        settings = THESSLA_PRESET_MODES[preset_mode]
        
        # Set special mode if needed
        if "special" in settings:
            special_value = SPECIAL_MODES.get(settings["special"], 0)
            special_reg = "special_mode"
            if special_reg not in self.coordinator.available_registers.get("holding_registers", set()):
                special_reg = "special_mode_old"
            await self.coordinator.async_write_register(special_reg, special_value)
        else:
            # Clear special mode
            special_reg = "special_mode"
            if special_reg not in self.coordinator.available_registers.get("holding_registers", set()):
                special_reg = "special_mode_old"
            await self.coordinator.async_write_register(special_reg, 0)
        
        # Set operating mode
        if "mode" in settings:
            mode_reg = "mode"
            if mode_reg not in self.coordinator.available_registers.get("holding_registers", set()):
                mode_reg = "mode_old"
            await self.coordinator.async_write_register(mode_reg, settings["mode"])
        
        # Set intensity
        if "intensity" in settings:
            mode = settings.get("mode", self.coordinator.data.get("mode", 1))
            
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
            
            await self.coordinator.async_write_register(register, settings["intensity"])
        
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the climate on."""
        # Set to auto mode with default intensity
        await self.coordinator.async_write_register("mode", 0)
        await self.coordinator.async_write_register("air_flow_rate_auto", 50)
        
        # Ensure device is on
        if "on_off_panel_mode" in self.coordinator.available_registers.get("holding_registers", set()):
            await self.coordinator.async_write_register("on_off_panel_mode", 1)
        
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the climate off."""
        # Use device on/off if available
        if "on_off_panel_mode" in self.coordinator.available_registers.get("holding_registers", set()):
            await self.coordinator.async_write_register("on_off_panel_mode", 0)
        else:
            # Set minimal intensity as fallback
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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "last_update": getattr(self.coordinator, 'last_update_success_time', self.coordinator.last_update_success),
        }
        
        # Add all temperature readings
        temp_sensors = [
            ("outside_temperature", "Outside Temperature"),
            ("supply_temperature", "Supply Temperature"),
            ("exhaust_temperature", "Exhaust Temperature"),
            ("fpx_temperature", "FPX Temperature"),
            ("gwc_temperature", "GWC Temperature"),
        ]
        
        for key, name in temp_sensors:
            value = self.coordinator.data.get(key)
            if value is not None:
                attributes[name] = value
        
        # Add flow rates
        supply_flow = self.coordinator.data.get("supply_flowrate")
        if supply_flow is not None:
            attributes["Supply Flow Rate"] = f"{supply_flow} m³/h"
        
        exhaust_flow = self.coordinator.data.get("exhaust_flowrate")
        if exhaust_flow is not None:
            attributes["Exhaust Flow Rate"] = f"{exhaust_flow} m³/h"
        
        # Add fan percentages
        supply_pct = self.coordinator.data.get("supply_percentage")
        if supply_pct is not None:
            attributes["Supply Fan"] = f"{supply_pct}%"
        
        exhaust_pct = self.coordinator.data.get("exhaust_percentage")
        if exhaust_pct is not None:
            attributes["Exhaust Fan"] = f"{exhaust_pct}%"
        
        # Add system status
        attributes["Device Status"] = "ON" if self.coordinator.data.get("device_status_smart") else "OFF"
        
        # Add special function info
        special = self.coordinator.data.get("special_mode", 0)
        if special in SPECIAL_MODES:
            attributes["Special Function"] = SPECIAL_MODES[special]
        
        # Add efficiency if available
        efficiency = self.coordinator.data.get("heat_recovery_efficiency")
        if efficiency is not None:
            attributes["Heat Recovery Efficiency"] = f"{efficiency}%"
        
        # Add filter status
        filter_days = self.coordinator.data.get("filter_time_remaining")
        if filter_days is not None:
            attributes["Filter Days Remaining"] = filter_days
        
        return attributes