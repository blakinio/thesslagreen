"""POPRAWIONY Sensor platform for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
FIX: _attr_device_class AttributeError, sensor setup errors
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumetricFlux,
    UnitOfPressure,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_MAPPINGS
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Unit mappings for HA 2025.* compatibility
UNIT_MAPPINGS = {
    "°C": UnitOfTemperature.CELSIUS,
    "celsius": UnitOfTemperature.CELSIUS,
    "temperature": UnitOfTemperature.CELSIUS,
    "%": PERCENTAGE,
    "percent": PERCENTAGE,
    "percentage": PERCENTAGE,
    "m³/h": UnitOfVolumetricFlux.CUBIC_METERS_PER_HOUR,
    "m3/h": UnitOfVolumetricFlux.CUBIC_METERS_PER_HOUR,
    "l/s": UnitOfVolumetricFlux.LITERS_PER_SECOND,
    "Pa": UnitOfPressure.PA,
    "pascal": UnitOfPressure.PA,
    "kPa": UnitOfPressure.KPA,
    "hPa": UnitOfPressure.HPA,
    "mbar": UnitOfPressure.MBAR,
    "bar": UnitOfPressure.BAR,
    "h": UnitOfTime.HOURS,
    "hours": UnitOfTime.HOURS,
    "min": UnitOfTime.MINUTES,
    "minutes": UnitOfTime.MINUTES,
    "s": UnitOfTime.SECONDS,
    "seconds": UnitOfTime.SECONDS,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "kwh": UnitOfEnergy.KILO_WATT_HOUR,
    "Wh": UnitOfEnergy.WATT_HOUR,
    "wh": UnitOfEnergy.WATT_HOUR,
    "W": UnitOfPower.WATT,
    "watt": UnitOfPower.WATT,
    "kW": UnitOfPower.KILO_WATT,
    "kilowatt": UnitOfPower.KILO_WATT,
    "A": UnitOfElectricCurrent.AMPERE,
    "ampere": UnitOfElectricCurrent.AMPERE,
    "V": UnitOfElectricPotential.VOLT,
    "volt": UnitOfElectricPotential.VOLT,
    "ppm": "ppm",
    "rpm": "rpm",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """POPRAWIONE: Set up ThesslaGreen sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    
    # Get sensor entity mappings
    sensor_mappings = ENTITY_MAPPINGS.get("sensor", {})
    
    # Create sensors for available registers
    for register_name, entity_config in sensor_mappings.items():
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
                register_type = "unknown"  # Will be determined at runtime
        
        if is_available:
            entities.append(
                ThesslaGreenSensor(
                    coordinator=coordinator,
                    register_name=register_name,
                    entity_config=entity_config,
                    register_type=register_type,
                )
            )
            _LOGGER.debug("Created sensor entity: %s", register_name)
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d sensor entities", len(entities))
    else:
        _LOGGER.warning("No sensor entities were created - check device connectivity")


