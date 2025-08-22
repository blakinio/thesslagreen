"""Tests for register loading utilities."""

import json
import logging
from pathlib import Path

import custom_components.thessla_green_modbus.registers.loader as loader
from custom_components.thessla_green_modbus.registers import (
    get_all_registers,
    get_registers_by_function,
    group_reads,
)


def test_json_schema_valid() -> None:
    """Validate the register file against the schema."""
    text = Path("thessla_green_registers_full.json").read_text(encoding="utf-8")
    try:
        model = loader._RegisterFileModel.model_validate_json(text)
    except AttributeError:  # pragma: no cover - pydantic v1 fallback
        model = loader._RegisterFileModel.parse_raw(text)
    assert model.schema_version
    assert model.registers


def test_register_lookup_and_properties() -> None:
    """Verify registers are loaded and accessible for all function codes."""
    coil = {r.name: r.address for r in get_registers_by_function("01")}
    discrete = {r.name: r.address for r in get_registers_by_function("02")}
    holding = {r.name: r.address for r in get_registers_by_function("03")}
    input_regs = {r.name: r.address for r in get_registers_by_function("04")}
    assert coil["bypass"] == 9
    assert discrete["expansion"] == 0
    assert holding["mode"] == 4097
    assert input_regs["outside_temperature"] == 16


def test_enum_multiplier_resolution() -> None:
    """Check enum, multiplier and resolution extraction."""
    regs = {r.name: r for r in get_registers_by_function("03")}
    assert regs["special_mode"].enum["boost"] == 1
    assert regs["required_temperature"].multiplier == 0.5
    assert regs["required_temperature"].resolution == 0.5


def test_group_reads_cover_addresses() -> None:
    """Ensure group_reads covers all register addresses without gaps."""
    regs = get_all_registers()
    mapping: dict[str, list[int]] = {}
    for reg in regs:
        mapping.setdefault(reg.function, []).append(reg.address)
    plans = group_reads()
    grouped: dict[str, list[int]] = {}
    for plan in plans:
        grouped.setdefault(plan.function, []).extend(
            range(plan.address, plan.address + plan.length)
        )
    for fn, addresses in mapping.items():
        assert sorted(addresses) == grouped.get(fn, [])


def test_registers_csv_fallback(tmp_path, caplog, monkeypatch):
    """Loader should support CSV files with a warning."""
    csv_file = tmp_path / "regs.csv"
    csv_file.write_text(
        "function,address_dec,access,name,description\n" "input,1,ro,test_reg,Test register\n"
    )
    monkeypatch.setattr(loader, "_REGISTERS_FILE", csv_file)
    loader._load_register_definitions.cache_clear()
    with caplog.at_level(logging.WARNING):
        regs = get_registers_by_function("input")
    assert any(r.name == "test_reg" for r in regs)
    assert "deprecated" in caplog.text.lower()
    loader._load_register_definitions.cache_clear()
