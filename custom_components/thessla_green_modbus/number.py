"""Enhanced number platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up enhanced number platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # Enhanced Intensity Control Numbers (HA 2025.7+ Compatible)
    intensity_numbers = [
        ("air_flow_rate_manual", "Manual Intensity", "mdi:fan-speed-1", 10, 150, 1, PERCENTAGE,
         "Air flow intensity in manual mode", NumberMode.SLIDER),
        ("air_flow_rate_temporary", "Temporary Intensity", "mdi:fan-speed-2", 10, 150, 1, PERCENTAGE,
         "Air flow intensity in temporary mode", NumberMode.SLIDER),
        ("air_flow_rate_auto", "Auto Intensity", "mdi:fan-auto", 10, 150, 1, PERCENTAGE,
         "Air flow intensity in automatic mode", NumberMode.SLIDER),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in intensity_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenIntensityNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )
    
    # Enhanced Temperature Control Numbers (HA 2025.7+ Compatible)
    temperature_numbers = [
        ("supply_temperature_manual", "Manual Supply Temperature", "mdi:thermometer-lines", 15.0, 45.0, 0.5, UnitOfTemperature.CELSIUS,
         "Supply air temperature in manual mode", NumberMode.BOX),
        ("supply_temperature_temporary", "Temporary Supply Temperature", "mdi:thermometer-lines", 15.0, 45.0, 0.5, UnitOfTemperature.CELSIUS,
         "Supply air temperature in temporary mode", NumberMode.BOX),
        ("comfort_temperature_heating", "Comfort Heating Temperature", "mdi:thermometer-plus", 18.0, 30.0, 0.5, UnitOfTemperature.CELSIUS,
         "Comfort mode heating target temperature", NumberMode.BOX),
        ("comfort_temperature_cooling", "Comfort Cooling Temperature", "mdi:thermometer-minus", 20.0, 35.0, 0.5, UnitOfTemperature.CELSIUS,
         "Comfort mode cooling target temperature", NumberMode.BOX),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in temperature_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenTemperatureNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )
    
    # Enhanced GWC Control Numbers (HA 2025.7+ Compatible)
    gwc_numbers = [
        ("min_gwc_air_temperature", "GWC Min Air Temperature", "mdi:thermometer-low", -10.0, 10.0, 0.5, UnitOfTemperature.CELSIUS,
         "Minimum air temperature for GWC activation", NumberMode.BOX),
        ("max_gwc_air_temperature", "GWC Max Air Temperature", "mdi:thermometer-high", 20.0, 35.0, 0.5, UnitOfTemperature.CELSIUS,
         "Maximum air temperature for GWC activation", NumberMode.BOX),
        ("delta_t_gwc", "GWC Delta Temperature", "mdi:delta", 2.0, 10.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperature difference threshold for GWC", NumberMode.BOX),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in gwc_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenTemperatureNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )
    
    # Enhanced Bypass Control Numbers (HA 2025.7+ Compatible)
    bypass_numbers = [
        ("min_bypass_temperature", "Bypass Min Temperature", "mdi:valve", 15.0, 25.0, 0.5, UnitOfTemperature.CELSIUS,  
         "Minimum temperature for bypass activation", NumberMode.BOX),
        ("air_temperature_summer_free_heating", "Summer FreeHeating Temperature", "mdi:weather-sunny", 10.0, 20.0, 0.5, UnitOfTemperature.CELSIUS,
         "Air temperature threshold for summer free heating", NumberMode.BOX),
        ("air_temperature_summer_free_cooling", "Summer FreeCooling Temperature", "mdi:snowflake", 22.0, 30.0, 0.5, UnitOfTemperature.CELSIUS,
         "Air temperature threshold for summer free cooling", NumberMode.BOX),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in bypass_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenTemperatureNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )
    
    # Enhanced Constant Flow Control Numbers (HA 2025.7+ Compatible)
    cf_numbers = [
        ("constant_flow_supply_target", "CF Supply Target", "mdi:chart-line", 50, 500, 5, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         "Constant Flow supply air target flow rate", NumberMode.BOX),
        ("constant_flow_exhaust_target", "CF Exhaust Target", "mdi:chart-line", 50, 500, 5, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         "Constant Flow exhaust air target flow rate", NumberMode.BOX),
        ("constant_flow_tolerance", "CF Tolerance", "mdi:target-variant", 5, 25, 1, PERCENTAGE,
         "Constant Flow tolerance percentage", NumberMode.SLIDER),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in cf_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenFlowNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )
    
    # Enhanced Maintenance Control Numbers (HA 2025.7+ Compatible)
    maintenance_numbers = [
        ("filter_change_interval", "Filter Change Interval", "mdi:air-filter", 90, 365, 7, UnitOfTime.DAYS,
         "Filter replacement interval in days", NumberMode.BOX),
        ("filter_warning_threshold", "Filter Warning Threshold", "mdi:alert-outline", 7, 60, 1, UnitOfTime.DAYS,
         "Days before filter replacement warning", NumberMode.BOX),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in maintenance_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenMaintenanceNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )

    if entities:
        _LOGGER.debug("Adding %d enhanced number entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenBaseNumber(CoordinatorEntity, NumberEntity):
    """Enhanced base number entity for ThesslaGreen - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        min_value: float,
        max_value: float,
        step: float,
        unit: str,
        description: str,
        mode: NumberMode,
    ) -> None:
        """Initialize the enhanced base number entity."""
        super().__init__(coordinator)
        self._key = key
        
        # Enhanced device info handling
        device_info = coordinator.data.get("device_info", {}) if coordinator.data else {}
        device_name = device_info.get("device_name", f"ThesslaGreen {coordinator.host}")
        
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = mode
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        return float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        # Enhanced validation before setting (HA 2025.7+)
        if not self._validate_value(value):
            return
            
        modbus_value = self._convert_to_modbus_value(value)
        
        # Additional range validation
        if modbus_value < 0 or modbus_value > 65535:
            _LOGGER.error("Value %s out of Modbus range for %s", modbus_value, self._key)
            return

        success = await self.coordinator.async_write_register(self._key, modbus_value)
        if success:
            _LOGGER.debug("Set %s to %.1f (Modbus value: %d)", self._key, value, modbus_value)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s to %.1f", self._key, value)

    def _validate_value(self, value: float) -> bool:
        """Enhanced value validation - HA 2025.7+ Compatible."""
        # Basic range check
        if not (self._attr_native_min_value <= value <= self._attr_native_max_value):
            _LOGGER.error("Value %.1f out of range [%.1f, %.1f] for %s", 
                         value, self._attr_native_min_value, self._attr_native_max_value, self._key)
            return False
            
        # Context-specific validation
        return self._validate_context_specific(value)

    def _validate_context_specific(self, value: float) -> bool:
        """Context-specific validation - override in subclasses."""
        return True

    def _convert_to_modbus_value(self, value: float) -> int:
        """Convert display value to Modbus value - override in subclasses."""
        return int(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "register_key": self._key,
            "description": getattr(self, '_attr_entity_description', ''),
            "min_value": self._attr_native_min_value,
            "max_value": self._attr_native_max_value,
            "step": self._attr_native_step,
        }
        
        # Add last update timestamp
        if hasattr(self.coordinator, 'last_update_success_time'):
            attributes["last_updated"] = self.coordinator.last_update_success_time.isoformat()
            
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self._key in self.coordinator.data
        )


