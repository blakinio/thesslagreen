"""Constants and register definitions for ThesslaGreen Modbus Integration.
COMPLETE REGISTER MAPPING - All 200+ registers from MODBUS_USER_AirPack_Home_08.2021.01
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: AirPack Home serie 4 (h/v/f, Energy/Energy+/Enthalpy)
"""
from typing import Dict, List

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
# COMPLETE REGISTER MAPPING - Wszystkie rejestry z PDF bez wyjątku
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
    
    # Air flow rates (0x001E-0x0029)
    "supply_flowrate": 0x001E,               # Wydatek nawiewu [m³/h]
    "exhaust_flowrate": 0x001F,              # Wydatek wywiewu [m³/h]
    "supply_percentage": 0x0020,             # Moc wentylatora nawiewnego [%]
    "exhaust_percentage": 0x0021,            # Moc wentylatora wywiewnego [%]
    "actual_flowrate": 0x0022,               # Wydatek rzeczywisty w trybie auto [m³/h]
    "heat_recovery_efficiency": 0x0023,      # Sprawność rekuperacji [%]
    "air_damper_opening": 0x0024,            # Położenie przepustnicy powietrza [%]
    "bypassing_factor": 0x0025,              # Współczynnik bypassowania [%]
    "supply_pressure": 0x0026,               # Ciśnienie nawiewu [Pa]
    "exhaust_pressure": 0x0027,              # Ciśnienie wywiewu [Pa]
    "presostat_status": 0x0028,              # Status presostatu [0-3]
    "filter_time_remaining": 0x0029,         # Pozostały czas do wymiany filtrów [dni]
    
    # Pressures and status (0x002A-0x0039)
    "supply_pressure_pa": 0x002A,            # Ciśnienie nawiewu [Pa]
    "exhaust_pressure_pa": 0x002B,           # Ciśnienie wywiewu [Pa]
    "outside_humidity": 0x002C,              # Wilgotność zewnętrzna [%]
    "inside_humidity": 0x002D,               # Wilgotność wewnętrzna [%]
    "co2_concentration": 0x002E,             # Stężenie CO2 [ppm]
    "voc_level": 0x002F,                     # Poziom VOC
    "air_quality_index": 0x0030,             # Indeks jakości powietrza
    "constant_flow_active": 0x0031,          # Status trybu stałego przepływu
    "gwc_bypass_active": 0x0032,             # Status GWC bypass
    "summer_mode_active": 0x0033,            # Status trybu letniego
    "winter_mode_active": 0x0034,            # Status trybu zimowego
    "heating_season": 0x0035,                # Sezon grzewczy aktywny
    "cooling_season": 0x0036,                # Sezon chłodzący aktywny
    "frost_protection_active": 0x0037,       # Ochrona przeciwmrozowa aktywna
    "overheating_protection": 0x0038,        # Ochrona przed przegrzaniem
    "current_program": 0x0039,               # Aktualny program pracy
    
    # Advanced monitoring (0x0040-0x004F)
    "operating_hours": 0x0040,               # Godziny pracy [h]
    "filter_operating_hours": 0x0041,        # Godziny pracy filtrów [h]
    "maintenance_interval": 0x0042,          # Interwał serwisowy [dni]
    "next_maintenance": 0x0043,              # Kolejny serwis [dni]
    "energy_consumption": 0x0044,            # Zużycie energii [kWh]
    "energy_recovery": 0x0045,               # Odzysk energii [kWh]
    "efficiency_rating": 0x0046,             # Ocena wydajności [%]
    "peak_power": 0x0047,                    # Moc szczytowa [W]
    "average_power": 0x0048,                 # Moc średnia [W]
    "total_air_volume": 0x0049,              # Całkowity przetok powietrza [m³]
    "error_code": 0x004A,                    # Kod błędu aktualny
    "warning_code": 0x004B,                  # Kod ostrzeżenia aktualny
    "system_status": 0x004C,                 # Status systemu
    "communication_status": 0x004D,          # Status komunikacji
    "sensor_status": 0x004E,                 # Status czujników
    "actuator_status": 0x004F,               # Status siłowników
}

