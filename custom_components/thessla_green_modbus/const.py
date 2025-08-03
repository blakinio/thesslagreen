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

# Temperature sensor invalid value (according to documentation)
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
    "dp_ahu_filter_overflow": 0x0012,       # Presostat filtrów rekuperatora (DP1)
    "ahu_filter_protection": 0x0013,        # Zabezpieczenie termiczne FPX
    "empty_house": 0x0015,                  # Sygnał PUSTY DOM
}

# INPUT REGISTERS (04 - READ INPUT REGISTERS) - CORRECTED according to documentation
INPUT_REGISTERS: Final[dict[str, int]] = {
    # Firmware version
    "firmware_major": 0x0000,               # Wersja główna oprogramowania
    "firmware_minor": 0x0001,               # Wersja poboczna oprogramowania
    "day_of_week": 0x0002,                  # Bieżący dzień tygodnia
    "period": 0x0003,                       # Bieżący odcinek czasowy
    "firmware_patch": 0x0004,               # Patch wersji oprogramowania
    "compilation_days": 0x000E,             # Data kompilacji (dni od 2000-01-01)
    "compilation_seconds": 0x000F,          # Godzina kompilacji (sekundy od 00:00)
    
    # Temperature sensors (multiplier 0.1°C, 0x8000 = invalid)
    "outside_temperature": 0x0010,          # Temperatura zewnętrzna (TZ1)
    "supply_temperature": 0x0011,           # Temperatura nawiewu (TN1)
    "exhaust_temperature": 0x0012,          # Temperatura wywiewu (TP)
    "fpx_temperature": 0x0013,              # Temperatura FPX (TZ2)
    "duct_supply_temperature": 0x0014,      # Temperatura kanałowa (TN2)
    "gwc_temperature": 0x0015,              # Temperatura GWC (TZ3)
    "ambient_temperature": 0x0016,          # Temperatura otoczenia (TO)
    
    # Serial number
    "serial_number_1": 0x0018,
    "serial_number_2": 0x0019,
    "serial_number_3": 0x001A,
    "serial_number_4": 0x001B,
    "serial_number_5": 0x001C,
    "serial_number_6": 0x001D,
    
    # Constant Flow system
    "constant_flow_active": 0x010F,         # Status aktywności CF
    "supply_percentage": 0x0110,            # Intensywność nawiewu (%)
    "exhaust_percentage": 0x0111,           # Intensywność wywiewu (%)
    "supply_flowrate": 0x0112,              # Przepływ nawiewu (m³/h)
    "exhaust_flowrate": 0x0113,             # Przepływ wywiewu (m³/h)
    "min_percentage": 0x0114,               # Minimalna intensywność (%)
    "max_percentage": 0x0115,               # Maksymalna intensywność (%)
    "water_removal_active": 0x012A,         # Status procedury HEWR
    
    # Air flow values (CF system)
    "supply_air_flow": 0x0100,              # Strumień nawiewu CF
    "exhaust_air_flow": 0x0101,             # Strumień wywiewu CF
    
    # DAC outputs (voltage control 0-10V, multiplier 0.00244)
    "dac_supply": 0x0500,                   # Napięcie wentylatora nawiewnego [mV]
    "dac_exhaust": 0x0501,                  # Napięcie wentylatora wywiewnego [mV]
    "dac_heater": 0x0502,                   # Napięcie nagrzewnicy kanałowej [mV]
    "dac_cooler": 0x0503,                   # Napięcie chłodnicy kanałowej [mV]
}

