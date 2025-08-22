"""Ensure all JSON-defined Modbus registers exist in the integration."""

import json
from pathlib import Path

from custom_components.thessla_green_modbus.const import COIL_REGISTERS, DISCRETE_INPUT_REGISTERS
from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS, INPUT_REGISTERS
from typing import Iterator

from custom_components.thessla_green_modbus.utils import _to_snake_case

JSON_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "thessla_green_modbus"
    / "data"
    / "modbus_registers.json"
)

ALL_REGISTERS = {
    **COIL_REGISTERS,
    **DISCRETE_INPUT_REGISTERS,
    **HOLDING_REGISTERS,
    **INPUT_REGISTERS,
}


def _iter_json_registers() -> Iterator[str]:
    """Yield register names from the JSON file."""
    with JSON_PATH.open(encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)
    for row in data.get("registers", []):
        func = row.get("function")
        if func in {"01", "02", "03", "04"}:
            name = _to_snake_case(row["name"])
            name = {
                "date_time_rrmm": "date_time",
                "date_time_ddtt": "date_time",
                "date_time_ggmm": "date_time",
                "date_time_sscc": "date_time",
                "lock_date_rrmm": "lock_date",
                "lock_date_ddtt": "lock_date",
                "lock_date_ggmm": "lock_date",
                "lock_date_rr": "lock_date",
                "lock_date_mm": "lock_date",
                "lock_date_dd": "lock_date",
            }.get(name, name)
            yield name


def test_all_json_registers_defined() -> None:
    """Ensure every JSON entry is defined in the codebase."""
    missing = [name for name in _iter_json_registers() if name not in ALL_REGISTERS]
    assert not missing, f"Missing registers: {missing}"  # nosec B101