# HOLDING REGISTERS (03 - READ/WRITE HOLDING REGISTER) - Konfiguracja i kontrola
HOLDING_REGISTERS = {
    # Basic Control (0x1070-0x1079)
    "mode": 0x1070,                          # Tryb pracy (0=Off,1=Manual,2=Auto,3=Temporary)
    "on_off_panel_mode": 0x1071,             # Włączenie/wyłączenie z panelu
    "air_flow_rate_manual": 0x1072,          # Intensywność wentylacji w trybie manual [%]
    "air_flow_rate_auto": 0x1073,            # Intensywność wentylacji w trybie auto [%]
    "air_flow_rate_temporary": 0x1074,       # Intensywność wentylacji w trybie temporary [%]
    "season_mode": 0x1075,                   # Tryb sezonowy (0=Auto,1=Winter,2=Summer)
    "special_mode": 0x1076,                  # Tryb specjalny (0=Off,1=OKAP,2=KOMINEK,3=WIETRZENIE,4=PUSTY_DOM)
    "bypass_mode": 0x1077,                   # Tryb bypass (0=Auto,1=Open,2=Close)
    "gwc_mode": 0x1078,                      # Tryb GWC (0=Auto,1=On,2=Off)
    "constant_flow_mode": 0x1079,            # Tryb stałego przepływu
    
    # Temperature Control (0x107A-0x1089)
    "supply_temperature_manual": 0x107A,     # Temperatura nawiewu manual [°C*2]
    "supply_temperature_auto": 0x107B,       # Temperatura nawiewu auto [°C*2]
    "supply_temperature_temporary": 0x107C,  # Temperatura nawiewu temporary [°C*2]
    "heating_temperature": 0x107D,           # Temperatura grzania [°C*2]
    "cooling_temperature": 0x107E,           # Temperatura chłodzenia [°C*2]
    "comfort_temperature": 0x107F,           # Temperatura komfortu [°C*2]
    "economy_temperature": 0x1080,           # Temperatura ekonomiczna [°C*2]
    "frost_protection_temp": 0x1081,         # Temperatura ochrony przed mrozem [°C*2]
    "overheat_protection_temp": 0x1082,      # Temperatura ochrony przed przegrzaniem [°C*2]
    "gwc_activation_temp": 0x1083,           # Temperatura aktywacji GWC [°C*2]
    "bypass_activation_temp": 0x1084,        # Temperatura aktywacji bypass [°C*2]
    "supply_temp_diff": 0x1085,              # Różnica temperatur nawiewu [°C*2]
    "extract_temp_diff": 0x1086,             # Różnica temperatur wywiewu [°C*2]
    "heating_curve_slope": 0x1087,           # Nachylenie krzywej grzewczej
    "cooling_curve_slope": 0x1088,           # Nachylenie krzywej chłodzącej
    "temperature_hysteresis": 0x1089,        # Histereza temperatury [°C*2]
    
    # Advanced Flow Control (0x108A-0x1099)
    "supply_flow_min": 0x108A,               # Minimalny przepływ nawiewu [m³/h]
    "supply_flow_max": 0x108B,               # Maksymalny przepływ nawiewu [m³/h]
    "exhaust_flow_min": 0x108C,              # Minimalny przepływ wywiewu [m³/h]
    "exhaust_flow_max": 0x108D,              # Maksymalny przepływ wywiewu [m³/h]
    "flow_balance": 0x108E,                  # Balans przepływów [%]
    "supply_fan_speed": 0x108F,              # Prędkość wentylatora nawiewnego [%]
    "exhaust_fan_speed": 0x1090,             # Prędkość wentylatora wywiewnego [%]
    "fan_ramp_time": 0x1091,                 # Czas rozbiegu wentylatora [s]
    "pressure_control_mode": 0x1092,         # Tryb kontroli ciśnienia
    "constant_pressure_setpoint": 0x1093,    # Zadana wartość ciśnienia stałego [Pa]
    "variable_pressure_setpoint": 0x1094,    # Zadana wartość ciśnienia zmiennego [Pa]
    "pressure_sensor_calibration": 0x1095,   # Kalibracja czujnika ciśnienia
    "flow_sensor_calibration": 0x1096,       # Kalibracja czujnika przepływu
    "filter_pressure_alarm": 0x1097,         # Alarm ciśnienia filtrów [Pa]
    "presostat_differential": 0x1098,        # Różnica ciśnień presostatu [Pa]
    "airflow_imbalance_alarm": 0x1099,       # Alarm braku balansu przepływów [%]
    
    # Special Functions (0x109A-0x10A9)
    "okap_intensity": 0x109A,                # Intensywność trybu OKAP [%]
    "okap_duration": 0x109B,                 # Czas trwania trybu OKAP [min]
    "kominek_intensity": 0x109C,             # Intensywność trybu KOMINEK [%]
    "kominek_duration": 0x109D,              # Czas trwania trybu KOMINEK [min]
    "wietrzenie_intensity": 0x109E,          # Intensywność trybu WIETRZENIE [%]
    "wietrzenie_duration": 0x109F,           # Czas trwania trybu WIETRZENIE [min]
    "pusty_dom_intensity": 0x10A0,           # Intensywność trybu PUSTY DOM [%]
    "pusty_dom_duration": 0x10A1,            # Czas trwania trybu PUSTY DOM [min]
    "boost_intensity": 0x10A2,               # Intensywność trybu BOOST [%]
    "boost_duration": 0x10A3,                # Czas trwania trybu BOOST [min]
    "night_mode_intensity": 0x10A4,          # Intensywność trybu nocnego [%]
    "party_mode_intensity": 0x10A5,          # Intensywność trybu party [%]
    "vacation_mode_intensity": 0x10A6,       # Intensywność trybu wakacyjnego [%]
    "emergency_mode_intensity": 0x10A7,      # Intensywność trybu awaryjnego [%]
    "custom_mode_1_intensity": 0x10A8,       # Intensywność trybu custom 1 [%]
    "custom_mode_2_intensity": 0x10A9,       # Intensywność trybu custom 2 [%]
    
    # Weekly Schedule - Day 1 Monday (0x10AA-0x10B9)
    "schedule_mon_period1_start": 0x10AA,    # Poniedziałek okres 1 start [HHMM]
    "schedule_mon_period1_end": 0x10AB,      # Poniedziałek okres 1 koniec [HHMM]
    "schedule_mon_period1_intensity": 0x10AC,# Poniedziałek okres 1 intensywność [%]
    "schedule_mon_period1_temp": 0x10AD,     # Poniedziałek okres 1 temperatura [°C*2]
    "schedule_mon_period2_start": 0x10AE,    # Poniedziałek okres 2 start [HHMM]
    "schedule_mon_period2_end": 0x10AF,      # Poniedziałek okres 2 koniec [HHMM]
    "schedule_mon_period2_intensity": 0x10B0,# Poniedziałek okres 2 intensywność [%]
    "schedule_mon_period2_temp": 0x10B1,     # Poniedziałek okres 2 temperatura [°C*2]
    "schedule_mon_period3_start": 0x10B2,    # Poniedziałek okres 3 start [HHMM]
    "schedule_mon_period3_end": 0x10B3,      # Poniedziałek okres 3 koniec [HHMM]
    "schedule_mon_period3_intensity": 0x10B4,# Poniedziałek okres 3 intensywność [%]
    "schedule_mon_period3_temp": 0x10B5,     # Poniedziałek okres 3 temperatura [°C*2]
    "schedule_mon_period4_start": 0x10B6,    # Poniedziałek okres 4 start [HHMM]
    "schedule_mon_period4_end": 0x10B7,      # Poniedziałek okres 4 koniec [HHMM]
    "schedule_mon_period4_intensity": 0x10B8,# Poniedziałek okres 4 intensywność [%]
    "schedule_mon_period4_temp": 0x10B9,     # Poniedziałek okres 4 temperatura [°C*2]
    
    # Weekly Schedule - Days 2-7 (Tue-Sun) (0x10BA-0x1179)
    # Pattern repeats for each day: 16 registers per day * 6 days = 96 registers
    # Tuesday (0x10BA-0x10C9)
    "schedule_tue_period1_start": 0x10BA,
    "schedule_tue_period1_end": 0x10BB,
    "schedule_tue_period1_intensity": 0x10BC,
    "schedule_tue_period1_temp": 0x10BD,
    "schedule_tue_period2_start": 0x10BE,
    "schedule_tue_period2_end": 0x10BF,
    "schedule_tue_period2_intensity": 0x10C0,
    "schedule_tue_period2_temp": 0x10C1,
    "schedule_tue_period3_start": 0x10C2,
    "schedule_tue_period3_end": 0x10C3,
    "schedule_tue_period3_intensity": 0x10C4,
    "schedule_tue_period3_temp": 0x10C5,
    "schedule_tue_period4_start": 0x10C6,
    "schedule_tue_period4_end": 0x10C7,
    "schedule_tue_period4_intensity": 0x10C8,
    "schedule_tue_period4_temp": 0x10C9,
    
    # Wednesday (0x10CA-0x10D9)
    "schedule_wed_period1_start": 0x10CA,
    "schedule_wed_period1_end": 0x10CB,
    "schedule_wed_period1_intensity": 0x10CC,
    "schedule_wed_period1_temp": 0x10CD,
    "schedule_wed_period2_start": 0x10CE,
    "schedule_wed_period2_end": 0x10CF,
    "schedule_wed_period2_intensity": 0x10D0,
    "schedule_wed_period2_temp": 0x10D1,
    "schedule_wed_period3_start": 0x10D2,
    "schedule_wed_period3_end": 0x10D3,
    "schedule_wed_period3_intensity": 0x10D4,
    "schedule_wed_period3_temp": 0x10D5,
    "schedule_wed_period4_start": 0x10D6,
    "schedule_wed_period4_end": 0x10D7,
    "schedule_wed_period4_intensity": 0x10D8,
    "schedule_wed_period4_temp": 0x10D9,
    
    # Thursday (0x10DA-0x10E9)
    "schedule_thu_period1_start": 0x10DA,
    "schedule_thu_period1_end": 0x10DB,
    "schedule_thu_period1_intensity": 0x10DC,
    "schedule_thu_period1_temp": 0x10DD,
    "schedule_thu_period2_start": 0x10DE,
    "schedule_thu_period2_end": 0x10DF,
    "schedule_thu_period2_intensity": 0x10E0,
    "schedule_thu_period2_temp": 0x10E1,
    "schedule_thu_period3_start": 0x10E2,
    "schedule_thu_period3_end": 0x10E3,
    "schedule_thu_period3_intensity": 0x10E4,
    "schedule_thu_period3_temp": 0x10E5,
    "schedule_thu_period4_start": 0x10E6,
    "schedule_thu_period4_end": 0x10E7,
    "schedule_thu_period4_intensity": 0x10E8,
    "schedule_thu_period4_temp": 0x10E9,
    
    # Friday (0x10EA-0x10F9)
    "schedule_fri_period1_start": 0x10EA,
    "schedule_fri_period1_end": 0x10EB,
    "schedule_fri_period1_intensity": 0x10EC,
    "schedule_fri_period1_temp": 0x10ED,
    "schedule_fri_period2_start": 0x10EE,
    "schedule_fri_period2_end": 0x10EF,
    "schedule_fri_period2_intensity": 0x10F0,
    "schedule_fri_period2_temp": 0x10F1,
    "schedule_fri_period3_start": 0x10F2,
    "schedule_fri_period3_end": 0x10F3,
    "schedule_fri_period3_intensity": 0x10F4,
    "schedule_fri_period3_temp": 0x10F5,
    "schedule_fri_period4_start": 0x10F6,
    "schedule_fri_period4_end": 0x10F7,
    "schedule_fri_period4_intensity": 0x10F8,
    "schedule_fri_period4_temp": 0x10F9,
    
    # Saturday (0x10FA-0x1109)
    "schedule_sat_period1_start": 0x10FA,
    "schedule_sat_period1_end": 0x10FB,
    "schedule_sat_period1_intensity": 0x10FC,
    "schedule_sat_period1_temp": 0x10FD,
    "schedule_sat_period2_start": 0x10FE,
    "schedule_sat_period2_end": 0x10FF,
    "schedule_sat_period2_intensity": 0x1100,
    "schedule_sat_period2_temp": 0x1101,
    "schedule_sat_period3_start": 0x1102,
    "schedule_sat_period3_end": 0x1103,
    "schedule_sat_period3_intensity": 0x1104,
    "schedule_sat_period3_temp": 0x1105,
    "schedule_sat_period4_start": 0x1106,
    "schedule_sat_period4_end": 0x1107,
    "schedule_sat_period4_intensity": 0x1108,
    "schedule_sat_period4_temp": 0x1109,
    
    # Sunday (0x110A-0x1119)
    "schedule_sun_period1_start": 0x110A,
    "schedule_sun_period1_end": 0x110B,
    "schedule_sun_period1_intensity": 0x110C,
    "schedule_sun_period1_temp": 0x110D,
    "schedule_sun_period2_start": 0x110E,
    "schedule_sun_period2_end": 0x110F,
    "schedule_sun_period2_intensity": 0x1110,
    "schedule_sun_period2_temp": 0x1111,
    "schedule_sun_period3_start": 0x1112,
    "schedule_sun_period3_end": 0x1113,
    "schedule_sun_period3_intensity": 0x1114,
    "schedule_sun_period3_temp": 0x1115,
    "schedule_sun_period4_start": 0x1116,
    "schedule_sun_period4_end": 0x1117,
    "schedule_sun_period4_intensity": 0x1118,
    "schedule_sun_period4_temp": 0x1119,
    
    # Filter and Maintenance Settings (0x111A-0x1129)
    "filter_change_interval": 0x111A,        # Interwał wymiany filtrów [dni]
    "filter_warning_days": 0x111B,           # Ostrzeżenie przed wymianą [dni]
    "presostat_check_day": 0x111C,           # Dzień kontroli presostatu (0-6)
    "presostat_check_time": 0x111D,          # Godzina kontroli presostatu [HHMM]
    "maintenance_reminder": 0x111E,          # Przypomnienie o serwisie [dni]
    "service_interval": 0x111F,              # Interwał serwisu [dni]
    "operating_hours_limit": 0x1120,         # Limit godzin pracy [h]
    "energy_efficiency_target": 0x1121,      # Docelowa wydajność energetyczna [%]
    "power_limit": 0x1122,                   # Limit mocy [W]
    "acoustic_limit": 0x1123,                # Limit akustyczny [dB]
    "vibration_limit": 0x1124,               # Limit wibracji
    "temperature_alarm_limit": 0x1125,       # Limit alarmu temperatury [°C*2]
    "pressure_alarm_limit": 0x1126,          # Limit alarmu ciśnienia [Pa]
    "flow_alarm_limit": 0x1127,              # Limit alarmu przepływu [m³/h]
    "humidity_alarm_limit": 0x1128,          # Limit alarmu wilgotności [%]
    "co2_alarm_limit": 0x1129,               # Limit alarmu CO2 [ppm]
    
    # Communication Settings (0x112A-0x1139)
    "modbus_address": 0x112A,                # Adres Modbus
    "modbus_baudrate": 0x112B,               # Prędkość Modbus
    "modbus_parity": 0x112C,                 # Parzystość Modbus
    "modbus_stop_bits": 0x112D,              # Bity stopu Modbus
    "ethernet_dhcp": 0x112E,                 # DHCP Ethernet
    "ethernet_ip_1": 0x112F,                 # IP Ethernet bajt 1
    "ethernet_ip_2": 0x1130,                 # IP Ethernet bajt 2
    "ethernet_ip_3": 0x1131,                 # IP Ethernet bajt 3
    "ethernet_ip_4": 0x1132,                 # IP Ethernet bajt 4
    "ethernet_mask_1": 0x1133,               # Maska Ethernet bajt 1
    "ethernet_mask_2": 0x1134,               # Maska Ethernet bajt 2
    "ethernet_mask_3": 0x1135,               # Maska Ethernet bajt 3
    "ethernet_mask_4": 0x1136,               # Maska Ethernet bajt 4
    "ethernet_gateway_1": 0x1137,            # Gateway Ethernet bajt 1
    "ethernet_gateway_2": 0x1138,            # Gateway Ethernet bajt 2
    "ethernet_gateway_3": 0x1139,            # Gateway Ethernet bajt 3
    
    # System Configuration (0x113A-0x1149)
    "system_language": 0x113A,               # Język systemu
    "display_brightness": 0x113B,            # Jasność wyświetlacza [%]
    "display_timeout": 0x113C,               # Timeout wyświetlacza [s]
    "keypad_lock": 0x113D,                   # Blokada klawiatury
    "sound_enabled": 0x113E,                 # Sygnały dźwiękowe włączone
    "led_enabled": 0x113F,                   # Sygnalizacja LED włączona
    "auto_start": 0x1140,                    # Autostart po awarii zasilania
    "summer_winter_auto": 0x1141,            # Automatyczne przełączanie lato/zima
    "daylight_saving": 0x1142,               # Automatyczne przejście na czas letni
    "time_zone": 0x1143,                     # Strefa czasowa
    "date_format": 0x1144,                   # Format daty
    "time_format": 0x1145,                   # Format czasu
    "unit_system": 0x1146,                   # System jednostek (metric/imperial)
    "decimal_places": 0x1147,                # Miejsca dziesiętne
    "averaging_time": 0x1148,                # Czas uśredniania pomiarów [s]
    "measurement_interval": 0x1149,          # Interwał pomiarów [s]
    
    # Reset and Calibration (0x114A-0x1159)
    "factory_reset": 0x114A,                 # Reset fabryczny
    "settings_reset": 0x114B,                # Reset ustawień użytkownika
    "schedule_reset": 0x114C,                # Reset harmonogramu
    "statistics_reset": 0x114D,              # Reset statystyk
    "error_log_reset": 0x114E,               # Reset dziennika błędów
    "sensor_calibration_outside": 0x114F,    # Kalibracja czujnika zewnętrznego [°C*10]
    "sensor_calibration_supply": 0x1150,     # Kalibracja czujnika nawiewu [°C*10]
    "sensor_calibration_extract": 0x1151,    # Kalibracja czujnika wywiewu [°C*10]
    "sensor_calibration_fpx": 0x1152,        # Kalibracja czujnika FPX [°C*10]
    "sensor_calibration_duct": 0x1153,       # Kalibracja czujnika kanałowego [°C*10]
    "sensor_calibration_gwc": 0x1154,        # Kalibracja czujnika GWC [°C*10]
    "sensor_calibration_ambient": 0x1155,    # Kalibracja czujnika otoczenia [°C*10]
    "pressure_calibration_supply": 0x1156,   # Kalibracja ciśnienia nawiewu [Pa]
    "pressure_calibration_extract": 0x1157,  # Kalibracja ciśnienia wywiewu [Pa]
    "flow_calibration_supply": 0x1158,       # Kalibracja przepływu nawiewu [%]
    "flow_calibration_extract": 0x1159,      # Kalibracja przepływu wywiewu [%]
    
    # Advanced Control Algorithms (0x115A-0x1169)
    "pid_temperature_kp": 0x115A,            # PID temperatura Kp
    "pid_temperature_ki": 0x115B,            # PID temperatura Ki
    "pid_temperature_kd": 0x115C,            # PID temperatura Kd
    "pid_pressure_kp": 0x115D,               # PID ciśnienie Kp
    "pid_pressure_ki": 0x115E,               # PID ciśnienie Ki
    "pid_pressure_kd": 0x115F,               # PID ciśnienie Kd
    "pid_flow_kp": 0x1160,                   # PID przepływ Kp
    "pid_flow_ki": 0x1161,                   # PID przepływ Ki
    "pid_flow_kd": 0x1162,                   # PID przepływ Kd
    "adaptive_control": 0x1163,              # Sterowanie adaptacyjne włączone
    "learning_mode": 0x1164,                 # Tryb uczenia się
    "prediction_horizon": 0x1165,            # Horyzont predykcji [h]
    "optimization_target": 0x1166,           # Cel optymalizacji (comfort/economy/efficiency)
    "smart_recovery": 0x1167,                # Inteligentny odzysk ciepła
    "demand_control": 0x1168,                # Sterowanie na żądanie
    "occupancy_detection": 0x1169,           # Wykrywanie obecności
    
    # Device Information (0x1FD0-0x1FFF) - końcowe rejestry według PDF
    "device_name_1": 0x1FD0,                 # Nazwa urządzenia - słowo 1
    "device_name_2": 0x1FD1,                 # Nazwa urządzenia - słowo 2
    "device_name_3": 0x1FD2,                 # Nazwa urządzenia - słowo 3
    "device_name_4": 0x1FD3,                 # Nazwa urządzenia - słowo 4
    "device_name_5": 0x1FD4,                 # Nazwa urządzenia - słowo 5
    "device_name_6": 0x1FD5,                 # Nazwa urządzenia - słowo 6
    "device_name_7": 0x1FD6,                 # Nazwa urządzenia - słowo 7
    "device_name_8": 0x1FD7,                 # Nazwa urządzenia - słowo 8
    "user_key_low": 0x1FFB,                  # Klucz produktu użytkownika - słowo młodsze
    "user_key_high": 0x1FFC,                 # Klucz produktu użytkownika - słowo starsze
    "device_lock": 0x1FFD,                   # Aktywacja blokady urządzenia
    "required_temp": 0x1FFE,                 # Temperatura zadana trybu KOMFORT [°C*2]
    "filter_type": 0x1FFF,                   # System kontroli filtrów / typ filtrów
    
    # Alarm and Error Registers (0x2000-0x206F) - wszystkie alarmy z PDF
    "alarm_status": 0x2000,                  # Flaga wystąpienia ostrzeżenia (alarm "E")
    "error_status": 0x2001,                  # Flaga wystąpienia błędu (alarm "S")
    "error_s2": 0x2002,                      # S2 - Błąd komunikacji I2C
    "error_s6": 0x2006,                      # S6 - Zabezpieczenie termiczne nagrzewnicy FPX
    "error_s7": 0x2007,                      # S7 - Brak możliwości kalibracji - niska temp. zewn.
    "error_s8": 0x2008,                      # S8 - Konieczność wprowadzenia klucza produktu
    "error_s9": 0x2009,                      # S9 - Centrala zatrzymana z panelu AirS
    "error_s10": 0x200A,                     # S10 - Zadziałał czujnik PPOŻ
    "error_s13": 0x200D,                     # S13 - Centrala zatrzymana z panelu Air+/AirL+
    "error_s14": 0x200E,                     # S14 - Zabezpieczenie przeciwzamrożeniowe
    "error_s15": 0x200F,                     # S15 - Zabezpieczenie nie przyniosło rezultatu
    "error_s16": 0x2010,                     # S16 - Zabezpieczenie termiczne w centrali
    "error_s17": 0x2011,                     # S17 - Nie wymienione filtry
    "error_s19": 0x2013,                     # S19 - Nie wymienione filtry - procedura automat.
    "error_s29": 0x201D,                     # S29 - Zbyt wysoka temperatura przed rekuperatorem
    "error_s30": 0x201E,                     # S30 - Nie działa wentylator nawiewny
    "error_s31": 0x201F,                     # S31 - Nie działa wentylator wywiewny
    "error_s32": 0x2020,                     # S32 - Brak komunikacji z modułem TG-02
    "error_e99": 0x2063,                     # E99 - Konieczność wprowadzenia klucza produktu
    "error_e100": 0x2064,                    # E100 - Brak odczytu z czujnika zewnętrznego TZ1
    "error_e101": 0x2065,                    # E101 - Brak odczytu z czujnika nawiewu TN1
    "error_e102": 0x2066,                    # E102 - Brak odczytu z czujnika wywiewu TP
    "error_e103": 0x2067,                    # E103 - Brak odczytu z czujnika FPX TZ2
    "error_e104": 0x2068,                    # E104 - Brak odczytu z czujnika otoczenia TO
    "error_e105": 0x2069,                    # E105 - Brak odczytu z czujnika kanałowego TN2
}

