"""Constants and register definitions for the ThesslaGreen Modbus integration."""

import json
import logging
from pathlib import Path
from typing import Any, cast

from .registers import (  # noqa: F401
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
)

OPTIONS_PATH = Path(__file__).parent / "options"
_LOGGER = logging.getLogger(__name__)


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
CONF_SCAN_UART_SETTINGS = "scan_uart_settings"
CONF_SKIP_MISSING_REGISTERS = "skip_missing_registers"

DEFAULT_SCAN_UART_SETTINGS = False
DEFAULT_SKIP_MISSING_REGISTERS = False

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

# ============================================================================
# Complete register mapping from MODBUS_USER_AirPack_Home_08.2021.01 PDF
# ============================================================================


def _load_json_option(filename: str) -> list[Any]:
    """Load an option list from a JSON file in ``OPTIONS_PATH``.

    Returns an empty list if the file does not exist or cannot be parsed.
    ``filename`` should be relative to ``OPTIONS_PATH``.
    """

    try:
        return cast(list[Any], json.loads((OPTIONS_PATH / filename).read_text()))
    except (FileNotFoundError, json.JSONDecodeError) as err:
        _LOGGER.warning("Failed to load %s: %s", filename, err)
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
