"""Enhanced switch platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
    """Set up enhanced switch platform."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    coil_regs = coordinator.available_registers.get("coil_registers", set())
    
    # Enhanced System Control Switches (HA 2025.7+ Compatible)
    system_switches = [
        ("system_on_off", "System Power", "mdi:power", SwitchDeviceClass.SWITCH, 
         "Main power control for the ventilation system"),
        ("constant_flow_active", "Constant Flow", "mdi:chart-line", SwitchDeviceClass.SWITCH,
         "Enable constant flow control for precise air flow management"),
        ("gwc_active", "GWC Enable", "mdi:earth", SwitchDeviceClass.SWITCH,
         "Enable Ground Heat Exchanger for improved efficiency"),
        ("bypass_active", "Bypass Enable", "mdi:valve", SwitchDeviceClass.SWITCH,
         "Enable bypass for free heating and cooling"),
        ("comfort_active", "Comfort Mode", "mdi:home-thermometer", SwitchDeviceClass.SWITCH,
         "Enable comfort temperature control"),
    ]
    
    for switch_key, name, icon, device_class, description in system_switches:
        if switch_key in coil_regs:
            entities.append(
                ThesslaGreenSwitch(
                    coordinator, switch_key, name, icon, device_class, description
                )
            )
    
    # Enhanced Protection and Mode Switches (HA 2025.7+)
    protection_switches = [
        ("antifreeze_mode", "Antifreeze Protection", "mdi:snowflake-alert", SwitchDeviceClass.SWITCH,
         "Enable antifreeze protection for cold weather operation"),
        ("summer_mode", "Summer Mode", "mdi:weather-sunny", SwitchDeviceClass.SWITCH,
         "Optimize system for summer operation"),
        ("preheating_active", "Preheating", "mdi:radiator", SwitchDeviceClass.SWITCH,
         "Enable preheating for supply air"),
        ("cooling_active", "Cooling", "mdi:snowflake", SwitchDeviceClass.SWITCH,
         "Enable active cooling of supply air"),
        ("night_cooling_active", "Night Cooling", "mdi:weather-night", SwitchDeviceClass.SWITCH,
         "Enable night cooling for energy savings"),
    ]
    
    for switch_key, name, icon, device_class, description in protection_switches:
        if switch_key in coil_regs:
            entities.append(
                ThesslaGreenSwitch(
                    coordinator, switch_key, name, icon, device_class, description
                )
            )
    
    # Enhanced Maintenance Mode Switch (HA 2025.7+)
    if "maintenance_mode" in coil_regs:
        entities.append(
            ThesslaGreenMaintenanceSwitch(coordinator)
        )

    if entities:
        _LOGGER.debug("Adding %d enhanced switch entities", len(entities))
        async_add_entities(entities)


