"""Sensors for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator
from .entity import ThesslaGreenEntity

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
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "input_registers",
    },
    # System information
    "day_of_week": {
        "translation_key": "day_of_week",
        "icon": "mdi:calendar-week",
        "register_type": "input_registers",
    },
    "period": {
        "translation_key": "period",
        "icon": "mdi:clock-outline",
        "register_type": "input_registers",
    },
    "compilation_days": {
        "translation_key": "compilation_days",
        "icon": "mdi:calendar",
        "register_type": "input_registers",
    },
    "compilation_seconds": {
        "translation_key": "compilation_seconds",
        "icon": "mdi:timer",
        "register_type": "input_registers",
    },
    "serial_number_1": {
        "translation_key": "serial_number_1",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_2": {
        "translation_key": "serial_number_2",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_3": {
        "translation_key": "serial_number_3",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_4": {
        "translation_key": "serial_number_4",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_5": {
        "translation_key": "serial_number_5",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    "serial_number_6": {
        "translation_key": "serial_number_6",
        "icon": "mdi:identifier",
        "register_type": "input_registers",
    },
    # Flow sensors
    "supply_flow_rate": {
        "translation_key": "supply_flow_rate",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "exhaust_flow_rate": {
        "translation_key": "exhaust_flow_rate",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "input_registers",
    },
    "supply_air_flow": {
        "translation_key": "supply_air_flow",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "exhaust_air_flow": {
        "translation_key": "exhaust_air_flow",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "max_supply_air_flow_rate": {
        "translation_key": "max_supply_air_flow_rate",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "max_exhaust_air_flow_rate": {
        "translation_key": "max_exhaust_air_flow_rate",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "nominal_supply_air_flow": {
        "translation_key": "nominal_supply_air_flow",
        "icon": "mdi:fan",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "nominal_exhaust_air_flow": {
        "translation_key": "nominal_exhaust_air_flow",
        "icon": "mdi:fan-clock",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "register_type": "holding_registers",
    },
    "bypass_off": {
        "translation_key": "bypass_off",
        "icon": "mdi:thermometer-off",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "register_type": "holding_registers",
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
    # Percentage sensors
    "supply_percentage": {
        "translation_key": "supply_percentage",
        "icon": "mdi:fan-plus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "exhaust_percentage": {
        "translation_key": "exhaust_percentage",
        "icon": "mdi:fan-minus",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "min_percentage": {
        "translation_key": "min_percentage",
        "icon": "mdi:percent-outline",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    "max_percentage": {
        "translation_key": "max_percentage",
        "icon": "mdi:percent-outline",
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": PERCENTAGE,
        "register_type": "input_registers",
    },
    # Firmware and version info
    "version_major": {
        "translation_key": "firmware_major",
        "icon": "mdi:chip",
        "unit": None,
        "register_type": "input_registers",
    },
    "version_minor": {
        "translation_key": "firmware_minor",
        "icon": "mdi:chip",
        "unit": None,
        "register_type": "input_registers",
    },
    "version_patch": {
        "translation_key": "firmware_patch",
        "icon": "mdi:chip",
        "unit": None,
        "register_type": "input_registers",
    },
    "exp_version": {
        "translation_key": "expansion_version",
        "icon": "mdi:expansion-card",
        "unit": None,
        "register_type": "holding_registers",
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


class ThesslaGreenSensor(ThesslaGreenEntity, SensorEntity):
    """Sensor entity for ThesslaGreen device."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        sensor_definition: Dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, register_name)
        self._attr_device_info = coordinator.get_device_info()

        self._register_name = register_name
        self._sensor_def = sensor_definition

        # Sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        self._attr_native_unit_of_measurement = sensor_definition.get("unit")
        self._attr_device_class = sensor_definition.get("device_class")
        self._attr_state_class = sensor_definition.get("state_class")

        # Translation setup
        self._attr_translation_key = sensor_definition.get("translation_key")

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
        if self._register_name in ["version_major", "version_minor", "version_patch"]:
            return value

        # Special handling for expansion version (convert hex to decimal.decimal format)
        if self._register_name == "exp_version" and isinstance(value, int):
            major = (value >> 8) & 0xFF
            minor = value & 0xFF
            return f"{major}.{minor:02d}"

        return value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}

        # Add register address for debugging
        if hasattr(self.coordinator, "device_scan_result") and self.coordinator.device_scan_result:
            attrs["register_name"] = self._register_name
            attrs["register_type"] = self._sensor_def["register_type"]

        # Add raw value for diagnostic purposes
        raw_value = self.coordinator.data.get(self._register_name)
        if raw_value is not None and isinstance(raw_value, (int, float)):
            attrs["raw_value"] = raw_value

        return attrs
