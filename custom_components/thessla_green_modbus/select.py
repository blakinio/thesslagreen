"""Enhanced select platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OPERATING_MODES, SEASON_MODES, SPECIAL_MODES
from .coordinator import ThesslaGreenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up enhanced select platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # Enhanced Operating Mode Select (HA 2025.7+ Compatible)
    if "mode" in holding_regs:
        entities.append(
            ThesslaGreenModeSelect(
                coordinator,
                "mode",
                "Operating Mode",
                "mdi:cog",
                OPERATING_MODES,
                "Select the operating mode of the ventilation system"
            )
        )
    
    # Enhanced Season Mode Select (HA 2025.7+ Compatible)
    if "season_mode" in holding_regs:
        entities.append(
            ThesslaGreenModeSelect(
                coordinator,
                "season_mode", 
                "Season Mode",
                "mdi:weather-partly-cloudy",
                SEASON_MODES,
                "Select winter or summer mode for optimal performance"
            )
        )
    
    # Enhanced Special Function Select (HA 2025.7+ Compatible)
    if "special_mode" in holding_regs:
        entities.append(
            ThesslaGreenModeSelect(
                coordinator,
                "special_mode",
                "Special Function",
                "mdi:function",
                SPECIAL_MODES,
                "Activate special functions like OKAP, KOMINEK, etc."
            )
        )
    
    # Enhanced Comfort Mode Select (HA 2025.7+)
    if "comfort_mode" in holding_regs:
        comfort_modes = {
            0: "Nieaktywny",
            1: "Grzanie", 
            2: "Chłodzenie"
        }
        entities.append(
            ThesslaGreenModeSelect(
                coordinator,
                "comfort_mode",
                "Comfort Mode",
                "mdi:home-thermometer",
                comfort_modes,
                "Control heating/cooling comfort mode"
            )
        )
    
    # Enhanced GWC Mode Select (HA 2025.7+)
    if "gwc_mode" in holding_regs:
        gwc_modes = {
            0: "Nieaktywny",
            1: "Zima",
            2: "Lato"
        }
        entities.append(
            ThesslaGreenModeSelect(
                coordinator,
                "gwc_mode",
                "GWC Mode",
                "mdi:earth",
                gwc_modes,
                "Control Ground Heat Exchanger mode"
            )
        )
    
    # Enhanced GWC Regeneration Mode Select (HA 2025.7+)
    if "gwc_regeneration_mode" in holding_regs:
        gwc_regen_modes = {
            0: "Wyłączone",
            1: "Dobowe",
            2: "Temperaturowe",
            3: "Wymuszone"
        }
        entities.append(
            ThesslaGreenModeSelect(
                coordinator,
                "gwc_regeneration_mode",
                "GWC Regeneration",
                "mdi:earth-arrow-right",
                gwc_regen_modes,
                "Select GWC regeneration mode"
            )
        )
    
    # Enhanced Bypass Mode Select (HA 2025.7+)
    if "bypass_mode" in holding_regs:
        bypass_modes = {
            0: "Nieaktywny",
            1: "FreeHeating",
            2: "FreeCooling"
        }
        entities.append(
            ThesslaGreenModeSelect(
                coordinator,
                "bypass_mode",
                "Bypass Mode",
                "mdi:valve",
                bypass_modes,
                "Control bypass mode for free heating/cooling"
            )
        )
    
    # Enhanced Constant Flow Mode Select (HA 2025.7+)
    if "constant_flow_mode" in holding_regs:
        cf_modes = {
            0: "Wyłączony",
            1: "Aktywny"
        }
        entities.append(
            ThesslaGreenModeSelect(
                coordinator,
                "constant_flow_mode",
                "Constant Flow Mode",
                "mdi:chart-line",
                cf_modes,
                "Enable/disable constant flow control"
            )
        )

    if entities:
        _LOGGER.debug("Adding %d enhanced select entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenModeSelect(CoordinatorEntity, SelectEntity):
    """Enhanced ThesslaGreen mode select entity - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        mode_map: dict[int, str],
        description: str,
    ) -> None:
        """Initialize the enhanced mode select."""
        super().__init__(coordinator)
        self._key = key
        self._mode_map = mode_map
        self._reverse_map = {v: k for k, v in mode_map.items()}
        
        # Enhanced device info handling
        device_info = coordinator.data.get("device_info", {}) if coordinator.data else {}
        device_name = device_info.get("device_name", f"ThesslaGreen {coordinator.host}")
        
        self._attr_name = name
        self._attr_icon = icon
        self._attr_options = list(mode_map.values())
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        return self._mode_map.get(value)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option not in self._reverse_map:
            _LOGGER.error("Invalid option %s for %s", option, self._key)
            return
        
        mode_value = self._reverse_map[option]
        
        # Enhanced validation for special modes (HA 2025.7+)
        if self._key == "special_mode" and not self._validate_special_mode(mode_value):
            _LOGGER.warning("Special mode %s may not be suitable in current conditions", option)
        
        success = await self.coordinator.async_write_register(self._key, mode_value)
        if success:
            _LOGGER.info("Set %s to %s (value: %d)", self._key, option, mode_value)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s to %s", self._key, option)

    def _validate_special_mode(self, mode_value: int) -> bool:
        """Enhanced validation for special modes - HA 2025.7+."""
        if not self.coordinator.data:
            return True  # Allow if no data available
        
        current_mode = self.coordinator.data.get("mode", 0)
        outside_temp = self.coordinator.data.get("outside_temperature")
        
        # Some special modes work better in manual mode
        intensive_modes = [1, 2, 5, 8]  # OKAP, KOMINEK, BOOST, GOTOWANIE
        if mode_value in intensive_modes and current_mode == 0:
            _LOGGER.info("Special mode %d works best in manual mode", mode_value)
        
        # Temperature-dependent modes
        if mode_value == 12 and outside_temp is not None:  # OTWARTE OKNA
            if outside_temp < 5:
                _LOGGER.warning("Open windows mode not recommended below 5°C (current: %.1f°C)", outside_temp)
                return False
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "register_key": self._key,
            "available_options": len(self._attr_options),
        }
        
        # Enhanced context information (HA 2025.7+)
        current_value = self.coordinator.data.get(self._key)
        if current_value is not None:
            attributes["current_value"] = current_value
            
        # Add mode-specific context
        if self._key == "mode":
            attributes["description"] = "Controls the main operating mode of the ventilation system"
            # Add intensity info for current mode
            if current_value == 0:  # Auto
                attributes["current_intensity"] = self.coordinator.data.get("supply_percentage")
            elif current_value == 1:  # Manual
                attributes["current_intensity"] = self.coordinator.data.get("air_flow_rate_manual")
            elif current_value == 2:  # Temporary
                attributes["current_intensity"] = self.coordinator.data.get("air_flow_rate_temporary")
                temp_remaining = self.coordinator.data.get("temporary_time_remaining")
                if temp_remaining:
                    attributes["time_remaining_minutes"] = temp_remaining
                    
        elif self._key == "special_mode":
            attributes["description"] = "Activates special functions for specific situations"
            if current_value and current_value != 0:
                # Add time remaining for temporary special modes
                boost_remaining = self.coordinator.data.get("boost_time_remaining")
                if boost_remaining and current_value == 5:  # BOOST mode
                    attributes["boost_time_remaining_minutes"] = boost_remaining
                    
        elif self._key == "season_mode":
            attributes["description"] = "Optimizes system performance for seasonal conditions"
            outside_temp = self.coordinator.data.get("outside_temperature")
            if outside_temp is not None:
                attributes["outside_temperature"] = outside_temp
                if current_value == 0:  # Winter
                    attributes["recommended"] = outside_temp < 15
                elif current_value == 1:  # Summer  
                    attributes["recommended"] = outside_temp > 20
                    
        elif self._key == "gwc_mode":
            attributes["description"] = "Controls Ground Heat Exchanger operation"
            gwc_temp = self.coordinator.data.get("gwc_temperature")
            if gwc_temp is not None:
                attributes["gwc_temperature"] = gwc_temp
                
        elif self._key == "bypass_mode":
            attributes["description"] = "Controls bypass for free heating/cooling"
            bypass_position = self.coordinator.data.get("bypass_position")
            if bypass_position is not None:
                attributes["bypass_position"] = f"{bypass_position}%"
        
        # Add last update timestamp
        if hasattr(self.coordinator, 'last_update_success_time'):
            attributes["last_updated"] = getattr(self.coordinator, 'last_update_success_time', self.coordinator.last_update_success).isoformat()
            
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self._key in self.coordinator.data
        )