"""Climate platform for ThesslaGreen Modbus integration."""
from __future__ import annotations

import logging
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OPERATING_MODES, SEASON_MODES
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Check if basic mode control is available
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    if "mode" in holding_regs:
        entities.append(ThesslaGreenClimate(coordinator))
    
    if entities:
        _LOGGER.debug("Adding %d climate entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenClimate(CoordinatorEntity, ClimateEntity):
    """ThesslaGreen climate entity."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the climate entity."""
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
        
        # Supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
        )
        
        # Temperature settings
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_min_temp = 20
        self._attr_max_temp = 45
        self._attr_target_temperature_step = 0.5
        
        # HVAC modes
        self._attr_hvac_modes = [
            HVACMode.AUTO,
            HVACMode.FAN_ONLY,
            HVACMode.OFF,
        ]
        
        # Fan modes (intensity levels)
        self._attr_fan_modes = [
            "10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # Use supply temperature as current temperature
        temp = self.coordinator.data.get("supply_temperature")
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
            # Round to nearest 10%
            rounded_intensity = round(intensity / 10) * 10
            return f"{rounded_intensity}%"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Operating mode
        mode = self.coordinator.data.get("mode")
        if mode is not None:
            attributes["operating_mode"] = OPERATING_MODES.get(mode, "Unknown")
        
        # Season mode
        season = self.coordinator.data.get("season_mode")
        if season is not None:
            attributes["season_mode"] = SEASON_MODES.get(season, "Unknown")
        
        # Special mode
        special_mode = self.coordinator.data.get("special_mode")
        if special_mode is not None:
            attributes["special_function"] = special_mode
        
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
        
        return attributes

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        # Set temperature for manual mode
        success = await self.coordinator.async_write_register(
            "supply_air_temperature_manual", temperature
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
        try:
            # Extract percentage from fan mode string (e.g., "60%" -> 60)
            intensity = int(fan_mode.rstrip('%'))
            
            # Ensure intensity is within valid range
            intensity = max(10, min(100, intensity))
            
            # Get current mode to determine which register to write
            mode = self.coordinator.data.get("mode", 1)  # Default to manual
            
            if mode == 1:  # Manual mode
                register = "air_flow_rate_manual"
            elif mode == 2:  # Temporary mode
                register = "air_flow_rate_temporary"
            else:
                # For auto mode, switch to manual mode first
                await self.coordinator.async_write_register("mode", 1)
                register = "air_flow_rate_manual"
            
            success = await self.coordinator.async_write_register(register, intensity)
            
            if success:
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to set fan mode")
                
        except ValueError:
            _LOGGER.error("Invalid fan mode format: %s", fan_mode)