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
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_RETRY = "retry"

# Modbus function codes
FUNCTION_READ_COILS = 1
FUNCTION_READ_DISCRETE_INPUTS = 2
FUNCTION_READ_HOLDING_REGISTERS = 3
FUNCTION_READ_INPUT_REGISTERS = 4

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

# INPUT REGISTERS (04 - READ INPUT REGISTER)
INPUT_REGISTERS: Final[dict[str, int]] = {
    # Wersja firmware
    "firmware_major": 0x0000,               # Wersja główna oprogramowania
    "firmware_minor": 0x0001,               # Wersja poboczna oprogramowania
    "day_of_week": 0x0002,                  # Bieżący dzień tygodnia
    "period": 0x0003,                       # Bieżący odcinek czasowy
    "firmware_patch": 0x0004,               # Patch wersji oprogramowania
    "compilation_days": 0x000E,             # Data kompilacji (dni od 2000-01-01)
    "compilation_seconds": 0x000F,          # Godzina kompilacji (sekundy od 00:00)
    
    # Temperatury (x0.1°C, 0x8000 = brak odczytu)
    "outside_temperature": 0x0010,          # Temperatura zewnętrzna (TZ1)
    "supply_temperature": 0x0011,           # Temperatura nawiewu (TN1)
    "exhaust_temperature": 0x0012,          # Temperatura wywiewu (TP)
    "fpx_temperature": 0x0013,              # Temperatura za nagrzewnicą FPX (TZ2)
    "duct_supply_temperature": 0x0014,      # Temperatura za nagrzewnicą kanałową (TN2)
    "gwc_temperature": 0x0015,              # Temperatura GWC (TZ3)
    "ambient_temperature": 0x0016,          # Temperatura otoczenia (TO)
    
    # Numer seryjny
    "serial_number_1": 0x0018,
    "serial_number_2": 0x0019,
    "serial_number_3": 0x001A,
    "serial_number_4": 0x001B,
    "serial_number_5": 0x001C,
    "serial_number_6": 0x001D,
    
    # System Constant Flow
    "constant_flow_active": 0x010F,         # Status aktywności CF
    "supply_percentage": 0x0110,            # Intensywność nawiewu (%)
    "exhaust_percentage": 0x0111,           # Intensywność wywiewu (%)
    "supply_flowrate": 0x0112,              # Przepływ nawiewu (m³/h)
    "exhaust_flowrate": 0x0113,             # Przepływ wywiewu (m³/h)
    "min_percentage": 0x0114,               # Minimalna intensywność (%)
    "max_percentage": 0x0115,               # Maksymalna intensywność (%)
    "water_removal_active": 0x012A,         # Status procedury HEWR
    
    # Wartości przepływu
    "supply_air_flow": 0x0100,              # Strumień nawiewu CF
    "exhaust_air_flow": 0x0101,             # Strumień wywiewu CF
    
    # Sygnały sterujące (DAC)
    "dac_supply": 0x0500,                   # Napięcie wentylatora nawiewnego (V)
    "dac_exhaust": 0x0501,                  # Napięcie wentylatora wywiewnego (V)
    "dac_heater": 0x0502,                   # Napięcie nagrzewnicy kanałowej (V)
    "dac_cooler": 0x0503,                   # Napięcie chłodnicy kanałowej (V)
}

