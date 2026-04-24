"""Focused tests for refactored register loader helpers."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.thessla_green_modbus.registers.loader import (
    _coerce_scaling_fields,
    _normalise_enum_map,
)


def test_normalise_enum_map_numeric_keys() -> None:
    enum_map = {"1": "one", "2": "two"}
    assert _normalise_enum_map("mode", enum_map) == {1: "one", 2: "two"}


def test_normalise_enum_map_numeric_values() -> None:
    enum_map = {"one": "1", "two": "2"}
    assert _normalise_enum_map("mode", enum_map) == {1: "one", 2: "two"}


def test_coerce_scaling_fields_defaults() -> None:
    parsed = SimpleNamespace(multiplier=None, resolution=None)
    assert _coerce_scaling_fields(parsed) == (1, 1)
