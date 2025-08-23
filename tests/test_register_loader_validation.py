from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from tools.validate_register_pdf import parse_pdf_registers

import pydantic
import pytest
from custom_components.thessla_green_modbus.registers.loader import RegisterDefinition


EXPECTED = {
    "01": {"min": 5, "max": 15, "count": 8},
    "02": {"min": 0, "max": 21, "count": 16},
    "03": {"min": 0, "max": 8444, "count": 270},
    "04": {"min": 0, "max": 298, "count": 24},
}


def test_register_file_valid() -> None:
    """Validate register JSON structure and completeness."""

    json_file = (
        resources.files("custom_components.thessla_green_modbus.registers")
        .joinpath("thessla_green_registers_full.json")
    )
    data = json.loads(json_file.read_text(encoding="utf-8"))
    registers = data.get("registers", data)

    parsed = [RegisterDefinition.model_validate(item) for item in registers]

    by_fn: dict[str, list[int]] = {}
    for reg in parsed:
        by_fn.setdefault(reg.function, []).append(reg.address_dec)

    for fn, spec in EXPECTED.items():
        addrs = by_fn.get(fn, [])
        assert len(addrs) == spec["count"]
        assert min(addrs) == spec["min"]
        assert max(addrs) == spec["max"]


def test_registers_match_pdf() -> None:
    """Ensure registers JSON matches vendor PDF documentation."""

    json_file = (
        resources.files("custom_components.thessla_green_modbus.registers")
        .joinpath("thessla_green_registers_full.json")
    )
    json_data = json.loads(json_file.read_text(encoding="utf-8"))["registers"]

    pdf_path = Path(__file__).resolve().parents[1] / "MODBUS_USER_AirPack_Home_08.2021.01 1.pdf"
    pdf_data = parse_pdf_registers(pdf_path)

    json_map = {(r["function"], r["address_dec"]): r for r in json_data}
    pdf_map = {
        (r["function"], r["address_dec"]): r
        for r in pdf_data
        if (r["function"], r["address_dec"]) in json_map
    }

    # Known omission in PDF: heating_temperature (function 04 addr 23)
    json_map.pop(("04", 23), None)

    assert json_map.keys() == pdf_map.keys()
    for key in json_map:
        expected = json_map[key]
        parsed = pdf_map[key]
        assert expected["access"] == parsed["access"]

def test_schema_rejects_unknown_function() -> None:
    """Unknown function codes should be rejected."""

    bad = {
        "name": "x",
        "function": "05",
        "address_dec": 0,
        "address_hex": "0x0",
        "access": "R/W",
    }
    with pytest.raises(pydantic.ValidationError):
        RegisterDefinition.model_validate(bad)


def test_schema_rejects_unknown_access() -> None:
    """Unexpected access types should raise an error."""

    bad = {
        "name": "x",
        "function": "03",
        "address_dec": 0,
        "address_hex": "0x0",
        "access": "RW",
    }
    with pytest.raises(pydantic.ValidationError):
        RegisterDefinition.model_validate(bad)
