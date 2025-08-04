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
    "min_percentage": 0x0114,               # Minimalna intensywność (%)
    "max_percentage": 0x0115,               # Maksymalna intensywność (%)
    "water_removal_active": 0x012A,         # Status procedury HEWR
    
    # Air flow values (CF system) - addresses 0x0100-0x0101
    "supply_air_flow": 0x0100,              # Strumień nawiewu CF
    "exhaust_air_flow": 0x0101,             # Strumień wywiewu CF
    
    # DAC outputs (voltage control 0-10V, multiplier 0.00244) - addresses 0x0500-0x0503
    "dac_supply": 0x0500,                   # Napięcie wentylatora nawiewnego [mV]
    "dac_exhaust": 0x0501,                  # Napięcie wentylatora wywiewnego [mV]
    "dac_heater": 0x0502,                   # Napięcie nagrzewnicy kanałowej [mV]
    "dac_cooler": 0x0503,                   # Napięcie chłodnicy kanałowej [mV]
}

# HOLDING REGISTERS (03 - READ HOLDING REGISTERS) - VERIFIED against documentation
HOLDING_REGISTERS: Final[dict[str, int]] = {
    # Date and time (addresses 0x0000-0x0003)
    "datetime_year_month": 0x0000,          # Rok i miesiąc [RRMM]
    "datetime_day_dow": 0x0001,             # Dzień i dzień tygodnia [DDTT]
    "datetime_hour_minute": 0x0002,         # Godzina i minuta [GGmm]
    "datetime_second_cs": 0x0003,           # Sekunda i setne części [sscc]
    
    # Lock date (addresses 0x0007-0x0009)
    "lock_date_year": 0x0007,               # Rok blokady
    "lock_date_month": 0x0008,              # Miesiąc blokady
    "lock_date_day": 0x0009,                # Dzień blokady
    
    # Configuration (addresses 0x000D, 0x000F)
    "configuration_mode": 0x000D,           # Tryby specjalne pracy
    "access_level": 0x000F,                 # Poziom dostępu
    
    # Summer schedule (addresses 0x0010-0x002B) - time start registers
    # Winter schedule (addresses 0x002C-0x0047) - time start registers
    # Summer settings (addresses 0x0048-0x0063) - airflow & temperature [AATT]
    # Winter settings (addresses 0x0064-0x007F) - airflow & temperature [AATT]
    # Airing schedule summer (addresses 0x0080-0x0098)
    # Airing schedule winter (addresses 0x009C-0x00B4)
    
    # RTC calibration (address 0x00C0)
    "rtc_cal": 0x00C0,                      # Dane kalibracyjne zegara
    
    # Module versions (addresses 0x00F0-0x00F1)
    "cf_version": 0x00F0,                   # Wersja oprogramowania modułu CF/TG-02
    "exp_version": 0x00F1,                  # Wersja oprogramowania modułu Expansion
    
    # Air flow readings (addresses 0x0100-0x0101)
    "supply_air_flow_value": 0x0100,        # Wartość chwilowa strumienia - nawiew
    "exhaust_air_flow_value": 0x0101,       # Wartość chwilowa strumienia - wywiew
    
    # Flow rate limits (addresses 0x1015-0x1018)
    "max_supply_air_flow_rate": 0x1015,     # Maksymalna intensywność nawieu
    "max_supply_air_flow_rate_gwc": 0x1016, # Maksymalna intensywność nawiewu GWC
    "max_exhaust_air_flow_rate": 0x1017,    # Maksymalna intensywność wywiewu
    "max_exhaust_air_flow_rate_gwc": 0x1018, # Maksymalna intensywność wywiewu GWC
    
    # System status (addresses 0x1060, 0x1066)
    "antifreeze_mode": 0x1060,              # Flaga uruchomienia FPX
    "antifreeze_stage": 0x1066,             # Tryb działania FPX
    
    # MAIN OPERATING PARAMETERS (addresses 0x1070-0x1075) - CRITICAL
    "mode": 0x1070,                         # Tryb pracy (0=auto, 1=manual, 2=temp)
    "season_mode": 0x1071,                  # Sezon (0=lato, 1=zima)
    "air_flow_rate_manual": 0x1072,         # Intensywność - tryb manualny
    "air_flow_rate_temporary": 0x1073,      # Intensywność - tryb chwilowy
    "supply_air_temperature_manual": 0x1074, # Temperatura - tryb manualny (×0.5°C)
    "supply_air_temperature_temporary": 0x1075, # Temperatura - tryb chwilowy (×0.5°C)
    
    # AirS panel settings (addresses 0x1078-0x107B)
    "fan_speed_1_coef": 0x1078,             # Intensywność 1 bieg (%)
    "fan_speed_2_coef": 0x1079,             # Intensywność 2 bieg (%)
    "fan_speed_3_coef": 0x107A,             # Intensywność 3 bieg (%)
    "manual_airing_time_to_start": 0x107B,  # Godzina rozpoczęcia wietrzenia manualnego [GGMM]
    
    # Special functions (addresses 0x1080-0x1089)
    "special_mode": 0x1080,                 # Funkcje specjalne (0-11)
    "hood_supply_coef": 0x1082,             # Intensywność OKAP nawiew (%)
    "hood_exhaust_coef": 0x1083,            # Intensywność OKAP wywiew (%)
    "fireplace_supply_coef": 0x1084,        # Różnicowanie KOMINEK (%)
    "airing_bathroom_coef": 0x1085,         # Intensywność WIETRZENIE łazienka (%)
    "airing_coef": 0x1086,                  # Intensywność WIETRZENIE pokoje (%)
    "contamination_coef": 0x1087,           # Intensywność czujnik jakości (%)
    "empty_house_coef": 0x1088,             # Intensywność PUSTY DOM (%)
    "airing_panel_mode_time": 0x1089,       # Czas działania WIETRZENIE pokoje (min)
    
    # More special function timers (addresses 0x108A-0x108F)
    "airing_switch_mode_time": 0x108A,      # Czas WIETRZENIE łazienka dzwonkowy (min)
    "airing_switch_mode_on_delay": 0x108B,  # Opóźnienie załączenia WIETRZENIE (min)
    "airing_switch_mode_off_delay": 0x108C, # Opóźnienie wyłączenia WIETRZENIE (min)
    "fireplace_mode_time": 0x108D,          # Czas działania KOMINEK (min)
    "airing_switch_coef": 0x108E,           # Intensywność WIETRZENIE przełączniki (%)
    "open_window_coef": 0x108F,             # Intensywność OTWARTE OKNA (%)
    
    # Filter check settings (addresses 0x1094-0x1095)
    "pres_check_day": 0x1094,               # Dzień kontroli filtrów
    "pres_check_time": 0x1095,              # Godzina kontroli filtrów [GGMM]
    
    # GWC system (addresses 0x10A0-0x10AF)
    "gwc_off": 0x10A0,                      # Dezaktywacja GWC
    "min_gwc_air_temperature": 0x10A1,      # Dolny próg GWC (×0.5°C)
    "max_gwc_air_temperature": 0x10A2,      # Górny próg GWC (×0.5°C)
    "gwc_regen": 0x10A6,                    # Typ regeneracji GWC
    "gwc_mode": 0x10A7,                     # Status GWC (read-only)
    "gwc_regen_period": 0x10A8,             # Czas regeneracji (h)
    "delta_t_gwc": 0x10AA,                  # Różnica temperatur regeneracji (×0.5°C)
    "start_gwc_regen_winter_time": 0x10AB,  # Start regeneracji zima [GGMM]
    "stop_gwc_regen_winter_time": 0x10AC,   # Stop regeneracji zima [GGMM]
    "start_gwc_regen_summer_time": 0x10AD,  # Start regeneracji lato [GGMM]
    "stop_gwc_regen_summer_time": 0x10AE,   # Stop regeneracji lato [GGMM]
    "gwc_regen_flag": 0x10AF,               # Flaga regeneracji GWC (read-only)
    
    # Comfort mode (addresses 0x10D0-0x10D1)
    "comfort_mode_panel": 0x10D0,           # Wybór EKO/KOMFORT
    "comfort_mode": 0x10D1,                 # Status KOMFORT (read-only)
    
    # Bypass system (addresses 0x10E0-0x10ED)
    "bypass_off": 0x10E0,                   # Dezaktywacja bypass
    "min_bypass_temperature": 0x10E1,       # Minimalna temperatura bypass (×0.5°C)
    "air_temperature_summer_free_heating": 0x10E2, # Temperatura FreeHeating (×0.5°C)
    "air_temperature_summer_free_cooling": 0x10E3, # Temperatura FreeCooling (×0.5°C)
    "bypass_mode": 0x10EA,                  # Status bypass (read-only)
    "bypass_user_mode": 0x10EB,             # Sposób realizacji bypass (1-3)
    "bypass_coef1": 0x10EC,                 # Różnicowanie bypass (%)
    "bypass_coef2": 0x10ED,                 # Intensywność bypass (%)
    
    # Nominal flows (addresses 0x1102-0x1105)
    "nominal_supply_air_flow": 0x1102,      # Nominalny strumień nawiewu
    "nominal_exhaust_air_flow": 0x1103,     # Nominalny strumień wywiewu
    "nominal_supply_air_flow_gwc": 0x1104,  # Nominalny strumień nawiewu GWC
    "nominal_exhaust_air_flow_gwc": 0x1105, # Nominalny strumień wywiewu GWC
    
    # System control (addresses 0x1120, 0x1123, 0x112F)
    "stop_ahu_code": 0x1120,                # Kod alarmu zatrzymującego
    "on_off_panel_mode": 0x1123,            # ON/OFF urządzenia - CRITICAL REGISTER
    "language": 0x112F,                     # Język panelu
    
    # Alternative control registers (addresses 0x1130-0x1135)
    "cfg_mode1": 0x1130,                    # Tryb pracy - alternatywny
    "air_flow_rate_temporary_alt": 0x1131,  # Intensywność chwilowy - alternatywny
    "airflow_rate_change_flag": 0x1132,     # Flaga zmiany intensywności
    "cfg_mode2": 0x1133,                    # Tryb pracy - alternatywny 2
    "supply_air_temperature_temporary_alt": 0x1134, # Temperatura chwilowy - alternatywny
    "temperature_change_flag": 0x1135,      # Flaga zmiany temperatury
    
    # System reset (addresses 0x113D-0x113E)
    "hard_reset_settings": 0x113D,          # Reset ustawień użytkownika
    "hard_reset_schedule": 0x113E,          # Reset harmonogramów
    
    # Duplicate filter check (addresses 0x1150-0x1151)
    "pres_check_day_alt": 0x1150,           # Dzień kontroli filtrów - alternatywny
    "pres_check_time_alt": 0x1151,          # Godzina kontroli filtrów - alternatywny
    
    # Modbus communication settings (addresses 0x1164-0x116B)
    "uart0_id": 0x1164,                     # Modbus ID port Air-B
    "uart0_baud": 0x1165,                   # Modbus baud port Air-B
    "uart0_parity": 0x1166,                 # Modbus parity port Air-B
    "uart0_stop": 0x1167,                   # Modbus stop bits port Air-B
    "uart1_id": 0x1168,                     # Modbus ID port Air++
    "uart1_baud": 0x1169,                   # Modbus baud port Air++
    "uart1_parity": 0x116A,                 # Modbus parity port Air++
    "uart1_stop": 0x116B,                   # Modbus stop bits port Air++
    
    # Device name (addresses 0x1FD0-0x1FD7) - 8 registers ASCII
    "device_name_1": 0x1FD0,
    "device_name_2": 0x1FD1,
    "device_name_3": 0x1FD2,
    "device_name_4": 0x1FD3,
    "device_name_5": 0x1FD4,
    "device_name_6": 0x1FD5,
    "device_name_7": 0x1FD6,
    "device_name_8": 0x1FD7,
    
    # Product key and system (addresses 0x1FFB-0x1FFF)
    "lock_pass_1": 0x1FFB,                  # Klucz produktu słowo młodsze
    "lock_pass_2": 0x1FFC,                  # Klucz produktu słowo starsze
    "lock_flag": 0x1FFD,                    # Aktywacja blokady
    "required_temp": 0x1FFE,                # Temperatura zadana KOMFORT (×0.5°C)
    "filter_change": 0x1FFF,                # System kontroli filtrów
    
    # Alarm flags (addresses 0x2000-0x2001)
    "alarm_flag": 0x2000,                   # Flaga alarmów E
    "error_flag": 0x2001,                   # Flaga błędów S
    
    # Individual alarm registers (addresses 0x2002+) - selected important ones
    "s2_i2c_error": 0x2002,                 # S2: Błąd komunikacji I2C
    "s6_fpx_protection": 0x2006,            # S6: Zabezpieczenie FPX
    "s7_calibration_error": 0x2007,         # S7: Błąd kalibracji
    "s8_product_key": 0x2008,               # S8: Klucz produktu
    "s9_airs_stop": 0x2009,                 # S9: Zatrzymanie z AirS
    "s10_fire_alarm": 0x200A,               # S10: Alarm pożarowy
    "s13_panel_stop": 0x200D,               # S13: Zatrzymanie z panelu
    "s17_filter_change": 0x2011,            # S17: Wymiana filtrów (presostat)
    "s19_filter_change_timer": 0x2013,      # S19: Wymiana filtrów (timer)
    "s20_duct_filter": 0x2014,              # S20: Filtr kanałowy
    "e99_product_key_warning": 0x2063,      # E99: Ostrzeżenie klucz produktu
    "e100_temp_outside": 0x2064,            # E100: Czujnik TZ1
    "e101_temp_supply": 0x2065,             # E101: Czujnik TN1
    "e102_temp_exhaust": 0x2066,            # E102: Czujnik TP
    "e103_temp_fpx": 0x2067,                # E103: Czujnik TZ2
    "e250_filter_timer": 0x20FA,            # E250: Wymiana filtrów timer
    "e251_duct_filter_timer": 0x20FB,       # E251: Filtr kanałowy timer
    "e252_filter_presostat": 0x20FC,        # E252: Wymiana filtrów presostat
}

# Operating modes - VERIFIED against documentation
OPERATING_MODES = {
    0: "Automatyczny",
    1: "Manualny", 
    2: "Chwilowy"
}

# Season modes - VERIFIED
SEASON_MODES = {
    0: "Lato",
    1: "Zima"
}

# Special functions - VERIFIED against documentation (register 0x1080)
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

# GWC modes - VERIFIED (register 0x10A7)
GWC_MODES = {
    0: "GWC nieaktywny",
    1: "Tryb zima",
    2: "Tryb lato"
}

# Bypass modes - VERIFIED (register 0x10EA)
BYPASS_MODES = {
    0: "Bypass nieaktywny",
    1: "Funkcja grzania (FreeHeating)",
    2: "Funkcja chłodzenia (FreeCooling)"
}

# Comfort modes - VERIFIED (register 0x10D1)
COMFORT_MODES = {
    0: "KOMFORT nieaktywny",
    1: "Funkcja grzania",
    2: "Funkcja chłodzenia"
}

# FPX modes - VERIFIED (register 0x1066)
FPX_MODES = {
    0: "FPX OFF",
    1: "Tryb FPX1",
    2: "Tryb FPX2"
}