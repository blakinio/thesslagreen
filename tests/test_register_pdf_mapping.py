"""Validate key register mappings against the manufacturer PDF."""

from __future__ import annotations

import json
from importlib import resources

from custom_components.thessla_green_modbus.utils import BCD_TIME_PREFIXES


def _load_register_json() -> dict[str, dict[str, object]]:
    path = resources.files("custom_components.thessla_green_modbus.registers").joinpath(
        "thessla_green_registers_full.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["name"]: entry for entry in data["registers"]}


def _normalise_function(value: object) -> int:
    """Return the canonical Modbus function code."""

    return int(str(value))


def test_pdf_register_addresses_and_functions() -> None:
    """Ensure key registers match PDF addresses and Modbus functions."""

    registers = _load_register_json()
    expected = [
        ("version_major", 4, 0),
        ("version_minor", 4, 1),
        ("version_patch", 4, 4),
        ("outside_temperature", 4, 16),
        ("supply_temperature", 4, 17),
        ("exhaust_temperature", 4, 18),
        ("fpx_temperature", 4, 19),
        ("duct_supply_temperature", 4, 20),
        ("gwc_temperature", 4, 21),
        ("ambient_temperature", 4, 22),
        ("supply_percentage", 4, 272),
        ("exhaust_percentage", 4, 273),
        ("supply_flow_rate", 4, 274),
        ("exhaust_flow_rate", 4, 275),
        ("mode", 3, 4208),
        ("season_mode", 3, 4209),
        ("air_flow_rate_manual", 3, 4210),
        ("supply_air_temperature_manual", 3, 4212),
        ("special_mode", 3, 4224),
    ]

    for name, fn, address in expected:
        entry = registers[name]
        assert _normalise_function(entry["function"]) == fn
        assert entry["address_dec"] == address


def test_pdf_register_decoding_types() -> None:
    """Ensure register decoding types align with PDF expectations."""

    registers = _load_register_json()
    temperature_names = [
        "outside_temperature",
        "supply_temperature",
        "exhaust_temperature",
        "fpx_temperature",
        "duct_supply_temperature",
        "gwc_temperature",
        "ambient_temperature",
    ]
    for name in temperature_names:
        entry = registers[name]
        assert "temperature" in entry["name"]
        assert entry["unit"] == "°C"

    assert registers["schedule_summer_mon_1"]["name"].startswith(BCD_TIME_PREFIXES)
    assert registers["manual_airing_time_to_start"]["name"].startswith(BCD_TIME_PREFIXES)
    assert registers["setting_summer_mon_1"]["name"].startswith("setting_")


def test_pdf_register_units() -> None:
    """Ensure units match PDF specifications for key registers."""

    registers = _load_register_json()

    assert registers["supply_flow_rate"]["unit"] == "m3/h"
    assert registers["exhaust_flow_rate"]["unit"] == "m3/h"

    assert registers["supply_percentage"]["unit"] == "%"
    assert registers["exhaust_percentage"]["unit"] == "%"
    assert registers["air_flow_rate_manual"]["unit"] == "%"

    assert registers["supply_air_temperature_manual"]["unit"] == "°C"
    assert registers["supply_air_temperature_manual"]["multiplier"] == 0.5


def test_pdf_register_access() -> None:
    """Ensure read/write access flags match PDF specifications."""

    registers = _load_register_json()

    read_only = [
        "outside_temperature",
        "supply_temperature",
        "exhaust_temperature",
        "supply_percentage",
        "exhaust_percentage",
        "supply_flow_rate",
        "exhaust_flow_rate",
        "version_major",
        "version_minor",
        "version_patch",
    ]
    for name in read_only:
        assert registers[name]["access"] == "R", f"{name} should be read-only"

    read_write = [
        "mode",
        "season_mode",
        "air_flow_rate_manual",
        "supply_air_temperature_manual",
        "special_mode",
        "schedule_summer_mon_1",
        "setting_summer_mon_1",
    ]
    for name in read_write:
        assert registers[name]["access"] == "RW", f"{name} should be read-write"


def test_pdf_register_enum_values() -> None:
    """Ensure enum registers have correct value sets from PDF."""

    registers = _load_register_json()

    mode_reg = registers["mode"]
    assert mode_reg.get("enum") is not None
    assert "0" in mode_reg["enum"]
    assert "1" in mode_reg["enum"]
    assert "2" in mode_reg["enum"]

    season_reg = registers["season_mode"]
    assert season_reg.get("enum") is not None
    assert set(season_reg["enum"].keys()) == {"0", "1"}

    special_reg = registers["special_mode"]
    assert special_reg.get("enum") is not None
    assert len(special_reg["enum"]) >= 10
