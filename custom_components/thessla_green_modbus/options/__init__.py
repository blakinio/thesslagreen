"""Options loading helpers for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Directory containing the JSON option files (this package directory).
OPTIONS_PATH = Path(__file__).parent

# Shared option lists populated by async_setup_options during integration setup.
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
_OPTIONS_INIT_LOCK: asyncio.Lock | None = None


def _load_json_option(filename: str) -> list[Any]:
    """Load an option list from a JSON file in OPTIONS_PATH."""
    try:
        return cast(
            list[Any],
            json.loads((OPTIONS_PATH / filename).read_text(encoding="utf-8")),
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _get_options_init_lock() -> asyncio.Lock:
    """Return a shared lock guarding global options initialization."""
    global _OPTIONS_INIT_LOCK
    if _OPTIONS_INIT_LOCK is None:
        _OPTIONS_INIT_LOCK = asyncio.Lock()
    return _OPTIONS_INIT_LOCK


async def async_setup_options(hass: HomeAssistant | None = None) -> None:
    """Asynchronously populate option lists from JSON files.

    When ``hass`` is provided, file I/O is offloaded to the executor.
    If Home Assistant utilities are unavailable, the lists are populated
    synchronously when running in tests.
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

    async with _get_options_init_lock():
        if hass is not None:
            results = await asyncio.gather(
                *[hass.async_add_executor_job(_load_json_option, fn) for fn, _ in filenames]
            )
        else:
            results = [_load_json_option(fn) for fn, _ in filenames]

        (
            SPECIAL_MODE_OPTIONS,
            DAYS_OF_WEEK,
            PERIODS,
            BYPASS_MODES,
            GWC_MODES,
            FILTER_TYPES,
            RESET_TYPES,
            MODBUS_PORTS,
            MODBUS_BAUD_RATES,
            MODBUS_PARITY,
            MODBUS_STOP_BITS,
        ) = results


__all__ = [
    "BYPASS_MODES",
    "DAYS_OF_WEEK",
    "FILTER_TYPES",
    "GWC_MODES",
    "MODBUS_BAUD_RATES",
    "MODBUS_PARITY",
    "MODBUS_PORTS",
    "MODBUS_STOP_BITS",
    "OPTIONS_PATH",
    "PERIODS",
    "RESET_TYPES",
    "SPECIAL_MODE_OPTIONS",
    "_OPTIONS_INIT_LOCK",
    "_get_options_init_lock",
    "_load_json_option",
    "async_setup_options",
]