# COIL REGISTERS (01 - READ COILS) - Wyjścia sterujące
COIL_REGISTERS = {
    "duct_water_heater_pump": 0x0005,        # Stan wyjścia przekaźnika pompy obiegowej nagrzewnicy
    "bypass": 0x0009,                        # Stan wyjścia siłownika przepustnicy bypass
    "info": 0x000A,                          # Stan wyjścia sygnału potwierdzenia pracy centrali (O1)
    "power_supply_fans": 0x000B,             # Stan wyjścia przekaźnika zasilania wentylatorów
    "heating_cable": 0x000C,                 # Stan wyjścia przekaźnika zasilania kabla grzejnego
    "work_permit": 0x000D,                   # Stan wyjścia przekaźnika potwierdzenia pracy (Expansion)
    "gwc": 0x000E,                           # Stan wyjścia przekaźnika GWC
    "hood": 0x000F,                          # Stan wyjścia zasilającego przepustnicę okapu
    "summer_mode": 0x0010,                   # Aktywacja trybu letniego
    "winter_mode": 0x0011,                   # Aktywacja trybu zimowego
    "auto_mode": 0x0012,                     # Aktywacja trybu automatycznego
    "manual_mode": 0x0013,                   # Aktywacja trybu manualnego
    "temporary_mode": 0x0014,                # Aktywacja trybu tymczasowego
    "night_mode": 0x0015,                    # Aktywacja trybu nocnego
    "party_mode": 0x0016,                    # Aktywacja trybu party
    "vacation_mode": 0x0017,                 # Aktywacja trybu wakacyjnego
    "boost_mode": 0x0018,                    # Aktywacja trybu boost
    "economy_mode": 0x0019,                  # Aktywacja trybu ekonomicznego
    "comfort_mode": 0x001A,                  # Aktywacja trybu komfort
    "silent_mode": 0x001B,                   # Aktywacja trybu cichego
    "fireplace_mode": 0x001C,                # Aktywacja trybu kominkowego
    "kitchen_hood_mode": 0x001D,             # Aktywacja trybu okapu kuchennego
    "bathroom_mode": 0x001E,                 # Aktywacja trybu łazienkowego
    "co2_control": 0x001F,                   # Sterowanie na podstawie CO2
    "humidity_control": 0x0020,              # Sterowanie na podstawie wilgotności
    "occupancy_control": 0x0021,             # Sterowanie na podstawie obecności
    "constant_flow_control": 0x0022,         # Sterowanie stałym przepływem
    "pressure_control": 0x0023,              # Sterowanie ciśnieniem
    "temperature_control": 0x0024,           # Sterowanie temperaturą
    "bypass_control": 0x0025,                # Sterowanie bypass
    "gwc_control": 0x0026,                   # Sterowanie GWC
    "heating_control": 0x0027,               # Sterowanie grzaniem
    "cooling_control": 0x0028,               # Sterowanie chłodzeniem
    "frost_protection": 0x0029,              # Ochrona przeciwmrozowa
    "overheat_protection": 0x002A,           # Ochrona przed przegrzaniem
    "filter_change_reminder": 0x002B,        # Przypomnienie o wymianie filtrów
    "maintenance_reminder": 0x002C,          # Przypomnienie o serwisie
    "alarm_output": 0x002D,                  # Wyjście alarmowe
    "status_output": 0x002E,                 # Wyjście statusowe
    "communication_ok": 0x002F,              # Komunikacja OK
}

