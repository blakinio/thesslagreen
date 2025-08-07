"""Constants and register definitions for ThesslaGreen Modbus Integration.
COMPLETE REGISTER MAPPING - Supports both old and new firmware versions.
"""
from typing import Dict, List

# Integration constants
DOMAIN = "thessla_green_modbus"
MANUFACTURER = "ThesslaGreen"
MODEL = "AirPack Home"

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
# COMPLETE REGISTER MAPPING - All 200+ registers from both PDFs
# ============================================================================

# INPUT REGISTERS (04 - READ INPUT REGISTER) - Read-only sensor values
INPUT_REGISTERS = {
    # Firmware version (0x0000-0x0004)
    "firmware_major": 0x0000,                # Wersja główna (MM)
    "firmware_minor": 0x0001,                # Wersja podrzędna (mm)
    "day_of_week": 0x0002,                   # Dzień tygodnia (0-6)
    "period": 0x0003,                         # Odcinek czasowy (0-3)
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
    
    # Fan percentages (0x0020-0x0021)
    "supply_percentage": 0x0020,             # Procent nawiewu (%)
    "exhaust_percentage": 0x0021,            # Procent wywiewu (%)
    
    # Operating status (0x0022-0x0023)
    "device_status_smart": 0x0022,           # Status urządzenia (0/1)
    "constant_flow_active": 0x0023,          # Stały przepływ aktywny (0/1)
    
    # Error/Warning codes (0x0024-0x0025)
    "error_code": 0x0024,                    # Kod błędu (0-50)
    "warning_code": 0x0025,                  # Kod ostrzeżenia (0-50)
    
    # Filter status (0x0026)
    "filter_time_remaining": 0x0026,         # Dni do wymiany filtra
    
    # Additional sensors (0x0027-0x002F)
    "heat_recovery_efficiency": 0x0027,      # Sprawność odzysku ciepła (%)
    "bypass_position": 0x0028,               # Pozycja bypassa (%)
    "heater_power": 0x0029,                  # Moc nagrzewnicy (W)
    "cooler_power": 0x002A,                  # Moc chłodnicy (W)
    "total_power_consumption": 0x002B,       # Całkowite zużycie mocy (W)
    "filter_pressure_drop": 0x002C,          # Spadek ciśnienia na filtrze (Pa)
    "system_pressure": 0x002D,               # Ciśnienie w systemie (Pa)
    "humidity_level": 0x002E,                # Poziom wilgotności (%)
    "co2_level": 0x002F,                     # Poziom CO2 (ppm)
    
    # Flow rates (0x0030-0x0031)
    "supply_flowrate": 0x0030,               # Przepływ nawiewu (m³/h)
    "exhaust_flowrate": 0x0031,              # Przepływ wywiewu (m³/h)
    
    # Extended sensors (0x0032-0x003F)
    "supply_fan_rpm": 0x0032,                # Obroty wentylatora nawiewu (RPM)
    "exhaust_fan_rpm": 0x0033,               # Obroty wentylatora wywiewu (RPM)
    "heat_exchanger_efficiency": 0x0034,     # Sprawność wymiennika (%)
    "defrost_status": 0x0035,                # Status rozmrażania (0/1)
    "defrost_time_remaining": 0x0036,        # Czas do rozmrażania (min)
    "summer_mode_active": 0x0037,            # Tryb letni aktywny (0/1)
    "winter_mode_active": 0x0038,            # Tryb zimowy aktywny (0/1)
    "auto_mode_active": 0x0039,              # Tryb auto aktywny (0/1)
    "manual_mode_active": 0x003A,            # Tryb manualny aktywny (0/1)
    "temporary_mode_active": 0x003B,         # Tryb chwilowy aktywny (0/1)
    "service_mode_active": 0x003C,           # Tryb serwisowy aktywny (0/1)
}

