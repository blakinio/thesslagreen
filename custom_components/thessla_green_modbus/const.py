"""Constants and register definitions for the ThesslaGreen Modbus integration."""

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
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_RETRY = "retry"
CONF_FORCE_FULL_REGISTER_LIST = "force_full_register_list"

# Platforms
PLATFORMS = [
    "sensor",
    "binary_sensor",
    "climate",
    "fan",
    "select",
    "number",
    "switch",
]

# Entity mappings for various platforms
ENTITY_MAPPINGS = {
    "number": {
        "required_temperature": {
            "unit": "°C",
            "min": 16,
            "max": 26,
            "step": 0.5,
            "scale": 0.5,
        },
        "max_supply_temperature": {
            "unit": "°C",
            "min": 15,
            "max": 45,
            "step": 0.5,
            "scale": 0.5,
        },
        "min_supply_temperature": {
            "unit": "°C",
            "min": 5,
            "max": 30,
            "step": 0.5,
            "scale": 0.5,
        },
        "heating_curve_slope": {
            "min": 0,
            "max": 10,
            "step": 0.1,
            "scale": 0.1,
        },
        "heating_curve_offset": {
            "unit": "°C",
            "min": -10,
            "max": 10,
            "step": 0.5,
            "scale": 0.5,
        },
        "boost_air_flow_rate": {
            "unit": "%",
            "min": 0,
            "max": 100,
            "step": 1,
        },
        "boost_duration": {
            "unit": "min",
            "min": 0,
            "max": 240,
            "step": 1,
        },
        "humidity_target": {
            "unit": "%",
            "min": 0,
            "max": 100,
            "step": 1,
        },
    }
}

# ============================================================================
# Complete register mapping from MODBUS_USER_AirPack_Home_08.2021.01 PDF
# ============================================================================

# INPUT REGISTERS (04 - READ INPUT REGISTER) - Sensors and read-only values
INPUT_REGISTERS = {
    # Firmware version (0x0000-0x0004)
    "firmware_major": 0x0000,
    "firmware_minor": 0x0001,
    "day_of_week": 0x0002,
    "period": 0x0003,
    "firmware_patch": 0x0004,
    
    # Compilation info (0x000E-0x000F)
    "compilation_days": 0x000E,
    "compilation_seconds": 0x000F,
    
    # Temperature sensors (0x0010-0x0017) - 0.1°C resolution, 0x8000 = no sensor
    "outside_temperature": 0x0010,
    "supply_temperature": 0x0011,
    "exhaust_temperature": 0x0012,
    "fpx_temperature": 0x0013,
    "duct_supply_temperature": 0x0014,
    "gwc_temperature": 0x0015,
    "ambient_temperature": 0x0016,
    "heating_temperature": 0x0017,
    
    # Flow sensors (0x0018-0x001E) - m³/h, 0x8000 = no sensor
    "supply_flowrate": 0x0018,
    "exhaust_flowrate": 0x0019,
    "outdoor_flowrate": 0x001A,
    "inside_flowrate": 0x001B,
    "gwc_flowrate": 0x001C,
    "heat_recovery_flowrate": 0x001D,
    "bypass_flowrate": 0x001E,
    
    # Air quality sensors (0x0020-0x0027)
    "co2_level": 0x0020,
    "humidity_indoor": 0x0021,
    "humidity_outdoor": 0x0022,
    "pm1_level": 0x0023,
    "pm25_level": 0x0024,
    "pm10_level": 0x0025,
    "voc_level": 0x0026,
    "air_quality_index": 0x0027,
    
    # System status registers (0x0030-0x003F)
    "heat_recovery_efficiency": 0x0030,
    "filter_lifetime_remaining": 0x0031,
    "preheater_power": 0x0032,
    "main_heater_power": 0x0033,
    "cooler_power": 0x0034,
    "supply_fan_power": 0x0035,
    "exhaust_fan_power": 0x0036,
    "total_power_consumption": 0x0037,
    "annual_energy_consumption": 0x0038,
    "daily_energy_consumption": 0x0039,
    "annual_energy_savings": 0x003A,
    "co2_reduction": 0x003B,
    "system_uptime": 0x003C,
    "fault_counter": 0x003D,
    "maintenance_counter": 0x003E,
    "filter_replacement_counter": 0x003F,
    
    # Expansion module version (0x00F1)
    "expansion_version": 0x00F1,
    
    # Current airflow (0x0100-0x0101)
    "supply_air_flow": 0x0100,
    "exhaust_air_flow": 0x0101,
    
    # PWM control values (0x0500-0x0503) - 0-4095 (0-10V)
    "dac_supply": 0x0500,
    "dac_exhaust": 0x0501,
    "dac_heater": 0x0502,
    "dac_cooler": 0x0503,
    
    # Advanced diagnostics (0x0504-0x051F)
    "motor_supply_rpm": 0x0504,
    "motor_exhaust_rpm": 0x0505,
    "motor_supply_current": 0x0506,
    "motor_exhaust_current": 0x0507,
    "motor_supply_voltage": 0x0508,
    "motor_exhaust_voltage": 0x0509,
    "supply_pressure": 0x050A,
    "exhaust_pressure": 0x050B,
    "differential_pressure": 0x050C,
    "heat_exchanger_temperature_1": 0x050D,
    "heat_exchanger_temperature_2": 0x050E,
    "heat_exchanger_temperature_3": 0x050F,
    "heat_exchanger_temperature_4": 0x0510,
    "damper_position_bypass": 0x0511,
    "damper_position_gwc": 0x0512,
    "damper_position_mix": 0x0513,
    "frost_protection_active": 0x0514,
    "defrost_cycle_active": 0x0515,
    "summer_bypass_active": 0x0516,
    "winter_heating_active": 0x0517,
    "night_cooling_active": 0x0518,
    "constant_flow_active": 0x0519,
    "air_quality_control_active": 0x051A,
    "humidity_control_active": 0x051B,
    "temperature_control_active": 0x051C,
    "demand_control_active": 0x051D,
    "schedule_control_active": 0x051E,
    "manual_control_active": 0x051F,
}

