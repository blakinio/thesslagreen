"""Constants for the ThesslaGreen Modbus integration."""
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

# Temperature sensor invalid value
INVALID_TEMPERATURE = 0x8000  # 32768 decimal - indicates sensor not connected

# Air flow invalid value  
INVALID_FLOW = 65535  # Indicates CF not active

# COIL REGISTERS (01 - READ COILS)
COIL_REGISTERS: Final[dict[str, int]] = {
    "duct_water_heater_pump": 0x0005,      # Stan wyjścia pompy obiegowej nagrzewnicy
    "bypass": 0x0009,                       # Stan wyjścia siłownika bypass
    "info": 0x000A,                         # Stan wyjścia potwierdzenia pracy (O1)
    "power_supply_fans": 0x000B,            # Stan wyjścia zasilania wentylatorów
    "heating_cable": 0x000C,                # Stan wyjścia kabla grzejnego
    "work_permit": 0x000D,                  # Stan wyjścia potwierdzenia pracy (Expansion)
    "gwc": 0x000E,                          # Stan wyjścia GWC
    "hood": 0x000F,                         # Stan wyjścia przepustnicy okapu
}

# DISCRETE INPUT REGISTERS (02 - READ DISCRETE INPUTS)
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
    "empty_house": 0x0010,                  # Włącznik PUSTY DOM
    "dp_ahu_filter_overflow": 0x0011,       # Presostat filtra centrali
    "ahu_filter_protection": 0x0012,        # Zabezpieczenie termiczne nagrzewnicy centrali
}