class ThesslaGreenIntensityNumber(ThesslaGreenBaseNumber):
    """Enhanced intensity number entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the enhanced intensity number."""
        super().__init__(coordinator, key, name, icon, min_value, max_value, step, unit, description, mode)

    def _validate_context_specific(self, value: float) -> bool:
        """Enhanced intensity validation - HA 2025.7+."""
        # Check if system is on
        if not self.coordinator.data:
            return True
            
        system_power = self.coordinator.data.get("system_on_off", True)
        if not system_power:
            _LOGGER.warning("Cannot set intensity while system is off")
            return False
        
        # Warn about very high intensities
        if value > 120:
            _LOGGER.info("Setting high intensity (%.0f%%) - monitor power consumption", value)
        
        # Check if setting matches current mode
        current_mode = self.coordinator.data.get("mode", 0)
        if self._key == "air_flow_rate_manual" and current_mode != 1:
            _LOGGER.info("Setting manual intensity while not in manual mode")
        elif self._key == "air_flow_rate_temporary" and current_mode != 2:
            _LOGGER.info("Setting temporary intensity while not in temporary mode")
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced intensity context
        current_value = self.native_value
        if current_value is not None:
            # Intensity category
            if current_value <= 30:
                attributes["intensity_category"] = "low"
            elif current_value <= 70:
                attributes["intensity_category"] = "medium"
            elif current_value <= 100:
                attributes["intensity_category"] = "high"
            else:
                attributes["intensity_category"] = "very_high"
        
        # Add current mode context
        current_mode = self.coordinator.data.get("mode", 0)
        mode_names = {0: "Auto", 1: "Manual", 2: "Temporary"}
        attributes["current_mode"] = mode_names.get(current_mode, "Unknown")
        
        # Show if this setting is active
        if self._key == "air_flow_rate_manual":
            attributes["setting_active"] = current_mode == 1
        elif self._key == "air_flow_rate_temporary":
            attributes["setting_active"] = current_mode == 2
        elif self._key == "air_flow_rate_auto":
            attributes["setting_active"] = current_mode == 0
        
        return attributes


