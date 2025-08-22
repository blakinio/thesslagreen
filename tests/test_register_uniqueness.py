"""Ensure register definitions have unique names and addresses."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import json


REGISTERS_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "thessla_green_modbus"
    / "registers"
    / "thessla_green_registers_full.json"
)


def test_register_uniqueness() -> None:
    """All register names and (function, address) pairs should be unique."""
    data = json.loads(REGISTERS_PATH.read_text())
    registers = data.get("registers", data)

    name_counts = Counter(reg["name"] for reg in registers)
    duplicate_names = {name: count for name, count in name_counts.items() if count > 1}
    assert not duplicate_names, f"Duplicate register names found: {duplicate_names}"

    def address(reg: dict) -> int:
        if reg.get("address_dec") is not None:
            return int(reg["address_dec"])
        return int(str(reg["address_hex"]), 16)

    pair_counts = Counter((reg["function"], address(reg)) for reg in registers)
    duplicate_pairs = {pair: count for pair, count in pair_counts.items() if count > 1}
    assert not duplicate_pairs, (
        "Duplicate (function, address) pairs found: " f"{duplicate_pairs}"
    )
