"""Constants and register definitions for the ThesslaGreen Modbus integration."""

import json
from pathlib import Path

from .registers import (  # noqa: F401
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
)

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
