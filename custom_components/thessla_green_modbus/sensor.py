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
        "name": "Temperatura zewnętrzna",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "supply_temperature": {
        "name": "Temperatura nawiewu",
        "icon": "mdi:thermometer-plus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "exhaust_temperature": {
        "name": "Temperatura wywiewu",
        "icon": "mdi:thermometer-minus",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "fpx_temperature": {
        "name": "Temperatura FPX",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "duct_supply_temperature": {
        "name": "Temperatura kanałowa",
        "icon": "mdi:thermometer-lines",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "gwc_temperature": {
        "name": "Temperatura GWC",
        "icon": "mdi:thermometer-low",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "ambient_temperature": {
        "name": "Temperatura otoczenia",
        "icon": "mdi:home-thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heating_temperature": {
        "name": "Temperatura grzania",
        "icon": "mdi:thermometer-high",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    
    # Heat exchanger temperatures
    "heat_exchanger_temperature_1": {
        "name": "Temperatura wymiennika 1",
        "icon": "mdi:heat-pump",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heat_exchanger_temperature_2": {
        "name": "Temperatura wymiennika 2",
        "icon": "mdi:heat-pump",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heat_exchanger_temperature_3": {
        "name": "Temperatura wymiennika 3",
        "icon": "mdi:heat-pump",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    "heat_exchanger_temperature_4": {
        "name": "Temperatura wymiennika 4",
        "icon": "mdi:heat-pump",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    
    # Flow sensors
    "supply_flowrate": {
        "name": "Przepływ nawiewu",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_flowrate": {
        "name": "Przepływ wywiewu",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "outdoor_flowrate": {
        "name": "Przepływ zewnętrzny",
        "icon": "mdi:weather-windy",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "inside_flowrate": {
        "name": "Przepływ wewnętrzny",
        "icon": "mdi:home-circle",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "gwc_flowrate": {
        "name": "Przepływ GWC",
        "icon": "mdi:pipe",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "heat_recovery_flowrate": {
        "name": "Przepływ rekuperatora",
        "icon": "mdi:heat-pump",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "bypass_flowrate": {
        "name": "Przepływ bypass",
        "icon": "mdi:pipe-leak",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "supply_air_flow": {
        "name": "Strumień nawiewu",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_air_flow": {
        "name": "Strumień wywiewu",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    
    # Air quality sensors
    "co2_level": {
        "name": "Poziom CO2",
        "icon": "mdi:molecule-co2",
        "device_class": SensorDeviceClass.CO2,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "register_type": "input_registers",
    },
    "humidity_indoor": {
        "name": "Wilgotność wewnętrzna",
        "icon": "mdi:water-percent",
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "humidity_outdoor": {
        "name": "Wilgotność zewnętrzna",
        "icon": "mdi:water-percent",
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "pm1_level": {
        "name": "PM1.0",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.PM1,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "register_type": "input_registers",
    },
    "pm25_level": {
        "name": "PM2.5",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.PM25,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "register_type": "input_registers",
    },
    "pm10_level": {
        "name": "PM10",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.PM10,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "register_type": "input_registers",
    },
    "voc_level": {
        "name": "VOC",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": CONCENTRATION_PARTS_PER_BILLION,
        "register_type": "input_registers",
    },
    "air_quality_index": {
        "name": "Indeks jakości powietrza",
        "icon": "mdi:air-filter",
        "device_class": SensorDeviceClass.AQI,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": None,
        "register_type": "input_registers",
    },
    
    # System efficiency and status
    "heat_recovery_efficiency": {
        "name": "Sprawność rekuperacji",
        "icon": "mdi:percent",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "filter_lifetime_remaining": {
        "name": "Pozostały czas życia filtra",
        "icon": "mdi:filter-variant",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTime.DAYS,
        "register_type": "input_registers",
    },
    
    # Power and energy sensors
    "preheater_power": {
        "name": "Moc wstępnego grzania",
        "icon": "mdi:heating-coil",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "main_heater_power": {
        "name": "Moc głównego grzania",
        "icon": "mdi:heating-coil",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "cooler_power": {
        "name": "Moc chłodzenia",
        "icon": "mdi:snowflake",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "supply_fan_power": {
        "name": "Moc wentylatora nawiewnego",
        "icon": "mdi:fan",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "exhaust_fan_power": {
        "name": "Moc wentylatora wywiewnego",
        "icon": "mdi:fan-clock",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "total_power_consumption": {
        "name": "Całkowite zużycie energii",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.WATT,
        "register_type": "input_registers",
    },
    "daily_energy_consumption": {
        "name": "Dzienne zużycie energii",
        "icon": "mdi:counter",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfEnergy.WATT_HOUR,
        "register_type": "input_registers",
    },
    "annual_energy_consumption": {
        "name": "Roczne zużycie energii",
        "icon": "mdi:counter",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "register_type": "input_registers",
    },
    "annual_energy_savings": {
        "name": "Roczne oszczędności energii",
        "icon": "mdi:leaf",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "register_type": "input_registers",
    },
    "co2_reduction": {
        "name": "Redukcja CO2",
        "icon": "mdi:tree",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": "kg/rok",
        "register_type": "input_registers",
    },
    
    # System diagnostics
    "system_uptime": {
        "name": "Czas pracy systemu",
        "icon": "mdi:clock-outline",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfTime.HOURS,
        "register_type": "input_registers",
    },
    "fault_counter": {
        "name": "Licznik błędów",
        "icon": "mdi:alert-circle",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": None,
        "register_type": "input_registers",
    },
    "maintenance_counter": {
        "name": "Licznik konserwacji",
        "icon": "mdi:wrench",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": None,
        "register_type": "input_registers",
    },
    "filter_replacement_counter": {
        "name": "Licznik wymian filtra",
        "icon": "mdi:filter-variant",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": None,
        "register_type": "input_registers",
    },
    
    # Pressure sensors
    "supply_pressure": {
        "name": "Ciśnienie nawiewu",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPressure.PA,
        "register_type": "input_registers",
    },
    "exhaust_pressure": {
        "name": "Ciśnienie wywiewu",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPressure.PA,
        "register_type": "input_registers",
    },
    "differential_pressure": {
        "name": "Ciśnienie różnicowe",
        "icon": "mdi:gauge",
        "device_class": SensorDeviceClass.PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPressure.PA,
        "register_type": "input_registers",
    },
    
    # Motor diagnostics
    "motor_supply_rpm": {
        "name": "Obroty silnika nawiewnego",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": REVOLUTIONS_PER_MINUTE,
        "register_type": "input_registers",
    },
    "motor_exhaust_rpm": {
        "name": "Obroty silnika wywiewnego",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": REVOLUTIONS_PER_MINUTE,
        "register_type": "input_registers",
    },
    "motor_supply_current": {
        "name": "Prąd silnika nawiewnego",
        "icon": "mdi:current-ac",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_CURRENT_MILLIAMPERE,
        "register_type": "input_registers",
    },
    "motor_exhaust_current": {
        "name": "Prąd silnika wywiewnego",
        "icon": "mdi:current-ac",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_CURRENT_MILLIAMPERE,
        "register_type": "input_registers",
    },
    "motor_supply_voltage": {
        "name": "Napięcie silnika nawiewnego",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_MILLIVOLT,
        "register_type": "input_registers",
    },
    "motor_exhaust_voltage": {
        "name": "Napięcie silnika wywiewnego",
        "icon": "mdi:lightning-bolt",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_MILLIVOLT,
        "register_type": "input_registers",
    },
    
    # PWM control values
    "dac_supply": {
        "name": "Sterowanie wentylatorem nawiewnym",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_VOLT,
        "register_type": "input_registers",
    },
    "dac_exhaust": {
        "name": "Sterowanie wentylatorem wywiewnym",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_VOLT,
        "register_type": "input_registers",
    },
    "dac_heater": {
        "name": "Sterowanie nagrzewnicą",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_VOLT,
        "register_type": "input_registers",
    },
    "dac_cooler": {
        "name": "Sterowanie chłodnicą",
        "icon": "mdi:sine-wave",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": ELECTRIC_POTENTIAL_VOLT,
        "register_type": "input_registers",
    },
    
    # Damper positions
    "damper_position_bypass": {
        "name": "Pozycja przepustnicy bypass",
        "icon": "mdi:valve",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "damper_position_gwc": {
        "name": "Pozycja przepustnicy GWC",
        "icon": "mdi:valve",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "damper_position_mix": {
        "name": "Pozycja przepustnicy mieszającej",
        "icon": "mdi:valve",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    
    # Firmware and version info
    "firmware_major": {
        "name": "Wersja firmware (główna)",
        "icon": "mdi:chip",
        "unit": None,
        "register_type": "input_registers",
    },
    "firmware_minor": {
        "name": "Wersja firmware (podrzędna)",
        "icon": "mdi:chip",
        "unit": None,
        "register_type": "input_registers",
    },
    "firmware_patch": {
        "name": "Wersja firmware (poprawka)",
        "icon": "mdi:chip",
        "unit": None,
        "register_type": "input_registers",
    },
    "expansion_version": {
        "name": "Wersja modułu Expansion",
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
            _LOGGER.debug("Created sensor: %s", sensor_def["name"])
    
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
        self._attr_name = f"{coordinator.device_name} {sensor_definition['name']}"
        self._attr_device_info = coordinator.device_info_dict
        
        # Sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        self._attr_native_unit_of_measurement = sensor_definition.get("unit")
        self._attr_device_class = sensor_definition.get("device_class")
        self._attr_state_class = sensor_definition.get("state_class")
        
        _LOGGER.debug("Sensor initialized: %s (%s)", self._attr_name, register_name)

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