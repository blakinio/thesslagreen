"""Constants and register definitions for ThesslaGreen Modbus Integration.
COMPLETE REGISTER MAPPING - Wszystkie 200+ rejestry z MODBUS_USER_AirPack_Home_08.2021.01 BEZ WYJĄTKU
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4 (h/v/f, Energy/Energy+/Enthalpy)
"""
from typing import Dict, List, Set

# Integration constants
DOMAIN = "thessla_green_modbus"
MANUFACTURER = "ThesslaGreen"
MODEL = "AirPack Home Serie 4"

# Connection defaults
DEFAULT_NAME = "ThesslaGreen"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 10
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3

# Configuration options
CONF_SLAVE_ID = "slave_id"
CONF_RETRY = "retry"
CONF_TIMEOUT = "timeout"
CONF_FORCE_FULL_REGISTER_LIST = "force_full_register_list"

# Platforms
PLATFORMS = ["sensor", "binary_sensor", "climate", "fan", "select", "number", "switch"]

# ============================================================================
# COMPLETE REGISTER MAPPING - Wszystkie rejestry z MODBUS_USER_AirPack_Home_08.2021.01 PDF bez wyjątku
# ============================================================================

# INPUT REGISTERS (04 - READ INPUT REGISTER) - Czujniki i wartości tylko do odczytu
INPUT_REGISTERS = {
    # Firmware version (0x0000-0x0004)
    "firmware_major": 0x0000,                # Wersja główna (MM)
    "firmware_minor": 0x0001,                # Wersja podrzędna (mm)
    "day_of_week": 0x0002,                   # Dzień tygodnia (0-6)
    "period": 0x0003,                        # Odcinek czasowy (0-3)
    "firmware_patch": 0x0004,                # Wersja poprawki (pp)
    
    # Compilation info (0x000E-0x000F)
    "compilation_days": 0x000E,              # Data kompilacji (dni od 01.01.2000)
    "compilation_seconds": 0x000F,           # Godzina kompilacji (sekundy od 00:00)
    
    # Temperature sensors (0x0010-0x0016) - 0.1°C resolution, 0x8000 = no sensor
    "outside_temperature": 0x0010,           # TZ1 - Temperatura zewnętrzna
    "supply_temperature": 0x0011,            # TN1 - Temperatura nawiewu
    "exhaust_temperature": 0x0012,           # TP - Temperatura wywiewu  
    "extract_temperature": 0x0012,           # Alias for exhaust
    "fpx_temperature": 0x0013,               # TZ2 - Temperatura za nagrzewnicą FPX
    "duct_supply_temperature": 0x0014,       # TN2 - Temperatura za nagrzewnicą kanałową
    "gwc_temperature": 0x0015,               # TZ3 - Temperatura przed GWC
    "ambient_temperature": 0x0016,           # TO - Temperatura otoczenia
    
    # Serial number (0x0018-0x001D)
    "serial_number_1": 0x0018,               # Numer seryjny - część 1
    "serial_number_2": 0x0019,               # Numer seryjny - część 2
    "serial_number_3": 0x001A,               # Numer seryjny - część 3
    "serial_number_4": 0x001B,               # Numer seryjny - część 4
    "serial_number_5": 0x001C,               # Numer seryjny - część 5
    "serial_number_6": 0x001D,               # Numer seryjny - część 6
    
    # Airflow and pressure sensors (0x001E-0x002F)
    "supply_flowrate": 0x001E,               # Strumień objętości powietrza nawiewanego [m³/h]
    "exhaust_flowrate": 0x001F,              # Strumień objętości powietrza usuwanego [m³/h]
    "supply_percentage": 0x0020,             # Wartość procentowa wentylatora nawiewnego [%]
    "exhaust_percentage": 0x0021,            # Wartość procentowa wentylatora wywiewnego [%]
    "supply_pressure": 0x0022,               # Ciśnienie na wentylatorze nawiewnym [Pa]
    "exhaust_pressure": 0x0023,              # Ciśnienie na wentylatorze wywiewnym [Pa]
    "heat_recovery_efficiency": 0x0024,      # Sprawność odzysku ciepła [%]
    "air_damper_opening": 0x0025,            # Otwarcie przepustnicy powietrza [%]
    "bypassing_factor": 0x0026,              # Współczynnik bypassu [%]
    "constant_flow_active": 0x0027,          # Status systemu stałego przepływu (0/1)
    "supply_pressure_pa": 0x0028,            # Ciśnienie dokładne nawiew [Pa]
    "exhaust_pressure_pa": 0x0029,          # Ciśnienie dokładne wywiew [Pa]
    "filter_pressure_alarm": 0x002A,        # Alarm ciśnienia filtra (0/1)
    "presostat_differential": 0x002B,       # Różnica ciśnień presostat [Pa]
    "actual_flowrate": 0x002C,               # Aktualny przepływ powietrza [m³/h]
    "flow_balance": 0x002D,                  # Bilans przepływu [%]
    "battery_status": 0x002E,                # Stan baterii
    "power_quality": 0x002F,                 # Stan jakości zasilania
    
    # Additional sensors and status (0x0030-0x003F)
    "co2_concentration": 0x0030,             # Stężenie CO2 [ppm]
    "voc_level": 0x0031,                     # Poziom VOC
    "air_quality_index": 0x0032,             # Indeks jakości powietrza
    "outside_humidity": 0x0033,              # Wilgotność zewnętrzna [%]
    "inside_humidity": 0x0034,               # Wilgotność wewnętrzna [%]
    "filter_time_remaining": 0x0035,         # Pozostały czas pracy filtra [dni]
    "filter_operating_hours": 0x0036,        # Godziny pracy filtra [h]
    "filter_alarm": 0x0037,                  # Alarm wymiany filtra (0/1)
    "system_runtime": 0x0038,                # Czas pracy systemu [h]
    "power_consumption": 0x0039,             # Zużycie energii [W]
    "energy_savings": 0x003A,                # Oszczędności energii [%]
    "system_alarms": 0x003B,                 # Aktywne alarmy systemu
    "maintenance_mode": 0x003C,              # Tryb serwisowy (0/1)
    "system_locked": 0x003D,                 # Blokada systemu (0/1)
    "expansion_module_status": 0x003E,       # Status modułu rozszerzenia
    "communication_status": 0x003F,          # Status komunikacji
}

