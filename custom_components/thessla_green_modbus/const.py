"""Constants for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import importlib.util
import re
import sys
from functools import cache, lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

try:  # pragma: no cover - optional during isolated tests
    from .registers.loader import get_registers_by_function
except (ImportError, AttributeError):  # pragma: no cover - fallback when stubs incomplete

    def get_registers_by_function(fn: str):
        return []


if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.core import HomeAssistant

# Maximum number of registers that can be read in a single request.
# The registers loader previously created a circular dependency with
# ``modbus_helpers`` but this has been resolved, allowing the import to
# appear before this constant.
MAX_BATCH_REGISTERS = 16


@cache
def _build_map(fn: str) -> dict[str, int]:
    return {r.name: r.address for r in get_registers_by_function(fn) if r.name}


COIL_REGISTERS = _build_map("coil")
DISCRETE_INPUT_REGISTERS = _build_map("discrete")
HOLDING_REGISTERS = _build_map("holding")
INPUT_REGISTERS = _build_map("input")
def coil_registers() -> dict[str, int]:
    return _build_map("coil")


def discrete_input_registers() -> dict[str, int]:
    return _build_map("discrete")


def holding_registers() -> dict[str, int]:
    return _build_map("holding")


def input_registers() -> dict[str, int]:
    return _build_map("input")


@lru_cache(maxsize=1)
def multi_register_sizes() -> dict[str, int]:
    return {
        r.name: r.length for r in get_registers_by_function("holding") if r.name and r.length > 1
    }


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
DEFAULT_BACKOFF = 0.0
DEFAULT_BACKOFF_JITTER = 0.0
DEFAULT_MAX_BACKOFF = 30.0
MIN_SCAN_INTERVAL = 5

# Connection / transport configuration
CONF_CONNECTION_TYPE = "connection_type"
CONF_SERIAL_PORT = "serial_port"
CONF_BAUD_RATE = "baud_rate"
CONF_PARITY = "parity"
CONF_STOP_BITS = "stop_bits"

CONNECTION_TYPE_TCP = "tcp"
CONNECTION_TYPE_RTU = "rtu"
DEFAULT_CONNECTION_TYPE = CONNECTION_TYPE_TCP

# Default serial settings mirror the values used by Thessla Green controllers
DEFAULT_SERIAL_PORT = ""
DEFAULT_BAUD_RATE = 19200
DEFAULT_PARITY = "even"
DEFAULT_STOP_BITS = 1

SERIAL_PARITY_MAP = {
    "none": "N",
    "even": "E",
    "odd": "O",
}

SERIAL_STOP_BITS_MAP = {
    "1": 1,
    "2": 2,
    1: 1,
    2: 2,
}

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
CONF_BACKOFF = "backoff"
CONF_BACKOFF_JITTER = "backoff_jitter"
CONF_FORCE_FULL_REGISTER_LIST = "force_full_register_list"
CONF_SCAN_UART_SETTINGS = "scan_uart_settings"
CONF_SKIP_MISSING_REGISTERS = "skip_missing_registers"
CONF_AIRFLOW_UNIT = "airflow_unit"
CONF_DEEP_SCAN = "deep_scan"  # Perform exhaustive raw register scan for diagnostics
CONF_MAX_REGISTERS_PER_REQUEST = "max_registers_per_request"
CONF_LOG_LEVEL = "log_level"
CONF_SAFE_SCAN = "safe_scan"

AIRFLOW_UNIT_M3H = "m3h"
AIRFLOW_UNIT_PERCENTAGE = "percentage"
DEFAULT_AIRFLOW_UNIT = AIRFLOW_UNIT_M3H

# Registers reporting airflow that changed units from percentage to m³/h
AIRFLOW_RATE_REGISTERS = {"supply_flow_rate", "exhaust_flow_rate"}

DEFAULT_SCAN_UART_SETTINGS = False
DEFAULT_SKIP_MISSING_REGISTERS = False
DEFAULT_DEEP_SCAN = False
DEFAULT_MAX_REGISTERS_PER_REQUEST = MAX_BATCH_REGISTERS
DEFAULT_LOG_LEVEL = "info"
LOG_LEVEL_OPTIONS = ["debug", "info", "warning", "error"]
DEFAULT_SAFE_SCAN = False

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


# Migration helpers
_ENTITY_LOOKUP: dict[str, tuple[str, str | None, int | None]] | None = None


def _sanitize_identifier(value: str) -> str:
    """Sanitize identifier components used inside unique IDs."""

    sanitized = re.sub(r"[^0-9A-Za-z_-]", "-", value)
    sanitized = re.sub(r"-{2,}", "-", sanitized)
    sanitized = re.sub(r"_{2,}", "_", sanitized)
    return sanitized.strip("-_")


def device_unique_id_prefix(
    serial_number: str | None,
    host: str,
    port: int,
) -> str:
    """Return the device specific prefix used in entity unique IDs."""

    if serial_number:
        serial_token = _sanitize_identifier(serial_number)
        if serial_token:
            return serial_token

    host_part = _sanitize_identifier(host.replace(":", "-")) if host else ""
    port_part = _sanitize_identifier(str(port)) if port is not None else ""

    if host_part and port_part:
        return f"{host_part}-{port_part}"
    if host_part:
        return host_part
    if port_part:
        return f"device-{port_part}"
    return "device"


def _build_entity_lookup() -> dict[str, tuple[str, str | None, int | None]]:
    """Build mapping of entity keys to register info."""
    global _ENTITY_LOOKUP
    if _ENTITY_LOOKUP is None:
        from .entity_mappings import ENTITY_MAPPINGS as _MAP

        lookup: dict[str, tuple[str, str | None, int | None]] = {}
        for platform in ("sensor", "binary_sensor", "switch", "select", "number"):
            for key, cfg in _MAP.get(platform, {}).items():
                register = cfg.get("register", key)
                lookup[key] = (register, cfg.get("register_type"), cfg.get("bit"))
        _ENTITY_LOOKUP = lookup
    return _ENTITY_LOOKUP


def migrate_unique_id(
    unique_id: str,
    *,
    serial_number: str | None,
    host: str,
    port: int,
    slave_id: int,
) -> str:
    """Migrate a legacy unique_id to the current format."""

    uid = unique_id.replace(":", "-")
    prefix = device_unique_id_prefix(serial_number, host, port)

    for unit in (AIRFLOW_UNIT_M3H, AIRFLOW_UNIT_PERCENTAGE):
        suffix = f"_{unit}"
        if uid.endswith(suffix):
            uid = uid[: -len(suffix)]
            break

    pattern_new = rf"{re.escape(prefix)}_{slave_id}_[^_]+_\d+(?:_bit\d+)?$"
    if re.fullmatch(pattern_new, uid):
        return uid

    if uid.startswith(f"{DOMAIN}_"):
        uid_no_domain = uid[len(DOMAIN) + 1 :]
    else:
        uid_no_domain = uid

    lookup = _build_entity_lookup()

    def _bit_index(bit: int | None) -> int | None:
        return bit.bit_length() - 1 if bit is not None else None

    def _register_address(register: str, register_type: str | None) -> int | None:
        if register_type == "holding_registers":
            return holding_registers().get(register)
        if register_type == "input_registers":
            return input_registers().get(register)
        if register_type == "coil_registers":
            return coil_registers().get(register)
        if register_type == "discrete_inputs":
            return discrete_input_registers().get(register)
        return None

    reverse_by_address: dict[tuple[int, int | None], str] = {}
    register_to_key: dict[str, str] = {}

    for key, (register_name, register_type, bit) in lookup.items():
        register_to_key.setdefault(register_name, key)
        address = _register_address(register_name, register_type)
        if address is None:
            continue
        reverse_by_address.setdefault((address, _bit_index(bit)), key)

    match = re.match(rf".*_{slave_id}_(.+)", uid_no_domain)
    remainder = match.group(1) if match else None

    base_uid: str | None = None

    if remainder:
        match_address = re.fullmatch(r"(\d+)(?:_bit(\d+))?", remainder)
        if match_address:
            address = int(match_address.group(1))
            bit_index = int(match_address.group(2)) if match_address.group(2) else None
            key = reverse_by_address.get((address, bit_index)) or reverse_by_address.get(
                (address, None)
            )
            if key:
                bit_suffix = f"_bit{bit_index}" if bit_index is not None else ""
                base_uid = f"{slave_id}_{key}_{address}{bit_suffix}"
        else:
            key = None
            register_name: str | None = None
            bit_index: int | None = None

            if remainder in lookup:
                key = remainder
                register_name, register_type, bit = lookup[key]
                bit_index = _bit_index(bit)
            elif remainder in register_to_key:
                key = register_to_key[remainder]
                register_name, register_type, bit = lookup[key]
                bit_index = _bit_index(bit)

            if register_name:
                address = _register_address(register_name, register_type)
                if address is not None:
                    bit_suffix = f"_bit{bit_index}" if bit_index is not None else ""
                    base_uid = f"{slave_id}_{key}_{address}{bit_suffix}"
            elif remainder == "fan":
                base_uid = f"{slave_id}_fan_0"

    if base_uid is None:
        fallback = uid_no_domain
        if not fallback.startswith(f"{prefix}_"):
            fallback = f"{prefix}_{fallback}"
        return fallback

    if base_uid.startswith(prefix):
        return base_uid

    return f"{prefix}_{base_uid}"


# Mapping of writable register names to Home Assistant number entity metadata
# (unit, ranges, scaling factors, etc.)
NUMBER_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
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
ENTITY_MAPPINGS: dict[str, dict[str, dict[str, Any]]] = {
    "number": NUMBER_ENTITY_MAPPINGS,
}

# Aggregated entity mappings for all platforms.  Additional platforms can be
# added here in the future.
# ============================================================================
# Complete register mapping from MODBUS_USER_AirPack_Home_08.2021.01 PDF
# https://thesslagreen.com/wp-content/uploads/MODBUS_USER_AirPack_Home_08.2021.01.pdf
# ============================================================================


def _load_json_option(filename: str) -> list[Any]:
    """Load an option list from a JSON file in ``OPTIONS_PATH``."""

    import json

    try:
        return cast(
            list[Any],
            json.loads((OPTIONS_PATH / filename).read_text(encoding="utf-8")),
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return []


async def async_setup_options(hass: HomeAssistant | None = None) -> None:
    """Asynchronously populate option lists from JSON files.

    When ``hass`` is provided, file I/O is offloaded to the executor.
    If Home Assistant utilities are unavailable, the lists are populated
    synchronously for compatibility with tests.
    """

    global SPECIAL_MODE_OPTIONS, DAYS_OF_WEEK, PERIODS, BYPASS_MODES, GWC_MODES
    global FILTER_TYPES, RESET_TYPES, MODBUS_PORTS, MODBUS_BAUD_RATES
    global MODBUS_PARITY, MODBUS_STOP_BITS

    filenames = [
        ("special_modes.json", "SPECIAL_MODE_OPTIONS"),
        ("days_of_week.json", "DAYS_OF_WEEK"),
        ("periods.json", "PERIODS"),
        ("bypass_modes.json", "BYPASS_MODES"),
        ("gwc_modes.json", "GWC_MODES"),
        ("filter_types.json", "FILTER_TYPES"),
        ("reset_types.json", "RESET_TYPES"),
        ("modbus_ports.json", "MODBUS_PORTS"),
        ("modbus_baud_rates.json", "MODBUS_BAUD_RATES"),
        ("modbus_parity.json", "MODBUS_PARITY"),
        ("modbus_stop_bits.json", "MODBUS_STOP_BITS"),
    ]

    if hass is not None:
        results = await asyncio.gather(
            *[hass.async_add_executor_job(_load_json_option, fn) for fn, _ in filenames]
        )
    else:
        results = [_load_json_option(fn) for fn, _ in filenames]

    for (_, name), value in zip(filenames, results, strict=False):
        globals()[name] = value


def _sync_setup_options() -> None:
    """Populate option lists synchronously."""

    global SPECIAL_MODE_OPTIONS, DAYS_OF_WEEK, PERIODS, BYPASS_MODES, GWC_MODES
    global FILTER_TYPES, RESET_TYPES, MODBUS_PORTS, MODBUS_BAUD_RATES
    global MODBUS_PARITY, MODBUS_STOP_BITS

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


# Shared option lists loaded during setup
SPECIAL_MODE_OPTIONS: list[Any] = []
DAYS_OF_WEEK: list[Any] = []
PERIODS: list[Any] = []
BYPASS_MODES: list[Any] = []
GWC_MODES: list[Any] = []
FILTER_TYPES: list[Any] = []
RESET_TYPES: list[Any] = []
MODBUS_PORTS: list[Any] = []
MODBUS_BAUD_RATES: list[Any] = []
MODBUS_PARITY: list[Any] = []
MODBUS_STOP_BITS: list[Any] = []


try:  # pragma: no cover - handle partially initialized module
    _HAS_HA = importlib.util.find_spec("homeassistant") is not None
except (ImportError, ValueError):
    _HAS_HA = False

# Load option lists immediately when Home Assistant isn't available or during tests
if not _HAS_HA or "pytest" in sys.modules:  # pragma: no cover - test env
    _sync_setup_options()

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
