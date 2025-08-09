"""COMPLETE Binary sensor entities for ThesslaGreen Modbus Integration - SILVER STANDARD.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
COMPLETE: Wszystkie czujniki binarne z autoscan - tylko dostępne encje
"""
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
        "name": "Pompa obiegowa nagrzewnicy",
        "icon": "mdi:pump",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "bypass": {
        "name": "Bypass",
        "icon": "mdi:pipe-leak",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "coil_registers",
    },
    "info": {
        "name": "Potwierdzenie pracy centrali",
        "icon": "mdi:information",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "power_supply_fans": {
        "name": "Zasilanie wentylatorów",
        "icon": "mdi:fan",
        "device_class": BinarySensorDeviceClass.POWER,
        "register_type": "coil_registers",
    },
    "heating_cable": {
        "name": "Kabel grzejny",
        "icon": "mdi:heating-coil",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "coil_registers",
    },
    "work_permit": {
        "name": "Potwierdzenie pracy (Expansion)",
        "icon": "mdi:check-circle",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "gwc": {
        "name": "GWC",
        "icon": "mdi:pipe",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    "hood": {
        "name": "Okap",
        "icon": "mdi:stove",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "coil_registers",
    },
    
    # System status (from discrete inputs)
    "expansion": {
        "name": "Moduł Expansion",
        "icon": "mdi:expansion-card",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "register_type": "discrete_inputs",
    },
    "contamination_sensor": {
        "name": "Czujnik zanieczyszczenia",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "external_contact_1": {
        "name": "Kontakt zewnętrzny 1",
        "icon": "mdi:electric-switch",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "discrete_inputs",
    },
    "external_contact_2": {
        "name": "Kontakt zewnętrzny 2",
        "icon": "mdi:electric-switch",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "discrete_inputs",
    },
    "external_contact_3": {
        "name": "Kontakt zewnętrzny 3",
        "icon": "mdi:electric-switch",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "discrete_inputs",
    },
    "external_contact_4": {
        "name": "Kontakt zewnętrzny 4",
        "icon": "mdi:electric-switch",
        "device_class": BinarySensorDeviceClass.OPENING,
        "register_type": "discrete_inputs",
    },
    
    # Alarms and errors (from discrete inputs)
    "fire_alarm": {
        "name": "Alarm pożarowy",
        "icon": "mdi:fire",
        "device_class": BinarySensorDeviceClass.SAFETY,
        "register_type": "discrete_inputs",
    },
    "frost_alarm": {
        "name": "Alarm przeciwmrozowy",
        "icon": "mdi:snowflake-alert",
        "device_class": BinarySensorDeviceClass.COLD,
        "register_type": "discrete_inputs",
    },
    "filter_alarm": {
        "name": "Alarm filtra",
        "icon": "mdi:filter-variant-remove",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "maintenance_alarm": {
        "name": "Alarm konserwacji",
        "icon": "mdi:wrench-clock",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "sensor_error": {
        "name": "Błąd czujnika",
        "icon": "mdi:sensor-off",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "communication_error": {
        "name": "Błąd komunikacji",
        "icon": "mdi:wifi-off",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "register_type": "discrete_inputs",
    },
    "fan_error": {
        "name": "Błąd wentylatora",
        "icon": "mdi:fan-off",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "heater_error": {
        "name": "Błąd grzałki",
        "icon": "mdi:heating-coil",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "discrete_inputs",
    },
    "cooler_error": {
        "name": "Błąd chłodnicy",
        "icon": "mdi:snowflake-off",
        "device_class": BinarySensorDeviceClass.COLD,
        "register_type": "discrete_inputs",
    },
    "bypass_error": {
        "name": "Błąd bypass",
        "icon": "mdi:pipe-disconnected",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "gwc_error": {
        "name": "Błąd GWC",
        "icon": "mdi:pipe-wrench",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    "expansion_error": {
        "name": "Błąd modułu Expansion",
        "icon": "mdi:expansion-card-variant",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "register_type": "discrete_inputs",
    },
    
    # Active protection systems (from input registers)
    "frost_protection_active": {
        "name": "Ochrona przeciwmrozowa",
        "icon": "mdi:snowflake-check",
        "device_class": BinarySensorDeviceClass.COLD,
        "register_type": "input_registers",
    },
    "defrost_cycle_active": {
        "name": "Cykl odszraniania",
        "icon": "mdi:snowflake-thermometer",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "summer_bypass_active": {
        "name": "Letni bypass",
        "icon": "mdi:weather-sunny",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "winter_heating_active": {
        "name": "Zimowe grzanie",
        "icon": "mdi:weather-snowy",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "input_registers",
    },
    "night_cooling_active": {
        "name": "Nocne chłodzenie",
        "icon": "mdi:weather-night",
        "device_class": BinarySensorDeviceClass.COLD,
        "register_type": "input_registers",
    },
    "constant_flow_active": {
        "name": "Stały przepływ",
        "icon": "mdi:waves",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "air_quality_control_active": {
        "name": "Kontrola jakości powietrza",
        "icon": "mdi:air-filter",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "humidity_control_active": {
        "name": "Kontrola wilgotności",
        "icon": "mdi:water-percent",
        "device_class": BinarySensorDeviceClass.MOISTURE,
        "register_type": "input_registers",
    },
    "temperature_control_active": {
        "name": "Kontrola temperatury",
        "icon": "mdi:thermometer-auto",
        "device_class": BinarySensorDeviceClass.HEAT,
        "register_type": "input_registers",
    },
    "demand_control_active": {
        "name": "Kontrola na żądanie",
        "icon": "mdi:hand-extended",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "schedule_control_active": {
        "name": "Kontrola harmonogramu",
        "icon": "mdi:calendar-clock",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    "manual_control_active": {
        "name": "Kontrola manualna",
        "icon": "mdi:hand-pointing-up",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "register_type": "input_registers",
    },
    
    # Device main status (from holding registers)
    "on_off_panel_mode": {
        "name": "Zasilanie główne",
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
            _LOGGER.debug("Created binary sensor: %s", sensor_def["name"])
    
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
        self._attr_name = f"{coordinator.device_name} {sensor_definition['name']}"
        self._attr_device_info = coordinator.device_info_dict
        
        # Binary sensor specific attributes
        self._attr_icon = sensor_definition.get("icon")
        self._attr_device_class = sensor_definition.get("device_class")
        
        _LOGGER.debug("Binary sensor initialized: %s (%s)", self._attr_name, register_name)

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