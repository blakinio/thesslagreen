"""Entity mapping definitions for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .utils import _to_snake_case

CSV_PATH = Path(__file__).parent / "data" / "modbus_registers.csv"


def _parse_float(value: str) -> float:
    """Parse a numeric value which may be in decimal or hexadecimal format."""
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        try:
            return float(int(value, 0))
        except ValueError:
            return 0.0


def _load_number_mappings() -> dict[str, dict[str, Any]]:
    """Load writable register metadata from the CSV file."""
    with CSV_PATH.open(encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(
            row for row in csvfile if row.strip() and not row.lstrip().startswith("#")
        )

        rows: list[tuple[str, int, dict[str, Any]]] = []
        for row in reader:
            if row["Function_Code"] != "03" or row["Access"] != "R/W":
                continue

            name = _to_snake_case(row["Register_Name"])
            addr = int(row["Address_DEC"])
            step = _parse_float(row["Multiplier"])
            step = step if step else 1.0

            config: dict[str, Any] = {
                "min": _parse_float(row["Min"]),
                "max": _parse_float(row["Max"]),
                "step": step,
            }

            if step not in (0, 1):
                config["scale"] = step

            unit = row.get("Unit")
            if unit:
                config["unit"] = unit

            rows.append((name, addr, config))

    # Ensure unique register names
    rows.sort(key=lambda r: r[1])
    counts: dict[str, int] = {}
    for name, _, _ in rows:
        counts[name] = counts.get(name, 0) + 1

    seen: dict[str, int] = {}
    mapping: dict[str, dict[str, Any]] = {}
    for name, _, cfg in rows:
        if counts[name] > 1:
            idx = seen.get(name, 0) + 1
            seen[name] = idx
            key = f"{name}_{idx}"
        else:
            key = name
        mapping[key] = cfg

    return mapping


# Mapping of read-only registers to sensor metadata
NUMBER_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = _load_number_mappings()
SENSOR_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {
    # Temperature sensors
    "outside_temperature": {
        "translation_key": "outside_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "register_type": "input_registers",
    },
    "supply_temperature": {
        "translation_key": "supply_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "register_type": "input_registers",
    },
    "exhaust_temperature": {
        "translation_key": "exhaust_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "register_type": "input_registers",
    },
    "fpx_temperature": {
        "translation_key": "fpx_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "register_type": "input_registers",
    },
    "duct_supply_temperature": {
        "translation_key": "duct_supply_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "register_type": "input_registers",
    },
    "gwc_temperature": {
        "translation_key": "gwc_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "register_type": "input_registers",
    },
    "ambient_temperature": {
        "translation_key": "ambient_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "register_type": "input_registers",
    },
    "heating_temperature": {
        "translation_key": "heating_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "register_type": "input_registers",
    },
    # System information
    "version_major": {
        "translation_key": "version_major",
        "register_type": "input_registers",
    },
    "version_minor": {
        "translation_key": "version_minor",
        "register_type": "input_registers",
    },
    "version_patch": {
        "translation_key": "version_patch",
        "register_type": "input_registers",
    },
    "day_of_week": {
        "translation_key": "day_of_week",
        "register_type": "input_registers",
    },
    "period": {
        "translation_key": "period",
        "register_type": "input_registers",
    },
    "compilation_days": {
        "translation_key": "compilation_days",
        "register_type": "input_registers",
    },
    "compilation_seconds": {
        "translation_key": "compilation_seconds",
        "register_type": "input_registers",
    },
    "serial_number_1": {
        "translation_key": "serial_number_1",
        "register_type": "input_registers",
    },
    "serial_number_2": {
        "translation_key": "serial_number_2",
        "register_type": "input_registers",
    },
    "serial_number_3": {
        "translation_key": "serial_number_3",
        "register_type": "input_registers",
    },
    "serial_number_4": {
        "translation_key": "serial_number_4",
        "register_type": "input_registers",
    },
    "serial_number_5": {
        "translation_key": "serial_number_5",
        "register_type": "input_registers",
    },
    "serial_number_6": {
        "translation_key": "serial_number_6",
        "register_type": "input_registers",
    },
    # Flow sensors
    "supply_flow_rate": {
        "translation_key": "supply_flow_rate",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "input_registers",
    },
    "exhaust_flow_rate": {
        "translation_key": "exhaust_flow_rate",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "input_registers",
    },
    "supply_air_flow": {
        "translation_key": "supply_air_flow",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "holding_registers",
    },
    "exhaust_air_flow": {
        "translation_key": "exhaust_air_flow",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "holding_registers",
    },
    "max_supply_air_flow_rate": {
        "translation_key": "max_supply_air_flow_rate",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "holding_registers",
    },
    "max_exhaust_air_flow_rate": {
        "translation_key": "max_exhaust_air_flow_rate",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "holding_registers",
    },
    "nominal_supply_air_flow": {
        "translation_key": "nominal_supply_air_flow",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "holding_registers",
    },
    "nominal_exhaust_air_flow": {
        "translation_key": "nominal_exhaust_air_flow",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "holding_registers",
    },
    "air_flow_rate_manual": {
        "translation_key": "air_flow_rate_manual",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "holding_registers",
    },
    "air_flow_rate_temporary_2": {
        "translation_key": "air_flow_rate_temporary_2",
        "state_class": "measurement",
        "unit": "m3/h",
        "register_type": "holding_registers",
    },
    "bypass_off": {
        "translation_key": "bypass_off",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit": "°C",
        "register_type": "holding_registers",
    },
    # DAC voltages
    "dac_supply": {
        "translation_key": "dac_supply",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit": "V",
        "register_type": "holding_registers",
    },
    "dac_exhaust": {
        "translation_key": "dac_exhaust",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit": "V",
        "register_type": "holding_registers",
    },
    "dac_heater": {
        "translation_key": "dac_heater",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit": "V",
        "register_type": "holding_registers",
    },
    "dac_cooler": {
        "translation_key": "dac_cooler",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit": "V",
        "register_type": "holding_registers",
    },
    # Percentage coefficients
    "supply_percentage": {
        "translation_key": "supply_percentage",
        "state_class": "measurement",
        "unit": "%",
        "register_type": "input_registers",
    },
    "exhaust_percentage": {
        "translation_key": "exhaust_percentage",
        "state_class": "measurement",
        "unit": "%",
        "register_type": "input_registers",
    },
    "min_percentage": {
        "translation_key": "min_percentage",
        "state_class": "measurement",
        "unit": "%",
        "register_type": "input_registers",
    },
    "max_percentage": {
        "translation_key": "max_percentage",
        "state_class": "measurement",
        "unit": "%",
        "register_type": "input_registers",
    },
    # System modes and flags
    "constant_flow_active": {
        "translation_key": "constant_flow_active",
        "register_type": "input_registers",
    },
    "water_removal_active": {
        "translation_key": "water_removal_active",
        "register_type": "input_registers",
    },
    "cf_version": {
        "translation_key": "cf_version",
        "register_type": "holding_registers",
    },
    "antifreeze_mode": {
        "translation_key": "antifreeze_mode",
        "register_type": "holding_registers",
    },
    "antifreez_stage": {
        "translation_key": "antifreez_stage",
        "register_type": "holding_registers",
    },
    "mode": {
        "translation_key": "mode",
        "register_type": "holding_registers",
        "value_map": {0: "auto", 1: "manual", 2: "temporary"},
    },
    "season_mode": {
        "translation_key": "season_mode",
        "register_type": "holding_registers",
        "value_map": {0: "winter", 1: "summer"},
    },
    "filter_change": {
        "translation_key": "filter_change",
        "register_type": "holding_registers",
        "value_map": {
            1: "presostat",
            2: "flat_filters",
            3: "cleanpad",
            4: "cleanpad_pure",
        },
    },
    "gwc_mode": {
        "translation_key": "gwc_mode",
        "register_type": "holding_registers",
        "value_map": {0: "off", 1: "auto", 2: "forced"},
    },
    "gwc_regen_flag": {
        "translation_key": "gwc_regen_flag",
        "register_type": "holding_registers",
    },
    "comfort_mode": {
        "translation_key": "comfort_mode",
        "register_type": "holding_registers",
    },
    "bypass_mode": {
        "translation_key": "bypass_mode",
        "register_type": "holding_registers",
        "value_map": {0: "auto", 1: "open", 2: "closed"},
    },
}
BINARY_SENSOR_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}
SWITCH_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}
SELECT_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}

ENTITY_MAPPINGS: dict[str, dict[str, dict[str, Any]]] = {
    "number": NUMBER_ENTITY_MAPPINGS,
    "sensor": SENSOR_ENTITY_MAPPINGS,
    "binary_sensor": BINARY_SENSOR_ENTITY_MAPPINGS,
    "switch": SWITCH_ENTITY_MAPPINGS,
    "select": SELECT_ENTITY_MAPPINGS,
}
