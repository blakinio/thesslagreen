"""Enhanced binary sensor platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
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

from .const import DOMAIN, ERROR_CODES, WARNING_CODES
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up enhanced binary sensor platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Get available register sets
    coil_regs = coordinator.available_registers.get("coil_registers", set())
    discrete_regs = coordinator.available_registers.get("discrete_inputs", set())
    input_regs = coordinator.available_registers.get("input_registers", set())
    
    # System status sensors (from coil registers)
    system_sensors = [
        ("system_on_off", "System Power", "mdi:power", BinarySensorDeviceClass.POWER),
        ("constant_flow_active", "Constant Flow", "mdi:chart-line", BinarySensorDeviceClass.RUNNING),
        ("gwc_active", "GWC Active", "mdi:earth", BinarySensorDeviceClass.RUNNING),
        ("bypass_active", "Bypass Active", "mdi:valve", BinarySensorDeviceClass.RUNNING),
        ("comfort_active", "Comfort Mode", "mdi:home-thermometer", BinarySensorDeviceClass.RUNNING),
        ("antifreeze_mode", "Antifreeze Protection", "mdi:snowflake-alert", BinarySensorDeviceClass.SAFETY),
        ("summer_mode", "Summer Mode", "mdi:weather-sunny", BinarySensorDeviceClass.RUNNING),
        ("preheating_active", "Preheating", "mdi:radiator", BinarySensorDeviceClass.HEAT),
        ("cooling_active", "Cooling", "mdi:snowflake", BinarySensorDeviceClass.COLD),
        ("night_cooling_active", "Night Cooling", "mdi:weather-night", BinarySensorDeviceClass.COLD),
    ]
    
    for sensor_key, name, icon, device_class in system_sensors:
        if sensor_key in coil_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class, "coil"
                )
            )
    
    # Maintenance and alarm sensors (from coil registers)
    maintenance_sensors = [
        ("filter_warning", "Filter Warning", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM),
        ("service_required", "Service Required", "mdi:wrench-outline", BinarySensorDeviceClass.PROBLEM),
        ("error_active", "System Error", "mdi:alert-circle", BinarySensorDeviceClass.PROBLEM),
        ("warning_active", "System Warning", "mdi:alert", BinarySensorDeviceClass.PROBLEM),
        ("maintenance_mode", "Maintenance Mode", "mdi:cog", BinarySensorDeviceClass.RUNNING),
    ]
    
    for sensor_key, name, icon, device_class in maintenance_sensors:
        if sensor_key in coil_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class, "coil"
                )
            )
    
    # Component status sensors (from discrete inputs)
    component_sensors = [
        ("outside_temp_sensor_ok", "Outside Temperature Sensor", "mdi:thermometer-check", BinarySensorDeviceClass.CONNECTIVITY),
        ("supply_temp_sensor_ok", "Supply Temperature Sensor", "mdi:thermometer-check", BinarySensorDeviceClass.CONNECTIVITY),
        ("exhaust_temp_sensor_ok", "Exhaust Temperature Sensor", "mdi:thermometer-check", BinarySensorDeviceClass.CONNECTIVITY),
        ("fpx_temp_sensor_ok", "FPX Temperature Sensor", "mdi:thermometer-check", BinarySensorDeviceClass.CONNECTIVITY),
        ("duct_temp_sensor_ok", "Duct Temperature Sensor", "mdi:thermometer-check", BinarySensorDeviceClass.CONNECTIVITY),
        ("gwc_temp_sensor_ok", "GWC Temperature Sensor", "mdi:thermometer-check", BinarySensorDeviceClass.CONNECTIVITY),
        ("ambient_temp_sensor_ok", "Ambient Temperature Sensor", "mdi:thermometer-check", BinarySensorDeviceClass.CONNECTIVITY),
        ("heat_exchanger_ok", "Heat Exchanger", "mdi:hvac", BinarySensorDeviceClass.RUNNING),
        ("supply_fan_ok", "Supply Fan", "mdi:fan-chevron-up", BinarySensorDeviceClass.RUNNING),
        ("exhaust_fan_ok", "Exhaust Fan", "mdi:fan-chevron-down", BinarySensorDeviceClass.RUNNING),
        ("preheater_ok", "Preheater", "mdi:radiator", BinarySensorDeviceClass.HEAT),
        ("bypass_motor_ok", "Bypass Motor", "mdi:engine", BinarySensorDeviceClass.RUNNING),
    ]
    
    for sensor_key, name, icon, device_class in component_sensors:
        if sensor_key in discrete_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class, "discrete"
                )
            )
    
    # Enhanced diagnostics sensors (HA 2025.7+ from discrete inputs)
    diagnostic_sensors = [
        ("communication_error", "Communication Error", "mdi:network-off", BinarySensorDeviceClass.CONNECTIVITY),
        ("overheating_protection", "Overheating Protection", "mdi:thermometer-alert", BinarySensorDeviceClass.SAFETY),
        ("freezing_protection", "Freezing Protection", "mdi:snowflake-alert", BinarySensorDeviceClass.SAFETY),
        ("filter_clogged", "Filter Clogged", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM),
        ("power_supply_ok", "Power Supply", "mdi:power-plug", BinarySensorDeviceClass.POWER),
        ("gwc_pump_running", "GWC Pump", "mdi:pump", BinarySensorDeviceClass.RUNNING),
        ("external_heater_active", "External Heater", "mdi:radiator", BinarySensorDeviceClass.HEAT),
        ("external_cooler_active", "External Cooler", "mdi:air-conditioner", BinarySensorDeviceClass.COLD),
        ("humidity_sensor_ok", "Humidity Sensor", "mdi:water-percent", BinarySensorDeviceClass.CONNECTIVITY),
    ]
    
    for sensor_key, name, icon, device_class in diagnostic_sensors:
        if sensor_key in discrete_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class, "discrete"
                )
            )

    # Enhanced error/warning binary sensors based on numeric codes (HA 2025.7+)
    if "error_code" in input_regs:
        entities.append(
            ThesslaGreenErrorBinarySensor(coordinator, "error_code", "System Error Active")
        )
    
    if "warning_code" in input_regs:
        entities.append(
            ThesslaGreenErrorBinarySensor(coordinator, "warning_code", "System Warning Active")
        )

    if entities:
        _LOGGER.debug("Adding %d enhanced binary sensor entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Enhanced ThesslaGreen binary sensor entity."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        device_class: BinarySensorDeviceClass | None,
        register_type: str,
    ) -> None:
        """Initialize the enhanced binary sensor."""
        super().__init__(coordinator)
        self._key = key
        self._register_type = register_type
        
        # Enhanced device info handling
        device_info = coordinator.data.get("device_info", {}) if coordinator.data else {}
        device_name = device_info.get("device_name", f"ThesslaGreen {coordinator.host}")
        
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        return bool(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "register_type": self._register_type,
            "register_key": self._key,
        }
        
        # Add enhanced diagnostics for HA 2025.7+
        if self._register_type == "discrete":
            attributes["sensor_type"] = "status_input"
        elif self._register_type == "coil":
            attributes["sensor_type"] = "control_status"
            
        # Add timestamp for status changes
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


class ThesslaGreenErrorBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Enhanced binary sensor for error/warning codes - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
    ) -> None:
        """Initialize the enhanced error binary sensor."""
        super().__init__(coordinator)
        self._key = key
        
        device_info = coordinator.data.get("device_info", {}) if coordinator.data else {}
        device_name = device_info.get("device_name", f"ThesslaGreen {coordinator.host}")
        
        self._attr_name = name
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}_active"
        
        # Enhanced icons based on error type
        if "error" in key:
            self._attr_icon = "mdi:alert-circle"
        else:
            self._attr_icon = "mdi:alert"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if there's an active error/warning."""
        code = self.coordinator.data.get(self._key)
        if code is None:
            return None
        return code != 0  # 0 means no error/warning

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes with error details."""
        attributes = {}
        
        code = self.coordinator.data.get(self._key, 0)
        attributes["code"] = code
        
        # Enhanced error/warning descriptions
        if self._key == "error_code":
            description = ERROR_CODES.get(code, f"Unknown error ({code})")
            attributes["description"] = description
            attributes["severity"] = "error" if code != 0 else "none"
        elif self._key == "warning_code":
            description = WARNING_CODES.get(code, f"Unknown warning ({code})")
            attributes["description"] = description
            attributes["severity"] = "warning" if code != 0 else "none"
        
        # Enhanced troubleshooting hints (HA 2025.7+)
        if code != 0:
            attributes["troubleshooting_hint"] = self._get_troubleshooting_hint(code)
            
        return attributes

    def _get_troubleshooting_hint(self, code: int) -> str:
        """Provide enhanced troubleshooting hints based on error/warning code."""
        if self._key == "error_code":
            hints = {
                1: "Check outside temperature sensor wiring and connections",
                2: "Check supply air temperature sensor wiring",
                3: "Check exhaust air temperature sensor wiring", 
                4: "Check FPX temperature sensor wiring",
                5: "Check duct temperature sensor wiring",
                6: "Check GWC temperature sensor wiring",
                7: "Check ambient temperature sensor wiring",
                8: "Check supply fan electrical connections and motor",
                9: "Check exhaust fan electrical connections and motor",
                10: "Check Modbus communication cable and settings",
                11: "Check thermal protection and ventilation around unit",
                12: "Check bypass motor operation and position feedback",
                13: "Check GWC pump and water circulation",
                14: "Check preheater electrical connections and safety switches",
                15: "Check cooling system operation and refrigerant levels",
                16: "Check main power supply voltage and connections",
                17: "Unit may require factory reset or firmware update",
                18: "Unit requires professional calibration service",
            }
            return hints.get(code, "Contact technical support for assistance")
        
        elif self._key == "warning_code":
            hints = {
                1: "Replace air filters - check filter access door",
                2: "Schedule professional service inspection",  
                3: "Normal operation in cold weather - monitor performance",
                4: "Consider increasing ventilation or using summer mode",
                5: "Check air filters and heat exchanger cleanliness",
                6: "Verify ventilation duct connections and sealing",
                7: "Check GWC water flow and heat exchanger condition",
                8: "Verify bypass damper operation and calibration",
                9: "Schedule preventive maintenance service",
                10: "Replace or clean air filters - check filter quality",
                11: "Review system settings and usage patterns",
                12: "Check sensor calibration and system balance",
            }
            return hints.get(code, "Monitor system performance and schedule service if needed")
        
        return ""

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self._key in self.coordinator.data
        )