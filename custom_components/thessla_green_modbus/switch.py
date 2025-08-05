"""Enhanced switch platform for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
        device_class: SwitchDeviceClass | None,
        description: str,
    ) -> None:
        """Initialize the enhanced switch."""
        super().__init__(coordinator)
        self._key = key
        
        # Enhanced device info handling
        device_info = coordinator.data.get("device_info", {}) if coordinator.data else {}
        device_name = device_info.get("device_name", f"ThesslaGreen {coordinator.host}")
        
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_{key}"
        
        # Enhanced entity description for HA 2025.7+
        self._attr_entity_description = description
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # Enhanced pre-conditions validation (HA 2025.7+)
        if not self._validate_turn_on():
            return
            
        success = await self.coordinator.async_write_register(self._key, 1)
        if success:
            _LOGGER.info("Turned on %s", self._key)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn on %s", self._key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # Enhanced pre-conditions validation (HA 2025.7+)
        if not self._validate_turn_off():
            return
            
        success = await self.coordinator.async_write_register(self._key, 0)
        if success:
            _LOGGER.info("Turned off %s", self._key)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to turn off %s", self._key)

    def _validate_turn_on(self) -> bool:
        """Enhanced validation before turning on - HA 2025.7+."""
        if not self.coordinator.data:
            return True  # Allow if no data available
        
        # System power must be on for most other switches
        if self._key != "system_on_off":
            system_power = self.coordinator.data.get("system_on_off", False)
            if not system_power:
                _LOGGER.warning("Cannot enable %s while system power is off", self._key)
                return False
        
        # GWC specific validations
        if self._key == "gwc_active":
            outside_temp = self.coordinator.data.get("outside_temperature")
            if outside_temp is not None and outside_temp > 30:
                _LOGGER.warning("GWC may not be effective at high outside temperatures (%.1f°C)", outside_temp)
        
        # Bypass specific validations
        if self._key == "bypass_active":
            outside_temp = self.coordinator.data.get("outside_temperature")
            supply_temp = self.coordinator.data.get("supply_temperature")
            if outside_temp is not None and supply_temp is not None:
                temp_diff = abs(outside_temp - supply_temp)
                if temp_diff < 2:
                    _LOGGER.info("Bypass may not be beneficial with small temperature difference (%.1f°C)", temp_diff)
        
        # Cooling validation
        if self._key == "cooling_active":
            outside_temp = self.coordinator.data.get("outside_temperature")
            if outside_temp is not None and outside_temp < 20:
                _LOGGER.warning("Cooling may not be needed at low outside temperatures (%.1f°C)", outside_temp)
        
        # Preheating validation
        if self._key == "preheating_active":
            outside_temp = self.coordinator.data.get("outside_temperature")
            if outside_temp is not None and outside_temp > 25:
                _LOGGER.warning("Preheating may not be needed at high outside temperatures (%.1f°C)", outside_temp)
        
        return True

    def _validate_turn_off(self) -> bool:
        """Enhanced validation before turning off - HA 2025.7+."""
        if not self.coordinator.data:
            return True
        
        # Warn about turning off critical protections
        critical_switches = ["antifreeze_mode", "system_on_off"]
        if self._key in critical_switches:
            _LOGGER.info("Turning off critical system component: %s", self._key)
        
        # Antifreeze protection warning
        if self._key == "antifreeze_mode":
            outside_temp = self.coordinator.data.get("outside_temperature")
            if outside_temp is not None and outside_temp < 0:
                _LOGGER.warning("Disabling antifreeze protection in freezing conditions (%.1f°C)", outside_temp)
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "register_key": self._key,
            "description": getattr(self, '_attr_entity_description', ''),
        }
        
        # Enhanced context information (HA 2025.7+)
        if self._key == "gwc_active":
            gwc_temp = self.coordinator.data.get("gwc_temperature")
            gwc_efficiency = self.coordinator.data.get("gwc_efficiency")
            if gwc_temp is not None:
                attributes["gwc_temperature"] = gwc_temp
            if gwc_efficiency is not None:
                attributes["gwc_efficiency"] = f"{gwc_efficiency}%"
                
        elif self._key == "bypass_active":
            bypass_position = self.coordinator.data.get("bypass_position")
            bypass_mode = self.coordinator.data.get("bypass_mode")
            if bypass_position is not None:
                attributes["bypass_position"] = f"{bypass_position}%"
            if bypass_mode is not None:
                bypass_modes = {0: "Nieaktywny", 1: "FreeHeating", 2: "FreeCooling"}
                attributes["bypass_mode"] = bypass_modes.get(bypass_mode, "Unknown")
                
        elif self._key == "constant_flow_active":
            cf_supply = self.coordinator.data.get("constant_flow_supply")
            cf_exhaust = self.coordinator.data.get("constant_flow_exhaust")
            if cf_supply is not None:
                attributes["current_supply_flow"] = f"{cf_supply} m³/h"
            if cf_exhaust is not None:
                attributes["current_exhaust_flow"] = f"{cf_exhaust} m³/h"
                
        elif self._key == "comfort_active":
            comfort_mode = self.coordinator.data.get("comfort_mode")
            comfort_temp_heating = self.coordinator.data.get("comfort_temperature_heating")
            comfort_temp_cooling = self.coordinator.data.get("comfort_temperature_cooling")
            if comfort_mode is not None:
                modes = {0: "Nieaktywny", 1: "Grzanie", 2: "Chłodzenie"}
                attributes["comfort_mode"] = modes.get(comfort_mode, "Unknown")
            if comfort_temp_heating is not None:
                attributes["heating_setpoint"] = f"{comfort_temp_heating}°C"
            if comfort_temp_cooling is not None:
                attributes["cooling_setpoint"] = f"{comfort_temp_cooling}°C"
        
        # Add system status context
        if self._key != "system_on_off":
            system_power = self.coordinator.data.get("system_on_off", False)
            attributes["system_power_on"] = system_power
        
        # Add environmental context
        outside_temp = self.coordinator.data.get("outside_temperature")
        if outside_temp is not None and self._key in ["gwc_active", "bypass_active", "cooling_active", "preheating_active"]:
            attributes["outside_temperature"] = outside_temp
        
        # Add last update timestamp
        if hasattr(self.coordinator, 'last_update_success_time'):
            attributes["last_updated"] = self.coordinator.last_update_success_time.isoformat()
            
        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self._key in self.coordinator.data
        )


class ThesslaGreenMaintenanceSwitch(CoordinatorEntity, SwitchEntity):
    """Enhanced maintenance mode switch with safety features - HA 2025.7+."""

    def __init__(self, coordinator: ThesslaGreenCoordinator) -> None:
        """Initialize the enhanced maintenance switch."""
        super().__init__(coordinator)
        self._key = "maintenance_mode"
        
        device_info = coordinator.data.get("device_info", {}) if coordinator.data else {}
        device_name = device_info.get("device_name", f"ThesslaGreen {coordinator.host}")
        
        self._attr_name = "Maintenance Mode"
        self._attr_icon = "mdi:wrench"
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_unique_id = f"{coordinator.host}_{coordinator.slave_id}_maintenance_mode"
        self._attr_entity_description = "Enable maintenance mode for service operations"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{coordinator.host}_{coordinator.slave_id}")},
            "name": device_name,
            "manufacturer": "ThesslaGreen",
            "model": "AirPack Home",
            "sw_version": device_info.get("firmware", "Unknown"),
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if maintenance mode is active."""
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on maintenance mode with safety confirmation."""
        _LOGGER.warning("Activating maintenance mode - system will operate in reduced capacity")
        
        success = await self.coordinator.async_write_register(self._key, 1)
        if success:
            _LOGGER.info("Maintenance mode activated")
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to activate maintenance mode")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off maintenance mode and return to normal operation."""
        success = await self.coordinator.async_write_register(self._key, 0)
        if success:
            _LOGGER.info("Maintenance mode deactivated - returning to normal operation")
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to deactivate maintenance mode")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes = {
            "register_key": self._key,
            "description": "Service and maintenance mode for technical operations",
            "warning": "Only activate during scheduled maintenance",
        }
        
        # Add current system status
        system_power = self.coordinator.data.get("system_on_off", False)
        attributes["system_power_on"] = system_power
        
        # Add active error/warning status
        error_code = self.coordinator.data.get("error_code", 0)
        warning_code = self.coordinator.data.get("warning_code", 0)
        attributes["active_errors"] = error_code != 0
        attributes["active_warnings"] = warning_code != 0
        
        # Add service indicators
        filter_warning = self.coordinator.data.get("filter_warning", False)
        service_required = self.coordinator.data.get("service_required", False)
        attributes["filter_warning_active"] = filter_warning
        attributes["service_required"] = service_required
        
        if hasattr(self.coordinator, 'last_update_success_time'):
            attributes["last_updated"] = self.coordinator.last_update_success_time.isoformat()
            
        return attributes