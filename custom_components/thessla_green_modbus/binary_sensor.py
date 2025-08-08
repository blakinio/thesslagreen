"""Enhanced binary sensor platform for ThesslaGreen Modbus integration.
Wszystkie sensory binarne z kompletnej mapy rejestrów + autoscan.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up enhanced binary sensor platform with comprehensive register support."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    coil_regs = coordinator.available_registers.get("coil_registers", set())
    discrete_regs = coordinator.available_registers.get("discrete_inputs", set())
    input_regs = coordinator.available_registers.get("input_registers", set())
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # System Status Binary Sensors - wszystkie z PDF + autoscan
    system_status_sensors = [
        # Coil registers - outputs/actuators
        ("duct_water_heater_pump", "Water Heater Pump", "mdi:pump", "Stan pompy obiegowej nagrzewnicy", BinarySensorDeviceClass.RUNNING),
        ("bypass", "Bypass", "mdi:swap-horizontal", "Stan siłownika przepustnicy bypass", None),
        ("info", "System Running", "mdi:information", "Sygnał potwierdzenia pracy centrali", BinarySensorDeviceClass.RUNNING),
        ("power_supply_fans", "Fan Power Supply", "mdi:fan", "Stan zasilania wentylatorów", BinarySensorDeviceClass.POWER),
        ("heating_cable", "Heating Cable", "mdi:cable-data", "Stan zasilania kabla grzejnego", BinarySensorDeviceClass.HEAT),
        ("work_permit", "Work Permit", "mdi:check-circle", "Potwierdzenie pracy (Expansion)", None),
        ("gwc", "GWC Active", "mdi:heat-pump", "Stan przekaźnika GWC", BinarySensorDeviceClass.RUNNING),
        ("hood", "Hood Active", "mdi:cooktop", "Stan zasilania przepustnicy okapu", BinarySensorDeviceClass.RUNNING),
        
        # Extended coil registers
        ("summer_mode", "Summer Mode", "mdi:weather-sunny", "Aktywacja trybu letniego", None),
        ("winter_mode", "Winter Mode", "mdi:weather-snowy", "Aktywacja trybu zimowego", None),
        ("auto_mode", "Auto Mode", "mdi:autorenew", "Aktywacja trybu automatycznego", None),
        ("manual_mode", "Manual Mode", "mdi:hand-extended", "Aktywacja trybu manualnego", None),
        ("temporary_mode", "Temporary Mode", "mdi:clock-fast", "Aktywacja trybu tymczasowego", None),
        ("night_mode", "Night Mode", "mdi:weather-night", "Aktywacja trybu nocnego", None),
        ("party_mode", "Party Mode", "mdi:party-popper", "Aktywacja trybu party", None),
        ("vacation_mode", "Vacation Mode", "mdi:airplane", "Aktywacja trybu wakacyjnego", None),
        ("boost_mode", "Boost Mode", "mdi:rocket-launch", "Aktywacja trybu boost", None),
        ("economy_mode", "Economy Mode", "mdi:leaf", "Aktywacja trybu ekonomicznego", None),
        ("comfort_mode", "Comfort Mode", "mdi:home-heart", "Aktywacja trybu komfort", None),
        ("silent_mode", "Silent Mode", "mdi:volume-off", "Aktywacja trybu cichego", None),
        ("fireplace_mode", "Fireplace Mode", "mdi:fireplace", "Aktywacja trybu kominkowego", None),
        ("kitchen_hood_mode", "Kitchen Hood Mode", "mdi:cooktop", "Aktywacja trybu okapu kuchennego", None),
        ("bathroom_mode", "Bathroom Mode", "mdi:shower", "Aktywacja trybu łazienkowego", None),
        
        # Control modes
        ("co2_control", "CO2 Control", "mdi:molecule-co2", "Sterowanie na podstawie CO2", None),
        ("humidity_control", "Humidity Control", "mdi:water-percent", "Sterowanie na podstawie wilgotności", None),
        ("occupancy_control", "Occupancy Control", "mdi:account-check", "Sterowanie na podstawie obecności", None),
        ("constant_flow_control", "Constant Flow Control", "mdi:fan-auto", "Sterowanie stałym przepływem", None),
        ("pressure_control", "Pressure Control", "mdi:gauge", "Sterowanie ciśnieniem", None),
        ("temperature_control", "Temperature Control", "mdi:thermometer", "Sterowanie temperaturą", None),
        ("bypass_control", "Bypass Control", "mdi:swap-horizontal", "Sterowanie bypass", None),
        ("gwc_control", "GWC Control", "mdi:heat-pump", "Sterowanie GWC", None),
        ("heating_control", "Heating Control", "mdi:radiator", "Sterowanie grzaniem", BinarySensorDeviceClass.HEAT),
        ("cooling_control", "Cooling Control", "mdi:snowflake", "Sterowanie chłodzeniem", BinarySensorDeviceClass.COLD),
        
        # Protection systems
        ("frost_protection", "Frost Protection", "mdi:snowflake-alert", "Ochrona przeciwmrozowa", None),
        ("overheat_protection", "Overheat Protection", "mdi:thermometer-alert", "Ochrona przed przegrzaniem", None),
        
        # Maintenance and alarms
        ("filter_change_reminder", "Filter Change Reminder", "mdi:air-filter", "Przypomnienie o wymianie filtrów", None),
        ("maintenance_reminder", "Maintenance Reminder", "mdi:wrench-clock", "Przypomnienie o serwisie", None),
        ("alarm_output", "Alarm Output", "mdi:alarm-light", "Wyjście alarmowe", None),
        ("status_output", "Status Output", "mdi:led-on", "Wyjście statusowe", None),
        ("communication_ok", "Communication OK", "mdi:wifi-check", "Komunikacja OK", BinarySensorDeviceClass.CONNECTIVITY),
    ]
    
    for sensor_key, name, icon, description, device_class in system_status_sensors:
        if sensor_key in coil_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, description, device_class, "coil"
                )
            )
    
    # Input Status Binary Sensors - wszystkie z PDF + autoscan
    input_status_sensors = [
        # Discrete inputs - external inputs/sensors
        ("expansion", "Expansion Module", "mdi:expansion-card", "Stan modułu rozszerzającego", BinarySensorDeviceClass.CONNECTIVITY),
        ("fire_alarm", "Fire Alarm", "mdi:fire-alert", "Stan sygnału pożarowego PPOŻ", BinarySensorDeviceClass.SAFETY),
        ("external_stop", "External Stop", "mdi:stop-circle", "Stan zatrzymania zewnętrznego", None),
        ("window_contact", "Window Contact", "mdi:window-open-variant", "Stan kontaktronu okna", BinarySensorDeviceClass.WINDOW),
        ("door_contact", "Door Contact", "mdi:door-open", "Stan kontaktronu drzwi", BinarySensorDeviceClass.DOOR),
        ("presence_sensor", "Presence Sensor", "mdi:motion-sensor", "Stan czujnika obecności", BinarySensorDeviceClass.OCCUPANCY),
        ("motion_sensor", "Motion Sensor", "mdi:run", "Stan czujnika ruchu", BinarySensorDeviceClass.MOTION),
        ("light_sensor", "Light Sensor", "mdi:brightness-6", "Stan czujnika światła", BinarySensorDeviceClass.LIGHT),
        ("sound_sensor", "Sound Sensor", "mdi:microphone", "Stan czujnika dźwięku", BinarySensorDeviceClass.SOUND),
        ("external_alarm", "External Alarm", "mdi:alarm", "Stan alarmu zewnętrznego", None),
        ("maintenance_switch", "Maintenance Switch", "mdi:wrench", "Stan przełącznika serwisowego", None),
        ("emergency_switch", "Emergency Switch", "mdi:alert-octagon", "Stan przełącznika awaryjnego", None),
        ("filter_pressure_switch", "Filter Pressure Switch", "mdi:air-filter", "Stan przełącznika ciśnienia filtrów", None),
        ("high_pressure_switch", "High Pressure Switch", "mdi:gauge-full", "Stan przełącznika wysokiego ciśnienia", None),
        ("low_pressure_switch", "Low Pressure Switch", "mdi:gauge-empty", "Stan przełącznika niskiego ciśnienia", None),
        ("temperature_switch", "Temperature Switch", "mdi:thermometer", "Stan przełącznika temperatury", BinarySensorDeviceClass.HEAT),
        ("humidity_switch", "Humidity Switch", "mdi:water-percent", "Stan przełącznika wilgotności", BinarySensorDeviceClass.MOISTURE),
        ("air_quality_switch", "Air Quality Switch", "mdi:air-filter", "Stan przełącznika jakości powietrza", None),
        ("co2_switch", "CO2 Switch", "mdi:molecule-co2", "Stan przełącznika CO2", BinarySensorDeviceClass.GAS),
        ("voc_switch", "VOC Switch", "mdi:air-purifier", "Stan przełącznika VOC", BinarySensorDeviceClass.GAS),
        
        # Communication and external systems
        ("external_controller", "External Controller", "mdi:remote", "Stan kontrolera zewnętrznego", BinarySensorDeviceClass.CONNECTIVITY),
        ("building_management", "Building Management", "mdi:office-building", "Stan systemu zarządzania budynkiem", BinarySensorDeviceClass.CONNECTIVITY),
        ("modbus_communication", "Modbus Communication", "mdi:lan", "Stan komunikacji Modbus", BinarySensorDeviceClass.CONNECTIVITY),
        ("ethernet_communication", "Ethernet Communication", "mdi:ethernet", "Stan komunikacji Ethernet", BinarySensorDeviceClass.CONNECTIVITY),
        ("wifi_communication", "WiFi Communication", "mdi:wifi", "Stan komunikacji WiFi", BinarySensorDeviceClass.CONNECTIVITY),
        ("cloud_communication", "Cloud Communication", "mdi:cloud", "Stan komunikacji z chmurą", BinarySensorDeviceClass.CONNECTIVITY),
        ("mobile_app", "Mobile App", "mdi:cellphone", "Stan aplikacji mobilnej", BinarySensorDeviceClass.CONNECTIVITY),
        ("web_interface", "Web Interface", "mdi:web", "Stan interfejsu webowego", BinarySensorDeviceClass.CONNECTIVITY),
        ("remote_access", "Remote Access", "mdi:remote-desktop", "Stan dostępu zdalnego", BinarySensorDeviceClass.CONNECTIVITY),
        
        # Power and backup systems
        ("backup_power", "Backup Power", "mdi:battery-backup", "Stan zasilania awaryjnego", BinarySensorDeviceClass.POWER),
        ("battery_status", "Battery Status", "mdi:battery", "Stan baterii", BinarySensorDeviceClass.BATTERY),
        ("power_quality", "Power Quality", "mdi:flash-alert", "Stan jakości zasilania", BinarySensorDeviceClass.POWER),
    ]
    
    for sensor_key, name, icon, description, device_class in input_status_sensors:
        if sensor_key in discrete_regs:
            entities.append(
                ThesslaGreenBinarySensor(
                    coordinator, sensor_key, name, icon, description, device_class, "discrete"
                )
            )
    
    # Status Flags from Input/Holding Registers - wszystkie z PDF + autoscan
    status_flag_sensors = [
        # System operational states
        ("constant_flow_active", "Constant Flow Active", "mdi:fan-auto", "Status trybu stałego przepływu", None),
        ("gwc_bypass_active", "GWC Bypass Active", "mdi:heat-pump", "Status GWC bypass", None),
        ("summer_mode_active", "Summer Mode Active", "mdi:weather-sunny", "Status trybu letniego", None),
        ("winter_mode_active", "Winter Mode Active", "mdi:weather-snowy", "Status trybu zimowego", None),
        ("heating_season", "Heating Season", "mdi:radiator", "Sezon grzewczy aktywny", BinarySensorDeviceClass.HEAT),
        ("cooling_season", "Cooling Season", "mdi:snowflake", "Sezon chłodzący aktywny", BinarySensorDeviceClass.COLD),
        ("frost_protection_active", "Frost Protection Active", "mdi:snowflake-alert", "Ochrona przeciwmrozowa aktywna", None),
        ("overheating_protection", "Overheating Protection", "mdi:thermometer-alert", "Ochrona przed przegrzaniem", None),
        
        # System configuration flags
        ("auto_start", "Auto Start", "mdi:power", "Autostart po awarii zasilania", None),
        ("summer_winter_auto", "Summer/Winter Auto", "mdi:autorenew", "Automatyczne przełączanie lato/zima", None),
        ("daylight_saving", "Daylight Saving", "mdi:clock-fast", "Automatyczne przejście na czas letni", None),
        ("sound_enabled", "Sound Enabled", "mdi:volume-high", "Sygnały dźwiękowe włączone", BinarySensorDeviceClass.SOUND),
        ("led_enabled", "LED Enabled", "mdi:led-on", "Sygnalizacja LED włączona", None),
        ("keypad_lock", "Keypad Lock", "mdi:lock", "Blokada klawiatury", None),
        
        # Advanced control flags
        ("adaptive_control", "Adaptive Control", "mdi:brain", "Sterowanie adaptacyjne włączone", None),
        ("learning_mode", "Learning Mode", "mdi:school", "Tryb uczenia się", None),
        ("smart_recovery", "Smart Recovery", "mdi:recycle", "Inteligentny odzysk ciepła", None),
        ("demand_control", "Demand Control", "mdi:chart-line", "Sterowanie na żądanie", None),
        ("occupancy_detection", "Occupancy Detection", "mdi:account-search", "Wykrywanie obecności", BinarySensorDeviceClass.OCCUPANCY),
        
        # Network configuration
        ("ethernet_dhcp", "Ethernet DHCP", "mdi:router", "DHCP Ethernet", BinarySensorDeviceClass.CONNECTIVITY),
    ]
    
    for sensor_key, name, icon, description, device_class in status_flag_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenStatusFlagSensor(
                    coordinator, sensor_key, name, icon, description, device_class
                )
            )
    
    # Error and Alarm Binary Sensors - wszystkie z PDF + autoscan
    error_alarm_sensors = [
        ("alarm_status", "General Alarm", "mdi:alarm-light", "Wystąpienie ostrzeżenia (alarm E)", None),
        ("error_status", "General Error", "mdi:alert-circle", "Wystąpienie błędu (alarm S)", None),
        ("error_s2", "I2C Communication Error", "mdi:wifi-alert", "S2 - Błąd komunikacji I2C", BinarySensorDeviceClass.PROBLEM),
        ("error_s6", "FPX Thermal Protection", "mdi:thermometer-alert", "S6 - Zabezpieczenie termiczne FPX", BinarySensorDeviceClass.HEAT),
        ("error_s7", "Calibration Error", "mdi:thermometer-minus", "S7 - Brak możliwości kalibracji", BinarySensorDeviceClass.PROBLEM),
        ("error_s8", "Product Key Required", "mdi:key-alert", "S8 - Konieczność klucza produktu", BinarySensorDeviceClass.PROBLEM),
        ("error_s9", "Stopped from AirS Panel", "mdi:stop-circle", "S9 - Zatrzymanie z panelu AirS", None),
        ("error_s10", "Fire Sensor Triggered", "mdi:fire-alert", "S10 - Zadziałał czujnik PPOŻ", BinarySensorDeviceClass.SAFETY),
        ("error_s13", "Stopped from Air+ Panel", "mdi:stop-circle", "S13 - Zatrzymanie z panelu Air+", None),
        ("error_s14", "Antifreeze Protection", "mdi:snowflake-alert", "S14 - Zabezpieczenie przeciwzamrożeniowe", None),
        ("error_s15", "Antifreeze No Effect", "mdi:snowflake-alert", "S15 - Zabezpieczenie nie przyniosło rezultatu", None),
        ("error_s16", "Thermal Protection Central", "mdi:thermometer-alert", "S16 - Zabezpieczenie termiczne w centrali", BinarySensorDeviceClass.HEAT),
        ("error_s17", "Filters Not Changed", "mdi:air-filter", "S17 - Nie wymienione filtry", None),
        ("error_s19", "Auto Filter Procedure", "mdi:air-filter", "S19 - Nie wymienione filtry - procedura automat.", None),
        ("error_s29", "High Temperature Before Recuperator", "mdi:thermometer-alert", "S29 - Zbyt wysoka temperatura przed rekuperatorem", BinarySensorDeviceClass.HEAT),
        ("error_s30", "Supply Fan Failure", "mdi:fan-alert", "S30 - Nie działa wentylator nawiewny", BinarySensorDeviceClass.PROBLEM),
        ("error_s31", "Exhaust Fan Failure", "mdi:fan-alert", "S31 - Nie działa wentylator wywiewny", BinarySensorDeviceClass.PROBLEM),
        ("error_s32", "TG-02 Communication Error", "mdi:wifi-alert", "S32 - Brak komunikacji z modułem TG-02", BinarySensorDeviceClass.CONNECTIVITY),
        ("error_e99", "Product Key Required Central", "mdi:key", "E99 - Konieczność klucza produktu centrali", BinarySensorDeviceClass.PROBLEM),
        ("error_e100", "Outside Temperature Sensor", "mdi:thermometer-off", "E100 - Brak odczytu czujnika TZ1", BinarySensorDeviceClass.PROBLEM),
        ("error_e101", "Supply Temperature Sensor", "mdi:thermometer-off", "E101 - Brak odczytu czujnika TN1", BinarySensorDeviceClass.PROBLEM),
        ("error_e102", "Exhaust Temperature Sensor", "mdi:thermometer-off", "E102 - Brak odczytu czujnika TP", BinarySensorDeviceClass.PROBLEM),
        ("error_e103", "FPX Temperature Sensor", "mdi:thermometer-off", "E103 - Brak odczytu czujnika TZ2", BinarySensorDeviceClass.PROBLEM),
        ("error_e104", "Ambient Temperature Sensor", "mdi:thermometer-off", "E104 - Brak odczytu czujnika TO", BinarySensorDeviceClass.PROBLEM),
        ("error_e105", "Duct Temperature Sensor", "mdi:thermometer-off", "E105 - Brak odczytu czujnika TN2", BinarySensorDeviceClass.PROBLEM),
    ]
    
    for sensor_key, name, icon, description, device_class in error_alarm_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenErrorAlarmBinarySensor(
                    coordinator, sensor_key, name, icon, description, device_class
                )
            )
    
    # Device Lock and Security Sensors - z PDF + autoscan
    security_sensors = [
        ("device_lock", "Device Lock", "mdi:lock", "Aktywacja blokady urządzenia", None),
        ("user_key_low", "User Key Status", "mdi:key-variant", "Status klucza użytkownika", None),
    ]
    
    for sensor_key, name, icon, description, device_class in security_sensors:
        if sensor_key in holding_regs:
            entities.append(
                ThesslaGreenSecuritySensor(
                    coordinator, sensor_key, name, icon, description, device_class
                )
            )
    
    if entities:
        _LOGGER.info("Adding %d binary sensor entities (autoscan detected)", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No binary sensor entities created - check device connectivity and register availability")


class ThesslaGreenBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base binary sensor for ThesslaGreen devices with enhanced functionality."""
    
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        device_class: BinarySensorDeviceClass | None,
        register_type: str = "unknown",
    ) -> None:
        """Initialize the binary sensor."""
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
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        
        # Check if register is marked as unavailable
        perf_stats = self.coordinator.performance_stats
        if self._key in perf_stats.get("unavailable_registers", set()):
            return False
            
        return self._key in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
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


