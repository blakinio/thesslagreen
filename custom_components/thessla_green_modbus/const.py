"""Constants and register definitions for the ThesslaGreen Modbus integration."""

import json
from pathlib import Path

OPTIONS_PATH = Path(__file__).parent / "options"


# Integration constants
DOMAIN = "thessla_green_modbus"
MANUFACTURER = "ThesslaGreen"
MODEL = "AirPack Home Series 4"

# Connection defaults
DEFAULT_NAME = "ThesslaGreen"
DEFAULT_PORT = 502  # Standard Modbus TCP port; legacy versions used 8899
DEFAULT_SLAVE_ID = 10
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3

# Sensor constants
SENSOR_UNAVAILABLE = 0x8000  # Indicates missing/invalid sensor reading

# Configuration options
CONF_SLAVE_ID = "slave_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_RETRY = "retry"
CONF_FORCE_FULL_REGISTER_LIST = "force_full_register_list"

# Platforms supported by the integration
# Diagnostics is handled separately and therefore not listed here
PLATFORMS = [
    "sensor",
    "binary_sensor",
    "climate",
    "fan",
    "select",
    "number",
    "switch",
]

# ============================================================================
# Complete register mapping from MODBUS_USER_AirPack_Home_08.2021.01 PDF
# ============================================================================

# COIL REGISTERS (01 - READ COILS) - Output and relay states
COIL_REGISTERS = {
    "duct_water_heater_pump": 5,  # Circulation pump relay output
    "bypass": 9,  # Bypass damper actuator output
    "info": 10,  # System operation confirmation output (O1)
    "power_supply_fans": 11,  # Fan power relay output
    "heating_cable": 12,  # Heating cable power relay output
    "work_permit": 13,  # Operation confirmation relay (Expansion)
    "gwc": 14,  # GWC relay output
    "hood": 15,  # Hood damper power output
}

# DISCRETE INPUT REGISTERS (02 - READ DISCRETE INPUTS) - Digital input states
DISCRETE_INPUT_REGISTERS = {
    "duct_heater_protection": 0,  # Thermal protection of duct heater
    "expansion": 1,  # Expansion module communication
    "dp_duct_filter_overflow": 3,  # Duct filter pressure switch
    "hood": 4,  # Hood function switch
    "contamination_sensor": 5,  # Air quality sensor input
    "airing_sensor": 6,  # Humidity sensor input
    "airing_switch": 7,  # Ventilation switch
    "airing_mini": 10,  # AirS switch position "Airing"
    "fan_speed_3": 11,  # AirS switch position "3rd speed"
    "fan_speed_2": 12,  # AirS switch position "2nd speed"
    "fan_speed_1": 13,  # AirS switch position "1st speed"
    "fireplace": 14,  # Fireplace function switch
    "ppoz": 15,  # Fire alarm input
    "dp_ahu_filter_overflow": 18,  # AHU filter pressure switch (DP1)
    "ahu_filter_protection": 19,  # Thermal protection of FPX heater
    "empty_house": 21,  # Empty house input
}

# Shared option lists
SPECIAL_MODE_OPTIONS = json.loads((OPTIONS_PATH / "special_modes.json").read_text())
DAYS_OF_WEEK = json.loads((OPTIONS_PATH / "days_of_week.json").read_text())
PERIODS = json.loads((OPTIONS_PATH / "periods.json").read_text())
BYPASS_MODES = json.loads((OPTIONS_PATH / "bypass_modes.json").read_text())
GWC_MODES = json.loads((OPTIONS_PATH / "gwc_modes.json").read_text())
FILTER_TYPES = json.loads((OPTIONS_PATH / "filter_types.json").read_text())
RESET_TYPES = json.loads((OPTIONS_PATH / "reset_types.json").read_text())
MODBUS_PORTS = json.loads((OPTIONS_PATH / "modbus_ports.json").read_text())
MODBUS_BAUD_RATES = json.loads((OPTIONS_PATH / "modbus_baud_rates.json").read_text())
MODBUS_PARITY = json.loads((OPTIONS_PATH / "modbus_parity.json").read_text())
MODBUS_STOP_BITS = json.loads((OPTIONS_PATH / "modbus_stop_bits.json").read_text())

# Special function bit mappings for services
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

# Complete mapping including additional internal modes
SPECIAL_MODES = {
    "normal": 0,
    **SPECIAL_FUNCTION_MAP,
    "defrost": 2048,
    "frost_protection": 4096,
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
    # Flow registers - m³/h
    "supply_air_flow": "m³/h",
    "exhaust_air_flow": "m³/h",
    "supply_flow_rate": "m³/h",
    "exhaust_flow_rate": "m³/h",
    # Percentages
    "air_flow_rate_manual": "%",
    # Temperature set-point
    "supply_air_temperature_manual": "°C",
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
    # Voltage
    "dac_supply": "voltage",
    "dac_exhaust": "voltage",
    "dac_heater": "voltage",
    "dac_cooler": "voltage",
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
    "supply_flow_rate": "measurement",
    "exhaust_flow_rate": "measurement",
    "supply_air_flow": "measurement",
    "exhaust_air_flow": "measurement",
    "dac_supply": "measurement",
    "dac_exhaust": "measurement",
    "dac_heater": "measurement",
    "dac_cooler": "measurement",
}
