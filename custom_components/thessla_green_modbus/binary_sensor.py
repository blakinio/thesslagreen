"""Binary sensor platform for ThesslaGreen Modbus Integration - FIXED VERSION."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


class DeviceStatusDetector:
    """Smart device status detection using multiple indicators."""
    
    def __init__(self, data: dict) -> None:
        """Initialize detector with coordinator data."""
        self.data = data
    
    def detect_device_status(self) -> bool | None:
        """Detect if device is actually running using multiple indicators."""
        indicators = []
        
        # Primary indicator: official panel register
        panel_mode = self.data.get("on_off_panel_mode")
        if panel_mode is not None:
            indicators.append(("panel_register", bool(panel_mode), 0.4))
        
        # Secondary indicators: actual activity
        fan_power = self.data.get("power_supply_fans")
        if fan_power is not None:
            indicators.append(("fan_power_coil", bool(fan_power), 0.3))
        
        # Ventilation activity indicators
        supply_pct = self.data.get("supply_percentage", 0)
        exhaust_pct = self.data.get("exhaust_percentage", 0)
        if supply_pct > 0 or exhaust_pct > 0:
            indicators.append(("ventilation_active", True, 0.2))
        
        # Air flow indicators
        supply_flow = self.data.get("supply_flowrate", 0) 
        exhaust_flow = self.data.get("exhaust_flowrate", 0)
        if supply_flow > 0 or exhaust_flow > 0:
            indicators.append(("airflow_detected", True, 0.15))
        
        # DAC voltage indicators (fan control signals)
        dac_supply = self.data.get("dac_supply", 0)
        dac_exhaust = self.data.get("dac_exhaust", 0) 
        if dac_supply > 0.5 or dac_exhaust > 0.5:  # Above 0.5V indicates active control
            indicators.append(("fan_voltages", True, 0.1))
        
        if not indicators:
            return None
            
        # Weighted decision
        positive_weight = sum(weight for _, status, weight in indicators if status)
        total_weight = sum(weight for _, _, weight in indicators)
        
        if total_weight == 0:
            return None
            
        confidence = positive_weight / total_weight
        return confidence > 0.3  # Device is ON if >30% confidence


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen binary sensors - FIXED VERSION."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Smart device status sensor (primary)
    entities.append(ThesslaGreenSmartDeviceStatus(coordinator))
    
    # Discrete input sensors
    discrete_inputs = coordinator.available_registers.get("discrete_inputs", set())
    
    discrete_sensors = [
        ("expansion", "Moduł Expansion", "mdi:expansion-card", BinarySensorDeviceClass.CONNECTIVITY),
        ("contamination_sensor", "Czujnik jakości powietrza", "mdi:air-filter", None),
        ("airing_sensor", "Czujnik wilgotności", "mdi:water-percent", BinarySensorDeviceClass.MOISTURE),
        ("fireplace", "Włącznik KOMINEK", "mdi:fireplace", None),
        ("empty_house", "Sygnał PUSTY DOM", "mdi:home-minus", BinarySensorDeviceClass.PRESENCE),
        ("hood_input", "Włącznik OKAP", "mdi:kitchen", None),
        ("fire_alarm", "Alarm pożarowy", "mdi:fire", BinarySensorDeviceClass.SAFETY),
        ("duct_heater_protection", "Zabezpieczenie nagrzewnicy", "mdi:shield-alert", BinarySensorDeviceClass.SAFETY),
        ("ahu_filter_protection", "Zabezpieczenie FPX", "mdi:shield-check", BinarySensorDeviceClass.SAFETY),
        ("dp_ahu_filter_overflow", "Presostat filtrów AHU", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM),
        ("dp_duct_filter_overflow", "Presostat filtra kanałowego", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM),
    ]
    
    for sensor_key, name, icon, device_class in discrete_sensors:
        if sensor_key in discrete_inputs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class
                )
            )
    
    # System status sensors from input registers
    input_registers = coordinator.available_registers.get("input_registers", set())
    
    if "constant_flow_active" in input_registers:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator, "constant_flow_active", "Constant Flow aktywny", 
                "mdi:fan-auto", BinarySensorDeviceClass.RUNNING
            )
        )
    
    if "water_removal_active" in input_registers:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator, "water_removal_active", "HEWR aktywny",
                "mdi:water-pump", BinarySensorDeviceClass.RUNNING
            )
        )
    
    # Coil status sensors  
    coil_registers = coordinator.available_registers.get("coil_registers", set())
    
    coil_sensors = [
        ("power_supply_fans", "Zasilanie wentylatorów", "mdi:power", BinarySensorDeviceClass.POWER),
        ("bypass", "Siłownik bypass", "mdi:valve", None),
        ("gwc", "Przekaźnik GWC", "mdi:heat-pump", BinarySensorDeviceClass.RUNNING),
        ("hood", "Przepustnica okapu", "mdi:kitchen", None),
        ("heating_cable", "Kabel grzejny", "mdi:heating-coil", BinarySensorDeviceClass.HEAT),
        ("duct_water_heater_pump", "Pompa nagrzewnicy", "mdi:pump", BinarySensorDeviceClass.RUNNING),
    ]
    
    for sensor_key, name, icon, device_class in coil_sensors:
        if sensor_key in coil_registers:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class
                )
            )
    
    # Alarm sensors from holding registers
    holding_registers = coordinator.available_registers.get("holding_registers", set())
    
    if "alarm_flag" in holding_registers:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator, "alarm_flag", "Alarmy ostrzeżeń (E)",
                "mdi:alert", BinarySensorDeviceClass.PROBLEM
            )
        )
    
    if "error_flag" in holding_registers:
        entities.append(
            ThesslaGreenBinarySensor(
                coordinator, "error_flag", "Błędy krytyczne (S)",
                "mdi:alert-octagon", BinarySensorDeviceClass.PROBLEM
            )
        )
    
    _LOGGER.debug("Adding %d binary sensor entities", len(entities))
    async_add_entities(entities)


class ThesslaGreenBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """ThesslaGreen binary sensor entity - FIXED."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        sensor_key: str,
        name: str,
        icon: str,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class
        
        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{sensor_key}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.data.get(self._sensor_key)
        if value is None:
            return None
        return bool(value)


class ThesslaGreenSmartDeviceStatus(CoordinatorEntity, BinarySensorEntity):
    """Smart device status sensor using multiple indicators - ENHANCED."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the smart device status sensor."""
        super().__init__(coordinator)
        self._attr_name = "Urządzenie włączone"
        self._attr_icon = "mdi:power"
        self._attr_device_class = BinarySensorDeviceClass.POWER
        
        device_info = coordinator.device_info
        device_name = device_info.get("device_name", "ThesslaGreen")
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_device_status_smart"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the device is on using smart detection."""
        detector = DeviceStatusDetector(self.coordinator.data)
        return detector.detect_device_status()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes for debugging."""
        data = self.coordinator.data
        return {
            "panel_register": data.get("on_off_panel_mode"),
            "fan_power_coil": data.get("power_supply_fans"),
            "supply_percentage": data.get("supply_percentage"),
            "exhaust_percentage": data.get("exhaust_percentage"),
            "supply_flowrate": data.get("supply_flowrate"),
            "exhaust_flowrate": data.get("exhaust_flowrate"),
            "dac_supply_voltage": data.get("dac_supply"),
            "dac_exhaust_voltage": data.get("dac_exhaust"),
            "constant_flow_active": data.get("constant_flow_active"),
            "operating_mode": data.get("mode"),
            "detection_method": "smart_multi_indicator",
        }