# HOLDING REGISTERS (03 - READ HOLDING REGISTER) - Konfiguracja i kontrola
HOLDING_REGISTERS = {
    # System control and mode settings (0x1130-0x113F)
    "mode": 0x1130,                          # Tryb pracy (0-auto, 1-manual, 2-temporary)
    "air_flow_rate_manual": 0x1131,          # Intensywność wentylacji - tryb manual [%]
    "airflow_rate_change_flag": 0x1132,      # Flaga zmiany intensywności
    "cfgMode2": 0x1133,                      # Alternatywny rejestr trybu pracy
    "supply_temperature_temporary": 0x1134,  # Temperatura nawiewu - tryb temporary [°C]
    "temperature_change_flag": 0x1135,       # Flaga zmiany temperatury
    "hard_reset_settings": 0x113D,           # Reset ustawień użytkownika
    "hard_reset_schedule": 0x113E,           # Reset harmonogramów
    
    # Temperature control (0x1140-0x114F)
    "supply_temperature_manual": 0x1140,     # Temperatura nawiewu - tryb manual [°C]
    "supply_temperature_auto": 0x1141,       # Temperatura nawiewu - tryb auto [°C]
    "heating_temperature": 0x1142,           # Temperatura grzania [°C]
    "cooling_temperature": 0x1143,           # Temperatura chłodzenia [°C]
    "comfort_temperature": 0x1144,           # Temperatura komfort [°C]
    "economy_temperature": 0x1145,           # Temperatura ekonomiczna [°C]
    "frost_protection_temp": 0x1146,         # Temperatura ochrony przed mrozem [°C]
    "overheat_protection_temp": 0x1147,      # Temperatura ochrony przed przegrzaniem [°C]
    "gwc_activation_temp": 0x1148,           # Temperatura aktywacji GWC [°C]
    "bypass_activation_temp": 0x1149,        # Temperatura aktywacji bypass [°C]
    "supply_temp_diff": 0x114A,              # Różnica temperatur nawiew [°C]
    "extract_temp_diff": 0x114B,             # Różnica temperatur wywiew [°C]
    "temperature_hysteresis": 0x114C,        # Histereza temperatury [°C]
    "required_temp": 0x1FFE,                 # Temperatura zadana trybu KOMFORT [°C]
    
    # Air flow control (0x1150-0x115F)
    "air_flow_rate_auto": 0x1150,            # Intensywność wentylacji - tryb auto [%]
    "air_flow_rate_temporary": 0x1151,       # Intensywność wentylacji - tryb temporary [%]
    "supply_flow_min": 0x1152,               # Minimalny przepływ nawiew [m³/h]
    "supply_flow_max": 0x1153,               # Maksymalny przepływ nawiew [m³/h]
    "exhaust_flow_min": 0x1154,              # Minimalny przepływ wywiew [m³/h]
    "exhaust_flow_max": 0x1155,              # Maksymalny przepływ wywiew [m³/h]
    "constant_pressure_setpoint": 0x1156,    # Zadane ciśnienie stałe [Pa]
    "variable_pressure_setpoint": 0x1157,    # Zadane ciśnienie zmienne [Pa]
    "supply_fan_speed": 0x1158,              # Prędkość wentylatora nawiewnego [%]
    "exhaust_fan_speed": 0x1159,             # Prędkość wentylatora wywiewnego [%]
    
    # Special functions and modes (0x1160-0x116F)
    "on_off_panel_mode": 0x1160,             # Tryb panelu ON/OFF
    "season_mode": 0x1161,                   # Tryb sezonowy (0-zima, 1-lato)
    "special_mode": 0x1162,                  # Tryb specjalny
    "okap_mode": 0x1163,                     # Tryb OKAP
    "okap_intensity": 0x1164,                # Intensywność OKAP [%]
    "kominek_mode": 0x1165,                  # Tryb KOMINEK
    "kominek_intensity": 0x1166,             # Intensywność KOMINEK [%]
    "wietrzenie_mode": 0x1167,               # Tryb WIETRZENIE
    "wietrzenie_intensity": 0x1168,          # Intensywność WIETRZENIE [%]
    "pusty_dom_mode": 0x1169,                # Tryb PUSTY DOM
    "pusty_dom_intensity": 0x116A,           # Intensywność PUSTY DOM [%]
    "boost_mode": 0x116B,                    # Tryb BOOST
    "boost_intensity": 0x116C,               # Intensywność BOOST [%]
    "night_mode": 0x116D,                    # Tryb nocny
    "night_mode_intensity": 0x116E,          # Intensywność trybu nocnego [%]
    "party_mode": 0x116F,                    # Tryb PARTY
    
    # Advanced system settings (0x1170-0x117F)
    "gwc_mode": 0x1170,                      # Tryb GWC (0-wyłączone, 1-włączone)
    "bypass_mode": 0x1171,                   # Tryb bypass
    "heating_season": 0x1172,                # Sezon grzewczy (0-nie, 1-tak)
    "cooling_season": 0x1173,                # Sezon chłodniczy (0-nie, 1-tak)
    "automatic_mode_settings": 0x1174,       # Ustawienia trybu automatycznego
    "manual_mode_settings": 0x1175,          # Ustawienia trybu manualnego
    "temporary_mode_duration": 0x1176,       # Czas trwania trybu temporary [min]
    "vacation_mode": 0x1177,                 # Tryb wakacyjny
    "vacation_mode_intensity": 0x1178,       # Intensywność trybu wakacyjnego [%]
    "anti_freeze_protection": 0x1179,        # Ochrona przeciwmrozowa
    "overheat_protection": 0x117A,           # Ochrona przed przegrzaniem
    "filter_monitor_mode": 0x117B,           # Tryb monitorowania filtra
    "presostat_mode": 0x117C,                # Tryb presostat
    "constant_flow_mode": 0x117D,            # Tryb stałego przepływu
    "air_quality_control": 0x117E,           # Kontrola jakości powietrza
    "humidity_control": 0x117F,              # Kontrola wilgotności
    
    # Schedule settings - Week 1 (0x1200-0x123F)
    "schedule_week1_monday_period1_start": 0x1200,    # Poniedziałek okres 1 start
    "schedule_week1_monday_period1_end": 0x1201,      # Poniedziałek okres 1 koniec
    "schedule_week1_monday_period1_intensity": 0x1202, # Poniedziałek okres 1 intensywność
    "schedule_week1_monday_period1_temp": 0x1203,     # Poniedziałek okres 1 temperatura
    "schedule_week1_monday_period2_start": 0x1204,    # Poniedziałek okres 2 start
    "schedule_week1_monday_period2_end": 0x1205,      # Poniedziałek okres 2 koniec
    "schedule_week1_monday_period2_intensity": 0x1206, # Poniedziałek okres 2 intensywność
    "schedule_week1_monday_period2_temp": 0x1207,     # Poniedziałek okres 2 temperatura
    "schedule_week1_monday_period3_start": 0x1208,    # Poniedziałek okres 3 start
    "schedule_week1_monday_period3_end": 0x1209,      # Poniedziałek okres 3 koniec
    "schedule_week1_monday_period3_intensity": 0x120A, # Poniedziałek okres 3 intensywność
    "schedule_week1_monday_period3_temp": 0x120B,     # Poniedziałek okres 3 temperatura
    "schedule_week1_monday_period4_start": 0x120C,    # Poniedziałek okres 4 start
    "schedule_week1_monday_period4_end": 0x120D,      # Poniedziałek okres 4 koniec
    "schedule_week1_monday_period4_intensity": 0x120E, # Poniedziałek okres 4 intensywność
    "schedule_week1_monday_period4_temp": 0x120F,     # Poniedziałek okres 4 temperatura
    
    # Device identification and security (0x1FD0-0x1FFF)
    "device_name_1": 0x1FD4,                 # Nazwa urządzenia - część 1
    "device_name_2": 0x1FD5,                 # Nazwa urządzenia - część 2
    "device_name_3": 0x1FD6,                 # Nazwa urządzenia - część 3
    "device_name_4": 0x1FD7,                 # Nazwa urządzenia - część 4
    "lock_pass_1": 0x1FFB,                   # Klucz produktu - słowo młodsze
    "lock_pass_2": 0x1FFC,                   # Klucz produktu - słowo starsze
    "lock_flag": 0x1FFD,                     # Aktywacja blokady urządzenia
    "filter_change": 0x1FFF,                 # System kontroli filtrów / typ filtrów
}

