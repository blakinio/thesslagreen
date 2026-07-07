#!/usr/bin/env python3
"""Normalize register names to snake_case and sort deterministically."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = (
    ROOT
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)

SNAKE_RE = re.compile(r"[^0-9a-zA-Z]+")
CAMEL_RE_1 = re.compile(r"(.)([A-Z][a-z]+)")
CAMEL_RE_2 = re.compile(r"([a-z0-9])([A-Z])")


def _snake_case(name: str) -> str:
    """Return *name* converted to snake_case."""
    name = SNAKE_RE.sub("_", name)
    name = CAMEL_RE_1.sub(r"\1_\2", name)
    name = CAMEL_RE_2.sub(r"\1_\2", name)
    return name.strip("_").lower()


def migrate(path: Path = JSON_PATH) -> None:
    """Update *path* in place with normalised names and sorting."""
    data = json.loads(path.read_text(encoding="utf-8"))
    registers = data.get("registers", [])
    for reg in registers:
        reg["name"] = _snake_case(str(reg["name"]))

    # Special-case known duplicates that should have descriptive names
    special = {
        ("hood", "01"): "hood_output",
        ("hood", "02"): "hood_switch",
    }
    for reg in registers:
        key = (reg["name"], str(reg["function"]))
        if key in special:
            reg["name"] = special[key]

    # Append numeric suffixes for remaining duplicates
    counts = {}
    for reg in registers:
        name = reg["name"]
        counts[name] = counts.get(name, 0) + 1
    seen = {}
    for reg in registers:
        name = reg["name"]
        if counts[name] > 1:
            idx = seen.get(name, 0) + 1
            seen[name] = idx
            reg["name"] = f"{name}_{idx}"

    # Verify uniqueness and sort deterministically
    names = [reg["name"] for reg in registers]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate register names after normalisation")
    registers.sort(key=lambda r: (int(r["address_dec"]), r["name"]))
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    migrate()
