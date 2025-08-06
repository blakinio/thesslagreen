"""Enhanced number platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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
        ("comfort_temperature_heating", "Heating Target Temperature", "mdi:thermometer-chevron-up", 18.0, 30.0, 0.5, UnitOfTemperature.CELSIUS,
         "Target temperature for heating mode", NumberMode.BOX),
        ("comfort_temperature_cooling", "Cooling Target Temperature", "mdi:thermometer-chevron-down", 20.0, 35.0, 0.5, UnitOfTemperature.CELSIUS,
         "Target temperature for cooling mode", NumberMode.BOX),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in temperature_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenTemperatureNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )
    
    # Enhanced Time Control Numbers (HA 2025.7+ Compatible)
    time_numbers = [
        ("temporary_time_remaining", "Temporary Mode Time", "mdi:timer", 1, 480, 1, UnitOfTime.MINUTES,
         "Remaining time in temporary mode", NumberMode.BOX),
        ("boost_duration", "Boost Duration", "mdi:rocket-launch", 5, 120, 5, UnitOfTime.MINUTES,
         "Duration for boost mode", NumberMode.BOX),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in time_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenTimeNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )
    
    # Enhanced GWC Temperature Control Numbers (HA 2025.7+ Compatible)
    gwc_numbers = [
        ("gwc_delta_temp_summer", "GWC Summer Delta Temperature", "mdi:thermometer-plus", 2.0, 15.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperature difference for summer GWC operation", NumberMode.BOX),
        ("gwc_delta_temp_winter", "GWC Winter Delta Temperature", "mdi:thermometer-minus", 2.0, 15.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperature difference for winter GWC operation", NumberMode.BOX),
        ("gwc_max_temp", "GWC Maximum Temperature", "mdi:thermometer-high", 15.0, 35.0, 0.5, UnitOfTemperature.CELSIUS,
         "Maximum temperature for GWC operation", NumberMode.BOX),
        ("gwc_min_temp", "GWC Minimum Temperature", "mdi:thermometer-low", -10.0, 10.0, 0.5, UnitOfTemperature.CELSIUS,
         "Minimum temperature for GWC operation", NumberMode.BOX),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in gwc_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenGWCNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )
    
    # Enhanced Constant Flow Control Numbers (HA 2025.7+ Compatible)
    cf_numbers = [
        ("constant_flow_supply_target", "CF Supply Target", "mdi:chart-line-variant", 50, 500, 10, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         "Target supply flow for constant flow mode", NumberMode.BOX),
        ("constant_flow_exhaust_target", "CF Exhaust Target", "mdi:chart-line", 50, 500, 10, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         "Target exhaust flow for constant flow mode", NumberMode.BOX),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode in cf_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenConstantFlowNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode
                )
            )
    
    # Enhanced Maintenance Control Numbers (HA 2025.7+ Compatible)
    maintenance_numbers = [
        ("filter_change_interval", "Filter Change Interval", "mdi:air-filter", 90, 365, 1, UnitOfTime.DAYS,
         "Interval between filter changes", NumberMode.BOX),
        ("filter_warning_threshold", "Filter Warning Threshold", "mdi:air-filter-outline", 7, 60, 1, UnitOfTime.DAYS,
         "Days before filter change to show warning", NumberMode.BOX),
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
    """Base number entity for ThesslaGreen devices - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = mode
        self._description = description
        
        # Enhanced device info (HA 2025.7+)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": f"ThesslaGreen ({coordinator.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": coordinator.device_scan_result.get("device_info", {}).get("firmware", "Unknown"),
        }

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None
        
        # Convert based on unit type
        if self._attr_native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            # Temperature values are stored as 0.1°C units
            return round(raw_value / 10.0, 1)
        else:
            # Other values are direct
            return float(raw_value)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self.coordinator.data.get(self._key) is not None
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if not self._validate_value(value):
            _LOGGER.error("Invalid value %.2f for %s (range: %.2f-%.2f)", 
                         value, self._key, self._attr_native_min_value, self._attr_native_max_value)
            return

        # Perform context-specific validation
        if not self._validate_context_specific(value):
            return

        # Convert value for device
        device_value = self._convert_value_for_device(value)
        
        # Write to device
        success = await self.coordinator.async_write_register(self._key, device_value)
        if success:
            _LOGGER.info("Set %s to %.2f (device value: %d)", self._key, value, device_value)
            # Update coordinator data immediately for better UI responsiveness
            self.coordinator.data[self._key] = device_value
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to set %s to %.2f", self._key, value)

    def _validate_value(self, value: float) -> bool:
        """Validate value is within acceptable range."""
        return self._attr_native_min_value <= value <= self._attr_native_max_value

    def _validate_context_specific(self, value: float) -> bool:
        """Perform context-specific validation. Override in subclasses."""
        return True

    def _convert_value_for_device(self, value: float) -> int:
        """Convert HA value to device value."""
        if self._attr_native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            # Convert to 0.1°C units
            return int(round(value * 10))
        else:
            # Direct conversion
            return int(round(value))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "description": self._description,
            "register_key": self._key,
            "device_value": self.coordinator.data.get(self._key),
            "last_update": getattr(self.coordinator, 'last_update_success_time', self.coordinator.last_update_success),
        }


class ThesslaGreenIntensityNumber(ThesslaGreenBaseNumber):
    """Enhanced intensity number entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the intensity number."""
        super().__init__(coordinator, key, name, icon, min_value, max_value, step, unit, description, mode)

    def _validate_context_specific(self, value: float) -> bool:
        """Enhanced intensity validation - HA 2025.7+."""
        # Check if intensity is reasonable for current mode
        current_mode = self.coordinator.data.get("mode", 0)
        
        if current_mode == 0:  # Auto mode
            if value > 100:
                _LOGGER.warning("High intensity (%.0f%%) in auto mode may not be applied", value)
        
        elif current_mode == 1:  # Manual mode
            if value < 20:
                _LOGGER.info("Low intensity (%.0f%%) - ensure adequate ventilation", value)
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced intensity context (HA 2025.7+)
        current_value = self.native_value
        if current_value is not None:
            # Intensity categories
            if current_value < 30:
                attributes["intensity_level"] = "low"
            elif current_value < 60:
                attributes["intensity_level"] = "medium"
            elif current_value < 90:
                attributes["intensity_level"] = "high"
            else:
                attributes["intensity_level"] = "maximum"
        
        # Add current mode context
        current_mode = self.coordinator.data.get("mode")
        if current_mode is not None:
            mode_names = {0: "Auto", 1: "Manual", 2: "Temporary"}
            attributes["current_mode"] = mode_names.get(current_mode, "Unknown")
            
            # Check if this intensity setting is active
            if "manual" in self._key and current_mode == 1:
                attributes["setting_active"] = True
            elif "temporary" in self._key and current_mode == 2:
                attributes["setting_active"] = True
            elif "auto" in self._key and current_mode == 0:
                attributes["setting_active"] = True
            else:
                attributes["setting_active"] = False
        
        return attributes


class ThesslaGreenTemperatureNumber(ThesslaGreenBaseNumber):
    """Enhanced temperature number entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the temperature number."""
        super().__init__(coordinator, key, name, icon, min_value, max_value, step, unit, description, mode)
        # Temperature controls are usually configuration parameters
        self._attr_entity_category = EntityCategory.CONFIG

    def _validate_context_specific(self, value: float) -> bool:
        """Enhanced temperature validation - HA 2025.7+."""
        # Check heating/cooling temperature logic
        if "heating" in self._key:
            cooling_temp = self.coordinator.data.get("comfort_temperature_cooling")
            if cooling_temp and value >= cooling_temp / 10.0:
                _LOGGER.warning("Heating temperature (%.1f°C) should be lower than cooling temperature", value)
        
        elif "cooling" in self._key:
            heating_temp = self.coordinator.data.get("comfort_temperature_heating")
            if heating_temp and value <= heating_temp / 10.0:
                _LOGGER.warning("Cooling temperature (%.1f°C) should be higher than heating temperature", value)
        
        # Check supply temperature safety
        elif "supply" in self._key:
            if value > 40.0:
                _LOGGER.warning("High supply temperature (%.1f°C) - check safety settings", value)
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced temperature context (HA 2025.7+)
        current_value = self.native_value
        if current_value is not None:
            # Temperature categories
            if current_value < 18:
                attributes["temperature_category"] = "cold"
            elif current_value < 22:
                attributes["temperature_category"] = "cool"
            elif current_value < 26:
                attributes["temperature_category"] = "comfortable"
            elif current_value < 30:
                attributes["temperature_category"] = "warm"
            else:
                attributes["temperature_category"] = "hot"
        
        # Add related temperature references
        if "heating" in self._key:
            cooling_temp = self.coordinator.data.get("comfort_temperature_cooling")
            if cooling_temp:
                attributes["cooling_temperature"] = round(cooling_temp / 10.0, 1)
        
        elif "cooling" in self._key:
            heating_temp = self.coordinator.data.get("comfort_temperature_heating")
            if heating_temp:
                attributes["heating_temperature"] = round(heating_temp / 10.0, 1)
        
        # Check if comfort mode is active
        comfort_active = self.coordinator.data.get("comfort_active", False)
        attributes["comfort_mode_active"] = comfort_active
        
        return attributes


