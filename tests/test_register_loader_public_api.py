"""Split register loader tests."""

import json
from pathlib import Path

from custom_components.thessla_green_modbus.registers.loader import (
    clear_cache,
    get_all_registers,
    get_registers_path,
)


def _add_desc(reg: dict) -> dict:
    return {**reg, "description": reg.get("description", "desc"), "description_en": reg.get("description_en", "desc")}


def _write(path: Path, regs: list[dict]) -> None:
    path.write_text(json.dumps({"registers": [_add_desc(r) for r in regs]}))

def test_register_file_sorted() -> None:
    """Ensure register JSON is sorted and loader preserves ordering."""

    data = json.loads(get_registers_path().read_text(encoding="utf-8"))
    regs = data["registers"]
    keys = [(str(r["function"]), int(r["address_dec"])) for r in regs]
    assert keys == sorted(keys)

def test_get_all_registers_sorted(tmp_path) -> None:
    """get_all_registers should order registers by function then address."""

    regs = [
        {
            "function": "03",
            "address_dec": 2,
            "name": "reg_c",
            "access": "R",
        },
        {
            "function": "01",
            "address_dec": 1,
            "name": "reg_a",
            "access": "R",
        },
        {
            "function": "03",
            "address_dec": 1,
            "name": "reg_b",
            "access": "R",
        },
    ]

    path = tmp_path / "regs.json"
    _write(path, regs)

    clear_cache()
    ordered = get_all_registers(path)
    keys = [(r.function, r.address) for r in ordered]
    assert keys == sorted(keys)

def test_loader_all_has_no_private_cache_names() -> None:
    """loader.__all__ should only expose public API names."""
    from custom_components.thessla_green_modbus.registers import loader

    assert "_cached_file_info" not in loader.__all__
    assert "_register_cache" not in loader.__all__
