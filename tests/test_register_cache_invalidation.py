import json
import os
from pathlib import Path

from custom_components.thessla_green_modbus.registers.loader import (
    _REGISTERS_PATH,
    clear_cache,
    load_registers,
)


def test_cache_invalidation_on_content_change(tmp_path: Path, monkeypatch) -> None:
    """Changing file contents should invalidate cache."""

    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(_REGISTERS_PATH.read_text(), encoding="utf-8")
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._REGISTERS_PATH",
        tmp_json,
    )

    clear_cache()
    first = load_registers()[0]
    assert first.description

    data = json.loads(tmp_json.read_text())
    data["registers"][0]["description"] = "changed description"
    tmp_json.write_text(json.dumps(data), encoding="utf-8")

    updated = load_registers()[0]
    assert updated.description == "changed description"

    clear_cache()


def test_cache_invalidation_on_mtime_change(tmp_path: Path, monkeypatch) -> None:
    """Touching file without content change should reload registers."""

    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(_REGISTERS_PATH.read_text(), encoding="utf-8")
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._REGISTERS_PATH",
        tmp_json,
    )

    clear_cache()
    first_id = id(load_registers())

    os.utime(tmp_json, None)

    second_id = id(load_registers())
    assert first_id != second_id

    clear_cache()