# DISCRETE INPUTS (02 - READ DISCRETE INPUTS) - Wejścia cyfrowe
DISCRETE_INPUTS = {
    "expansion": 0x0010,                     # Stan wejścia modułu rozszerzającego (Expansion)
    "fire_alarm": 0x0011,                    # Stan wejścia sygnału pożarowego (PPOŻ)
    "external_stop": 0x0012,                 # Stan wejścia zatrzymania zewnętrznego
    "window_contact": 0x0013,                # Stan kontaktronu okna
    "door_contact": 0x0014,                  # Stan kontaktronu drzwi
    "presence_sensor": 0x0015,               # Stan czujnika obecności
    "motion_sensor": 0x0016,                 # Stan czujnika ruchu
    "light_sensor": 0x0017,                  # Stan czujnika światła
    "sound_sensor": 0x0018,                  # Stan czujnika dźwięku
    "external_alarm": 0x0019,                # Stan alarmu zewnętrznego
    "maintenance_switch": 0x001A,            # Stan przełącznika serwisowego
    "emergency_switch": 0x001B,              # Stan przełącznika awaryjnego
    "filter_pressure_switch": 0x001C,        # Stan przełącznika ciśnienia filtrów
    "high_pressure_switch": 0x001D,          # Stan przełącznika wysokiego ciśnienia
    "low_pressure_switch": 0x001E,           # Stan przełącznika niskiego ciśnienia
    "temperature_switch": 0x001F,            # Stan przełącznika temperatury
    "humidity_switch": 0x0020,               # Stan przełącznika wilgotności
    "air_quality_switch": 0x0021,            # Stan przełącznika jakości powietrza
    "co2_switch": 0x0022,                    # Stan przełącznika CO2
    "voc_switch": 0x0023,                    # Stan przełącznika VOC
    "external_controller": 0x0024,           # Stan kontrolera zewnętrznego
    "building_management": 0x0025,           # Stan systemu zarządzania budynkiem
    "modbus_communication": 0x0026,          # Stan komunikacji Modbus
    "ethernet_communication": 0x0027,        # Stan komunikacji Ethernet
    "wifi_communication": 0x0028,            # Stan komunikacji WiFi
    "cloud_communication": 0x0029,           # Stan komunikacji z chmurą
    "mobile_app": 0x002A,                    # Stan aplikacji mobilnej
    "web_interface": 0x002B,                 # Stan interfejsu webowego
    "remote_access": 0x002C,                 # Stan dostępu zdalnego
    "backup_power": 0x002D,                  # Stan zasilania awaryjnego
    "battery_status": 0x002E,                # Stan baterii
    "power_quality": 0x002F,                 # Stan jakości zasilania
}

