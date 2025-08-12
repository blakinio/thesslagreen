"""Ensure all CSV-defined Modbus registers exist in the integration."""

import csv
from pathlib import Path

from custom_components.thessla_green_modbus.const import COIL_REGISTERS, DISCRETE_INPUT_REGISTERS
from custom_components.thessla_green_modbus.device_scanner import _to_snake_case
from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS, INPUT_REGISTERS

CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "thessla_green_modbus"
    / "data"
    / "modbus_registers.csv"
)

ALL_REGISTERS = {
    **COIL_REGISTERS,
    **DISCRETE_INPUT_REGISTERS,
    **HOLDING_REGISTERS,
    **INPUT_REGISTERS,
}


def _iter_csv_registers() -> list[str]:
    """Yield register names from the CSV file."""
    with CSV_PATH.open(newline="") as csvfile:
        reader = csv.DictReader(
            row for row in csvfile if row.strip() and not row.lstrip().startswith("#")
        )
        for row in reader:
            func = row.get("Function_Code")
            if func in {"01", "02", "03", "04"}:
                yield _to_snake_case(row["Register_Name"])


def test_all_csv_registers_defined() -> None:
    """Ensure every CSV entry is defined in the codebase."""
    missing = [name for name in _iter_csv_registers() if name not in ALL_REGISTERS]
    assert not missing, f"Missing registers: {missing}"  # nosec B101
