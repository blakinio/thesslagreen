"""Constants and register definitions for the ThesslaGreen Modbus integration."""

from typing import Any, Dict

# Large data structures are provided by dedicated modules
from .entity_mappings import ENTITY_MAPPINGS, NUMBER_ENTITY_MAPPINGS
from .multipliers import REGISTER_MULTIPLIERS
from .registers import HOLDING_REGISTERS, INPUT_REGISTERS

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
    "duct_water_heater_pump": 5,  # State of circulation pump relay output
    "bypass": 9,  # State of bypass damper actuator output
    "info": 10,  # State of system operation confirmation output (O1)
    "power_supply_fans": 11,  # State of fan power relay output
    "heating_cable": 12,  # State of heating cable power relay output
    "work_permit": 13,  # State of operation confirmation relay output (Expansion)
    "gwc": 14,  # State of GWC relay output
    "hood": 15,  # State of hood damper power output
}

# DISCRETE INPUT REGISTERS (02 - READ DISCRETE INPUTS) - Digital input states
DISCRETE_INPUT_REGISTERS = {
    "expansion": 0,  # Expansion module state
    "contamination_sensor": 1,  # Contamination sensor state
    "external_contact_1": 2,  # External contact 1 state
    "external_contact_2": 3,  # External contact 2 state
    "external_contact_3": 4,  # External contact 3 state
    "external_contact_4": 5,  # External contact 4 state
    "fire_alarm": 6,  # Fire alarm state
    "frost_alarm": 7,  # Frost alarm state
    "filter_alarm": 8,  # Filter alarm state
    "maintenance_alarm": 9,  # Maintenance alarm state
    "sensor_error": 10,  # Sensor error status
    "communication_error": 11,  # Communication error status
    "fan_error": 12,  # Fan error status
    "heater_error": 13,  # Heater error status
    "cooler_error": 14,  # Cooler error status
    "bypass_error": 15,  # Bypass error status
    "gwc_error": 16,  # GWC error status
    "expansion_error": 17,  # Expansion module error status
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
    "co2_reduction": "kg",
    "air_quality_index": "",
    "fault_counter": "",
    "maintenance_counter": "",
    "filter_replacement_counter": "",
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
    # Mass
    "co2_reduction": "weight",
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