# HOLDING REGISTERS (03 - READ HOLDING REGISTER) - Read/Write control values
HOLDING_REGISTERS = {
    # Date and time (0x0000-0x0003) - must be read/written as 4 consecutive registers
    "date_year_month": 0x0000,               # [RRMM] - rok i miesiąc
    "date_day_weekday": 0x0001,              # [DDTT] - dzień i dzień tygodnia
    "time_hour_minute": 0x0002,              # [GGmm] - godzina i minuta
    "time_second_centisecond": 0x0003,       # [sscc] - sekunda i setne sekundy
    
    # Lock date (0x0007-0x0009) - read-only
    "lock_date_year": 0x0007,                # Rok zablokowania
    "lock_date_month": 0x0008,               # Miesiąc zablokowania
    "lock_date_day": 0x0009,                 # Dzień zablokowania
    
    # Configuration (0x000D, 0x000F)
    "configuration_mode": 0x000D,            # Tryby specjalne (0=normal, 47=filter, 65=AFC)
    "access_level": 0x000F,                  # Poziom dostępu (0=user, 1=service, 3=manufacturer)
    
    # Basic operating modes (0x1000-0x1003) - NEW FIRMWARE
    "mode": 0x1000,                          # Tryb pracy (0=Auto, 1=Manual, 2=Temporary, 3=Service)
    "on_off_panel_mode": 0x1001,             # Panel ON/OFF (0/1)
    "special_mode": 0x1002,                  # Funkcja specjalna
    "season_mode": 0x1003,                   # Tryb sezonowy (0=auto, 1=zima, 2=lato)
    
    # Comfort settings (0x1004-0x1006)
    "comfort_mode": 0x1004,                  # Tryb komfort (0=OFF, 1=Heat, 2=Cool)
    "comfort_temperature_heating": 0x1005,   # Temperatura komfort grzanie (°C * 10)
    "comfort_temperature_cooling": 0x1006,   # Temperatura komfort chłodzenie (°C * 10)
    
    # Intensity settings for 10 levels (0x1010-0x1019)
    "intensity_1": 0x1010,                   # Intensywność biegu 1 (10-150%)
    "intensity_2": 0x1011,                   # Intensywność biegu 2 (10-150%)
    "intensity_3": 0x1012,                   # Intensywność biegu 3 (10-150%)
    "intensity_4": 0x1013,                   # Intensywność biegu 4 (10-150%)
    "intensity_5": 0x1014,                   # Intensywność biegu 5 (10-150%)
    "intensity_6": 0x1015,                   # Intensywność biegu 6 (10-150%)
    "intensity_7": 0x1016,                   # Intensywność biegu 7 (10-150%)
    "intensity_8": 0x1017,                   # Intensywność biegu 8 (10-150%)
    "intensity_9": 0x1018,                   # Intensywność biegu 9 (10-150%)
    "intensity_10": 0x1019,                  # Intensywność biegu 10 (10-150%)
    
    # Manual/Temporary/Auto intensity (aliases for backward compatibility)
    "air_flow_rate_manual": 0x1010,          # Intensywność tryb manualny
    "air_flow_rate_temporary": 0x1011,       # Intensywność tryb chwilowy
    "air_flow_rate_auto": 0x1012,            # Intensywność tryb auto
    
    # Temperature setpoints (0x1020-0x1022)
    "supply_temperature_manual": 0x1020,     # Temperatura nawiewu manual (°C * 10)
    "supply_temperature_temporary": 0x1021,  # Temperatura nawiewu temporary (°C * 10)
    "frost_protection_temperature": 0x1022,  # Temperatura ochrony przed zamarzaniem (°C * 10)
    
    # GWC (Ground Heat Exchanger) settings (0x1030-0x1032)
    "gwc_mode": 0x1030,                      # Tryb GWC (0=OFF, 1=AUTO, 2=ON)
    "gwc_activation_temperature": 0x1031,    # Temperatura aktywacji GWC (°C * 10)
    "gwc_deactivation_temperature": 0x1032,  # Temperatura dezaktywacji GWC (°C * 10)
    
    # Bypass settings (0x1040-0x1042)
    "bypass_mode": 0x1040,                   # Tryb bypass (0=OFF, 1=AUTO, 2=ON)
    "bypass_activation_temperature": 0x1041, # Temperatura aktywacji bypass (°C * 10)
    "bypass_deactivation_temperature": 0x1042, # Temperatura dezaktywacji bypass (°C * 10)
    
    # Time schedules (0x1050-0x105D)
    "schedule_monday_start": 0x1050,         # Poniedziałek start [GGMM]
    "schedule_monday_end": 0x1051,           # Poniedziałek koniec [GGMM]
    "schedule_tuesday_start": 0x1052,        # Wtorek start [GGMM]
    "schedule_tuesday_end": 0x1053,          # Wtorek koniec [GGMM]
    "schedule_wednesday_start": 0x1054,      # Środa start [GGMM]
    "schedule_wednesday_end": 0x1055,        # Środa koniec [GGMM]
    "schedule_thursday_start": 0x1056,       # Czwartek start [GGMM]
    "schedule_thursday_end": 0x1057,         # Czwartek koniec [GGMM]
    "schedule_friday_start": 0x1058,         # Piątek start [GGMM]
    "schedule_friday_end": 0x1059,           # Piątek koniec [GGMM]
    "schedule_saturday_start": 0x105A,       # Sobota start [GGMM]
    "schedule_saturday_end": 0x105B,         # Sobota koniec [GGMM]
    "schedule_sunday_start": 0x105C,         # Niedziela start [GGMM]
    "schedule_sunday_end": 0x105D,           # Niedziela koniec [GGMM]
    
    # OLD FIRMWARE - Alternative addresses (0x1070-0x10FF)
    "mode_old": 0x1070,                      # Tryb pracy (stary firmware)
    "special_mode_old": 0x1071,              # Funkcja specjalna (stary firmware)
    "intensity_1_old": 0x1080,               # Intensywność 1 (stary firmware)
    "intensity_2_old": 0x1081,               # Intensywność 2 (stary firmware)
    "intensity_3_old": 0x1082,               # Intensywność 3 (stary firmware)
    "intensity_4_old": 0x1083,               # Intensywność 4 (stary firmware)
    "intensity_5_old": 0x1084,               # Intensywność 5 (stary firmware)
    
    # Extended configuration (0x1100-0x11FF)
    "filter_type": 0x1100,                   # Typ filtra (1=presostat, 2=płaski, 3=CleanPad)
    "filter_change_interval": 0x1101,        # Interwał wymiany filtra (dni)
    "filter_warning_days": 0x1102,           # Ostrzeżenie o filtrze (dni)
    "service_interval": 0x1103,              # Interwał serwisowy (dni)
    "service_warning_days": 0x1104,          # Ostrzeżenie o serwisie (dni)
    
    # Mode configuration (0x1130-0x1135)
    "cfg_mode1": 0x1130,                     # Tryb pracy - grupa 1
    "air_flow_rate_temporary_cfg": 0x1131,   # Intensywność chwilowa
    "airflow_rate_change_flag": 0x1132,      # Flaga zmiany intensywności
    "cfg_mode2": 0x1133,                     # Tryb pracy - grupa 2
    "supply_air_temperature_temporary": 0x1134, # Temperatura nawiewu chwilowa
    "temperature_change_flag": 0x1135,       # Flaga zmiany temperatury
    
    # Reset settings (0x113D-0x113E)
    "hard_reset_settings": 0x113D,           # Reset ustawień użytkownika
    "hard_reset_schedule": 0x113E,           # Reset harmonogramów
    
    # Presostat configuration (0x1150-0x1151)
    "pres_check_day": 0x1150,                # Dzień kontroli filtrów (0-6)
    "pres_check_time": 0x1151,               # Godzina kontroli filtrów [GGMM]
    
    # Communication settings (0x1164-0x116B)
    "uart0_id": 0x1164,                      # Modbus ID - port Air-B (10-19)
    "uart0_baud": 0x1165,                    # Baudrate - port Air-B
    "uart0_parity": 0x1166,                  # Parzystość - port Air-B
    "uart0_stop": 0x1167,                    # Bity stopu - port Air-B
    "uart1_id": 0x1168,                      # Modbus ID - port Air++
    "uart1_baud": 0x1169,                    # Baudrate - port Air++
    "uart1_parity": 0x116A,                  # Parzystość - port Air++
    "uart1_stop": 0x116B,                    # Bity stopu - port Air++
    
    # Device configuration (0x1FD0-0x1FFF)
    "device_name_1": 0x1FD0,                 # Nazwa urządzenia - część 1
    "device_name_2": 0x1FD1,                 # Nazwa urządzenia - część 2
    "device_name_3": 0x1FD2,                 # Nazwa urządzenia - część 3
    "device_name_4": 0x1FD3,                 # Nazwa urządzenia - część 4
    "device_name_5": 0x1FD4,                 # Nazwa urządzenia - część 5
    "device_name_6": 0x1FD5,                 # Nazwa urządzenia - część 6
    "device_name_7": 0x1FD6,                 # Nazwa urządzenia - część 7
    "device_name_8": 0x1FD7,                 # Nazwa urządzenia - część 8
    
    # Product key and lock (0x1FFB-0x1FFD)
    "lock_pass1": 0x1FFB,                    # Klucz produktu - część 1
    "lock_pass2": 0x1FFC,                    # Klucz produktu - część 2
    "lock_flag": 0x1FFD,                     # Aktywacja blokady (0/1)
    
    # Final configuration (0x1FFE-0x1FFF)
    "required_temp": 0x1FFE,                 # Temperatura zadana KOMFORT (20-90°C)
    "filter_change": 0x1FFF,                 # System kontroli filtrów (1-4)
}