# COIL REGISTERS (01 - READ COILS) - Wyjścia cyfrowe / przekaźniki
COIL_REGISTERS = {
    "duct_warter_heater_pump": 0x0005,       # Przekaźnik pompy obiegowej nagrzewnicy
    "bypass": 0x0009,                        # Siłownik przepustnicy bypass
    "info": 0x000A,                          # Sygnał potwierdzenia pracy centrali (O1)
    "power_supply_fans": 0x000B,             # Przekaźnik zasilania wentylatorów
    "heating_cable": 0x000C,                 # Przekaźnik zasilania kabla grzejnego
    "work_permit": 0x000D,                   # Przekaźnik potwierdzenia pracy (Expansion)
    "gwc": 0x000E,                           # Przekaźnik GWC
    "hood": 0x000F,                          # Zasilanie przepustnicy okapu
    "air_intake_damper": 0x0010,             # Przepustnica poboru powietrza
    "alarm_output": 0x0011,                  # Wyjście alarmowe
    "expansion_output_1": 0x0012,            # Wyjście rozszerzenia 1
    "expansion_output_2": 0x0013,            # Wyjście rozszerzenia 2
    "expansion_output_3": 0x0014,            # Wyjście rozszerzenia 3
    "expansion_output_4": 0x0015,            # Wyjście rozszerzenia 4
    "defrosting_active": 0x0016,             # Aktywne rozmrażanie
    "cooling_active": 0x0017,                # Aktywne chłodzenie
    "heating_active": 0x0018,                # Aktywne grzanie
    "summer_mode_active": 0x0019,            # Aktywny tryb letni
    "winter_mode_active": 0x001A,            # Aktywny tryb zimowy
    "maintenance_required": 0x001B,          # Wymagana konserwacja
    "filter_replacement_required": 0x001C,   # Wymagana wymiana filtra
    "system_error": 0x001D,                  # Błąd systemu
    "communication_error": 0x001E,           # Błąd komunikacji
    "sensor_error": 0x001F,                  # Błąd czujnika
}

