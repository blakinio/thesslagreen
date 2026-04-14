"""Tests for RegisterDefinition validator edge cases in registers/schema.py."""

import pytest
from custom_components.thessla_green_modbus.registers.schema import RegisterDefinition
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Minimal valid base record (function 3 = holding registers, access RW)
# ---------------------------------------------------------------------------

_BASE = {
    "name": "test_register",
    "function": 3,
    "address_dec": 100,
    "access": "RW",
    "description": "Test register",
    "description_en": "Test register",
}


def _make(**overrides) -> RegisterDefinition:
    data = {**_BASE, **overrides}
    return RegisterDefinition(**data)


# ---------------------------------------------------------------------------
# access field normalisation (lines 188-197)
# ---------------------------------------------------------------------------


def test_access_rw_normalised():
    """access='RW' is accepted and stored as 'RW'."""
    reg = _make(access="RW")
    assert reg.access == "RW"  # nosec B101


def test_access_r_slash_w_normalised():
    """access='R/W' is normalised to 'RW'."""
    reg = _make(access="R/W")
    assert reg.access == "RW"  # nosec B101


def test_access_r_slash_dash_normalised():
    """access='R/-' is normalised to 'R'."""
    reg = _make(access="R/-", function=2)  # function 2 → read-only
    assert reg.access == "R"  # nosec B101


def test_access_w_accepted(monkeypatch):
    """access='W' is normalised and stored as 'W' (lines 194-195)."""
    reg = _make(access="W")
    assert reg.access == "W"  # nosec B101


def test_access_invalid_raises():
    """Unknown access value raises a validation error (lines 196-197)."""
    with pytest.raises(ValidationError):
        _make(access="INVALID")


# ---------------------------------------------------------------------------
# address_dec field validation (lines 200-211)
# ---------------------------------------------------------------------------


def test_address_dec_decimal_string_accepted():
    """Decimal string address_dec is coerced to int."""
    reg = _make(address_dec="42")
    assert reg.address_dec == 42  # nosec B101


def test_address_dec_hex_string_raises():
    """Non-decimal string (hex) raises ValueError (lines 204-208)."""
    with pytest.raises(ValidationError):
        _make(address_dec="0x64")


def test_address_dec_alphabetic_string_raises():
    """Alphabetic string raises ValueError (lines 204-208)."""
    with pytest.raises(ValidationError):
        _make(address_dec="abc")


def test_address_dec_float_raises():
    """Float address_dec raises TypeError (line 211)."""
    with pytest.raises(ValidationError):
        _make(address_dec=100.0)


def test_address_dec_bool_raises():
    """Bool address_dec raises TypeError (line 211 — bool is not int for our purposes)."""
    with pytest.raises(ValidationError):
        _make(address_dec=True)


# ---------------------------------------------------------------------------
# function field normalisation (lines 69-110)
# ---------------------------------------------------------------------------


def test_function_string_alias_accepted():
    """'holding_registers' string is normalised to function code 3."""
    reg = _make(function="holding_registers")
    assert reg.function == 3  # nosec B101


def test_function_read_only_with_rw_access_raises():
    """Functions 1 or 2 require R access; RW should raise (lines 260-263)."""
    with pytest.raises(ValidationError):
        _make(function=1, access="RW")
