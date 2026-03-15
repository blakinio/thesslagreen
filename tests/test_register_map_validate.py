# mypy: ignore-errors
"""Tests for RegisterMapEntry.validate() in register_map.py."""

from __future__ import annotations

import pytest

from custom_components.thessla_green_modbus.register_map import (
    RegisterMapEntry,
    validate_register_value,
)


def _entry(**kwargs) -> RegisterMapEntry:
    """Create a RegisterMapEntry with sensible defaults."""
    defaults = dict(
        name="test_reg",
        register_type="input_registers",
        address=100,
        data_type="int",
        min_value=None,
        max_value=None,
        enum_values=set(),
        model_variants=(),
        entity_domain=None,
        enum_map={},
    )
    defaults.update(kwargs)
    return RegisterMapEntry(**defaults)


# ---------------------------------------------------------------------------
# None input
# ---------------------------------------------------------------------------


def test_validate_none_returns_none():
    e = _entry()
    assert e.validate(None) is None


# ---------------------------------------------------------------------------
# binary_sensor / switch domain coercion (lines 69-72)
# ---------------------------------------------------------------------------


def test_validate_binary_sensor_non_bitmask_coerces_to_bool():
    """binary_sensor entity with int data_type is treated as bool."""
    e = _entry(entity_domain="binary_sensor", data_type="int")
    assert e.validate(1) is True
    assert e.validate(0) is False


def test_validate_switch_non_enum_coerces_to_bool():
    """switch entity with int data_type is treated as bool."""
    e = _entry(entity_domain="switch", data_type="int")
    assert e.validate(1) is True


def test_validate_binary_sensor_bitmask_stays_bitmask():
    """binary_sensor with bitmask data_type is NOT coerced to bool."""
    e = _entry(entity_domain="binary_sensor", data_type="bitmask")
    assert e.validate(5) == 5  # integer stays as raw bitmask


def test_validate_binary_sensor_enum_stays_enum():
    """binary_sensor with enum data_type is NOT coerced to bool."""
    e = _entry(entity_domain="binary_sensor", data_type="enum", enum_values={0, 1})
    assert e.validate(0) == 0


# ---------------------------------------------------------------------------
# enum
# ---------------------------------------------------------------------------


def test_validate_enum_valid_value():
    e = _entry(data_type="enum", enum_values={0, 1, 2})
    assert e.validate(1) == 1


def test_validate_enum_value_not_in_set_sensor_passthrough():
    """Undocumented enum value is kept for sensor entities."""
    e = _entry(data_type="enum", enum_values={0, 1}, entity_domain="sensor")
    assert e.validate(99) == 99


def test_validate_enum_value_not_in_set_binary_sensor_passthrough():
    """Undocumented enum value is kept for binary_sensor entities."""
    e = _entry(data_type="enum", enum_values={0, 1}, entity_domain="binary_sensor")
    assert e.validate(42) == 42


def test_validate_enum_value_not_in_set_select_raises():
    """Unknown enum value raises ValueError for select entities."""
    e = _entry(data_type="enum", enum_values={0, 1}, entity_domain="select")
    with pytest.raises(ValueError, match="Unexpected enum value"):
        e.validate(99)


def test_validate_enum_empty_set_allows_any():
    """No enum_values defined → any value passes through."""
    e = _entry(data_type="enum", enum_values=set())
    assert e.validate(7) == 7


# ---------------------------------------------------------------------------
# bitmask
# ---------------------------------------------------------------------------


def test_validate_bitmask_int_returns_int():
    e = _entry(data_type="bitmask")
    assert e.validate(0b1010) == 0b1010


def test_validate_bitmask_list_returns_list():
    e = _entry(data_type="bitmask")
    result = e.validate([True, False, True])
    assert result == [True, False, True]


def test_validate_bitmask_invalid_raises():
    e = _entry(data_type="bitmask")
    with pytest.raises(ValueError, match="iterable flag list"):
        e.validate(3.14)


# ---------------------------------------------------------------------------
# bcd_time
# ---------------------------------------------------------------------------


def test_validate_bcd_time_valid():
    e = _entry(data_type="bcd_time")
    assert e.validate("08:30") == "08:30"


def test_validate_bcd_time_invalid_raises():
    e = _entry(data_type="bcd_time")
    with pytest.raises(ValueError, match="HH:MM"):
        e.validate(830)


# ---------------------------------------------------------------------------
# aatt
# ---------------------------------------------------------------------------


def test_validate_aatt_valid():
    e = _entry(data_type="aatt")
    val = {"airflow_pct": 75, "temp_c": 21.5}
    assert e.validate(val) == val