# INPUT REGISTERS (04 - READ INPUT REGISTERS)
INPUT_REGISTERS: Final[dict[str, int]] = {
    # Firmware version
    "firmware_major": 0x0000,               # Wersja firmware - major
    "firmware_minor": 0x0001,               # Wersja firmware - minor
    "firmware_type": 0x0002,                # Typ firmware (1=release, 2=beta)
    "firmware_patch": 0x0004,               # Wersja firmware - patch
    
    # Device identification
    "device_id_1": 0x0008,                  # Identyfikator urządzenia część 1
    "device_id_2": 0x0009,                  # Identyfikator urządzenia część 2
    "device_id_3": 0x000A,                  # Identyfikator urządzenia część 3
    "device_id_4": 0x000B,                  # Identyfikator urządzenia część 4
    
    # Serial number
    "serial_number_1": 0x0018,              # Numer seryjny część 1
    "serial_number_2": 0x0019,              # Numer seryjny część 2
    "serial_number_3": 0x001A,              # Numer seryjny część 3
    "serial_number_4": 0x001B,              # Numer seryjny część 4
    "serial_number_5": 0x001C,              # Numer seryjny część 5
    "serial_number_6": 0x001D,              # Numer seryjny część 6
    
    # Temperature sensors
    "outside_temperature": 0x0010,          # Temperatura zewnętrzna (TZ1)
    "supply_temperature": 0x0011,           # Temperatura powietrza nawiewanego (TN1)
    "exhaust_temperature": 0x0012,          # Temperatura powietrza wywiewanego (TP)
    "fpx_temperature": 0x0013,              # Temperatura FPX (TZ2)
    "ambient_temperature": 0x0014,          # Temperatura otoczenia (TO)
    "duct_temperature": 0x0015,             # Temperatura kanałowa (TN2)
    "gwc_temperature": 0x0016,              # Temperatura GWC (TZ3)
    
    # Air flow measurements
    "supply_air_flow": 0x0020,              # Strumień nawiewu [m³/h]
    "exhaust_air_flow": 0x0021,             # Strumień wywiewu [m³/h]
    "supply_percentage": 0x0022,            # Intensywność nawiewu [%]
    "exhaust_percentage": 0x0023,           # Intensywność wywiewu [%]
    "min_percentage": 0x0024,               # Minimalna intensywność [%]
    "max_percentage": 0x0025,               # Maksymalna intensywność [%]
    
    # Constant Flow system status
    "constant_flow_active": 0x0030,         # Status Constant Flow (0=nieaktywny, 1=aktywny)
    "water_removal_active": 0x0031,         # Status HEWR (0=nieaktywny, 1=aktywny)
    
    # DAC outputs (0-10V)
    "dac_supply": 0x0040,                   # Napięcie wentylatora nawiewnego [mV]
    "dac_exhaust": 0x0041,                  # Napięcie wentylatora wywiewnego [mV]
    "dac_heater": 0x0042,                   # Napięcie nagrzewnicy [mV]
    "dac_cooler": 0x0043,                   # Napięcie chłodnicy [mV]
    
    # Alarms - Type S (critical errors that stop operation)
    "s01_product_key": 0x2001,              # S01: Brak klucza produktu
    "s02_fpx_no_function": 0x2002,          # S02: FPX bez funkcji
    "s03_fpx_overheating": 0x2003,          # S03: Przegrzanie FPX
    "s04_fpx_underheating": 0x2004,         # S04: Niedogrzanie FPX
    "s05_supply_air_sensor": 0x2005,        # S05: Uszkodzony czujnik nawiewu
    "s06_exhaust_air_sensor": 0x2006,       # S06: Uszkodzony czujnik wywiewu
    "s07_water_heater_sensor": 0x2007,      # S07: Uszkodzony czujnik nagrzewnicy wodnej
    "s08_fpx_sensor": 0x2008,               # S08: Uszkodzony czujnik FPX
    "s09_ambient_sensor": 0x2009,           # S09: Uszkodzony czujnik otoczenia
    "s10_fpx_heater_damaged": 0x200A,       # S10: Uszkodzona nagrzewnica FPX
    "s11_fpx_heater_protection": 0x200B,    # S11: Zabezpieczenie termiczne FPX
    "s12_fpx_with_heater_protection": 0x200C, # S12: Zabezpieczenie termiczne FPX z nagrzewnicą
    "s13_duct_sensor_damaged": 0x200D,      # S13: Uszkodzony czujnik kanałowy
    "s25_outside_sensor_damaged": 0x2019,   # S25: Uszkodzony czujnik zewnętrzny
    "s26_gwc_sensor_damaged": 0x201A,       # S26: Uszkodzony czujnik GWC
    "s29_high_temperature": 0x201D,         # S29: Wysoka temperatura
    "s30_supply_fan_failure": 0x201E,       # S30: Awaria wentylatora nawiewnego
    "s31_exhaust_fan_failure": 0x201F,      # S31: Awaria wentylatora wywiewnego
    "s32_tg02_communication": 0x2020,       # S32: Komunikacja z TG-02
    
    # Alarms - Type E (warnings)
    "e99_product_key_warning": 0x2063,      # E99: Ostrzeżenie klucz produktu
    "e100_outside_temp_sensor": 0x2064,     # E100: Czujnik temperatury zewnętrznej
    "e101_supply_temp_sensor": 0x2065,      # E101: Czujnik temperatury nawiewu
    "e102_exhaust_temp_sensor": 0x2066,     # E102: Czujnik temperatury wywiewu
    "e103_fpx_temp_sensor": 0x2067,         # E103: Czujnik temperatury FPX
    "e104_ambient_temp_sensor": 0x2068,     # E104: Czujnik temperatury otoczenia
    "e105_duct_temp_sensor": 0x2069,        # E105: Czujnik temperatury kanałowy
    "e106_gwc_temp_sensor": 0x206A,         # E106: Czujnik temperatury GWC
    "e138_cf_supply_sensor": 0x208A,        # E138: Czujnik CF nawiewu
    "e139_cf_exhaust_sensor": 0x208B,       # E139: Czujnik CF wywiewu
    "e152_high_exhaust_temp": 0x2098,       # E152: Wysoka temperatura wywiewu
    "e196_regulation_not_done": 0x20C6,     # E196: Regulacja nie wykonana
    "e197_regulation_interrupted": 0x20C7,  # E197: Regulacja przerwana
    "e198_cf2_communication": 0x20C8,       # E198: Komunikacja CF2
    "e199_cf_communication": 0x20C9,        # E199: Komunikacja CF
    "e200_electric_heater_ahu": 0x20CA,     # E200: Nagrzewnica elektryczna centrali
    "e201_electric_heater_duct": 0x20CB,    # E201: Nagrzewnica elektryczna kanałowa
    "e249_expansion_communication": 0x20F9, # E249: Komunikacja Expansion
    "e250_filter_change_no_pres": 0x20FA,   # E250: Wymiana filtrów (bez presostatu)
    "e251_duct_filter_change": 0x20FB,      # E251: Wymiana filtra kanałowego
    "e252_filter_change_pres": 0x20FC,      # E252: Wymiana filtrów (presostat)
}

