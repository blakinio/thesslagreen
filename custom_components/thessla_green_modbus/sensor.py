"""Sensors for the ThesslaGreen Modbus integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ELECTRIC_CURRENT_MILLIAMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    REVOLUTIONS_PER_MINUTE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    REGISTER_UNITS,
    DEVICE_CLASSES,
    STATE_CLASSES,
)
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Complete sensor definitions with enhanced metadata
SENSOR_DEFINITIONS = {
    # Temperature sensors
    "outside_temperature": {
        "translation_key": "outside_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "supply_temperature": {
        "translation_key": "supply_temperature",
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "exhaust_temperature": {
        "translation_key": "exhaust_temperature",
        "icon": "mdi:thermometer-minus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "fpx_temperature": {
        "translation_key": "fpx_temperature",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "duct_supply_temperature": {
        "translation_key": "duct_supply_temperature",
        "icon": "mdi:thermometer-lines",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "gwc_temperature": {
        "translation_key": "gwc_temperature",
        "icon": "mdi:thermometer-low",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "ambient_temperature": {
        "translation_key": "ambient_temperature",
        "icon": "mdi:home-thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heating_temperature": {
        "translation_key": "heating_temperature",
        "icon": "mdi:thermometer-high",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    
    # Heat exchanger temperatures
    "heat_exchanger_temperature_1": {
        "translation_key": "heat_exchanger_temperature_1",
        "icon": "mdi:heat-pump",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heat_exchanger_temperature_2": {
        "translation_key": "heat_exchanger_temperature_2",
        "icon": "mdi:heat-pump",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heat_exchanger_temperature_3": {
        "translation_key": "heat_exchanger_temperature_3",
        "icon": "mdi:heat-pump",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heat_exchanger_temperature_4": {
        "translation_key": "heat_exchanger_temperature_4",
        "icon": "mdi:heat-pump",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    
    # Flow sensors
    "supply_flowrate": {
        "translation_key": "supply_flowrate",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_flowrate": {
        "translation_key": "exhaust_flowrate",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "outdoor_flowrate": {
        "translation_key": "outdoor_flowrate",
        "icon": "mdi:weather-windy",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "inside_flowrate": {
        "translation_key": "inside_flowrate",
        "icon": "mdi:home-circle",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "gwc_flowrate": {
        "translation_key": "gwc_flowrate",
        "icon": "mdi:pipe",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "heat_recovery_flowrate": {
        "translation_key": "heat_recovery_flowrate",
        "icon": "mdi:heat-pump",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "bypass_flowrate": {
        "translation_key": "bypass_flowrate",
        "icon": "mdi:pipe-leak",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "supply_air_flow": {
        "translation_key": "supply_air_flow",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_air_flow": {
        "translation_key": "exhaust_air_flow",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    
    # Air quality sensors
    "co2_level": {
        "translation_key": "co2_level",
        "icon": "mdi:molecule-co2",
        "device_class": SensorDeviceClass.CO2,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "register_type": "input_registers",
    },
    "humidity_indoor": {
        "translation_key": "humidity_indoor",
        "icon": "mdi:water-percent",
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "humidity_outdoor": {
        "translation_key": "humidity_outdoor",
        "icon": "mdi:water-percent",
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "pm1_level": {
        "translation_key": "pm1_level",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.PM1,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "register_type": "input_registers",
    },
    "pm25_level": {
        "translation_key": "pm25_level",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.PM25,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "register_type": "input_registers",
    },
    "pm10_level": {
        "translation_key": "pm10_level",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.PM10,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "register_type": "input_registers",
    },
    "voc_level": {
        "translation_key": "voc_level",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_PARTS_PER_BILLION,
        "register_type": "input_registers",
    },
    "air_quality_index": {
        "translation_key": "air_quality_index",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.AQI,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": None,
        "register_type": "input_registers",
    },
    
    # System efficiency and status
    "heat_recovery_efficiency": {
        "translation_key": "heat_recovery_efficiency",
        "icon": "mdi:percent",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "filter_lifetime_remaining": {
        "translation_key": "filter_lifetime_remaining",
        "icon": "mdi:filter-variant",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTime.DAYS,
        "register_type": "input_registers",
    },
    
    # Power and energy sensors
    "preheater_power": {
        "translation_key": "preheater_power",
        "icon": "mdi:heating-coil",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "main_heater_power": {
        "translation_key": "main_heater_power",
        "icon": "mdi:heating-coil",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "cooler_power": {
        "translation_key": "cooler_power",
        "icon": "mdi:snowflake",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "supply_fan_power": {
        "translation_key": "supply_fan_power",
        "icon": "mdi:fan",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "exhaust_fan_power": {
        "translation_key": "exhaust_fan_power",
        "icon": "mdi:fan-clock",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "total_power_consumption": {
        "translation_key": "total_power_consumption",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "daily_energy_consumption": {
        "translation_key": "daily_energy_consumption",
        "icon": "mdi:counter",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfEnergy.WATT_HOUR,
        "register_type": "input_registers",
    },
    "annual_energy_consumption": {
        "translation_key": "annual_energy_consumption",
        "icon": "mdi:counter",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "register_type": "input_registers",
    },
    "annual_energy_savings": {
        "translation_key": "annual_energy_savings",
        "icon": "mdi:leaf",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "register_type": "input_registers",
    },
    "co2_reduction": {
        "translation_key": "co2_reduction",
        "icon": "mdi:tree",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": "kg/rok",
        "register_type": "input_registers",
    },
    
    # System diagnostics
    "system_uptime": {
        "translation_key": "system_uptime",
        "icon": "mdi:clock-outline",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfTime.HOURS,
        "register_type": "input_registers",
    },
    "fault_counter": {
        "translation_key": "fault_counter",
        "icon": "mdi:alert-circle",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": None,
        "register_type": "input_registers",
    },
    "maintenance_counter": {
        "translation_key": "maintenance_counter",
        "icon": "mdi:wrench",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": None,
        "register_type": "input_registers",
    },
    "filter_replacement_counter": {
        "translation_key": "filter_replacement_counter",
        "icon": "mdi:filter-variant",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": None,
        "register_type": "input_registers",
    },
    
    # Pressure sensors
    "supply_pressure": {
        "translation_key": "supply_pressure",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPressure.PA,
        "register_type": "input_registers",
    },
    "exhaust_pressure": {
        "translation_key": "exhaust_pressure",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPressure.PA,
        "register_type": "input_registers",
    },
    "differential_pressure": {
        "translation_key": "differential_pressure",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPressure.PA,
        "register_type": "input_registers",
    },
    
    # Motor diagnostics
    "motor_supply_rpm": {
        "translation_key": "motor_supply_rpm",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": REVOLUTIONS_PER_MINUTE,
        "register_type": "input_registers",
    },
    "motor_exhaust_rpm": {
        "translation_key": "motor_exhaust_rpm",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": REVOLUTIONS_PER_MINUTE,
        "register_type": "input_registers",
    },
    "motor_supply_current": {
        "translation_key": "motor_supply_current",
        "icon": "mdi:current-ac",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_CURRENT_MILLIAMPERE,
        "register_type": "input_registers",
    },
    "motor_exhaust_current": {
        "translation_key": "motor_exhaust_current",
        "icon": "mdi:current-ac",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_CURRENT_MILLIAMPERE,
        "register_type": "input_registers",
    },
    "motor_supply_voltage": {
        "translation_key": "motor_supply_voltage",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_MILLIVOLT,
        "register_type": "input_registers",
    },
    "motor_exhaust_voltage": {
        "translation_key": "motor_exhaust_voltage",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_MILLIVOLT,
        "register_type": "input_registers",
    },
    
    # PWM control values
    "dac_supply": {
        "translation_key": "dac_supply",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_VOLT,
        "register_type": "input_registers",
    },
    "dac_exhaust": {
        "translation_key": "dac_exhaust",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_VOLT,
        "register_type": "input_registers",
    },
    "dac_heater": {
        "translation_key": "dac_heater",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_VOLT,
        "register_type": "input_registers",
    },
    "dac_cooler": {
        "translation_key": "dac_cooler",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_VOLT,
        "register_type": "input_registers",
    },
    
    # Damper positions
    "damper_position_bypass": {
        "translation_key": "damper_position_bypass",
        "icon": "mdi:valve",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "damper_position_gwc": {
        "translation_key": "damper_position_gwc",
        "icon": "mdi:valve",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "damper_position_mix": {
        "translation_key": "damper_position_mix",
        "icon": "mdi:valve",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    
    # Firmware and version info
    "firmware_major": {
        "translation_key": "firmware_major",
        "icon": "mdi:chip",
        "unit": None,
        "register_type": "input_registers",
    },
    "firmware_minor": {
        "translation_key": "firmware_minor",
        "icon": "mdi:chip",
        "unit": None,
        "register_type": "input_registers",
    },
    "firmware_patch": {
        "translation_key": "firmware_patch",
        "icon": "mdi:chip",
        "unit": None,
        "register_type": "input_registers",
    },
    "expansion_version": {
        "translation_key": "expansion_version",
        "icon": "mdi:expansion-card",
        "unit": None,
        "register_type": "input_registers",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen sensor entities based on available registers."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Create sensors only for available registers (autoscan result)
    for register_name, sensor_def in SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]
        
        # Check if this register is available on the device
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenSensor(coordinator, register_name, sensor_def))
            _LOGGER.debug("Created sensor: %s", sensor_def["translation_key"])
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Created %d sensor entities for %s", len(entities), coordinator.device_name)
    else:
        _LOGGER.warning("No sensor entities created - no compatible registers found")


class ThesslaGreenSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for ThesslaGreen device."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        sensor_definition: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._register_name = register_name
        self._sensor_def = sensor_definition
        
        # Entity attributes
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{register_name}"
        self._attr_device_info = coordinator.device_info_dict

        # Sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        self._attr_native_unit_of_measurement = sensor_definition.get("unit")
        self._attr_device_class = sensor_definition.get("device_class")
        self._attr_state_class = sensor_definition.get("state_class")

        # Translation setup
        self._attr_translation_key = sensor_definition.get("translation_key")
        self._attr_has_entity_name = True

        _LOGGER.debug(
            "Sensor initialized: %s (%s)",
            sensor_definition.get("translation_key"),
            register_name,
        )

    @property
    def native_value(self) -> Optional[float | int | str]:
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self._register_name)
        
        if value is None:
            return None
        
        # Special handling for firmware version display
        if self._register_name in ["firmware_major", "firmware_minor", "firmware_patch"]:
            return value
        
        # Special handling for expansion version (convert hex to decimal.decimal format)
        if self._register_name == "expansion_version" and isinstance(value, int):
            major = (value >> 8) & 0xFF
            minor = value & 0xFF
            return f"{major}.{minor:02d}"
        
        return value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and
            self._register_name in self.coordinator.data
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}
        
        # Add register address for debugging
        if hasattr(self.coordinator, 'device_scan_result') and self.coordinator.device_scan_result:
            attrs["register_name"] = self._register_name
            attrs["register_type"] = self._sensor_def["register_type"]
        
        # Add raw value for diagnostic purposes
        raw_value = self.coordinator.data.get(self._register_name)
        if raw_value is not None and isinstance(raw_value, (int, float)):
            attrs["raw_value"] = raw_value
        
        return attrs