class ThesslaGreenTimeNumber(ThesslaGreenBaseNumber):
    """Enhanced time number entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the time number."""
        super().__init__(coordinator, key, name, icon, min_value, max_value, step, unit, description, mode)

    def _validate_context_specific(self, value: float) -> bool:
        """Enhanced time validation - HA 2025.7+."""
        if self._key == "temporary_time_remaining":
            current_mode = self.coordinator.data.get("mode", 0)
            if current_mode != 2:
                _LOGGER.info("Setting temporary time while not in temporary mode")
        
        elif self._key == "boost_duration":
            if value > 60:
                _LOGGER.info("Long boost duration (%.0f min) - consider energy consumption", value)
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced time context (HA 2025.7+)
        current_value = self.native_value
        if current_value is not None:
            # Time categories
            if current_value < 15:
                attributes["duration_category"] = "short"
            elif current_value < 60:
                attributes["duration_category"] = "medium"
            elif current_value < 180:
                attributes["duration_category"] = "long"
            else:
                attributes["duration_category"] = "very_long"
            
            # Convert to hours for user context
            if current_value >= 60:
                attributes["hours"] = round(current_value / 60, 1)
        
        # Add mode context for temporary time
        if "temporary" in self._key:
            current_mode = self.coordinator.data.get("mode")
            attributes["temporary_mode_active"] = (current_mode == 2)
        
        return attributes


class ThesslaGreenGWCNumber(ThesslaGreenBaseNumber):
    """Enhanced GWC number entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the GWC number."""
        super().__init__(coordinator, key, name, icon, min_value, max_value, step, unit, description, mode)
        # GWC settings are configuration parameters
        self._attr_entity_category = EntityCategory.CONFIG

    def _validate_context_specific(self, value: float) -> bool:
        """Enhanced GWC validation - HA 2025.7+."""
        # Validate GWC temperature ranges make sense
        if "delta" in self._key:
            if value < 3.0:
                _LOGGER.warning("Low GWC delta temperature (%.1f°C) may reduce effectiveness", value)
        
        elif "max_temp" in self._key:
            min_temp = self.coordinator.data.get("gwc_min_temp")
            if min_temp and value <= min_temp / 10.0:
                _LOGGER.warning("GWC max temp (%.1f°C) should be higher than min temp", value)
        
        elif "min_temp" in self._key:
            max_temp = self.coordinator.data.get("gwc_max_temp")
            if max_temp and value >= max_temp / 10.0:
                _LOGGER.warning("GWC min temp (%.1f°C) should be lower than max temp", value)
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced GWC context (HA 2025.7+)
        current_value = self.native_value
        if current_value is not None:
            if "delta" in self._key:
                if current_value < 5:
                    attributes["efficiency_impact"] = "low"
                elif current_value < 10:
                    attributes["efficiency_impact"] = "medium" 
                else:
                    attributes["efficiency_impact"] = "high"
        
        # Add GWC status
        gwc_active = self.coordinator.data.get("gwc_active", False)
        attributes["gwc_active"] = gwc_active
        
        gwc_mode = self.coordinator.data.get("gwc_mode")
        if gwc_mode is not None:
            mode_names = {0: "Inactive", 1: "Winter", 2: "Summer"}
            attributes["gwc_mode"] = mode_names.get(gwc_mode, "Unknown")
        
        return attributes


class ThesslaGreenConstantFlowNumber(ThesslaGreenBaseNumber):
    """Enhanced constant flow number entity - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, min_value, max_value, step, unit, description, mode):
        """Initialize the constant flow number."""
        super().__init__(coordinator, key, name, icon, min_value, max_value, step, unit, description, mode)
        # Flow targets are configuration parameters
        self._attr_entity_category = EntityCategory.CONFIG

    def _validate_context_specific(self, value: float) -> bool:
        """Enhanced constant flow validation - HA 2025.7+."""
        # Check flow balance
        if "supply" in self._key:
            exhaust_target = self.coordinator.data.get("constant_flow_exhaust_target")
            if exhaust_target and abs(value - exhaust_target) > 50:
                _LOGGER.info("Supply flow (%.0f) differs significantly from exhaust target", value)
        
        elif "exhaust" in self._key:
            supply_target = self.coordinator.data.get("constant_flow_supply_target")
            if supply_target and abs(value - supply_target) > 50:
                _LOGGER.info("Exhaust flow (%.0f) differs significantly from supply target", value)
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced flow context (HA 2025.7+)
        current_value = self.native_value
        if current_value is not None:
            # Flow categories for typical home units
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
        self._attr_entity_category = EntityCategory.CONFIG

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
        
        # Enhanced maintenance context (HA 2025.7+)
        current_value = self.native_value
        if current_value is not None:
            if "interval" in self._key:
                attributes["weeks"] = round(current_value / 7, 1)
                attributes["months"] = round(current_value / 30, 1)
                
                # Maintenance frequency categories
                if current_value < 120:
                    attributes["maintenance_frequency"] = "frequent"
                elif current_value < 180:
                    attributes["maintenance_frequency"] = "normal"
                else:
                    attributes["maintenance_frequency"] = "infrequent"
        
        # Add current filter status
        filter_time_remaining = self.coordinator.data.get("filter_time_remaining")
        if filter_time_remaining is not None:
            attributes["current_filter_remaining"] = filter_time_remaining
            
            # Calculate next change date (approximation)
            if filter_time_remaining > 0:
                attributes["filter_status"] = "ok"
            else:
                attributes["filter_status"] = "needs_replacement"
        
        return attributes