from __future__ import annotations

from typing import Any


def route_enum_mapping(target: str | None, register: str, payload: dict[str, Any] | None, *, sensor_mappings: dict[str, Any], binary_mappings: dict[str, Any], switch_mappings: dict[str, Any], select_mappings: dict[str, Any]) -> bool:
    if target == "switch":
        switch_mappings.setdefault(register, payload)
        return True
    if target == "binary":
        binary_mappings.setdefault(register, payload)
        return True
    if target == "select":
        select_mappings.setdefault(register, payload)
        return True
    if target == "sensor":
        sensor_mappings.setdefault(register, payload)
        return True
    return False


def route_min_max_mapping(target: str | None, register: str, payload: dict[str, Any] | None, *, number_mappings: dict[str, Any], binary_mappings: dict[str, Any], switch_mappings: dict[str, Any], select_mappings: dict[str, Any]) -> bool:
    if target == "switch":
        switch_mappings.setdefault(register, payload)
        return True
    if target == "binary":
        binary_mappings.setdefault(register, payload)
        return True
    if target == "select":
        select_mappings.setdefault(register, payload)
        return True
    if target == "number":
        number_mappings.setdefault(register, payload)
        return True
    return False