class ThesslaGreenSwitch(CoordinatorEntity, SwitchEntity):
    """Enhanced ThesslaGreen switch entity - HA 2025.7+ Compatible."""

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        device_class: SwitchDeviceClass,
        description: str,
    ) -> None:
        """Initialize the enhanced switch."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"
        self._description = description
        
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
        """Return true if the switch is on."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        
        return bool(value)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self.coordinator.data.get(self._key) is not None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        success = await self.coordinator.async_write_register(self._key, 1)
        if success:
            _LOGGER.info("Turned on %s", self._key)
            # Update local state immediately for better UI responsiveness
            self.coordinator.data[self._key] = 1
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to turn on %s", self._key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        success = await self.coordinator.async_write_register(self._key, 0)
        if success:
            _LOGGER.info("Turned off %s", self._key)
            # Update local state immediately for better UI responsiveness
            self.coordinator.data[self._key] = 0
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to turn off %s", self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "description": self._description,
            "register_key": self._key,
            "last_update": getattr(self.coordinator, 'last_update_success_time', self.coordinator.last_update_success),
        }
        
        # Add context-specific attributes
        if self._key == "system_on_off":
            # Add system status information
            mode = self.coordinator.data.get("mode")
            if mode is not None:
                mode_names = {0: "Auto", 1: "Manual", 2: "Temporary"}
                attributes["current_mode"] = mode_names.get(mode, "Unknown")
            
            intensity = self.coordinator.data.get("air_flow_rate_manual", 0)
            attributes["current_intensity"] = f"{intensity}%"
            
        elif self._key == "gwc_active":
            # Add GWC information
            gwc_mode = self.coordinator.data.get("gwc_mode")
            if gwc_mode is not None:
                mode_names = {0: "Inactive", 1: "Winter", 2: "Summer"}
                attributes["gwc_mode"] = mode_names.get(gwc_mode, "Unknown")
            
            gwc_temp = self.coordinator.data.get("gwc_temperature")
            if gwc_temp is not None:
                attributes["gwc_temperature"] = f"{gwc_temp / 10.0:.1f}°C"
                
        elif self._key == "bypass_active":
            # Add bypass information
            bypass_mode = self.coordinator.data.get("bypass_mode")
            if bypass_mode is not None:
                mode_names = {0: "Inactive", 1: "FreeHeating", 2: "FreeCooling"}
                attributes["bypass_mode"] = mode_names.get(bypass_mode, "Unknown")
                
        elif self._key == "constant_flow_active":
            # Add constant flow information
            supply_target = self.coordinator.data.get("constant_flow_supply_target")
            if supply_target is not None:
                attributes["supply_target"] = f"{supply_target} m³/h"
                
            exhaust_target = self.coordinator.data.get("constant_flow_exhaust_target")
            if exhaust_target is not None:
                attributes["exhaust_target"] = f"{exhaust_target} m³/h"
                
        elif self._key == "comfort_active":
            # Add comfort mode information
            comfort_mode = self.coordinator.data.get("comfort_mode")
            if comfort_mode is not None:
                mode_names = {0: "Inactive", 1: "Heating", 2: "Cooling"}
                attributes["comfort_mode"] = mode_names.get(comfort_mode, "Unknown")
                
            heating_temp = self.coordinator.data.get("comfort_temperature_heating")
            if heating_temp is not None:
                attributes["heating_temperature"] = f"{heating_temp / 10.0:.1f}°C"
                
            cooling_temp = self.coordinator.data.get("comfort_temperature_cooling")
            if cooling_temp is not None:
                attributes["cooling_temperature"] = f"{cooling_temp / 10.0:.1f}°C"
        
        return attributes


class ThesslaGreenMaintenanceSwitch(ThesslaGreenSwitch):
    """Enhanced maintenance mode switch - HA 2025.7+ Compatible."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the maintenance switch."""
        super().__init__(
            coordinator,
            "maintenance_mode",
            "Maintenance Mode",
            "mdi:wrench",
            SwitchDeviceClass.SWITCH,
            "Enable maintenance mode for service operations"
        )
        # ✅ FIXED: Use EntityCategory enum instead of string
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on maintenance mode with safety checks."""
        # Safety check - ensure system is not in critical state
        error_code = self.coordinator.data.get("error_code", 0)
        if error_code != 0:
            _LOGGER.warning("Cannot enable maintenance mode while system has errors (code: %d)", error_code)
            return
        
        # Warn user about maintenance mode implications
        _LOGGER.info("Enabling maintenance mode - normal operation will be suspended")
        
        await super().async_turn_on(**kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off maintenance mode."""
        _LOGGER.info("Disabling maintenance mode - resuming normal operation")
        await super().async_turn_off(**kwargs)
        
        # Request refresh to update system state after maintenance
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = super().extra_state_attributes
        
        # Add maintenance-specific information
        if self.is_on:
            attributes["maintenance_status"] = "active"
            attributes["normal_operation"] = "suspended"
            attributes["safety_notice"] = "System is in maintenance mode"
        else:
            attributes["maintenance_status"] = "inactive"
            attributes["normal_operation"] = "active"
        
        # Add system status for maintenance context
        error_code = self.coordinator.data.get("error_code", 0)
        warning_code = self.coordinator.data.get("warning_code", 0)
        
        attributes["system_errors"] = error_code
        attributes["system_warnings"] = warning_code
        
        if error_code == 0 and warning_code == 0:
            attributes["system_health"] = "good"
        elif error_code == 0:
            attributes["system_health"] = "warnings_present"
        else:
            attributes["system_health"] = "errors_present"
        
        # Add operating hours for maintenance scheduling
        operating_hours = self.coordinator.data.get("operating_hours")
        if operating_hours is not None:
            attributes["operating_hours"] = operating_hours
            attributes["operating_days"] = round(operating_hours / 24, 1)
            
            # Maintenance recommendations based on operating hours
            if operating_hours > 8760:  # 1 year
                attributes["maintenance_recommendation"] = "Annual service recommended"
            elif operating_hours > 4380:  # 6 months
                attributes["maintenance_recommendation"] = "Filter check recommended"
            else:
                attributes["maintenance_recommendation"] = "No maintenance required"
        
        return attributes