class ThesslaGreenTemperatureNumber(ThesslaGreenBaseNumber):
    """Enhanced temperature number entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the enhanced temperature number."""
        super().__init__(coordinator, key, name, icon, min_value, max_value, step, unit, description, mode)
        self._attr_device_class = NumberDeviceClass.TEMPERATURE

    def _convert_to_modbus_value(self, value: float) -> int:
        """Convert temperature to Modbus value (×2 for 0.5°C resolution)."""
        return int(value * 2)

    def _validate_context_specific(self, value: float) -> bool:
        """Enhanced temperature validation - HA 2025.7+."""
        if not self.coordinator.data:
            return True
            
        # Check outside temperature for realistic settings
        outside_temp = self.coordinator.data.get("outside_temperature")
        
        if "supply_temperature" in self._key:
            if outside_temp is not None:
                # Don't heat too much above outside temperature
                if value > outside_temp + 25:
                    _LOGGER.warning("Supply temperature %.1f°C may be too high (outside: %.1f°C)", 
                                   value, outside_temp)
                # Don't cool too much below outside temperature
                elif value < outside_temp - 10:
                    _LOGGER.warning("Supply temperature %.1f°C may be too low (outside: %.1f°C)", 
                                   value, outside_temp)
        
        elif "comfort_temperature" in self._key:
            # Check realistic comfort ranges
            if "heating" in self._key and value > 26:
                _LOGGER.info("High heating temperature %.1f°C - consider energy efficiency", value)
            elif "cooling" in self._key and value < 22:
                _LOGGER.info("Low cooling temperature %.1f°C - consider energy efficiency", value)
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced temperature context
        current_value = self.native_value
        outside_temp = self.coordinator.data.get("outside_temperature")
        
        if current_value is not None and outside_temp is not None:
            temp_diff = current_value - outside_temp
            attributes["temperature_difference"] = round(temp_diff, 1)
            
            if "supply_temperature" in self._key:
                if temp_diff > 0:
                    attributes["heating_provided"] = round(temp_diff, 1)
                else:
                    attributes["cooling_provided"] = round(abs(temp_diff), 1)
        
        # Add season recommendation
        if outside_temp is not None:
            if outside_temp < 10:
                attributes["season_hint"] = "winter_heating"
            elif outside_temp > 25:
                attributes["season_hint"] = "summer_cooling"
            else:
                attributes["season_hint"] = "transitional"
        
        return attributes


