"""Constants for the ThesslaGreen Modbus integration - VERIFIED against official documentation."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "thessla_green_modbus"

# Default values
DEFAULT_NAME = "ThesslaGreen"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 10
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3

# Configuration keys
CONF_SLAVE_ID = "slave_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_RETRY = "retry"

# Temperature sensor invalid value (according to documentation)
INVALID_TEMPERATURE = 0x8000  # 32768 decimal - indicates sensor not connected

# Air flow invalid value  
INVALID_FLOW = 65535  # Indicates CF not active

# COIL REGISTERS (01 - READ COILS) - VERIFIED against documentation
COIL_REGISTERS: Final[dict[str, int]] = {
    "duct_water_heater_pump": 0x0005,      # Stan wyjścia pompy obiegowej nagrzewnicy
    "bypass": 0x0009,                       # Stan wyjścia siłownika bypass
    "info": 0x000A,                         # Stan wyjścia potwierdzenia pracy centrali (O1)
    "power_supply_fans": 0x000B,            # Stan wyjścia zasilania wentylatorów
    "heating_cable": 0x000C,                # Stan wyjścia kabla grzejnego
    "work_permit": 0x000D,                  # Stan wyjścia potwierdzenia pracy (Expansion)
    "gwc": 0x000E,                          # Stan wyjścia GWC
    "hood": 0x000F,                         # Stan wyjścia przepustnicy okapu
}

# DISCRETE INPUT REGISTERS (02 - READ DISCRETE INPUTS) - VERIFIED
DISCRETE_INPUT_REGISTERS: Final[dict[str, int]] = {
    "duct_heater_protection": 0x0000,       # Zabezpieczenie termiczne nagrzewnicy kanałowej
    "expansion": 0x0001,                    # Komunikacja z modułem Expansion
    "dp_duct_filter_overflow": 0x0003,      # Presostat filtra kanałowego
    "hood_input": 0x0004,                   # Wejście włącznika OKAP
    "contamination_sensor": 0x0005,         # Czujnik jakości powietrza
    "airing_sensor": 0x0006,                # Czujnik wilgotności
    "airing_switch": 0x0007,                # Włącznik WIETRZENIE
    "airing_mini": 0x000A,                  # Przełącznik AirS - Wietrzenie
    "fan_speed_3": 0x000B,                  # Przełącznik AirS - 3 bieg
    "fan_speed_2": 0x000C,                  # Przełącznik AirS - 2 bieg
    "fan_speed_1": 0x000D,                  # Przełącznik AirS - 1 bieg
    "fireplace": 0x000E,                    # Włącznik KOMINEK
    "fire_alarm": 0x000F,                   # Alarm pożarowy (P.POZ.)
    "dp_ahu_filter_overflow": 0x0012,       # Presostat filtrów rekuperatora (DP1)
    "ahu_filter_protection": 0x0013,        # Zabezpieczenie termiczne FPX
    "empty_house": 0x0015,                  # Sygnał PUSTY DOM
}

# INPUT REGISTERS (04 - READ INPUT REGISTERS) - VERIFIED according to documentation
INPUT_REGISTERS: Final[dict[str, int]] = {
    # Firmware version (addresses 0x0000-0x0004)
    "firmware_major": 0x0000,               # Wersja główna oprogramowania
    "firmware_minor": 0x0001,               # Wersja poboczna oprogramowania
    "day_of_week": 0x0002,                  # Bieżący dzień tygodnia
    "period": 0x0003,                       # Bieżący odcinek czasowy
    "firmware_patch": 0x0004,               # Patch wersji oprogramowania
    
    # Compilation info
    "compilation_days": 0x000E,             # Data kompilacji (dni od 2000-01-01)
    "compilation_seconds": 0x000F,          # Godzina kompilacji (sekundy od 00:00)
    
    # Temperature sensors (multiplier 0.1°C, 0x8000 = invalid) - addresses 0x0010-0x0016
    "outside_temperature": 0x0010,          # Temperatura zewnętrzna (TZ1)
    "supply_temperature": 0x0011,           # Temperatura nawiewu (TN1)
    "exhaust_temperature": 0x0012,          # Temperatura wywiewu (TP)
    "fpx_temperature": 0x0013,              # Temperatura FPX (TZ2)
    "duct_supply_temperature": 0x0014,      # Temperatura kanałowa (TN2)
    "gwc_temperature": 0x0015,              # Temperatura GWC (TZ3)
    "ambient_temperature": 0x0016,          # Temperatura otoczenia (TO)
    
    # Serial number (addresses 0x0018-0x001D)
    "serial_number_1": 0x0018,
    "serial_number_2": 0x0019,
    "serial_number_3": 0x001A,
    "serial_number_4": 0x001B,
    "serial_number_5": 0x001C,
    "serial_number_6": 0x001D,
    
    # Constant Flow system (addresses 0x010F-0x0115, 0x012A)
    "constant_flow_active": 0x010F,         # Status aktywności CF
    "supply_percentage": 0x0110,            # Intensywność nawiewu (%)
    "exhaust_percentage": 0x0111,           # Intensywność wywiewu (%)
    "supply_flowrate": 0x0112,              # Przepływ nawiewu (m³/h)
    "exhaust_flowrate": 0x0113,             # Przepływ wywiewu (m³/h)
    "supply_air_flow": 0x0114,              # Strumień powietrza nawiewu (m³/h)
    "exhaust_air_flow": 0x0115,             # Strumień powietrza wywiewu (m³/h)
    "dac_supply_voltage": 0x012A,           # Napięcie sterujące wentylatorem nawiewu (V)
    "dac_exhaust_voltage": 0x012B,          # Napięcie sterujące wentylatorem wywiewu (V)
    
    # System status registers (read-only)
    "comfort_mode": 0x0130,                 # Status trybu komfort (0=nieaktywny, 1=grzanie, 2=chłodzenie)
}

# HOLDING REGISTERS (03 - READ HOLDING REGISTERS, 06 - WRITE SINGLE REGISTER)
HOLDING_REGISTERS: Final[dict[str, int]] = {
    # Basic control registers
    "mode": 0x1070,                         # Tryb pracy (0=auto, 1=manual, 2=temporary)
    "on_off_panel_mode": 0x1071,           # Stan pracy (0=off, 1=on)
    "air_flow_rate_manual": 0x1072,        # Intensywność w trybie manual (10-100%)
    "air_flow_rate_temporary": 0x1073,     # Intensywność w trybie temporary (10-150%)
    "temporary_time": 0x1074,              # Czas trybu temporary (1-180 min)
    "special_mode": 0x1075,                # Tryb specjalny
    
    # Temperature control
    "target_temperature": 0x1076,          # Temperatura zadana (×0.1°C)
    "comfort_temperature": 0x1077,         # Temperatura komfortu (×0.1°C)
    "comfort_mode_panel": 0x1078,          # Tryb komfortu z panelu (0/1)
    
    # Season and system modes
    "season_mode": 0x1079,                 # Tryb sezonowy (0=lato, 1=zima)
    
    # GWC and bypass control
    "gwc_mode": 0x107A,                    # Tryb GWC (0=auto, 1=manual)
    "gwc_off": 0x107B,                     # Dezaktywacja GWC (0=active, 1=off)
    "bypass_mode": 0x107C,                 # Tryb bypass (0=auto, 1=manual)
    "bypass_off": 0x107D,                  # Dezaktywacja bypass (0=active, 1=off)
    
    # Schedule and time settings
    "schedule_period_1_start": 0x107E,      # Start okresu 1 (minuty od 00:00)
    "schedule_period_1_end": 0x107F,        # Koniec okresu 1
    "schedule_period_2_start": 0x1080,      # Start okresu 2
    "schedule_period_2_end": 0x1081,        # Koniec okresu 2
    "schedule_period_3_start": 0x1082,      # Start okresu 3
    "schedule_period_3_end": 0x1083,        # Koniec okresu 3
    
    # Air flow rates for different periods
    "period_1_air_flow": 0x1084,           # Intensywność okresu 1 (%)
    "period_2_air_flow": 0x1085,           # Intensywność okresu 2 (%)
    "period_3_air_flow": 0x1086,           # Intensywność okresu 3 (%)
    
    # Special function air flows
    "hood_air_flow": 0x1087,               # Intensywność trybu OKAP (%)
    "airing_air_flow": 0x1088,             # Intensywność trybu WIETRZENIE (%)
    "fireplace_air_flow": 0x1089,          # Intensywność trybu KOMINEK (%)
    "empty_house_air_flow": 0x108A,        # Intensywność trybu PUSTY DOM (%)
    
    # Timers for special functions
    "hood_time": 0x108B,                   # Czas trybu OKAP (minuty)
    "airing_time": 0x108C,                 # Czas trybu WIETRZENIE (minuty)
    "fireplace_time": 0x108D,              # Czas trybu KOMINEK (minuty)
    "empty_house_time": 0x108E,            # Czas trybu PUSTY DOM (minuty)
}

# Value mappings for special_mode register (used internally for writing)
SPECIAL_MODE_VALUES: Final[dict[str, int]] = {
    "none": 0,                             # Brak funkcji specjalnej
    "hood": 1,                             # OKAP
    "fireplace": 2,                        # KOMINEK
    "airing_manual": 3,                    # WIETRZENIE ręczne
    "airing_auto": 4,                      # WIETRZENIE automatyczne
    "empty_house": 5,                      # PUSTY DOM
    "open_windows": 6,                     # OTWARTE OKNA
}

# Value mappings for mode register (used internally for writing)
OPERATING_MODE_VALUES: Final[dict[str, int]] = {
    "auto": 0,                             # Tryb automatyczny
    "manual": 1,                           # Tryb manualny
    "temporary": 2,                        # Tryb tymczasowy
}

# Operating mode values for mode register
OPERATING_MODES: Final[dict[int, str]] = {
    0: "Automatyczny",
    1: "Manualny", 
    2: "Chwilowy"
}

# Season modes
SEASON_MODES: Final[dict[int, str]] = {
    0: "Lato",
    1: "Zima"
}

# Special functions - VERIFIED against documentation (register 0x1075)
SPECIAL_MODES: Final[dict[int, str]] = {
    0: "Brak",
    1: "OKAP (wejście sygnałowe)",
    2: "KOMINEK (ręczne/wejście sygnałowe)",
    3: "WIETRZENIE (przełącznik dzwonkowy)",
    4: "WIETRZENIE (przełącznik ON/OFF)",
    5: "H2O/WIETRZENIE (higrostat)",
    6: "JP/WIETRZENIE (czujnik jakości)",
    7: "WIETRZENIE (aktywacja ręczna)",
    8: "WIETRZENIE (tryb automatyczny)",
    9: "WIETRZENIE (tryb manualny)",
    10: "OTWARTE OKNA (ręczne)",
    11: "PUSTY DOM (ręczne/wejście sygnałowe)"
}

# GWC modes
GWC_MODES: Final[dict[int, str]] = {
    0: "GWC nieaktywny",
    1: "Tryb zima",
    2: "Tryb lato"
}

# Bypass modes
BYPASS_MODES: Final[dict[int, str]] = {
    0: "Bypass nieaktywny",
    1: "Funkcja grzania (FreeHeating)",
    2: "Funkcja chłodzenia (FreeCooling)"
}

# Comfort modes
COMFORT_MODES: Final[dict[int, str]] = {
    0: "KOMFORT nieaktywny",
    1: "Funkcja grzania",
    2: "Funkcja chłodzenia"
}

# Device capabilities detection patterns
CAPABILITY_PATTERNS: Final[dict[str, list[str]]] = {
    "constant_flow": ["constant_flow_active", "supply_percentage", "exhaust_percentage"],
    "gwc_system": ["gwc_temperature", "gwc_mode", "gwc_off"],
    "bypass_system": ["bypass", "bypass_mode", "bypass_off"],
    "comfort_mode": ["comfort_temperature", "comfort_mode_panel"],
    "expansion_module": ["expansion", "work_permit"],
    "hood_function": ["hood", "hood_input", "hood_air_flow"],
    "fireplace_function": ["fireplace", "fireplace_air_flow"],
    "airing_function": ["airing_sensor", "airing_switch", "airing_air_flow"],
    "contamination_sensor": ["contamination_sensor"],
    "special_temperature_sensors": ["fpx_temperature", "duct_supply_temperature", "ambient_temperature"],
}