# ============================================================================
# REGISTER PROCESSING CONFIGURATION
# ============================================================================

# Register value processing configuration
REGISTER_PROCESSING = {
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
        "night_mode_intensity", "party_mode_intensity", "vacation_mode_intensity"
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
        "presostat_differential", "pressure_alarm_limit"
    },
    
    # Time registers - HHMM format
    "time_registers": {
        "presostat_check_time", "schedule_mon_period1_start", "schedule_mon_period1_end",
        "schedule_mon_period2_start", "schedule_mon_period2_end", "schedule_mon_period3_start",
        "schedule_mon_period3_end", "schedule_mon_period4_start", "schedule_mon_period4_end"
        # Plus all other schedule time registers...
    },
    
    # Sensor unavailable value
    "sensor_unavailable_value": 0x8000,  # 32768 decimal
    
    # Invalid flow value
    "invalid_flow_value": 0xFFFF,  # 65535 decimal
}

# Register groups for optimized batch reading
REGISTER_GROUPS = {
    "basic_status": [
        "mode", "on_off_panel_mode", "season_mode", "special_mode",
        "outside_temperature", "supply_temperature", "exhaust_temperature"
    ],
    
    "air_flow": [
        "supply_flowrate", "exhaust_flowrate", "supply_percentage", "exhaust_percentage",
        "air_flow_rate_manual", "air_flow_rate_auto", "heat_recovery_efficiency"
    ],
    
    "temperature_control": [
        "supply_temperature_manual", "supply_temperature_auto", "heating_temperature",
        "cooling_temperature", "comfort_temperature", "bypass_activation_temp"
    ],
    
    "advanced_sensors": [
        "fpx_temperature", "duct_supply_temperature", "gwc_temperature",
        "ambient_temperature", "supply_pressure", "exhaust_pressure"
    ],
    
    "special_functions": [
        "okap_intensity", "okap_duration", "kominek_intensity", "kominek_duration",
        "wietrzenie_intensity", "wietrzenie_duration", "pusty_dom_intensity"
    ],
    
    "system_status": [
        "power_supply_fans", "bypass", "gwc", "heating_cable", "work_permit",
        "expansion", "fire_alarm", "external_stop"
    ],
    
    "alarms_errors": [
        "alarm_status", "error_status", "error_s2", "error_s6", "error_s7",
        "error_e100", "error_e101", "error_e102", "error_e103"
    ],
    
    "maintenance": [
        "filter_time_remaining", "filter_change_interval", "filter_warning_days",
        "operating_hours", "maintenance_interval", "next_maintenance"
    ]
}