class ThesslaGreenSensor(CoordinatorEntity, SensorEntity):
    """POPRAWIONY ThesslaGreen sensor entity z naprawionymi atrybutami."""
    
    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        entity_config: Dict[str, Any],
        register_type: Optional[str] = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self.register_name = register_name
        self.entity_config = entity_config
        self.register_type = register_type
        
        # Entity configuration
        self._attr_name = self._generate_entity_name()
        self._attr_unique_id = f"{coordinator.device_name}_{register_name}"
        self._attr_device_info = coordinator.device_info
        
        # POPRAWKA: Initialize attributes before setup
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_native_unit_of_measurement = None
        self._attr_icon = None
        self._attr_entity_category = None
        
        # Sensor configuration
        self._setup_sensor_attributes()
        
        _LOGGER.debug("Initialized sensor: %s (register: %s)", self._attr_name, register_name)
    
    def _generate_entity_name(self) -> str:
        """Generate human-readable entity name."""
        # Use configured name if available
        if "name" in self.entity_config:
            return self.entity_config["name"]
        
        # Convert register name to human readable
        name_parts = self.register_name.split("_")
        
        # Common replacements for better readability
        replacements = {
            "temperature": "Temperature",
            "flowrate": "Flow Rate", 
            "percentage": "Percentage",
            "supply": "Supply",
            "exhaust": "Exhaust",
            "outside": "Outside",
            "ambient": "Ambient",
            "fpx": "FPX",
            "duct": "Duct",
            "gwc": "GWC",
            "co2": "CO2",
            "voc": "VOC",
            "concentration": "Concentration",
            "level": "Level",
            "pressure": "Pressure",
            "difference": "Difference",
            "drop": "Drop",
            "efficiency": "Efficiency",
            "recovery": "Recovery",
            "consumption": "Consumption",
            "current": "Current",
            "total": "Total",
            "energy": "Energy",
            "operating": "Operating",
            "hours": "Hours",
            "filter": "Filter",
            "error": "Error",
            "warning": "Warning",
            "code": "Code",
            "firmware": "Firmware",
            "major": "Major",
            "minor": "Minor",
            "patch": "Patch",
            "serial": "Serial",
            "number": "Number",
            "flow": "Flow",
            "effective": "Effective",
            "balance": "Balance",
            "battery": "Battery",
            "status": "Status",
            "power": "Power",
            "quality": "Quality",
            "humidity": "Humidity",
            "heat": "Heat",
            "maintenance": "Maintenance",
            "counter": "Counter",
        }
        
        # Apply replacements and capitalize
        processed_parts = []
        for part in name_parts:
            if part in replacements:
                processed_parts.append(replacements[part])
            else:
                processed_parts.append(part.capitalize())
        
        return " ".join(processed_parts)
    
    def _setup_sensor_attributes(self) -> None:
        """POPRAWIONE: Setup sensor attributes based on entity configuration."""
        # Unit of measurement
        if "unit" in self.entity_config:
            unit = self.entity_config["unit"]
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS.get(unit, unit)
        
        # Device class
        if "device_class" in self.entity_config:
            device_class_str = self.entity_config["device_class"]
            try:
                # Map device classes for HA 2025.* compatibility
                device_class_mapping = {
                    "carbon_dioxide": "co2",  # HA 2025.* uses 'co2' instead of 'carbon_dioxide'
                    "temperature": "temperature",
                    "humidity": "humidity", 
                    "pressure": "pressure",
                    "power": "power",
                    "energy": "energy",
                }
                
                mapped_class = device_class_mapping.get(device_class_str, device_class_str)
                
                # Try to get from SensorDeviceClass enum
                if hasattr(SensorDeviceClass, mapped_class.upper()):
                    self._attr_device_class = getattr(SensorDeviceClass, mapped_class.upper())
                else:
                    # Fallback to string for custom device classes
                    self._attr_device_class = mapped_class
                    
            except AttributeError:
                # Fallback to string for custom device classes
                self._attr_device_class = device_class_str
        
        # Icon
        if "icon" in self.entity_config:
            self._attr_icon = self.entity_config["icon"]
        
        # POPRAWKA: Sprawdzenie czy _attr_device_class istnieje przed użyciem
        # State class for statistics - HA 2025.* compatibility
        if hasattr(self, '_attr_device_class') and self._attr_device_class is not None:
            if (self._attr_device_class in [
                SensorDeviceClass.TEMPERATURE,
                SensorDeviceClass.HUMIDITY,
                SensorDeviceClass.PRESSURE,
                SensorDeviceClass.POWER,
                SensorDeviceClass.ENERGY,
            ] or (isinstance(self._attr_device_class, str) and self._attr_device_class in ["co2", "temperature", "humidity", "pressure", "power", "energy"])):
                self._attr_state_class = SensorStateClass.MEASUREMENT
        
        # Additional state class checks
        if "energy" in self.register_name or "consumption" in self.register_name:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif "hours" in self.register_name or "counter" in self.register_name:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        
        # Entity category for diagnostic sensors
        if any(keyword in self.register_name for keyword in [
            "error", "warning", "firmware", "serial", "compilation", "communication",
            "maintenance", "battery", "power_quality"
        ]):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.register_name not in self.coordinator.data:
            return None
            
        raw_value = self.coordinator.data[self.register_name]
        
        # Handle None values (invalid/no sensor)
        if raw_value is None:
            return None
        
        # Apply any additional processing
        return self._process_value(raw_value)
    
    def _process_value(self, raw_value: Any) -> Any:
        """Process raw value for display."""
        if raw_value is None:
            return None
            
        # Handle firmware version formatting
        if "firmware" in self.register_name and isinstance(raw_value, (int, float)):
            if self.register_name == "firmware_major":
                return f"{raw_value:02d}"
            elif self.register_name == "firmware_minor":
                return f"{raw_value:02d}"
            elif self.register_name == "firmware_patch":
                return f"{raw_value:02d}"
        
        # Handle serial number formatting
        if "serial_number" in self.register_name and isinstance(raw_value, (int, float)):
            return f"{raw_value:04X}"
        
        # Handle percentage values
        if self._attr_native_unit_of_measurement == PERCENTAGE:
            if isinstance(raw_value, (int, float)):
                return max(0, min(100, raw_value))  # Clamp to 0-100%
        
        # Handle temperature values with HA 2025.* compatibility
        if (hasattr(self, '_attr_device_class') and 
            (self._attr_device_class == SensorDeviceClass.TEMPERATURE or 
             (isinstance(self._attr_device_class, str) and self._attr_device_class == "temperature"))):
            if isinstance(raw_value, (int, float)):
                # Check for invalid temperature readings
                if raw_value < -50 or raw_value > 100:
                    return None
                return round(raw_value, 1)
        
        # Handle flow rates
        if "flowrate" in self.register_name or "flow" in self.register_name:
            if isinstance(raw_value, (int, float)):
                return max(0, raw_value)  # Flow cannot be negative
        
        # Handle pressure values with HA 2025.* compatibility
        if (hasattr(self, '_attr_device_class') and 
            (self._attr_device_class == SensorDeviceClass.PRESSURE or 
             (isinstance(self._attr_device_class, str) and self._attr_device_class == "pressure"))):
            if isinstance(raw_value, (int, float)):
                return round(raw_value, 1)
        
        # Handle power and energy with HA 2025.* compatibility
        if (hasattr(self, '_attr_device_class') and 
            (self._attr_device_class in [SensorDeviceClass.POWER, SensorDeviceClass.ENERGY] or
             (isinstance(self._attr_device_class, str) and self._attr_device_class in ["power", "energy"]))):
            if isinstance(raw_value, (int, float)):
                return max(0, raw_value)  # Power/energy cannot be negative
        
        return raw_value
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add register information for diagnostics
        if hasattr(self, '_attr_entity_category') and self._attr_entity_category == EntityCategory.DIAGNOSTIC:
            attributes["register_name"] = self.register_name
            if self.register_type:
                attributes["register_type"] = self.register_type
        
        # Add data quality information
        if self.register_name in self.coordinator.data:
            raw_value = self.coordinator.data[self.register_name]
            if raw_value is not None:
                attributes["raw_value"] = raw_value
        
        # Add scale information if applicable
        if "scale" in self.entity_config:
            attributes["scale_factor"] = self.entity_config["scale"]
        
        # Add last update time
        if hasattr(self.coordinator, 'last_successful_read') and self.coordinator.last_successful_read:
            attributes["last_updated"] = self.coordinator.last_successful_read.isoformat()
        
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