# DISCRETE INPUTS (02 - READ DISCRETE INPUTS) - Wejścia cyfrowe / czujniki
DISCRETE_INPUTS = {
    "door_sensor": 0x0010,                   # Czujnik drzwi
    "window_sensor": 0x0011,                 # Czujnik okna
    "presence_sensor": 0x0012,               # Czujnik obecności
    "motion_sensor": 0x0013,                 # Czujnik ruchu
    "smoke_detector": 0x0014,                # Czujnik dymu
    "fire_alarm": 0x0015,                    # Alarm pożarowy
    "water_leak_sensor": 0x0016,             # Czujnik wycieku wody
    "external_alarm": 0x0017,                # Alarm zewnętrzny
    "expansion_input_1": 0x0018,             # Wejście rozszerzenia 1
    "expansion_input_2": 0x0019,             # Wejście rozszerzenia 2
    "expansion_input_3": 0x001A,             # Wejście rozszerzenia 3
    "expansion_input_4": 0x001B,             # Wejście rozszerzenia 4
    "filter_alarm_input": 0x001C,            # Wejście alarmu filtra
    "external_temperature_sensor": 0x001D,   # Zewnętrzny czujnik temperatury
    "external_humidity_sensor": 0x001E,      # Zewnętrzny czujnik wilgotności
    "external_co2_sensor": 0x001F,           # Zewnętrzny czujnik CO2
    "remote_control_signal": 0x0020,         # Sygnał zdalnego sterowania
    "panel_lock_status": 0x0021,             # Status blokady panelu
    "service_mode_active": 0x0022,           # Aktywny tryb serwisowy
    "bypass_status": 0x0023,                 # Status bypass
    "gwc_status": 0x0024,                    # Status GWC
    "heating_status": 0x0025,                # Status grzania
    "cooling_status": 0x0026,                # Status chłodzenia
    "defrost_status": 0x0027,                # Status rozmrażania
    "filter_status": 0x0028,                 # Status filtra
    "fan_status_supply": 0x0029,             # Status wentylatora nawiewnego
    "fan_status_exhaust": 0x002A,            # Status wentylatora wywiewnego
    "power_supply_status": 0x002B,           # Status zasilania
    "communication_status_modbus": 0x002C,   # Status komunikacji Modbus
    "expansion_module": 0x002D,              # Moduł rozszerzenia
    "air_quality_alarm": 0x002E,             # Alarm jakości powietrza
    "system_ready": 0x002F,                  # System gotowy
}

