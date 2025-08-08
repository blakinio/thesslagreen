"""Select platform for ThesslaGreen Modbus Integration.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_MAPPINGS, HOLDING_REGISTERS
from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ThesslaGreen select entities from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    
    # Get select entity mappings
    select_mappings = ENTITY_MAPPINGS.get("select", {})
    
    # Create select entities for available writable registers
    for register_name, entity_config in select_mappings.items():
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
                ThesslaGreenSelect(
                    coordinator=coordinator,
                    register_name=register_name,
                    entity_config=entity_config,
                    register_type=register_type,
                )
            )
            _LOGGER.debug("Created select entity: %s", register_name)
    
    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d select entities", len(entities))
    else:
        _LOGGER.debug("No select entities were created")


class ThesslaGreenSelect(CoordinatorEntity, SelectEntity):
    """ThesslaGreen select entity."""
    
    def __init__(
        self,
        coordinator: ThesslaGreenModbusCoordinator,
        register_name: str,
        entity_config: Dict[str, Any],
        register_type: Optional[str] = None,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        
        self.register_name = register_name
        self.entity_config = entity_config
        self.register_type = register_type
        
        # Entity configuration
        self._attr_name = self._generate_entity_name()
        self._attr_unique_id = f"{coordinator.device_name}_{register_name}"
        self._attr_device_info = coordinator.get_device_info()
        
        # Select configuration
        self._setup_select_attributes()
        
        _LOGGER.debug("Initialized select entity: %s (register: %s)", self._attr_name, register_name)
    
    def _generate_entity_name(self) -> str:
        """Generate human-readable entity name."""
        # Convert register name to human readable
        name_parts = self.register_name.split("_")
        
        # Common replacements for better readability
        replacements = {
            "mode": "Mode",
            "season": "Season",
            "gwc": "GWC",
            "bypass": "Bypass",
            "filter": "Filter",
            "change": "Change Type",
            "special": "Special",
            "okap": "Hood",
            "auto": "Auto",
            "manual": "Manual",
            "temporary": "Temporary",
            "winter": "Winter",
            "summer": "Summer",
            "off": "Off",
            "panel": "Panel",
            "on": "On",
        }
        
        # Apply replacements and capitalize
        processed_parts = []
        for part in name_parts:
            if part in replacements:
                processed_parts.append(replacements[part])
            else:
                processed_parts.append(part.capitalize())
        
        return " ".join(processed_parts)
    
    def _setup_select_attributes(self) -> None:
        """Setup select attributes based on entity configuration."""
        # Options list
        self._attr_options = self.entity_config.get("options", [])
        
        # Icon based on register type
        if "mode" in self.register_name:
            self._attr_icon = "mdi:cog"
        elif "season" in self.register_name:
            self._attr_icon = "mdi:weather-sunny"
        elif "gwc" in self.register_name:
            self._attr_icon = "mdi:earth"
        elif "bypass" in self.register_name:
            self._attr_icon = "mdi:valve"
        elif "filter" in self.register_name:
            self._attr_icon = "mdi:air-filter"
        else:
            self._attr_icon = "mdi:format-list-bulleted"
        
        # Entity category for configuration parameters
        if any(keyword in self.register_name for keyword in [
            "season", "filter", "gwc", "bypass"
        ]):
            self._attr_entity_category = EntityCategory.CONFIG
    
    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.register_name not in self.coordinator.data:
            return None
            
        raw_value = self.coordinator.data[self.register_name]
        
        # Handle None values
        if raw_value is None:
            return None
        
        # Map raw value to option string
        return self._value_to_option(raw_value)
    
    def _value_to_option(self, value: Any) -> str | None:
        """Convert raw register value to option string."""
        if value is None:
            return None
        
        # Handle different register types
        if self.register_name == "mode":
            value_map = {0: "Auto", 1: "Manual", 2: "Temporary"}
            return value_map.get(value, "Auto")
        
        elif self.register_name == "season_mode":
            value_map = {0: "Auto", 1: "Winter", 2: "Summer"}
            return value_map.get(value, "Auto")
        
        elif self.register_name == "gwc_mode":
            value_map = {0: "Off", 1: "Auto", 2: "Manual"}
            return value_map.get(value, "Off")
        
        elif self.register_name == "bypass_mode":
            value_map = {0: "Off", 1: "Auto", 2: "Manual"}
            return value_map.get(value, "Off")
        
        elif self.register_name == "filter_change":
            value_map = {
                1: "Presostat", 
                2: "Flat Filters", 
                3: "CleanPad", 
                4: "CleanPad Pure"
            }
            return value_map.get(value, "Presostat")
        
        # Default: return first option if value is valid index
        if isinstance(value, int) and 0 <= value < len(self._attr_options):
            return self._attr_options[value]
        
        return None
    
    def _option_to_value(self, option: str) -> int:
        """Convert option string to raw register value."""
        # Handle different register types
        if self.register_name == "mode":
            option_map = {"Auto": 0, "Manual": 1, "Temporary": 2}
            return option_map.get(option, 0)
        
        elif self.register_name == "season_mode":
            option_map = {"Auto": 0, "Winter": 1, "Summer": 2}
            return option_map.get(option, 0)
        
        elif self.register_name == "gwc_mode":
            option_map = {"Off": 0, "Auto": 1, "Manual": 2}
            return option_map.get(option, 0)
        
        elif self.register_name == "bypass_mode":
            option_map = {"Off": 0, "Auto": 1, "Manual": 2}
            return option_map.get(option, 0)
        
        elif self.register_name == "filter_change":
            option_map = {
                "Presostat": 1,
                "Flat Filters": 2,
                "CleanPad": 3,
                "CleanPad Pure": 4
            }
            return option_map.get(option, 1)
        
        # Default: return option index
        try:
            return self._attr_options.index(option)
        except ValueError:
            return 0
    
    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        if option not in self._attr_options:
            _LOGGER.error("Invalid option %s for %s", option, self.register_name)
            return
        
        try:
            value = self._option_to_value(option)
            await self._write_register(self.register_name, value)
            _LOGGER.info("Set %s to %s (value: %d)", self.register_name, option, value)
            
        except Exception as exc:
            _LOGGER.error("Failed to set %s to %s: %s", self.register_name, option, exc)
    
    async def _write_register(self, register_name: str, value: int) -> None:
        """Write value to register."""
        if register_name not in HOLDING_REGISTERS:
            raise ValueError(f"Register {register_name} is not writable")
        
        register_address = HOLDING_REGISTERS[register_name]
        
        # Ensure client is connected
        if not self.coordinator.client or not self.coordinator.client.connected:
            if not await self.coordinator._async_setup_client():
                raise RuntimeError("Failed to connect to device")
        
        # Write register - pymodbus 3.5+ compatible
        response = await self.coordinator.client.write_register(
            address=register_address, 
            value=value, 
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
        
        # Add available options
        attributes["available_options"] = self._attr_options
        
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
            
        # For select entities, we don't require the register to be in current data
        # as they are primarily for control, not just display
        return True