# HOLDING REGISTERS (03 - READ HOLDING REGISTERS)
HOLDING_REGISTERS: Final[dict[str, int]] = {
    # Date and time
    "datetime_year_month": 0x0000,          # Rok i miesiąc [RRMM]
    "datetime_day_dow": 0x0001,             # Dzień i dzień tygodnia [DDTT]
    "datetime_hour_minute": 0x0002,         # Godzina i minuta [GGmm]
    "datetime_second_cs": 0x0003,           # Sekunda i setne części [sscc]
    
    # Lock date
    "lock_date_year": 0x0007,               # Rok blokady
    "lock_date_month": 0x0008,              # Miesiąc blokady
    "lock_date_day": 0x0009,                # Dzień blokady
    
    # Configuration
    "configuration_mode": 0x000D,           # Tryby specjalne pracy
    "access_level": 0x000F,                 # Poziom dostępu
    
    # Basic operation control
    "mode": 0x1070,                         # Tryb pracy (0=auto, 1=manual, 2=temp)
    "season_mode": 0x1071,                  # Sezon (0=lato, 1=zima)
    "air_flow_rate_manual": 0x1072,         # Intensywność - tryb manualny
    "air_flow_rate_temporary": 0x1073,      # Intensywność - tryb chwilowy
    "supply_air_temperature_manual": 0x1074, # Temperatura - tryb manualny (×0.5°C)
    "supply_air_temperature_temporary": 0x1075, # Temperatura - tryb chwilowy (×0.5°C)
    
    # Device control
    "on_off_panel_mode": 0x1123,            # ON/OFF urządzenia
    
    # Special functions
    "special_mode": 0x1080,                 # Funkcje specjalne (0-11)
    "hood_supply_coef": 0x1082,             # Intensywność OKAP nawiew (%)
    "hood_exhaust_coef": 0x1083,            # Intensywność OKAP wywiew (%)
    "fireplace_supply_coef": 0x1084,        # Różnicowanie KOMINEK (%)
    "airing_bathroom_coef": 0x1085,         # Intensywność WIETRZENIE łazienka (%)
    "airing_coef": 0x1086,                  # Intensywność WIETRZENIE pokoje (%)
    "contamination_coef": 0x1087,           # Intensywność czujnik jakości (%)
    "empty_house_coef": 0x1088,             # Intensywność PUSTY DOM (%)
    
    # AirS panel settings
    "fan_speed_1_coef": 0x1078,             # Intensywność 1 bieg (%)
    "fan_speed_2_coef": 0x1079,             # Intensywność 2 bieg (%)
    "fan_speed_3_coef": 0x107A,             # Intensywność 3 bieg (%)
    
    # GWC system
    "gwc_off": 0x10A0,                      # Dezaktywacja GWC
    "min_gwc_air_temperature": 0x10A1,      # Dolny próg GWC (×0.5°C)
    "max_gwc_air_temperature": 0x10A2,      # Górny próg GWC (×0.5°C)
    "gwc_regen": 0x10A6,                    # Typ regeneracji GWC
    "gwc_mode": 0x10A7,                     # Status GWC (read-only)
    "gwc_regen_period": 0x10A8,             # Czas regeneracji (h)
    "delta_t_gwc": 0x10AA,                  # Różnica temperatur regeneracji (×0.5°C)
    "gwc_regen_flag": 0x10AF,               # Flaga regeneracji GWC
    
    # Comfort mode
    "comfort_mode_panel": 0x10D0,           # Wybór EKO/KOMFORT
    "comfort_mode": 0x10D1,                 # Status KOMFORT (read-only)
    
    # Bypass system
    "bypass_off": 0x10E0,                   # Dezaktywacja bypass
    "min_bypass_temperature": 0x10E1,       # Minimalna temperatura bypass (×0.5°C)
    "air_temperature_summer_free_heating": 0x10E2, # Temperatura FreeHeating (×0.5°C)
    "air_temperature_summer_free_cooling": 0x10E3, # Temperatura FreeCooling (×0.5°C)
    "bypass_mode": 0x10EA,                  # Status bypass (read-only)
    "bypass_user_mode": 0x10EB,             # Sposób realizacji bypass (1-3)
    "bypass_coef1": 0x10EC,                 # Różnicowanie bypass (%)
    "bypass_coef2": 0x10ED,                 # Intensywność bypass (%)
    
    # System control
    "antifreeze_mode": 0x1060,              # Flaga uruchomienia FPX
    "antifreeze_stage": 0x1066,             # Tryb działania FPX
    "stop_ahu_code": 0x1120,                # Kod alarmu zatrzymującego
    "language": 0x112F,                     # Język panelu
    
    # Device name (8 registers ASCII)
    "device_name_1": 0x1FD0,
    "device_name_2": 0x1FD1,
    "device_name_3": 0x1FD2,
    "device_name_4": 0x1FD3,
    "device_name_5": 0x1FD4,
    "device_name_6": 0x1FD5,
    "device_name_7": 0x1FD6,
    "device_name_8": 0x1FD7,
    
    # Product key
    "lock_pass_1": 0x1FFB,                  # Klucz produktu słowo młodsze
    "lock_pass_2": 0x1FFC,                  # Klucz produktu słowo starsze
    "lock_flag": 0x1FFD,                    # Aktywacja blokady
    "required_temp": 0x1FFE,                # Temperatura zadana KOMFORT (×0.5°C)
    "filter_change": 0x1FFF,                # System kontroli filtrów
    
    # Alarm flags
    "alarm_flag": 0x2000,                   # Flaga alarmów E
    "error_flag": 0x2001,                   # Flaga błędów S
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
GWC_MODES = {
    0: "GWC nieaktywny",
    1: "Tryb zima",
    2: "Tryb lato"
}

# Bypass modes
BYPASS_MODES = {
    0: "Bypass nieaktywny",
    1: "Funkcja grzania (FreeHeating)",
    2: "Funkcja chłodzenia (FreeCooling)"
}

# Comfort modes
COMFORT_MODES = {
    0: "KOMFORT nieaktywny",
    1: "Funkcja grzania",
    2: "Funkcja chłodzenia"
}

# FPX modes
FPX_MODES = {
    0: "FPX OFF",
    1: "Tryb FPX1",
    2: "Tryb FPX2"
}
