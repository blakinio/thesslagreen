"""Enhanced select platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    COMFORT_MODES,
    DOMAIN,
    FILTER_TYPES,
    OPERATING_MODES,
    SEASON_MODES,
    SPECIAL_MODES,
)
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
    
    # Enhanced Select Entities (HA 2025.7+ Compatible)
    select_entities = [
        ("mode", "Operating Mode", "mdi:state-machine", list(OPERATING_MODES.values()), OPERATING_MODES, False),
        ("special_mode", "Special Function", "mdi:function-variant", list(SPECIAL_MODES.values()), SPECIAL_MODES, False),
        ("comfort_mode", "Comfort Mode", "mdi:home-thermometer", list(COMFORT_MODES.values()), COMFORT_MODES, False),
        ("season_mode", "Season Mode", "mdi:weather-partly-cloudy", list(SEASON_MODES.values()), SEASON_MODES, False),
        ("filter_change", "Filter Type", "mdi:air-filter", list(FILTER_TYPES.values()), FILTER_TYPES, True),
        ("gwc_mode", "GWC Mode", "mdi:pipe", ["Off", "Auto", "On"], {0: "Off", 1: "Auto", 2: "On"}, False),
        ("bypass_mode", "Bypass Mode", "mdi:debug-step-over", ["Off", "Auto", "On"], {0: "Off", 1: "Auto", 2: "On"}, False),
        ("configuration_mode", "Configuration Mode", "mdi:cog", ["Normal", "Filter Control", "AFC"], {0: "Normal", 47: "Filter Control", 65: "AFC"}, True),
    ]
    
    for reg_key, name, icon, options, mapping, is_config in select_entities:
        # Check both new and old register names
        if reg_key in holding_regs or f"{reg_key}_old" in holding_regs:
            entities.append(
                ThesslaGreenSelect(
                    coordinator, reg_key, name, icon, options, mapping, is_config
                )
            )
    
    # Day of week selector for preset check
    if "pres_check_day" in holding_regs:
        entities.append(
            ThesslaGreenSelect(
                coordinator,
                "pres_check_day",
                "Filter Check Day",
                "mdi:calendar-check",
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"},
                True
            )
        )
    
    if entities:
        _LOGGER.debug("Adding %d enhanced select entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenSelect(CoordinatorEntity, SelectEntity):
    """Enhanced select entity for ThesslaGreen devices - HA 2025.7+ Compatible."""
    
    _attr_has_entity_name = True  # ✅ FIX: Enable entity naming

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        options: list[str],
        mapping: dict[int, str],
        is_config: bool = False,
    ) -> None:
        """Initialize the enhanced select entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_options = options
        self._mapping = mapping
        self._reverse_mapping = {v: k for k, v in mapping.items()}
        self._attr_translation_key = key
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.','_')}_{coordinator.slave_id}_{key}"
        
        # Set entity category
        if is_config:
            self._attr_entity_category = EntityCategory.CONFIG
        
        # Enhanced device info
        device_info = coordinator.device_scan_result.get("device_info", {}) if hasattr(coordinator, 'device_scan_result') else {}
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": f"ThesslaGreen AirPack ({coordinator.host})",
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option."""
        # Try both new and old register names
        value = self.coordinator.data.get(self._key)
        if value is None and f"{self._key}_old" in self.coordinator.data:
            value = self.coordinator.data.get(f"{self._key}_old")
        
        if value is None:
            return None
        
        return self._mapping.get(value, f"Unknown ({value})")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self._reverse_mapping:
            _LOGGER.error("Invalid option %s for %s", option, self._key)
            return
        
        value = self._reverse_mapping[option]
        
        # Try to write to the appropriate register
        register = self._key
        if register not in self.coordinator.available_registers.get("holding_registers", set()):
            # Try old register name
            register = f"{self._key}_old"
            if register not in self.coordinator.available_registers.get("holding_registers", set()):
                _LOGGER.error("Register %s not available", self._key)
                return
        
        success = await self.coordinator.async_write_register(register, value)
        if success:
            await self.coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and 
            (self.coordinator.data.get(self._key) is not None or 
             self.coordinator.data.get(f"{self._key}_old") is not None)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "register_key": self._key,
            "last_update": getattr(self.coordinator, 'last_update_success_time', self.coordinator.last_update_success),
        }
        
        # Add raw value for debugging
        value = self.coordinator.data.get(self._key)
        if value is None:
            value = self.coordinator.data.get(f"{self._key}_old")
        
        if value is not None:
            attributes["raw_value"] = value
        
        # Add context-specific attributes
        if self._key == "mode":
            # Add current intensity based on mode
            if value == 1:  # Manual
                intensity = self.coordinator.data.get("air_flow_rate_manual")
                if intensity is None:
                    intensity = self.coordinator.data.get("intensity_1")
                if intensity is not None:
                    attributes["current_intensity"] = f"{intensity}%"
            elif value == 2:  # Temporary
                intensity = self.coordinator.data.get("air_flow_rate_temporary")
                if intensity is None:
                    intensity = self.coordinator.data.get("intensity_2")
                if intensity is not None:
                    attributes["current_intensity"] = f"{intensity}%"
            elif value == 0:  # Auto
                intensity = self.coordinator.data.get("air_flow_rate_auto")
                if intensity is None:
                    intensity = self.coordinator.data.get("intensity_3")
                if intensity is not None:
                    attributes["current_intensity"] = f"{intensity}%"
        
        elif self._key == "special_mode":
            # Add special mode details
            if value == 1:  # OKAP
                attributes["description"] = "Kitchen hood mode - increased exhaust"
            elif value == 2:  # KOMINEK
                attributes["description"] = "Fireplace mode - increased supply"
            elif value == 3:  # WIETRZENIE
                attributes["description"] = "Airing mode - maximum ventilation"
            elif value == 4:  # PUSTY_DOM
                attributes["description"] = "Empty house - minimal ventilation"
        
        elif self._key == "comfort_mode":
            # Add temperature setpoints
            if value == 1:  # Heating
                temp = self.coordinator.data.get("comfort_temperature_heating")
                if temp is not None:
                    attributes["target_temperature"] = f"{temp / 10.0}°C"
            elif value == 2:  # Cooling
                temp = self.coordinator.data.get("comfort_temperature_cooling")
                if temp is not None:
                    attributes["target_temperature"] = f"{temp / 10.0}°C"
        
        elif self._key == "filter_change":
            # Add filter status
            days = self.coordinator.data.get("filter_time_remaining")
            if days is not None:
                attributes["days_remaining"] = days
                if days < 30:
                    attributes["status"] = "replacement_soon"
                else:
                    attributes["status"] = "ok"
        
        elif self._key == "gwc_mode":
            # Add GWC temperature
            gwc_temp = self.coordinator.data.get("gwc_temperature")
            if gwc_temp is not None:
                attributes["gwc_temperature"] = f"{gwc_temp / 10.0}°C"
        
        elif self._key == "bypass_mode":
            # Add bypass position
            bypass_pos = self.coordinator.data.get("bypass_position")
            if bypass_pos is not None:
                attributes["bypass_position"] = f"{bypass_pos}%"
        
        return attributes