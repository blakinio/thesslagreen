"""Enhanced climate platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_SLEEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OPERATING_MODES, SEASON_MODES, SPECIAL_MODES
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)

# Enhanced HVAC mode mapping
HVAC_MODE_MAP = {
    0: HVACMode.AUTO,      # Automatyczny
    1: HVACMode.FAN_ONLY,  # Manualny
    2: HVACMode.FAN_ONLY,  # Chwilowy
}

HVAC_MODE_REVERSE_MAP = {
    HVACMode.AUTO: 0,
    HVACMode.FAN_ONLY: 1,
    HVACMode.OFF: 0,  # Map OFF to AUTO for simplicity
}

# ThesslaGreen preset modes mapping (Enhanced HA 2025.7+)
PRESET_MODE_MAP = {
    PRESET_ECO: {"mode": 0, "intensity": 25, "special": 6},      # Auto mode, low intensity, ECO
    PRESET_COMFORT: {"mode": 0, "intensity": 50, "special": 0},  # Auto mode, medium intensity  
    PRESET_BOOST: {"mode": 1, "intensity": 100, "special": 5},   # Manual mode, high intensity, BOOST
    PRESET_SLEEP: {"mode": 1, "intensity": 15, "special": 13},   # Manual mode, very low intensity, Night
    PRESET_AWAY: {"mode": 1, "intensity": 20, "special": 11},    # Manual mode, low intensity, empty house
}

# Enhanced custom preset modes specific to ThesslaGreen (HA 2025.7+)
CUSTOM_PRESETS = {
    "okap": {"mode": 1, "special": 1, "intensity": 80, "name": "OKAP"},           # Hood mode
    "kominek": {"mode": 1, "special": 2, "intensity": 60, "name": "KOMINEK"},     # Fireplace mode  
    "wietrzenie": {"mode": 1, "special": 7, "intensity": 70, "name": "WIETRZENIE"}, # Airing mode
    "gotowanie": {"mode": 1, "special": 8, "intensity": 90, "name": "GOTOWANIE"},  # Cooking mode
    "pranie": {"mode": 1, "special": 9, "intensity": 85, "name": "PRANIE"},       # Laundry mode
    "lazienka": {"mode": 1, "special": 10, "intensity": 75, "name": "ŁAZIENKA"},   # Bathroom mode
}

ALL_PRESET_MODES = [PRESET_ECO, PRESET_COMFORT, PRESET_BOOST, PRESET_SLEEP, PRESET_AWAY] + list(CUSTOM_PRESETS.keys())


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
    if "mode" in holding_regs:
        entities.append(ThesslaGreenClimate(coordinator))
    
    if entities:
        _LOGGER.debug("Adding %d enhanced climate entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenClimate(CoordinatorEntity, ClimateEntity):
    """Enhanced ThesslaGreen climate entity with preset modes - HA 2025.7+ Compatible."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the enhanced climate entity."""
        super().__init__(coordinator)
        
        # Enhanced device info handling
        device_info = coordinator.device_scan_result.get("device_info", {}) if hasattr(coordinator, 'device_scan_result') else {}
        device_name = device_info.get("device_name", f"ThesslaGreen {coordinator.host}")
        
        self._attr_name = f"{device_name} Climate"
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_climate"
        
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
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation mode."""
        system_on = self.coordinator.data.get("system_on_off", True)
        if not system_on:
            return HVACMode.OFF
            
        mode = self.coordinator.data.get("mode")
        if mode is None:
            return None
            
        return HVAC_MODE_MAP.get(mode, HVACMode.AUTO)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # Use supply temperature as current temperature
        return self.coordinator.data.get("supply_temperature")

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        mode = self.coordinator.data.get("mode", 0)
        
        if mode == 1:  # Manual mode
            return self.coordinator.data.get("supply_temperature_manual")
        elif mode == 2:  # Temporary mode
            return self.coordinator.data.get("supply_temperature_temporary")
        else:  # Auto mode - use comfort temperature
            comfort_mode = self.coordinator.data.get("comfort_mode", 0)
            if comfort_mode == 1:  # Heating
                return self.coordinator.data.get("comfort_temperature_heating")
            elif comfort_mode == 2:  # Cooling
                return self.coordinator.data.get("comfort_temperature_cooling")
        
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return current fan mode."""
        intensity = self._get_current_intensity()
        if intensity is None:
            return "Auto"
        
        # Map intensity to fan mode
        if intensity <= 10:
            return "10%"
        elif intensity >= 100:
            return "100%"
        else:
            # Round to nearest 10%
            rounded = int(round(intensity / 10) * 10)
            return f"{rounded}%"

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        # Enhanced preset detection based on system state
        mode = self.coordinator.data.get("mode", 0)
        special_mode = self.coordinator.data.get("special_mode", 0)
        intensity = self._get_current_intensity()
        
        # Check for special function presets first
        if special_mode != 0:
            for preset_key, config in CUSTOM_PRESETS.items():
                if config["special"] == special_mode:
                    return preset_key
            
            # Check standard special modes
            if special_mode == 5:  # BOOST
                return PRESET_BOOST
            elif special_mode == 6:  # ECO
                return PRESET_ECO
            elif special_mode == 11:  # Empty house
                return PRESET_AWAY
            elif special_mode == 13:  # Night
                return PRESET_SLEEP
        
        # Auto mode detection
        if mode == 0:
            if intensity is not None:
                if intensity <= 30:
                    return PRESET_ECO
                elif intensity >= 80:
                    return PRESET_BOOST
                else:
                    return PRESET_COMFORT
            return PRESET_COMFORT
        
        # Manual/Temporary mode - determine by intensity
        if intensity is not None:
            if intensity <= 20:
                return PRESET_SLEEP
            elif intensity <= 35:
                return PRESET_ECO
            elif intensity <= 65:
                return PRESET_COMFORT
            else:
                return PRESET_BOOST
                
        return PRESET_COMFORT

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            success = await self.coordinator.async_write_register("system_on_off", 0)
        else:
            # Ensure system is on
            await self.coordinator.async_write_register("system_on_off", 1)
            
            # Set the appropriate mode
            mode_value = HVAC_MODE_REVERSE_MAP.get(hvac_mode, 0)
            success = await self.coordinator.async_write_register("mode", mode_value)
        
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Set HVAC mode to %s", hvac_mode)
        else:
            _LOGGER.error("Failed to set HVAC mode to %s", hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
            
        # Convert to Modbus value (×2 for 0.5°C resolution)
        temp_value = int(temperature * 2)
        
        # Determine which register to write based on current mode
        mode = self.coordinator.data.get("mode", 0)
        
        if mode == 1:  # Manual mode
            register_key = "supply_temperature_manual"
        elif mode == 2:  # Temporary mode
            register_key = "supply_temperature_temporary"
        else:  # Auto mode - set comfort temperature
            comfort_mode = self.coordinator.data.get("comfort_mode", 1)
            if comfort_mode == 2:  # Cooling mode
                register_key = "comfort_temperature_cooling"
            else:  # Heating mode (default)
                register_key = "comfort_temperature_heating"
        
        success = await self.coordinator.async_write_register(register_key, temp_value)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Set target temperature to %.1f°C", temperature)
        else:
            _LOGGER.error("Failed to set target temperature to %.1f°C", temperature)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode == "Auto":
            # Switch to auto mode
            success = await self.coordinator.async_write_register("mode", 0)
        else:
            # Extract intensity from fan mode (e.g., "60%" -> 60)
            try:
                intensity = int(fan_mode.rstrip('%'))
            except ValueError:
                _LOGGER.error("Invalid fan mode: %s", fan_mode)
                return
            
            # Ensure we're in manual mode for direct fan control
            current_mode = self.coordinator.data.get("mode", 0)
            if current_mode == 0:  # Auto mode - switch to manual
                await self.coordinator.async_write_register("mode", 1)
                register_key = "air_flow_rate_manual"
            elif current_mode == 1:  # Manual mode
                register_key = "air_flow_rate_manual"
            elif current_mode == 2:  # Temporary mode
                register_key = "air_flow_rate_temporary"
            else:
                register_key = "air_flow_rate_manual"
            
            success = await self.coordinator.async_write_register(register_key, intensity)
        
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Set fan mode to %s", fan_mode)
        else:
            _LOGGER.error("Failed to set fan mode to %s", fan_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in ALL_PRESET_MODES:
            _LOGGER.error("Invalid preset mode: %s", preset_mode)
            return
        
        # Enhanced preset mode implementation for HA 2025.7+
        config = None
        
        # Check standard preset modes
        if preset_mode in PRESET_MODE_MAP:
            config = PRESET_MODE_MAP[preset_mode]
        # Check custom ThesslaGreen preset modes
        elif preset_mode in CUSTOM_PRESETS:
            config = CUSTOM_PRESETS[preset_mode]
        
        if not config:
            _LOGGER.error("No configuration found for preset mode: %s", preset_mode)
            return
        
        # Ensure system is on
        system_on = self.coordinator.data.get("system_on_off", True)
        if not system_on:
            await self.coordinator.async_write_register("system_on_off", 1)
        
        # Apply preset configuration
        success = True
        
        # Set operating mode
        success &= await self.coordinator.async_write_register("mode", config["mode"])
        
        # Set special mode
        if "special" in config and config["special"] != 0:
            success &= await self.coordinator.async_write_register("special_mode", config["special"])
        else:
            # Clear special mode if not specified
            success &= await self.coordinator.async_write_register("special_mode", 0)
        
        # Set intensity if specified
        if "intensity" in config:
            if config["mode"] == 0:  # Auto mode
                register_key = "air_flow_rate_auto"
            elif config["mode"] == 1:  # Manual mode
                register_key = "air_flow_rate_manual"
            elif config["mode"] == 2:  # Temporary mode
                register_key = "air_flow_rate_temporary"
            else:
                register_key = "air_flow_rate_manual"
            
            success &= await self.coordinator.async_write_register(register_key, config["intensity"])
        
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Set preset mode to %s", preset_mode)
        else:
            _LOGGER.error("Failed to set preset mode to %s", preset_mode)

    async def async_turn_on(self) -> None:
        """Turn the climate entity on."""
        success = await self.coordinator.async_write_register("system_on_off", 1)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Turned on climate entity")
        else:
            _LOGGER.error("Failed to turn on climate entity")

    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        success = await self.coordinator.async_write_register("system_on_off", 0)
        if success:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Turned off climate entity")
        else:
            _LOGGER.error("Failed to turn off climate entity")

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
            attributes["operating_mode"] = OPERATING_MODES.get(mode, "Unknown")
        
        # Season mode
        season = self.coordinator.data.get("season_mode")
        if season is not None:
            attributes["season_mode"] = SEASON_MODES.get(season, "Unknown")
        
        # Special mode with description
        special_mode = self.coordinator.data.get("special_mode")
        if special_mode is not None:
            attributes["special_function"] = SPECIAL_MODES.get(special_mode, f"Unknown ({special_mode})")
        
        # Comfort mode status
        comfort_mode = self.coordinator.data.get("comfort_mode")
        if comfort_mode is not None:
            comfort_status = ["Nieaktywny", "Grzanie", "Chłodzenie"]
            attributes["comfort_mode"] = comfort_status[comfort_mode] if comfort_mode < len(comfort_status) else "Unknown"
        
        # System statuses  
        if self.coordinator.data.get("constant_flow_active") is not None:
            attributes["constant_flow"] = "Aktywny" if self.coordinator.data["constant_flow_active"] else "Nieaktywny"
        
        gwc_mode = self.coordinator.data.get("gwc_mode")
        if gwc_mode is not None:
            gwc_status = ["Nieaktywny", "Zima", "Lato"]
            attributes["gwc_mode"] = gwc_status[gwc_mode] if gwc_mode < len(gwc_status) else "Unknown"
        
        bypass_mode = self.coordinator.data.get("bypass_mode")
        if bypass_mode is not None:
            bypass_status = ["Nieaktywny", "FreeHeating", "FreeCooling"]
            attributes["bypass_mode"] = bypass_status[bypass_mode] if bypass_mode < len(bypass_status) else "Unknown"
        
        # Flow rates
        supply_flow = self.coordinator.data.get("supply_flowrate")
        if supply_flow is not None:
            attributes["supply_flow"] = f"{supply_flow} m³/h"
            
        exhaust_flow = self.coordinator.data.get("exhaust_flowrate")
        if exhaust_flow is not None:
            attributes["exhaust_flow"] = f"{exhaust_flow} m³/h"
        
        # Enhanced diagnostics (HA 2025.7+)
        attributes["current_intensity"] = self._get_current_intensity()
        attributes["antifreeze_mode"] = self.coordinator.data.get("antifreeze_mode")
        attributes["antifreeze_stage"] = self.coordinator.data.get("antifreeze_stage")
        
        # Temperature context
        outside_temp = self.coordinator.data.get("outside_temperature")
        if outside_temp is not None:
            attributes["outside_temperature"] = outside_temp
            
            supply_temp = self.coordinator.data.get("supply_temperature")
            if supply_temp is not None:
                attributes["temperature_rise"] = round(supply_temp - outside_temp, 1)
        
        # Enhanced system efficiency (HA 2025.7+)
        heat_recovery_eff = self.coordinator.data.get("heat_recovery_efficiency")
        if heat_recovery_eff is not None:
            attributes["heat_recovery_efficiency"] = f"{heat_recovery_eff}%"
        
        # Enhanced power information (HA 2025.7+)
        power_consumption = self.coordinator.data.get("actual_power_consumption")
        if power_consumption is not None:
            attributes["power_consumption"] = f"{power_consumption} W"
        
        # Enhanced filter status (HA 2025.7+)
        filter_remaining = self.coordinator.data.get("filter_time_remaining")
        if filter_remaining is not None:
            attributes["filter_days_remaining"] = filter_remaining
            if filter_remaining <= 7:
                attributes["filter_status"] = "replace_now"
            elif filter_remaining <= 30:
                attributes["filter_status"] = "replace_soon"
            else:
                attributes["filter_status"] = "ok"
        
        # Enhanced time remaining information (HA 2025.7+)
        if mode == 2:  # Temporary mode
            temp_remaining = self.coordinator.data.get("temporary_time_remaining")
            if temp_remaining is not None:
                attributes["temporary_time_remaining"] = f"{temp_remaining} min"
        
        boost_remaining = self.coordinator.data.get("boost_time_remaining")
        if boost_remaining is not None and boost_remaining > 0:
            attributes["boost_time_remaining"] = f"{boost_remaining} min"
        
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and 
            "mode" in self.coordinator.data
        )