# COIL REGISTERS (01 - READ COILS) - Read-only binary outputs
COIL_REGISTERS = {
    "duct_water_heater_pump": 0x0005,        # Pompa obiegowa nagrzewnicy
    "bypass": 0x0009,                        # Siłownik przepustnicy bypass
    "info": 0x000A,                          # Sygnał potwierdzenia pracy (O1)
    "power_supply_fans": 0x000B,             # Zasilanie wentylatorów
    "heating_cable": 0x000C,                 # Kabel grzejny
    "work_permit": 0x000D,                   # Potwierdzenie pracy (Expansion)
    "gwc": 0x000E,                           # Przekaźnik GWC
    "hood": 0x000F,                          # Zasilanie przepustnicy okapu
    
    # Extended coils (0x0010-0x001F)
    "heater_active": 0x0010,                 # Nagrzewnica aktywna
    "cooler_active": 0x0011,                 # Chłodnica aktywna
    "humidifier_active": 0x0012,             # Nawilżacz aktywny
    "dehumidifier_active": 0x0013,           # Osuszacz aktywny
    "preheater_active": 0x0014,              # Nagrzewnica wstępna aktywna
    "afterheater_active": 0x0015,            # Nagrzewnica wtórna aktywna
    "electric_heater_active": 0x0016,        # Nagrzewnica elektryczna aktywna
    "water_heater_active": 0x0017,           # Nagrzewnica wodna aktywna
}

