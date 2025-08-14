"""Entity mapping definitions for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

CSV_PATH = Path(__file__).parent / "data" / "modbus_registers.csv"


def _to_snake_case(name: str) -> str:
    """Convert a register name from the CSV to ``snake_case``."""
    replacements = {"flowrate": "flow_rate"}
    for old, new in replacements.items():
        name = name.replace(old, new)
    name = re.sub(r"[\s\-/]", "_", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"(?<=\D)(\d)", r"_\1", name)
    name = re.sub(r"__+", "_", name)
    name = name.lower()
    token_map = {"temp": "temperature"}
    tokens = [token_map.get(token, token) for token in name.split("_")]
    return "_".join(tokens)


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


NUMBER_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = _load_number_mappings()
SENSOR_ENTITY_MAPPINGS: dict[str, dict[str, Any]] = {}
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

