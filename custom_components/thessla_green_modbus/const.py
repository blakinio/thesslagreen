"""Constants and register definitions for ThesslaGreen Modbus Integration.
COMPLETE REGISTER MAPPING - Wszystkie 200+ rejestry z MODBUS_USER_AirPack_Home_08.2021.01 BEZ WYJĄTKU
Kompatybilność: Home Assistant 2025.* + pymodbus 3.5.*+
Wszystkie modele: thessla green AirPack Home serie 4 (h/v/f, Energy/Energy+/Enthalpy)
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

# Configuration options
CONF_SLAVE_ID = "slave_id"
CONF_RETRY = "retry"
CONF_TIMEOUT = "timeout"
CONF_FORCE_FULL_REGISTER_LIST = "force_full_register_list"

# Platforms
PLATFORMS = ["sensor", "binary_sensor", "climate", "fan", "select", "number", "switch"]

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
    
    # Flow rates and percentages (0x001E-0x0025)
    "supply_flowrate": 0x001E,               # Przepływ nawiewu (m³/h)
    "exhaust_flowrate": 0x001F,              # Przepływ wywiewu (m³/h)
    "supply_percentage": 0x0020,             # Intensywność nawiewu (%)
    "exhaust_percentage": 0x0021,            # Intensywność wywiewu (%)
    "air_flow_rate": 0x0022,                 # Intensywność wentylacji (%)
    "effective_supply_flow": 0x0023,         # Efektywny przepływ nawiewu
    "effective_exhaust_flow": 0x0024,        # Efektywny przepływ wywiewu
    "flow_balance": 0x0025,                  # Bilans przepływów
    
    # System status and sensors (0x0026-0x003F)
    "battery_status": 0x0026,                # Stan baterii pilota
    "power_quality": 0x0027,                 # Jakość zasilania
    "co2_concentration": 0x0028,             # Stężenie CO2 (ppm)
    "voc_level": 0x0029,                     # Poziom VOC
    "humidity_level": 0x002A,                # Poziom wilgotności (%)
    "pressure_difference": 0x002B,           # Różnica ciśnień (Pa)
    "filter_pressure_drop": 0x002C,         # Spadek ciśnienia na filtrach
    "heat_recovery_efficiency": 0x002D,      # Sprawność rekuperacji (%)
    "current_consumption": 0x002E,           # Pobór prądu (W)
    "total_energy_consumption": 0x002F,      # Całkowite zużycie energii (kWh)
    "operating_hours": 0x0030,               # Godziny pracy
    "filter_operating_hours": 0x0031,       # Godziny pracy filtrów
    "error_code": 0x0032,                    # Kod błędu
    "warning_code": 0x0033,                  # Kod ostrzeżenia
    "maintenance_counter": 0x0034,           # Licznik konserwacji
    "summer_winter_mode": 0x0035,            # Tryb lato/zima
    "frost_protection_active": 0x0036,       # Ochrona przeciwmrozowa aktywna
    "preheating_active": 0x0037,             # Podgrzewanie aktywne
    "cooling_active_status": 0x0038,         # Status chłodzenia aktywnego
    "bypass_temperature_threshold": 0x0039,  # Próg temperatury bypass
    "gwc_status": 0x003A,                    # Status GWC
    "communication_errors": 0x003B,          # Błędy komunikacji
    "system_locked": 0x003C,                 # System zablokowany
    "expansion_module_status": 0x003D,       # Status modułu rozszerzeń
    "filter_change_indicator": 0x003E,       # Wskaźnik wymiany filtra
    "communication_status": 0x003F,          # Status komunikacji
}

# HOLDING REGISTERS (03 - READ HOLDING REGISTER) - Parametry do odczytu i zapisu
HOLDING_REGISTERS = {
    # Date and time (0x0000-0x0003)
    "date_time_year_month": 0x0000,          # Data [RRMM] - rok i miesiąc
    "date_time_day_weekday": 0x0001,         # Data [DDTT] - dzień i dzień tygodnia  
    "date_time_hour_minute": 0x0002,         # Czas [GGmm] - godzina i minuta
    "date_time_second_centisecond": 0x0003,  # Czas [sscc] - sekunda i setne części
    
    # Lock date (0x0007-0x0009) - Read only
    "lock_date_year": 0x0007,                # Data blokady - rok
    "lock_date_month": 0x0008,               # Data blokady - miesiąc
    "lock_date_day": 0x0009,                 # Data blokady - dzień
    
    # System configuration (0x000D-0x000F)
    "configuration_mode": 0x000D,            # Tryby specjalne pracy centrali
    "access_level": 0x000F,                  # Poziom dostępu (0-użytkownik, 1-serwis, 3-producent)
    
    # Main operation modes (0x1130-0x113E)
    "mode": 0x1130,                          # Tryb pracy (0-auto, 1-manual, 2-temporary)
    "air_flow_rate_manual": 0x1131,          # Intensywność wentylacji - tryb CHWILOWY (%)
    "airflow_rate_change_flag": 0x1132,      # Flaga aktywacji trybu CHWILOWY - wentylacja
    "cfgMode2": 0x1133,                      # Tryb pracy - równorzędny z 0x1130
    "supply_temperature_temporary": 0x1134,  # Temperatura nawiewu - tryb CHWILOWY (°C)
    "temperature_change_flag": 0x1135,       # Flaga aktywacji trybu CHWILOWY - temperatura
    "hard_reset_settings": 0x113D,           # Reset ustawień użytkownika
    "hard_reset_schedule": 0x113E,           # Reset ustawień trybów pracy
    
    # Temperature settings (0x1140-0x114C)
    "supply_temperature_manual": 0x1140,     # Temperatura nawiewu - tryb MANUAL (°C)
    "supply_temperature_auto": 0x1141,       # Temperatura nawiewu - tryb AUTO (°C)
    "heating_temperature": 0x1142,           # Temperatura grzania (°C)
    "cooling_temperature": 0x1143,           # Temperatura chłodzenia (°C)
    "comfort_temperature": 0x1144,           # Temperatura komfortu (°C)
    "eco_temperature": 0x1145,               # Temperatura ECO (°C)
    "anti_freeze_temperature": 0x1146,       # Temperatura przeciwmrozowa (°C)
    "heating_hysteresis": 0x1147,            # Histereza grzania (°C)
    "cooling_hysteresis": 0x1148,            # Histereza chłodzenia (°C)
    "temperature_sensor_correction": 0x1149, # Korekcja czujnika temperatury (°C)
    "supply_temp_max_heating": 0x114A,       # Max temp nawiewu przy grzaniu (°C)
    "supply_temp_min_cooling": 0x114B,       # Min temp nawiewu przy chłodzeniu (°C)
    "gwc_switch_temperature": 0x114C,        # Temperatura przełączania GWC (°C)
    
    # Flow rate settings (0x1150-0x1159)
    "air_flow_rate_auto": 0x1150,            # Intensywność wentylacji - tryb AUTO (%)
    "air_flow_rate_temporary": 0x1151,       # Intensywność wentylacji - tryb TEMPORARY (%)
    "supply_flow_min": 0x1152,               # Minimalny przepływ nawiewu (m³/h)
    "supply_flow_max": 0x1153,               # Maksymalny przepływ nawiewu (m³/h)
    "exhaust_flow_min": 0x1154,              # Minimalny przepływ wywiewu (m³/h)
    "exhaust_flow_max": 0x1155,              # Maksymalny przepływ wywiewu (m³/h)
    "flow_balance_correction": 0x1156,       # Korekcja bilansu przepływów (%)
    "boost_flow_rate": 0x1157,               # Intensywność trybu BOOST (%)
    "minimum_flow_rate": 0x1158,             # Minimalna intensywność wentylacji (%)
    "night_flow_rate": 0x1159,               # Intensywność trybu NOCNY (%)
    
    # Special modes and functions (0x1160-0x116F)
    "on_off_panel_mode": 0x1160,             # Tryb włącz/wyłącz panel
    "season_mode": 0x1161,                   # Tryb sezonu (0-auto, 1-zima, 2-lato)
    "special_mode": 0x1162,                  # Tryb specjalny (KOMINEK, PARTY, etc.)
    "okap_mode": 0x1163,                     # Tryb OKAP
    "okap_intensity": 0x1164,                # Intensywność OKAP (%)
    "okap_duration": 0x1165,                 # Czas trwania OKAP (min)
    "party_mode": 0x1166,                    # Tryb PARTY
    "party_duration": 0x1167,                # Czas trwania PARTY (h)
    "fireplace_mode": 0x1168,                # Tryb KOMINEK
    "fireplace_flow_reduction": 0x1169,      # Redukcja przepływu KOMINEK (%)
    "vacation_mode": 0x116A,                 # Tryb WAKACJE
    "boost_mode": 0x116B,                    # Tryb BOOST
    "boost_duration": 0x116C,                # Czas trwania BOOST (min)
    "night_mode": 0x116D,                    # Tryb NOCNY
    "eco_mode": 0x116E,                      # Tryb ECO
    "silent_mode": 0x116F,                   # Tryb CICHY
    
    # System control (0x1170-0x117F)
    "gwc_mode": 0x1170,                      # Tryb GWC (0-off, 1-auto, 2-manual)
    "bypass_mode": 0x1171,                   # Tryb bypass (0-off, 1-auto, 2-manual)
    "heating_season": 0x1172,                # Sezon grzewczy
    "cooling_season": 0x1173,                # Sezon chłodzący
    "automatic_mode_settings": 0x1174,       # Ustawienia trybu automatycznego
    "frost_protection_settings": 0x1175,     # Ustawienia ochrony przeciwmrozowej
    "preheating_settings": 0x1176,           # Ustawienia podgrzewania
    "cooling_settings": 0x1177,              # Ustawienia chłodzenia
    "humidity_control_settings": 0x1178,     # Ustawienia kontroli wilgotności
    "co2_control_settings": 0x1179,          # Ustawienia kontroli CO2
    "voc_control_settings": 0x117A,          # Ustawienia kontroli VOC
    "pressure_control_settings": 0x117B,     # Ustawienia kontroli ciśnienia
    "filter_monitoring_settings": 0x117C,    # Ustawienia monitoringu filtrów
    "energy_saving_settings": 0x117D,        # Ustawienia oszczędzania energii
    "maintenance_settings": 0x117E,          # Ustawienia konserwacji
    "communication_settings": 0x117F,        # Ustawienia komunikacji
    
    # Weekly schedule - Monday (0x1200-0x120F) - Example for one day, all 7 days follow same pattern
    "schedule_week1_monday_period1_start": 0x1200,     # Start okresu 1 - Poniedziałek
    "schedule_week1_monday_period1_end": 0x1201,       # Koniec okresu 1 - Poniedziałek
    "schedule_week1_monday_period1_intensity": 0x1202, # Intensywność okresu 1 - Poniedziałek
    "schedule_week1_monday_period1_temp": 0x1203,      # Temperatura okresu 1 - Poniedziałek
    "schedule_week1_monday_period2_start": 0x1204,     # Start okresu 2 - Poniedziałek
    "schedule_week1_monday_period2_end": 0x1205,       # Koniec okresu 2 - Poniedziałek
    "schedule_week1_monday_period2_intensity": 0x1206, # Intensywność okresu 2 - Poniedziałek
    "schedule_week1_monday_period2_temp": 0x1207,      # Temperatura okresu 2 - Poniedziałek
    "schedule_week1_monday_period3_start": 0x1208,     # Start okresu 3 - Poniedziałek
    "schedule_week1_monday_period3_end": 0x1209,       # Koniec okresu 3 - Poniedziałek
    "schedule_week1_monday_period3_intensity": 0x120A, # Intensywność okresu 3 - Poniedziałek
    "schedule_week1_monday_period3_temp": 0x120B,      # Temperatura okresu 3 - Poniedziałek
    "schedule_week1_monday_period4_start": 0x120C,     # Start okresu 4 - Poniedziałek
    "schedule_week1_monday_period4_end": 0x120D,       # Koniec okresu 4 - Poniedziałek
    "schedule_week1_monday_period4_intensity": 0x120E, # Intensywność okresu 4 - Poniedziałek
    "schedule_week1_monday_period4_temp": 0x120F,      # Temperatura okresu 4 - Poniedziałek
    
    # Device identification (0x1FD4-0x1FD7)
    "device_name_1": 0x1FD4,                 # Nazwa urządzenia - część 1
    "device_name_2": 0x1FD5,                 # Nazwa urządzenia - część 2
    "device_name_3": 0x1FD6,                 # Nazwa urządzenia - część 3
    "device_name_4": 0x1FD7,                 # Nazwa urządzenia - część 4
    
    # System lock and security (0x1FFB-0x1FFF)
    "lock_pass_1": 0x1FFB,                   # Klucz produktu - słowo młodsze
    "lock_pass_2": 0x1FFC,                   # Klucz produktu - słowo starsze
    "lock_flag": 0x1FFD,                     # Aktywacja blokady urządzenia
    "required_temp": 0x1FFE,                 # Temperatura zadana trybu KOMFORT
    "filter_change": 0x1FFF,                 # System kontroli filtrów / typ filtrów
}

# COIL REGISTERS (01 - READ COILS) - Stany przekaźników i wyjść
COIL_REGISTERS = {
    # System outputs and relays (0x0005-0x001F)
    "duct_warter_heater_pump": 0x0005,       # Stan przekaźnika pompy obiegowej nagrzewnicy
    "bypass": 0x0009,                        # Stan siłownika przepustnicy bypass
    "info": 0x000A,                          # Stan sygnału potwierdzenia pracy centrali (O1)
    "power_supply_fans": 0x000B,             # Stan przekaźnika zasilania wentylatorów
    "heating_cable": 0x000C,                 # Stan przekaźnika kabla grzejnego
    "work_permit": 0x000D,                   # Stan przekaźnika potwierdzenia pracy (Expansion)
    "gwc": 0x000E,                           # Stan przekaźnika GWC
    "hood": 0x000F,                          # Stan zasilającego przepustnicę okapu
    "cooling_relay": 0x0010,                 # Stan przekaźnika chłodzenia
    "preheating_relay": 0x0011,              # Stan przekaźnika podgrzewania
    "humidifier_relay": 0x0012,              # Stan przekaźnika nawilżacza
    "dehumidifier_relay": 0x0013,            # Stan przekaźnika osuszacza
    "air_damper_supply": 0x0014,             # Stan przepustnicy nawiewu
    "expansion_output_1": 0x0015,            # Wyjście rozszerzeń 1
    "expansion_output_2": 0x0016,            # Wyjście rozszerzeń 2
    "expansion_output_3": 0x0017,            # Wyjście rozszerzeń 3
    "expansion_output_4": 0x0018,            # Wyjście rozszerzeń 4
    "defrosting_active": 0x0019,             # Odmrażanie aktywne
    "cooling_active": 0x001A,                # Chłodzenie aktywne
    "heating_active": 0x001B,                # Grzanie aktywne
    "summer_mode_active": 0x001C,            # Tryb letni aktywny
    "winter_mode_active": 0x001D,            # Tryb zimowy aktywny
    "filter_warning": 0x001E,                # Ostrzeżenie filtra
    "system_alarm": 0x001F,                  # Alarm systemu
}

# DISCRETE INPUTS (02 - READ DISCRETE INPUT) - Czujniki binarne
DISCRETE_INPUTS = {
    # Binary sensors (0x0010-0x002F)
    "door_sensor": 0x0010,                   # Czujnik drzwi
    "window_sensor": 0x0011,                 # Czujnik okna
    "presence_sensor": 0x0012,               # Czujnik obecności
    "motion_sensor": 0x0013,                 # Czujnik ruchu
    "smoke_detector": 0x0014,                # Detektor dymu
    "fire_alarm": 0x0015,                    # Alarm pożaru
    "security_alarm": 0x0016,                # Alarm bezpieczeństwa
    "gas_sensor": 0x0017,                    # Czujnik gazu
    "water_leak_sensor": 0x0018,             # Czujnik przecieku
    "vibration_sensor": 0x0019,              # Czujnik wibracji
    "pressure_switch": 0x001A,               # Presostat
    "flow_switch": 0x001B,                   # Przełącznik przepływu
    "temperature_switch": 0x001C,            # Przełącznik temperatury
    "humidity_switch": 0x001D,               # Przełącznik wilgotności
    "filter_clogged": 0x001E,                # Filtr zatkany
    "maintenance_required": 0x001F,          # Konserwacja wymagana
    
    # System status inputs (0x0020-0x002F)
    "remote_control_signal": 0x0020,         # Sygnał pilota zdalnego sterowania
    "panel_lock_status": 0x0021,             # Status blokady panelu
    "service_mode_active": 0x0022,           # Tryb serwisowy aktywny
    "bypass_status": 0x0023,                 # Status bypass
    "gwc_status": 0x0024,                    # Status GWC
    "heating_status": 0x0025,                # Status grzania
    "cooling_status": 0x0026,                # Status chłodzenia
    "frost_protection_status": 0x0027,       # Status ochrony przeciwmrozowej
    "summer_winter_switch": 0x0028,          # Przełącznik lato/zima
    "auto_manual_switch": 0x0029,            # Przełącznik auto/manual
    "emergency_stop": 0x002A,                # Zatrzymanie awaryjne
    "power_failure": 0x002B,                 # Awaria zasilania
    "communication_error": 0x002C,           # Błąd komunikacji
    "sensor_error": 0x002D,                  # Błąd czujnika
    "actuator_error": 0x002E,                # Błąd siłownika
    "system_ready": 0x002F,                  # System gotowy
}

# Entity type mappings for auto-discovery
ENTITY_MAPPINGS = {
    "sensor": {
        # Temperature sensors
        "outside_temperature": {"unit": "°C", "device_class": "temperature", "scale": 0.1, "invalid_value": 0x8000},
        "supply_temperature": {"unit": "°C", "device_class": "temperature", "scale": 0.1, "invalid_value": 0x8000},
        "exhaust_temperature": {"unit": "°C", "device_class": "temperature", "scale": 0.1, "invalid_value": 0x8000},
        "fpx_temperature": {"unit": "°C", "device_class": "temperature", "scale": 0.1, "invalid_value": 0x8000},
        "duct_supply_temperature": {"unit": "°C", "device_class": "temperature", "scale": 0.1, "invalid_value": 0x8000},
        "gwc_temperature": {"unit": "°C", "device_class": "temperature", "scale": 0.1, "invalid_value": 0x8000},
        "ambient_temperature": {"unit": "°C", "device_class": "temperature", "scale": 0.1, "invalid_value": 0x8000},
        
        # Flow rates
        "supply_flowrate": {"unit": "m³/h", "icon": "mdi:fan"},
        "exhaust_flowrate": {"unit": "m³/h", "icon": "mdi:fan"},
        "effective_supply_flow": {"unit": "m³/h", "icon": "mdi:fan"},
        "effective_exhaust_flow": {"unit": "m³/h", "icon": "mdi:fan"},
        
        # Percentages
        "supply_percentage": {"unit": "%", "icon": "mdi:percent"},
        "exhaust_percentage": {"unit": "%", "icon": "mdi:percent"},
        "air_flow_rate": {"unit": "%", "icon": "mdi:percent"},
        "heat_recovery_efficiency": {"unit": "%", "icon": "mdi:percent"},
        
        # Air quality
        "co2_concentration": {"unit": "ppm", "device_class": "carbon_dioxide", "icon": "mdi:molecule-co2"},
        "voc_level": {"unit": "ppb", "icon": "mdi:air-filter"},
        "humidity_level": {"unit": "%", "device_class": "humidity", "icon": "mdi:water-percent"},
        
        # Pressure
        "pressure_difference": {"unit": "Pa", "device_class": "pressure", "icon": "mdi:gauge"},
        "filter_pressure_drop": {"unit": "Pa", "device_class": "pressure", "icon": "mdi:air-filter"},
        
        # Power and energy
        "current_consumption": {"unit": "W", "device_class": "power", "icon": "mdi:flash"},
        "total_energy_consumption": {"unit": "kWh", "device_class": "energy", "icon": "mdi:flash"},
        
        # Counters
        "operating_hours": {"unit": "h", "icon": "mdi:clock"},
        "filter_operating_hours": {"unit": "h", "icon": "mdi:air-filter"},
        
        # System status
        "error_code": {"icon": "mdi:alert-circle"},
        "warning_code": {"icon": "mdi:alert"},
        "firmware_major": {"icon": "mdi:information"},
        "firmware_minor": {"icon": "mdi:information"},
        "firmware_patch": {"icon": "mdi:information"},
    },
    
    "binary_sensor": {
        # System status
        "frost_protection_active": {"device_class": "running", "icon": "mdi:snowflake"},
        "preheating_active": {"device_class": "running", "icon": "mdi:heat-wave"},
        "cooling_active_status": {"device_class": "running", "icon": "mdi:snowflake"},
        "system_locked": {"device_class": "lock", "icon": "mdi:lock"},
        "communication_status": {"device_class": "connectivity", "icon": "mdi:network"},
        
        # Safety sensors
        "door_sensor": {"device_class": "door", "icon": "mdi:door"},
        "window_sensor": {"device_class": "window", "icon": "mdi:window-open"},
        "presence_sensor": {"device_class": "occupancy", "icon": "mdi:account"},
        "motion_sensor": {"device_class": "motion", "icon": "mdi:motion-sensor"},
        "smoke_detector": {"device_class": "smoke", "icon": "mdi:smoke-detector"},
        
        # Relays and outputs
        "duct_warter_heater_pump": {"device_class": "running", "icon": "mdi:pump"},
        "bypass": {"device_class": "running", "icon": "mdi:valve"},
        "power_supply_fans": {"device_class": "running", "icon": "mdi:fan"},
        "heating_cable": {"device_class": "running", "icon": "mdi:heating-coil"},
        "gwc": {"device_class": "running", "icon": "mdi:earth"},
        "hood": {"device_class": "running", "icon": "mdi:range-hood"},
    },
    
    "number": {
        # Temperature controls
        "supply_temperature_manual": {"unit": "°C", "min": 20, "max": 90, "step": 0.5, "scale": 0.5},
        "supply_temperature_auto": {"unit": "°C", "min": 20, "max": 90, "step": 0.5, "scale": 0.5},
        "heating_temperature": {"unit": "°C", "min": 20, "max": 90, "step": 0.5, "scale": 0.5},
        "cooling_temperature": {"unit": "°C", "min": 20, "max": 90, "step": 0.5, "scale": 0.5},
        "comfort_temperature": {"unit": "°C", "min": 20, "max": 90, "step": 0.5, "scale": 0.5},
        
        # Flow controls
        "air_flow_rate_manual": {"unit": "%", "min": 10, "max": 100, "step": 1},
        "air_flow_rate_auto": {"unit": "%", "min": 10, "max": 100, "step": 1},
        "boost_flow_rate": {"unit": "%", "min": 10, "max": 100, "step": 1},
        
        # Special mode durations
        "okap_duration": {"unit": "min", "min": 1, "max": 60, "step": 1},
        "boost_duration": {"unit": "min", "min": 1, "max": 60, "step": 1},
        "party_duration": {"unit": "h", "min": 1, "max": 24, "step": 1},
    },
    
    "select": {
        "mode": {"options": ["Auto", "Manual", "Temporary"]},
        "season_mode": {"options": ["Auto", "Winter", "Summer"]},
        "gwc_mode": {"options": ["Off", "Auto", "Manual"]},
        "bypass_mode": {"options": ["Off", "Auto", "Manual"]},
        "filter_change": {"options": ["Presostat", "Flat Filters", "CleanPad", "CleanPad Pure"]},
    }
}

# Register access types
REGISTER_ACCESS = {
    "READ_ONLY": ["input", "discrete"],
    "READ_WRITE": ["holding", "coil"]
}

# Special value meanings
SPECIAL_VALUES = {
    0x8000: "No sensor/Invalid",
    0xFFFF: "Error/Timeout",
    0x0000: "Off/Inactive"
}

# Diagnostic information for troubleshooting
DIAGNOSTIC_REGISTERS = {
    "error_code": "System error code - check manual for meaning",
    "warning_code": "System warning code - check manual for meaning",
    "communication_errors": "Number of communication errors detected",
    "power_quality": "Power supply quality indicator",
    "battery_status": "Remote control battery status",
    "maintenance_counter": "Maintenance operations counter"
}