class ThesslaGreenBinarySensor(ThesslaGreenBaseBinarySensor):
    """Standard binary sensor for coil and discrete input registers."""
    
    pass


class ThesslaGreenStatusFlagSensor(ThesslaGreenBaseBinarySensor):
    """Binary sensor for status flags from input/holding registers."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def is_on(self) -> bool | None:
        """Return true if the status flag is active."""
        if not self.available:
            return None
        
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        
        # Handle specific status flag logic
        if "active" in self._key:
            # For *_active registers, non-zero means active
            return bool(value) if isinstance(value, (int, bool)) else None
        
        # For mode flags, check for specific active values
        if "mode" in self._key:
            return value not in [0, "Off", "off", False]
        
        # Default boolean handling
        return super().is_on


class ThesslaGreenErrorAlarmBinarySensor(ThesslaGreenBaseBinarySensor):
    """Binary sensor for error and alarm conditions."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def is_on(self) -> bool | None:
        """Return true if error/alarm is active."""
        if not self.available:
            return None
        
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        
        # Error/alarm active states
        if isinstance(value, (int, bool)):
            return bool(value)
        elif isinstance(value, str):
            return value.lower() in ("active", "error", "alarm", "1", "true", "on")
        
        return bool(value)

    @property
    def icon(self) -> str:
        """Return dynamic icon based on error state."""
        if self.is_on:
            if "fire" in self._key:
                return "mdi:fire-alert"
            elif "temperature" in self._key or "thermal" in self._key:
                return "mdi:thermometer-alert"
            elif "fan" in self._key:
                return "mdi:fan-alert"
            elif "communication" in self._key or "modbus" in self._key:
                return "mdi:wifi-alert"
            elif "sensor" in self._key:
                return "mdi:thermometer-off"
            else:
                return "mdi:alert-circle"
        else:
            return "mdi:check-circle"


class ThesslaGreenSecuritySensor(ThesslaGreenBaseBinarySensor):
    """Binary sensor for security and access control."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def is_on(self) -> bool | None:
        """Return true if security feature is active."""
        if not self.available:
            return None
        
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        
        # Handle device lock status
        if self._key == "device_lock":
            return bool(value)
        
        # Handle user key status - non-zero means key is set
        if "key" in self._key:
            return value != 0 if isinstance(value, int) else bool(value)
        
        return bool(value)

    @property
    def icon(self) -> str:
        """Return dynamic icon based on security state."""
        if self.is_on:
            if "lock" in self._key:
                return "mdi:lock"
            elif "key" in self._key:
                return "mdi:key"
            else:
                return "mdi:shield-check"
        else:
            if "lock" in self._key:
                return "mdi:lock-open"
            elif "key" in self._key:
                return "mdi:key-off"
            else:
                return "mdi:shield-off"