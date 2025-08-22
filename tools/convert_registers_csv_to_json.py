"""Convert legacy CSV register definitions to JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "tools" / "modbus_registers.csv"
JSON_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)


def convert(csv_path: Path = CSV_PATH, json_path: Path = JSON_PATH) -> None:
    """Convert *csv_path* to *json_path* using a simple schema."""
    rows: list[dict[str, object]] = []
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row.get("Register_Name")
            if not name:
                continue
            try:
                addr = int(row.get("Address_DEC", 0))
            except (TypeError, ValueError):
                continue
            entry: dict[str, object] = {
                "function": row.get("Function_Code"),
                "address_dec": addr,
                "name": name,
                "access": row.get("Access"),
                "description": row.get("Description"),
                "unit": row.get("Unit"),
                "multiplier": float(row["Multiplier"]) if row.get("Multiplier") else None,
                "resolution": float(row["Resolution"]) if row.get("Resolution") else None,
                "min": float(row["Min"]) if row.get("Min") else None,
                "max": float(row["Max"]) if row.get("Max") else None,
                "default": float(row["Default"]) if row.get("Default") else None,
                "information": row.get("Information"),
            }
            rows.append(entry)
    json_path.write_text(json.dumps({"registers": rows}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    convert()
