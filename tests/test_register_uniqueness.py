"""Ensure register definitions have unique names and addresses."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REGISTERS_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)


def test_register_uniqueness() -> None:
    """All register names are unique, snake_case and sorted by address."""
    data = json.loads(REGISTERS_PATH.read_text())
    registers = data.get("registers", data)

    # Names must be unique
    name_counts = Counter(reg["name"] for reg in registers)
    duplicate_names = {name: count for name, count in name_counts.items() if count > 1}
    assert not duplicate_names, f"Duplicate register names found: {duplicate_names}"

    # Names must be snake_case
    snake_case = re.compile(r"^[a-z0-9_]+$")
    bad_names = [reg["name"] for reg in registers if not snake_case.fullmatch(reg["name"])]
    assert not bad_names, f"Non-snake_case names found: {bad_names}"

    def address(reg: dict) -> int:
        if reg.get("address_dec") is not None:
            return int(reg["address_dec"])
        return int(str(reg["address_hex"]), 16)

    # (function, address_dec) pairs must be unique
    pair_counts = Counter((reg["function"], address(reg)) for reg in registers)
    duplicate_pairs = {pair: count for pair, count in pair_counts.items() if count > 1}
    assert not duplicate_pairs, (
        "Duplicate (function, address_dec) pairs found: " f"{duplicate_pairs}"
    )

    # The list must be deterministically sorted by address then name
    sorted_regs = sorted(registers, key=lambda r: (address(r), r["name"]))
    assert registers == sorted_regs, "Registers are not sorted by address_dec"
