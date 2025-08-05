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
    "mode": 0x1000,                          # Tryb pracy (0=Auto, 1=Manual, 2=Temporary)
    "on_off_panel_mode": 0x1001,             # Panel włączenia/wyłączenia
    "special_mode": 0x1002,                  # Funkcja specjalna
    "season_mode": 0x1003,                   # Tryb sezonowy (Zima/Lato)
    
    # Intensity control (10-150%)
    "air_flow_rate_manual": 0x1010,          # Intensywność w trybie manualnym
    "air_flow_rate_temporary": 0x1011,       # Intensywność w trybie chwilowym
    "air_flow_rate_auto": 0x1012,            # Intensywność w trybie automatycznym
    
    # Temperature control (0.5°C resolution)
    "supply_temperature_manual": 0x1020,     # Temperatura nawiewu - tryb manualny
    "supply_temperature_temporary": 0x1021,  # Temperatura nawiewu - tryb chwilowy
    "comfort_temperature_heating": 0x1022,   # Temperatura komfortu - grzanie
    "comfort_temperature_cooling": 0x1023,   # Temperatura komfortu - chłodzenie
    
    # Advanced control (HA 2025.7+ Enhanced)
    "comfort_mode": 0x1030,                  # Tryb komfortu (0=Off, 1=Heat, 2=Cool)
    "night_mode": 0x1031,                    # Tryb nocny
    "vacation_mode": 0x1032,                 # Tryb wakacyjny
    "boost_time_remaining": 0x1033,          # Czas pozostały trybu BOOST (min)
    "temporary_time_remaining": 0x1034,      # Czas pozostały trybu chwilowego (min)
    
    # Filter and maintenance
    "filter_change_interval": 0x1040,        # Interwał wymiany filtra (dni)
    "filter_warning_threshold": 0x1041,      # Próg ostrzeżenia filtra (dni)
    "maintenance_reset": 0x1042,             # Reset ostrzeżeń serwisowych
    
    # GWC control
    "gwc_mode": 0x1050,                      # Tryb GWC (0=Off, 1=Winter, 2=Summer)
    "gwc_regeneration_mode": 0x1051,         # Tryb regeneracji GWC
    "min_gwc_air_temperature": 0x1052,       # Min temperatura powietrza dla GWC
    "max_gwc_air_temperature": 0x1053,       # Max temperatura powietrza dla GWC
    "delta_t_gwc": 0x1054,                   # Delta T dla GWC
    
    # Bypass control (Enhanced for HA 2025.7+)
    "bypass_mode": 0x1060,                   # Tryb bypass (0=Off, 1=FreeHeating, 2=FreeCooling)
    "min_bypass_temperature": 0x1061,        # Min temperatura dla bypass
    "air_temperature_summer_free_heating": 0x1062,   # Temperatura powietrza lato FreeHeating
    "air_temperature_summer_free_cooling": 0x1063,   # Temperatura powietrza lato FreeCooling
    
    # Constant Flow control
    "constant_flow_mode": 0x1070,            # Tryb Constant Flow
    "constant_flow_supply_target": 0x1071,   # Zadany przepływ nawiewu CF
    "constant_flow_exhaust_target": 0x1072,  # Zadany przepływ wywiewu CF
    "constant_flow_tolerance": 0x1073,       # Tolerancja CF (%)
}

# Enhanced Coil Registers (Digital inputs/outputs) - HA 2025.7+ Compatible
COIL_REGISTERS = {
    # System control
    "system_on_off": 0x2000,                 # Główne włączenie/wyłączenie systemu
    "constant_flow_active": 0x2001,          # Aktywacja Constant Flow
    "gwc_active": 0x2002,                    # Aktywacja GWC
    "bypass_active": 0x2003,                 # Aktywacja Bypass
    "comfort_active": 0x2004,                # Aktywacja trybu komfortu
    
    # Enhanced features (HA 2025.7+)
    "antifreeze_mode": 0x2010,               # Tryb zabezpieczenia przed zamarzaniem
    "summer_mode": 0x2011,                   # Tryb letni
    "preheating_active": 0x2012,             # Podgrzewanie aktywne
    "cooling_active": 0x2013,                # Chłodzenie aktywne
    "night_cooling_active": 0x2014,          # Nocne chłodzenie aktywne
    
    # Maintenance and alarms
    "filter_warning": 0x2020,                # Ostrzeżenie wymiany filtra
    "service_required": 0x2021,              # Wymagany serwis
    "error_active": 0x2022,                  # Aktywny błąd
    "warning_active": 0x2023,                # Aktywne ostrzeżenie
    "maintenance_mode": 0x2024,              # Tryb serwisowy
}

# Discrete Inputs (Read-only digital status) - HA 2025.7+ Compatible
DISCRETE_INPUTS = {
    # Sensor status
    "outside_temp_sensor_ok": 0x3000,        # Status czujnika TZ1
    "supply_temp_sensor_ok": 0x3001,         # Status czujnika TN1
    "exhaust_temp_sensor_ok": 0x3002,        # Status czujnika TP
    "fpx_temp_sensor_ok": 0x3003,            # Status czujnika TZ2
    "duct_temp_sensor_ok": 0x3004,           # Status czujnika TN2
    "gwc_temp_sensor_ok": 0x3005,            # Status czujnika TZ3
    "ambient_temp_sensor_ok": 0x3006,        # Status czujnika TO
    
    # System status
    "heat_exchanger_ok": 0x3010,             # Status wymiennika ciepła
    "supply_fan_ok": 0x3011,                 # Status wentylatora nawiewu
    "exhaust_fan_ok": 0x3012,                # Status wentylatora wywiewu
    "preheater_ok": 0x3013,                  # Status podgrzewacza
    "bypass_motor_ok": 0x3014,               # Status silnika bypass
    
    # Enhanced diagnostics (HA 2025.7+)
    "communication_error": 0x3020,           # Błąd komunikacji
    "overheating_protection": 0x3021,        # Zabezpieczenie przed przegrzaniem
    "freezing_protection": 0x3022,           # Zabezpieczenie przed zamarzaniem
    "filter_clogged": 0x3023,                # Filtr zatkany
    "power_supply_ok": 0x3024,               # Status zasilania
    
    # External systems
    "gwc_pump_running": 0x3030,              # Pompa GWC w ruchu
    "external_heater_active": 0x3031,        # Zewnętrzny grzejnik aktywny
    "external_cooler_active": 0x3032,        # Zewnętrzny chłodzący aktywny
    "humidity_sensor_ok": 0x3033,            # Status czujnika wilgotności
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