# HOLDING REGISTERS (03 - READ HOLDING REGISTERS)
HOLDING_REGISTERS: Final[dict[str, int]] = {
    # Basic control
    "on_off_panel_mode": 0x1000,            # Tryb panelu ON/OFF
    "mode": 0x1070,                         # Tryb pracy (0=auto, 1=manual, 2=temp)
    "season_mode": 0x1071,                  # Sezon (0=lato, 1=zima)
    "special_mode": 0x1072,                 # Funkcja specjalna
    
    # Manual control
    "air_flow_rate_manual": 0x1073,         # Intensywność w trybie manualnym [%]
    "supply_air_temperature_manual": 0x1074, # Temperatura nawiewu manualny [0.5°C]
    
    # Temporary control
    "air_flow_rate_temporary": 0x1075,      # Intensywność w trybie chwilowym [%]
    "supply_air_temperature_temporary": 0x1076, # Temperatura nawiewu chwilowy [0.5°C]
    "temporary_mode_time": 0x1077,          # Czas trybu chwilowego [min]
    
    # Comfort mode
    "comfort_mode_panel": 0x1078,           # Panel trybu KOMFORT
    "comfort_mode": 0x1079,                 # Tryb KOMFORT (read-only)
    
    # Special function coefficients
    "hood_supply_coef": 0x1080,             # Współczynnik OKAP nawiew [%]
    "hood_exhaust_coef": 0x1081,            # Współczynnik OKAP wywiew [%]
    "fireplace_supply_coef": 0x1082,        # Różnicowanie KOMINEK [%]
    "airing_coef": 0x1083,                  # Współczynnik WIETRZENIE [%]
    "contamination_coef": 0x1084,           # Współczynnik czujnik jakości [%]
    "empty_house_coef": 0x1085,             # Współczynnik PUSTY DOM [%]
    
    # AirS panel configuration
    "fan_speed_1_coef": 0x1090,             # AirS 1 bieg [%]
    "fan_speed_2_coef": 0x1091,             # AirS 2 bieg [%]
    "fan_speed_3_coef": 0x1092,             # AirS 3 bieg [%]
    
    # GWC system
    "gwc_mode": 0x10A0,                     # Tryb GWC (read-only)
    "gwc_off": 0x10A1,                      # Dezaktywacja GWC (0=aktywny, 1=nieaktywny)
    "gwc_regen_mode": 0x10A2,               # Tryb regeneracji GWC
    "gwc_winter_threshold": 0x10A3,         # Próg zimowy GWC [0.5°C]
    "gwc_summer_threshold": 0x10A4,         # Próg letni GWC [0.5°C]
    
    # Bypass system
    "bypass_mode": 0x10B0,                  # Tryb Bypass (read-only)
    "bypass_off": 0x10B1,                   # Dezaktywacja Bypass (0=aktywny, 1=nieaktywny)
    "bypass_threshold_temp": 0x10B2,        # Próg temperatury Bypass [0.5°C]
    "bypass_threshold_diff": 0x10B3,        # Próg różnicy Bypass [0.5°C]
    
    # Device name (8 registers = 16 characters)
    "device_name_1": 0x1FD0,                # Nazwa urządzenia część 1
    "device_name_2": 0x1FD1,                # Nazwa urządzenia część 2
    "device_name_3": 0x1FD2,                # Nazwa urządzenia część 3
    "device_name_4": 0x1FD3,                # Nazwa urządzenia część 4
    "device_name_5": 0x1FD4,                # Nazwa urządzenia część 5
    "device_name_6": 0x1FD5,                # Nazwa urządzenia część 6
    "device_name_7": 0x1FD6,                # Nazwa urządzenia część 7
    "device_name_8": 0x1FD7,                # Nazwa urządzenia część 8
}

# Operating modes
OPERATING_MODES = {
    0: "Automatyczny",
    1: "Manualny", 
    2: "Chwilowy"
}

# Season modes
SEASON_MODES = {
    0: "Lato",
    1: "Zima"
}

# Special functions
SPECIAL_MODES = {
    0: "Brak",
    1: "OKAP (wejście sygnałowe)",
    2: "KOMINEK (ręczne/wejście sygnałowe)",
    3: "WIETRZENIE (przełącznik dzwonkowy)",
    4: "CZUJNIK JAKOŚCI (automatyczny)",
    5: "PUSTY DOM (przełącznik dzwonkowy)",
}

# GWC modes (read-only)
GWC_MODES = {
    0: "Nieaktywny",
    1: "Zima",
    2: "Lato",
    3: "Regeneracja"
}

# Bypass modes (read-only)
BYPASS_MODES = {
    0: "Nieaktywny",
    1: "FreeHeating",
    2: "FreeCooling"
}

# Comfort modes (read-only)
COMFORT_MODES = {
    0: "Nieaktywny",
    1: "Aktywny"
}