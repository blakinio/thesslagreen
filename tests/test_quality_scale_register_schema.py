# mypy: ignore-errors
"""Risk-focused coverage for register schema normalization and validation."""

from __future__ import annotations

import pytest
from custom_components.thessla_green_modbus.registers.schema import (
    RegisterDefinition,
    RegisterList,
    _normalise_access,
    _normalise_address_dec,
    _normalise_function,
    _normalise_type_and_extra,
    _validate_bits_and_mask,
    _validate_enum_mapping,
    _validate_numeric_bounds,
    _validate_scaling_metadata,
    _validate_type_length,
)
from pydantic import ValidationError


def _raw(**overrides):
    data = {
        "function": 3,
        "address_dec": 10,
        "name": "test_register",
        "access": "RW",
        "description": "Test",
        "description_en": "Test",
    }
    data.update(overrides)
    return data


def test_function_access_and_address_normalizers_reject_invalid_values() -> None:
    assert _normalise_function("holding registers") == 3
    assert _normalise_function("04") == 4
    with pytest.raises(ValueError, match="unknown function code"):
        _normalise_function("unknown")
    with pytest.raises(ValueError, match="unknown function code"):
        _normalise_function(9)

    assert _normalise_access("R/-") == "R"
    assert _normalise_access("R/W") == "RW"
    assert _normalise_access("W") == "W"
    with pytest.raises(ValueError, match="access must be"):
        _normalise_access("write")

    assert _normalise_address_dec("0010") == 10
    assert _normalise_address_dec(10) == 10
    with pytest.raises(ValueError, match="decimal"):
        _normalise_address_dec("0x10")
    with pytest.raises(ValueError, match="int or str"):
        _normalise_address_dec(True)
    with pytest.raises(ValueError, match="int or str"):
        _normalise_address_dec(1.5)


def test_type_extra_and_scaling_normalizers_cover_optional_shapes() -> None:
    data = {"type": "u16", "extra": None}
    _normalise_type_and_extra(data)
    assert data == {"type": "u16", "extra": {"type": "u16"}}

    data = {"extra": {"type": "u32", "vendor": "x"}}
    _normalise_type_and_extra(data)
    assert data["type"] == "u32"
    assert data["extra"] == {"type": "u32", "vendor": "x"}

    data = {}
    _normalise_type_and_extra(data)
    assert data == {}

    scaling = {"multiplier": None, "resolution": None}
    _validate_scaling_metadata(scaling)
    assert scaling == {"multiplier": 1, "resolution": 1}

    explicit = {"multiplier": 0.1, "resolution": 0.5}
    _validate_scaling_metadata(explicit)
    assert explicit == {"multiplier": 0.1, "resolution": 0.5}


def test_type_length_validation_covers_defaults_and_errors() -> None:
    assert _validate_type_length(None, None) is None
    assert _validate_type_length("u16", None) == 1
    assert _validate_type_length("u16", 1) is None
    assert _validate_type_length("string", 4) is None

    for alias in ("uint", "int", "float"):
        with pytest.raises(ValueError, match="aliases are not allowed"):
            _validate_type_length(alias, 1)
    with pytest.raises(ValueError, match="string type requires"):
        _validate_type_length("string", None)
    with pytest.raises(ValueError, match="string type requires"):
        _validate_type_length("string", 0)
    with pytest.raises(ValueError, match="length does not match"):
        _validate_type_length("u32", 1)


def test_enum_and_numeric_bounds_validation_covers_all_failures() -> None:
    _validate_enum_mapping(None)
    _validate_enum_mapping({"0": "off", "1": "on"})
    with pytest.raises(ValueError, match="mapping"):
        _validate_enum_mapping(["bad"])
    with pytest.raises(ValueError, match="keys must be numeric"):
        _validate_enum_mapping({"off": "off"})
    with pytest.raises(ValueError, match="values must be strings"):
        _validate_enum_mapping({"0": 0})

    _validate_numeric_bounds(None, None, None)
    _validate_numeric_bounds(0, 10, 5)
    with pytest.raises(ValueError, match="min greater"):
        _validate_numeric_bounds(10, 0, None)
    with pytest.raises(ValueError, match="default below"):
        _validate_numeric_bounds(0, 10, -1)
    with pytest.raises(ValueError, match="default above"):
        _validate_numeric_bounds(0, 10, 11)


def test_bits_and_mask_validation_covers_structural_failures() -> None:
    _validate_bits_and_mask(None, None)
    _validate_bits_and_mask([{"index": 0, "name": "bit_zero"}], {"bitmask": "1"})
    _validate_bits_and_mask([{"index": 1, "name": "bit_one"}], {"bitmask": 3})

    cases = [
        ([{"index": i, "name": f"bit_{i}"} for i in range(17)], None, "exceed 16"),
        (["bad"], None, "must be objects"),
        ([{"index": 0}], None, "index and name"),
        ([{"index": True, "name": "bad"}], None, "must be an integer"),
        ([{"index": 16, "name": "bad"}], None, "out of range"),
        (
            [{"index": 1, "name": "one"}, {"index": 1, "name": "again"}],
            None,
            "must be unique",
        ),
        ([{"index": 1, "name": "Bad Name"}], None, "snake_case"),
        ([], {"bitmask": "0x01"}, "decimal digits"),
        ([{"index": 2, "name": "too_wide"}], {"bitmask": 1}, "bitmask width"),
    ]
    for bits, extra, message in cases:
        with pytest.raises(ValueError, match=message):
            _validate_bits_and_mask(bits, extra)


def test_register_definition_normalizes_supported_metadata() -> None:
    register = RegisterDefinition.model_validate(
        _raw(
            function="holding_registers",
            address_dec="0010",
            access="R/W",
            count=2,
            type="u32",
            multiplier=None,
            resolution=None,
            extra={"vendor": "value"},
        )
    )
    assert register.function == 3
    assert register.address_dec == 10
    assert register.access == "RW"
    assert register.length == 2
    assert register.multiplier == 1
    assert register.resolution == 1
    assert register.extra == {"vendor": "value", "type": "u32"}


def test_register_definition_rejects_read_write_for_read_only_and_bad_name() -> None:
    with pytest.raises(ValidationError, match="read-only functions"):
        RegisterDefinition.model_validate(_raw(function=1, access="RW"))
    with pytest.raises(ValidationError, match="snake_case"):
        RegisterDefinition.model_validate(_raw(name="Bad Name"))


def test_register_definition_consistency_helpers_surface_through_model() -> None:
    with pytest.raises(ValidationError, match="min greater"):
        RegisterDefinition.model_validate(_raw(min=10, max=1))
    with pytest.raises(ValidationError, match="keys must be numeric"):
        RegisterDefinition.model_validate(_raw(enum={"off": "off"}))
    with pytest.raises(ValidationError, match="bitmask width"):
        RegisterDefinition.model_validate(
            _raw(bits=[{"index": 2, "name": "bit_two"}], extra={"bitmask": 1})
        )


def test_register_list_rejects_duplicate_pair_and_duplicate_name() -> None:
    first = _raw(name="first", address_dec=1)
    with pytest.raises(ValidationError, match="duplicate register pair"):
        RegisterList.model_validate([first, _raw(name="second", address_dec=1)])

    with pytest.raises(ValidationError, match="duplicate register name"):
        RegisterList.model_validate([first, _raw(name="first", address_dec=2)])

    valid = RegisterList.model_validate([first, _raw(name="second", address_dec=2)])
    assert [register.name for register in valid.registers] == ["first", "second"]