# HOLDING REGISTERS (03 - READ HOLDING REGISTER)
HOLDING_REGISTERS: Final[dict[str, int]] = {
    # Data i czas
    "datetime_year_month": 0x0000,          # Rok i miesiąc [RRMM]
    "datetime_day_dow": 0x0001,             # Dzień i dzień tygodnia [DDTT]
    "datetime_hour_minute": 0x0002,         # Godzina i minuta [GGmm]
    "datetime_second_cs": 0x0003,           # Sekunda i setne części [sscc]
    
    # Data blokady
    "lock_date_year": 0x0007,               # Rok blokady
    "lock_date_month": 0x0008,              # Miesiąc blokady
    "lock_date_day": 0x0009,                # Dzień blokady
    
    # Konfiguracja
    "configuration_mode": 0x000D,           # Tryby specjalne pracy
    "access_level": 0x000F,                 # Poziom dostępu
    
    # Harmonogram LATO (Poniedziałek-Niedziela, 4 odcinki czasowe)
    "summer_mon_1_time": 0x0010,            # LATO - Poniedziałek - odcinek 1 [GGMM]
    "summer_mon_2_time": 0x0011,            # LATO - Poniedziałek - odcinek 2 [GGMM]
    "summer_mon_3_time": 0x0012,            # LATO - Poniedziałek - odcinek 3 [GGMM]
    "summer_mon_4_time": 0x0013,            # LATO - Poniedziałek - odcinek 4 [GGMM]
    "summer_tue_1_time": 0x0014,
    "summer_tue_2_time": 0x0015,
    "summer_tue_3_time": 0x0016,
    "summer_tue_4_time": 0x0017,
    "summer_wed_1_time": 0x0018,
    "summer_wed_2_time": 0x0019,
    "summer_wed_3_time": 0x001A,
    "summer_wed_4_time": 0x001B,
    "summer_thu_1_time": 0x001C,
    "summer_thu_2_time": 0x001D,
    "summer_thu_3_time": 0x001E,
    "summer_thu_4_time": 0x001F,
    "summer_fri_1_time": 0x0020,
    "summer_fri_2_time": 0x0021,
    "summer_fri_3_time": 0x0022,
    "summer_fri_4_time": 0x0023,
    "summer_sat_1_time": 0x0024,
    "summer_sat_2_time": 0x0025,
    "summer_sat_3_time": 0x0026,
    "summer_sat_4_time": 0x0027,
    "summer_sun_1_time": 0x0028,
    "summer_sun_2_time": 0x0029,
    "summer_sun_3_time": 0x002A,
    "summer_sun_4_time": 0x002B,
    
    # Harmonogram ZIMA
    "winter_mon_1_time": 0x002C,
    "winter_mon_2_time": 0x002D,
    "winter_mon_3_time": 0x002E,
    "winter_mon_4_time": 0x002F,
    "winter_tue_1_time": 0x0030,
    "winter_tue_2_time": 0x0031,
    "winter_tue_3_time": 0x0032,
    "winter_tue_4_time": 0x0033,
    "winter_wed_1_time": 0x0034,
    "winter_wed_2_time": 0x0035,
    "winter_wed_3_time": 0x0036,
    "winter_wed_4_time": 0x0037,
    "winter_thu_1_time": 0x0038,
    "winter_thu_2_time": 0x0039,
    "winter_thu_3_time": 0x003A,
    "winter_thu_4_time": 0x003B,
    "winter_fri_1_time": 0x003C,
    "winter_fri_2_time": 0x003D,
    "winter_fri_3_time": 0x003E,
    "winter_fri_4_time": 0x003F,
    "winter_sat_1_time": 0x0040,
    "winter_sat_2_time": 0x0041,
    "winter_sat_3_time": 0x0042,
    "winter_sat_4_time": 0x0043,
    "winter_sun_1_time": 0x0044,
    "winter_sun_2_time": 0x0045,
    "winter_sun_3_time": 0x0046,
    "winter_sun_4_time": 0x0047,
    
    # Harmonogram LATO - nastawy [AATT] (intensywność % i temperatura x0.5°C)
    "summer_mon_1_setting": 0x0048,
    "summer_mon_2_setting": 0x0049,
    "summer_mon_3_setting": 0x004A,
    "summer_mon_4_setting": 0x004B,
    "summer_tue_1_setting": 0x004C,
    "summer_tue_2_setting": 0x004D,
    "summer_tue_3_setting": 0x004E,
    "summer_tue_4_setting": 0x004F,
    "summer_wed_1_setting": 0x0050,
    "summer_wed_2_setting": 0x0051,
    "summer_wed_3_setting": 0x0052,
    "summer_wed_4_setting": 0x0053,
    "summer_thu_1_setting": 0x0054,
    "summer_thu_2_setting": 0x0055,
    "summer_thu_3_setting": 0x0056,
    "summer_thu_4_setting": 0x0057,
    "summer_fri_1_setting": 0x0058,
    "summer_fri_2_setting": 0x0059,
    "summer_fri_3_setting": 0x005A,
    "summer_fri_4_setting": 0x005B,
    "summer_sat_1_setting": 0x005C,
    "summer_sat_2_setting": 0x005D,
    "summer_sat_3_setting": 0x005E,
    "summer_sat_4_setting": 0x005F,
    "summer_sun_1_setting": 0x0060,
    "summer_sun_2_setting": 0x0061,
    "summer_sun_3_setting": 0x0062,
    "summer_sun_4_setting": 0x0063,
    
    # Harmonogram ZIMA - nastawy
    "winter_mon_1_setting": 0x0064,
    "winter_mon_2_setting": 0x0065,
    "winter_mon_3_setting": 0x0066,
    "winter_mon_4_setting": 0x0067,
    "winter_tue_1_setting": 0x0068,
    "winter_tue_2_setting": 0x0069,
    "winter_tue_3_setting": 0x006A,
    "winter_tue_4_setting": 0x006B,
    "winter_wed_1_setting": 0x006C,
    "winter_wed_2_setting": 0x006D,
    "winter_wed_3_setting": 0x006E,
    "winter_wed_4_setting": 0x006F,
    "winter_thu_1_setting": 0x0070,
    "winter_thu_2_setting": 0x0071,
    "winter_thu_3_setting": 0x0072,
    "winter_thu_4_setting": 0x0073,
    "winter_fri_1_setting": 0x0074,
    "winter_fri_2_setting": 0x0075,
    "winter_fri_3_setting": 0x0076,
    "winter_fri_4_setting": 0x0077,
    "winter_sat_1_setting": 0x0078,
    "winter_sat_2_setting": 0x0079,
    "winter_sat_3_setting": 0x007A,
    "winter_sat_4_setting": 0x007B,
    "winter_sun_1_setting": 0x007C,
    "winter_sun_2_setting": 0x007D,
    "winter_sun_3_setting": 0x007E,
    "winter_sun_4_setting": 0x007F,
    
    # Harmonogram wietrzenia LATO
    "summer_airing_mon": 0x0080,            # LATO - Poniedziałek [GGMM]
    "summer_airing_tue": 0x0084,            # LATO - Wtorek [GGMM]
    "summer_airing_wed": 0x0088,            # LATO - Środa [GGMM]
    "summer_airing_thu": 0x008C,            # LATO - Czwartek [GGMM]
    "summer_airing_fri": 0x0090,            # LATO - Piątek [GGMM]
    "summer_airing_sat": 0x0094,            # LATO - Sobota [GGMM]
    "summer_airing_sun": 0x0098,            # LATO - Niedziela [GGMM]
    
    # Harmonogram wietrzenia ZIMA
    "winter_airing_mon": 0x009C,            # ZIMA - Poniedziałek [GGMM]
    "winter_airing_tue": 0x00A0,            # ZIMA - Wtorek [GGMM]
    "winter_airing_wed": 0x00A4,            # ZIMA - Środa [GGMM]
    "winter_airing_thu": 0x00A8,            # ZIMA - Czwartek [GGMM]
    "winter_airing_fri": 0x00AC,            # ZIMA - Piątek [GGMM]
    "winter_airing_sat": 0x00B0,            # ZIMA - Sobota [GGMM]
    "winter_airing_sun": 0x00B4,            # ZIMA - Niedziela [GGMM]
    
    # Kalibracja RTC
    "rtc_calibration": 0x00C0,              # Dane kalibracyjne zegara
    
    # Wersje modułów
    "cf_version": 0x00F0,                   # Wersja modułu CF
    "exp_version": 0x00F1,                  # Wersja modułu Expansion
    
    # Maksymalne intensywności
    "max_supply_air_flow_rate": 0x1015,     # Maksymalna intensywność nawiewu
    "max_supply_air_flow_rate_gwc": 0x1016, # Maksymalna intensywność nawiewu GWC
    "max_exhaust_air_flow_rate": 0x1017,    # Maksymalna intensywność wywiewu
    "max_exhaust_air_flow_rate_gwc": 0x1018, # Maksymalna intensywność wywiewu GWC
    
    # System FPX
    "antifreeze_mode": 0x1060,              # Flaga uruchomienia FPX
    "antifreeze_stage": 0x1066,             # Tryb działania FPX
    
    # Tryby pracy
    "mode": 0x1070,                         # Tryb pracy (0=auto, 1=manual, 2=temp)
    "season_mode": 0x1071,                  # Sezon (0=lato, 1=zima)
    "air_flow_rate_manual": 0x1072,         # Intensywność - tryb manualny
    "air_flow_rate_temporary": 0x1073,      # Intensywność - tryb chwilowy
    "supply_air_temperature_manual": 0x1074, # Temperatura - tryb manualny
    "supply_air_temperature_temporary": 0x1075, # Temperatura - tryb chwilowy
    
    # Nastawy panelu AirS
    "fan_speed_1_coef": 0x1078,             # Intensywność 1 bieg (%)
    "fan_speed_2_coef": 0x1079,             # Intensywność 2 bieg (%)
    "fan_speed_3_coef": 0x107A,             # Intensywność 3 bieg (%)
    "manual_airing_time_to_start": 0x107B,  # Godzina wietrzenia manualnego [GGMM]
    
    # Funkcje specjalne
    "special_mode": 0x1080,                 # Funkcje specjalne (0-11)
    "hood_supply_coef": 0x1082,             # Intensywność OKAP nawiew (%)
    "hood_exhaust_coef": 0x1083,            # Intensywność OKAP wywiew (%)
    "fireplace_supply_coef": 0x1084,        # Różnicowanie KOMINEK (%)
    "airing_bathroom_coef": 0x1085,         # Intensywność WIETRZENIE łazienka (%)
    "airing_coef": 0x1086,                  # Intensywność WIETRZENIE pokoje (%)
    "contamination_coef": 0x1087,           # Intensywność czujnik jakości (%)
    "empty_house_coef": 0x1088,             # Intensywność PUSTY DOM (%)
    "airing_panel_mode_time": 0x1089,       # Czas WIETRZENIE pokoje (min)
    "airing_switch_mode_time": 0x108A,      # Czas WIETRZENIE łazienka (min)
    "airing_switch_mode_on_delay": 0x108B,  # Opóźnienie włączenia (min)
    "airing_switch_mode_off_delay": 0x108C, # Opóźnienie wyłączenia (min)
    "fireplace_mode_time": 0x108D,          # Czas KOMINEK (min)
    "airing_switch_coef": 0x108E,           # Intensywność przełącznik (%)
    "open_window_coef": 0x108F,             # Intensywność OTWARTE OKNA (%)
    
    # Kontrola filtrów
    "pres_check_day": 0x1094,               # Dzień kontroli filtrów
    "pres_check_time": 0x1095,              # Godzina kontroli filtrów [GGMM]
    
    # System GWC
    "gwc_off": 0x10A0,                      # Dezaktywacja GWC
    "min_gwc_air_temperature": 0x10A1,      # Dolny próg GWC (x0.5°C)
    "max_gwc_air_temperature": 0x10A2,      # Górny próg GWC (x0.5°C)
    "gwc_regen": 0x10A6,                    # Typ regeneracji GWC
    "gwc_mode": 0x10A7,                     # Status GWC (0=off, 1=zima, 2=lato)
    "gwc_regen_period": 0x10A8,             # Czas regeneracji (h)
    "delta_t_gwc": 0x10AA,                  # Różnica temperatur regeneracji (x0.5°C)
    "start_gwc_regen_winter_time": 0x10AB,  # Start regeneracji zima [GGMM]
    "stop_gwc_regen_winter_time": 0x10AC,   # Stop regeneracji zima [GGMM]
    "start_gwc_regen_summer_time": 0x10AD,  # Start regeneracji lato [GGMM]
    "stop_gwc_regen_summer_time": 0x10AE,   # Stop regeneracji lato [GGMM]
    "gwc_regen_flag": 0x10AF,               # Flaga regeneracji GWC
    
    # Tryb KOMFORT
    "comfort_mode_panel": 0x10D0,           # Wybór EKO/KOMFORT
    "comfort_mode": 0x10D1,                 # Status KOMFORT (0=off, 1=heat, 2=cool)
    
    # System Bypass
    "bypass_off": 0x10E0,                   # Dezaktywacja bypass
    "min_bypass_temperature": 0x10E1,       # Minimalna temperatura bypass (x0.5°C)
    "air_temperature_summer_free_heating": 0x10E2, # Temperatura FreeHeating (x0.5°C)
    "air_temperature_summer_free_cooling": 0x10E3, # Temperatura FreeCooling (x0.5°C)
    "bypass_mode": 0x10EA,                  # Status bypass (0=off, 1=heat, 2=cool)
    "bypass_user_mode": 0x10EB,             # Sposób realizacji bypass (1-3)
    "bypass_coef1": 0x10EC,                 # Różnicowanie bypass (%)
    "bypass_coef2": 0x10ED,                 # Intensywność bypass (%)
    
    # Nominalne strumienie
    "nominal_supply_air_flow": 0x1102,      # Nominalny strumień nawiewu (m³/h)
    "nominal_exhaust_air_flow": 0x1103,     # Nominalny strumień wywiewu (m³/h)
    "nominal_supply_air_flow_gwc": 0x1104,  # Nominalny strumień nawiewu GWC (m³/h)
    "nominal_exhaust_air_flow_gwc": 0x1105, # Nominalny strumień wywiewu GWC (m³/h)
    
    # Alarmy i sterowanie
    "stop_ahu_code": 0x1120,                # Kod alarmu zatrzymującego
    "on_off_panel_mode": 0x1123,            # ON/OFF urządzenia
    "language": 0x112F,                     # Język panelu
    
    # Alternatywne tryby sterowania
    "cfg_mode_1": 0x1130,                   # Tryb pracy - grupa 1
    "air_flow_rate_temporary_1": 0x1131,    # Intensywność chwilowa - grupa 1
    "airflow_rate_change_flag": 0x1132,     # Flaga zmiany intensywności
    "cfg_mode_2": 0x1133,                   # Tryb pracy - grupa 2
    "supply_air_temperature_temporary_2": 0x1134, # Temperatura chwilowa - grupa 2
    "temperature_change_flag": 0x1135,      # Flaga zmiany temperatury
    
    # Reset ustawień
    "hard_reset_settings": 0x113D,          # Reset ustawień użytkownika
    "hard_reset_schedule": 0x113E,          # Reset harmonogramów
    
    # Kontrola filtrów (duplikat)
    "pres_check_day_2": 0x1150,             # Dzień kontroli filtrów
    "pres_check_time_2": 0x1151,            # Godzina kontroli filtrów [GGMM]
    
    # Komunikacja Modbus
    "uart0_id": 0x1164,                     # ID urządzenia port Air-B
    "uart0_baud": 0x1165,                   # Prędkość port Air-B
    "uart0_parity": 0x1166,                 # Parzystość port Air-B
    "uart0_stop": 0x1167,                   # Bity stop port Air-B
    "uart1_id": 0x1168,                     # ID urządzenia port Air++
    "uart1_baud": 0x1169,                   # Prędkość port Air++
    "uart1_parity": 0x116A,                 # Parzystość port Air++
    "uart1_stop": 0x116B,                   # Bity stop port Air++
    
    # Nazwa urządzenia (8 rejestrów ASCII)
    "device_name_1": 0x1FD0,
    "device_name_2": 0x1FD1,
    "device_name_3": 0x1FD2,
    "device_name_4": 0x1FD3,
    "device_name_5": 0x1FD4,
    "device_name_6": 0x1FD5,
    "device_name_7": 0x1FD6,
    "device_name_8": 0x1FD7,
    
    # Klucz produktu
    "lock_pass_1": 0x1FFB,                  # Klucz produktu słowo młodsze
    "lock_pass_2": 0x1FFC,                  # Klucz produktu słowo starsze
    "lock_flag": 0x1FFD,                    # Aktywacja blokady
    "required_temp": 0x1FFE,                # Temperatura zadana KOMFORT (x0.5°C)
    "filter_change": 0x1FFF,                # System kontroli filtrów
    
    # ALARMY - wszystkie alarmy typu E i S (0x2000+)
    "alarm_flag": 0x2000,                   # Flaga alarmów E
    "error_flag": 0x2001,                   # Flaga błędów S
    "s2_i2c_error": 0x2002,                 # S2: Błąd komunikacji I2C
    "s6_fpx_thermal": 0x2006,               # S6: Zabezpieczenie FPX
    "s7_calibration_temp": 0x2007,          # S7: Temperatura kalibracji
    "s8_product_key": 0x2008,               # S8: Klucz produktu
    "s9_airs_stopped": 0x2009,              # S9: Stop z panelu AirS
    "s10_fire_alarm": 0x200A,               # S10: Alarm pożarowy
    "s13_panel_stopped": 0x200D,            # S13: Stop z panelu
    "s14_water_heater_thermal": 0x200E,     # S14: Zabezpieczenie nagrzewnicy wodnej
    "s15_water_heater_protection": 0x200F,  # S15: Ochrona nagrzewnicy wodnej
    "s16_electric_heater_thermal": 0x2010,  # S16: Zabezpieczenie nagrzewnicy elektrycznej
    "s17_filter_change_pres": 0x2011,       # S17: Wymiana filtrów (presostat)
    "s19_filter_change_no_pres": 0x2013,    # S19: Wymiana filtrów (bez presostatu)
    "s20_duct_filter_change": 0x2014,       # S20: Wymiana filtra kanałowego
    "s22_fpx_no_protection": 0x2016,        # S22: Brak ochrony FPX
    "s23_fpx_sensor_damaged": 0x2017,       # S23: Uszkodzony czujnik FPX
    "s24_duct_sensor_damaged": 0x2018,      # S24: Uszkodzony czujnik kanałowy
    "s25_outside_sensor_damaged": 0x2019,   # S25: Uszkodzony czujnik zewnętrzny
    "s26_gwc_sensor_damaged": 0x201A,       # S26: Uszkodzony czujnik GWC
    "s29_high_temperature": 0x201D,         # S29: Wysoka temperatura
    "s30_supply_fan_failure": 0x201E,       # S30: Awaria wentylatora nawiewnego
    "s31_exhaust_fan_failure": 0x201F,      # S31: Awaria wentylatora wywiewnego
    "s32_tg02_communication": 0x2020,       # S32: Komunikacja z TG-02
    
    # Alarmy typu E (ostrzeżenia)
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

# GWC regeneration types
GWC_REGEN_TYPES = {
    0: "Brak regeneracji",
    1: "Regeneracja dobowa",
    2: "Regeneracja temperaturowa"
}

# Bypass modes
BYPASS_MODES = {
    0: "Bypass nieaktywny",
    1: "Funkcja grzania (FreeHeating)",
    2: "Funkcja chłodzenia (FreeCooling)"
}

# Bypass user modes
BYPASS_USER_MODES = {
    1: "Tryb 1 - tylko przepustnica",
    2: "Tryb 2 - przepustnica + różnicowanie",
    3: "Tryb 3 - przepustnica + wyłączenie wywiewu"
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

# Languages
LANGUAGES = {
    0: "Polski",
    1: "English", 
    2: "Русский",
    3: "Українська",
    4: "Slovenčina"
}

# Filter types
FILTER_TYPES = {
    1: "Presostat",
    2: "Filtry płaskie",
    3: "Filtry CleanPad", 
    4: "Filtry CleanPad Pure"
}

# Days of week
DAYS_OF_WEEK = {
    0: "Poniedziałek",
    1: "Wtorek",
    2: "Środa",
    3: "Czwartek",
    4: "Piątek",
    5: "Sobota",
    6: "Niedziela"
}

# Communication settings
BAUD_RATES = {
    0: 4800,
    1: 9600,
    2: 14400,
    3: 19200,
    4: 28800,
    5: 38400,
    6: 57600,
    7: 76800,
    8: 115200
}

PARITY_MODES = {
    0: "Brak",
    1: "Parzysty",
    2: "Nieparzysty"
}

STOP_BITS = {
    0: "Jeden",
    1: "Dwa"
}

# Alarm codes and descriptions
ALARM_DESCRIPTIONS = {
    "S2": "Błąd komunikacji I2C",
    "S6": "Zabezpieczenie termiczne nagrzewnicy FPX zadziałało maksymalną ilość razy",
    "S7": "Brak możliwości kalibracji - zbyt niska temperatura zewnętrzna",
    "S8": "Sygnalizacja konieczności wprowadzenia klucza produktu",
    "S9": "Centrala zatrzymana z panelu AirS",
    "S10": "Zadziałał czujnik PPOŻ",
    "S13": "Centrala zatrzymana z panelu Air+/AirL+/Air++/AirMobile",
    "S14": "Zabezpieczenie przeciwzamrożeniowe nagrzewnicy wodnej zadziałało maksymalną ilość razy",
    "S15": "Zabezpieczenie przeciwzamrożeniowe nagrzewnicy wodnej nie przyniosło efektów",
    "S16": "Zadziałało zabezpieczenie termiczne nagrzewnicy elektrycznej przy aktywnym FPX",
    "S17": "Nie zostały wymienione filtry w centrali (presostat)",
    "S19": "Nie zostały wymienione filtry w centrali (bez presostatu)",
    "S20": "Nie został wymieniony filtr kanałowy",
    "S22": "Nie zadziałało zabezpieczenie przeciwzamrożeniowe wymiennika (FPX)",
    "S23": "Uszkodzony czujnik temperatury na wlocie do wymiennika przy warunkach FPX",
    "S24": "Uszkodzony czujnik temperatury za nagrzewnicą wodną",
    "S25": "Uszkodzony czujnik temperatury powietrza zewnętrznego",
    "S26": "Uszkodzone czujniki temperatury zewnętrznej i GWC",
    "S29": "Zbyt wysoka temperatura przed rekuperatorem",
    "S30": "Nie działa wentylator nawiewny",
    "S31": "Nie działa wentylator wywiewny",
    "S32": "Brak komunikacji z modułem TG-02",
    "E99": "Sygnalizacja konieczności wprowadzenia klucza produktu centrali",
    "E100": "Brak odczytu z czujnika temperatury zewnętrznej (TZ1)",
    "E101": "Brak odczytu z czujnika temperatury nawiewu (TN1)",
    "E102": "Brak odczytu z czujnika temperatury wywiewu (TP)",
    "E103": "Brak odczytu z czujnika temperatury FPX (TZ2)",
    "E104": "Brak odczytu z czujnika temperatury otoczenia (TO)",
    "E105": "Brak odczytu z czujnika temperatury kanałowej (TN2)",
    "E106": "Brak odczytu z czujnika temperatury GWC (TZ3)",
    "E138": "Awaria czujnika CF wentylatora nawiewnego",
    "E139": "Awaria czujnika CF wentylatora wywiewnego",
    "E152": "Temperatura powietrza wywiewanego wyższa od maksymalnej",
    "E196": "Regulacja instalacji nie została wykonana",
    "E197": "Regulacja instalacji została przerwana",
    "E198": "Brak komunikacji z modułem CF2",
    "E199": "Brak komunikacji z modułem CF",
    "E200": "Zadziałało zabezpieczenie termiczne nagrzewnicy elektrycznej w centrali",
    "E201": "Zadziałało zabezpieczenie termiczne nagrzewnicy elektrycznej w kanale",
    "E249": "Brak komunikacji z modułem Expansion",
    "E250": "Sygnalizacja konieczności wymiany filtrów (bez presostatu)",
    "E251": "Sygnalizacja konieczności wymiany filtra kanałowego",
    "E252": "Sygnalizacja konieczności wymiany filtrów (presostat)",
}

# Temperature sensor invalid value
INVALID_TEMPERATURE = 0x8000  # 32768 decimal - indicates sensor not connected

# Air flow invalid value  
INVALID_FLOW = 65535  # Indicates CF not active

# BCD time format helpers
def decode_bcd_time(value: int) -> tuple[int, int]:
    """Decode BCD time format [GGMM] to (hour, minute)."""
    hour = (value >> 8) & 0xFF
    minute = value & 0xFF
    return hour, minute

def encode_bcd_time(hour: int, minute: int) -> int:
    """Encode time to BCD format [GGMM]."""
    return (hour << 8) | minute

def decode_setting_aatt(value: int) -> tuple[int, float]:
    """Decode setting format [AATT] to (airflow_percent, temperature_celsius)."""
    airflow = (value >> 8) & 0xFF
    temp_raw = value & 0xFF
    temperature = temp_raw * 0.5
    return airflow, temperature

def encode_setting_aatt(airflow: int, temperature: float) -> int:
    """Encode setting format [AATT] from (airflow_percent, temperature_celsius)."""
    temp_raw = int(temperature * 2)
    return (airflow << 8) | temp_raw