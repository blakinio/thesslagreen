"""Constants and register definitions for the ThesslaGreen Modbus integration."""

import json
from pathlib import Path
from typing import Any, Dict, cast

from .registers import get_registers_by_function


def _build_map(fn: str) -> dict[str, int]:
    return {r.name: r.address for r in get_registers_by_function(fn) if r.name}


COIL_REGISTERS = _build_map("coil")
DISCRETE_INPUT_REGISTERS = _build_map("discrete")
HOLDING_REGISTERS = _build_map("holding")
INPUT_REGISTERS = _build_map("input")

OPTIONS_PATH = Path(__file__).parent / "options"

# Integration constants
DOMAIN = "thessla_green_modbus"
MANUFACTURER = "ThesslaGreen"
MODEL = "AirPack Home Series 4"
# Fallback model name used when the unit does not report one
UNKNOWN_MODEL = "Unknown"

# Connection defaults
DEFAULT_NAME = "ThesslaGreen"
DEFAULT_PORT = 502  # Standard Modbus TCP port; legacy versions used 8899
DEFAULT_SLAVE_ID = 10
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3

# Sensor constants
SENSOR_UNAVAILABLE = 0x8000  # Indicates missing/invalid sensor reading

# Registers that may report SENSOR_UNAVAILABLE (0x8000) when a sensor
# is missing or disconnected. Derived from the Thessla Green Modbus
# specification where each of these registers documents this sentinel
# value. The list is intentionally explicit to also serve as inline
# documentation for developers.
SENSOR_UNAVAILABLE_REGISTERS = {
    "outside_temperature",
    "supply_temperature",
    "exhaust_temperature",
    "fpx_temperature",
    "duct_supply_temperature",
    "gwc_temperature",
    "ambient_temperature",
    "heating_temperature",
    "supply_flow_rate",
    "exhaust_flow_rate",
}



# Configuration options
CONF_SLAVE_ID = "slave_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_RETRY = "retry"
CONF_FORCE_FULL_REGISTER_LIST = "force_full_register_list"
CONF_SCAN_UART_SETTINGS = "scan_uart_settings"
CONF_SKIP_MISSING_REGISTERS = "skip_missing_registers"
CONF_AIRFLOW_UNIT = "airflow_unit"
CONF_DEEP_SCAN = "deep_scan"  # Perform exhaustive raw register scan for diagnostics
CONF_SCAN_MAX_BLOCK_SIZE = "scan_max_block_size"

AIRFLOW_UNIT_M3H = "m3h"
AIRFLOW_UNIT_PERCENTAGE = "percentage"
DEFAULT_AIRFLOW_UNIT = AIRFLOW_UNIT_M3H

# Registers reporting airflow that changed units from percentage to m³/h
AIRFLOW_RATE_REGISTERS = {"supply_flow_rate", "exhaust_flow_rate"}

DEFAULT_SCAN_UART_SETTINGS = False
DEFAULT_SKIP_MISSING_REGISTERS = False
DEFAULT_DEEP_SCAN = False
DEFAULT_SCAN_MAX_BLOCK_SIZE = 64

# Registers that are known to be unavailable on some devices
KNOWN_MISSING_REGISTERS = {
    "input_registers": {"compilation_days"},
    "holding_registers": set(),
    "coil_registers": set(),
    "discrete_inputs": set(),
}

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

# Aggregated entity mappings for backward compatibility
ENTITY_MAPPINGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "number": NUMBER_ENTITY_MAPPINGS,
}

# Aggregated entity mappings for all platforms.  Additional platforms can be
# added here in the future.
# ============================================================================
# Complete register mapping from MODBUS_USER_AirPack_Home_08.2021.01 PDF
# ============================================================================


def _load_json_option(filename: str) -> list[Any]:
    """Load an option list from a JSON file in ``OPTIONS_PATH``.

    Returns an empty list if the file does not exist or cannot be parsed.
    ``filename`` should be relative to ``OPTIONS_PATH``.
    """

    try:
        return cast(
            list[Any],
            json.loads((OPTIONS_PATH / filename).read_text(encoding="utf-8")),
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# Shared option lists
SPECIAL_MODE_OPTIONS = _load_json_option("special_modes.json")
DAYS_OF_WEEK = _load_json_option("days_of_week.json")
PERIODS = _load_json_option("periods.json")
BYPASS_MODES = _load_json_option("bypass_modes.json")
GWC_MODES = _load_json_option("gwc_modes.json")
FILTER_TYPES = _load_json_option("filter_types.json")
RESET_TYPES = _load_json_option("reset_types.json")
MODBUS_PORTS = _load_json_option("modbus_ports.json")
MODBUS_BAUD_RATES = _load_json_option("modbus_baud_rates.json")
MODBUS_PARITY = _load_json_option("modbus_parity.json")
MODBUS_STOP_BITS = _load_json_option("modbus_stop_bits.json")

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
