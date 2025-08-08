"""Enhanced switch platform for ThesslaGreen Modbus integration.
Wszystkie przełączniki z kompletnej mapy rejestrów + autoscan.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
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
    """Set up enhanced switch platform with comprehensive register support."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    coil_regs = coordinator.available_registers.get("coil_registers", set())
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # System Control Switches - wszystkie z PDF + autoscan
    system_control_switches = [
        # Main system controls
        ("power_supply_fans", "Fan Power Supply", "mdi:fan", "Zasilanie wentylatorów", SwitchDeviceClass.SWITCH),
        ("heating_cable", "Heating Cable", "mdi:cable-data", "Kabel grzejny", SwitchDeviceClass.SWITCH),
        ("duct_water_heater_pump", "Water Heater Pump", "mdi:pump", "Pompa obiegowa nagrzewnicy", SwitchDeviceClass.SWITCH),
        ("work_permit", "Work Permit", "mdi:check-circle", "Potwierdzenie pracy (Expansion)", SwitchDeviceClass.SWITCH),
        ("info", "System Running Signal", "mdi:information", "Sygnał potwierdzenia pracy centrali", SwitchDeviceClass.SWITCH),
        
        # Climate control systems
        ("bypass", "Bypass", "mdi:swap-horizontal", "Siłownik przepustnicy bypass", SwitchDeviceClass.SWITCH),
        ("gwc", "GWC System", "mdi:heat-pump", "System GWC", SwitchDeviceClass.SWITCH),
        ("hood", "Hood Control", "mdi:cooktop", "Przepustnica okapu", SwitchDeviceClass.SWITCH),
        ("heating_control", "Heating Control", "mdi:radiator", "Sterowanie grzaniem", SwitchDeviceClass.SWITCH),
        ("cooling_control", "Cooling Control", "mdi:snowflake", "Sterowanie chłodzeniem", SwitchDeviceClass.SWITCH),
        
        # Protection systems
        ("frost_protection", "Frost Protection", "mdi:snowflake-alert", "Ochrona przeciwmrozowa", SwitchDeviceClass.SWITCH),
        ("overheat_protection", "Overheat Protection", "mdi:thermometer-alert", "Ochrona przed przegrzaniem", SwitchDeviceClass.SWITCH),
        
        # Advanced control features
        ("constant_flow_control", "Constant Flow Control", "mdi:fan-auto", "Sterowanie stałym przepływem", SwitchDeviceClass.SWITCH),
        ("pressure_control", "Pressure Control", "mdi:gauge", "Sterowanie ciśnieniem", SwitchDeviceClass.SWITCH),
        ("temperature_control", "Temperature Control", "mdi:thermometer", "Sterowanie temperaturą", SwitchDeviceClass.SWITCH),
        ("co2_control", "CO2 Control", "mdi:molecule-co2", "Sterowanie na podstawie CO2", SwitchDeviceClass.SWITCH),
        ("humidity_control", "Humidity Control", "mdi:water-percent", "Sterowanie na podstawie wilgotności", SwitchDeviceClass.SWITCH),
        ("occupancy_control", "Occupancy Control", "mdi:account-check", "Sterowanie na podstawie obecności", SwitchDeviceClass.SWITCH),
        
        # Output controls
        ("alarm_output", "Alarm Output", "mdi:alarm-light", "Wyjście alarmowe", SwitchDeviceClass.OUTLET),
        ("status_output", "Status Output", "mdi:led-on", "Wyjście statusowe", SwitchDeviceClass.OUTLET),
    ]
    
    for switch_key, name, icon, description, device_class in system_control_switches:
        if switch_key in coil_regs:
            entities.append(
                ThesslaGreenControlSwitch(
                    coordinator, switch_key, name, icon, description, device_class
                )
            )
    
    # Mode Switches - wszystkie z PDF + autoscan
    mode_switches = [
        # Season modes
        ("summer_mode", "Summer Mode", "mdi:weather-sunny", "Tryb letni", None),
        ("winter_mode", "Winter Mode", "mdi:weather-snowy", "Tryb zimowy", None),
        
        # Operation modes
        ("auto_mode", "Auto Mode", "mdi:autorenew", "Tryb automatyczny", None),
        ("manual_mode", "Manual Mode", "mdi:hand-extended", "Tryb manualny", None),
        ("temporary_mode", "Temporary Mode", "mdi:clock-fast", "Tryb tymczasowy", None),
        
        # Special modes
        ("night_mode", "Night Mode", "mdi:weather-night", "Tryb nocny", None),
        ("party_mode", "Party Mode", "mdi:party-popper", "Tryb party", None),
        ("vacation_mode", "Vacation Mode", "mdi:airplane", "Tryb wakacyjny", None),
        ("boost_mode", "Boost Mode", "mdi:rocket-launch", "Tryb boost", None),
        ("economy_mode", "Economy Mode", "mdi:leaf", "Tryb ekonomiczny", None),
        ("comfort_mode", "Comfort Mode", "mdi:home-heart", "Tryb komfort", None),
        ("silent_mode", "Silent Mode", "mdi:volume-off", "Tryb cichy", None),
        ("fireplace_mode", "Fireplace Mode", "mdi:fireplace", "Tryb kominkowy", None),
        ("kitchen_hood_mode", "Kitchen Hood Mode", "mdi:cooktop", "Tryb okapu kuchennego", None),
        ("bathroom_mode", "Bathroom Mode", "mdi:shower", "Tryb łazienkowy", None),
    ]
    
    for switch_key, name, icon, description, device_class in mode_switches:
        if switch_key in coil_regs:
            entities.append(
                ThesslaGreenModeSwitch(
                    coordinator, switch_key, name, icon, description, device_class
                )
            )
    
    # Configuration Switches - wszystkie z PDF + autoscan
    config_switches = [
        # System configuration
        ("auto_start", "Auto Start", "mdi:power", "Autostart po awarii zasilania", None),
        ("summer_winter_auto", "Auto Season Switch", "mdi:autorenew", "Automatyczne przełączanie lato/zima", None),
        ("daylight_saving", "Daylight Saving", "mdi:clock-fast", "Automatyczne przejście na czas letni", None),
        ("sound_enabled", "Sound Enabled", "mdi:volume-high", "Sygnały dźwiękowe", SwitchDeviceClass.SWITCH),
        ("led_enabled", "LED Enabled", "mdi:led-on", "Sygnalizacja LED", SwitchDeviceClass.SWITCH),
        ("keypad_lock", "Keypad Lock", "mdi:lock", "Blokada klawiatury", None),
        
        # Advanced features
        ("adaptive_control", "Adaptive Control", "mdi:brain", "Sterowanie adaptacyjne", None),
        ("learning_mode", "Learning Mode", "mdi:school", "Tryb uczenia się", None),
        ("smart_recovery", "Smart Recovery", "mdi:recycle", "Inteligentny odzysk ciepła", None),
        ("demand_control", "Demand Control", "mdi:chart-line", "Sterowanie na żądanie", None),
        ("occupancy_detection", "Occupancy Detection", "mdi:account-search", "Wykrywanie obecności", None),
        
        # Network configuration
        ("ethernet_dhcp", "Ethernet DHCP", "mdi:router", "DHCP Ethernet", SwitchDeviceClass.SWITCH),
        
        # Maintenance features
        ("filter_change_reminder", "Filter Change Reminder", "mdi:air-filter", "Przypomnienie wymiany filtrów", None),
        ("maintenance_reminder", "Maintenance Reminder", "mdi:wrench-clock", "Przypomnienie serwisu", None),
    ]
    
    for switch_key, name, icon, description, device_class in config_switches:
        if switch_key in coil_regs or switch_key in holding_regs:
            entities.append(
                ThesslaGreenConfigSwitch(
                    coordinator, switch_key, name, icon, description, device_class
                )
            )
    
    # System Enable/Disable Switches - z holding registers
    system_switches = [
        ("on_off_panel_mode", "System Power", "mdi:power", "Główne włączenie/wyłączenie systemu", SwitchDeviceClass.SWITCH),
        ("device_lock", "Device Lock", "mdi:lock", "Blokada urządzenia", None),
    ]
    
    for switch_key, name, icon, description, device_class in system_switches:
        if switch_key in holding_regs:
            entities.append(
                ThesslaGreenSystemSwitch(
                    coordinator, switch_key, name, icon, description, device_class
                )
            )
    
    # Reset and Maintenance Switches - z holding registers
    maintenance_switches = [
        ("factory_reset", "Factory Reset", "mdi:factory", "Reset fabryczny", None),
        ("settings_reset", "Settings Reset", "mdi:cog-refresh", "Reset ustawień użytkownika", None),
        ("schedule_reset", "Schedule Reset", "mdi:calendar-refresh", "Reset harmonogramu", None),
        ("statistics_reset", "Statistics Reset", "mdi:chart-line-variant", "Reset statystyk", None),
        ("error_log_reset", "Error Log Reset", "mdi:alert-remove", "Reset dziennika błędów", None),
    ]
    
    for switch_key, name, icon, description, device_class in maintenance_switches:
        if switch_key in holding_regs:
            entities.append(
                ThesslaGreenMaintenanceSwitch(
                    coordinator, switch_key, name, icon, description, device_class
                )
            )
    
    if entities:
        _LOGGER.info("Adding %d switch entities (autoscan detected)", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No switch entities created - check device connectivity and register availability")


class ThesslaGreenBaseSwitch(CoordinatorEntity, SwitchEntity):
    """Base switch for ThesslaGreen devices with enhanced functionality."""
    
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        device_class: SwitchDeviceClass | None,
        register_type: str = "coil",
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._key = key
        self._register_type = register_type
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_translation_key = key
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.', '_')}_{coordinator.slave_id}_{key}"
        self._attr_entity_registry_enabled_default = True
        
        # Enhanced device info
        self._attr_device_info = coordinator.device_info
        self._attr_extra_state_attributes = {
            "description": description,
            "register_key": key,
            "register_type": register_type,
            "last_updated": None,
        }

    @property
    def available(self) -> bool:
        """Return if switch is available."""
        if not self.coordinator.last_update_success:
            return False
        
        # Check if register is marked as unavailable
        perf_stats = self.coordinator.performance_stats
        if self._key in perf_stats.get("unavailable_registers", set()):
            return False
            
        return self._key in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if not self.available:
            return None
        
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        
        # Handle different value types
        if isinstance(value, bool):
            return value
        elif isinstance(value, int):
            return bool(value)
        elif isinstance(value, str):
            return value.lower() in ("on", "true", "1", "active", "yes")
        
        return bool(value)

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
        
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        success = await self.coordinator.async_write_register(self._key, True)
        
        if success:
            _LOGGER.info("Turned on %s", self._attr_name)
        else:
            _LOGGER.error("Failed to turn on %s", self._attr_name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        success = await self.coordinator.async_write_register(self._key, False)
        
        if success:
            _LOGGER.info("Turned off %s", self._attr_name)
        else:
            _LOGGER.error("Failed to turn off %s", self._attr_name)


class ThesslaGreenControlSwitch(ThesslaGreenBaseSwitch):
    """Control switch for system operations."""
    
    pass


class ThesslaGreenModeSwitch(ThesslaGreenBaseSwitch):
    """Mode switch for operation modes."""
    
    _attr_entity_category = EntityCategory.CONFIG
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the mode on and ensure mutual exclusion."""
        # For mode switches, turning one on may require turning others off
        mode_groups = {
            # Season modes are mutually exclusive
            "summer_mode": ["winter_mode"],
            "winter_mode": ["summer_mode"],
            
            # Operation modes are mutually exclusive
            "auto_mode": ["manual_mode", "temporary_mode"],
            "manual_mode": ["auto_mode", "temporary_mode"],
            "temporary_mode": ["auto_mode", "manual_mode"],
            
            # Special modes should turn off conflicting modes
            "night_mode": ["party_mode", "boost_mode"],
            "party_mode": ["night_mode", "silent_mode"],
            "boost_mode": ["night_mode", "silent_mode"],
            "silent_mode": ["party_mode", "boost_mode"],
        }
        
        # Turn off conflicting modes first
        if self._key in mode_groups:
            for conflicting_mode in mode_groups[self._key]:
                if conflicting_mode in self.coordinator.available_registers.get("coil_registers", set()):
                    await self.coordinator.async_write_register(conflicting_mode, False)
        
        # Now turn on this mode
        await super().async_turn_on(**kwargs)


class ThesslaGreenConfigSwitch(ThesslaGreenBaseSwitch):
    """Configuration switch for system settings."""
    
    _attr_entity_category = EntityCategory.CONFIG
    
    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        device_class: SwitchDeviceClass | None,
    ) -> None:
        """Initialize config switch."""
        # Determine register type based on availability
        if key in coordinator.available_registers.get("holding_registers", set()):
            register_type = "holding"
        else:
            register_type = "coil"
        
        super().__init__(coordinator, key, name, icon, description, device_class, register_type)


class ThesslaGreenSystemSwitch(ThesslaGreenBaseSwitch):
    """System-level switch for main controls."""
    
    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        device_class: SwitchDeviceClass | None,
    ) -> None:
        """Initialize system switch."""
        super().__init__(coordinator, key, name, icon, description, device_class, "holding")
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the system switch on with additional logic."""
        if self._key == "on_off_panel_mode":
            # When turning on main power, ensure system is in a valid state
            success = await self.coordinator.async_write_register(self._key, 1)
            if success:
                # Set to auto mode by default when turning on
                await self.coordinator.async_write_register("mode", 2)
        else:
            success = await self.coordinator.async_write_register(self._key, 1)
        
        if success:
            _LOGGER.info("Turned on system switch %s", self._attr_name)
        else:
            _LOGGER.error("Failed to turn on system switch %s", self._attr_name)
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the system switch off with additional logic."""
        if self._key == "on_off_panel_mode":
            # When turning off main power, also stop special modes
            await self.coordinator.async_write_register("special_mode", 0)
        
        success = await self.coordinator.async_write_register(self._key, 0)
        
        if success:
            _LOGGER.info("Turned off system switch %s", self._attr_name)
        else:
            _LOGGER.error("Failed to turn off system switch %s", self._attr_name)


class ThesslaGreenMaintenanceSwitch(ThesslaGreenBaseSwitch):
    """Maintenance switch for reset and maintenance operations."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        device_class: SwitchDeviceClass | None,
    ) -> None:
        """Initialize maintenance switch."""
        super().__init__(coordinator, key, name, icon, description, device_class, "holding")
    
    @property
    def is_on(self) -> bool | None:
        """Maintenance switches are always off (reset operations are momentary)."""
        return False
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Perform maintenance operation (write 1 then back to 0)."""
        # Write 1 to trigger the reset/maintenance operation
        success = await self.coordinator.async_write_register(self._key, 1)
        
        if success:
            _LOGGER.warning("Triggered maintenance operation: %s", self._attr_name)
            
            # For safety, immediately write 0 back to prevent accidental repeat
            await self.coordinator.async_write_register(self._key, 0)
        else:
            _LOGGER.error("Failed to trigger maintenance operation: %s", self._attr_name)
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Maintenance switches cannot be turned off (they're always off)."""
        _LOGGER.debug("Maintenance switch %s is always off", self._attr_name)