"""Binary sensor platform for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_MAPPINGS
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen binary sensors from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    
    # Get binary sensor entity mappings
    binary_sensor_mappings = ENTITY_MAPPINGS.get("binary_sensor", {})
    
    # Create binary sensors for available registers
    for register_name, entity_config in binary_sensor_mappings.items():
        # Check if this register is available in any register type
        is_available = False
        register_type = None
        
        for reg_type, registers in coordinator.available_registers.items():
            if register_name in registers:
                is_available = True
                register_type = reg_type
                break
                
        # If force full register list, check against all registers
        if not is_available and coordinator.force_full_register_list:
            from .const import INPUT_REGISTERS, HOLDING_REGISTERS, COIL_REGISTERS, DISCRETE_INPUTS
            all_registers = {**INPUT_REGISTERS, **HOLDING_REGISTERS, **COIL_REGISTERS, **DISCRETE_INPUTS}
            if register_name in all_registers:
                is_available = True
                register_type = "unknown"
        
        if is_available:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator=coordinator,
                    register_name=register_name,
                    entity_config=entity_config,
                    register_type=register_type,
                )
            )
            _LOGGER.debug("Created binary sensor entity: %s", register_name)
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d binary sensor entities", len(entities))
    else:
        _LOGGER.debug("No binary sensor entities were created")


class ThesslaGreenBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """ThesslaGreen binary sensor entity."""
    
    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        entity_config: Dict[str, Any],
        register_type: Optional[str] = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        
        self.register_name = register_name
        self.entity_config = entity_config
        self.register_type = register_type
        
        # Entity configuration
        self._attr_name = self._generate_entity_name()
        self._attr_unique_id = f"{coordinator.device_name}_{register_name}"
        self._attr_device_info = coordinator.get_device_info()
        
        # Binary sensor configuration
        self._setup_binary_sensor_attributes()
        
        _LOGGER.debug("Initialized binary sensor: %s (register: %s)", self._attr_name, register_name)
    
    def _generate_entity_name(self) -> str:
        """Generate human-readable entity name."""
        # Convert register name to human readable
        name_parts = self.register_name.split("_")
        
        # Common replacements for better readability
        replacements = {
            "duct": "Duct",
            "warter": "Water",
            "heater": "Heater", 
            "pump": "Pump",
            "bypass": "Bypass",
            "info": "Info Signal",
            "power": "Power",
            "supply": "Supply",
            "fans": "Fans",
            "heating": "Heating",
            "cable": "Cable",
            "work": "Work",
            "permit": "Permit",
            "gwc": "GWC",
            "hood": "Hood",
            "cooling": "Cooling",
            "preheating": "Preheating",
            "humidifier": "Humidifier",
            "dehumidifier": "Dehumidifier",
            "air": "Air",
            "damper": "Damper",
            "expansion": "Expansion",
            "output": "Output",
            "defrosting": "Defrosting",
            "active": "Active",
            "summer": "Summer",
            "winter": "Winter",
            "mode": "Mode",
            "filter": "Filter",
            "warning": "Warning",
            "system": "System",
            "alarm": "Alarm",
            "door": "Door",
            "sensor": "Sensor",
            "window": "Window",
            "presence": "Presence",
            "motion": "Motion",
            "smoke": "Smoke",
            "detector": "Detector",
            "fire": "Fire",
            "security": "Security",
            "gas": "Gas",
            "water": "Water",
            "leak": "Leak",
            "vibration": "Vibration",
            "pressure": "Pressure",
            "switch": "Switch",
            "flow": "Flow",
            "temperature": "Temperature",
            "humidity": "Humidity",
            "clogged": "Clogged",
            "maintenance": "Maintenance",
            "required": "Required",
            "remote": "Remote",
            "control": "Control",
            "signal": "Signal",
            "panel": "Panel",
            "lock": "Lock",
            "status": "Status",
            "service": "Service",
            "frost": "Frost",
            "protection": "Protection",
            "auto": "Auto",
            "manual": "Manual",
            "emergency": "Emergency",
            "stop": "Stop",
            "failure": "Failure",
            "communication": "Communication",
            "error": "Error",
            "actuator": "Actuator",
            "ready": "Ready",
        }
        
        # Apply replacements and capitalize
        processed_parts = []
        for part in name_parts:
            if part in replacements:
                processed_parts.append(replacements[part])
            else:
                processed_parts.append(part.capitalize())
        
        return " ".join(processed_parts)
    
    def _setup_binary_sensor_attributes(self) -> None:
        """Setup binary sensor attributes based on entity configuration."""
        # Device class
        if "device_class" in self.entity_config:
            device_class_str = self.entity_config["device_class"]
            try:
                # Try to get device class from BinarySensorDeviceClass enum
                self._attr_device_class = getattr(BinarySensorDeviceClass, device_class_str.upper())
            except AttributeError:
                # Fallback to string for custom device classes
                self._attr_device_class = device_class_str
        
        # Icon
        if "icon" in self.entity_config:
            self._attr_icon = self.entity_config["icon"]
        
        # Entity category for diagnostic sensors
        if any(keyword in self.register_name for keyword in [
            "error", "warning", "communication", "maintenance", "service",
            "power_failure", "sensor_error", "actuator_error", "system_ready"
        ]):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        
        # Entity category for configuration sensors  
        elif any(keyword in self.register_name for keyword in [
            "panel_lock", "auto_manual", "summer_winter"
        ]):
            self._attr_entity_category = EntityCategory.CONFIG
    
    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self.register_name not in self.coordinator.data:
            return None
            
        raw_value = self.coordinator.data[self.register_name]
        
        # Handle None values
        if raw_value is None:
            return None
        
        # Convert to boolean
        return bool(raw_value)
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add register information for diagnostics
        if self._attr_entity_category == EntityCategory.DIAGNOSTIC:
            attributes["register_name"] = self.register_name
            if self.register_type:
                attributes["register_type"] = self.register_type
        
        # Add raw value for debugging
        if self.register_name in self.coordinator.data:
            raw_value = self.coordinator.data[self.register_name]
            if raw_value is not None:
                attributes["raw_value"] = raw_value
        
        # Add last update time
        if self.coordinator.last_successful_update:
            attributes["last_updated"] = self.coordinator.last_successful_update.isoformat()
        
        # Add specific information for certain sensors
        if "relay" in self.register_name or "output" in self.register_name:
            attributes["type"] = "relay_output"
        elif "sensor" in self.register_name or "detector" in self.register_name:
            attributes["type"] = "input_sensor"
        elif "status" in self.register_name:
            attributes["type"] = "status_indicator"
        
        return attributes
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if coordinator is available and register has valid data
        if not self.coordinator.last_update_success:
            return False
            
        # Check if register is in current data
        if self.register_name not in self.coordinator.data:
            return False
            
        return True