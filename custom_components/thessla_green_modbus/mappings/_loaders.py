"""Loader functions for entity mapping generation."""

from __future__ import annotations

from typing import Any

from ..const import SPECIAL_FUNCTION_MAP
from ._mapping_builders import (
    _extend_entity_mappings_from_registers,
    _get_parent,
    _load_discrete_mappings,
    _load_number_mappings,
)


def _build_entity_mappings() -> None:
    """Populate entity mapping dictionaries (module-global side-effects)."""

    parent = _get_parent()

    def _maps(name: str) -> dict[str, Any]:
        return getattr(parent, name, {}) if parent else {}

    sensor_mappings = _maps("SENSOR_ENTITY_MAPPINGS")
    select_mappings = _maps("SELECT_ENTITY_MAPPINGS")
    binary_mappings = _maps("BINARY_SENSOR_ENTITY_MAPPINGS")
    switch_mappings = _maps("SWITCH_ENTITY_MAPPINGS")
    text_mappings = _maps("TEXT_ENTITY_MAPPINGS")
    special_mode_icons: dict[str, str] = _maps("SPECIAL_MODE_ICONS")

    number_mappings = _maps("NUMBER_ENTITY_MAPPINGS")
    number_mappings.clear()
    number_mappings.update(_load_number_mappings())
    time_mappings: dict[str, dict[str, Any]] = {}

    _gen_binary, _gen_switch, _gen_select = _load_discrete_mappings()
    for key in binary_mappings:
        _gen_binary.pop(key, None)
        _gen_switch.pop(key, None)
        _gen_select.pop(key, None)
    for key in switch_mappings:
        _gen_binary.pop(key, None)
        _gen_select.pop(key, None)
    for key in select_mappings:
        _gen_binary.pop(key, None)
        _gen_switch.pop(key, None)
    binary_mappings.update(_gen_binary)
    switch_mappings.update(_gen_switch)
    select_mappings.update(_gen_select)

    for mode, bit in SPECIAL_FUNCTION_MAP.items():
        switch_mappings[mode] = {
            "icon": special_mode_icons.get(mode, "mdi:toggle-switch"),
            "register": "special_mode",
            "register_type": "holding_registers",
            "category": None,
            "translation_key": mode,
            "bit": bit,
        }

    # Temporarily inject time_mappings into parent so
    # _extend_entity_mappings_from_registers can see it via _get_parent().
    if parent is not None:
        parent.TIME_ENTITY_MAPPINGS = time_mappings

    _extend_entity_mappings_from_registers()

    if parent is not None:
        parent.ENTITY_MAPPINGS = {
            "number": number_mappings,
            "sensor": sensor_mappings,
            "binary_sensor": binary_mappings,
            "switch": switch_mappings,
            "select": select_mappings,
            "text": text_mappings,
            "time": time_mappings,
        }


__all__ = [
    "_build_entity_mappings",
    "_extend_entity_mappings_from_registers",
    "_load_discrete_mappings",
    "_load_number_mappings",
]
