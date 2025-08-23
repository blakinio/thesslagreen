from __future__ import annotations

import json
import re
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

# Registers present in the vendor PDF but intentionally omitted in the JSON
# definition. Some of them are covered by aggregated entries or lack enough
# details in the documentation to be represented cleanly.
PDF_OMISSIONS: set[tuple[str, int]] = {
    ("04", 25),
    ("04", 26),
    ("04", 27),
    ("04", 28),
    ("04", 29),
    ("03", 241),
    ("03", 8145),
    ("03", 8146),
    ("03", 8147),
    ("03", 8148),
    ("03", 8149),
    ("03", 8150),
    ("03", 8151),
    ("03", 8188),
}

# Fields where the JSON intentionally diverges from the PDF (e.g. corrected
# units or scaling).  The mapping is keyed by (function, address) and contains
# a set of field names that should be skipped during comparison.
PDF_FIELD_OVERRIDES: dict[tuple[str, int], set[str]] = {
    ("04", 16): {"resolution"},
    ("04", 17): {"resolution"},
    ("04", 18): {"resolution"},
    ("04", 19): {"resolution"},
    ("04", 20): {"resolution"},
    ("04", 21): {"resolution"},
    ("04", 22): {"resolution"},
    ("03", 0): {"unit"},
    ("03", 1): {"unit"},
    ("03", 7): {"unit"},
    ("03", 128): {"unit"},
    ("03", 132): {"unit"},
    ("03", 136): {"unit"},
    ("03", 140): {"unit"},
    ("03", 144): {"unit"},
    ("03", 148): {"unit"},
    ("03", 152): {"unit"},
    ("03", 156): {"unit"},
    ("03", 160): {"unit"},
    ("03", 164): {"unit"},
    ("03", 168): {"unit"},
    ("03", 172): {"unit"},
    ("03", 176): {"unit"},
    ("03", 180): {"unit"},
    ("03", 1280): {"resolution"},
    ("03", 1281): {"resolution"},
    ("03", 1282): {"resolution"},
    ("03", 1283): {"resolution"},
    ("03", 4212): {"resolution"},
    ("03", 4213): {"resolution"},
    ("03", 4257): {"resolution"},
    ("03", 4258): {"resolution"},
    ("03", 4266): {"resolution"},
    ("03", 4321): {"resolution"},
    ("03", 4322): {"resolution"},
    ("03", 4323): {"resolution"},
    ("03", 4404): {"resolution"},
    ("03", 4453): {"resolution"},
    ("03", 4457): {"resolution"},
    ("03", 8190): {"resolution"},
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
    """Ensure register JSON mirrors the vendor PDF documentation."""

    json_file = (
        resources.files("custom_components.thessla_green_modbus.registers")
        .joinpath("thessla_green_registers_full.json")
    )
    json_data = json.loads(json_file.read_text(encoding="utf-8"))["registers"]

    pdf_path = Path(__file__).resolve().parents[1] / "MODBUS_USER_AirPack_Home_08.2021.01 1.pdf"
    pdf_data = parse_pdf_registers(pdf_path)

    json_map = {(r["function"], r["address_dec"]): r for r in json_data}
    pdf_map = {(r["function"], r["address_dec"]): r for r in pdf_data}

    missing = pdf_map.keys() - json_map.keys() - PDF_OMISSIONS
    assert not missing, f"Missing registers: {sorted(missing)}"

    for key, parsed in pdf_map.items():
        if key in PDF_OMISSIONS:
            continue
        expected = json_map[key]
        # Ensure names follow snake_case convention
        assert re.fullmatch(r"[a-z0-9_]+", expected["name"])
        # Access should always match
        assert expected["access"] == parsed["access"]
        overrides = PDF_FIELD_OVERRIDES.get(key, set())
        if parsed.get("unit") is not None and "unit" not in overrides:
            assert expected.get("unit") == parsed["unit"]
        if parsed.get("multiplier") is not None and "multiplier" not in overrides:
            assert expected.get("multiplier") == parsed["multiplier"]
        if parsed.get("resolution") is not None and "resolution" not in overrides:
            assert expected.get("resolution") == parsed["resolution"]

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
