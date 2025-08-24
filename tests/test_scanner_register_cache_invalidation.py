import json
from pathlib import Path

import custom_components.thessla_green_modbus.scanner_core as sc
from custom_components.thessla_green_modbus.registers.loader import (
    _REGISTERS_PATH,
    clear_cache,
)


def test_scanner_register_cache_invalidation(tmp_path: Path, monkeypatch) -> None:
    """Scanner should rebuild register maps when definitions change."""
    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(_REGISTERS_PATH.read_text(), encoding="utf-8")
    monkeypatch.setattr(
        "custom_components.thessla_green_modbus.registers.loader._REGISTERS_PATH",
        tmp_json,
    )

    clear_cache()
    sc.REGISTER_DEFINITIONS.clear()
    sc.INPUT_REGISTERS.clear()
    sc.HOLDING_REGISTERS.clear()
    sc.COIL_REGISTERS.clear()
    sc.DISCRETE_INPUT_REGISTERS.clear()
    sc.MULTI_REGISTER_SIZES.clear()
    sc.REGISTER_HASH = None
    sc._ensure_register_maps()

    first_hash = sc.REGISTER_HASH
    first_reg_name = next(iter(sc.REGISTER_DEFINITIONS))

    data = json.loads(tmp_json.read_text())
    data["registers"][0]["description"] = "changed description"
    tmp_json.write_text(json.dumps(data), encoding="utf-8")

    sc._ensure_register_maps()
    second_hash = sc.REGISTER_HASH

    assert first_hash != second_hash
    assert sc.REGISTER_DEFINITIONS[first_reg_name].description == "changed description"

    clear_cache()
    sc.REGISTER_DEFINITIONS.clear()
    sc.INPUT_REGISTERS.clear()
    sc.HOLDING_REGISTERS.clear()
    sc.COIL_REGISTERS.clear()
    sc.DISCRETE_INPUT_REGISTERS.clear()
    sc.MULTI_REGISTER_SIZES.clear()
    sc.REGISTER_HASH = None
