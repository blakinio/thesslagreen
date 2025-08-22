"""Convert legacy CSV register definitions to JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import re
from collections import OrderedDict

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "tools" / "modbus_registers.csv"
JSON_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)

_SNAKE_RE = re.compile(r"[^0-9a-zA-Z]+")
_ENUM_RE = re.compile(r"\s*([0-9]+)\s*-\s*([^;]+)")


def _snake_case(name: str) -> str:
    name = _SNAKE_RE.sub("_", name)
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.strip("_").lower()


def convert(csv_path: Path = CSV_PATH, json_path: Path = JSON_PATH) -> None:
    """Convert legacy CSV register definitions to a canonical JSON file."""

    rows: list[dict[str, object]] = []
    seen_names: set[str] = set()
    seen_pairs: set[tuple[str, int]] = set()

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

            func = str(row.get("Function_Code"))
            snake = _snake_case(name)

            # Derive unique suffix from description when duplicate names occur
            desc = row.get("Description") or ""
            suffix_match = re.search(r"\[(?P<suf>[^\]]+)\]", desc)
            if suffix_match:
                suffix = _SNAKE_RE.sub("_", suffix_match.group("suf")).strip("_").lower()
            else:
                suffix = None

            # Determine access - keep only the left part before '/'
            access = row.get("Access", "").strip()

            unit = row.get("Unit") or None
            enum: dict[str, str] | None = None
            if unit:
                matches = list(_ENUM_RE.finditer(unit))
                if matches:
                    enum = {m.group(1): m.group(2).strip() for m in matches}
                    unit = None

            def _to_float(value: str | None) -> float | None:
                if not value:
                    return None
                try:
                    return float(value)
                except ValueError:
                    return None

            multiplier = _to_float(row.get("Multiplier"))
            resolution = _to_float(row.get("Resolution"))
            if resolution is None and multiplier is not None:
                resolution = multiplier

            # Ensure unique name
            if snake in seen_names:
                if suffix:
                    snake = f"{snake}_{suffix}"
                else:
                    snake = f"{snake}_{addr}"

            entry = OrderedDict(
                [
                    ("function", func),
                    ("address_dec", addr),
                    ("address_hex", row.get("Address_HEX")),
                    ("name", snake),
                    ("access", access),
                    ("unit", unit),
                    ("enum", enum),
                    ("multiplier", multiplier),
                    ("resolution", resolution),
                    ("description", row.get("Description")),
                ]
            )

            # Enforce uniqueness of names and address/function pairs
            pair = (func, addr)
            if snake in seen_names or pair in seen_pairs:
                raise ValueError(f"Duplicate register detected: {func} {addr} {snake}")
            seen_names.add(snake)
            seen_pairs.add(pair)

            rows.append(entry)

    rows.sort(key=lambda r: (int(r["address_dec"]), str(r["name"])))
    json_path.write_text(
        json.dumps({"registers": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    convert()