# DISCRETE INPUTS (02 - READ DISCRETE INPUTS) - Read-only binary inputs
DISCRETE_INPUTS = {
    "bypass_closed": 0x0000,                 # Bypass zamknięty
    "bypass_open": 0x0001,                   # Bypass otwarty
    "filter_alarm": 0x0002,                  # Alarm filtra
    "frost_alarm": 0x0003,                   # Alarm zamarzania
    "fire_alarm": 0x0004,                    # Alarm pożarowy
    "emergency_stop": 0x0005,                # Zatrzymanie awaryjne
    "external_stop": 0x0006,                  # Zatrzymanie zewnętrzne
    "service_required": 0x0007,              # Wymagany serwis
    
    # Expansion inputs (0x0008-0x000F)
    "expansion": 0x0008,                     # Moduł rozszerzeń
    "external_on": 0x0009,                   # Włączenie zewnętrzne
    "external_off": 0x000A,                  # Wyłączenie zewnętrzne
    "boost_input": 0x000B,                   # Wejście boost
    "eco_input": 0x000C,                     # Wejście eco
    "night_input": 0x000D,                   # Wejście nocne
    "away_input": 0x000E,                    # Wejście nieobecność
    "schedule_override": 0x000F,             # Nadpisanie harmonogramu
    
    # Sensor status (0x0010-0x001F)
    "temp_sensor_1_ok": 0x0010,              # Czujnik temperatury 1 OK
    "temp_sensor_2_ok": 0x0011,              # Czujnik temperatury 2 OK
    "temp_sensor_3_ok": 0x0012,              # Czujnik temperatury 3 OK
    "temp_sensor_4_ok": 0x0013,              # Czujnik temperatury 4 OK
    "pressure_sensor_ok": 0x0014,            # Czujnik ciśnienia OK
    "humidity_sensor_ok": 0x0015,            # Czujnik wilgotności OK
    "co2_sensor_ok": 0x0016,                 # Czujnik CO2 OK
    "flow_sensor_ok": 0x0017,                # Czujnik przepływu OK
}

