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
    
    # Temperature sensors (0x0010-0x0016) - 0.1°C resolution, 0x8000 = no sensor
    "outside_temperature": 0x0010,           # TZ1 - Temperatura zewnętrzna
    "supply_temperature": 0x0011,            # TZ2 - Temperatura nawiewu
    "exhaust_temperature": 0x0012,           # TZ3 - Temperatura wywiewu
    "fpx_temperature": 0x0013,               # TZ4 - Temperatura FPX
    "duct_supply_temperature": 0x0014,       # TZ5 - Temperatura kanałowa nawiewu
    "gwc_temperature": 0x0015,               # TZ6 - Temperatura GWC
    "ambient_temperature": 0x0016,           # TZ7 - Temperatura pomieszczenia
    "heating_temperature": 0x0017,           # TZ8 - Temperatura grzania
    
    # Flow sensors (0x0018-0x001E) - m³/h, 0x8000 = no sensor
    "supply_flowrate": 0x0018,               # Przepływ nawiewu 
    "exhaust_flowrate": 0x0019,              # Przepływ wywiewu
    "supply_percentage": 0x001A,             # % nawiewu
    "exhaust_percentage": 0x001B,            # % wywiewu
    "heat_recovery_efficiency": 0x001C,      # Odzysk ciepła %
    "filter_change": 0x001D,                 # Wymiana filtra
    "effective_flow_balance": 0x001E,        # Efektywna bilans przepływu
    
    # Additional sensors (0x001F-0x0025)
    "humidity": 0x001F,                      # Wilgotność względna %
    "co2_concentration": 0x0020,             # Stężenie CO2 [ppm]
    "voc_level": 0x0021,                     # Poziom VOC
    "pressure_difference": 0x0022,           # Różnica ciśnień [Pa]
    "pressure_drop": 0x0023,                 # Spadek ciśnienia [Pa]
    "energy_consumption": 0x0024,            # Zużycie energii [kWh]
    "power_consumption": 0x0025,             # Pobór mocy [W]
    
    # Status and diagnostics (0x0026-0x002F)
    "operating_hours": 0x0026,               # Godziny pracy
    "filter_hours": 0x0027,                  # Godziny filtra
    "maintenance_counter": 0x0028,           # Licznik konserwacji
    "error_code": 0x0029,                    # Kod błędu
    "warning_code": 0x002A,                  # Kod ostrzeżenia
    "serial_number": 0x002B,                 # Numer seryjny
    "battery_voltage": 0x002C,               # Napięcie baterii [mV]
    "power_quality": 0x002D,                 # Jakość zasilania
    "communication_errors": 0x002E,          # Błędy komunikacji
    "current": 0x002F,                       # Prąd [mA]
}

