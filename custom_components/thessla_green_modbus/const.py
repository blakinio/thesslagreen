"""Constants and register definitions for the ThesslaGreen Modbus integration."""

from typing import Any, Dict

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

# Mapping of writable register names to Home Assistant number entity metadata
# (unit, ranges, scaling factors, etc.)
NUMBER_ENTITY_MAPPINGS: Dict[str, Dict[str, Any]] = {
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

# Aggregated entity mappings for all platforms.  Additional platforms can be
# added here in the future.
ENTITY_MAPPINGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "number": NUMBER_ENTITY_MAPPINGS,
}
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
    # Legacy register shares the same scaling as required_temperature
    "required_temperature_legacy": 0.5,
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
