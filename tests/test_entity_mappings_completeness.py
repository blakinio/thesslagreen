import json
from pathlib import Path

from custom_components.thessla_green_modbus.entity_mappings import (
    ENTITY_MAPPINGS,
    BINARY_SENSOR_ENTITY_MAPPINGS,
    NUMBER_ENTITY_MAPPINGS,
)
from custom_components.thessla_green_modbus.utils import _to_snake_case

CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "thessla_green_modbus"
    / "data"
    / "modbus_registers.json"
)

WHITELIST: set[str] = {
    "away",
    "bathroom",
    "boost",
    "calculated_efficiency",
    "eco",
    "estimated_power",
    "hood",
    "intensive_exhaust",
    "intensive_supply",
    "kitchen",
    "party",
    "required_temp",
    "sleep",
    "summer",
    "total_energy",
    "winter",
}


def _load_json_register_names() -> set[str]:
    names: list[str] = []
    with CSV_PATH.open(encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)
    for row in data.get("registers", []):
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
        names.append(name)
    counts: dict[str, int] = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    seen: dict[str, int] = {}
    result: set[str] = set()
    for name in names:
        if counts[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            name = f"{name}_{seen[name]}"
        result.add(name)
    return result


def _entity_mapping_keys() -> set[str]:
    keys: set[str] = set()
    for mapping in ENTITY_MAPPINGS.values():
        keys.update(mapping.keys())
    return keys


def test_entity_mappings_cover_all_registers() -> None:
    csv_names = _load_json_register_names()
    mapping_names = _entity_mapping_keys()
    missing = mapping_names - csv_names - WHITELIST
    assert not missing, f"Unknown registers in ENTITY_MAPPINGS: {sorted(missing)}"
    unmapped = csv_names - mapping_names
    assert not unmapped, f"Registers missing entity mapping: {sorted(unmapped)}"


def test_s_13_is_binary_only() -> None:
    assert "s_13" not in NUMBER_ENTITY_MAPPINGS
    assert "s_13" in BINARY_SENSOR_ENTITY_MAPPINGS