# Operating modes mapping
OPERATING_MODES = {
    0: "Auto",
    1: "Manual",
    2: "Temporary",
    3: "Service",
}

# Special modes mapping
SPECIAL_MODES = {
    0: "None",
    1: "OKAP",           # Kitchen hood
    2: "KOMINEK",        # Fireplace
    3: "WIETRZENIE",     # Airing
    4: "PUSTY_DOM",      # Empty house
    5: "OPEN_WINDOWS",   # Open windows
}

# Comfort modes mapping
COMFORT_MODES = {
    0: "Off",
    1: "Heating",
    2: "Cooling",
}

# Season modes mapping
SEASON_MODES = {
    0: "Auto",
    1: "Winter",
    2: "Summer",
}

# Filter types mapping
FILTER_TYPES = {
    1: "Presostat",
    2: "Flat",
    3: "CleanPad",
    4: "CleanPad Pure",
}

# Error codes mapping
ERROR_CODES = {
    0: "No error",
    1: "Temperature sensor 1 failure",
    2: "Temperature sensor 2 failure",
    3: "Temperature sensor 3 failure",
    4: "Temperature sensor 4 failure",
    5: "Supply fan failure",
    6: "Exhaust fan failure",
    7: "Filter alarm",
    8: "Frost protection active",
    9: "Fire alarm",
    10: "Emergency stop",
    11: "Communication error",
    12: "Configuration error",
    13: "Hardware failure",
    14: "Bypass failure",
    15: "GWC failure",
}

# Warning codes mapping
WARNING_CODES = {
    0: "No warning",
    1: "Filter replacement soon",
    2: "Service required soon",
    3: "Low efficiency",
    4: "High power consumption",
    5: "Temperature sensor degradation",
    6: "Fan imbalance",
    7: "Schedule conflict",
    8: "Manual override active",
}

# Service definitions
SERVICE_SET_MODE = "set_mode"
SERVICE_SET_INTENSITY = "set_intensity"
SERVICE_SET_SPECIAL_FUNCTION = "set_special_function"
SERVICE_SET_COMFORT_TEMPERATURE = "set_comfort_temperature"
SERVICE_RESET_ALARMS = "reset_alarms"
SERVICE_ACTIVATE_BOOST = "activate_boost"
SERVICE_CONFIGURE_GWC = "configure_gwc"
SERVICE_CONFIGURE_BYPASS = "configure_bypass"
SERVICE_SCHEDULE_MAINTENANCE = "schedule_maintenance"
SERVICE_CALIBRATE_SENSORS = "calibrate_sensors"
SERVICE_EMERGENCY_STOP = "emergency_stop"
SERVICE_QUICK_VENTILATION = "quick_ventilation"
SERVICE_CONFIGURE_CONSTANT_FLOW = "configure_constant_flow"
SERVICE_DEVICE_RESCAN = "device_rescan"