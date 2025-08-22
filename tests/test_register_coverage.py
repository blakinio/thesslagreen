"""Validate coverage of register definitions against CSV specification."""

import json
from pathlib import Path

from custom_components.thessla_green_modbus.const import COIL_REGISTERS, DISCRETE_INPUT_REGISTERS
from custom_components.thessla_green_modbus.registers import HOLDING_REGISTERS, INPUT_REGISTERS
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
    / "modbus_registers.json"
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


def load_json_mappings() -> dict[str, dict[str, int]]:
    rows: dict[str, list[tuple[str, int]]] = {code: [] for code in FUNCTION_MAP}
    with CSV_PATH.open(encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)
    for row in data.get("registers", []):
        func = row.get("function")
        if func in rows:
            name = _to_snake_case(row.get("name", ""))
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
            rows[func].append((name, int(row.get("address_dec", 0))))
    return {code: _build_map(items) for code, items in rows.items()}


def test_all_registers_covered() -> None:
    json_maps = load_json_mappings()
    missing = []
    mismatched = []

    for func, regs in json_maps.items():
        mapping = FUNCTION_MAP[func]
        for name, addr in regs.items():
            if name not in mapping:
                missing.append(f"{func}:{name}")
            elif mapping[name] != addr:
                mismatched.append(f"{func}:{name} expected {addr} got {mapping[name]}")

    assert (  # nosec B101
        not missing and not mismatched
    ), f"Missing registers: {missing}; mismatched addresses: {mismatched}"