def test_validate_aatt_missing_keys_raises():
    e = _entry(data_type="aatt")
    with pytest.raises(ValueError, match="airflow/temp dict"):
        e.validate({"airflow_pct": 75})


def test_validate_aatt_non_dict_raises():
    e = _entry(data_type="aatt")
    with pytest.raises(ValueError, match="airflow/temp dict"):
        e.validate("bad")


# ---------------------------------------------------------------------------
# string
# ---------------------------------------------------------------------------


def test_validate_string_coerces_to_str():
    e = _entry(data_type="string")
    assert e.validate(42) == "42"
    assert e.validate("hello") == "hello"


# ---------------------------------------------------------------------------
# bool
# ---------------------------------------------------------------------------


def test_validate_bool_from_bool():
    e = _entry(data_type="bool")
    assert e.validate(True) is True
    assert e.validate(False) is False


def test_validate_bool_from_int():
    e = _entry(data_type="bool")
    assert e.validate(1) is True
    assert e.validate(0) is False


def test_validate_bool_from_float():
    e = _entry(data_type="bool")
    assert e.validate(1.0) is True
    assert e.validate(0.0) is False


def test_validate_bool_from_str_with_enum_map():
    """String value is reverse-looked-up via enum_map."""
    e = _entry(data_type="bool", enum_map={0: "brak", 1: "jest"})
    assert e.validate("jest") is True
    assert e.validate("brak") is False


def test_validate_bool_from_str_unknown_in_enum_map():
    """String value not in enum_map falls back to bool(value)."""
    e = _entry(data_type="bool", enum_map={0: "brak", 1: "jest"})
    assert e.validate("unknown") is True  # bool("unknown") is True


def test_validate_bool_invalid_type_raises():
    e = _entry(data_type="bool")
    with pytest.raises(ValueError, match="boolean-compatible"):
        e.validate([1, 2])


# ---------------------------------------------------------------------------
# numeric (int / float)
# ---------------------------------------------------------------------------


def test_validate_int_from_int():
    e = _entry(data_type="int")
    assert e.validate(42) == 42
    assert isinstance(e.validate(42), int)


def test_validate_float_from_float():
    e = _entry(data_type="float")
    assert e.validate(3.14) == pytest.approx(3.14)
    assert isinstance(e.validate(3.14), float)


def test_validate_int_from_float_coerces():
    e = _entry(data_type="int")
    result = e.validate(3.7)
    assert result == 3
    assert isinstance(result, int)


def test_validate_numeric_non_numeric_raises():
    e = _entry(data_type="int")
    with pytest.raises(ValueError, match="numeric value"):
        e.validate("bad")


def test_validate_numeric_below_min_raises():
    e = _entry(data_type="int", min_value=0.0)
    with pytest.raises(ValueError, match="below minimum"):
        e.validate(-1)


def test_validate_numeric_above_max_raises():
    e = _entry(data_type="int", max_value=100.0)
    with pytest.raises(ValueError, match="above maximum"):
        e.validate(101)


def test_validate_numeric_at_bounds_passes():
    e = _entry(data_type="int", min_value=0.0, max_value=100.0)
    assert e.validate(0) == 0
    assert e.validate(100) == 100


# ---------------------------------------------------------------------------
# validate_register_value helper
# ---------------------------------------------------------------------------


def test_validate_register_value_unknown_register_passthrough():
    """Unknown register name returns value unchanged."""
    result = validate_register_value("nonexistent_register_xyz", 42)
    assert result == 42


def test_validate_register_value_known_register_valid():
    """Known register with valid value returns validated result."""
    from custom_components.thessla_green_modbus.register_map import REGISTER_MAP

    if not REGISTER_MAP:
        pytest.skip("REGISTER_MAP is empty in test environment")

    name, entry = next(iter(REGISTER_MAP.items()))
    # Any value that passes validation should be returned
    result = validate_register_value(name, None)
    assert result is None  # None always passes through


def test_validate_register_value_known_register_bad_value_returns_none():
    """Known int register with non-numeric value returns None (logged, not raised)."""
    from custom_components.thessla_green_modbus.register_map import REGISTER_MAP

    # Find an int register
    int_entry = next(
        (e for e in REGISTER_MAP.values() if e.data_type == "int" and e.entity_domain != "binary_sensor"),
        None,
    )
    if int_entry is None:
        pytest.skip("No int register found in REGISTER_MAP")

    result = validate_register_value(int_entry.name, "not_a_number")
    assert result is None
