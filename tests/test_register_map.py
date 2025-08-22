import csv
import json
import pathlib

from custom_components.thessla_green_modbus.utils import _to_snake_case

CSV_PATH = pathlib.Path("custom_components/thessla_green_modbus/data/modbus_registers.json")


def _build_map(rows: list[tuple[str, int]]) -> dict[str, int]:
    """Build mapping from register names to addresses with numbering for duplicates."""
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


def load_json_registers() -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    coil_rows: list[tuple[str, int]] = []
    discrete_rows: list[tuple[str, int]] = []
    input_rows: list[tuple[str, int]] = []
    holding_rows: list[tuple[str, int]] = []

    with CSV_PATH.open(encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)
    for row in data.get("registers", []):
        func = row.get("function")
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
        addr = int(row.get("address_dec", 0))
        if func == "01":
            coil_rows.append((name, addr))
        elif func == "02":
            discrete_rows.append((name, addr))
        elif func == "04":
            input_rows.append((name, addr))
        elif func == "03":
            holding_rows.append((name, addr))
    return (
        _build_map(coil_rows),
        _build_map(discrete_rows),
        _build_map(input_rows),
        _build_map(holding_rows),
    )


def test_register_map_matches_json() -> None:
    csv_coil, csv_discrete, csv_input, csv_holding = load_json_registers()

    from custom_components.thessla_green_modbus import registers as mod

    assert csv_coil == mod.COIL_REGISTERS  # nosec B101
    assert csv_discrete == mod.DISCRETE_INPUT_REGISTERS  # nosec B101
    assert csv_input == mod.INPUT_REGISTERS  # nosec B101
    assert csv_holding == mod.HOLDING_REGISTERS  # nosec B101
