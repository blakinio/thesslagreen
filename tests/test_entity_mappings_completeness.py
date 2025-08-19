import csv
from pathlib import Path

from custom_components.thessla_green_modbus.entity_mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.utils import _to_snake_case

CSV_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "thessla_green_modbus"
    / "data"
    / "modbus_registers.csv"
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


def _load_csv_register_names() -> set[str]:
    names: list[str] = []
    with CSV_PATH.open(encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(
            row for row in csvfile if row.strip() and not row.lstrip().startswith("#")
        )
        for row in reader:
            names.append(_to_snake_case(row["Register_Name"]))
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
    csv_names = _load_csv_register_names()
    mapping_names = _entity_mapping_keys()
    missing = mapping_names - csv_names - WHITELIST
    assert not missing, f"Unknown registers in ENTITY_MAPPINGS: {sorted(missing)}"