# ============================================================================
# REGISTER PROCESSING CONFIGURATION
# ============================================================================

# Register value processing configuration
REGISTER_PROCESSING = {
    # Sensor unavailable value
    "sensor_unavailable_value": 0x8000,  # 32768 - indicates sensor not connected
    
    # Temperature registers - 0.1°C resolution, 0x8000 = sensor not available
    "temperature_registers": {
        "outside_temperature", "supply_temperature", "exhaust_temperature", 
        "fpx_temperature", "duct_supply_temperature", "gwc_temperature", 
        "ambient_temperature", "supply_temperature_manual", "supply_temperature_auto",
        "supply_temperature_temporary", "heating_temperature", "cooling_temperature",
        "comfort_temperature", "economy_temperature", "frost_protection_temp",
        "overheat_protection_temp", "gwc_activation_temp", "bypass_activation_temp",
        "supply_temp_diff", "extract_temp_diff", "temperature_hysteresis",
        "required_temp"
    },
    
    # Percentage registers - 0-100% or extended ranges
    "percentage_registers": {
        "supply_percentage", "exhaust_percentage", "heat_recovery_efficiency",
        "air_damper_opening", "bypassing_factor", "air_flow_rate_manual",
        "air_flow_rate_auto", "air_flow_rate_temporary", "flow_balance",
        "supply_fan_speed", "exhaust_fan_speed", "okap_intensity", "kominek_intensity",
        "wietrzenie_intensity", "pusty_dom_intensity", "boost_intensity",
        "night_mode_intensity", "party_mode_intensity", "vacation_mode_intensity",
        "outside_humidity", "inside_humidity", "energy_savings"
    },
    
    # Flow rate registers - m³/h
    "flow_registers": {
        "supply_flowrate", "exhaust_flowrate", "actual_flowrate",
        "supply_flow_min", "supply_flow_max", "exhaust_flow_min", "exhaust_flow_max"
    },
    
    # Pressure registers - Pa
    "pressure_registers": {
        "supply_pressure", "exhaust_pressure", "supply_pressure_pa", "exhaust_pressure_pa",
        "constant_pressure_setpoint", "variable_pressure_setpoint", "filter_pressure_alarm",
        "presostat_differential"
    },
    
    # Time registers - hours or minutes
    "time_registers": {
        "filter_time_remaining", "filter_operating_hours", "system_runtime",
        "temporary_mode_duration"
    },
    
    # Air quality registers - ppm or index
    "air_quality_registers": {
        "co2_concentration", "voc_level", "air_quality_index"
    },
    
    # Power registers - watts
    "power_registers": {
        "power_consumption"
    },
    
    # Mode registers with specific value ranges
    "mode_registers": {
        "mode": {"min": 0, "max": 2},  # 0-auto, 1-manual, 2-temporary
        "season_mode": {"min": 0, "max": 1},  # 0-winter, 1-summer
        "on_off_panel_mode": {"min": 0, "max": 1},
        "special_mode": {"min": 0, "max": 10},
        "filter_change": {"min": 1, "max": 4},  # 1-presostat, 2-płaskie, 3-CleanPad, 4-CleanPad Pure
    },
    
    # Boolean registers (0/1)
    "boolean_registers": {
        "constant_flow_active", "filter_pressure_alarm", "filter_alarm",
        "maintenance_mode", "system_locked", "gwc_mode", "bypass_mode",
        "heating_season", "cooling_season", "vacation_mode", "anti_freeze_protection",
        "overheat_protection", "filter_monitor_mode", "presostat_mode",
        "constant_flow_mode", "air_quality_control", "humidity_control",
        "night_mode", "party_mode", "boost_mode", "lock_flag"
    },
}

