"""Climate platform for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HOLDING_REGISTERS
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Preset modes mapping
PRESET_MAPPING = {
    "comfort": "Comfort",
    "eco": "Eco", 
    "boost": "Boost",
    "sleep": "Sleep",
    "away": "Away",
    "fireplace": "Fireplace",
    "party": "Party",
    "vacation": "Vacation",
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen climate from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Check if climate control is available
    climate_registers = [
        "mode", "supply_temperature_manual", "supply_temperature_auto",
        "heating_temperature", "cooling_temperature", "comfort_temperature"
    ]
    
    has_climate_registers = False
    for register in climate_registers:
        for reg_type, registers in coordinator.available_registers.items():
            if register in registers:
                has_climate_registers = True
                break
        if has_climate_registers:
            break
    
    # If force full register list, assume climate is available
    if not has_climate_registers and coordinator.force_full_register_list:
        has_climate_registers = any(register in HOLDING_REGISTERS for register in climate_registers)
    
    if has_climate_registers:
        async_add_entities([ThesslaGreenClimate(coordinator)])
        _LOGGER.info("Added climate entity")
    else:
        _LOGGER.debug("No climate registers available - skipping climate entity")


class ThesslaGreenClimate(CoordinatorEntity, ClimateEntity):
    """ThesslaGreen climate entity."""
    
    def __init__(self, coordinator: ThesslaGreenModbusCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        
        # Entity configuration
        self._attr_name = f"{coordinator.device_name} Climate"
        self._attr_unique_id = f"{coordinator.device_name}_climate"
        self._attr_device_info = coordinator.get_device_info()
        
        # Climate configuration
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = 0.5
        self._attr_min_temp = 15.0
        self._attr_max_temp = 30.0
        self._attr_target_temperature_step = 0.5
        
        # HVAC modes
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL, HVACMode.FAN_ONLY]
        
        # Features
        features = ClimateEntityFeature.TARGET_TEMPERATURE
        
        # Check what features are available based on capabilities
        if coordinator.capabilities.has_heating:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        
        if coordinator.capabilities.has_scheduling:
            features |= ClimateEntityFeature.PRESET_MODE
        
        if any(reg in coordinator.available_registers.get("holding", {}) 
               for reg in ["air_flow_rate_manual", "air_flow_rate_auto"]):
            features |= ClimateEntityFeature.FAN_MODE
        
        self._attr_supported_features = features
        
        # Preset modes
        self._attr_preset_modes = list(PRESET_MAPPING.values())
        
        # Fan modes
        self._attr_fan_modes = ["Auto", "Low", "Medium", "High", "Max"]
        
        _LOGGER.debug("Initialized climate entity with features: %s", features)
    
    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # Use supply temperature as current temperature
        temp_registers = ["supply_temperature", "ambient_temperature"]
        
        for register in temp_registers:
            if register in self.coordinator.data:
                temp = self.coordinator.data[register]
                if temp is not None and isinstance(temp, (int, float)):
                    return round(float(temp), 1)
        
        return None
    
    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        # Get target temperature based on current mode
        current_mode = self._get_current_mode()
        
        if current_mode == "manual":
            temp_register = "supply_temperature_manual"
        elif current_mode == "auto":
            temp_register = "supply_temperature_auto"
        else:
            temp_register = "comfort_temperature"
        
        if temp_register in self.coordinator.data:
            temp = self.coordinator.data[temp_register]
            if temp is not None and isinstance(temp, (int, float)):
                return round(float(temp), 1)
        
        # Fallback to comfort temperature
        if "comfort_temperature" in self.coordinator.data:
            temp = self.coordinator.data["comfort_temperature"]
            if temp is not None and isinstance(temp, (int, float)):
                return round(float(temp), 1)
        
        return 22.0  # Default temperature
    
    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        # Check if system is on
        if "on_off_panel_mode" in self.coordinator.data:
            if not self.coordinator.data["on_off_panel_mode"]:
                return HVACMode.OFF
        
        # Determine mode based on system state
        current_mode = self._get_current_mode()
        
        if current_mode == "auto":
            # Check if heating or cooling is active
            if "heating_active" in self.coordinator.data and self.coordinator.data["heating_active"]:
                return HVACMode.HEAT
            elif "cooling_active_status" in self.coordinator.data and self.coordinator.data["cooling_active_status"]:
                return HVACMode.COOL
            else:
                return HVACMode.AUTO
        elif current_mode == "manual":
            return HVACMode.FAN_ONLY
        
        return HVACMode.AUTO
    
    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        # Check system state
        if "heating_active" in self.coordinator.data and self.coordinator.data["heating_active"]:
            return HVACAction.HEATING
        elif "cooling_active_status" in self.coordinator.data and self.coordinator.data["cooling_active_status"]:
            return HVACAction.COOLING
        elif "air_flow_rate" in self.coordinator.data and self.coordinator.data["air_flow_rate"] > 0:
            return HVACAction.FAN
        elif self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        else:
            return HVACAction.IDLE
    
    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        # Check special modes
        if "special_mode" in self.coordinator.data:
            special_mode = self.coordinator.data["special_mode"]
            if special_mode == 1:
                return PRESET_MAPPING["fireplace"]
            elif special_mode == 2:
                return PRESET_MAPPING["party"]
            elif special_mode == 3:
                return PRESET_MAPPING["vacation"]
        
        # Check individual mode flags
        if "boost_mode" in self.coordinator.data and self.coordinator.data["boost_mode"]:
            return PRESET_MAPPING["boost"]
        elif "eco_mode" in self.coordinator.data and self.coordinator.data["eco_mode"]:
            return PRESET_MAPPING["eco"]
        elif "night_mode" in self.coordinator.data and self.coordinator.data["night_mode"]:
            return PRESET_MAPPING["sleep"]
        
        return PRESET_MAPPING["comfort"]  # Default
    
    @property
    def fan_mode(self) -> str | None:
        """Return current fan mode."""
        if "air_flow_rate" in self.coordinator.data:
            flow_rate = self.coordinator.data["air_flow_rate"]
            if isinstance(flow_rate, (int, float)):
                if flow_rate <= 20:
                    return "Low"
                elif flow_rate <= 40:
                    return "Medium"
                elif flow_rate <= 70:
                    return "High"
                elif flow_rate <= 100:
                    return "Max"
        
        return "Auto"
    
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        # Determine which register to write based on current mode
        current_mode = self._get_current_mode()
        
        if current_mode == "manual":
            register_name = "supply_temperature_manual"
        elif current_mode == "auto":
            register_name = "supply_temperature_auto"
        else:
            register_name = "comfort_temperature"
        
        try:
            await self._write_register(register_name, temperature, scale=2)  # Scale by 2 for 0.5°C resolution
            _LOGGER.info("Set target temperature to %.1f°C (register: %s)", temperature, register_name)
        except Exception as exc:
            _LOGGER.error("Failed to set temperature: %s", exc)
    
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        try:
            if hvac_mode == HVACMode.OFF:
                await self._write_register("on_off_panel_mode", 0)
            elif hvac_mode == HVACMode.AUTO:
                await self._write_register("on_off_panel_mode", 1)
                await self._write_register("mode", 0)  # Auto mode
            elif hvac_mode == HVACMode.FAN_ONLY:
                await self._write_register("on_off_panel_mode", 1)
                await self._write_register("mode", 1)  # Manual mode
            elif hvac_mode in [HVACMode.HEAT, HVACMode.COOL]:
                await self._write_register("on_off_panel_mode", 1)
                await self._write_register("mode", 0)  # Auto mode with heating/cooling
            
            _LOGGER.info("Set HVAC mode to %s", hvac_mode)
        except Exception as exc:
            _LOGGER.error("Failed to set HVAC mode: %s", exc)
    
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        try:
            # Reset all special modes first
            special_mode_registers = [
                "boost_mode", "eco_mode", "night_mode", "party_mode", 
                "fireplace_mode", "vacation_mode"
            ]
            
            for register in special_mode_registers:
                if register in HOLDING_REGISTERS:
                    await self._write_register(register, 0)
            
            # Set new mode
            if preset_mode == PRESET_MAPPING["boost"]:
                await self._write_register("boost_mode", 1)
            elif preset_mode == PRESET_MAPPING["eco"]:
                await self._write_register("eco_mode", 1)
            elif preset_mode == PRESET_MAPPING["sleep"]:
                await self._write_register("night_mode", 1)
            elif preset_mode == PRESET_MAPPING["fireplace"]:
                await self._write_register("fireplace_mode", 1)
            elif preset_mode == PRESET_MAPPING["party"]:
                await self._write_register("party_mode", 1)
            elif preset_mode == PRESET_MAPPING["vacation"]:
                await self._write_register("vacation_mode", 1)
            # Comfort mode is default (all others off)
            
            _LOGGER.info("Set preset mode to %s", preset_mode)
        except Exception as exc:
            _LOGGER.error("Failed to set preset mode: %s", exc)
    
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        try:
            # Map fan mode to flow rate percentage
            flow_rate_map = {
                "Low": 25,
                "Medium": 50,
                "High": 75,
                "Max": 100,
                "Auto": None  # Keep current auto setting
            }
            
            if fan_mode == "Auto":
                await self._write_register("mode", 0)  # Auto mode
            else:
                flow_rate = flow_rate_map.get(fan_mode, 50)
                await self._write_register("mode", 1)  # Manual mode
                await self._write_register("air_flow_rate_manual", flow_rate)
            
            _LOGGER.info("Set fan mode to %s", fan_mode)
        except Exception as exc:
            _LOGGER.error("Failed to set fan mode: %s", exc)
    
    def _get_current_mode(self) -> str:
        """Get current system mode."""
        if "mode" in self.coordinator.data:
            mode_value = self.coordinator.data["mode"]
            if mode_value == 0:
                return "auto"
            elif mode_value == 1:
                return "manual"
            elif mode_value == 2:
                return "temporary"
        return "auto"  # Default
    
    async def _write_register(self, register_name: str, value: Any, scale: float = 1) -> None:
        """Write value to register."""
        if register_name not in HOLDING_REGISTERS:
            raise ValueError(f"Register {register_name} is not writable")
        
        register_address = HOLDING_REGISTERS[register_name]
        scaled_value = int(value * scale)
        
        # Ensure client is connected
        if not self.coordinator.client or not self.coordinator.client.connected:
            if not await self.coordinator._async_setup_client():
                raise RuntimeError("Failed to connect to device")
        
        # Write register - pymodbus 3.5+ compatible
        response = await self.coordinator.client.write_register(
            address=register_address, 
            value=scaled_value, 
            slave=self.coordinator.slave_id
        )
        
        if response.isError():
            raise RuntimeError(f"Failed to write register {register_name}: {response}")
        
        # Request immediate data update
        await self.coordinator.async_request_refresh()
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add system information
        if "outside_temperature" in self.coordinator.data:
            attributes["outside_temperature"] = self.coordinator.data["outside_temperature"]
        
        if "air_flow_rate" in self.coordinator.data:
            attributes["current_flow_rate"] = self.coordinator.data["air_flow_rate"]
        
        if "supply_flowrate" in self.coordinator.data:
            attributes["supply_flow"] = self.coordinator.data["supply_flowrate"]
        
        if "exhaust_flowrate" in self.coordinator.data:
            attributes["exhaust_flow"] = self.coordinator.data["exhaust_flowrate"]
        
        # Add system status
        system_status = []
        if "heating_active" in self.coordinator.data and self.coordinator.data["heating_active"]:
            system_status.append("heating")
        if "cooling_active_status" in self.coordinator.data and self.coordinator.data["cooling_active_status"]:
            system_status.append("cooling")
        if "bypass" in self.coordinator.data and self.coordinator.data["bypass"]:
            system_status.append("bypass")
        if "gwc" in self.coordinator.data and self.coordinator.data["gwc"]:
            system_status.append("gwc")
        
        if system_status:
            attributes["active_systems"] = system_status
        
        # Add last update time
        if self.coordinator.last_successful_update:
            attributes["last_updated"] = self.coordinator.last_successful_update.isoformat()
        
        return attributes