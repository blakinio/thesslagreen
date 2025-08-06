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
from homeassistant.helpers.entity import EntityCategory
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
                    coordinator, sensor_key, name, icon, device_class
                )
            )
    
    # Enhanced Status Sensors (from discrete inputs) - HA 2025.7+ Compatible
    status_sensors = [
        ("supply_fan_status", "Supply Fan Status", "mdi:fan", BinarySensorDeviceClass.RUNNING),
        ("exhaust_fan_status", "Exhaust Fan Status", "mdi:fan-minus", BinarySensorDeviceClass.RUNNING),
        ("filter_status", "Filter Status", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM),
        ("sensor_status", "Sensor Status", "mdi:thermometer-alert", BinarySensorDeviceClass.PROBLEM),
        ("communication_status", "Communication Status", "mdi:wifi", BinarySensorDeviceClass.CONNECTIVITY),
        ("maintenance_required", "Maintenance Required", "mdi:wrench", BinarySensorDeviceClass.PROBLEM),
    ]
    
    for sensor_key, name, icon, device_class in status_sensors:
        if sensor_key in discrete_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class, is_diagnostic=True
                )
            )
    
    # Enhanced Problem Detection Sensors (HA 2025.7+)
    if any(reg in coordinator.available_registers.get("holding_registers", set()) 
           for reg in ["error_code", "warning_code"]):
        
        # System error detection
        entities.append(
            ThesslaGreenProblemSensor(
                coordinator, "system_errors", "System Errors", "mdi:alert-circle", 
                BinarySensorDeviceClass.PROBLEM, "error_code"
            )
        )
        
        # System warning detection
        entities.append(
            ThesslaGreenProblemSensor(
                coordinator, "system_warnings", "System Warnings", "mdi:alert", 
                BinarySensorDeviceClass.PROBLEM, "warning_code"
            )
        )
    
    # Enhanced GWC Status Sensors (HA 2025.7+)
    if "gwc_active" in coil_regs:
        entities.append(
            ThesslaGreenGWCSensor(coordinator)
        )
    
    # Enhanced Filter Status Sensor (HA 2025.7+)
    if "filter_time_remaining" in coordinator.available_registers.get("holding_registers", set()):
        entities.append(
            ThesslaGreenFilterSensor(coordinator)
        )

    if entities:
        _LOGGER.debug("Adding %d enhanced binary sensor entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Enhanced binary sensor for ThesslaGreen devices - HA 2025.7+ Compatible."""

    def __init__(
        self, 
        coordinator: ThesslaGreenCoordinator, 
        key: str, 
        name: str, 
        icon: str, 
        device_class: BinarySensorDeviceClass,
        is_diagnostic: bool = False
    ) -> None:
        """Initialize the enhanced binary sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"
        
        # ✅ FIXED: Use EntityCategory enum instead of string
        if is_diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        
        # Enhanced device info (HA 2025.7+)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": f"ThesslaGreen ({coordinator.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": coordinator.device_scan_result.get("device_info", {}).get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        
        # Handle different value types
        if isinstance(value, bool):
            return value
        elif isinstance(value, int):
            return bool(value)
        else:
            return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self.coordinator.data.get(self._key) is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "register_key": self._key,
            "last_update": getattr(self.coordinator, 'last_update_success_time', self.coordinator.last_update_success),
        }
        
        # Add context-specific attributes
        if "fan" in self._key:
            # Add fan speed information if available
            if "supply" in self._key:
                speed = self.coordinator.data.get("supply_percentage")
                if speed is not None:
                    attributes["fan_speed_percentage"] = speed
            elif "exhaust" in self._key:
                speed = self.coordinator.data.get("exhaust_percentage")
                if speed is not None:
                    attributes["fan_speed_percentage"] = speed
        
        elif "filter" in self._key:
            # Add filter time remaining if available
            filter_time = self.coordinator.data.get("filter_time_remaining")
            if filter_time is not None:
                attributes["days_remaining"] = filter_time
                if filter_time < 30:
                    attributes["replacement_urgency"] = "urgent"
                elif filter_time < 60:
                    attributes["replacement_urgency"] = "soon"
                else:
                    attributes["replacement_urgency"] = "normal"
        
        return attributes


class ThesslaGreenProblemSensor(ThesslaGreenBinarySensor):
    """Enhanced problem detection sensor - HA 2025.7+ Compatible."""

    def __init__(
        self, 
        coordinator: ThesslaGreenCoordinator, 
        key: str, 
        name: str, 
        icon: str, 
        device_class: BinarySensorDeviceClass,
        code_key: str
    ) -> None:
        """Initialize the problem sensor."""
        super().__init__(coordinator, key, name, icon, device_class, is_diagnostic=True)
        self._code_key = code_key

    @property
    def is_on(self) -> bool | None:
        """Return true if there are active problems."""
        code = self.coordinator.data.get(self._code_key)
        if code is None:
            return None
        
        # Problem exists if code is not 0
        return code != 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        code = self.coordinator.data.get(self._code_key, 0)
        attributes["problem_code"] = code
        
        if self._code_key == "error_code":
            description = ERROR_CODES.get(code, f"Unknown error ({code})")
            attributes["problem_description"] = description
            attributes["problem_type"] = "error"
            attributes["severity"] = "high" if code != 0 else "none"
            
        elif self._code_key == "warning_code":
            description = WARNING_CODES.get(code, f"Unknown warning ({code})")
            attributes["problem_description"] = description
            attributes["problem_type"] = "warning"
            attributes["severity"] = "medium" if code != 0 else "none"
        
        # Add troubleshooting context
        if code != 0:
            attributes["requires_attention"] = True
            if code in [1, 2, 3, 4, 5, 6, 7]:  # Sensor-related
                attributes["category"] = "sensor"
                attributes["troubleshooting_tip"] = "Check sensor connections and calibration"
            elif code in [8, 9]:  # Fan-related
                attributes["category"] = "fan"
                attributes["troubleshooting_tip"] = "Check fan operation and mechanical parts"
            elif code == 10:  # Communication
                attributes["category"] = "communication"
                attributes["troubleshooting_tip"] = "Check network connection and Modbus settings"
            else:
                attributes["category"] = "system"
                attributes["troubleshooting_tip"] = "Contact technical support for assistance"
        else:
            attributes["requires_attention"] = False
            attributes["category"] = "none"
        
        return attributes


class ThesslaGreenGWCSensor(ThesslaGreenBinarySensor):
    """Enhanced GWC (Ground Heat Exchanger) status sensor - HA 2025.7+ Compatible."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the GWC sensor."""
        super().__init__(
            coordinator, "gwc_operational", "GWC Operational", "mdi:earth-check", 
            BinarySensorDeviceClass.RUNNING
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if GWC is operational."""
        gwc_active = self.coordinator.data.get("gwc_active")
        gwc_mode = self.coordinator.data.get("gwc_mode")
        
        if gwc_active is None:
            return None
        
        # GWC is operational if active and in a working mode
        if not gwc_active:
            return False
        
        if gwc_mode is None:
            return bool(gwc_active)
        
        # Mode 0 = Inactive, Mode 1 = Winter, Mode 2 = Summer
        return gwc_mode in [1, 2]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        gwc_active = self.coordinator.data.get("gwc_active", False)
        gwc_mode = self.coordinator.data.get("gwc_mode")
        
        attributes["gwc_enabled"] = gwc_active
        
        if gwc_mode is not None:
            mode_names = {0: "Inactive", 1: "Winter", 2: "Summer"}
            attributes["gwc_mode"] = mode_names.get(gwc_mode, "Unknown")
            
            if gwc_mode == 1:
                attributes["operation_purpose"] = "Preheating incoming air"
            elif gwc_mode == 2:
                attributes["operation_purpose"] = "Precooling incoming air"
            else:
                attributes["operation_purpose"] = "Not operational"
        
        # Add GWC temperature information if available
        gwc_temp = self.coordinator.data.get("gwc_temperature")
        if gwc_temp is not None:
            attributes["gwc_temperature"] = round(gwc_temp / 10.0, 1)
        
        outside_temp = self.coordinator.data.get("outside_temperature")
        if outside_temp is not None:
            attributes["outside_temperature"] = round(outside_temp / 10.0, 1)
            
            # Calculate GWC effectiveness if both temperatures available
            if gwc_temp is not None:
                temp_diff = abs((gwc_temp - outside_temp) / 10.0)
                attributes["temperature_difference"] = round(temp_diff, 1)
                
                if temp_diff > 5:
                    attributes["effectiveness"] = "high"
                elif temp_diff > 2:
                    attributes["effectiveness"] = "medium"
                else:
                    attributes["effectiveness"] = "low"
        
        return attributes


class ThesslaGreenFilterSensor(ThesslaGreenBinarySensor):
    """Enhanced filter status sensor - HA 2025.7+ Compatible."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the filter sensor."""
        super().__init__(
            coordinator, "filter_replacement_needed", "Filter Replacement Needed", 
            "mdi:air-filter-outline", BinarySensorDeviceClass.PROBLEM, is_diagnostic=True
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if filter replacement is needed."""
        filter_time = self.coordinator.data.get("filter_time_remaining")
        if filter_time is None:
            return None
        
        # Filter replacement needed if less than 7 days remaining
        return filter_time <= 7

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        filter_time = self.coordinator.data.get("filter_time_remaining")
        if filter_time is not None:
            attributes["days_remaining"] = filter_time
            attributes["weeks_remaining"] = round(filter_time / 7, 1)
            attributes["months_remaining"] = round(filter_time / 30, 1)
            
            # Filter status categories
            if filter_time <= 0:
                attributes["filter_status"] = "overdue"
                attributes["replacement_urgency"] = "critical"
            elif filter_time <= 7:
                attributes["filter_status"] = "replace_now"
                attributes["replacement_urgency"] = "urgent"
            elif filter_time <= 30:
                attributes["filter_status"] = "replace_soon"
                attributes["replacement_urgency"] = "soon"
            elif filter_time <= 60:
                attributes["filter_status"] = "monitor"
                attributes["replacement_urgency"] = "normal"
            else:
                attributes["filter_status"] = "good"
                attributes["replacement_urgency"] = "none"
        
        # Add filter change interval information
        filter_interval = self.coordinator.data.get("filter_change_interval")
        if filter_interval is not None:
            attributes["filter_change_interval"] = filter_interval
            
            # Calculate filter usage percentage
            if filter_time is not None:
                usage_percent = ((filter_interval - filter_time) / filter_interval) * 100
                attributes["filter_usage_percent"] = round(max(0, min(100, usage_percent)), 1)
        
        # Add maintenance tips
        if filter_time is not None:
            if filter_time <= 7:
                attributes["maintenance_tip"] = "Replace filter immediately to maintain air quality"
            elif filter_time <= 30:
                attributes["maintenance_tip"] = "Order replacement filter and schedule maintenance"
            else:
                attributes["maintenance_tip"] = "Filter condition is good"
        
        return attributes