class ThesslaGreenFlowNumber(ThesslaGreenBaseNumber):
    """Enhanced flow number entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the enhanced flow number."""
        super().__init__(coordinator, key, name, icon, min_value, max_value, step, unit, description, mode)

    def _validate_context_specific(self, value: float) -> bool:
        """Enhanced flow validation - HA 2025.7+."""
        if not self.coordinator.data:
            return True
            
        # Check Constant Flow is active for CF targets
        if "constant_flow" in self._key:
            cf_active = self.coordinator.data.get("constant_flow_active", False)
            if not cf_active:
                _LOGGER.info("Setting CF target while Constant Flow is not active")
        
        # Balance check for supply/exhaust
        if self._key == "constant_flow_supply_target":
            exhaust_target = self.coordinator.data.get("constant_flow_exhaust_target")
            if exhaust_target and abs(value - exhaust_target) > 50:
                _LOGGER.info("Large imbalance: supply %.0f vs exhaust %.0f m³/h", value, exhaust_target)
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced flow context
        current_value = self.native_value
        if current_value is not None:
            # Flow category for typical home units
            if current_value < 100:
                attributes["flow_category"] = "low"
            elif current_value < 250:
                attributes["flow_category"] = "medium"
            elif current_value < 400:
                attributes["flow_category"] = "high"
            else:
                attributes["flow_category"] = "very_high"
        
        # Add current actual flows for comparison
        if "supply" in self._key:
            actual_flow = self.coordinator.data.get("constant_flow_supply")
            if actual_flow is not None:
                attributes["actual_flow"] = actual_flow
                if current_value is not None:
                    attributes["flow_error"] = round(actual_flow - current_value, 0)
        elif "exhaust" in self._key:
            actual_flow = self.coordinator.data.get("constant_flow_exhaust")
            if actual_flow is not None:
                attributes["actual_flow"] = actual_flow
                if current_value is not None:
                    attributes["flow_error"] = round(actual_flow - current_value, 0)
        
        # CF status
        cf_active = self.coordinator.data.get("constant_flow_active", False)
        attributes["constant_flow_active"] = cf_active
        
        return attributes


class ThesslaGreenMaintenanceNumber(ThesslaGreenBaseNumber):
    """Enhanced maintenance number entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the enhanced maintenance number."""
        super().__init__(coordinator, key, name, icon, min_value, max_value, step, unit, description, mode)
        # These are typically configuration parameters
        self._attr_entity_category = "config"

    def _validate_context_specific(self, value: float) -> bool:
        """Enhanced maintenance validation - HA 2025.7+."""
        if self._key == "filter_change_interval":
            if value < 90:
                _LOGGER.info("Short filter interval (%.0f days) - ensure good filter quality", value)
            elif value > 300:
                _LOGGER.warning("Long filter interval (%.0f days) - monitor air quality", value)
        
        elif self._key == "filter_warning_threshold":
            filter_interval = self.coordinator.data.get("filter_change_interval")
            if filter_interval and value > filter_interval * 0.5:
                _LOGGER.warning("Warning threshold (%.0f days) is more than half the interval", value)
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced maintenance context
        if self._key == "filter_change_interval":
            current_value = self.native_value
            if current_value is not None:
                # Calculate approximate filter changes per year
                changes_per_year = 365 / current_value
                attributes["changes_per_year"] = round(changes_per_year, 1)
        
        # Add current filter status
        filter_remaining = self.coordinator.data.get("filter_time_remaining")
        if filter_remaining is not None:
            attributes["current_filter_remaining"] = filter_remaining
            
            if self._key == "filter_warning_threshold":
                current_value = self.native_value
                if current_value is not None:
                    attributes["warning_will_trigger"] = filter_remaining <= current_value
        
        return attributes