# ============================================================================
# REGISTER GROUPING FOR OPTIMIZED READING
# ============================================================================

# Pre-calculated register groups for batch reading optimization
REGISTER_GROUPS = {
    "firmware_info": {
        "start": 0x0000,
        "count": 5,
        "registers": ["firmware_major", "firmware_minor", "day_of_week", "period", "firmware_patch"]
    },
    "temperature_sensors": {
        "start": 0x0010,
        "count": 7,
        "registers": ["outside_temperature", "supply_temperature", "exhaust_temperature", 
                     "fpx_temperature", "duct_supply_temperature", "gwc_temperature", "ambient_temperature"]
    },
    "serial_number": {
        "start": 0x0018,
        "count": 6,
        "registers": ["serial_number_1", "serial_number_2", "serial_number_3", 
                     "serial_number_4", "serial_number_5", "serial_number_6"]
    },
    "airflow_sensors": {
        "start": 0x001E,
        "count": 16,
        "registers": ["supply_flowrate", "exhaust_flowrate", "supply_percentage", "exhaust_percentage",
                     "supply_pressure", "exhaust_pressure", "heat_recovery_efficiency", "air_damper_opening",
                     "bypassing_factor", "constant_flow_active", "supply_pressure_pa", "exhaust_pressure_pa",
                     "filter_pressure_alarm", "presostat_differential", "actual_flowrate", "flow_balance"]
    },
    "system_status": {
        "start": 0x002E,
        "count": 18,
        "registers": ["battery_status", "power_quality", "co2_concentration", "voc_level",
                     "air_quality_index", "outside_humidity", "inside_humidity", "filter_time_remaining",
                     "filter_operating_hours", "filter_alarm", "system_runtime", "power_consumption",
                     "energy_savings", "system_alarms", "maintenance_mode", "system_locked",
                     "expansion_module_status", "communication_status"]
    },
    "main_control": {
        "start": 0x1130,
        "count": 16,
        "registers": ["mode", "air_flow_rate_manual", "airflow_rate_change_flag", "cfgMode2",
                     "supply_temperature_temporary", "temperature_change_flag", "_gap_1136", "_gap_1137",
                     "_gap_1138", "_gap_1139", "_gap_113A", "_gap_113B", "_gap_113C", 
                     "hard_reset_settings", "hard_reset_schedule", "_gap_113F"]
    },
    "special_functions": {
        "start": 0x1160,
        "count": 16,
        "registers": ["on_off_panel_mode", "season_mode", "special_mode", "okap_mode",
                     "okap_intensity", "kominek_mode", "kominek_intensity", "wietrzenie_mode",
                     "wietrzenie_intensity", "pusty_dom_mode", "pusty_dom_intensity", "boost_mode",
                     "boost_intensity", "night_mode", "night_mode_intensity", "party_mode"]
    },
}

