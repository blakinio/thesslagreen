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

from .const import DOMAIN
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

# ThesslaGreen preset modes mapping
PRESET_MODE_MAP = {
    PRESET_ECO: {"mode": 0, "intensity": 25, "special": 0},      # Auto mode, low intensity
    PRESET_COMFORT: {"mode": 0, "intensity": 50, "special": 0},  # Auto mode, medium intensity  
    PRESET_BOOST: {"mode": 1, "intensity": 100, "special": 0},   # Manual mode, high intensity
    PRESET_SLEEP: {"mode": 1, "intensity": 15, "special": 0},    # Manual mode, very low intensity
    PRESET_AWAY: {"mode": 1, "intensity": 20, "special": 11},    # Manual mode, low intensity, empty house
}

# Custom preset modes specific to ThesslaGreen
CUSTOM_PRESETS = {
    "okap": {"mode": 1, "special": 1, "name": "OKAP"},           # Hood mode
    "kominek": {"mode": 1, "special": 2, "name": "KOMINEK"},     # Fireplace mode  
    "wietrzenie": {"mode": 1, "special": 7, "name": "WIETRZENIE"}, # Airing mode
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
    """Enhanced ThesslaGreen climate entity with preset modes."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the enhanced climate entity."""
        super().__init__(coordinator)
        
        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        
        self._attr_name = f"{device_name} Rekuperator"
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_climate"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen", 
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }
        
        # Enhanced supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        
        # Temperature settings
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_min_temp = 5
        self._attr_max_temp = 45
        self._attr_target_temperature_step = 0.5
        
        # HVAC modes
        self._attr_hvac_modes = [
            HVACMode.AUTO,
            HVACMode.FAN_ONLY,
            HVACMode.OFF,
        ]
        
        # Enhanced fan modes (intensity levels)
        self._attr_fan_modes = [
            "10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%", "Boost"
        ]
        
        # Preset modes
        self._attr_preset_modes = ALL_PRESET_MODES

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # Use supply temperature as current temperature
        temp = self.coordinator.data.get("supply_temperature")
        if temp is not None:
            return temp
        
        # Fallback to outside temperature
        temp = self.coordinator.data.get("outside_temperature")
        return temp if temp is not None else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        # Try comfort mode temperature first, then manual mode
        target = self.coordinator.data.get("required_temp")
        if target is not None:
            return target
        
        # Fallback to manual mode temperature
        manual_temp = self.coordinator.data.get("supply_air_temperature_manual")
        return manual_temp if manual_temp is not None else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        # Check if device is on
        device_on = self.coordinator.data.get("on_off_panel_mode", 1)
        if not device_on:
            return HVACMode.OFF
            
        mode = self.coordinator.data.get("mode", 0)
        return HVAC_MODE_MAP.get(mode, HVACMode.AUTO)

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        # Get current intensity based on mode
        mode = self.coordinator.data.get("mode", 0)
        
        if mode == 0:  # Auto mode - get current percentage
            intensity = self.coordinator.data.get("supply_percentage")
        elif mode == 1:  # Manual mode
            intensity = self.coordinator.data.get("air_flow_rate_manual")
        elif mode == 2:  # Temporary mode
            intensity = self.coordinator.data.get("air_flow_rate_temporary")
        else:
            intensity = None
            
        if intensity is not None:
            # Special handling for boost mode
            if intensity >= 100:
                return "Boost"
            # Round to nearest 10%
            rounded_intensity = round(intensity / 10) * 10
            return f"{rounded_intensity}%"
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        special_mode = self.coordinator.data.get("special_mode", 0)
        current_mode = self.coordinator.data.get("mode", 0)
        intensity = self.coordinator.data.get("air_flow_rate_manual", 50)
        
        # Check for custom presets first (based on special function)
        for preset_name, config in CUSTOM_PRESETS.items():
            if special_mode == config.get("special", 0) and special_mode != 0:
                return preset_name
        
        # Check for standard presets (based on mode and intensity)
        if current_mode == 0:  # Auto mode
            if intensity <= 30:
                return PRESET_ECO
            elif intensity >= 70:
                return PRESET_BOOST
            else:
                return PRESET_COMFORT
        elif current_mode == 1:  # Manual mode
            if intensity <= 20:
                if special_mode == 11:  # Empty house
                    return PRESET_AWAY
                else:
                    return PRESET_SLEEP
            elif intensity >= 90:
                return PRESET_BOOST
            elif intensity <= 30:
                return PRESET_ECO
            else:
                return PRESET_COMFORT
        
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        # Set temperature for manual mode (convert to register format)
        temp_register_value = int(temperature * 2)  # Assuming 0.5°C resolution
        success = await self.coordinator.async_write_register(
            "supply_air_temperature_manual", temp_register_value
        )
        
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set target temperature")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if hvac_mode == HVACMode.OFF:
            # Turn off device
            success = await self.coordinator.async_write_register("on_off_panel_mode", 0)
        else:
            # Turn on device if off and set mode
            device_on = self.coordinator.data.get("on_off_panel_mode", 1)
            if not device_on:
                await self.coordinator.async_write_register("on_off_panel_mode", 1)
            
            mode_value = HVAC_MODE_REVERSE_MAP.get(hvac_mode, 0)
            success = await self.coordinator.async_write_register("mode", mode_value)
        
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set HVAC mode")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode (intensity)."""
        if fan_mode == "Boost":
            intensity = 150  # Maximum boost
        else:
            try:
                # Extract percentage from fan mode string (e.g., "60%" -> 60)
                intensity = int(fan_mode.rstrip('%'))
            except ValueError:
                _LOGGER.error("Invalid fan mode format: %s", fan_mode)
                return
            
        # Ensure intensity is within valid range
        intensity = max(10, min(150, intensity))
        
        # Set manual mode first
        await self.coordinator.async_write_register("mode", 1)
        
        # Set air flow rate
        success = await self.coordinator.async_write_register("air_flow_rate_manual", intensity)
        
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set fan mode")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("Setting preset mode: %s", preset_mode)
        
        # First clear any active special functions
        await self.coordinator.async_write_register("special_mode", 0)
        
        # Check if it's a custom preset
        if preset_mode in CUSTOM_PRESETS:
            preset_config = CUSTOM_PRESETS[preset_mode]
            
            # Set mode
            await self.coordinator.async_write_register("mode", preset_config["mode"])
            
            # Set special function
            if "special" in preset_config:
                await self.coordinator.async_write_register("special_mode", preset_config["special"])
                
        elif preset_mode in PRESET_MODE_MAP:
            # Standard preset
            preset_config = PRESET_MODE_MAP[preset_mode]
            
            # Set mode
            await self.coordinator.async_write_register("mode", preset_config["mode"])
            
            # Set intensity
            await self.coordinator.async_write_register("air_flow_rate_manual", preset_config["intensity"])
            
            # Set special function if specified
            if preset_config["special"] != 0:
                await self.coordinator.async_write_register("special_mode", preset_config["special"])
        
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the climate device."""
        success = await self.coordinator.async_write_register("on_off_panel_mode", 1)
        if success:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the climate device."""
        success = await self.coordinator.async_write_register("on_off_panel_mode", 0)
        if success:
            await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add current device status
        device_on = self.coordinator.data.get("on_off_panel_mode")
        if device_on is not None:
            attributes["device_power"] = "On" if device_on else "Off"
        
        # Add current mode details
        mode = self.coordinator.data.get("mode")
        if mode is not None:
            mode_names = {0: "Auto", 1: "Manual", 2: "Temporary"}
            attributes["operating_mode"] = mode_names.get(mode, "Unknown")
        
        # Add special function status
        special_mode = self.coordinator.data.get("special_mode")
        if special_mode is not None and special_mode != 0:
            special_names = {
                1: "Hood", 2: "Fireplace", 7: "Airing Manual", 
                8: "Airing Auto", 11: "Empty House", 12: "Open Windows"
            }
            attributes["special_function"] = special_names.get(special_mode, f"Special {special_mode}")
        
        # Add temperature readings
        outside_temp = self.coordinator.data.get("outside_temperature")
        if outside_temp is not None:
            attributes["outside_temperature"] = outside_temp
            
        exhaust_temp = self.coordinator.data.get("exhaust_temperature")
        if exhaust_temp is not None:
            attributes["exhaust_temperature"] = exhaust_temp
        
        # Add flow rates
        supply_flow = self.coordinator.data.get("supply_flowrate")
        if supply_flow is not None:
            attributes["supply_airflow"] = f"{supply_flow} m³/h"
            
        exhaust_flow = self.coordinator.data.get("exhaust_flowrate")
        if exhaust_flow is not None:
            attributes["exhaust_airflow"] = f"{exhaust_flow} m³/h"
        
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.get("on_off_panel_mode") is not None
        )