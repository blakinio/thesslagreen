"""Tests for extracted transformation helpers in mapping builders."""

from custom_components.thessla_green_modbus.mappings._mapping_builders import (
    _apply_diagnostic_binary_overrides,
    _build_base_translation_mapping,
    _build_sensor_season_setting_mapping,
    _classify_enum_mapping,
    _classify_min_max_mapping,
    _diag_register_candidates,
    _is_binary_state_pair,
    _iter_bitmask_binary_entries,
    _register_context,
    _resolve_parent_child_mappings,
    _route_enum_mapping,
    _route_min_max_mapping,
    _route_problem_mapping,
    _route_time_and_season_mappings,
)
from homeassistant.helpers.entity import EntityCategory


def test_build_base_translation_mapping_shape() -> None:
    assert _build_base_translation_mapping("pump", "holding_registers") == {
        "translation_key": "pump",
        "register_type": "holding_registers",
    }


def test_build_sensor_season_setting_mapping_shape() -> None:
    assert _build_sensor_season_setting_mapping("setting_summer_mode") == {
        "translation_key": "setting_summer_mode",
        "icon": "mdi:fan",
        "register_type": "holding_registers",
    }


def test_is_binary_state_pair_detects_only_01_pairs() -> None:
    assert _is_binary_state_pair({"off": 0, "on": 1}) is True
    assert _is_binary_state_pair({"off": 0, "on": 2}) is False


def test_diag_register_candidates_includes_alarm_error_and_prefixed() -> None:
    candidates = _diag_register_candidates({"s_x", "e_1", "normal", "temp"})
    assert {"alarm", "error", "s_x", "e_1"}.issubset(candidates)


def test_iter_bitmask_binary_entries_named_and_fallback() -> None:
    reg = type("Reg", (), {"name": "status", "function": 3, "bits": [{"name": "Pump On"}, None]})
    entries = dict(_iter_bitmask_binary_entries(reg))
    assert entries["status_pump_on"] == {
        "translation_key": "status_pump_on",
        "register_type": "holding_registers",
        "register": "status",
        "bit": 1,
    }
    assert entries["status"] == {
        "translation_key": "status",
        "register_type": "holding_registers",
        "bitmask": True,
    }


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


def test_route_enum_mapping_routes_to_expected_bucket() -> None:
    sensor: dict[str, dict[str, object]] = {}
    binary: dict[str, dict[str, object]] = {}
    switch: dict[str, dict[str, object]] = {}
    select: dict[str, dict[str, object]] = {}
    payload = {"translation_key": "mode", "states": {"auto": 2}}

    handled = _route_enum_mapping(
        "select", "mode", payload, sensor, binary, switch, select
    )
    assert handled is True
    assert select == {"mode": payload}
    assert sensor == {}
    assert binary == {}
    assert switch == {}


def test_route_min_max_mapping_routes_to_expected_bucket() -> None:
    number: dict[str, dict[str, object]] = {}
    binary: dict[str, dict[str, object]] = {}
    switch: dict[str, dict[str, object]] = {}
    select: dict[str, dict[str, object]] = {}
    payload = {"unit": "%", "min": 0, "max": 100}

    handled = _route_min_max_mapping(
        "number", "speed", payload, number, binary, switch, select
    )
    assert handled is True
    assert number == {"speed": payload}
    assert binary == {}
    assert switch == {}
    assert select == {}


def test_register_context_normalizes_resolution_and_defaults() -> None:
    reg = type(
        "Reg",
        (),
        {
            "name": "speed",
            "access": "rw",
            "min": 0,
            "max": 100,
            "unit": "%",
            "information": None,
            "multiplier": 10,
            "resolution": None,
        },
    )
    assert _register_context(reg) == ("speed", "RW", 0, 100, "%", "", 10, 10)


def test_route_problem_mapping_requires_binary_translation_key() -> None:
    binary: dict[str, dict[str, object]] = {}
    assert _route_problem_mapping("alarm", {"alarm"}, binary) is True
    assert "alarm" in binary
    assert _route_problem_mapping("error", set(), binary) is False


def test_route_time_and_season_mappings_routes_expected_buckets() -> None:
    sensor: dict[str, dict[str, object]] = {}
    time: dict[str, dict[str, object]] = {}
    select: dict[str, dict[str, object]] = {}
    assert _route_time_and_season_mappings("schedule_wake", "RW", sensor, time, select) is True
    assert "schedule_wake" in time
    assert _route_time_and_season_mappings("setting_winter_mode", "R", sensor, time, select) is True
    assert "setting_winter_mode" in sensor


def test_apply_diagnostic_binary_overrides_sets_binary_and_clears_conflicts() -> None:
    binary = {}
    switch = {"alarm": {"translation_key": "alarm"}}
    select = {"s_1": {"translation_key": "s_1"}}

    _apply_diagnostic_binary_overrides(
        {"alarm", "s_1", "unknown"},
        {"s_1", "normal"},
        {"alarm", "s_1"},
        binary,
        switch,
        select,
    )

    assert binary == {
        "alarm": {
            "translation_key": "alarm",
            "register_type": "holding_registers",
            "entity_category": EntityCategory.DIAGNOSTIC,
        },
        "s_1": {
            "translation_key": "s_1",
            "register_type": "holding_registers",
            "entity_category": EntityCategory.DIAGNOSTIC,
        },
    }
    assert switch == {}
    assert select == {}


def test_apply_diagnostic_binary_overrides_skips_when_not_translated_or_not_holding() -> None:
    binary = {}
    switch = {"e_1": {"translation_key": "e_1"}}
    select = {"e_1": {"translation_key": "e_1"}}

    _apply_diagnostic_binary_overrides(
        {"e_1", "random"},
        {"normal"},
        {"alarm"},
        binary,
        switch,
        select,
    )

    assert binary == {}
    assert switch == {"e_1": {"translation_key": "e_1"}}
    assert select == {"e_1": {"translation_key": "e_1"}}
