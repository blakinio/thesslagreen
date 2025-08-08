"""Enhanced number platform for ThesslaGreen Modbus integration.
Wszystkie kontrolki numeryczne z kompletnej mapy rejestrów + autoscan.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime, UnitOfVolumeFlowRate, UnitOfPressure, UnitOfPower
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
    """Set up enhanced number platform with comprehensive register support."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # Temperature Control Numbers - wszystkie z PDF + autoscan
    temperature_numbers = [
        ("supply_temperature_manual", "Manual Supply Temperature", "mdi:thermometer-lines", 15.0, 45.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura nawiewu w trybie manual", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("supply_temperature_auto", "Auto Supply Temperature", "mdi:thermometer-auto", 15.0, 45.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura nawiewu w trybie auto", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("supply_temperature_temporary", "Temporary Supply Temperature", "mdi:thermometer-alert", 15.0, 45.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura nawiewu w trybie temporary", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("heating_temperature", "Heating Temperature", "mdi:radiator", 15.0, 35.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura grzania", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("cooling_temperature", "Cooling Temperature", "mdi:snowflake", 20.0, 35.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura chłodzenia", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("comfort_temperature", "Comfort Temperature", "mdi:home-thermometer", 18.0, 30.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura komfortu", NumberMode.SLIDER, NumberDeviceClass.TEMPERATURE),
        ("economy_temperature", "Economy Temperature", "mdi:leaf", 15.0, 25.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura ekonomiczna", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("frost_protection_temp", "Frost Protection Temperature", "mdi:snowflake-alert", -10.0, 10.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura ochrony przeciwmrozowej", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("overheat_protection_temp", "Overheat Protection Temperature", "mdi:thermometer-alert", 40.0, 80.0, 1.0, UnitOfTemperature.CELSIUS,
         "Temperatura ochrony przed przegrzaniem", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("gwc_activation_temp", "GWC Activation Temperature", "mdi:thermometer-chevron-down", -5.0, 15.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura aktywacji GWC", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("bypass_activation_temp", "Bypass Activation Temperature", "mdi:thermometer-chevron-up", 15.0, 30.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura aktywacji bypass", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("supply_temp_diff", "Supply Temperature Difference", "mdi:thermometer-plus", -10.0, 10.0, 0.5, UnitOfTemperature.CELSIUS,
         "Różnica temperatur nawiewu", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("extract_temp_diff", "Extract Temperature Difference", "mdi:thermometer-minus", -10.0, 10.0, 0.5, UnitOfTemperature.CELSIUS,
         "Różnica temperatur wywiewu", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("temperature_hysteresis", "Temperature Hysteresis", "mdi:thermometer", 0.5, 5.0, 0.1, UnitOfTemperature.CELSIUS,
         "Histereza temperatury", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("required_temp", "Required Temperature", "mdi:thermometer-check", 18.0, 30.0, 0.5, UnitOfTemperature.CELSIUS,
         "Temperatura zadana trybu KOMFORT", NumberMode.SLIDER, NumberDeviceClass.TEMPERATURE),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class in temperature_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenTemperatureNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class
                )
            )
    
    # Flow Control Numbers - wszystkie z PDF + autoscan
    flow_numbers = [
        ("air_flow_rate_manual", "Manual Flow Rate", "mdi:fan-speed-1", 10, 150, 1, PERCENTAGE,
         "Intensywność wentylacji w trybie manual", NumberMode.SLIDER, None),
        ("air_flow_rate_auto", "Auto Flow Rate", "mdi:fan-auto", 10, 150, 1, PERCENTAGE,
         "Intensywność wentylacji w trybie auto", NumberMode.SLIDER, None),
        ("air_flow_rate_temporary", "Temporary Flow Rate", "mdi:fan-speed-2", 10, 150, 1, PERCENTAGE,
         "Intensywność wentylacji w trybie temporary", NumberMode.SLIDER, None),
        ("supply_flow_min", "Supply Flow Min", "mdi:fan-chevron-down", 50, 500, 10, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         "Minimalny przepływ nawiewu", NumberMode.BOX, None),
        ("supply_flow_max", "Supply Flow Max", "mdi:fan-chevron-up", 200, 1000, 10, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         "Maksymalny przepływ nawiewu", NumberMode.BOX, None),
        ("exhaust_flow_min", "Exhaust Flow Min", "mdi:fan-chevron-down", 50, 500, 10, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         "Minimalny przepływ wywiewu", NumberMode.BOX, None),
        ("exhaust_flow_max", "Exhaust Flow Max", "mdi:fan-chevron-up", 200, 1000, 10, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         "Maksymalny przepływ wywiewu", NumberMode.BOX, None),
        ("flow_balance", "Flow Balance", "mdi:scale-balance", -20, 20, 1, PERCENTAGE,
         "Balans przepływów", NumberMode.SLIDER, None),
        ("supply_fan_speed", "Supply Fan Speed", "mdi:fan-speed-1", 0, 100, 1, PERCENTAGE,
         "Prędkość wentylatora nawiewnego", NumberMode.SLIDER, None),
        ("exhaust_fan_speed", "Exhaust Fan Speed", "mdi:fan-speed-2", 0, 100, 1, PERCENTAGE,
         "Prędkość wentylatora wywiewnego", NumberMode.SLIDER, None),
        ("airflow_imbalance_alarm", "Airflow Imbalance Alarm", "mdi:scale-unbalanced", 5, 50, 1, PERCENTAGE,
         "Alarm braku balansu przepływów", NumberMode.BOX, None),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class in flow_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenFlowNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class
                )
            )
    
    # Pressure Control Numbers - wszystkie z PDF + autoscan
    pressure_numbers = [
        ("constant_pressure_setpoint", "Constant Pressure Setpoint", "mdi:gauge-empty", 50, 500, 5, UnitOfPressure.PA,
         "Zadana wartość ciśnienia stałego", NumberMode.BOX, NumberDeviceClass.PRESSURE),
        ("variable_pressure_setpoint", "Variable Pressure Setpoint", "mdi:gauge-low", 50, 500, 5, UnitOfPressure.PA,
         "Zadana wartość ciśnienia zmiennego", NumberMode.BOX, NumberDeviceClass.PRESSURE),
        ("filter_pressure_alarm", "Filter Pressure Alarm", "mdi:gauge-alert", 100, 1000, 10, UnitOfPressure.PA,
         "Alarm ciśnienia filtrów", NumberMode.BOX, NumberDeviceClass.PRESSURE),
        ("presostat_differential", "Presostat Differential", "mdi:gauge", 20, 200, 5, UnitOfPressure.PA,
         "Różnica ciśnień presostatu", NumberMode.BOX, NumberDeviceClass.PRESSURE),
        ("pressure_alarm_limit", "Pressure Alarm Limit", "mdi:gauge-full", 200, 2000, 10, UnitOfPressure.PA,
         "Limit alarmu ciśnienia", NumberMode.BOX, NumberDeviceClass.PRESSURE),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class in pressure_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenPressureNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class
                )
            )
    
    # Special Mode Intensity Numbers - wszystkie z PDF + autoscan
    special_mode_numbers = [
        ("okap_intensity", "Hood Intensity", "mdi:cooktop", 10, 150, 5, PERCENTAGE,
         "Intensywność trybu OKAP", NumberMode.SLIDER, None),
        ("kominek_intensity", "Fireplace Intensity", "mdi:fireplace", 10, 150, 5, PERCENTAGE,
         "Intensywność trybu KOMINEK", NumberMode.SLIDER, None),
        ("wietrzenie_intensity", "Ventilation Intensity", "mdi:weather-windy", 10, 150, 5, PERCENTAGE,
         "Intensywność trybu WIETRZENIE", NumberMode.SLIDER, None),
        ("pusty_dom_intensity", "Empty House Intensity", "mdi:home-outline", 10, 80, 5, PERCENTAGE,
         "Intensywność trybu PUSTY DOM", NumberMode.SLIDER, None),
        ("boost_intensity", "Boost Intensity", "mdi:rocket-launch", 80, 150, 5, PERCENTAGE,
         "Intensywność trybu BOOST", NumberMode.SLIDER, None),
        ("night_mode_intensity", "Night Mode Intensity", "mdi:weather-night", 10, 50, 5, PERCENTAGE,
         "Intensywność trybu nocnego", NumberMode.SLIDER, None),
        ("party_mode_intensity", "Party Mode Intensity", "mdi:party-popper", 50, 150, 5, PERCENTAGE,
         "Intensywność trybu party", NumberMode.SLIDER, None),
        ("vacation_mode_intensity", "Vacation Mode Intensity", "mdi:airplane", 10, 50, 5, PERCENTAGE,
         "Intensywność trybu wakacyjnego", NumberMode.SLIDER, None),
        ("emergency_mode_intensity", "Emergency Mode Intensity", "mdi:alert-octagon", 80, 150, 5, PERCENTAGE,
         "Intensywność trybu awaryjnego", NumberMode.SLIDER, None),
        ("custom_mode_1_intensity", "Custom Mode 1 Intensity", "mdi:cog", 10, 150, 5, PERCENTAGE,
         "Intensywność trybu custom 1", NumberMode.SLIDER, None),
        ("custom_mode_2_intensity", "Custom Mode 2 Intensity", "mdi:cog", 10, 150, 5, PERCENTAGE,
         "Intensywność trybu custom 2", NumberMode.SLIDER, None),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class in special_mode_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenSpecialModeNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class
                )
            )
    
    # Duration Numbers - wszystkie z PDF + autoscan
    duration_numbers = [
        ("okap_duration", "Hood Duration", "mdi:timer", 5, 120, 5, UnitOfTime.MINUTES,
         "Czas trwania trybu OKAP", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("kominek_duration", "Fireplace Duration", "mdi:timer", 5, 120, 5, UnitOfTime.MINUTES,
         "Czas trwania trybu KOMINEK", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("wietrzenie_duration", "Ventilation Duration", "mdi:timer", 5, 60, 5, UnitOfTime.MINUTES,
         "Czas trwania trybu WIETRZENIE", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("pusty_dom_duration", "Empty House Duration", "mdi:timer", 60, 1440, 30, UnitOfTime.MINUTES,
         "Czas trwania trybu PUSTY DOM", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("boost_duration", "Boost Duration", "mdi:timer", 5, 60, 5, UnitOfTime.MINUTES,
         "Czas trwania trybu BOOST", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("fan_ramp_time", "Fan Ramp Time", "mdi:speedometer", 5, 120, 5, UnitOfTime.SECONDS,
         "Czas rozbiegu wentylatora", NumberMode.BOX, NumberDeviceClass.DURATION),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class in duration_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenDurationNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class
                )
            )
    
    # Maintenance and Filter Numbers - wszystkie z PDF + autoscan
    maintenance_numbers = [
        ("filter_change_interval", "Filter Change Interval", "mdi:air-filter", 30, 365, 7, UnitOfTime.DAYS,
         "Interwał wymiany filtrów", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("filter_warning_days", "Filter Warning Days", "mdi:calendar-alert", 1, 60, 1, UnitOfTime.DAYS,
         "Ostrzeżenie przed wymianą filtrów", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("maintenance_interval", "Maintenance Interval", "mdi:wrench-clock", 90, 730, 30, UnitOfTime.DAYS,
         "Interwał serwisowy", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("service_interval", "Service Interval", "mdi:tools", 365, 1825, 30, UnitOfTime.DAYS,
         "Interwał serwisu", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("operating_hours_limit", "Operating Hours Limit", "mdi:clock-outline", 1000, 50000, 100, UnitOfTime.HOURS,
         "Limit godzin pracy", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("maintenance_reminder", "Maintenance Reminder", "mdi:calendar-clock", 1, 90, 1, UnitOfTime.DAYS,
         "Przypomnienie o serwisie", NumberMode.BOX, NumberDeviceClass.DURATION),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class in maintenance_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenMaintenanceNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class
                )
            )
    
    # Alarm Limit Numbers - wszystkie z PDF + autoscan
    alarm_numbers = [
        ("energy_efficiency_target", "Energy Efficiency Target", "mdi:leaf", 50, 100, 1, PERCENTAGE,
         "Docelowa wydajność energetyczna", NumberMode.BOX, None),
        ("power_limit", "Power Limit", "mdi:speedometer-medium", 100, 2000, 50, UnitOfPower.WATT,
         "Limit mocy", NumberMode.BOX, NumberDeviceClass.POWER),
        ("acoustic_limit", "Acoustic Limit", "mdi:volume-high", 30, 70, 1, "dB",
         "Limit akustyczny", NumberMode.BOX, None),
        ("vibration_limit", "Vibration Limit", "mdi:vibrate", 1, 10, 0.1, "m/s²",
         "Limit wibracji", NumberMode.BOX, None),
        ("temperature_alarm_limit", "Temperature Alarm Limit", "mdi:thermometer-alert", 40, 80, 1, UnitOfTemperature.CELSIUS,
         "Limit alarmu temperatury", NumberMode.BOX, NumberDeviceClass.TEMPERATURE),
        ("flow_alarm_limit", "Flow Alarm Limit", "mdi:fan-alert", 50, 500, 10, UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
         "Limit alarmu przepływu", NumberMode.BOX, None),
        ("humidity_alarm_limit", "Humidity Alarm Limit", "mdi:water-alert", 30, 90, 5, PERCENTAGE,
         "Limit alarmu wilgotności", NumberMode.BOX, None),
        ("co2_alarm_limit", "CO2 Alarm Limit", "mdi:molecule-co2", 800, 5000, 100, "ppm",
         "Limit alarmu CO2", NumberMode.BOX, None),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class in alarm_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenAlarmLimitNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class
                )
            )
    
    # Advanced Control Numbers - wszystkie z PDF + autoscan
    advanced_numbers = [
        ("heating_curve_slope", "Heating Curve Slope", "mdi:chart-line", 0.5, 3.0, 0.1, None,
         "Nachylenie krzywej grzewczej", NumberMode.BOX, None),
        ("cooling_curve_slope", "Cooling Curve Slope", "mdi:chart-line", 0.5, 3.0, 0.1, None,
         "Nachylenie krzywej chłodzącej", NumberMode.BOX, None),
        ("prediction_horizon", "Prediction Horizon", "mdi:crystal-ball", 1, 24, 1, UnitOfTime.HOURS,
         "Horyzont predykcji", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("averaging_time", "Averaging Time", "mdi:chart-timeline-variant", 30, 600, 30, UnitOfTime.SECONDS,
         "Czas uśredniania pomiarów", NumberMode.BOX, NumberDeviceClass.DURATION),
        ("measurement_interval", "Measurement Interval", "mdi:timer-outline", 5, 120, 5, UnitOfTime.SECONDS,
         "Interwał pomiarów", NumberMode.BOX, NumberDeviceClass.DURATION),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class in advanced_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenAdvancedNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class
                )
            )
    
    # PID Control Numbers - wszystkie z PDF + autoscan
    pid_numbers = [
        ("pid_temperature_kp", "Temperature PID Kp", "mdi:tune", 0.1, 10.0, 0.1, None,
         "PID temperatura Kp", NumberMode.BOX, None),
        ("pid_temperature_ki", "Temperature PID Ki", "mdi:tune", 0.01, 5.0, 0.01, None,
         "PID temperatura Ki", NumberMode.BOX, None),
        ("pid_temperature_kd", "Temperature PID Kd", "mdi:tune", 0.001, 1.0, 0.001, None,
         "PID temperatura Kd", NumberMode.BOX, None),
        ("pid_pressure_kp", "Pressure PID Kp", "mdi:tune", 0.1, 10.0, 0.1, None,
         "PID ciśnienie Kp", NumberMode.BOX, None),
        ("pid_pressure_ki", "Pressure PID Ki", "mdi:tune", 0.01, 5.0, 0.01, None,
         "PID ciśnienie Ki", NumberMode.BOX, None),
        ("pid_pressure_kd", "Pressure PID Kd", "mdi:tune", 0.001, 1.0, 0.001, None,
         "PID ciśnienie Kd", NumberMode.BOX, None),
        ("pid_flow_kp", "Flow PID Kp", "mdi:tune", 0.1, 10.0, 0.1, None,
         "PID przepływ Kp", NumberMode.BOX, None),
        ("pid_flow_ki", "Flow PID Ki", "mdi:tune", 0.01, 5.0, 0.01, None,
         "PID przepływ Ki", NumberMode.BOX, None),
        ("pid_flow_kd", "Flow PID Kd", "mdi:tune", 0.001, 1.0, 0.001, None,
         "PID przepływ Kd", NumberMode.BOX, None),
    ]
    
    for reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class in pid_numbers:
        if reg_key in holding_regs:
            entities.append(
                ThesslaGreenPIDNumber(
                    coordinator, reg_key, name, icon, min_val, max_val, step, unit, description, mode, device_class
                )
            )
    
    if entities:
        _LOGGER.info("Adding %d number entities (autoscan detected)", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No number entities created - check device connectivity and register availability")


class ThesslaGreenBaseNumber(CoordinatorEntity, NumberEntity):
    """Base number for ThesslaGreen devices with enhanced functionality."""
    
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        min_value: float,
        max_value: float,
        step: float,
        unit: str | None,
        description: str,
        mode: NumberMode,
        device_class: NumberDeviceClass | None,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = mode
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category
        self._attr_translation_key = key
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.', '_')}_{coordinator.slave_id}_{key}"
        self._attr_entity_registry_enabled_default = True
        
        # Enhanced device info
        self._attr_device_info = coordinator.device_info
        self._attr_extra_state_attributes = {
            "description": description,
            "register_key": key,
            "last_updated": None,
        }

    @property
    def available(self) -> bool:
        """Return if number is available."""
        if not self.coordinator.last_update_success:
            return False
        
        # Check if register is marked as unavailable
        perf_stats = self.coordinator.performance_stats
        if self._key in perf_stats.get("unavailable_registers", set()):
            return False
            
        return self._key in self.coordinator.data

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if not self.available:
            return None
        
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        
        # Handle temperature values that may need conversion from register format
        if self._attr_device_class == NumberDeviceClass.TEMPERATURE:
            # Some temperature registers use *2 encoding (0.5°C resolution)
            if self._key in ["comfort_temperature", "required_temp"]:
                return float(value) / 2.0 if isinstance(value, int) else float(value)
        
        return float(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = self._attr_extra_state_attributes.copy()
        
        if self.coordinator.last_update_success:
            attrs["last_updated"] = self.coordinator.last_update_success_time
        
        # Add register-specific diagnostic info
        perf_stats = self.coordinator.performance_stats
        reg_stats = perf_stats.get("register_read_stats", {}).get(self._key, {})
        
        if reg_stats:
            attrs["success_count"] = reg_stats.get("success_count", 0)
            if "last_success" in reg_stats and reg_stats["last_success"]:
                attrs["last_success"] = reg_stats["last_success"]
        
        # Add intermittent status
        if self._key in perf_stats.get("intermittent_registers", set()):
            attrs["status"] = "intermittent"
        
        # Add raw value for debugging
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is not None:
            attrs["raw_value"] = raw_value
        
        return attrs

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        # Validate range
        if not (self.native_min_value <= value <= self.native_max_value):
            _LOGGER.warning("Value %s outside valid range %s-%s for %s", 
                          value, self.native_min_value, self.native_max_value, self._attr_name)
            return
        
        # Convert value for register format if needed
        reg_value = value
        
        # Handle temperature values that may need conversion to register format
        if self._attr_device_class == NumberDeviceClass.TEMPERATURE:
            if self._key in ["comfort_temperature", "required_temp"]:
                reg_value = int(value * 2)  # Convert to 0.5°C resolution
            else:
                reg_value = int(value * 10)  # Convert to 0.1°C resolution
        elif isinstance(value, float) and value == int(value):
            reg_value = int(value)
        
        success = await self.coordinator.async_write_register(self._key, reg_value)
        
        if success:
            _LOGGER.info("Set %s to %s %s", self._attr_name, value, self._attr_native_unit_of_measurement or "")
        else:
            _LOGGER.error("Failed to set %s to %s", self._attr_name, value)


class ThesslaGreenTemperatureNumber(ThesslaGreenBaseNumber):
    """Temperature control number."""
    
    pass


class ThesslaGreenFlowNumber(ThesslaGreenBaseNumber):
    """Flow control number."""
    
    pass


class ThesslaGreenPressureNumber(ThesslaGreenBaseNumber):
    """Pressure control number."""
    
    _attr_entity_category = EntityCategory.CONFIG


class ThesslaGreenSpecialModeNumber(ThesslaGreenBaseNumber):
    """Special mode intensity number."""
    
    _attr_entity_category = EntityCategory.CONFIG


class ThesslaGreenDurationNumber(ThesslaGreenBaseNumber):
    """Duration control number."""
    
    _attr_entity_category = EntityCategory.CONFIG


class ThesslaGreenMaintenanceNumber(ThesslaGreenBaseNumber):
    """Maintenance interval number."""
    
    _attr_entity_category = EntityCategory.CONFIG


class ThesslaGreenAlarmLimitNumber(ThesslaGreenBaseNumber):
    """Alarm limit number."""
    
    _attr_entity_category = EntityCategory.CONFIG


class ThesslaGreenAdvancedNumber(ThesslaGreenBaseNumber):
    """Advanced control number."""
    
    _attr_entity_category = EntityCategory.CONFIG


class ThesslaGreenPIDNumber(ThesslaGreenBaseNumber):
    """PID control number."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC