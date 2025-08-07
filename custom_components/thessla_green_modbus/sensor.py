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
        ("supply_flowrate", "Supply Flow Rate", "mdi:fan-plus", "Current supply air flow rate"),
        ("exhaust_flowrate", "Exhaust Flow Rate", "mdi:fan-minus", "Current exhaust air flow rate"),
    ]
    
    for sensor_key, name, icon, description in flow_sensors:
        if sensor_key in input_regs:
            entities.append(
                ThesslaGreenFlowSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Enhanced System Sensors (HA 2025.7+ Compatible)
    system_sensors = [
        ("supply_percentage", "Supply Fan Speed", "mdi:fan", "Supply fan speed percentage", PERCENTAGE),
        ("exhaust_percentage", "Exhaust Fan Speed", "mdi:fan", "Exhaust fan speed percentage", PERCENTAGE),
        ("heat_recovery_efficiency", "Heat Recovery Efficiency", "mdi:percent", "Current heat recovery efficiency", PERCENTAGE),
        ("filter_time_remaining", "Filter Time Remaining", "mdi:air-filter", "Days until filter replacement", UnitOfTime.DAYS),
        ("error_code", "Error Code", "mdi:alert-circle", "Current error code", None),
        ("warning_code", "Warning Code", "mdi:alert", "Current warning code", None),
    ]
    
    for sensor_key, name, icon, description, unit in system_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            if "error" in sensor_key:
                entities.append(
                    ThesslaGreenErrorSensor(coordinator)
                )
            elif "warning" in sensor_key:
                entities.append(
                    ThesslaGreenWarningSensor(coordinator)
                )
            else:
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
    
    _attr_has_entity_name = True  # ✅ FIX: Enable entity naming

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
        self._attr_translation_key = key
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.','_')}_{coordinator.slave_id}_{key}"
        
        # Enhanced device info (HA 2025.7+)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": f"ThesslaGreen AirPack ({coordinator.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": coordinator.device_scan_result.get("device_info", {}).get("firmware", "Unknown")
            if hasattr(coordinator, 'device_scan_result') else "Unknown",
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
            "last_update": getattr(self.coordinator, 'last_update_success_time', self.coordinator.last_update_success),
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
        
        # ✅ FIX: Value is already converted in coordinator, don't divide again
        temp_celsius = raw_value  # Already in °C from coordinator
        
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
            device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
            native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def native_value(self) -> float | None:
        """Return flow rate value."""
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None
        
        # Validate flow rate range
        if 0 <= raw_value <= 1000:
            return raw_value
        
        _LOGGER.warning("Invalid flow rate for %s: %d m³/h", self._key, raw_value)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Enhanced flow context (HA 2025.7+)
        flow = self.native_value
        if flow is not None:
            # Flow categories
            if flow < 50:
                attributes["flow_level"] = "low"
            elif flow < 150:
                attributes["flow_level"] = "medium"
            elif flow < 250:
                attributes["flow_level"] = "high"
            else:
                attributes["flow_level"] = "very_high"
            
            # Calculate percentage of typical max (400 m³/h)
            attributes["flow_percentage"] = round((flow / 400) * 100, 1)
        
        return attributes


class ThesslaGreenErrorSensor(ThesslaGreenBaseSensor):
    """Enhanced error code sensor - HA 2025.7+ Compatible."""

    def __init__(self, coordinator):
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
        attributes["severity"] = "critical" if code != 0 else "none"
        attributes["active"] = code != 0
        
        # Add maintenance recommendations
        if code != 0:
            attributes["requires_service"] = code in [1, 2, 5, 6, 8, 9]
            attributes["requires_reset"] = code in [3, 4, 7]
            
            if code in [1, 2]:
                attributes["category"] = "sensor_failure"
            elif code in [3, 4]:
                attributes["category"] = "communication"
            elif code in [5, 6, 7]:
                attributes["category"] = "hardware"
            else:
                attributes["category"] = "system"
        else:
            attributes["requires_service"] = False
            attributes["requires_reset"] = False
            attributes["category"] = "none"
        
        return attributes


class ThesslaGreenWarningSensor(ThesslaGreenBaseSensor):
    """Enhanced warning code sensor - HA 2025.7+ Compatible."""

    def __init__(self, coordinator):
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
        if self._key == "filter_time_remaining":
            days = self.native_value
            if days is not None:
                if days < 7:
                    attributes["urgency"] = "critical"
                    attributes["action_required"] = "Order replacement filter immediately"
                elif days < 30:
                    attributes["urgency"] = "high"
                    attributes["action_required"] = "Order replacement filter soon"
                elif days < 60:
                    attributes["urgency"] = "medium"
                    attributes["action_required"] = "Plan filter replacement"
                else:
                    attributes["urgency"] = "low"
                    attributes["action_required"] = "No action required"
        
        elif self._key == "heat_recovery_efficiency":
            efficiency = self.native_value
            if efficiency is not None:
                if efficiency > 85:
                    attributes["performance"] = "excellent"
                elif efficiency > 70:
                    attributes["performance"] = "good"
                elif efficiency > 50:
                    attributes["performance"] = "moderate"
                else:
                    attributes["performance"] = "poor"
        
        return attributes