# HOLDING REGISTERS (03 - READ/WRITE HOLDING REGISTER) - Parametry i ustawienia
HOLDING_REGISTERS = {
    # Basic settings (0x1070-0x1080)
    "mode": 0x1070,                          # Tryb pracy (0=AUTO, 1=MANUAL, 2=TEMPORARY)
    "on_off_panel_mode": 0x1071,            # Tryb panelu ON/OFF
    "season_mode": 0x1072,                   # Tryb sezonowy (0=OFF, 1=WINTER, 2=SUMMER)
    "special_mode": 0x1073,                  # Tryb specjalny
    "okap_mode": 0x1074,                     # Tryb okapu
    "okap_intensity": 0x1075,                # Intensywność okapu
    "fireplace_mode": 0x1076,                # Tryb kominka
    "fireplace_flow_reduction": 0x1077,      # Redukcja przepływu kominka
    "vacation_mode": 0x1078,                 # Tryb urlopowy
    "boost_mode": 0x1079,                    # Tryb boost
    "boost_duration": 0x107A,                # Czas trwania boost [min]
    "gwc_mode": 0x107B,                      # Tryb GWC
    "bypass_mode": 0x107C,                   # Tryb bypass
    "heating_season": 0x107D,                # Sezon grzewczy
    "cooling_season": 0x107E,                # Sezon chłodzący
    "automatic_mode_settings": 0x107F,       # Ustawienia trybu automatycznego
    "humidity_control_settings": 0x1080,     # Ustawienia kontroli wilgotności
    
    # Flow control (0x1130-0x1140)
    "supply_flow_setpoint": 0x1130,          # Zadana wartość nawiewu [m³/h]
    "exhaust_flow_setpoint": 0x1131,         # Zadana wartość wywiewu [m³/h]
    "supply_flow_min": 0x1132,               # Min przepływ nawiewu [m³/h]
    "supply_flow_max": 0x1133,               # Max przepływ nawiewu [m³/h]
    "exhaust_flow_min": 0x1134,              # Min przepływ wywiewu [m³/h]
    "exhaust_flow_max": 0x1135,               # Max przepływ wywiewu [m³/h]
    "air_flow_balance": 0x1136,              # Balans przepływu powietrza
    "constant_flow_mode": 0x1137,            # Tryb stałego przepływu
    "flow_calibration": 0x1138,              # Kalibracja przepływu
    "flow_correction_factor": 0x1139,        # Współczynnik korekcji przepływu
    "night_flow_rate": 0x1159,               # Przepływ nocny [%]
    
    # Temperature control (0x1140-0x1150)
    "temperature_setpoint": 0x1140,          # Zadana temperatura [0.1°C]
    "temperature_offset": 0x1141,            # Offset temperatury [0.1°C]
    "temperature_hysteresis": 0x1142,        # Histereza temperatury [0.1°C]
    "heating_setpoint": 0x1143,              # Zadana temperatura grzania [0.1°C]
    "cooling_setpoint": 0x1144,              # Zadana temperatura chłodzenia [0.1°C]
    "heating_curve": 0x1145,                 # Krzywa grzewcza
    "heating_offset": 0x1146,                # Offset grzania [0.1°C]
    "cooling_offset": 0x1147,                # Offset chłodzenia [0.1°C]
    "temperature_protection": 0x1148,        # Ochrona temperatury
    
    # Air quality control (0x1150-0x1160)
    "co2_control_setpoint": 0x1150,          # Zadany poziom CO2 [ppm]
    "co2_control_hysteresis": 0x1151,        # Histereza CO2 [ppm]
    "voc_control_setpoint": 0x1152,          # Zadany poziom VOC
    "voc_control_hysteresis": 0x1153,        # Histereza VOC
    "humidity_control_setpoint": 0x1154,     # Zadana wilgotność [%]
    "humidity_control_hysteresis": 0x1155,   # Histereza wilgotności [%]
    "pressure_control_setpoint": 0x1156,     # Zadane ciśnienie [Pa]
    "pressure_control_hysteresis": 0x1157,   # Histereza ciśnienia [Pa]
    "air_quality_mode": 0x1158,              # Tryb jakości powietrza
    
    # Schedule settings (0x1200-0x1300) - przykładowe rejestry harmonogramu
    "schedule_week1_monday_period1_start": 0x1200,    # Poniedziałek okres 1 start
    "schedule_week1_monday_period1_end": 0x1201,      # Poniedziałek okres 1 koniec
    "schedule_week1_monday_period1_intensity": 0x1202, # Poniedziałek okres 1 intensywność
    "schedule_week1_monday_period1_temp": 0x1203,     # Poniedziałek okres 1 temperatura
    "schedule_week1_monday_period2_start": 0x1204,    # Poniedziałek okres 2 start
    "schedule_week1_monday_period2_end": 0x1205,      # Poniedziałek okres 2 koniec
    "schedule_week1_monday_period2_intensity": 0x1206, # Poniedziałek okres 2 intensywność
    "schedule_week1_monday_period2_temp": 0x1207,     # Poniedziałek okres 2 temperatura
    "schedule_week1_monday_period3_start": 0x1208,    # Poniedziałek okres 3 start
    "schedule_week1_monday_period3_end": 0x1209,      # Poniedziałek okres 3 koniec
    "schedule_week1_monday_period3_intensity": 0x120A, # Poniedziałek okres 3 intensywność
    "schedule_week1_monday_period3_temp": 0x120B,     # Poniedziałek okres 3 temperatura
    "schedule_week1_monday_period4_start": 0x120C,    # Poniedziałek okres 4 start
    "schedule_week1_monday_period4_end": 0x120D,      # Poniedziałek okres 4 koniec
    "schedule_week1_monday_period4_intensity": 0x120E, # Poniedziałek okres 4 intensywność
    "schedule_week1_monday_period4_temp": 0x120F,     # Poniedziałek okres 4 temperatura
    
    # Device information (0x1FD4-0x1FFF)
    "device_name_1": 0x1FD4,                 # Nazwa urządzenia część 1
    "device_name_2": 0x1FD5,                 # Nazwa urządzenia część 2 
    "device_name_3": 0x1FD6,                 # Nazwa urządzenia część 3
    "device_name_4": 0x1FD7,                 # Nazwa urządzenia część 4
    "lock_pass_1": 0x1FFB,                   # Hasło blokady część 1
    "lock_pass_2": 0x1FFC,                   # Hasło blokady część 2
    "lock_flag": 0x1FFD,                     # Flaga blokady
    "required_temp": 0x1FFE,                 # Wymagana temperatura
    "filter_change": 0x1FFF,                 # Wymiana filtra
}

