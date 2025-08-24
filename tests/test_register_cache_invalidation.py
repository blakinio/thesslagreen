import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers.loader import (
    clear_cache,
    _load_registers,
    _REGISTERS_PATH,
)


def test_register_cache_invalidation(tmp_path: Path, monkeypatch) -> None:
    """Modifying the register JSON should trigger cache rebuilds."""

    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(_REGISTERS_PATH.read_text(), encoding="utf-8")
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._REGISTERS_PATH",
        tmp_json,
    )

    clear_cache()
    first = _load_registers()[0]
    assert first.description
    assert first.description_en

    data = json.loads(tmp_json.read_text())
    data["registers"][0]["description"] = "changed description"
    data["registers"][0]["description_en"] = "changed description en"
    tmp_json.write_text(json.dumps(data), encoding="utf-8")

    clear_cache()
    updated = _load_registers()[0]
    assert updated.description == "changed description"
    assert updated.description_en == "changed description en"

    clear_cache()