# HOLDING REGISTERS (03 - READ/WRITE HOLDING REGISTER) - Konfiguracja i kontrola
HOLDING_REGISTERS = {
    # Main control registers (0x1000-0x1020)
    "on_off_panel_mode": 0x1000,
    "mode": 0x1001,
    "air_flow_rate_manual": 0x1002,
    "supply_air_temperature_manual": 0x1003,
    "special_mode": 0x1004,
    "required_temperature": 0x1005,
    "comfort_temperature": 0x1006,
    "economy_temperature": 0x1007,
    "night_temperature": 0x1008,
    "away_temperature": 0x1009,
    "frost_protection_temperature": 0x100A,
    "max_supply_temperature": 0x100B,
    "min_supply_temperature": 0x100C,
    "heating_curve_slope": 0x100D,
    "heating_curve_offset": 0x100E,
    "supply_air_flow_rate": 0x100F,
    "exhaust_air_flow_rate": 0x1010,
    "minimum_air_flow_rate": 0x1011,
    "maximum_air_flow_rate": 0x1012,
    "eco_air_flow_rate": 0x1013,
    "night_air_flow_rate": 0x1014,
    "away_air_flow_rate": 0x1015,
    "boost_air_flow_rate": 0x1016,
    "boost_duration": 0x1017,
    "fireplace_air_flow_rate": 0x1018,
    "fireplace_duration": 0x1019,
    "hood_air_flow_rate": 0x101A,
    "hood_duration": 0x101B,
    "party_air_flow_rate": 0x101C,
    "party_duration": 0x101D,
    "bathroom_air_flow_rate": 0x101E,
    "bathroom_duration": 0x101F,
    "kitchen_air_flow_rate": 0x1020,
    
    # Special functions (0x1030-0x1050)
    "bypass_mode": 0x1030,
    "bypass_temperature_threshold": 0x1031,
    "bypass_hysteresis": 0x1032,
    "gwc_mode": 0x1033,
    "gwc_temperature_threshold": 0x1034,
    "gwc_hysteresis": 0x1035,
    "preheating_mode": 0x1036,
    "preheating_temperature": 0x1037,
    "defrost_mode": 0x1038,
    "defrost_temperature": 0x1039,
    "defrost_duration": 0x103A,
    "frost_protection_mode": 0x103B,
    "summer_mode": 0x103C,
    "winter_mode": 0x103D,
    "night_cooling_mode": 0x103E,
    "night_cooling_temperature": 0x103F,
    "air_quality_control": 0x1040,
    "humidity_control": 0x1041,
    "humidity_target": 0x1042,
    "humidity_hysteresis": 0x1043,
    "demand_control": 0x1044,
    "occupancy_sensor": 0x1045,
    "window_contact": 0x1046,
    "external_switch": 0x1047,
    "bathroom_switch": 0x1048,
    "kitchen_switch": 0x1049,
    "bedroom_switch": 0x104A,
    "living_room_switch": 0x104B,
    "office_switch": 0x104C,
    "guest_room_switch": 0x104D,
    "basement_switch": 0x104E,
    "attic_switch": 0x104F,
    "garage_switch": 0x1050,
    
    # Air quality settings (0x1060-0x1080)
    "co2_threshold_low": 0x1060,
    "co2_threshold_medium": 0x1061,
    "co2_threshold_high": 0x1062,
    "co2_hysteresis": 0x1063,
    "voc_threshold_low": 0x1064,
    "voc_threshold_medium": 0x1065,
    "voc_threshold_high": 0x1066,
    "voc_hysteresis": 0x1067,
    "pm25_threshold_low": 0x1068,
    "pm25_threshold_medium": 0x1069,
    "pm25_threshold_high": 0x106A,
    "pm25_hysteresis": 0x106B,
    "pm10_threshold_low": 0x106C,
    "pm10_threshold_medium": 0x106D,
    "pm10_threshold_high": 0x106E,
    "pm10_hysteresis": 0x106F,
    "air_quality_response_delay": 0x1070,
    "air_quality_boost_duration": 0x1071,
    "air_quality_boost_flow": 0x1072,
    "filter_alarm_threshold": 0x1073,
    "filter_warning_threshold": 0x1074,
    "maintenance_interval": 0x1075,
    "cleaning_reminder": 0x1076,
    "sensor_calibration_interval": 0x1077,
    "backup_settings": 0x1078,
    "factory_reset": 0x1079,
    "configuration_lock": 0x107A,
    "user_level": 0x107B,
    "display_brightness": 0x107C,
    "display_timeout": 0x107D,
    "keypad_lock": 0x107E,
    "sound_volume": 0x107F,
    "language": 0x1080,
    
    # Weekly schedule (0x1100-0x1127)
    "weekly_schedule_mode": 0x1100,
    "schedule_monday_period1_start": 0x1101,
    "schedule_monday_period1_end": 0x1102,
    "schedule_monday_period1_flow": 0x1103,
    "schedule_monday_period1_temp": 0x1104,
    "schedule_monday_period2_start": 0x1105,
    "schedule_monday_period2_end": 0x1106,
    "schedule_monday_period2_flow": 0x1107,
    "schedule_monday_period2_temp": 0x1108,
    "schedule_tuesday_period1_start": 0x1109,
    "schedule_tuesday_period1_end": 0x110A,
    "schedule_tuesday_period1_flow": 0x110B,
    "schedule_tuesday_period1_temp": 0x110C,
    "schedule_tuesday_period2_start": 0x110D,
    "schedule_tuesday_period2_end": 0x110E,
    "schedule_tuesday_period2_flow": 0x110F,
    "schedule_tuesday_period2_temp": 0x1110,
    "schedule_wednesday_period1_start": 0x1111,
    "schedule_wednesday_period1_end": 0x1112,
    "schedule_wednesday_period1_flow": 0x1113,
    "schedule_wednesday_period1_temp": 0x1114,
    "schedule_wednesday_period2_start": 0x1115,
    "schedule_wednesday_period2_end": 0x1116,
    "schedule_wednesday_period2_flow": 0x1117,
    "schedule_wednesday_period2_temp": 0x1118,
    "schedule_thursday_period1_start": 0x1119,
    "schedule_thursday_period1_end": 0x111A,
    "schedule_thursday_period1_flow": 0x111B,
    "schedule_thursday_period1_temp": 0x111C,
    "schedule_thursday_period2_start": 0x111D,
    "schedule_thursday_period2_end": 0x111E,
    "schedule_thursday_period2_flow": 0x111F,
    "schedule_thursday_period2_temp": 0x1120,
    "schedule_friday_period1_start": 0x1121,
    "schedule_friday_period1_end": 0x1122,
    "schedule_friday_period1_flow": 0x1123,
    "schedule_friday_period1_temp": 0x1124,
    "schedule_friday_period2_start": 0x1125,
    "schedule_friday_period2_end": 0x1126,
    "schedule_friday_period2_flow": 0x1127,
    
    # Temporary mode control (0x1130-0x1135) - z dokumentacji PDF
    "cfg_mode1": 0x1130,
    "air_flow_rate_temporary": 0x1131,
    "airflow_rate_change_flag": 0x1132,
    "cfg_mode2": 0x1133,
    "supply_air_temperature_temporary": 0x1134,
    "temperature_change_flag": 0x1135,
    
    # System reset controls (0x113D-0x113E) - z dokumentacji PDF
    "hard_reset_settings": 0x113D,
    "hard_reset_schedule": 0x113E,
    
    # Filter control (0x1150-0x1151) - z dokumentacji PDF
    "pres_check_day": 0x1150,
    "pres_check_time": 0x1151,
    
    # Modbus communication settings (0x1164-0x116B) - z dokumentacji PDF
    "uart0_id": 0x1164,
    "uart0_baud": 0x1165,
    "uart0_parity": 0x1166,
    "uart0_stop": 0x1167,
    "uart1_id": 0x1168,
    "uart1_baud": 0x1169,
    "uart1_parity": 0x116A,
    "uart1_stop": 0x116B,
    
    # Device name (0x1FD0-0x1FD7) - z dokumentacji PDF
    "device_name_1": 0x1FD0,
    "device_name_2": 0x1FD1,
    "device_name_3": 0x1FD2,
    "device_name_4": 0x1FD3,
    "device_name_5": 0x1FD4,
    "device_name_6": 0x1FD5,
    "device_name_7": 0x1FD6,
    "device_name_8": 0x1FD7,
    
    # Product key and lock (0x1FFB-0x1FFF) - z dokumentacji PDF
    "lock_pass1": 0x1FFB,
    "lock_pass2": 0x1FFC,
    "lock_flag": 0x1FFD,
    "required_temp": 0x1FFE,
    "filter_change": 0x1FFF,
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