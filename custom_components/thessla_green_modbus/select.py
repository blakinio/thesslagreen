"""Enhanced select platform for ThesslaGreen Modbus integration.
Wszystkie listy wyboru z kompletnej mapy rejestrów + autoscan.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
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
    """Set up enhanced select platform with comprehensive register support."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    input_regs = coordinator.available_registers.get("input_registers", set())
    
    # Operation Mode Selects - wszystkie z PDF + autoscan
    mode_selects = [
        ("mode", "Operation Mode", "mdi:cog", "Tryb pracy", {
            0: "Off", 1: "Manual", 2: "Auto", 3: "Temporary"
        }),
        ("season_mode", "Season Mode", "mdi:weather-partly-cloudy", "Tryb sezonowy", {
            0: "Auto", 1: "Winter", 2: "Summer"
        }),
        ("special_mode", "Special Mode", "mdi:star-settings", "Tryb specjalny", {
            0: "None", 1: "OKAP", 2: "KOMINEK", 3: "WIETRZENIE", 4: "PUSTY_DOM", 
            5: "BOOST", 6: "NIGHT", 7: "PARTY", 8: "VACATION", 9: "ECONOMY", 10: "COMFORT"
        }),
        ("bypass_mode", "Bypass Mode", "mdi:swap-horizontal", "Tryb bypass", {
            0: "Auto", 1: "Open", 2: "Closed"
        }),
        ("gwc_mode", "GWC Mode", "mdi:heat-pump", "Tryb GWC", {
            0: "Auto", 1: "On", 2: "Off"
        }),
        ("constant_flow_mode", "Constant Flow Mode", "mdi:fan-auto", "Tryb stałego przepływu", {
            0: "Off", 1: "Constant Volume", 2: "Constant Pressure"
        }),
        ("pressure_control_mode", "Pressure Control Mode", "mdi:gauge", "Tryb kontroli ciśnienia", {
            0: "Off", 1: "Constant", 2: "Variable", 3: "Adaptive"
        }),
    ]
    
    for select_key, name, icon, description, options in mode_selects:
        if select_key in holding_regs or select_key in input_regs:
            entities.append(
                ThesslaGreenModeSelect(
                    coordinator, select_key, name, icon, description, options
                )
            )
    
    # Filter and Maintenance Selects - wszystkie z PDF + autoscan
    filter_selects = [
        ("filter_type", "Filter Type", "mdi:air-filter", "Typ filtrów", {
            1: "Presostat", 2: "Flat Filters", 3: "CleanPad", 4: "CleanPad Pure"
        }),
        ("presostat_check_day", "Presostat Check Day", "mdi:calendar-check", "Dzień kontroli presostatu", {
            0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"
        }),
    ]
    
    for select_key, name, icon, description, options in filter_selects:
        if select_key in holding_regs:
            entities.append(
                ThesslaGreenMaintenanceSelect(
                    coordinator, select_key, name, icon, description, options
                )
            )
    
    # Communication Selects - wszystkie z PDF + autoscan
    communication_selects = [
        ("uart0_baud", "Air-B Port Baud Rate", "mdi:speedometer", "Szybkość transmisji Air-B", {
            0: "4800", 1: "9600", 2: "14400", 3: "19200", 4: "28800", 5: "38400", 6: "57600", 7: "76800", 8: "115200"
        }),
        ("uart0_parity", "Air-B Port Parity", "mdi:check-network", "Parzystość Air-B", {
            0: "None", 1: "Even", 2: "Odd"
        }),
        ("uart0_stop", "Air-B Port Stop Bits", "mdi:stop", "Bity stopu Air-B", {
            0: "One", 1: "Two"
        }),
        ("uart1_baud", "Air++ Port Baud Rate", "mdi:speedometer", "Szybkość transmisji Air++", {
            0: "4800", 1: "9600", 2: "14400", 3: "19200", 4: "28800", 5: "38400", 6: "57600", 7: "76800", 8: "115200"
        }),
        ("uart1_parity", "Air++ Port Parity", "mdi:check-network", "Parzystość Air++", {
            0: "None", 1: "Even", 2: "Odd"
        }),
        ("uart1_stop", "Air++ Port Stop Bits", "mdi:stop", "Bity stopu Air++", {
            0: "One", 1: "Two"
        }),
    ]
    
    for select_key, name, icon, description, options in communication_selects:
        if select_key in holding_regs:
            entities.append(
                ThesslaGreenCommunicationSelect(
                    coordinator, select_key, name, icon, description, options
                )
            )
    
    # System Configuration Selects - wszystkie z PDF + autoscan
    config_selects = [
        ("system_language", "System Language", "mdi:translate", "Język systemu", {
            0: "Polish", 1: "English", 2: "German", 3: "French", 4: "Italian", 5: "Spanish"
        }),
        ("date_format", "Date Format", "mdi:calendar", "Format daty", {
            0: "DD.MM.YYYY", 1: "MM/DD/YYYY", 2: "YYYY-MM-DD"
        }),
        ("time_format", "Time Format", "mdi:clock", "Format czasu", {
            0: "24H", 1: "12H"
        }),
        ("unit_system", "Unit System", "mdi:ruler", "System jednostek", {
            0: "Metric", 1: "Imperial"
        }),
        ("time_zone", "Time Zone", "mdi:earth", "Strefa czasowa", {
            0: "UTC-12", 1: "UTC-11", 2: "UTC-10", 3: "UTC-9", 4: "UTC-8", 5: "UTC-7", 6: "UTC-6",
            7: "UTC-5", 8: "UTC-4", 9: "UTC-3", 10: "UTC-2", 11: "UTC-1", 12: "UTC+0", 
            13: "UTC+1", 14: "UTC+2", 15: "UTC+3", 16: "UTC+4", 17: "UTC+5", 18: "UTC+6",
            19: "UTC+7", 20: "UTC+8", 21: "UTC+9", 22: "UTC+10", 23: "UTC+11", 24: "UTC+12"
        }),
        ("decimal_places", "Decimal Places", "mdi:decimal", "Miejsca dziesiętne", {
            0: "0", 1: "1", 2: "2", 3: "3"
        }),
        ("optimization_target", "Optimization Target", "mdi:target", "Cel optymalizacji", {
            0: "Comfort", 1: "Economy", 2: "Efficiency", 3: "Balanced"
        }),
    ]
    
    for select_key, name, icon, description, options in config_selects:
        if select_key in holding_regs:
            entities.append(
                ThesslaGreenConfigSelect(
                    coordinator, select_key, name, icon, description, options
                )
            )
    
    # Status Selects (Read-only) - wszystkie z PDF + autoscan
    status_selects = [
        ("day_of_week", "Current Day", "mdi:calendar-today", "Bieżący dzień tygodnia", {
            0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"
        }),
        ("period", "Current Period", "mdi:clock-outline", "Bieżący odcinek czasowy", {
            0: "Period 1", 1: "Period 2", 2: "Period 3", 3: "Period 4"
        }),
        ("current_program", "Current Program", "mdi:play", "Aktualny program pracy", {
            0: "Manual", 1: "Auto Schedule", 2: "Special Mode", 3: "Emergency", 4: "Maintenance"
        }),
        ("presostat_status", "Presostat Status", "mdi:air-filter", "Status presostatu", {
            0: "OK", 1: "Warning", 2: "Alarm", 3: "Error"
        }),
    ]
    
    for select_key, name, icon, description, options in status_selects:
        if select_key in input_regs:
            entities.append(
                ThesslaGreenStatusSelect(
                    coordinator, select_key, name, icon, description, options
                )
            )
    
    # Schedule Time Selects - przykłady z harmonogramu + autoscan
    schedule_selects = []
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    periods = [1, 2, 3, 4]
    
    # Generate time options (HHMM format)
    time_options = {}
    for hour in range(0, 24):
        for minute in [0, 15, 30, 45]:
            time_key = hour * 100 + minute
            time_options[time_key] = f"{hour:02d}:{minute:02d}"
    
    # Add schedule selects for first day as example (można rozszerzyć dla wszystkich dni)
    for day in ["mon"]:  # Ograniczamy do poniedziałku dla przykładu
        for period in [1, 2]:  # Ograniczamy do 2 okresów dla przykładu
            start_key = f"schedule_{day}_period{period}_start"
            end_key = f"schedule_{day}_period{period}_end"
            
            if start_key in holding_regs:
                schedule_selects.append((
                    start_key, f"{day.title()} Period {period} Start", "mdi:clock-start",
                    f"Czas rozpoczęcia {day} okres {period}", time_options
                ))
            
            if end_key in holding_regs:
                schedule_selects.append((
                    end_key, f"{day.title()} Period {period} End", "mdi:clock-end",
                    f"Czas zakończenia {day} okres {period}", time_options
                ))
    
    for select_key, name, icon, description, options in schedule_selects:
        entities.append(
            ThesslaGreenScheduleSelect(
                coordinator, select_key, name, icon, description, options
            )
        )
    
    if entities:
        _LOGGER.info("Adding %d select entities (autoscan detected)", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No select entities created - check device connectivity and register availability")


class ThesslaGreenBaseSelect(CoordinatorEntity, SelectEntity):
    """Base select for ThesslaGreen devices with enhanced functionality."""
    
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        options_map: dict[int, str],
        entity_category: EntityCategory | None = None,
        read_only: bool = False,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self._key = key
        self._options_map = options_map
        self._reverse_options_map = {v: k for k, v in options_map.items()}
        self._read_only = read_only
        self._attr_name = name
        self._attr_icon = icon
        self._attr_entity_category = entity_category
        self._attr_translation_key = key
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.', '_')}_{coordinator.slave_id}_{key}"
        self._attr_entity_registry_enabled_default = True
        self._attr_options = list(options_map.values())
        
        # Enhanced device info
        self._attr_device_info = coordinator.device_info
        self._attr_extra_state_attributes = {
            "description": description,
            "register_key": key,
            "read_only": read_only,
            "last_updated": None,
        }

    @property
    def available(self) -> bool:
        """Return if select is available."""
        if not self.coordinator.last_update_success:
            return False
        
        # Check if register is marked as unavailable
        perf_stats = self.coordinator.performance_stats
        if self._key in perf_stats.get("unavailable_registers", set()):
            return False
            
        return self._key in self.coordinator.data

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        if not self.available:
            return None
        
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        
        # Handle special cases
        if self._key == "filter_type" and isinstance(value, dict):
            # Filter type might be returned as dict with value and description
            raw_value = value.get("value", value)
        else:
            raw_value = value
        
        # Convert to integer if needed
        try:
            int_value = int(raw_value)
            return self._options_map.get(int_value)
        except (ValueError, TypeError):
            # Fallback to string matching
            str_value = str(raw_value)
            for option in self.options:
                if option.lower() == str_value.lower():
                    return option
        
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = self._attr_extra_state_attributes.copy()
        
        if self.coordinator.last_update_success:
            attrs["last_updated"] = self.coordinator.last_update_success_time
        
        # Add register-specific diagnostic info
        perf_stats = self.coordinator.performance_stats
        reg_stats = perf_stats.get("register_read_stats", {}).get(self._key, {})
        
        if reg_stats:
            attrs["success_count"] = reg_stats.get("success_count", 0)
            if "last_success" in reg_stats and reg_stats["last_success"]:
                attrs["last_success"] = reg_stats["last_success"]
        
        # Add intermittent status
        if self._key in perf_stats.get("intermittent_registers", set()):
            attrs["status"] = "intermittent"
        
        # Add raw value for debugging
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is not None:
            attrs["raw_value"] = raw_value
        
        # Add all available options with their numeric values
        attrs["options_map"] = self._options_map
        
        return attrs

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if self._read_only:
            _LOGGER.warning("Cannot set read-only select %s", self._attr_name)
            return
        
        if option not in self.options:
            _LOGGER.warning("Option %s not valid for %s", option, self._attr_name)
            return
        
        # Get numeric value for the option
        numeric_value = self._reverse_options_map.get(option)
        if numeric_value is None:
            _LOGGER.error("Could not find numeric value for option %s", option)
            return
        
        success = await self.coordinator.async_write_register(self._key, numeric_value)
        
        if success:
            _LOGGER.info("Set %s to %s (%d)", self._attr_name, option, numeric_value)
        else:
            _LOGGER.error("Failed to set %s to %s", self._attr_name, option)


class ThesslaGreenModeSelect(ThesslaGreenBaseSelect):
    """Mode selection for operation modes."""
    
    async def async_select_option(self, option: str) -> None:
        """Select mode with additional logic."""
        # For certain mode changes, we may need to update related settings
        if self._key == "mode":
            # When changing operation mode, ensure system is on
            if option != "Off":
                await self.coordinator.async_write_register("on_off_panel_mode", 1)
            else:
                await self.coordinator.async_write_register("on_off_panel_mode", 0)
        
        elif self._key == "special_mode":
            # When activating special mode, ensure system is in appropriate state
            if option != "None":
                await self.coordinator.async_write_register("on_off_panel_mode", 1)
                # Set to manual mode for special modes to work properly
                await self.coordinator.async_write_register("mode", 1)
        
        await super().async_select_option(option)


class ThesslaGreenMaintenanceSelect(ThesslaGreenBaseSelect):
    """Maintenance-related selection."""
    
    _attr_entity_category = EntityCategory.CONFIG


class ThesslaGreenCommunicationSelect(ThesslaGreenBaseSelect):
    """Communication settings selection."""
    
    _attr_entity_category = EntityCategory.CONFIG


class ThesslaGreenConfigSelect(ThesslaGreenBaseSelect):
    """System configuration selection."""
    
    _attr_entity_category = EntityCategory.CONFIG


class ThesslaGreenStatusSelect(ThesslaGreenBaseSelect):
    """Status display selection (read-only)."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        options_map: dict[int, str],
    ) -> None:
        """Initialize status select."""
        super().__init__(coordinator, key, name, icon, description, options_map, EntityCategory.DIAGNOSTIC, read_only=True)

    async def async_select_option(self, option: str) -> None:
        """Status selects are read-only."""
        _LOGGER.warning("Cannot change read-only status select %s", self._attr_name)


class ThesslaGreenScheduleSelect(ThesslaGreenBaseSelect):
    """Schedule time selection."""
    
    _attr_entity_category = EntityCategory.CONFIG
    
    @property
    def current_option(self) -> str | None:
        """Return current time option formatted as HH:MM."""
        if not self.available:
            return None
        
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        
        # Handle time values that might be formatted as string (HH:MM) or integer (HHMM)
        if isinstance(value, str) and ":" in value:
            return value  # Already formatted
        
        try:
            int_value = int(value)
            return self._options_map.get(int_value)
        except (ValueError, TypeError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Select time option."""
        # Convert HH:MM format to HHMM integer
        try:
            if ":" in option:
                hours, minutes = option.split(":")
                numeric_value = int(hours) * 100 + int(minutes)
            else:
                numeric_value = self._reverse_options_map.get(option)
            
            if numeric_value is None:
                _LOGGER.error("Could not convert time option %s to numeric value", option)
                return
            
            success = await self.coordinator.async_write_register(self._key, numeric_value)
            
            if success:
                _LOGGER.info("Set %s to %s (%d)", self._attr_name, option, numeric_value)
            else:
                _LOGGER.error("Failed to set %s to %s", self._attr_name, option)
                
        except ValueError as exc:
            _LOGGER.error("Invalid time format %s: %s", option, exc)