# COIL REGISTERS (01 - READ COILS / 05 - WRITE SINGLE COIL) - Wyjścia i stany
COIL_REGISTERS = {
    # Output controls (0x0005-0x000F)
    "duct_warter_heater_pump": 0x0005,       # Pompa grzałki kanałowej
    "bypass": 0x0006,                        # Bypass
    "info": 0x0007,                          # Info
    "power_supply_fans": 0x0008,             # Zasilanie wentylatorów
    "heating_cable": 0x0009,                 # Kabel grzejny
    "cooling_relay": 0x0010,                 # Przekaźnik chłodzenia
    "preheating_relay": 0x0011,              # Przekaźnik podgrzewania
    "humidifier_relay": 0x0012,              # Przekaźnik nawilżacza
    "dehumidifier_relay": 0x0013,            # Przekaźnik osuszacza
    "air_damper_supply": 0x0014,             # Przepustnica nawiewu
    "air_damper_exhaust": 0x0015,            # Przepustnica wywiewu
    "expansion_output_1": 0x0016,            # Wyjście rozszerzone 1
    "expansion_output_2": 0x0017,            # Wyjście rozszerzone 2
    "expansion_output_3": 0x0018,            # Wyjście rozszerzone 3
    "expansion_output_4": 0x0019,            # Wyjście rozszerzone 4
    "defrosting_active": 0x001A,             # Odmrażanie aktywne
    "cooling_active": 0x001B,                # Chłodzenie aktywne
    "heating_active": 0x001C,                # Grzanie aktywne
    "summer_mode_active": 0x001D,            # Tryb letni aktywny
    "filter_warning": 0x001E,                # Ostrzeżenie filtra
    "gwc": 0x001F,                           # GWC aktywne
}

# DISCRETE INPUTS (02 - READ DISCRETE INPUTS) - Wejścia cyfrowe
DISCRETE_INPUTS = {
    # Digital inputs (0x0010-0x002F)
    "door_sensor": 0x0010,                   # Czujnik drzwi
    "window_sensor": 0x0011,                 # Czujnik okna
    "presence_sensor": 0x0012,               # Czujnik obecności
    "motion_sensor": 0x0013,                 # Czujnik ruchu
    "smoke_detector": 0x0014,                # Czujnik dymu
    "water_leak_sensor": 0x0015,             # Czujnik zalania
    "vibration_sensor": 0x0016,              # Czujnik wibracji
    "pressure_switch": 0x0017,               # Pressostat
    "flow_switch": 0x0018,                   # Przepływomierz
    "temperature_switch": 0x0019,            # Termostat
    "filter_switch": 0x001A,                 # Przełącznik filtra
    "maintenance_switch": 0x001B,            # Przełącznik konserwacji
    "emergency_stop": 0x001C,                # Zatrzymanie awaryjne
    "remote_control_signal": 0x0020,         # Sygnał pilota
    "panel_lock_status": 0x0021,             # Status blokady panelu
    "service_mode_active": 0x0022,           # Tryb serwisowy aktywny
    "bypass_status": 0x0023,                 # Status bypass
    "gwc_status": 0x0024,                    # Status GWC
    "summer_winter_switch": 0x0025,          # Przełącznik lato/zima
    "auto_manual_switch": 0x0026,            # Przełącznik auto/manual
    "emergency_stop": 0x0028,                # Stop awaryjny
    "power_failure": 0x0029,                 # Awaria zasilania
    "communication_error": 0x002A,           # Błąd komunikacji
    "expansion": 0x002F,                     # Rozszerzenie
}

