"""Enhanced sensor platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
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
    """Set up enhanced sensor platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Get available register sets
    input_regs = coordinator.available_registers.get("input_registers", set())
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # Enhanced Temperature Sensors (HA 2025.7+ Compatible)
    temperature_sensors = [
        ("outside_temperature", "Outside Temperature", "mdi:thermometer", "Current outdoor air temperature"),
        ("supply_temperature", "Supply Temperature", "mdi:thermometer-lines", "Temperature of supply air"),
        ("exhaust_temperature", "Exhaust Temperature", "mdi:thermometer-minus", "Temperature of exhaust air"),
        ("fpx_temperature", "FPX Temperature", "mdi:thermometer-alert", "Temperature of heat exchanger"),
        ("duct_supply_temperature", "Duct Supply Temperature", "mdi:thermometer-lines", "Temperature in supply duct"),
        ("gwc_temperature", "GWC Temperature", "mdi:earth-thermometer", "Ground Heat Exchanger temperature"),
        ("ambient_temperature", "Ambient Temperature", "mdi:home-thermometer", "Indoor ambient temperature"),
    ]
    
    for sensor_key, name, icon, description in temperature_sensors:
        if sensor_key in input_regs:
            entities.append(
                ThesslaGreenTemperatureSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Enhanced Flow Sensors (HA 2025.7+ Compatible)
    flow_sensors = [
        ("supply_flowrate", "Supply Flow Rate", "mdi:fan", "Current supply air flow rate"),
        ("exhaust_flowrate", "Exhaust Flow Rate", "mdi:fan-minus", "Current exhaust air flow rate"),
        ("supply_air_flow", "Supply Air Flow", "mdi:air-filter", "Total supply air volume"),
        ("exhaust_air_flow", "Exhaust Air Flow", "mdi:air-filter", "Total exhaust air volume"),
    ]
    
    for sensor_key, name, icon, description in flow_sensors:
        if sensor_key in input_regs:
            entities.append(
                ThesslaGreenFlowSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Enhanced Performance Sensors (HA 2025.7+ Compatible)
    performance_sensors = [
        ("supply_percentage", "Supply Fan Speed", "mdi:fan-speed-1", "Current supply fan speed percentage"),
        ("exhaust_percentage", "Exhaust Fan Speed", "mdi:fan-speed-2", "Current exhaust fan speed percentage"),
        ("heat_recovery_efficiency", "Heat Recovery Efficiency", "mdi:percent", "Current heat recovery efficiency"),
        ("filter_efficiency", "Filter Efficiency", "mdi:air-filter-outline", "Current filter efficiency"),
        ("actual_power_consumption", "Power Consumption", "mdi:flash", "Actual power consumption"),
    ]
    
    for sensor_key, name, icon, description in performance_sensors:
        if sensor_key in input_regs:
            entities.append(
                ThesslaGreenPerformanceSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Enhanced System Status Sensors (HA 2025.7+ Compatible)
    if "error_code" in holding_regs:
        entities.append(ThesslaGreenErrorSensor(coordinator))
    
    if "warning_code" in holding_regs:
        entities.append(ThesslaGreenWarningSensor(coordinator))
    
    # Enhanced Device Information Sensors (HA 2025.7+ Compatible) 
    device_sensors = [
        ("firmware_version", "Firmware Version", "mdi:chip", "Device firmware version", None),
        ("device_serial", "Serial Number", "mdi:barcode", "Device serial number", None),
        ("operating_hours", "Operating Hours", "mdi:clock", "Total operating hours", UnitOfTime.HOURS),
        ("filter_time_remaining", "Filter Time Remaining", "mdi:air-filter", "Remaining filter life", UnitOfTime.DAYS),
    ]
    
    for sensor_key, name, icon, description, unit in device_sensors:
        if sensor_key in holding_regs:
            entities.append(
                ThesslaGreenDeviceSensor(
                    coordinator, sensor_key, name, icon, description, unit
                )
            )

    if entities:
        _LOGGER.debug("Adding %d enhanced sensor entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for ThesslaGreen devices - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"
        
        # Enhanced device info (HA 2025.7+)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": f"ThesslaGreen ({coordinator.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": coordinator.device_scan_result.get("device_info", {}).get("firmware", "Unknown"),
        }

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        return self.coordinator.data.get(self._key)

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
        return {
            "last_update": self.coordinator.last_update_success_time,
            "coordinator_update_interval": self.coordinator.update_interval.total_seconds(),
        }


class ThesslaGreenTemperatureSensor(ThesslaGreenBaseSensor):
    """Enhanced temperature sensor - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, description):
        """Initialize the temperature sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Enhanced entity description for temperature sensors (HA 2025.7+)
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def native_value(self) -> float | None:
        """Return temperature value."""
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None
        
        # Convert from device units (0.1°C) to Celsius
        temp_celsius = raw_value / 10.0
        
        # Validate reasonable temperature range
        if -50.0 <= temp_celsius <= 100.0:
            return round(temp_celsius, 1)
        
        _LOGGER.warning("Invalid temperature reading for %s: %.1f°C", self._key, temp_celsius)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced temperature context (HA 2025.7+)
        temp = self.native_value
        if temp is not None:
            # Temperature categories for user context
            if temp < 0:
                attributes["temperature_category"] = "freezing"
            elif temp < 10:
                attributes["temperature_category"] = "cold"
            elif temp < 20:
                attributes["temperature_category"] = "cool"
            elif temp < 25:
                attributes["temperature_category"] = "comfortable"
            elif temp < 30:
                attributes["temperature_category"] = "warm"
            else:
                attributes["temperature_category"] = "hot"
        
        # Add sensor-specific context
        if "outside" in self._key:
            attributes["sensor_type"] = "outdoor"
        elif "supply" in self._key:
            attributes["sensor_type"] = "supply_air"
        elif "exhaust" in self._key:
            attributes["sensor_type"] = "exhaust_air"
        else:
            attributes["sensor_type"] = "system"
        
        return attributes


class ThesslaGreenFlowSensor(ThesslaGreenBaseSensor):
    """Enhanced flow sensor - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, description):
        """Initialize the flow sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Enhanced entity description for flow sensors (HA 2025.7+)
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def native_value(self) -> float | None:
        """Return flow value in m³/h."""
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None
        
        # Flow values are typically in m³/h, validate range
        if 0 <= raw_value <= 1000:
            return round(float(raw_value), 1)
        
        _LOGGER.warning("Invalid flow reading for %s: %d m³/h", self._key, raw_value)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced flow context (HA 2025.7+)
        flow = self.native_value
        if flow is not None:
            # Flow categories for typical home units
            if flow < 50:
                attributes["flow_category"] = "low"
            elif flow < 150:
                attributes["flow_category"] = "medium"
            elif flow < 300:
                attributes["flow_category"] = "high"
            else:
                attributes["flow_category"] = "very_high"
        
        # Add ventilation context
        if "supply" in self._key:
            attributes["flow_type"] = "supply"
            # Get target flow if available
            target_flow = self.coordinator.data.get("supply_air_flow_target")
            if target_flow is not None:
                attributes["target_flow"] = target_flow
                if flow is not None:
                    attributes["flow_error"] = round(flow - target_flow, 1)
        elif "exhaust" in self._key:
            attributes["flow_type"] = "exhaust"
            target_flow = self.coordinator.data.get("exhaust_air_flow_target")
            if target_flow is not None:
                attributes["target_flow"] = target_flow
                if flow is not None:
                    attributes["flow_error"] = round(flow - target_flow, 1)
        
        return attributes


class ThesslaGreenPerformanceSensor(ThesslaGreenBaseSensor):
    """Enhanced performance sensor - HA 2025.7+ Compatible."""

    def __init__(self, coordinator, key, name, icon, description):
        """Initialize the performance sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Enhanced entity description for performance sensors (HA 2025.7+)
        if "percentage" in key or "efficiency" in key:
            unit = PERCENTAGE
        elif "power" in key:
            unit = "W"
        else:
            unit = None
            
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def native_value(self) -> float | None:
        """Return performance value."""
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None
        
        # Percentage values (0-100%)
        if "percentage" in self._key or "efficiency" in self._key:
            if 0 <= raw_value <= 100:
                return round(float(raw_value), 1)
        # Power consumption values
        elif "power" in self._key:
            if 0 <= raw_value <= 5000:  # Reasonable power range
                return round(float(raw_value), 1)
        else:
            return round(float(raw_value), 2)
        
        _LOGGER.warning("Invalid performance reading for %s: %s", self._key, raw_value)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced performance context (HA 2025.7+)
        value = self.native_value
        if value is not None:
            if "percentage" in self._key:
                if value < 25:
                    attributes["performance_level"] = "low"
                elif value < 50:
                    attributes["performance_level"] = "medium"
                elif value < 75:
                    attributes["performance_level"] = "high" 
                else:
                    attributes["performance_level"] = "maximum"
                    
                # Add fan context
                if "supply" in self._key:
                    attributes["fan_type"] = "supply"
                elif "exhaust" in self._key:
                    attributes["fan_type"] = "exhaust"
                    
            elif "efficiency" in self._key:
                if value < 50:
                    attributes["efficiency_level"] = "poor"
                elif value < 70:
                    attributes["efficiency_level"] = "fair"
                elif value < 85:
                    attributes["efficiency_level"] = "good"
                else:
                    attributes["efficiency_level"] = "excellent"
                    
            elif "power" in self._key:
                if value < 50:
                    attributes["power_level"] = "low"
                elif value < 200:
                    attributes["power_level"] = "medium"
                elif value < 500:
                    attributes["power_level"] = "high"
                else:
                    attributes["power_level"] = "very_high"
        
        return attributes


class ThesslaGreenErrorSensor(ThesslaGreenBaseSensor):
    """Enhanced error code sensor - HA 2025.7+ Compatible."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the error sensor."""
        super().__init__(coordinator, "error_code", "Error Code", "mdi:alert-circle", "Current system error code")
        
        # Enhanced entity description for error sensors (HA 2025.7+)
        self.entity_description = SensorEntityDescription(
            key="error_code",
            name="Error Code",
            icon="mdi:alert-circle",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced error context (HA 2025.7+)
        code = self.native_value or 0
        
        description = ERROR_CODES.get(code, f"Unknown error ({code})")
        attributes["description"] = description
        attributes["severity"] = "error" if code != 0 else "none"
        attributes["active"] = code != 0
        
        # Add troubleshooting information
        if code != 0:
            attributes["requires_attention"] = True
            if code in [1, 2, 3, 4, 5, 6, 7]:  # Sensor errors
                attributes["category"] = "sensor"
            elif code in [8, 9]:  # Fan errors
                attributes["category"] = "fan"
            elif code == 10:  # Communication error
                attributes["category"] = "communication"
            else:
                attributes["category"] = "system"
        else:
            attributes["requires_attention"] = False
            attributes["category"] = "none"
        
        return attributes


class ThesslaGreenWarningSensor(ThesslaGreenBaseSensor):
    """Enhanced warning code sensor - HA 2025.7+ Compatible."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the warning sensor."""
        super().__init__(coordinator, "warning_code", "Warning Code", "mdi:alert", "Current system warning code")
        
        # Enhanced entity description for warning sensors (HA 2025.7+)
        self.entity_description = SensorEntityDescription(
            key="warning_code",
            name="Warning Code",
            icon="mdi:alert",
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced warning context (HA 2025.7+)
        code = self.native_value or 0
        
        description = WARNING_CODES.get(code, f"Unknown warning ({code})")
        attributes["description"] = description
        attributes["severity"] = "warning" if code != 0 else "none"
        attributes["active"] = code != 0
        
        # Add maintenance context
        if code != 0:
            attributes["requires_attention"] = True
            if code in [1, 2]:  # Maintenance warnings
                attributes["category"] = "maintenance"
            elif code in [3, 4]:  # Temperature warnings
                attributes["category"] = "temperature"
            elif code in [5, 6]:  # Performance warnings
                attributes["category"] = "performance"
            else:
                attributes["category"] = "system"
        else:
            attributes["requires_attention"] = False
            attributes["category"] = "none"
        
        return attributes


class ThesslaGreenDeviceSensor(ThesslaGreenBaseSensor):
    """Enhanced device information sensor - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str | None,
    ) -> None:
        """Initialize the enhanced device sensor."""
        super().__init__(coordinator, key, name, icon, description)
        
        # Enhanced entity description for device sensors (HA 2025.7+)
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            icon=icon,
            native_unit_of_measurement=unit,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced device context (HA 2025.7+)
        if self._key == "firmware_version":
            fw_version = self.native_value
            if fw_version:
                try:
                    # Parse version for comparison
                    major, minor = fw_version.split('.')[:2]
                    attributes["firmware_major"] = int(major)
                    attributes["firmware_minor"] = int(minor)
                    
                    # Version recommendations
                    if int(major) < 4:
                        attributes["update_recommended"] = True
                        attributes["update_reason"] = "Old firmware version"
                    else:
                        attributes["update_recommended"] = False
                        
                except (ValueError, IndexError):
                    attributes["version_parsed"] = False
                    
        elif self._key == "operating_hours":
            hours = self.native_value
            if hours is not None:
                attributes["operating_days"] = round(hours / 24, 1)
                attributes["operating_years"] = round(hours / (24 * 365), 2)
                
                # Maintenance intervals
                if hours > 8760:  # 1 year
                    attributes["maintenance_due"] = True
                else:
                    attributes["maintenance_due"] = False
                    
        elif self._key == "filter_time_remaining":
            days = self.native_value
            if days is not None:
                attributes["weeks_remaining"] = round(days / 7, 1)
                attributes["months_remaining"] = round(days / 30, 1)
                
                # Filter replacement warnings
                if days < 30:
                    attributes["replacement_urgency"] = "urgent"
                elif days < 60:
                    attributes["replacement_urgency"] = "soon"
                else:
                    attributes["replacement_urgency"] = "normal"
        
        return attributes