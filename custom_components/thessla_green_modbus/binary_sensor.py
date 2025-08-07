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

from .const import DOMAIN
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
    input_regs = coordinator.available_registers.get("input_registers", set())
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    coil_regs = coordinator.available_registers.get("coil_registers", set())
    discrete_inputs = coordinator.available_registers.get("discrete_inputs", set())
    
    # Enhanced Device Status Binary Sensors (HA 2025.7+ Compatible)
    status_sensors = [
        ("device_status_smart", "Device Status Smart", "mdi:power", BinarySensorDeviceClass.RUNNING, False),
        ("power_supply_fans", "Power Supply Fans", "mdi:fan", BinarySensorDeviceClass.POWER, False),
        ("constant_flow_active", "Constant Flow Active", "mdi:air-filter", BinarySensorDeviceClass.RUNNING, False),
        ("emergency_mode", "Emergency Mode", "mdi:alert-octagon", BinarySensorDeviceClass.SAFETY, True),
        ("alarm_active", "Alarm Active", "mdi:alarm-light", BinarySensorDeviceClass.PROBLEM, True),
        ("service_required", "Service Required", "mdi:wrench", BinarySensorDeviceClass.PROBLEM, True),
    ]
    
    for sensor_key, name, icon, device_class, is_diagnostic in status_sensors:
        if sensor_key in input_regs or sensor_key in coil_regs or sensor_key in discrete_inputs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class, is_diagnostic
                )
            )
    
    # Enhanced Problem Detection Binary Sensors (HA 2025.7+ Compatible)
    problem_sensors = [
        ("error_active", "Error Active", "mdi:alert-circle", BinarySensorDeviceClass.PROBLEM, "error_code"),
        ("warning_active", "Warning Active", "mdi:alert", BinarySensorDeviceClass.PROBLEM, "warning_code"),
        ("filter_warning", "Filter Warning", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM, "filter_time_remaining"),
    ]
    
    for sensor_key, name, icon, device_class, code_key in problem_sensors:
        if code_key in input_regs or code_key in holding_regs:
            entities.append(
                ThesslaGreenProblemSensor(
                    coordinator, sensor_key, name, icon, device_class, code_key
                )
            )
    
    # Enhanced Component Status Binary Sensors (HA 2025.7+ Compatible)
    component_sensors = [
        ("gwc_active", "GWC System Active", "mdi:pipe", BinarySensorDeviceClass.RUNNING, False),
        ("bypass_active", "Bypass Active", "mdi:debug-step-over", BinarySensorDeviceClass.RUNNING, False),
        ("heater_active", "Heater Active", "mdi:radiator", BinarySensorDeviceClass.HEAT, False),
        ("cooler_active", "Cooler Active", "mdi:snowflake", BinarySensorDeviceClass.COLD, False),
        ("humidifier_active", "Humidifier Active", "mdi:water-percent", BinarySensorDeviceClass.MOISTURE, False),
    ]
    
    for sensor_key, name, icon, device_class, is_diagnostic in component_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs or sensor_key in coil_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class, is_diagnostic
                )
            )
    
    # Coil status sensors
    coil_sensors = [
        ("duct_water_heater_pump", "Duct Water Heater Pump", "mdi:pump", BinarySensorDeviceClass.RUNNING, False),
        ("bypass", "Bypass Damper", "mdi:debug-step-over", BinarySensorDeviceClass.OPENING, False),
        ("info", "Info Signal", "mdi:information-outline", BinarySensorDeviceClass.RUNNING, False),
        ("heating_cable", "Heating Cable", "mdi:heating-coil", BinarySensorDeviceClass.HEAT, False),
        ("work_permit", "Work Permit", "mdi:check-circle", BinarySensorDeviceClass.RUNNING, False),
        ("gwc", "GWC Relay", "mdi:pipe", BinarySensorDeviceClass.RUNNING, False),
        ("hood", "Hood Damper", "mdi:chef-hat", BinarySensorDeviceClass.OPENING, False),
    ]
    
    for sensor_key, name, icon, device_class, is_diagnostic in coil_sensors:
        if sensor_key in coil_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class, is_diagnostic
                )
            )
    
    # Discrete input sensors
    discrete_sensors = [
        ("bypass_closed", "Bypass Closed", "mdi:valve-closed", BinarySensorDeviceClass.OPENING, False),
        ("bypass_open", "Bypass Open", "mdi:valve-open", BinarySensorDeviceClass.OPENING, False),
        ("filter_alarm", "Filter Alarm", "mdi:air-filter", BinarySensorDeviceClass.PROBLEM, True),
        ("frost_alarm", "Frost Alarm", "mdi:snowflake-alert", BinarySensorDeviceClass.PROBLEM, True),
        ("fire_alarm", "Fire Alarm", "mdi:fire", BinarySensorDeviceClass.SMOKE, True),
        ("emergency_stop", "Emergency Stop", "mdi:alert-octagon", BinarySensorDeviceClass.SAFETY, True),
        ("external_stop", "External Stop", "mdi:stop-circle", BinarySensorDeviceClass.RUNNING, False),
        ("expansion", "Expansion Module", "mdi:expansion-card", BinarySensorDeviceClass.CONNECTIVITY, False),
    ]
    
    for sensor_key, name, icon, device_class, is_diagnostic in discrete_sensors:
        if sensor_key in discrete_inputs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, device_class, is_diagnostic
                )
            )
    
    if entities:
        _LOGGER.debug("Adding %d enhanced binary sensor entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Enhanced binary sensor for ThesslaGreen devices - HA 2025.7+ Compatible."""
    
    _attr_has_entity_name = True  # ✅ FIX: Enable entity naming

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
        self._attr_translation_key = key
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.','_')}_{coordinator.slave_id}_{key}"
        
        # ✅ FIX: Use EntityCategory enum instead of string
        if is_diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        
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
        
        elif "bypass" in self._key:
            # Add bypass position if available
            bypass_pos = self.coordinator.data.get("bypass_position")
            if bypass_pos is not None:
                attributes["position_percentage"] = bypass_pos
                if bypass_pos == 0:
                    attributes["state"] = "closed"
                elif bypass_pos == 100:
                    attributes["state"] = "fully_open"
                else:
                    attributes["state"] = f"partially_open_{bypass_pos}%"
        
        elif "gwc" in self._key:
            # Add GWC temperature if available
            gwc_temp = self.coordinator.data.get("gwc_temperature")
            if gwc_temp is not None:
                attributes["temperature"] = gwc_temp / 10.0  # Convert from 0.1°C units
        
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
        if self._key == "filter_warning":
            # Filter warning based on days remaining
            days = self.coordinator.data.get(self._code_key)
            if days is None:
                return None
            return days < 30  # Warning when less than 30 days
        else:
            # Error/warning based on code
            code = self.coordinator.data.get(self._code_key)
            if code is None:
                return None
            return code != 0  # Problem exists if code is not 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Add problem details
        if self._key == "filter_warning":
            days = self.coordinator.data.get(self._code_key)
            if days is not None:
                attributes["days_remaining"] = days
                attributes["requires_replacement"] = days < 7
                if days < 7:
                    attributes["urgency"] = "critical"
                    attributes["message"] = "Filter replacement required immediately"
                elif days < 30:
                    attributes["urgency"] = "high"
                    attributes["message"] = "Filter replacement required soon"
                else:
                    attributes["urgency"] = "normal"
                    attributes["message"] = "Filter OK"
        else:
            code = self.coordinator.data.get(self._code_key)
            if code is not None:
                attributes["code"] = code
                if self._key == "error_active":
                    from .const import ERROR_CODES
                    attributes["description"] = ERROR_CODES.get(code, f"Unknown error ({code})")
                    attributes["severity"] = "critical"
                elif self._key == "warning_active":
                    from .const import WARNING_CODES
                    attributes["description"] = WARNING_CODES.get(code, f"Unknown warning ({code})")
                    attributes["severity"] = "warning"
                
                # Add recommended actions
                if code != 0:
                    if code in [1, 2, 5, 6]:  # Hardware failures
                        attributes["action_required"] = "Contact service technician"
                    elif code in [7]:  # Filter alarm
                        attributes["action_required"] = "Replace filter"
                    elif code in [8]:  # Frost protection
                        attributes["action_required"] = "Check heater and temperature sensors"
                    elif code in [3, 4, 11]:  # Communication errors
                        attributes["action_required"] = "Check connections and restart device"
                    else:
                        attributes["action_required"] = "Check system status"
        
        return attributes