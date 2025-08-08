"""Enhanced sensor platform for ThesslaGreen Modbus integration.
Wszystkie sensory z kompletnej mapy rejestrów + autoscan.
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
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
    """Set up enhanced sensor platform with comprehensive register support."""
    coordinator: ThesslaGreenCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    input_regs = coordinator.available_registers.get("input_registers", set())
    holding_regs = coordinator.available_registers.get("holding_registers", set())
    
    # Temperature Sensors - wszystkie z PDF + autoscan
    temperature_sensors = [
        ("outside_temperature", "Outside Temperature", "mdi:thermometer", "TZ1 - Temperatura powietrza zewnętrznego"),
        ("supply_temperature", "Supply Temperature", "mdi:thermometer-lines", "TN1 - Temperatura powietrza nawiewanego"), 
        ("exhaust_temperature", "Exhaust Temperature", "mdi:thermometer-minus", "TP - Temperatura powietrza usuwanego"),
        ("fpx_temperature", "FPX Temperature", "mdi:thermometer-plus", "TZ2 - Temperatura za nagrzewnicą FPX"),
        ("duct_supply_temperature", "Duct Supply Temperature", "mdi:thermometer-chevron-up", "TN2 - Temperatura za nagrzewnicą kanałową"),
        ("gwc_temperature", "GWC Temperature", "mdi:thermometer-water", "TZ3 - Temperatura przed wymiennikiem GWC"),
        ("ambient_temperature", "Ambient Temperature", "mdi:thermometer-bluetooth", "TO - Temperatura otoczenia centrali"),
        ("heating_temperature", "Heating Temperature", "mdi:radiator", "Temperatura grzania"),
        ("cooling_temperature", "Cooling Temperature", "mdi:snowflake", "Temperatura chłodzenia"),
        ("comfort_temperature", "Comfort Temperature", "mdi:home-thermometer", "Temperatura komfortu"),
        ("economy_temperature", "Economy Temperature", "mdi:leaf", "Temperatura ekonomiczna"),
        ("frost_protection_temp", "Frost Protection Temperature", "mdi:snowflake-alert", "Temperatura ochrony przeciwmrozowej"),
        ("overheat_protection_temp", "Overheat Protection Temperature", "mdi:thermometer-alert", "Temperatura ochrony przed przegrzaniem"),
        ("gwc_activation_temp", "GWC Activation Temperature", "mdi:thermometer-chevron-down", "Temperatura aktywacji GWC"),
        ("bypass_activation_temp", "Bypass Activation Temperature", "mdi:thermometer-chevron-up", "Temperatura aktywacji bypass"),
        ("required_temp", "Required Temperature", "mdi:thermometer-check", "Temperatura zadana trybu KOMFORT"),
    ]
    
    for sensor_key, name, icon, description in temperature_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenTemperatureSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Flow Rate Sensors - wszystkie z PDF + autoscan
    flow_sensors = [
        ("supply_flowrate", "Supply Flow Rate", "mdi:fan-plus", "Wydatek nawiewu"),
        ("exhaust_flowrate", "Exhaust Flow Rate", "mdi:fan-minus", "Wydatek wywiewu"),
        ("actual_flowrate", "Actual Flow Rate", "mdi:fan", "Wydatek rzeczywisty w trybie auto"),
        ("supply_flow_min", "Supply Flow Min", "mdi:fan-chevron-down", "Minimalny przepływ nawiewu"),
        ("supply_flow_max", "Supply Flow Max", "mdi:fan-chevron-up", "Maksymalny przepływ nawiewu"),
        ("exhaust_flow_min", "Exhaust Flow Min", "mdi:fan-chevron-down", "Minimalny przepływ wywiewu"),
        ("exhaust_flow_max", "Exhaust Flow Max", "mdi:fan-chevron-up", "Maksymalny przepływ wywiewu"),
        ("total_air_volume", "Total Air Volume", "mdi:chart-box", "Całkowity przetok powietrza"),
    ]
    
    for sensor_key, name, icon, description in flow_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenFlowSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Percentage Sensors - wszystkie z PDF + autoscan
    percentage_sensors = [
        ("supply_percentage", "Supply Fan Speed", "mdi:fan", "Moc wentylatora nawiewnego"),
        ("exhaust_percentage", "Exhaust Fan Speed", "mdi:fan", "Moc wentylatora wywiewnego"),
        ("heat_recovery_efficiency", "Heat Recovery Efficiency", "mdi:percent", "Sprawność rekuperacji"),
        ("air_damper_opening", "Air Damper Opening", "mdi:valve", "Położenie przepustnicy powietrza"),
        ("bypassing_factor", "Bypassing Factor", "mdi:swap-horizontal", "Współczynnik bypassowania"),
        ("air_flow_rate_manual", "Manual Flow Rate", "mdi:hand-extended", "Intensywność wentylacji tryb manual"),
        ("air_flow_rate_auto", "Auto Flow Rate", "mdi:autorenew", "Intensywność wentylacji tryb auto"),
        ("air_flow_rate_temporary", "Temporary Flow Rate", "mdi:clock-fast", "Intensywność wentylacji tryb temporary"),
        ("flow_balance", "Flow Balance", "mdi:scale-balance", "Balans przepływów"),
        ("supply_fan_speed", "Supply Fan Speed Control", "mdi:fan-speed-1", "Prędkość wentylatora nawiewnego"),
        ("exhaust_fan_speed", "Exhaust Fan Speed Control", "mdi:fan-speed-2", "Prędkość wentylatora wywiewnego"),
        ("efficiency_rating", "Efficiency Rating", "mdi:star", "Ocena wydajności"),
        ("okap_intensity", "Hood Intensity", "mdi:cooktop", "Intensywność trybu OKAP"),
        ("kominek_intensity", "Fireplace Intensity", "mdi:fireplace", "Intensywność trybu KOMINEK"),
        ("wietrzenie_intensity", "Ventilation Intensity", "mdi:weather-windy", "Intensywność trybu WIETRZENIE"),
        ("pusty_dom_intensity", "Empty House Intensity", "mdi:home-outline", "Intensywność trybu PUSTY DOM"),
        ("boost_intensity", "Boost Intensity", "mdi:rocket-launch", "Intensywność trybu BOOST"),
        ("night_mode_intensity", "Night Mode Intensity", "mdi:weather-night", "Intensywność trybu nocnego"),
        ("party_mode_intensity", "Party Mode Intensity", "mdi:party-popper", "Intensywność trybu party"),
        ("vacation_mode_intensity", "Vacation Mode Intensity", "mdi:airplane", "Intensywność trybu wakacyjnego"),
        ("outside_humidity", "Outside Humidity", "mdi:water-percent", "Wilgotność zewnętrzna"),
        ("inside_humidity", "Inside Humidity", "mdi:water-percent", "Wilgotność wewnętrzna"),
    ]
    
    for sensor_key, name, icon, description in percentage_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenPercentageSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Pressure Sensors - wszystkie z PDF + autoscan
    pressure_sensors = [
        ("supply_pressure", "Supply Pressure", "mdi:gauge", "Ciśnienie nawiewu"),
        ("exhaust_pressure", "Exhaust Pressure", "mdi:gauge", "Ciśnienie wywiewu"),
        ("supply_pressure_pa", "Supply Pressure Pa", "mdi:gauge-full", "Ciśnienie nawiewu Pa"),
        ("exhaust_pressure_pa", "Exhaust Pressure Pa", "mdi:gauge-full", "Ciśnienie wywiewu Pa"),
        ("constant_pressure_setpoint", "Constant Pressure Setpoint", "mdi:gauge-empty", "Zadana wartość ciśnienia stałego"),
        ("variable_pressure_setpoint", "Variable Pressure Setpoint", "mdi:gauge-low", "Zadana wartość ciśnienia zmiennego"),
        ("filter_pressure_alarm", "Filter Pressure Alarm", "mdi:gauge-alert", "Alarm ciśnienia filtrów"),
        ("presostat_differential", "Presostat Differential", "mdi:gauge", "Różnica ciśnień presostatu"),
    ]
    
    for sensor_key, name, icon, description in pressure_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenPressureSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Time and Duration Sensors - wszystkie z PDF + autoscan
    time_sensors = [
        ("filter_time_remaining", "Filter Time Remaining", "mdi:air-filter", "Pozostały czas do wymiany filtrów", UnitOfTime.DAYS),
        ("operating_hours", "Operating Hours", "mdi:clock-outline", "Godziny pracy", UnitOfTime.HOURS),
        ("filter_operating_hours", "Filter Operating Hours", "mdi:air-filter", "Godziny pracy filtrów", UnitOfTime.HOURS),
        ("maintenance_interval", "Maintenance Interval", "mdi:wrench-clock", "Interwał serwisowy", UnitOfTime.DAYS),
        ("next_maintenance", "Next Maintenance", "mdi:calendar-clock", "Kolejny serwis", UnitOfTime.DAYS),
        ("filter_change_interval", "Filter Change Interval", "mdi:air-filter", "Interwał wymiany filtrów", UnitOfTime.DAYS),
        ("filter_warning_days", "Filter Warning Days", "mdi:calendar-alert", "Ostrzeżenie przed wymianą", UnitOfTime.DAYS),
        ("service_interval", "Service Interval", "mdi:tools", "Interwał serwisu", UnitOfTime.DAYS),
        ("okap_duration", "Hood Duration", "mdi:timer", "Czas trwania trybu OKAP", UnitOfTime.MINUTES),
        ("kominek_duration", "Fireplace Duration", "mdi:timer", "Czas trwania trybu KOMINEK", UnitOfTime.MINUTES),
        ("wietrzenie_duration", "Ventilation Duration", "mdi:timer", "Czas trwania trybu WIETRZENIE", UnitOfTime.MINUTES),
        ("pusty_dom_duration", "Empty House Duration", "mdi:timer", "Czas trwania trybu PUSTY DOM", UnitOfTime.MINUTES),
        ("boost_duration", "Boost Duration", "mdi:timer", "Czas trwania trybu BOOST", UnitOfTime.MINUTES),
        ("fan_ramp_time", "Fan Ramp Time", "mdi:speedometer", "Czas rozbiegu wentylatora", UnitOfTime.SECONDS),
    ]
    
    for sensor_key, name, icon, description, unit in time_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenTimeSensor(
                    coordinator, sensor_key, name, icon, description, unit
                )
            )
    
    # Energy and Power Sensors - wszystkie z PDF + autoscan
    energy_power_sensors = [
        ("energy_consumption", "Energy Consumption", "mdi:lightning-bolt-circle", "Zużycie energii", UnitOfEnergy.KILO_WATT_HOUR),
        ("energy_recovery", "Energy Recovery", "mdi:recycle", "Odzysk energii", UnitOfEnergy.KILO_WATT_HOUR),
        ("peak_power", "Peak Power", "mdi:lightning-bolt", "Moc szczytowa", UnitOfPower.WATT),
        ("average_power", "Average Power", "mdi:flash", "Moc średnia", UnitOfPower.WATT),
        ("power_limit", "Power Limit", "mdi:speedometer-medium", "Limit mocy", UnitOfPower.WATT),
    ]
    
    for sensor_key, name, icon, description, unit in energy_power_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenEnergyPowerSensor(
                    coordinator, sensor_key, name, icon, description, unit
                )
            )
    
    # Air Quality Sensors - wszystkie z PDF + autoscan
    air_quality_sensors = [
        ("co2_concentration", "CO2 Concentration", "mdi:molecule-co2", "Stężenie CO2", "ppm"),
        ("voc_level", "VOC Level", "mdi:air-purifier", "Poziom VOC", None),
        ("air_quality_index", "Air Quality Index", "mdi:air-filter", "Indeks jakości powietrza", None),
        ("co2_alarm_limit", "CO2 Alarm Limit", "mdi:molecule-co2", "Limit alarmu CO2", "ppm"),
        ("humidity_alarm_limit", "Humidity Alarm Limit", "mdi:water-alert", "Limit alarmu wilgotności", PERCENTAGE),
    ]
    
    for sensor_key, name, icon, description, unit in air_quality_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenAirQualitySensor(
                    coordinator, sensor_key, name, icon, description, unit
                )
            )
    
    # System Status Sensors - wszystkie z PDF + autoscan
    system_sensors = [
        ("presostat_status", "Presostat Status", "mdi:air-filter", "Status presostatu"),
        ("system_status", "System Status", "mdi:information", "Status systemu"),
        ("communication_status", "Communication Status", "mdi:wifi", "Status komunikacji"),
        ("sensor_status", "Sensor Status", "mdi:thermometer", "Status czujników"),
        ("actuator_status", "Actuator Status", "mdi:electric-switch", "Status siłowników"),
        ("mode", "Operation Mode", "mdi:cog", "Tryb pracy"),
        ("season_mode", "Season Mode", "mdi:weather-partly-cloudy", "Tryb sezonowy"),
        ("special_mode", "Special Mode", "mdi:star-settings", "Tryb specjalny"),
        ("bypass_mode", "Bypass Mode", "mdi:swap-horizontal", "Tryb bypass"),
        ("gwc_mode", "GWC Mode", "mdi:heat-pump", "Tryb GWC"),
        ("constant_flow_mode", "Constant Flow Mode", "mdi:fan-auto", "Tryb stałego przepływu"),
        ("pressure_control_mode", "Pressure Control Mode", "mdi:gauge", "Tryb kontroli ciśnienia"),
        ("filter_type", "Filter Type", "mdi:air-filter", "Typ filtrów"),
        ("current_program", "Current Program", "mdi:play", "Aktualny program pracy"),
    ]
    
    for sensor_key, name, icon, description in system_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenSystemSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Device Information Sensors - wszystkie z PDF + autoscan
    device_info_sensors = [
        ("firmware_major", "Firmware Major", "mdi:chip", "Wersja firmware - główna"),
        ("firmware_minor", "Firmware Minor", "mdi:chip", "Wersja firmware - podrzędna"),
        ("firmware_patch", "Firmware Patch", "mdi:chip", "Wersja firmware - poprawka"),
        ("serial_number_1", "Serial Number 1", "mdi:barcode", "Numer seryjny - część 1"),
        ("serial_number_2", "Serial Number 2", "mdi:barcode", "Numer seryjny - część 2"),
        ("serial_number_3", "Serial Number 3", "mdi:barcode", "Numer seryjny - część 3"),
        ("compilation_days", "Compilation Days", "mdi:calendar", "Data kompilacji - dni"),
        ("compilation_seconds", "Compilation Seconds", "mdi:clock", "Data kompilacji - sekundy"),
        ("device_name_1", "Device Name 1", "mdi:tag", "Nazwa urządzenia - część 1"),
        ("device_name_2", "Device Name 2", "mdi:tag", "Nazwa urządzenia - część 2"),
    ]
    
    for sensor_key, name, icon, description in device_info_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenDeviceInfoSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Schedule Sensors - przykłady harmonogramu + autoscan
    schedule_sensors = [
        ("schedule_mon_period1_start", "Monday Period 1 Start", "mdi:clock-start", "Poniedziałek okres 1 start"),
        ("schedule_mon_period1_end", "Monday Period 1 End", "mdi:clock-end", "Poniedziałek okres 1 koniec"),
        ("schedule_mon_period1_intensity", "Monday Period 1 Intensity", "mdi:fan", "Poniedziałek okres 1 intensywność"),
        ("schedule_tue_period1_start", "Tuesday Period 1 Start", "mdi:clock-start", "Wtorek okres 1 start"),
        ("schedule_wed_period1_start", "Wednesday Period 1 Start", "mdi:clock-start", "Środa okres 1 start"),
        ("schedule_thu_period1_start", "Thursday Period 1 Start", "mdi:clock-start", "Czwartek okres 1 start"),
        ("schedule_fri_period1_start", "Friday Period 1 Start", "mdi:clock-start", "Piątek okres 1 start"),
        ("schedule_sat_period1_start", "Saturday Period 1 Start", "mdi:clock-start", "Sobota okres 1 start"),
        ("schedule_sun_period1_start", "Sunday Period 1 Start", "mdi:clock-start", "Niedziela okres 1 start"),
    ]
    
    for sensor_key, name, icon, description in schedule_sensors:
        if sensor_key in holding_regs:
            entities.append(
                ThesslaGreenScheduleSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Error and Alarm Sensors - wszystkie z PDF + autoscan
    error_alarm_sensors = [
        ("error_code", "Error Code", "mdi:alert-circle", "Kod błędu aktualny"),
        ("warning_code", "Warning Code", "mdi:alert", "Kod ostrzeżenia aktualny"),
        ("alarm_status", "Alarm Status", "mdi:alarm-light", "Status alarmów"),
        ("error_status", "Error Status", "mdi:alert-circle", "Status błędów"),
        ("error_s2", "Error S2", "mdi:wifi-alert", "S2 - Błąd komunikacji I2C"),
        ("error_s6", "Error S6", "mdi:thermometer-alert", "S6 - Zabezpieczenie termiczne FPX"),
        ("error_s7", "Error S7", "mdi:thermometer-minus", "S7 - Brak możliwości kalibracji"),
        ("error_s8", "Error S8", "mdi:key-alert", "S8 - Konieczność klucza produktu"),
        ("error_s9", "Error S9", "mdi:stop-circle", "S9 - Zatrzymanie z panelu AirS"),
        ("error_s10", "Error S10", "mdi:fire-alert", "S10 - Zadziałał czujnik PPOŻ"),
        ("error_e99", "Error E99", "mdi:key", "E99 - Klucz produktu centrali"),
        ("error_e100", "Error E100", "mdi:thermometer-off", "E100 - Brak odczytu TZ1"),
        ("error_e101", "Error E101", "mdi:thermometer-off", "E101 - Brak odczytu TN1"),
        ("error_e102", "Error E102", "mdi:thermometer-off", "E102 - Brak odczytu TP"),
        ("error_e103", "Error E103", "mdi:thermometer-off", "E103 - Brak odczytu TZ2"),
        ("error_e104", "Error E104", "mdi:thermometer-off", "E104 - Brak odczytu TO"),
        ("error_e105", "Error E105", "mdi:thermometer-off", "E105 - Brak odczytu TN2"),
    ]
    
    for sensor_key, name, icon, description in error_alarm_sensors:
        if sensor_key in input_regs or sensor_key in holding_regs:
            entities.append(
                ThesslaGreenErrorAlarmSensor(
                    coordinator, sensor_key, name, icon, description
                )
            )
    
    # Diagnostic Sensors - dla debugowania i monitorowania
    if coordinator.data and "_system_info" in coordinator.data:
        entities.extend([
            ThesslaGreenDiagnosticSensor(
                coordinator, "update_duration", "Update Duration", "mdi:timer", 
                "Czas aktualizacji danych", UnitOfTime.SECONDS
            ),
            ThesslaGreenDiagnosticSensor(
                coordinator, "data_quality", "Data Quality", "mdi:check-circle", 
                "Jakość danych", PERCENTAGE
            ),
            ThesslaGreenDiagnosticSensor(
                coordinator, "register_count", "Register Count", "mdi:counter", 
                "Liczba odczytanych rejestrów", None
            ),
        ])
    
    if entities:
        _LOGGER.info("Adding %d sensor entities (autoscan detected)", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning("No sensor entities created - check device connectivity and register availability")


class ThesslaGreenBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for ThesslaGreen devices with enhanced functionality."""
    
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_translation_key = key
        self._attr_unique_id = f"thessla_{coordinator.host.replace('.', '_')}_{coordinator.slave_id}_{key}"
        self._attr_entity_registry_enabled_default = True
        
        # Enhanced device info
        self._attr_device_info = coordinator.device_info
        self._attr_extra_state_attributes = {
            "description": description,
            "register_key": key,
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
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        if not self.available:
            return None
        return self.coordinator.data.get(self._key)

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
        
        return attrs


class ThesslaGreenTemperatureSensor(ThesslaGreenBaseSensor):
    """Temperature sensor with enhanced features."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1


class ThesslaGreenFlowSensor(ThesslaGreenBaseSensor):
    """Flow rate sensor with enhanced features."""
    
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:fan"


class ThesslaGreenPercentageSensor(ThesslaGreenBaseSensor):
    """Percentage sensor with enhanced features."""
    
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 0


class ThesslaGreenPressureSensor(ThesslaGreenBaseSensor):
    """Pressure sensor with enhanced features."""
    
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPressure.PA
    _attr_suggested_display_precision = 0


class ThesslaGreenTimeSensor(ThesslaGreenBaseSensor):
    """Time/duration sensor with enhanced features."""
    
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str,
    ) -> None:
        """Initialize time sensor with unit."""
        super().__init__(coordinator, key, name, icon, description)
        self._attr_native_unit_of_measurement = unit


class ThesslaGreenEnergyPowerSensor(ThesslaGreenBaseSensor):
    """Energy/power sensor with enhanced features."""
    
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    
    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str,
    ) -> None:
        """Initialize energy/power sensor with unit and device class."""
        super().__init__(coordinator, key, name, icon, description)
        self._attr_native_unit_of_measurement = unit
        
        if "power" in key.lower():
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif "energy" in key.lower():
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING


class ThesslaGreenAirQualitySensor(ThesslaGreenBaseSensor):
    """Air quality sensor with enhanced features."""
    
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str | None,
    ) -> None:
        """Initialize air quality sensor with unit."""
        super().__init__(coordinator, key, name, icon, description)
        self._attr_native_unit_of_measurement = unit
        
        if "co2" in key.lower():
            self._attr_device_class = SensorDeviceClass.CO2
        elif "humidity" in key.lower():
            self._attr_device_class = SensorDeviceClass.HUMIDITY


class ThesslaGreenSystemSensor(ThesslaGreenBaseSensor):
    """System status sensor with enhanced features."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def native_value(self) -> Any:
        """Return formatted system status value."""
        raw_value = super().native_value
        if raw_value is None:
            return None
        
        # Format specific system values
        if self._key == "mode":
            mode_names = {0: "Off", 1: "Manual", 2: "Auto", 3: "Temporary"}
            return mode_names.get(raw_value, f"Unknown ({raw_value})")
        
        elif self._key == "season_mode":
            season_names = {0: "Auto", 1: "Winter", 2: "Summer"}
            return season_names.get(raw_value, f"Unknown ({raw_value})")
        
        elif self._key == "special_mode":
            special_names = {0: "Off", 1: "OKAP", 2: "KOMINEK", 3: "WIETRZENIE", 4: "PUSTY_DOM"}
            return special_names.get(raw_value, f"Unknown ({raw_value})")
        
        elif self._key == "filter_type" and isinstance(raw_value, dict):
            return raw_value.get("description", raw_value.get("value", raw_value))
        
        return raw_value


class ThesslaGreenDeviceInfoSensor(ThesslaGreenBaseSensor):
    """Device information sensor with enhanced features."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def native_value(self) -> Any:
        """Return formatted device info value."""
        raw_value = super().native_value
        if raw_value is None:
            return None
        
        # Format firmware version components
        if "firmware" in self._key:
            return f"v{raw_value}"
        
        return raw_value


class ThesslaGreenScheduleSensor(ThesslaGreenBaseSensor):
    """Schedule sensor with enhanced features."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def native_value(self) -> Any:
        """Return formatted schedule value."""
        raw_value = super().native_value
        if raw_value is None:
            return None
        
        # Format time values (HHMM format)
        if "start" in self._key or "end" in self._key:
            if isinstance(raw_value, str):
                return raw_value  # Already formatted as HH:MM
            elif isinstance(raw_value, int):
                hours = (raw_value >> 8) & 0xFF
                minutes = raw_value & 0xFF
                return f"{hours:02d}:{minutes:02d}"
        
        return raw_value


class ThesslaGreenErrorAlarmSensor(ThesslaGreenBaseSensor):
    """Error/alarm sensor with enhanced features."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-circle"
    
    @property
    def native_value(self) -> Any:
        """Return formatted error/alarm value."""
        raw_value = super().native_value
        if raw_value is None:
            return None
        
        # Format error status
        if "status" in self._key:
            return "Active" if raw_value else "OK"
        
        # Format specific error codes
        if raw_value == 0:
            return "OK"
        elif raw_value == 1:
            return "Active"
        
        return raw_value

    @property
    def icon(self) -> str:
        """Return dynamic icon based on error state."""
        if self.native_value in ["OK", 0]:
            return "mdi:check-circle"
        elif self.native_value in ["Active", 1]:
            return "mdi:alert-circle"
        return "mdi:help-circle"


class ThesslaGreenDiagnosticSensor(ThesslaGreenBaseSensor):
    """Diagnostic sensor for system monitoring."""
    
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(
        self,
        coordinator: ThesslaGreenCoordinator,
        key: str,
        name: str,
        icon: str,
        description: str,
        unit: str | None,
    ) -> None:
        """Initialize diagnostic sensor."""
        super().__init__(coordinator, key, name, icon, description)
        self._attr_native_unit_of_measurement = unit
    
    @property
    def native_value(self) -> Any:
        """Return diagnostic value from system info."""
        if not self.coordinator.data or "_system_info" not in self.coordinator.data:
            return None
        
        system_info = self.coordinator.data["_system_info"]
        
        if self._key == "update_duration":
            return round(system_info.get("update_duration", 0), 3)
        elif self._key == "data_quality":
            return round(system_info.get("data_quality", 0) * 100, 1)
        elif self._key == "register_count":
            return system_info.get("register_count", 0)
        
        return None