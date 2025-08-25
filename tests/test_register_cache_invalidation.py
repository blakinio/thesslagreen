import json
import os
from pathlib import Path

import custom_components.thessla_green_modbus.registers.loader as loader


def test_cache_invalidation_on_content_change(tmp_path: Path) -> None:
    """Changing file contents should invalidate the cache."""

    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(loader._REGISTERS_PATH.read_text(), encoding="utf-8")

    loader.clear_cache()
    first_hash = loader.registers_sha256(tmp_json)
    first = loader.load_registers(tmp_json)[0]
    assert first.description
    assert first_hash

    data = json.loads(tmp_json.read_text())
    data["registers"][0]["description"] = "changed description"
    tmp_json.write_text(json.dumps(data), encoding="utf-8")

    second_hash = loader.registers_sha256(tmp_json)
    updated = loader.load_registers(tmp_json)[0]
    assert updated.description == "changed description"
    assert first_hash != second_hash

    loader.clear_cache()


def test_cache_invalidation_on_mtime_change(tmp_path: Path) -> None:
    """Touching file without content change should reload registers."""

    tmp_json = tmp_path / "registers.json"
    tmp_json.write_text(loader._REGISTERS_PATH.read_text(), encoding="utf-8")

    loader.clear_cache()
    first_id = id(loader.load_registers(tmp_json))

    os.utime(tmp_json, None)

    second_id = id(loader.load_registers(tmp_json))
    assert first_id != second_id

    loader.clear_cache()
