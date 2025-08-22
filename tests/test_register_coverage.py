"""Validate coverage of register definitions against CSV specification."""

import csv
from pathlib import Path

from custom_components.thessla_green_modbus.const import (
    COIL_REGISTERS,
    DISCRETE_INPUT_REGISTERS,
    HOLDING_REGISTERS,
    INPUT_REGISTERS,
)
from custom_components.thessla_green_modbus.utils import _to_snake_case

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


def _build_map(rows: list[tuple[str, int]]) -> dict[str, int]:
    """Return register mapping with numbered duplicates."""
    rows.sort(key=lambda item: item[1])
    counts: dict[str, int] = {}
    for name, _ in rows:
        counts[name] = counts.get(name, 0) + 1
    seen: dict[str, int] = {}
    mapping: dict[str, int] = {}
    for name, addr in rows:
        if counts[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            name = f"{name}_{seen[name]}"
        mapping[name] = addr
    return mapping


def load_csv_mappings() -> dict[str, dict[str, int]]:
    rows: dict[str, list[tuple[str, int]]] = {code: [] for code in FUNCTION_MAP}
    with CSV_PATH.open(newline="") as csvfile:
        reader = csv.DictReader(
            row for row in csvfile if row.strip() and not row.lstrip().startswith("#")
        )
        for row in reader:
            func = row["Function_Code"]
            if func in rows:
                name = _to_snake_case(row["Register_Name"])
                rows[func].append((name, int(row["Address_DEC"])))
    return {code: _build_map(items) for code, items in rows.items()}


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