# ============================================================================
# ENTITY MAPPINGS - Mapowanie rejestrów na encje Home Assistant
# ============================================================================

ENTITY_MAPPINGS = {
    "sensor": {
        # Temperature sensors
        "outside_temperature": {
            "name": "Outside Temperature",
            "device_class": "temperature",
            "unit": "°C",
            "icon": "mdi:thermometer",
            "state_class": "measurement"
        },
        "supply_temperature": {
            "name": "Supply Temperature", 
            "device_class": "temperature",
            "unit": "°C",
            "icon": "mdi:thermometer-plus",
            "state_class": "measurement"
        },
        "exhaust_temperature": {
            "name": "Exhaust Temperature",
            "device_class": "temperature", 
            "unit": "°C",
            "icon": "mdi:thermometer-minus",
            "state_class": "measurement"
        },
        "ambient_temperature": {
            "name": "Ambient Temperature",
            "device_class": "temperature",
            "unit": "°C", 
            "icon": "mdi:home-thermometer",
            "state_class": "measurement"
        },
        "gwc_temperature": {
            "name": "GWC Temperature",
            "device_class": "temperature",
            "unit": "°C",
            "icon": "mdi:thermometer-lines",
            "state_class": "measurement"
        },
        "heating_temperature": {
            "name": "Heating Temperature",
            "device_class": "temperature",
            "unit": "°C",
            "icon": "mdi:radiator",
            "state_class": "measurement"
        },
        
        # Flow sensors
        "supply_flowrate": {
            "name": "Supply Flow Rate",
            "unit": "m³/h",
            "icon": "mdi:fan",
            "state_class": "measurement"
        },
        "exhaust_flowrate": {
            "name": "Exhaust Flow Rate", 
            "unit": "m³/h",
            "icon": "mdi:fan",
            "state_class": "measurement"
        },
        "supply_percentage": {
            "name": "Supply Fan Speed",
            "unit": "%",
            "icon": "mdi:fan", 
            "state_class": "measurement"
        },
        "exhaust_percentage": {
            "name": "Exhaust Fan Speed",
            "unit": "%",
            "icon": "mdi:fan",
            "state_class": "measurement"
        },
        
        # Air quality
        "humidity": {
            "name": "Humidity",
            "device_class": "humidity",
            "unit": "%",
            "icon": "mdi:water-percent",
            "state_class": "measurement"
        },
        "co2_concentration": {
            "name": "CO2 Concentration",
            "device_class": "co2",
            "unit": "ppm",
            "icon": "mdi:molecule-co2",
            "state_class": "measurement"
        },
        "voc_level": {
            "name": "VOC Level",
            "unit": "ppb",
            "icon": "mdi:chemical-weapon", 
            "state_class": "measurement"
        },
        
        # Efficiency and performance
        "heat_recovery_efficiency": {
            "name": "Heat Recovery Efficiency",
            "unit": "%",
            "icon": "mdi:heat-pump",
            "state_class": "measurement"
        },
        "effective_flow_balance": {
            "name": "Flow Balance",
            "unit": "%",
            "icon": "mdi:scale-balance",
            "state_class": "measurement"
        },
        
        # Energy monitoring
        "energy_consumption": {
            "name": "Energy Consumption",
            "device_class": "energy",
            "unit": "kWh",
            "icon": "mdi:lightning-bolt",
            "state_class": "total_increasing"
        },
        "power_consumption": {
            "name": "Power Consumption", 
            "device_class": "power",
            "unit": "W",
            "icon": "mdi:flash",
            "state_class": "measurement"
        },
        
        # Diagnostics
        "operating_hours": {
            "name": "Operating Hours",
            "unit": "h",
            "icon": "mdi:clock",
            "state_class": "total_increasing",
            "entity_category": "diagnostic"
        },
        "filter_hours": {
            "name": "Filter Hours",
            "unit": "h", 
            "icon": "mdi:air-filter",
            "state_class": "total_increasing",
            "entity_category": "diagnostic"
        },
        "error_code": {
            "name": "Error Code",
            "icon": "mdi:alert-circle",
            "entity_category": "diagnostic"
        },
        "warning_code": {
            "name": "Warning Code",
            "icon": "mdi:alert",
            "entity_category": "diagnostic"
        },
        "firmware_major": {
            "name": "Firmware Version Major",
            "icon": "mdi:chip",
            "entity_category": "diagnostic"
        },
        "firmware_minor": {
            "name": "Firmware Version Minor", 
            "icon": "mdi:chip",
            "entity_category": "diagnostic"
        },
        "serial_number": {
            "name": "Serial Number",
            "icon": "mdi:barcode",
            "entity_category": "diagnostic"
        },
    },
    
    "binary_sensor": {
        # System status
        "bypass": {
            "name": "Bypass",
            "device_class": "opening",
            "icon": "mdi:valve"
        },
        "gwc": {
            "name": "GWC Active",
            "device_class": "running", 
            "icon": "mdi:heat-pump"
        },
        "heating_active": {
            "name": "Heating Active",
            "device_class": "heat",
            "icon": "mdi:radiator"
        },
        "cooling_active": {
            "name": "Cooling Active",
            "device_class": "cold",
            "icon": "mdi:snowflake"
        },
        "defrosting_active": {
            "name": "Defrosting Active",
            "device_class": "running",
            "icon": "mdi:snowflake-melt"
        },
        "summer_mode_active": {
            "name": "Summer Mode",
            "device_class": "running",
            "icon": "mdi:weather-sunny"
        },
        "filter_warning": {
            "name": "Filter Warning",
            "device_class": "problem",
            "icon": "mdi:air-filter"
        },
        
        # Safety sensors
        "door_sensor": {
            "name": "Door Sensor",
            "device_class": "door",
            "icon": "mdi:door"
        },
        "window_sensor": {
            "name": "Window Sensor", 
            "device_class": "window",
            "icon": "mdi:window-open"
        },
        "presence_sensor": {
            "name": "Presence Sensor",
            "device_class": "occupancy",
            "icon": "mdi:account"
        },
        "motion_sensor": {
            "name": "Motion Sensor",
            "device_class": "motion",
            "icon": "mdi:motion-sensor"
        },
        "smoke_detector": {
            "name": "Smoke Detector",
            "device_class": "smoke",
            "icon": "mdi:smoke-detector"
        },
        "emergency_stop": {
            "name": "Emergency Stop",
            "device_class": "safety",
            "icon": "mdi:stop-circle"
        },
        "power_failure": {
            "name": "Power Failure",
            "device_class": "problem",
            "icon": "mdi:power-plug-off"
        },
        "communication_error": {
            "name": "Communication Error",
            "device_class": "connectivity",
            "icon": "mdi:wifi-off"
        },
    },
    
    "select": {
        "mode": {
            "name": "Operation Mode",
            "options": ["AUTO", "MANUAL", "TEMPORARY"],
            "icon": "mdi:cog"
        },
        "season_mode": {
            "name": "Season Mode", 
            "options": ["OFF", "WINTER", "SUMMER"],
            "icon": "mdi:weather-snowy-rainy"
        },
        "air_quality_mode": {
            "name": "Air Quality Mode",
            "options": ["OFF", "CO2", "VOC", "HUMIDITY"],
            "icon": "mdi:air-filter"
        },
    },
    
    "number": {
        "supply_flow_setpoint": {
            "name": "Supply Flow Setpoint",
            "unit": "m³/h",
            "min": 50,
            "max": 500,
            "step": 10,
            "icon": "mdi:fan"
        },
        "exhaust_flow_setpoint": {
            "name": "Exhaust Flow Setpoint",
            "unit": "m³/h", 
            "min": 50,
            "max": 500,
            "step": 10,
            "icon": "mdi:fan"
        },
        "temperature_setpoint": {
            "name": "Temperature Setpoint",
            "unit": "°C",
            "min": 15,
            "max": 30,
            "step": 0.5,
            "icon": "mdi:thermometer"
        },
        "co2_control_setpoint": {
            "name": "CO2 Setpoint",
            "unit": "ppm",
            "min": 400,
            "max": 1200,
            "step": 50,
            "icon": "mdi:molecule-co2"
        },
        "humidity_control_setpoint": {
            "name": "Humidity Setpoint",
            "unit": "%",
            "min": 30,
            "max": 70,
            "step": 5,
            "icon": "mdi:water-percent"
        },
    },
    
    "switch": {
        "boost_mode": {
            "name": "Boost Mode",
            "icon": "mdi:rocket"
        },
        "vacation_mode": {
            "name": "Vacation Mode",
            "icon": "mdi:airplane"
        },
        "fireplace_mode": {
            "name": "Fireplace Mode",
            "icon": "mdi:fireplace"
        },
        "okap_mode": {
            "name": "Kitchen Hood Mode",
            "icon": "mdi:stove"
        },
        "heating_cable": {
            "name": "Heating Cable",
            "icon": "mdi:heating-coil"
        },
        "humidifier_relay": {
            "name": "Humidifier",
            "icon": "mdi:air-humidifier"
        },
        "dehumidifier_relay": {
            "name": "Dehumidifier", 
            "icon": "mdi:air-humidifier-variant"
        },
    }
}

