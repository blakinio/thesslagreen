"""Validate coverage of register definitions against CSV specification."""

import csv
from pathlib import Path

from custom_components.thessla_green_modbus.const import COIL_REGISTERS, DISCRETE_INPUT_REGISTERS
from custom_components.thessla_green_modbus.device_scanner import _to_snake_case
from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS, INPUT_REGISTERS

FUNCTION_MAP = {
    "01": COIL_REGISTERS,
    "02": DISCRETE_INPUT_REGISTERS,
    "03": HOLDING_REGISTERS,
    "04": INPUT_REGISTERS,
}

CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "thessla_green_modbus"
    / "data"
    / "modbus_registers.csv"
)


def load_csv_mappings() -> dict[str, dict[str, int]]:
    path = pathlib.Path("custom_components/thessla_green_modbus/data/modbus_registers.csv")
    result: dict[str, dict[str, int]] = {code: {} for code in FUNCTION_MAP}
    with CSV_PATH.open(newline="") as csvfile:
        reader = csv.DictReader(
            row for row in csvfile if row.strip() and not row.lstrip().startswith("#")
        )
        for row in reader:
            func = row["Function_Code"]
            if func in result:
                name = _to_snake_case(row["Register_Name"])
                result[func][name] = int(row["Address_DEC"])
    return result


def test_all_registers_covered() -> None:
    csv_maps = load_csv_mappings()
    missing = []
    mismatched = []

    for func, regs in csv_maps.items():
        mapping = FUNCTION_MAP[func]
        for name, addr in regs.items():
            if name not in mapping:
                missing.append(f"{func}:{name}")
            elif mapping[name] != addr:
                mismatched.append(f"{func}:{name} expected {addr} got {mapping[name]}")

    assert (  # nosec B101
        not missing and not mismatched
    ), f"Missing registers: {missing}; mismatched addresses: {mismatched}"
