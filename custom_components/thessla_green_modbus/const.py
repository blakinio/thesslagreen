"""Constants for ThesslaGreen Modbus integration - HA 2025.7+ Compatible."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "thessla_green_modbus"

# Default configuration values
DEFAULT_NAME = "ThesslaGreen"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 10
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3

# Configuration keys
CONF_SLAVE_ID = "slave_id"
CONF_TIMEOUT = "timeout"
CONF_RETRY = "retry"

# Platforms
PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.CLIMATE,
    Platform.FAN,
]

# Enhanced Input Registers (Read-only values) - HA 2025.7+ Compatible
INPUT_REGISTERS = {
    # Firmware information
    "firmware_major": 0x0000,                # Wersja oprogramowania - część całkowita
    "firmware_minor": 0x0001,                # Wersja oprogramowania - część ułamkowa

    # Temperature sensors (0.5°C resolution, signed values)
    "outside_temperature": 0x0010,           # TZ1 - Temperatura zewnętrzna
    "supply_temperature": 0x0011,            # TN1 - Temperatura nawiewu
    "exhaust_temperature": 0x0012,           # TP - Temperatura wywiewu
    "fpx_temperature": 0x0013,               # TZ2 - Temperatura FPX
    "duct_supply_temperature": 0x0014,       # TN2 - Temperatura kanałowa
    "gwc_temperature": 0x0015,               # TZ3 - Temperatura GWC
    "ambient_temperature": 0x0016,           # TO - Temperatura otoczenia
    
    # Flow rates (m³/h)
    "supply_flowrate": 0x0020,               # Przepływ nawiewu
    "exhaust_flowrate": 0x0021,              # Przepływ wywiewu
    "supply_air_flow": 0x0022,               # Strumień nawiewu
    "exhaust_air_flow": 0x0023,              # Strumień wywiewu
    
    # Performance indicators (%)
    "supply_percentage": 0x0030,             # Intensywność nawiewu
    "exhaust_percentage": 0x0031,            # Intensywność wywiewu
    "heat_recovery_efficiency": 0x0032,      # Sprawność rekuperacji
    "heating_efficiency": 0x0033,            # Sprawność grzania
    
    # System status registers
    "operating_hours": 0x0040,               # Godziny pracy
    "filter_time_remaining": 0x0041,         # Czas do wymiany filtra (dni)
    "antifreeze_stage": 0x0042,              # Stopień zabezpieczenia przed zamarzaniem
    "error_code": 0x0043,                    # Aktualny kod błędu
    "warning_code": 0x0044,                  # Aktualny kod ostrzeżenia
    
    # Enhanced diagnostics (HA 2025.7+)
    "firmware_version": 0x0050,              # Wersja firmware
    "device_serial": 0x0051,                 # Numer seryjny urządzenia
    "actual_power_consumption": 0x0052,      # Aktualne zużycie mocy (W)
    "cumulative_power_consumption": 0x0053,  # Zużycie energii skumulowane (kWh)
    
    # Constant Flow system
    "constant_flow_supply": 0x0060,          # CF - Przepływ nawiewu
    "constant_flow_exhaust": 0x0061,         # CF - Przepływ wywiewu
    "constant_flow_supply_setpoint": 0x0062, # CF - Zadane nawiewu
    "constant_flow_exhaust_setpoint": 0x0063, # CF - Zadane wywiewu
    
    # GWC (Ground Heat Exchanger) readings
    "gwc_inlet_temperature": 0x0070,         # Temperatura wlotu GWC
    "gwc_outlet_temperature": 0x0071,        # Temperatura wylotu GWC
    "gwc_efficiency": 0x0072,                # Sprawność GWC
    
    # Bypass system
    "bypass_position": 0x0080,               # Pozycja bypassa (%)
    "bypass_inlet_temperature": 0x0081,      # Temperatura wlotu bypass
    "bypass_outlet_temperature": 0x0082,     # Temperatura wylotu bypass
}

# Enhanced Holding Registers (Read/Write control values) - HA 2025.7+ Compatible  
HOLDING_REGISTERS = {
    # Basic control
    "mode": 0x1070,                          # Tryb pracy AirPack
    "season_mode": 0x1071,                   # Wybór harmonogramu - tryb AUTOMATYCZNY
    "air_flow_rate_manual": 0x1072,          # Intensywność wentylacji - tryb MANUALNY
    "air_flow_rate_temporary": 0x1073,       # Intensywność wentylacji - tryb CHWILOWY
    "supply_temperature_manual": 0x1074,     # Temperatura nawiewu - tryb MANUALNY
    "supply_temperature_temporary": 0x1075,  # Temperatura nawiewu - tryb CHWILOWY
    "fan_speed_1_coef": 0x1078,              # Współczynnik prędkości went. - bieg 1
    "fan_speed_2_coef": 0x1079,              # Współczynnik prędkości went. - bieg 2
    "fan_speed_3_coef": 0x107A,              # Współczynnik prędkości went. - bieg 3
    "manual_airing_time_to_start": 0x107B,   # Czas do startu ręcznego wietrzenia
    "special_mode": 0x1080,                  # Funkcja specjalna

    # Constant Flow control
    "constant_flow_mode": 0x1090,            # Tryb Constant Flow
    "constant_flow_supply_target": 0x1091,   # Zadany przepływ nawiewu CF
    "constant_flow_exhaust_target": 0x1092,  # Zadany przepływ wywiewu CF
    "constant_flow_tolerance": 0x1093,       # Tolerancja CF (%)
}

# Enhanced Coil Registers (Digital inputs/outputs) - HA 2025.7+ Compatible
COIL_REGISTERS = {
    # Digital outputs
    "duct_warter_heater_pump": 0x0005,       # Przekaźnik pompy nagrzewnicy kanałowej
    "bypass": 0x0009,                        # Siłownik przepustnicy bypass
    "info": 0x000A,                          # Sygnał potwierdzenia pracy centrali (O1)
    "power_supply_fans": 0x000B,             # Przekaźnik zasilania wentylatorów
    "heating_cable": 0x000C,                 # Przekaźnik zasilania kabla grzejnego
    "workt_permit": 0x000D,                  # Przekaźnik potwierdzenia pracy (Expansion)
    "gwc": 0x000E,                           # Przekaźnik GWC
}

# Discrete Inputs (Read-only digital status) - HA 2025.7+ Compatible
DISCRETE_INPUTS = {
    # Digital inputs
    "duct_heater_protection": 0x0000,        # Zabezpieczenie termiczne nagrzewnicy kanałowej
    "expansion": 0x0001,                     # Komunikacja z modułem Expansion
    "dp_duct_filter_overflow": 0x0003,       # Presostat filtra kanałowego
    "hood": 0x0004,                          # Wejście funkcji OKAP
    "contamination_sensor": 0x0005,          # Czujnik jakości powietrza
    "airing_sensor": 0x0006,                 # Czujnik wilgotności dwustanowy
    "airing_switch": 0x0007,                 # Włącznik funkcji WIETRZENIE
    "airing_mini": 0x000A,                   # Przełącznik AirS - wietrzenie
    "fan_speed_3": 0x000B,                   # Przełącznik AirS - 3 bieg
    "fan_speed_2": 0x000C,                   # Przełącznik AirS - 2 bieg
    "fan_speed_1": 0x000D,                   # Przełącznik AirS - 1 bieg
    "fireplace": 0x000E,                     # Włącznik funkcji KOMINEK
    "ppoz": 0x000F,                          # Alarm pożarowy (P.POZ.)
    "dp_ahu_filter_overflow": 0x0012,        # Presostat filtrów w rekuperatorze (DP1)
    "ahu_filter_protection": 0x0013,         # Zabezpieczenie filtrów w rekuperatorze
    "empty_house": 0x0015,                   # Sygnał funkcji PUSTY DOM
}

# Enhanced Operating Modes - HA 2025.7+ Compatible
OPERATING_MODES = {
    0: "Automatyczny",
    1: "Manualny", 
    2: "Chwilowy",
    3: "Tryb serwisowy",  # Enhanced for HA 2025.7+
    4: "Tryb awaryjny",   # Enhanced for HA 2025.7+
}

SEASON_MODES = {
    0: "Zima",
    1: "Lato",
    2: "Przejściowy",     # Enhanced for HA 2025.7+
}

# Enhanced Special Functions - HA 2025.7+ Compatible
SPECIAL_MODES = {
    0: "Brak",
    1: "OKAP",                    # Hood extraction mode
    2: "KOMINEK",                 # Fireplace mode
    3: "WIETRZENIE RECZNE",       # Manual airing
    4: "WIETRZENIE AUTO",         # Automatic airing  
    5: "BOOST",                   # Boost mode (Enhanced HA 2025.7+)
    6: "ECO",                     # Eco mode (Enhanced HA 2025.7+)
    7: "WIETRZENIE",             # General airing
    8: "GOTOWANIE",              # Cooking mode (Enhanced HA 2025.7+)
    9: "PRANIE",                 # Laundry mode (Enhanced HA 2025.7+)
    10: "LAZIENKA",              # Bathroom mode (Enhanced HA 2025.7+)
    11: "PUSTY DOM",             # Empty house mode
    12: "OTWARTE OKNA",          # Open windows mode (Enhanced HA 2025.7+)
    13: "NOC",                   # Night mode (Enhanced HA 2025.7+)
    14: "WAKACJE",               # Vacation mode (Enhanced HA 2025.7+)
    15: "PARTY",                 # Party mode (Enhanced HA 2025.7+)
}

# Enhanced Error Codes - HA 2025.7+ Compatible
ERROR_CODES = {
    0: "Brak błędu",
    1: "Błąd czujnika TZ1",
    2: "Błąd czujnika TN1", 
    3: "Błąd czujnika TP",
    4: "Błąd czujnika TZ2",
    5: "Błąd czujnika TN2",
    6: "Błąd czujnika TZ3",
    7: "Błąd czujnika TO",
    8: "Błąd wentylatora nawiewu",
    9: "Błąd wentylatora wywiewu",
    10: "Błąd komunikacji Modbus",
    11: "Błąd zabezpieczenia termicznego",
    12: "Błąd bypass",
    13: "Błąd GWC",
    14: "Błąd podgrzewacza",          # Enhanced HA 2025.7+
    15: "Błąd systemu chłodzenia",    # Enhanced HA 2025.7+
    16: "Błąd zasilania",             # Enhanced HA 2025.7+
    17: "Błąd pamięci",               # Enhanced HA 2025.7+
    18: "Błąd kalibracji",            # Enhanced HA 2025.7+
}

WARNING_CODES = {
    0: "Brak ostrzeżeń",
    1: "Wymiana filtra",
    2: "Serwis urządzenia",
    3: "Niska temperatura zewnętrzna",
    4: "Wysoka temperatura zewnętrzna",
    5: "Obniżona sprawność",
    6: "Nieoptymalne warunki pracy",
    7: "Konieczne sprawdzenie GWC",
    8: "Konieczne sprawdzenie bypass",
    9: "Zbliżający się serwis",       # Enhanced HA 2025.7+
    10: "Niska efektywność filtra",   # Enhanced HA 2025.7+
    11: "Wysokie zużycie energii",    # Enhanced HA 2025.7+
    12: "Niestabilne parametry",      # Enhanced HA 2025.7+
}

# Service names - ALL REQUIRED FOR __init__.py
SERVICE_SET_MODE = "set_operating_mode"
SERVICE_SET_INTENSITY = "set_intensity"
SERVICE_SET_SPECIAL_FUNCTION = "set_special_function"  
SERVICE_RESET_ALARMS = "reset_alarms"
SERVICE_DEVICE_RESCAN = "rescan_device"

# Enhanced service names (HA 2025.7+) - ALL REQUIRED FOR __init__.py
SERVICE_SET_COMFORT_TEMPERATURE = "set_comfort_temperature"
SERVICE_ACTIVATE_BOOST = "activate_boost_mode"
SERVICE_SCHEDULE_MAINTENANCE = "schedule_maintenance"
SERVICE_CALIBRATE_SENSORS = "calibrate_sensors"
SERVICE_CONFIGURE_GWC = "configure_gwc"
SERVICE_CONFIGURE_BYPASS = "configure_bypass"
SERVICE_CONFIGURE_CONSTANT_FLOW = "configure_constant_flow"
SERVICE_EMERGENCY_STOP = "emergency_stop"
SERVICE_QUICK_VENTILATION = "quick_ventilation"

# Register groups for optimized batch reading
REGISTER_GROUPS = {
    "temperatures": ["outside_temperature", "supply_temperature", "exhaust_temperature", 
                    "fpx_temperature", "duct_supply_temperature", "gwc_temperature", "ambient_temperature"],
    "flows": ["supply_flowrate", "exhaust_flowrate", "supply_air_flow", "exhaust_air_flow"],
    "performance": ["supply_percentage", "exhaust_percentage", "heat_recovery_efficiency"],
    "control": ["mode", "special_mode", "air_flow_rate_manual", "comfort_mode"],
    "diagnostics": ["error_code", "warning_code", "operating_hours", "filter_time_remaining"],
    "enhanced": ["actual_power_consumption", "firmware_version", "device_serial"],  # HA 2025.7+
}