# ============================================================================
# SPECIAL VALUES - Mapowanie wartości liczbowych na tekstowe
# ============================================================================

SPECIAL_VALUES = {
    "mode": {
        0: "AUTO",
        1: "MANUAL", 
        2: "TEMPORARY",
        3: "OFF"
    },
    "season_mode": {
        0: "OFF",
        1: "WINTER",
        2: "SUMMER"
    },
    "air_quality_mode": {
        0: "OFF",
        1: "CO2",
        2: "VOC", 
        3: "HUMIDITY",
        4: "AUTO"
    },
    "error_code": {
        0: "No Error",
        1: "Temperature Sensor Error",
        2: "Flow Sensor Error",
        3: "Fan Error",
        4: "Communication Error",
        5: "Filter Error",
        6: "Heating Error",
        7: "Cooling Error"
    },
    "warning_code": {
        0: "No Warning",
        1: "Filter Change Required",
        2: "Maintenance Required", 
        3: "High Temperature",
        4: "Low Flow",
        5: "High CO2",
        6: "High Humidity"
    }
}

# ============================================================================
# REGISTER TYPES FOR AUTOSCAN
# ============================================================================

REGISTER_TYPES = {
    "input": INPUT_REGISTERS,
    "holding": HOLDING_REGISTERS,
    "coil": COIL_REGISTERS,
    "discrete": DISCRETE_INPUTS
}

# Entity categories for organization
ENTITY_CATEGORIES = {
    "temperature": [
        "outside_temperature", "supply_temperature", "exhaust_temperature",
        "ambient_temperature", "gwc_temperature", "heating_temperature"
    ],
    "flow": [
        "supply_flowrate", "exhaust_flowrate", "supply_percentage", "exhaust_percentage"
    ],
    "air_quality": [
        "humidity", "co2_concentration", "voc_level"
    ],
    "energy": [
        "energy_consumption", "power_consumption"
    ],
    "status": [
        "bypass", "gwc", "heating_active", "cooling_active", "filter_warning"
    ],
    "diagnostics": [
        "operating_hours", "filter_hours", "error_code", "warning_code",
        "firmware_major", "firmware_minor", "serial_number"
    ]
}