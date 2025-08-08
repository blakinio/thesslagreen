"""Enhanced climate platform for ThesslaGreen Modbus integration.
Kompletna jednostka klimatyczna z obsługą wszystkich trybów i funkcji.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)

# Enhanced HVAC modes mapping
HVAC_MODE_MAP = {
    0: HVACMode.OFF,          # System off
    1: HVACMode.FAN_ONLY,     # Manual mode - fan only
    2: HVACMode.AUTO,         # Auto mode - intelligent control
    3: HVACMode.HEAT_COOL,    # Temporary mode - heating/cooling
}

# Reverse mapping for setting modes
HVAC_MODE_REVERSE_MAP = {v: k for k, v in HVAC_MODE_MAP.items()}

# Enhanced preset modes mapping with all special functions
PRESET_MODE_MAP = {
    0: "none",
    1: "okap",              # OKAP - Kitchen hood mode
    2: "kominek",           # KOMINEK - Fireplace mode  
    3: "wietrzenie",        # WIETRZENIE - Ventilation mode
    4: "pusty_dom",         # PUSTY DOM - Empty house mode
    5: "boost",             # BOOST - Maximum ventilation
    6: "night",             # Night mode
    7: "party",             # Party mode
    8: "vacation",          # Vacation mode
    9: "economy",           # Economy mode
    10: "comfort",          # Comfort mode
    11: "silent",           # Silent mode
}

# Reverse mapping for setting preset modes
PRESET_MODE_REVERSE_MAP = {v: k for k, v in PRESET_MODE_MAP.items()}

# Enhanced HVAC action mapping
HVAC_ACTION_MAP = {
    "heating": HVACAction.HEATING,
    "cooling": HVACAction.COOLING,
    "ventilation": HVACAction.FAN,
    "idle": HVACAction.IDLE,
    "off": HVACAction.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up enhanced climate platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Check if required registers are available
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    input_regs = coordinator.available_registers.get("input_registers", set())
    
    required_registers = {"mode", "supply_temperature"}
    if not any(reg in holding_regs or reg in input_regs for reg in required_registers):
        _LOGGER.warning("Required climate registers not available, skipping climate entity")
        return
    
    entities = [ThesslaGreenClimate(coordinator)]
    
    _LOGGER.info("Adding enhanced climate entity with comprehensive control features")
    async_add_entities(entities)


class ThesslaGreenClimate(CoordinatorEntity, ClimateEntity):
    """Enhanced climate entity for ThesslaGreen AirPack with comprehensive features."""
    
    _attr_has_entity_name = True
    _attr_name = "Climate Control"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 15.0
    _attr_max_temp = 35.0
    _attr_translation_key = "climate"
    
    # Enhanced supported features - wszystkie dostępne funkcje
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.PRESET_MODE |
        ClimateEntityFeature.SWING_MODE |
        ClimateEntityFeature.AUX_HEAT |
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the enhanced climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.', '_')}_{coordinator.slave_id}_climate"
        self._attr_device_info = coordinator.device_info
        
        # Determine available capabilities based on scanned registers
        self._available_holding = coordinator.available_registers.get("holding_registers", set())
        self._available_input = coordinator.available_registers.get("input_registers", set())
        self._available_coil = coordinator.available_registers.get("coil_registers", set())
        
        # Enhanced HVAC modes based on available registers
        self._hvac_modes = [HVACMode.OFF]
        if "mode" in self._available_holding:
            self._hvac_modes.extend([HVACMode.FAN_ONLY, HVACMode.AUTO])
        if any(reg in self._available_holding for reg in ["heating_temperature", "cooling_temperature"]):
            self._hvac_modes.append(HVACMode.HEAT_COOL)
        
        # Enhanced preset modes based on available special mode registers
        self._preset_modes = ["none"]
        if "special_mode" in self._available_holding:
            available_presets = []
            if "okap_intensity" in self._available_holding:
                available_presets.append("okap")
            if "kominek_intensity" in self._available_holding:
                available_presets.append("kominek")
            if "wietrzenie_intensity" in self._available_holding:
                available_presets.append("wietrzenie")
            if "pusty_dom_intensity" in self._available_holding:
                available_presets.append("pusty_dom")
            if "boost_intensity" in self._available_holding:
                available_presets.append("boost")
            if "night_mode_intensity" in self._available_holding:
                available_presets.append("night")
            if "party_mode_intensity" in self._available_holding:
                available_presets.append("party")
            if "vacation_mode_intensity" in self._available_holding:
                available_presets.append("vacation")
            
            self._preset_modes.extend(available_presets)
        
        # Enhanced fan modes based on available intensity controls
        self._fan_modes = []
        if "air_flow_rate_manual" in self._available_holding:
            self._fan_modes.extend(["low", "medium", "high", "auto"])
        if "supply_fan_speed" in self._available_holding:
            self._fan_modes.append("custom")
        
        # Enhanced swing modes for bypass control
        self._swing_modes = []
        if "bypass_mode" in self._available_holding:
            self._swing_modes.extend(["auto", "on", "off"])
        
        _LOGGER.debug(
            "Climate entity initialized with modes: HVAC=%s, Preset=%s, Fan=%s, Swing=%s",
            self._hvac_modes, self._preset_modes, self._fan_modes, self._swing_modes
        )

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return available HVAC modes."""
        return self._hvac_modes

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        return self._preset_modes

    @property
    def fan_modes(self) -> list[str]:
        """Return available fan modes."""
        return self._fan_modes

    @property
    def swing_modes(self) -> list[str]:
        """Return available swing modes."""
        return self._swing_modes

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if not self.coordinator.data:
            return HVACMode.OFF
        
        # Check system power state first
        power_on = self.coordinator.data.get("on_off_panel_mode", 0)
        if not power_on:
            return HVACMode.OFF
        
        # Get current mode
        current_mode = self.coordinator.data.get("mode", 0)
        return HVAC_MODE_MAP.get(current_mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if not self.coordinator.data:
            return HVACAction.OFF
        
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        
        # Determine action based on system state
        heating_active = self.coordinator.data.get("heating_control", False)
        cooling_active = self.coordinator.data.get("cooling_control", False)
        fan_active = self.coordinator.data.get("power_supply_fans", False)
        
        if heating_active:
            return HVACAction.HEATING
        elif cooling_active:
            return HVACAction.COOLING
        elif fan_active:
            return HVACAction.FAN
        else:
            return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature from supply air sensor."""
        if not self.coordinator.data:
            return None
        
        # Try multiple temperature sources in order of preference
        temp_sources = [
            "supply_temperature",      # TN1 - Primary supply temperature
            "duct_supply_temperature", # TN2 - Duct supply temperature  
            "ambient_temperature",     # TO - Ambient temperature
            "outside_temperature",     # TZ1 - Outside temperature (fallback)
        ]
        
        for source in temp_sources:
            temp = self.coordinator.data.get(source)
            if temp is not None:
                return float(temp)
        
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature based on current mode."""
        if not self.coordinator.data:
            return None
        
        # Get target temperature based on current mode
        current_mode = self.coordinator.data.get("mode", 0)
        
        if current_mode == 1:  # Manual mode
            temp = self.coordinator.data.get("supply_temperature_manual")
        elif current_mode == 2:  # Auto mode  
            temp = self.coordinator.data.get("supply_temperature_auto")
        elif current_mode == 3:  # Temporary mode
            temp = self.coordinator.data.get("supply_temperature_temporary")
        else:
            # Fallback to comfort temperature
            temp = self.coordinator.data.get("comfort_temperature")
        
        if temp is not None:
            return float(temp)
        
        # Final fallback to required temperature
        required_temp = self.coordinator.data.get("required_temp")
        return float(required_temp) if required_temp is not None else None

    @property
    def preset_mode(self) -> str:
        """Return current preset mode."""
        if not self.coordinator.data:
            return "none"
        
        special_mode = self.coordinator.data.get("special_mode", 0)
        return PRESET_MODE_MAP.get(special_mode, "none")

    @property
    def fan_mode(self) -> str:
        """Return current fan mode."""
        if not self.coordinator.data:
            return "auto"
        
        # Determine fan mode based on current system state
        current_mode = self.coordinator.data.get("mode", 0)
        
        if current_mode == 2:  # Auto mode
            return "auto"
        
        # Check manual intensity setting
        manual_intensity = self.coordinator.data.get("air_flow_rate_manual", 50)
        if manual_intensity <= 30:
            return "low"
        elif manual_intensity <= 70:
            return "medium"
        elif manual_intensity <= 100:
            return "high"
        else:
            return "custom"

    @property
    def swing_mode(self) -> str:
        """Return current swing mode (bypass control)."""
        if not self.coordinator.data:
            return "auto"
        
        bypass_mode = self.coordinator.data.get("bypass_mode", 0)
        swing_modes = {0: "auto", 1: "on", 2: "off"}
        return swing_modes.get(bypass_mode, "auto")

    @property
    def is_aux_heat(self) -> bool:
        """Return if auxiliary heating is active."""
        if not self.coordinator.data:
            return False
        
        # Check if heating systems are active
        heating_cable = self.coordinator.data.get("heating_cable", False)
        duct_heater = self.coordinator.data.get("duct_water_heater_pump", False)
        
        return bool(heating_cable or duct_heater)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return enhanced state attributes."""
        if not self.coordinator.data:
            return {}
        
        attrs = {}
        
        # Temperature readings
        temps = {}
        temp_sensors = [
            ("outside", "outside_temperature"),
            ("supply", "supply_temperature"), 
            ("exhaust", "exhaust_temperature"),
            ("fpx", "fpx_temperature"),
            ("duct_supply", "duct_supply_temperature"),
            ("gwc", "gwc_temperature"),
            ("ambient", "ambient_temperature"),
        ]
        
        for name, key in temp_sensors:
            temp = self.coordinator.data.get(key)
            if temp is not None:
                temps[f"{name}_temperature"] = temp
        
        if temps:
            attrs.update(temps)
        
        # Flow rates and efficiency
        flow_data = {}
        flow_sensors = [
            ("supply_flow", "supply_flowrate"),
            ("exhaust_flow", "exhaust_flowrate"),
            ("actual_flow", "actual_flowrate"),
            ("supply_percentage", "supply_percentage"),
            ("exhaust_percentage", "exhaust_percentage"),
            ("efficiency", "heat_recovery_efficiency"),
        ]
        
        for name, key in flow_sensors:
            value = self.coordinator.data.get(key)
            if value is not None:
                flow_data[name] = value
        
        if flow_data:
            attrs.update(flow_data)
        
        # System status
        status_data = {}
        status_keys = [
            ("season_mode", "season_mode"),
            ("bypass_active", "bypass"),
            ("gwc_active", "gwc"),
            ("filter_remaining", "filter_time_remaining"),
            ("operating_hours", "operating_hours"),
        ]
        
        for name, key in status_keys:
            value = self.coordinator.data.get(key)
            if value is not None:
                status_data[name] = value
        
        if status_data:
            attrs.update(status_data)
        
        # Error status
        error_status = self.coordinator.data.get("error_status", 0)
        alarm_status = self.coordinator.data.get("alarm_status", 0)
        if error_status or alarm_status:
            attrs["error_status"] = bool(error_status)
            attrs["alarm_status"] = bool(alarm_status)
        
        # Performance metrics
        perf_stats = self.coordinator.performance_stats
        attrs["update_success_rate"] = f"{perf_stats.get('success_rate', 0):.1f}%"
        attrs["last_update_duration"] = f"{perf_stats.get('last_update_duration', 0):.3f}s"
        
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode not in self._hvac_modes:
            _LOGGER.warning("HVAC mode %s not supported", hvac_mode)
            return
        
        if hvac_mode == HVACMode.OFF:
            # Turn off system
            success = await self.coordinator.async_write_register("on_off_panel_mode", 0)
        else:
            # Turn on system first if needed
            await self.coordinator.async_write_register("on_off_panel_mode", 1)
            
            # Set operation mode
            mode_value = HVAC_MODE_REVERSE_MAP.get(hvac_mode, 0)
            success = await self.coordinator.async_write_register("mode", mode_value)
        
        if success:
            _LOGGER.info("Set HVAC mode to %s", hvac_mode)
        else:
            _LOGGER.error("Failed to set HVAC mode to %s", hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        # Validate temperature range
        if not (self.min_temp <= temperature <= self.max_temp):
            _LOGGER.warning("Temperature %s outside valid range %s-%s", 
                          temperature, self.min_temp, self.max_temp)
            return
        
        # Set temperature based on current mode
        current_mode = self.coordinator.data.get("mode", 0) if self.coordinator.data else 0
        
        # Convert temperature to register format (usually *2 for 0.5°C resolution)
        temp_value = int(temperature * 2)
        
        success = False
        if current_mode == 1:  # Manual mode
            success = await self.coordinator.async_write_register("supply_temperature_manual", temp_value)
        elif current_mode == 2:  # Auto mode
            success = await self.coordinator.async_write_register("supply_temperature_auto", temp_value)
        elif current_mode == 3:  # Temporary mode
            success = await self.coordinator.async_write_register("supply_temperature_temporary", temp_value)
        else:
            # Fallback to comfort temperature
            success = await self.coordinator.async_write_register("comfort_temperature", temp_value)
        
        if success:
            _LOGGER.info("Set target temperature to %s°C", temperature)
        else:
            _LOGGER.error("Failed to set target temperature to %s°C", temperature)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if preset_mode not in self._preset_modes:
            _LOGGER.warning("Preset mode %s not supported", preset_mode)
            return
        
        preset_value = PRESET_MODE_REVERSE_MAP.get(preset_mode, 0)
        success = await self.coordinator.async_write_register("special_mode", preset_value)
        
        if success:
            _LOGGER.info("Set preset mode to %s", preset_mode)
        else:
            _LOGGER.error("Failed to set preset mode to %s", preset_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        if fan_mode not in self._fan_modes:
            _LOGGER.warning("Fan mode %s not supported", fan_mode)
            return
        
        # Map fan mode to intensity percentage
        fan_intensities = {
            "low": 30,
            "medium": 60, 
            "high": 90,
            "auto": 0,  # Auto mode handled separately
            "custom": 100,
        }
        
        if fan_mode == "auto":
            # Switch to auto mode
            success = await self.coordinator.async_write_register("mode", 2)
        else:
            # Set manual mode with specific intensity
            await self.coordinator.async_write_register("mode", 1)
            intensity = fan_intensities.get(fan_mode, 60)
            success = await self.coordinator.async_write_register("air_flow_rate_manual", intensity)
        
        if success:
            _LOGGER.info("Set fan mode to %s", fan_mode)
        else:
            _LOGGER.error("Failed to set fan mode to %s", fan_mode)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode (bypass control)."""
        if swing_mode not in self._swing_modes:
            _LOGGER.warning("Swing mode %s not supported", swing_mode)
            return
        
        # Map swing mode to bypass control
        bypass_modes = {"auto": 0, "on": 1, "off": 2}
        bypass_value = bypass_modes.get(swing_mode, 0)
        
        success = await self.coordinator.async_write_register("bypass_mode", bypass_value)
        
        if success:
            _LOGGER.info("Set swing mode (bypass) to %s", swing_mode)
        else:
            _LOGGER.error("Failed to set swing mode (bypass) to %s", swing_mode)

    async def async_turn_aux_heat_on(self) -> None:
        """Turn auxiliary heating on."""
        success = await self.coordinator.async_write_register("heating_control", True)
        
        if success:
            _LOGGER.info("Turned auxiliary heating on")
        else:
            _LOGGER.error("Failed to turn auxiliary heating on")

    async def async_turn_aux_heat_off(self) -> None:
        """Turn auxiliary heating off."""
        success = await self.coordinator.async_write_register("heating_control", False)
        
        if success:
            _LOGGER.info("Turned auxiliary heating off")
        else:
            _LOGGER.error("Failed to turn auxiliary heating off")

    async def async_turn_on(self) -> None:
        """Turn the climate entity on."""
        success = await self.coordinator.async_write_register("on_off_panel_mode", 1)
        
        if success:
            _LOGGER.info("Turned climate control on")
        else:
            _LOGGER.error("Failed to turn climate control on")

    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        success = await self.coordinator.async_write_register("on_off_panel_mode", 0)
        
        if success:
            _LOGGER.info("Turned climate control off")
        else:
            _LOGGER.error("Failed to turn climate control off")

    @property
    def available(self) -> bool:
        """Return if climate control is available."""
        if not self.coordinator.last_update_success:
            return False
        
        # Check if critical registers are available
        required_regs = ["mode", "on_off_panel_mode"]
        available_regs = (
            self.coordinator.available_registers.get("holding_registers", set()) |
            self.coordinator.available_registers.get("input_registers", set())
        )
        
        return any(reg in available_regs for reg in required_regs)