"""Number platform for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_MAPPINGS, HOLDING_REGISTERS
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Unit mappings
UNIT_MAPPINGS = {
    "°C": UnitOfTemperature.CELSIUS,
    "%": PERCENTAGE,
    "min": UnitOfTime.MINUTES,
    "h": UnitOfTime.HOURS,
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen number entities from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    
    # Get number entity mappings
    number_mappings = ENTITY_MAPPINGS.get("number", {})
    
    # Create number entities for available writable registers
    for register_name, entity_config in number_mappings.items():
        # Check if this register is available and writable
        is_available = False
        register_type = None
        
        # Only check holding registers as they are writable
        if register_name in coordinator.available_registers.get("holding", {}):
            is_available = True
            register_type = "holding"
        
        # If force full register list, check against holding registers
        if not is_available and coordinator.force_full_register_list:
            if register_name in HOLDING_REGISTERS:
                is_available = True
                register_type = "holding"
        
        if is_available:
            entities.append(
                ThesslaGreenNumber(
                    coordinator=coordinator,
                    register_name=register_name,
                    entity_config=entity_config,
                    register_type=register_type,
                )
            )
            _LOGGER.debug("Created number entity: %s", register_name)
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d number entities", len(entities))
    else:
        _LOGGER.debug("No number entities were created")


class ThesslaGreenNumber(CoordinatorEntity, NumberEntity):
    """ThesslaGreen number entity."""
    
    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        entity_config: Dict[str, Any],
        register_type: Optional[str] = None,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        
        self.register_name = register_name
        self.entity_config = entity_config
        self.register_type = register_type
        
        # Entity configuration
        self._attr_name = self._generate_entity_name()
        self._attr_unique_id = f"{coordinator.device_name}_{register_name}"
        self._attr_device_info = coordinator.get_device_info()
        
        # Number configuration
        self._setup_number_attributes()
        
        _LOGGER.debug("Initialized number entity: %s (register: %s)", self._attr_name, register_name)
    
    def _generate_entity_name(self) -> str:
        """Generate human-readable entity name."""
        # Convert register name to human readable
        name_parts = self.register_name.split("_")
        
        # Common replacements for better readability
        replacements = {
            "supply": "Supply",
            "temperature": "Temperature", 
            "manual": "Manual",
            "auto": "Auto",
            "heating": "Heating",
            "cooling": "Cooling",
            "comfort": "Comfort",
            "eco": "Eco",
            "anti": "Anti",
            "freeze": "Freeze",
            "hysteresis": "Hysteresis",
            "sensor": "Sensor",
            "correction": "Correction",
            "temp": "Temperature",
            "max": "Max",
            "min": "Min",
            "gwc": "GWC",
            "switch": "Switch",
            "air": "Air",
            "flow": "Flow",
            "rate": "Rate",
            "temporary": "Temporary",
            "boost": "Boost",
            "minimum": "Minimum",
            "night": "Night",
            "okap": "Hood",
            "intensity": "Intensity",
            "duration": "Duration",
            "party": "Party",
            "fireplace": "Fireplace",
            "reduction": "Reduction",
            "vacation": "Vacation",
            "mode": "Mode",
            "balance": "Balance",
            "correction": "Correction",
        }
        
        # Apply replacements and capitalize
        processed_parts = []
        for part in name_parts:
            if part in replacements:
                processed_parts.append(replacements[part])
            else:
                processed_parts.append(part.capitalize())
        
        return " ".join(processed_parts)
    
    def _setup_number_attributes(self) -> None:
        """Setup number attributes based on entity configuration."""
        # Unit of measurement
        if "unit" in self.entity_config:
            unit = self.entity_config["unit"]
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS.get(unit, unit)
        
        # Min/max values
        self._attr_native_min_value = self.entity_config.get("min", 0)
        self._attr_native_max_value = self.entity_config.get("max", 100)
        
        # Step size
        self._attr_native_step = self.entity_config.get("step", 1)
        
        # Mode - slider for temperatures and durations, box for others
        if "temperature" in self.register_name or "duration" in self.register_name:
            self._attr_mode = NumberMode.SLIDER
        else:
            self._attr_mode = NumberMode.BOX
        
        # Icon
        if "temperature" in self.register_name:
            self._attr_icon = "mdi:thermometer"
        elif "flow" in self.register_name or "rate" in self.register_name:
            self._attr_icon = "mdi:fan"
        elif "duration" in self.register_name:
            self._attr_icon = "mdi:timer"
        elif "intensity" in self.register_name:
            self._attr_icon = "mdi:gauge"
        else:
            self._attr_icon = "mdi:numeric"
        
        # Entity category for configuration parameters
        if any(keyword in self.register_name for keyword in [
            "hysteresis", "correction", "max", "min", "balance"
        ]):
            self._attr_entity_category = EntityCategory.CONFIG
    
    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.register_name not in self.coordinator.data:
            return None
            
        raw_value = self.coordinator.data[self.register_name]
        
        # Handle None values
        if raw_value is None:
            return None
        
        # Apply scale factor if configured
        scale = self.entity_config.get("scale", 1)
        if scale != 1 and isinstance(raw_value, (int, float)):
            return round(float(raw_value) * scale, 2)
        
        return float(raw_value) if isinstance(raw_value, (int, float)) else None
    
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        try:
            # Apply inverse scale factor if configured
            scale = self.entity_config.get("scale", 1)
            scaled_value = value / scale if scale != 1 else value
            
            await self._write_register(self.register_name, scaled_value)
            _LOGGER.info("Set %s to %.2f", self.register_name, value)
            
        except Exception as exc:
            _LOGGER.error("Failed to set %s to %.2f: %s", self.register_name, value, exc)
    
    async def _write_register(self, register_name: str, value: float) -> None:
        """Write value to register."""
        if register_name not in HOLDING_REGISTERS:
            raise ValueError(f"Register {register_name} is not writable")
        
        register_address = HOLDING_REGISTERS[register_name]
        
        # Convert to integer for Modbus
        int_value = int(round(value))
        
        # Ensure client is connected
        if not self.coordinator.client or not self.coordinator.client.connected:
            if not await self.coordinator._async_setup_client():
                raise RuntimeError("Failed to connect to device")
        
        # Write register - pymodbus 3.5+ compatible
        response = await self.coordinator.client.write_register(
            address=register_address, 
            value=int_value, 
            slave=self.coordinator.slave_id
        )
        
        if response.isError():
            raise RuntimeError(f"Failed to write register {register_name}: {response}")
        
        # Request immediate data update
        await self.coordinator.async_request_refresh()
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        attributes = {}
        
        # Add register information
        attributes["register_name"] = self.register_name
        attributes["register_address"] = f"0x{HOLDING_REGISTERS.get(self.register_name, 0):04X}"
        
        # Add raw value for debugging
        if self.register_name in self.coordinator.data:
            raw_value = self.coordinator.data[self.register_name]
            if raw_value is not None:
                attributes["raw_value"] = raw_value
        
        # Add scale information if applicable
        if "scale" in self.entity_config:
            attributes["scale_factor"] = self.entity_config["scale"]
        
        # Add valid range
        attributes["valid_range"] = {
            "min": self._attr_native_min_value,
            "max": self._attr_native_max_value,
            "step": self._attr_native_step
        }
        
        # Add last update time
        if self.coordinator.last_successful_update:
            attributes["last_updated"] = self.coordinator.last_successful_update.isoformat()
        
        return attributes
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if coordinator is available
        if not self.coordinator.last_update_success:
            return False
            
        # For number entities, we don't require the register to be in current data
        # as they are primarily for control, not just display
        return True