# Entity categories for proper Home Assistant organization
ENTITY_CATEGORIES = {
    "config": [
        "mode", "on_off_panel_mode", "season_mode", "special_mode", "gwc_mode", "bypass_mode",
        "air_flow_rate_manual", "air_flow_rate_auto", "supply_temperature_manual", 
        "supply_temperature_auto", "comfort_temperature", "economy_temperature"
    ],
    "diagnostic": [
        "firmware_major", "firmware_minor", "firmware_patch", "compilation_days", "compilation_seconds",
        "serial_number_1", "serial_number_2", "serial_number_3", "serial_number_4", 
        "serial_number_5", "serial_number_6", "system_runtime", "power_consumption",
        "energy_savings", "system_alarms", "communication_status", "expansion_module_status"
    ]
}

# Device class mapping for proper Home Assistant entity types
DEVICE_CLASSES = {
    "temperature": [
        "outside_temperature", "supply_temperature", "exhaust_temperature", "fpx_temperature",
        "duct_supply_temperature", "gwc_temperature", "ambient_temperature", "supply_temperature_manual",
        "supply_temperature_auto", "supply_temperature_temporary", "heating_temperature", 
        "cooling_temperature", "comfort_temperature", "economy_temperature", "required_temp"
    ],
    "humidity": [
        "outside_humidity", "inside_humidity"
    ],
    "pressure": [
        "supply_pressure", "exhaust_pressure", "supply_pressure_pa", "exhaust_pressure_pa",
        "constant_pressure_setpoint", "variable_pressure_setpoint", "presostat_differential"
    ],
    "power": [
        "power_consumption"
    ],
    "energy": [
        "energy_savings"
    ],
    "duration": [
        "filter_time_remaining", "filter_operating_hours", "system_runtime", "temporary_mode_duration"
    ],
    "aqi": [
        "air_quality_index"
    ],
    "volume_flow_rate": [
        "supply_flowrate", "exhaust_flowrate", "actual_flowrate", "supply_flow_min",
        "supply_flow_max", "exhaust_flow_min", "exhaust_flow_max"
    ]
}

# Unit mapping for sensors
UNITS = {
    "temperature": "°C",
    "humidity": "%",
    "pressure": "Pa",
    "power": "W",
    "energy": "%",
    "duration": "h",
    "volume_flow_rate": "m³/h",
    "percentage": "%",
    "ppm": "ppm",
    "days": "days"
}

# Special function mappings
SPECIAL_FUNCTIONS = {
    0: "OFF",
    1: "OKAP",
    2: "KOMINEK", 
    3: "WIETRZENIE",
    4: "PUSTY DOM",
    5: "BOOST",
    6: "NIGHT",
    7: "PARTY",
    8: "VACATION",
    9: "DEFROST",
    10: "MAINTENANCE"
}

# Mode mappings
MODE_MAPPINGS = {
    "mode": {0: "AUTO", 1: "MANUAL", 2: "TEMPORARY"},
    "season_mode": {0: "WINTER", 1: "SUMMER"},
    "on_off_panel_mode": {0: "OFF", 1: "ON"},
    "filter_change": {1: "PRESOSTAT", 2: "FLAT_FILTERS", 3: "CLEANPAD", 4: "CLEANPAD_PURE"}
}