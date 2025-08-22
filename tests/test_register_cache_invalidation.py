"""Tests for automatic register cache invalidation when the JSON file changes."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers import loader as mr


def test_register_cache_invalidation(tmp_path: Path, monkeypatch) -> None:
    """Modifying the register JSON should trigger cache rebuilds."""

    # Minimal register file used for testing
    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(
        json.dumps(
            {
                "registers": [
                    {
                        "function": "01",
                        "address_hex": "0x0000",
                        "address_dec": 0,
                        "name": "test_reg",
                        "description": "original",
                        "access": "R",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mr, "_REGISTERS_PATH", tmp_json)

    mr._cache_clear()

    first = mr.get_all_registers()[0]
    assert first.description == "original"

    data = json.loads(tmp_json.read_text())
    data["registers"][0]["description"] = "changed"
    tmp_json.write_text(json.dumps(data), encoding="utf-8")

    updated = mr.get_all_registers()[0]
    assert updated.description == "changed"
