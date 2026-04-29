"""Tests for extracted transformation helpers in mapping builders."""

from custom_components.thessla_green_modbus.mappings._mapping_builders import (
    _classify_enum_mapping,
    _classify_min_max_mapping,
    _resolve_parent_child_mappings,
)


def test_resolve_parent_child_mappings_returns_parent_dicts() -> None:
    parent = type(
        "Parent",
        (),
        {
            "NUMBER_ENTITY_MAPPINGS": {"a": {}},
            "SENSOR_ENTITY_MAPPINGS": {"b": {}},
            "BINARY_SENSOR_ENTITY_MAPPINGS": {"c": {}},
            "SWITCH_ENTITY_MAPPINGS": {"d": {}},
            "SELECT_ENTITY_MAPPINGS": {"e": {}},
            "TEXT_ENTITY_MAPPINGS": {"f": {}},
            "TIME_ENTITY_MAPPINGS": {"g": {}},
        },
    )

    maps = _resolve_parent_child_mappings(parent)
    assert maps[0] is parent.NUMBER_ENTITY_MAPPINGS
    assert maps[6] is parent.TIME_ENTITY_MAPPINGS


def test_classify_enum_mapping_shapes() -> None:
    target, payload = _classify_enum_mapping(
        "mode", {"0": "Off", "1": "On", "2": "Auto"}, "RW", set(), set(), {"mode"}
    )
    assert target == "select"
    assert payload == {
        "icon": "mdi:format-list-bulleted",
        "translation_key": "mode",
        "states": {"off": 0, "on": 1, "auto": 2},
        "register_type": "holding_registers",
    }


def test_classify_min_max_mapping_select_then_number() -> None:
    target, payload = _classify_min_max_mapping(
        "fan_mode",
        "RW",
        0,
        10,
        "0 - low;1 - high",
        None,
        1,
        1,
        set(),
        set(),
        {"fan_mode"},
        set(),
    )
    assert target == "select"
    assert payload and payload["states"] == {"low": 0, "high": 1}

    target, payload = _classify_min_max_mapping(
        "speed",
        "RW",
        0,
        100,
        "",
        "%",
        5,
        1,
        set(),
        set(),
        set(),
        {"speed"},
    )
    assert target == "number"
    assert payload == {
        "unit": "%",
        "icon": "mdi:percent-outline",
        "min": 0,
        "max": 100,
        "step": 5,
        "scale": 1,
    }
