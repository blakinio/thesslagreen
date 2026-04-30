"""Classification and routing helpers for generated entity mappings."""

from __future__ import annotations

from typing import Any

from ..utils import _to_snake_case
from ._helpers import _infer_icon
from ._mapping_payloads import (
    build_binary_toggle_mapping as _build_binary_toggle_mapping,
)
from ._mapping_payloads import (
    build_select_mapping as _build_select_mapping,
)
from ._mapping_payloads import (
    build_switch_mapping as _build_switch_mapping,
)
from ._mapping_payloads import (
    parse_info_states as _parse_info_states,
)


def classify_enum_mapping(
    register: str,
    enum: dict[Any, Any],
    access: str,
    switch_keys: set[str],
    binary_keys: set[str],
    select_keys: set[str],
) -> tuple[str | None, dict[str, Any] | None]:
    """Classify enum register into target mapping bucket and payload."""
    enum_states = {_to_snake_case(str(v)): int(k) for k, v in enum.items()}
    enum_values = {int(k) for k in enum}

    if len(enum) == 2 and enum_values == {0, 1}:
        if "W" in access:
            if register not in switch_keys:
                return None, None
            return "switch", _build_switch_mapping(register)
        if register not in binary_keys:
            return None, None
        return "binary", _build_binary_toggle_mapping(register)

    if "W" in access:
        if register not in select_keys:
            return None, None
        return "select", _build_select_mapping(register, enum_states)

    return "sensor", {
        "translation_key": register,
        "icon": "mdi:information-outline",
        "register_type": "holding_registers",
    }


def classify_min_max_mapping(
    register: str,
    access: str,
    min_val: Any,
    max_val: Any,
    info_text: str,
    unit: Any,
    step: Any,
    scale: Any,
    switch_keys: set[str],
    binary_keys: set[str],
    select_keys: set[str],
    number_keys: set[str],
) -> tuple[str | None, dict[str, Any] | None]:
    """Classify numeric min/max register into a mapping bucket and payload."""
    if min_val is None or max_val is None:
        return None, None

    if max_val <= 1:
        if "W" in access:
            if register not in switch_keys:
                return None, None
            return "switch", _build_switch_mapping(register)
        if register not in binary_keys:
            return None, None
        return "binary", _build_binary_toggle_mapping(register)

    if "W" in access and info_text and ";" in info_text and max_val <= 10:
        states = _parse_info_states(info_text)
        if states:
            if register not in select_keys:
                return None, None
            return "select", _build_select_mapping(register, states)

    if "W" in access:
        if register not in number_keys:
            return None, None
        return "number", {
            "unit": unit,
            "icon": _infer_icon(register, unit),
            "min": min_val,
            "max": max_val,
            "step": step,
            "scale": scale,
        }

    return None, None
