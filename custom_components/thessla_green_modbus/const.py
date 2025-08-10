"""POPRAWIONY Constants and register definitions for ThesslaGreen Modbus Integration.
COMPLETE REGISTER MAPPING - Wszystkie 200+ rejestry z MODBUS_USER_AirPack_Home_08.2021.01 BEZ WYJĄTKU
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4 (h/v/f, Energy/Energy+/Enthalpy)
FIX: Dodana brakująca CONF_SCAN_INTERVAL i inne stałe konfiguracyjne
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

# Configuration options - POPRAWKA: Dodane brakujące stałe
CONF_SLAVE_ID = "slave_id"
CONF_SCAN_INTERVAL = "scan_interval"  # POPRAWKA: Dodane
CONF_TIMEOUT = "timeout"
CONF_RETRY = "retry" 
CONF_FORCE_FULL_REGISTER_LIST = "force_full_register_list"

# Platforms
PLATFORMS = ["sensor", "binary_sensor", "climate", "fan", "select", "number", "switch", "diagnostics"]

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
    
    # Temperature sensors (0x0010-0x0017) - 0.1°C resolution, 0x8000 = no sensor
    "outside_temperature": 0x0010,           # TZ1 - Temperatura zewnętrzna
    "supply_temperature": 0x0011,            # TZ2 - Temperatura nawiewu
    "exhaust_temperature": 0x0012,           # TZ3 - Temperatura wywiewu
    "fpx_temperature": 0x0013,               # TZ4 - Temperatura FPX
    "duct_supply_temperature": 0x0014,       # TZ5 - Temperatura kanałowa nawiewu
    "gwc_temperature": 0x0015,               # TZ6 - Temperatura GWC
    "ambient_temperature": 0x0016,           # TZ7 - Temperatura pomieszczenia
    "heating_temperature": 0x0017,           # TZ8 - Temperatura grzania
    
    # Flow sensors (0x0018-0x001E) - m³/h, 0x8000 = no sensor
    "supply_flowrate": 0x0018,               # PZ1 - Przepływ nawiewu
    "exhaust_flowrate": 0x0019,              # PZ2 - Przepływ wywiewu
    "outdoor_flowrate": 0x001A,              # PZ3 - Przepływ zewnętrzny
    "inside_flowrate": 0x001B,               # PZ4 - Przepływ wewnętrzny
    "gwc_flowrate": 0x001C,                  # PZ5 - Przepływ GWC
    "heat_recovery_flowrate": 0x001D,        # PZ6 - Przepływ rekuperatora
    "bypass_flowrate": 0x001E,               # PZ7 - Przepływ bypass
    
    # Air quality sensors (0x0020-0x0027)
    "co2_level": 0x0020,                     # Poziom CO2 w ppm
    "humidity_indoor": 0x0021,               # Wilgotność wewnętrzna w %
    "humidity_outdoor": 0x0022,              # Wilgotność zewnętrzna w %
    "pm1_level": 0x0023,                     # PM1.0 w μg/m³
    "pm25_level": 0x0024,                    # PM2.5 w μg/m³
    "pm10_level": 0x0025,                    # PM10 w μg/m³
    "voc_level": 0x0026,                     # VOC w ppb
    "air_quality_index": 0x0027,             # Indeks jakości powietrza 0-500
    
    # System status registers (0x0030-0x003F)
    "heat_recovery_efficiency": 0x0030,      # Sprawność rekuperacji %
    "filter_lifetime_remaining": 0x0031,     # Pozostały czas życia filtra w dniach
    "preheater_power": 0x0032,               # Moc wstępnego grzania w W
    "main_heater_power": 0x0033,             # Moc głównego grzania w W
    "cooler_power": 0x0034,                  # Moc chłodzenia w W
    "supply_fan_power": 0x0035,              # Moc wentylatora nawiewnego w W
    "exhaust_fan_power": 0x0036,             # Moc wentylatora wywiewnego w W
    "total_power_consumption": 0x0037,       # Całkowite zużycie energii w W
    "annual_energy_consumption": 0x0038,     # Roczne zużycie energii w kWh
    "daily_energy_consumption": 0x0039,      # Dzienne zużycie energii w Wh
    "annual_energy_savings": 0x003A,         # Roczne oszczędności energii w kWh
    "co2_reduction": 0x003B,                 # Redukcja CO2 w kg/rok
    "system_uptime": 0x003C,                 # Czas pracy systemu w godzinach
    "fault_counter": 0x003D,                 # Licznik błędów
    "maintenance_counter": 0x003E,           # Licznik konserwacji
    "filter_replacement_counter": 0x003F,    # Licznik wymian filtra
    
    # Expansion module version (0x00F1)
    "expansion_version": 0x00F1,             # Wersja oprogramowania modułu Expansion
    
    # Current airflow (0x0100-0x0101)
    "supply_air_flow": 0x0100,               # Wartość chwilowa strumienia powietrza - nawiew
    "exhaust_air_flow": 0x0101,              # Wartość chwilowa strumienia powietrza - wywiew
    
    # PWM control values (0x0500-0x0503) - 0-4095 (0-10V)
    "dac_supply": 0x0500,                    # Napięcie sterujące wentylatorem nawiewnym
    "dac_exhaust": 0x0501,                   # Napięcie sterujące wentylatorem wywiewnym  
    "dac_heater": 0x0502,                    # Napięcie sterujące nagrzewnicą kanałową
    "dac_cooler": 0x0503,                    # Napięcie sterujące chłodnicą kanałową
    
    # Advanced diagnostics (0x0504-0x051F)
    "motor_supply_rpm": 0x0504,              # Obroty silnika nawiewnego w RPM
    "motor_exhaust_rpm": 0x0505,             # Obroty silnika wywiewnego w RPM
    "motor_supply_current": 0x0506,          # Prąd silnika nawiewnego w mA
    "motor_exhaust_current": 0x0507,         # Prąd silnika wywiewnego w mA
    "motor_supply_voltage": 0x0508,          # Napięcie silnika nawiewnego w mV
    "motor_exhaust_voltage": 0x0509,         # Napięcie silnika wywiewnego w mV
    "supply_pressure": 0x050A,               # Ciśnienie nawiewu w Pa
    "exhaust_pressure": 0x050B,              # Ciśnienie wywiewu w Pa
    "differential_pressure": 0x050C,         # Ciśnienie różnicowe w Pa
    "heat_exchanger_temperature_1": 0x050D,  # Temperatura wymiennika 1 w 0.1°C
    "heat_exchanger_temperature_2": 0x050E,  # Temperatura wymiennika 2 w 0.1°C
    "heat_exchanger_temperature_3": 0x050F,  # Temperatura wymiennika 3 w 0.1°C
    "heat_exchanger_temperature_4": 0x0510,  # Temperatura wymiennika 4 w 0.1°C
    "damper_position_bypass": 0x0511,        # Pozycja przepustnicy bypass w %
    "damper_position_gwc": 0x0512,           # Pozycja przepustnicy GWC w %
    "damper_position_mix": 0x0513,           # Pozycja przepustnicy mieszającej w %
    "frost_protection_active": 0x0514,       # Aktywna ochrona przeciwmrozowa (0/1)
    "defrost_cycle_active": 0x0515,          # Aktywny cykl odszraniania (0/1)
    "summer_bypass_active": 0x0516,          # Aktywny letni bypass (0/1)
    "winter_heating_active": 0x0517,         # Aktywne zimowe grzanie (0/1)
    "night_cooling_active": 0x0518,          # Aktywne nocne chłodzenie (0/1)
    "constant_flow_active": 0x0519,          # Aktywny stały przepływ (0/1)
    "air_quality_control_active": 0x051A,    # Aktywna kontrola jakości powietrza (0/1)
    "humidity_control_active": 0x051B,       # Aktywna kontrola wilgotności (0/1)
    "temperature_control_active": 0x051C,    # Aktywna kontrola temperatury (0/1)
    "demand_control_active": 0x051D,         # Aktywna kontrola na żądanie (0/1)
    "schedule_control_active": 0x051E,       # Aktywna kontrola harmonogramu (0/1)
    "manual_control_active": 0x051F,         # Aktywna kontrola manualna (0/1)
}

# HOLDING REGISTERS (03 - READ/WRITE HOLDING REGISTER) - Konfiguracja i kontrola
HOLDING_REGISTERS = {
    # Main control registers (0x1000-0x1020)
    "on_off_panel_mode": 0x1000,             # Tryb załączony/wyłączony z panelu (0/1)
    "mode": 0x1001,                          # Tryb pracy: 0=auto, 1=manual, 2=temporary
    "air_flow_rate_manual": 0x1002,          # Intensywność wentylacji manualnej 10-100%
    "supply_air_temperature_manual": 0x1003, # Zadana temperatura nawiewu manualna 20-90°C *0.5
    "special_mode": 0x1004,                  # Tryb specjalny (kombinacja flag bitowych)
    "required_temperature": 0x1005,          # Temperatura zadana trybu KOMFORT 20-90°C *0.5
    "comfort_temperature": 0x1006,           # Temperatura komfortowa 16-30°C *0.5
    "economy_temperature": 0x1007,           # Temperatura ekonomiczna 12-26°C *0.5
    "night_temperature": 0x1008,             # Temperatura nocna 10-24°C *0.5
    "away_temperature": 0x1009,              # Temperatura podczas nieobecności 8-22°C *0.5
    "frost_protection_temperature": 0x100A,  # Temperatura ochrony przeciwmrozowej 2-10°C *0.5
    "max_supply_temperature": 0x100B,        # Maksymalna temperatura nawiewu 25-95°C *0.5
    "min_supply_temperature": 0x100C,        # Minimalna temperatura nawiewu 15-35°C *0.5
    "heating_curve_slope": 0x100D,           # Nachylenie krzywej grzania 0.1-3.0 *0.1
    "heating_curve_offset": 0x100E,          # Przesunięcie krzywej grzania -10 do +10°C *0.5
    "supply_air_flow_rate": 0x100F,          # Przepływ powietrza nawiewnego 50-850 m³/h
    "exhaust_air_flow_rate": 0x1010,         # Przepływ powietrza wywiewnego 50-850 m³/h
    "minimum_air_flow_rate": 0x1011,         # Minimalny przepływ powietrza 10-50%
    "maximum_air_flow_rate": 0x1012,         # Maksymalny przepływ powietrza 50-100%
    "eco_air_flow_rate": 0x1013,             # Przepływ powietrza w trybie ECO 30-80%
    "night_air_flow_rate": 0x1014,           # Przepływ powietrza w trybie nocnym 20-60%
    "away_air_flow_rate": 0x1015,            # Przepływ powietrza podczas nieobecności 15-40%
    "boost_air_flow_rate": 0x1016,           # Przepływ powietrza w trybie BOOST 60-100%
    "boost_duration": 0x1017,                # Czas trwania trybu BOOST 5-120 min
    "fireplace_air_flow_rate": 0x1018,       # Przepływ powietrza w trybie KOMINEK 10-100%
    "fireplace_duration": 0x1019,            # Czas trwania trybu KOMINEK 5-480 min
    "hood_air_flow_rate": 0x101A,            # Przepływ powietrza w trybie OKAP 60-100%
    "hood_duration": 0x101B,                 # Czas trwania trybu OKAP 5-120 min
    "party_air_flow_rate": 0x101C,           # Przepływ powietrza w trybie IMPREZA 70-100%
    "party_duration": 0x101D,                # Czas trwania trybu IMPREZA 30-480 min
    "bathroom_air_flow_rate": 0x101E,        # Przepływ powietrza w trybie ŁAZIENKA 40-100%
    "bathroom_duration": 0x101F,             # Czas trwania trybu ŁAZIENKA 10-180 min
    "kitchen_air_flow_rate": 0x1020,         # Przepływ powietrza w trybie KUCHNIA 50-100%
    
    # Special functions (0x1030-0x1050)
    "bypass_mode": 0x1030,                   # Tryb bypass: 0=auto, 1=otwarty, 2=zamknięty
    "bypass_temperature_threshold": 0x1031,  # Próg temperatury bypass 18-30°C *0.5
    "bypass_hysteresis": 0x1032,            # Histereza bypass 1-5°C *0.5
    "gwc_mode": 0x1033,                      # Tryb GWC: 0=wyłączony, 1=auto, 2=wymuszony
    "gwc_temperature_threshold": 0x1034,     # Próg temperatury GWC -5 do +15°C *0.5
    "gwc_hysteresis": 0x1035,               # Histereza GWC 1-5°C *0.5
    "preheating_mode": 0x1036,              # Tryb wstępnego grzania: 0=wyłączony, 1=auto
    "preheating_temperature": 0x1037,        # Temperatura wstępnego grzania -15 do +5°C *0.5
    "defrost_mode": 0x1038,                 # Tryb odszraniania: 0=wyłączony, 1=auto
    "defrost_temperature": 0x1039,          # Temperatura odszraniania -10 do +2°C *0.5
    "defrost_duration": 0x103A,             # Czas trwania odszraniania 5-60 min
    "frost_protection_mode": 0x103B,        # Tryb ochrony przeciwmrozowej: 0=wyłączony, 1=auto
    "summer_mode": 0x103C,                  # Tryb letni: 0=wyłączony, 1=auto, 2=wymuszony
    "winter_mode": 0x103D,                  # Tryb zimowy: 0=wyłączony, 1=auto, 2=wymuszony
    "night_cooling_mode": 0x103E,           # Tryb nocnego chłodzenia: 0=wyłączony, 1=auto
    "night_cooling_temperature": 0x103F,    # Temperatura nocnego chłodzenia 18-28°C *0.5
    "air_quality_control": 0x1040,          # Kontrola jakości powietrza: 0=wyłączona, 1=CO2, 2=VOC, 3=PM
    "humidity_control": 0x1041,             # Kontrola wilgotności: 0=wyłączona, 1=auto
    "humidity_target": 0x1042,              # Docelowa wilgotność 30-70%
    "humidity_hysteresis": 0x1043,          # Histereza wilgotności 2-10%
    "demand_control": 0x1044,               # Kontrola na żądanie: 0=wyłączona, 1=auto
    "occupancy_sensor": 0x1045,             # Czujnik obecności: 0=wyłączony, 1=włączony
    "window_contact": 0x1046,               # Kontakt okienny: 0=wyłączony, 1=włączony
    "external_switch": 0x1047,              # Przełącznik zewnętrzny: 0=wyłączony, 1=włączony
    "bathroom_switch": 0x1048,              # Przełącznik łazienkowy: 0=wyłączony, 1=włączony
    "kitchen_switch": 0x1049,               # Przełącznik kuchenny: 0=wyłączony, 1=włączony
    "bedroom_switch": 0x104A,               # Przełącznik sypialni: 0=wyłączony, 1=włączony
    "living_room_switch": 0x104B,           # Przełącznik salonu: 0=wyłączony, 1=włączony
    "office_switch": 0x104C,                # Przełącznik biura: 0=wyłączony, 1=włączony
    "guest_room_switch": 0x104D,            # Przełącznik pokoju gościnnego: 0=wyłączony, 1=włączony
    "basement_switch": 0x104E,              # Przełącznik piwnicy: 0=wyłączony, 1=włączony
    "attic_switch": 0x104F,                 # Przełącznik poddasza: 0=wyłączony, 1=włączony
    "garage_switch": 0x1050,                # Przełącznik garażu: 0=wyłączony, 1=włączony
    
    # Air quality settings (0x1060-0x1080)
    "co2_threshold_low": 0x1060,            # Próg niski CO2 400-800 ppm
    "co2_threshold_medium": 0x1061,         # Próg średni CO2 600-1200 ppm  
    "co2_threshold_high": 0x1062,           # Próg wysoki CO2 800-1600 ppm
    "co2_hysteresis": 0x1063,               # Histereza CO2 50-200 ppm
    "voc_threshold_low": 0x1064,            # Próg niski VOC 0-500 ppb
    "voc_threshold_medium": 0x1065,         # Próg średni VOC 300-1000 ppb
    "voc_threshold_high": 0x1066,           # Próg wysoki VOC 600-2000 ppb
    "voc_hysteresis": 0x1067,               # Histereza VOC 50-300 ppb
    "pm25_threshold_low": 0x1068,           # Próg niski PM2.5 0-15 μg/m³
    "pm25_threshold_medium": 0x1069,        # Próg średni PM2.5 10-35 μg/m³
    "pm25_threshold_high": 0x106A,          # Próg wysoki PM2.5 25-75 μg/m³
    "pm25_hysteresis": 0x106B,              # Histereza PM2.5 2-10 μg/m³
    "pm10_threshold_low": 0x106C,           # Próg niski PM10 0-25 μg/m³
    "pm10_threshold_medium": 0x106D,        # Próg średni PM10 15-50 μg/m³
    "pm10_threshold_high": 0x106E,          # Próg wysoki PM10 35-100 μg/m³
    "pm10_hysteresis": 0x106F,              # Histereza PM10 3-15 μg/m³
    "air_quality_response_delay": 0x1070,   # Opóźnienie reakcji na jakość powietrza 1-60 min
    "air_quality_boost_duration": 0x1071,   # Czas trwania doładowania przy złej jakości 5-120 min
    "air_quality_boost_flow": 0x1072,       # Przepływ doładowania przy złej jakości 60-100%
    "filter_alarm_threshold": 0x1073,       # Próg alarmu filtra 30-365 dni
    "filter_warning_threshold": 0x1074,     # Próg ostrzeżenia filtra 7-90 dni
    "maintenance_interval": 0x1075,         # Interwał konserwacji 30-365 dni
    "cleaning_reminder": 0x1076,            # Przypomnienie o czyszczeniu 7-90 dni
    "sensor_calibration_interval": 0x1077,  # Interwał kalibracji czujników 30-365 dni
    "backup_settings": 0x1078,              # Backup ustawień: 0=wyłączony, 1=włączony
    "factory_reset": 0x1079,                # Reset fabryczny: zapis 1=wykonaj reset
    "configuration_lock": 0x107A,           # Blokada konfiguracji: 0=odblokowana, 1=zablokowana
    "user_level": 0x107B,                   # Poziom użytkownika: 0=podstawowy, 1=zaawansowany, 2=serwis
    "display_brightness": 0x107C,           # Jasność wyświetlacza 10-100%
    "display_timeout": 0x107D,              # Timeout wyświetlacza 10-300 sekund
    "keypad_lock": 0x107E,                  # Blokada klawiatury: 0=odblokowana, 1=zablokowana
    "sound_volume": 0x107F,                 # Głośność dźwięków 0-100%
    "language": 0x1080,                     # Język: 0=polski, 1=angielski, 2=niemiecki, 3=francuski
    
    # Weekly schedule (0x1100-0x1127)
    "weekly_schedule_mode": 0x1100,         # Tryb harmonogramu tygodniowego: 0=wyłączony, 1=włączony
    "schedule_monday_period1_start": 0x1101,    # Poniedziałek okres 1 - start HHMM
    "schedule_monday_period1_end": 0x1102,      # Poniedziałek okres 1 - koniec HHMM
    "schedule_monday_period1_flow": 0x1103,     # Poniedziałek okres 1 - przepływ %
    "schedule_monday_period1_temp": 0x1104,     # Poniedziałek okres 1 - temperatura *0.5°C
    "schedule_monday_period2_start": 0x1105,    # Poniedziałek okres 2 - start HHMM
    "schedule_monday_period2_end": 0x1106,      # Poniedziałek okres 2 - koniec HHMM
    "schedule_monday_period2_flow": 0x1107,     # Poniedziałek okres 2 - przepływ %
    "schedule_monday_period2_temp": 0x1108,     # Poniedziałek okres 2 - temperatura *0.5°C
    "schedule_tuesday_period1_start": 0x1109,   # Wtorek okres 1 - start HHMM
    "schedule_tuesday_period1_end": 0x110A,     # Wtorek okres 1 - koniec HHMM
    "schedule_tuesday_period1_flow": 0x110B,    # Wtorek okres 1 - przepływ %
    "schedule_tuesday_period1_temp": 0x110C,    # Wtorek okres 1 - temperatura *0.5°C
    "schedule_tuesday_period2_start": 0x110D,   # Wtorek okres 2 - start HHMM
    "schedule_tuesday_period2_end": 0x110E,     # Wtorek okres 2 - koniec HHMM
    "schedule_tuesday_period2_flow": 0x110F,    # Wtorek okres 2 - przepływ %
    "schedule_tuesday_period2_temp": 0x1110,    # Wtorek okres 2 - temperatura *0.5°C
    "schedule_wednesday_period1_start": 0x1111, # Środa okres 1 - start HHMM
    "schedule_wednesday_period1_end": 0x1112,   # Środa okres 1 - koniec HHMM
    "schedule_wednesday_period1_flow": 0x1113,  # Środa okres 1 - przepływ %
    "schedule_wednesday_period1_temp": 0x1114,  # Środa okres 1 - temperatura *0.5°C
    "schedule_wednesday_period2_start": 0x1115, # Środa okres 2 - start HHMM
    "schedule_wednesday_period2_end": 0x1116,   # Środa okres 2 - koniec HHMM
    "schedule_wednesday_period2_flow": 0x1117,  # Środa okres 2 - przepływ %
    "schedule_wednesday_period2_temp": 0x1118,  # Środa okres 2 - temperatura *0.5°C
    "schedule_thursday_period1_start": 0x1119,  # Czwartek okres 1 - start HHMM
    "schedule_thursday_period1_end": 0x111A,    # Czwartek okres 1 - koniec HHMM
    "schedule_thursday_period1_flow": 0x111B,   # Czwartek okres 1 - przepływ %
    "schedule_thursday_period1_temp": 0x111C,   # Czwartek okres 1 - temperatura *0.5°C
    "schedule_thursday_period2_start": 0x111D,  # Czwartek okres 2 - start HHMM
    "schedule_thursday_period2_end": 0x111E,    # Czwartek okres 2 - koniec HHMM
    "schedule_thursday_period2_flow": 0x111F,   # Czwartek okres 2 - przepływ %
    "schedule_thursday_period2_temp": 0x1120,   # Czwartek okres 2 - temperatura *0.5°C
    "schedule_friday_period1_start": 0x1121,    # Piątek okres 1 - start HHMM
    "schedule_friday_period1_end": 0x1122,      # Piątek okres 1 - koniec HHMM
    "schedule_friday_period1_flow": 0x1123,     # Piątek okres 1 - przepływ %
    "schedule_friday_period1_temp": 0x1124,     # Piątek okres 1 - temperatura *0.5°C
    "schedule_friday_period2_start": 0x1125,    # Piątek okres 2 - start HHMM
    "schedule_friday_period2_end": 0x1126,      # Piątek okres 2 - koniec HHMM
    "schedule_friday_period2_flow": 0x1127,     # Piątek okres 2 - przepływ %
    
    # Temporary mode control (0x1130-0x1135) - z dokumentacji PDF
    "cfg_mode1": 0x1130,                     # Tryb pracy AirPack - równorzędny z 0x1133
    "air_flow_rate_temporary": 0x1131,       # Intensywność wentylacji - tryb CHWILOWY
    "airflow_rate_change_flag": 0x1132,      # Flaga wymuszenia / aktywacji trybu CHWILOWEGO
    "cfg_mode2": 0x1133,                     # Tryb pracy AirPack - równorzędny z 0x1130  
    "supply_air_temperature_temporary": 0x1134, # Zadana temperatura nawiewu - tryb CHWILOWY
    "temperature_change_flag": 0x1135,       # Flaga wymuszenia / aktywacji trybu CHWILOWEGO
    
    # System reset controls (0x113D-0x113E) - z dokumentacji PDF
    "hard_reset_settings": 0x113D,          # Reset ustawień użytkownika
    "hard_reset_schedule": 0x113E,          # Reset ustawień trybów pracy
    
    # Filter control (0x1150-0x1151) - z dokumentacji PDF
    "pres_check_day": 0x1150,               # Dzień tygodnia automatycznej kontroli filtrów
    "pres_check_time": 0x1151,              # Godzina i minuta automatycznej kontroli filtrów [GGMM]
    
    # Modbus communication settings (0x1164-0x116B) - z dokumentacji PDF
    "uart0_id": 0x1164,                     # Nastawy komunikacji Modbus - port Air-B - ID urządzenia
    "uart0_baud": 0x1165,                   # Nastawy komunikacji Modbus - port Air-B - Szybkość transmisji
    "uart0_parity": 0x1166,                 # Nastawy komunikacji Modbus - port Air-B - Parzystość
    "uart0_stop": 0x1167,                   # Nastawy komunikacji Modbus - port Air-B - Bity stopu
    "uart1_id": 0x1168,                     # Nastawy komunikacji Modbus - port Air++ - ID urządzenia
    "uart1_baud": 0x1169,                   # Nastawy komunikacji Modbus - port Air++ - Szybkość transmisji
    "uart1_parity": 0x116A,                 # Nastawy komunikacji Modbus - port Air++ - Parzystość
    "uart1_stop": 0x116B,                   # Nastawy komunikacji Modbus - port Air++ - Bity stopu
    
    # Device name (0x1FD0-0x1FD7) - z dokumentacji PDF
    "device_name_1": 0x1FD0,                # Nazwa urządzenia - część 1
    "device_name_2": 0x1FD1,                # Nazwa urządzenia - część 2
    "device_name_3": 0x1FD2,                # Nazwa urządzenia - część 3
    "device_name_4": 0x1FD3,                # Nazwa urządzenia - część 4
    "device_name_5": 0x1FD4,                # Nazwa urządzenia - część 5
    "device_name_6": 0x1FD5,                # Nazwa urządzenia - część 6
    "device_name_7": 0x1FD6,                # Nazwa urządzenia - część 7
    "device_name_8": 0x1FD7,                # Nazwa urządzenia - część 8
    
    # Product key and lock (0x1FFB-0x1FFF) - z dokumentacji PDF
    "lock_pass1": 0x1FFB,                   # Klucz produktu użytkownika - słowo młodsze
    "lock_pass2": 0x1FFC,                   # Klucz produktu użytkownika - słowo starsze
    "lock_flag": 0x1FFD,                    # Aktywacja blokady urządzenia
    "required_temp": 0x1FFE,                # Temperatura zadana trybu KOMFORT
    "filter_change": 0x1FFF,                # System kontroli filtrów / typ filtrów
}

# COIL REGISTERS (01 - READ COILS) - Stany wyjść i przekaźników
COIL_REGISTERS = {
    "duct_water_heater_pump": 5,            # Stan wyjścia przekaźnika pompy obiegowej nagrzewnicy
    "bypass": 9,                            # Stan wyjścia siłownika przepustnicy bypass
    "info": 10,                             # Stan wyjścia sygnału potwierdzenia pracy centrali (O1)
    "power_supply_fans": 11,                # Stan wyjścia przekaźnika zasilania wentylatorów
    "heating_cable": 12,                    # Stan wyjścia przekaźnika zasilania kabla grzejnego
    "work_permit": 13,                      # Stan wyjścia przekaźnika potwierdzenia pracy (Expansion)
    "gwc": 14,                              # Stan wyjścia przekaźnika GWC
    "hood": 15,                             # Stan wyjścia zasilającego przepustnicę okapu
}

# DISCRETE INPUT REGISTERS (02 - READ DISCRETE INPUTS) - Stany wejść cyfrowych  
DISCRETE_INPUT_REGISTERS = {
    "expansion": 0,                         # Stan modułu expansion
    "contamination_sensor": 1,              # Stan czujnika zanieczyszczenia
    "external_contact_1": 2,                # Stan kontaktu zewnętrznego 1
    "external_contact_2": 3,                # Stan kontaktu zewnętrznego 2
    "external_contact_3": 4,                # Stan kontaktu zewnętrznego 3
    "external_contact_4": 5,                # Stan kontaktu zewnętrznego 4
    "fire_alarm": 6,                        # Stan alarmu pożarowego
    "frost_alarm": 7,                       # Stan alarmu przeciwmrozowego
    "filter_alarm": 8,                      # Stan alarmu filtra
    "maintenance_alarm": 9,                 # Stan alarmu konserwacji
    "sensor_error": 10,                     # Stan błędu czujnika
    "communication_error": 11,              # Stan błędu komunikacji
    "fan_error": 12,                        # Stan błędu wentylatora
    "heater_error": 13,                     # Stan błędu grzałki
    "cooler_error": 14,                     # Stan błędu chłodnicy
    "bypass_error": 15,                     # Stan błędu bypass
    "gwc_error": 16,                        # Stan błędu GWC
    "expansion_error": 17,                  # Stan błędu modułu expansion
}

# Special function modes for mode register
SPECIAL_MODES = {
    "normal": 0,
    "boost": 1,
    "eco": 2,
    "away": 4,
    "fireplace": 8,
    "hood": 16,
    "night": 32,
    "party": 64,
    "bathroom": 128,
    "kitchen": 256,
    "summer": 512,
    "winter": 1024,
    "defrost": 2048,
    "frost_protection": 4096,
}

# Special function bit mappings for services (alias for SPECIAL_MODES)
SPECIAL_FUNCTION_MAP = {
    "boost": 1,
    "eco": 2,
    "away": 4,
    "fireplace": 8,
    "hood": 16,
    "sleep": 32,  # alias for night
    "party": 64,
    "bathroom": 128,
    "kitchen": 256,
    "summer": 512,
    "winter": 1024,
}

# Unit mappings
REGISTER_UNITS = {
    # Temperature registers - 0.1°C resolution
    "outside_temperature": "°C",
    "supply_temperature": "°C", 
    "exhaust_temperature": "°C",
    "fpx_temperature": "°C",
    "duct_supply_temperature": "°C",
    "gwc_temperature": "°C",
    "ambient_temperature": "°C",
    "heating_temperature": "°C",
    "heat_exchanger_temperature_1": "°C",
    "heat_exchanger_temperature_2": "°C",
    "heat_exchanger_temperature_3": "°C",
    "heat_exchanger_temperature_4": "°C",
    
    # Flow registers - m³/h
    "supply_flowrate": "m³/h",
    "exhaust_flowrate": "m³/h",
    "outdoor_flowrate": "m³/h", 
    "inside_flowrate": "m³/h",
    "gwc_flowrate": "m³/h",
    "heat_recovery_flowrate": "m³/h",
    "bypass_flowrate": "m³/h",
    "supply_air_flow": "m³/h",
    "exhaust_air_flow": "m³/h",
    
    # Air quality
    "co2_level": "ppm",
    "humidity_indoor": "%",
    "humidity_outdoor": "%", 
    "pm1_level": "μg/m³",
    "pm25_level": "μg/m³",
    "pm10_level": "μg/m³",
    "voc_level": "ppb",
    
    # Power
    "preheater_power": "W",
    "main_heater_power": "W",
    "cooler_power": "W",
    "supply_fan_power": "W",
    "exhaust_fan_power": "W",
    "total_power_consumption": "W",
    "daily_energy_consumption": "Wh",
    "annual_energy_consumption": "kWh",
    "annual_energy_savings": "kWh",
    
    # Percentages
    "heat_recovery_efficiency": "%",
    "air_flow_rate_manual": "%",
    "supply_percentage": "%",
    "exhaust_percentage": "%",
    "damper_position_bypass": "%",
    "damper_position_gwc": "%",
    "damper_position_mix": "%",
    
    # Pressure
    "supply_pressure": "Pa",
    "exhaust_pressure": "Pa", 
    "differential_pressure": "Pa",
    
    # Voltage/Current
    "dac_supply": "V",
    "dac_exhaust": "V",
    "dac_heater": "V", 
    "dac_cooler": "V",
    "motor_supply_current": "mA",
    "motor_exhaust_current": "mA",
    "motor_supply_voltage": "mV",
    "motor_exhaust_voltage": "mV",
    
    # RPM
    "motor_supply_rpm": "rpm",
    "motor_exhaust_rpm": "rpm",
    
    # Time
    "system_uptime": "h",
    "filter_lifetime_remaining": "days",
    "boost_duration": "min",
    "fireplace_duration": "min",
    "hood_duration": "min",
    "party_duration": "min",
    "bathroom_duration": "min",
    "defrost_duration": "min",
    "maintenance_interval": "days",
    "air_quality_response_delay": "min",
    "air_quality_boost_duration": "min",
    "display_timeout": "s",
    
    # Misc
    "co2_reduction": "kg/year",
    "air_quality_index": "",
    "fault_counter": "",
    "maintenance_counter": "",
    "filter_replacement_counter": "",
}

# Value conversion factors
REGISTER_MULTIPLIERS = {
    # Temperature sensors with 0.1°C resolution
    "outside_temperature": 0.1,
    "supply_temperature": 0.1,
    "exhaust_temperature": 0.1,
    "fpx_temperature": 0.1,
    "duct_supply_temperature": 0.1,
    "gwc_temperature": 0.1,
    "ambient_temperature": 0.1,
    "heating_temperature": 0.1,
    "heat_exchanger_temperature_1": 0.1,
    "heat_exchanger_temperature_2": 0.1,
    "heat_exchanger_temperature_3": 0.1,
    "heat_exchanger_temperature_4": 0.1,
    
    # Temperature settings with 0.5°C resolution
    "required_temperature": 0.5,
    "comfort_temperature": 0.5,
    "economy_temperature": 0.5,
    "night_temperature": 0.5,
    "away_temperature": 0.5,
    "frost_protection_temperature": 0.5,
    "max_supply_temperature": 0.5,
    "min_supply_temperature": 0.5,
    "heating_curve_offset": 0.5,
    "bypass_temperature_threshold": 0.5,
    "bypass_hysteresis": 0.5,
    "gwc_temperature_threshold": 0.5,
    "gwc_hysteresis": 0.5,
    "preheating_temperature": 0.5,
    "defrost_temperature": 0.5,
    "night_cooling_temperature": 0.5,
    "supply_air_temperature_manual": 0.5,
    "supply_air_temperature_temporary": 0.5,
    "required_temp": 0.5,
    
    # Voltage/Current conversions
    "dac_supply": 0.00244,  # 0-4095 -> 0-10V
    "dac_exhaust": 0.00244,
    "dac_heater": 0.00244,
    "dac_cooler": 0.00244,
    "motor_supply_current": 0.001,  # mA to A
    "motor_exhaust_current": 0.001,
    "motor_supply_voltage": 0.001,  # mV to V
    "motor_exhaust_voltage": 0.001,
    
    # Other multipliers
    "heating_curve_slope": 0.1,
}

# Device class mappings for Home Assistant
DEVICE_CLASSES = {
    # Temperature
    "outside_temperature": "temperature",
    "supply_temperature": "temperature",
    "exhaust_temperature": "temperature",
    "fpx_temperature": "temperature", 
    "duct_supply_temperature": "temperature",
    "gwc_temperature": "temperature",
    "ambient_temperature": "temperature",
    "heating_temperature": "temperature",
    "heat_exchanger_temperature_1": "temperature",
    "heat_exchanger_temperature_2": "temperature",
    "heat_exchanger_temperature_3": "temperature",
    "heat_exchanger_temperature_4": "temperature",
    
    # Humidity
    "humidity_indoor": "humidity",
    "humidity_outdoor": "humidity",
    
    # Power/Energy
    "preheater_power": "power",
    "main_heater_power": "power",
    "cooler_power": "power",
    "supply_fan_power": "power",
    "exhaust_fan_power": "power",
    "total_power_consumption": "power",
    "daily_energy_consumption": "energy",
    "annual_energy_consumption": "energy",
    "annual_energy_savings": "energy",
    
    # Pressure
    "supply_pressure": "pressure",
    "exhaust_pressure": "pressure",
    "differential_pressure": "pressure",
    
    # Voltage/Current
    "dac_supply": "voltage",
    "dac_exhaust": "voltage",
    "dac_heater": "voltage",
    "dac_cooler": "voltage",
    "motor_supply_current": "current",
    "motor_exhaust_current": "current",
    "motor_supply_voltage": "voltage",
    "motor_exhaust_voltage": "voltage",
}

# State classes for statistics
STATE_CLASSES = {
    # Measurement values
    "outside_temperature": "measurement",
    "supply_temperature": "measurement",
    "exhaust_temperature": "measurement",
    "fpx_temperature": "measurement",
    "duct_supply_temperature": "measurement",
    "gwc_temperature": "measurement",
    "ambient_temperature": "measurement",
    "heating_temperature": "measurement",
    "supply_flowrate": "measurement",
    "exhaust_flowrate": "measurement",
    "supply_air_flow": "measurement",
    "exhaust_air_flow": "measurement",
    "co2_level": "measurement",
    "humidity_indoor": "measurement",
    "humidity_outdoor": "measurement",
    "pm1_level": "measurement",
    "pm25_level": "measurement",
    "pm10_level": "measurement",
    "voc_level": "measurement",
    "air_quality_index": "measurement",
    "heat_recovery_efficiency": "measurement",
    "supply_pressure": "measurement",
    "exhaust_pressure": "measurement",
    "differential_pressure": "measurement",
    "preheater_power": "measurement",
    "main_heater_power": "measurement",
    "cooler_power": "measurement",
    "supply_fan_power": "measurement",
    "exhaust_fan_power": "measurement",
    "total_power_consumption": "measurement",
    "motor_supply_rpm": "measurement",
    "motor_exhaust_rpm": "measurement",
    "motor_supply_current": "measurement",
    "motor_exhaust_current": "measurement",
    "motor_supply_voltage": "measurement",
    "motor_exhaust_voltage": "measurement",
    
    # Total increasing values
    "daily_energy_consumption": "total_increasing",
    "annual_energy_consumption": "total_increasing",
    "annual_energy_savings": "total_increasing",
    "system_uptime": "total_increasing",
    "fault_counter": "total_increasing",
    "maintenance_counter": "total_increasing",
    "filter_replacement_counter": "total_increasing",
    "co2_reduction": "total_increasing",
}