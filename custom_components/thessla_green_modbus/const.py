"""Constants for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import importlib.util
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, cast

from custom_components.thessla_green_modbus.registers.loader import (
    get_registers_by_function,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.core import HomeAssistant

# Maximum number of registers that can be read in a single request.
# The registers loader previously created a circular dependency with
# ``modbus_helpers`` but this has been resolved, allowing the import to
# appear before this constant.
MAX_BATCH_REGISTERS = 16


@lru_cache(maxsize=None)
def _build_map(fn: str) -> dict[str, int]:
    return {r.name: r.address for r in get_registers_by_function(fn) if r.name}


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
        r.name: r.length
        for r in get_registers_by_function("holding")
        if r.name and r.length > 1
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
CONF_MAX_REGISTERS_PER_REQUEST = "max_registers_per_request"

AIRFLOW_UNIT_M3H = "m3h"
AIRFLOW_UNIT_PERCENTAGE = "percentage"
DEFAULT_AIRFLOW_UNIT = AIRFLOW_UNIT_M3H

# Registers reporting airflow that changed units from percentage to m³/h
AIRFLOW_RATE_REGISTERS = {"supply_flow_rate", "exhaust_flow_rate"}

DEFAULT_SCAN_UART_SETTINGS = False
DEFAULT_SKIP_MISSING_REGISTERS = False
DEFAULT_DEEP_SCAN = False
DEFAULT_MAX_REGISTERS_PER_REQUEST = MAX_BATCH_REGISTERS

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

    for unit in (AIRFLOW_UNIT_M3H, AIRFLOW_UNIT_PERCENTAGE):
        suffix = f"_{unit}"
        if uid.endswith(suffix):
            uid = uid[: -len(suffix)]
            break

    pattern_new = rf"{slave_id}_\d+(?:_bit\d+)?$"
    if re.fullmatch(pattern_new, uid):
        return uid

    if uid.startswith(f"{DOMAIN}_"):
        uid_no_domain = uid[len(DOMAIN) + 1 :]
    else:
        uid_no_domain = uid

    match = re.match(rf".*_{slave_id}_(.+)", uid_no_domain)
    if not match:
        return uid_no_domain

    remainder = match.group(1)

    if re.fullmatch(r"\d+(?:_bit\d+)?", remainder):
        return f"{slave_id}_{remainder}"

    lookup = _build_entity_lookup()
    register_name, register_type, bit = lookup.get(remainder, (remainder, None, None))
    address: int | None = None
    if register_type == "holding_registers":
        address = holding_registers().get(register_name)
    elif register_type == "input_registers":
        address = input_registers().get(register_name)
    elif register_type == "coil_registers":
        address = coil_registers().get(register_name)
    elif register_type == "discrete_inputs":
        address = discrete_input_registers().get(register_name)

    if address is not None:
        bit_suffix = f"_bit{bit.bit_length() - 1}" if bit is not None else ""
        return f"{slave_id}_{address}{bit_suffix}"

    if remainder == "fan":
        return f"{slave_id}_0"

    return uid_no_domain


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

    for (_, name), value in zip(filenames, results):
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
