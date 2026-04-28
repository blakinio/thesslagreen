"""Focused tests for refactored register loader helpers."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.thessla_green_modbus.registers.parser import (
    coerce_scaling_fields,
    normalise_enum_map,
)


def test_normalise_enum_map_numeric_keys() -> None:
    enum_map = {"1": "one", "2": "two"}
    assert normalise_enum_map("mode", enum_map) == {1: "one", 2: "two"}


def test_normalise_enum_map_numeric_values() -> None:
    enum_map = {"one": "1", "two": "2"}
    assert normalise_enum_map("mode", enum_map) == {1: "one", 2: "two"}


def test_coerce_scaling_fields_defaults() -> None:
    parsed = SimpleNamespace(multiplier=None, resolution=None)
    assert coerce_scaling_fields(parsed) == (1, 1)
