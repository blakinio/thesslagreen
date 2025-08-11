"""Binary sensors for the ThesslaGreen Modbus integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Complete binary sensor definitions
BINARY_SENSOR_DEFINITIONS = {
    # System status (from coil registers)
    "duct_water_heater_pump": {
        "translation_key": "duct_water_heater_pump",
        "icon": "mdi:pump",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "bypass": {
        "translation_key": "bypass",
        "icon": "mdi:pipe-leak",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "coil_registers",
    },
    "info": {
        "translation_key": "info",
        "icon": "mdi:information",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "power_supply_fans": {
        "translation_key": "power_supply_fans",
        "icon": "mdi:fan",
        "device_class": BinarySensorDeviceClass.POWER,
        "register_type": "coil_registers",
    },
    "heating_cable": {
        "translation_key": "heating_cable",
        "icon": "mdi:heating-coil",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "coil_registers",
    },
    "work_permit": {
        "translation_key": "work_permit",
        "icon": "mdi:check-circle",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "gwc": {
        "translation_key": "gwc",
        "icon": "mdi:pipe",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "hood": {
        "translation_key": "hood",
        "icon": "mdi:stove",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    
    # System status (from discrete inputs)
    "expansion": {
        "translation_key": "expansion",
        "icon": "mdi:expansion-card",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "register_type": "discrete_inputs",
    },
    "contamination_sensor": {
        "translation_key": "contamination_sensor",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "external_contact_1": {
        "translation_key": "external_contact_1",
        "icon": "mdi:electric-switch",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "discrete_inputs",
    },
    "external_contact_2": {
        "translation_key": "external_contact_2",
        "icon": "mdi:electric-switch",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "discrete_inputs",
    },
    "external_contact_3": {
        "translation_key": "external_contact_3",
        "icon": "mdi:electric-switch",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "discrete_inputs",
    },
    "external_contact_4": {
        "translation_key": "external_contact_4",
        "icon": "mdi:electric-switch",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "discrete_inputs",
    },
    
    # Alarms and errors (from discrete inputs)
    "fire_alarm": {
        "translation_key": "fire_alarm",
        "icon": "mdi:fire",
        "device_class": BinarySensorDeviceClass.SAFETY,
        "register_type": "discrete_inputs",
    },
    "frost_alarm": {
        "translation_key": "frost_alarm",
        "icon": "mdi:snowflake-alert",
        "device_class": BinarySensorDeviceClass.COLD,
        "register_type": "discrete_inputs",
    },
    "filter_alarm": {
        "translation_key": "filter_alarm",
        "icon": "mdi:filter-variant-remove",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "maintenance_alarm": {
        "translation_key": "maintenance_alarm",
        "icon": "mdi:wrench-clock",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "sensor_error": {
        "translation_key": "sensor_error",
        "icon": "mdi:sensor-off",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "communication_error": {
        "translation_key": "communication_error",
        "icon": "mdi:wifi-off",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "register_type": "discrete_inputs",
    },
    "fan_error": {
        "translation_key": "fan_error",
        "icon": "mdi:fan-off",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "heater_error": {
        "translation_key": "heater_error",
        "icon": "mdi:heating-coil",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "discrete_inputs",
    },
    "cooler_error": {
        "translation_key": "cooler_error",
        "icon": "mdi:snowflake-off",
        "device_class": BinarySensorDeviceClass.COLD,
        "register_type": "discrete_inputs",
    },
    "bypass_error": {
        "translation_key": "bypass_error",
        "icon": "mdi:pipe-disconnected",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "gwc_error": {
        "translation_key": "gwc_error",
        "icon": "mdi:pipe-wrench",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "expansion_error": {
        "translation_key": "expansion_error",
        "icon": "mdi:expansion-card-variant",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    
    # Active protection systems (from input registers)
    "frost_protection_active": {
        "translation_key": "frost_protection_active",
        "icon": "mdi:snowflake-check",
        "device_class": BinarySensorDeviceClass.COLD,
        "register_type": "input_registers",
    },
    "defrost_cycle_active": {
        "translation_key": "defrost_cycle_active",
        "icon": "mdi:snowflake-thermometer",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "summer_bypass_active": {
        "translation_key": "summer_bypass_active",
        "icon": "mdi:weather-sunny",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "winter_heating_active": {
        "translation_key": "winter_heating_active",
        "icon": "mdi:weather-snowy",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "input_registers",
    },
    "night_cooling_active": {
        "translation_key": "night_cooling_active",
        "icon": "mdi:weather-night",
        "device_class": BinarySensorDeviceClass.COLD,
        "register_type": "input_registers",
    },
    "constant_flow_active": {
        "translation_key": "constant_flow_active",
        "icon": "mdi:waves",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "air_quality_control_active": {
        "translation_key": "air_quality_control_active",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "humidity_control_active": {
        "translation_key": "humidity_control_active",
        "icon": "mdi:water-percent",
        "device_class": BinarySensorDeviceClass.MOISTURE,
        "register_type": "input_registers",
    },
    "temperature_control_active": {
        "translation_key": "temperature_control_active",
        "icon": "mdi:thermometer-auto",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "input_registers",
    },
    "demand_control_active": {
        "translation_key": "demand_control_active",
        "icon": "mdi:hand-extended",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "schedule_control_active": {
        "translation_key": "schedule_control_active",
        "icon": "mdi:calendar-clock",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "manual_control_active": {
        "translation_key": "manual_control_active",
        "icon": "mdi:hand-pointing-up",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    
    # Device main status (from holding registers)
    "on_off_panel_mode": {
        "translation_key": "on_off_panel_mode",
        "icon": "mdi:power",
        "device_class": BinarySensorDeviceClass.POWER,
        "register_type": "holding_registers",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen binary sensor entities based on available registers."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Create binary sensors only for available registers (autoscan result)
    for register_name, sensor_def in BINARY_SENSOR_DEFINITIONS.items():
        register_type = sensor_def["register_type"]
        
        # Check if this register is available on the device
        if register_name in coordinator.available_registers.get(register_type, set()):
            entities.append(ThesslaGreenBinarySensor(coordinator, register_name, sensor_def))
            _LOGGER.debug("Created binary sensor: %s", sensor_def["translation_key"])
    
    if entities:
        async_add_entities(entities, True)
        _LOGGER.info("Created %d binary sensor entities for %s", len(entities), coordinator.device_name)
    else:
        _LOGGER.warning("No binary sensor entities created - no compatible registers found")


class ThesslaGreenBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor entity for ThesslaGreen device."""

    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        sensor_definition: Dict[str, Any],
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        
        self._register_name = register_name
        self._sensor_def = sensor_definition

        # Entity attributes
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{register_name}"
        self._attr_device_info = coordinator.get_device_info()

        # Binary sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        self._attr_device_class = sensor_definition.get("device_class")

        # Translation setup
        self._attr_translation_key = sensor_definition.get("translation_key")
        self._attr_has_entity_name = True

        _LOGGER.debug(
            "Binary sensor initialized: %s (%s)",
            sensor_definition.get("translation_key"),
            register_name,
        )

    @property
    def is_on(self) -> Optional[bool]:
        """Return True if the binary sensor is on."""
        value = self.coordinator.data.get(self._register_name)
        
        if value is None:
            return None
        
        # Handle different register types
        register_type = self._sensor_def["register_type"]
        
        if register_type in ["coil_registers", "discrete_inputs"]:
            # Coils and discrete inputs are already boolean
            return bool(value)
        
        elif register_type == "input_registers":
            # Input registers: 1 = active/on, 0 = inactive/off
            return bool(value)
        
        elif register_type == "holding_registers":
            # Holding registers: depends on register
            if self._register_name == "on_off_panel_mode":
                return bool(value)
            else:
                return bool(value)
        
        return False

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
        
        # Add register information for debugging
        if hasattr(self.coordinator, 'device_scan_result') and self.coordinator.device_scan_result:
            attrs["register_name"] = self._register_name
            attrs["register_type"] = self._sensor_def["register_type"]
        
        # Add raw value for diagnostic purposes
        raw_value = self.coordinator.data.get(self._register_name)
        if raw_value is not None:
            attrs["raw_value"] = raw_value
        
        # Add specific information for alarm/error sensors
        if "alarm" in self._register_name or "error" in self._register_name:
            attrs["severity"] = "warning" if self.is_on else "normal"
        
        return attrs

    @property
    def icon(self) -> str:
        """Return the icon for the binary sensor."""
        base_icon = self._attr_icon
        
        # Dynamic icon changes for certain sensors
        if self._register_name in ["bypass", "gwc", "power_supply_fans", "heating_cable"]:
            if self.is_on:
                return base_icon
            else:
                # Return "off" version of icon
                if "fan" in base_icon:
                    return base_icon.replace("fan", "fan-off")
                elif "heating" in base_icon:
                    return "mdi:heating-coil-off"
                elif "pipe" in base_icon:
                    return "mdi:pipe-disconnected"
        
        # Dynamic icon for alarms and errors
        if "alarm" in self._register_name or "error" in self._register_name:
            if self.is_on:
                return "mdi:alert-circle"
            else:
                return "mdi:check-circle"
        
        return base_icon