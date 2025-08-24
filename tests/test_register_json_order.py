"""Verify the canonical register JSON file is sorted."""

from __future__ import annotations

import json
from pathlib import Path


def test_register_json_order() -> None:
    """Registers should be ordered by function then decimal address."""

    json_path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "thessla_green_modbus"
        / "registers"
        / "thessla_green_registers_full.json"
    )
    data = json.loads(json_path.read_text(encoding="utf-8"))
    registers = data["registers"]
    sorted_regs = sorted(
        registers,
        key=lambda r: (int(str(r["function"])), int(r["address_dec"])),
    )
    assert registers == sorted_regs
