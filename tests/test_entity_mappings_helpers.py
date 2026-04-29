"""Direct tests for pure mapping-builder helper functions."""

from custom_components.thessla_green_modbus.mappings._mapping_builders import (
    _build_binary_toggle_mapping,
    _build_problem_binary_mapping,
    _build_select_mapping,
    _build_switch_mapping,
    _build_time_like_mapping,
    _is_already_mapped,
    _is_mapped_as_binary_source,
    _is_problem_register,
    _is_register_mapped_anywhere,
    _parse_info_states,
)
from homeassistant.components.binary_sensor import BinarySensorDeviceClass


def test_is_already_mapped_true_and_false() -> None:
    mappings = {"reg_a": {"translation_key": "reg_a"}}
    assert _is_already_mapped("reg_a", mappings) is True
    assert _is_already_mapped("reg_b", mappings) is False


def test_is_mapped_as_binary_source() -> None:
    binary = {
        "source_reg_bit_0": {"register": "source_reg", "bit": 1},
        "simple_reg": {"translation_key": "simple_reg"},
    }
    assert _is_mapped_as_binary_source("source_reg", binary) is True
    assert _is_mapped_as_binary_source("other_reg", binary) is False


def test_is_problem_register_variants() -> None:
    assert _is_problem_register("alarm") is True
    assert _is_problem_register("error") is True
    assert _is_problem_register("s_status") is True
    assert _is_problem_register("e_12") is True
    assert _is_problem_register("f_fault") is True
    assert _is_problem_register("normal_register") is False


def test_parse_info_states_parses_and_skips_invalid_parts() -> None:
    parsed = _parse_info_states("0 - off; x - broken;1 - on;ignored")
    assert parsed == {"off": 0, "on": 1}


def test_is_register_mapped_anywhere() -> None:
    assert _is_register_mapped_anywhere("reg_a", ({"reg_a": {}}, {"reg_b": {}})) is True
    assert _is_register_mapped_anywhere("reg_x", ({"reg_a": {}}, {"reg_b": {}})) is False


def test_build_problem_binary_mapping_shape() -> None:
    assert _build_problem_binary_mapping("alarm") == {
        "translation_key": "alarm",
        "icon": "mdi:alert-circle",
        "register_type": "holding_registers",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    }


def test_build_time_like_mapping_shape() -> None:
    assert _build_time_like_mapping("schedule_slot") == {
        "translation_key": "schedule_slot",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
    }


def test_build_switch_mapping_shape() -> None:
    assert _build_switch_mapping("enable_feature") == {
        "icon": "mdi:toggle-switch",
        "register": "enable_feature",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "enable_feature",
    }


def test_build_binary_toggle_mapping_shape() -> None:
    assert _build_binary_toggle_mapping("filter_dirty") == {
        "translation_key": "filter_dirty",
        "icon": "mdi:checkbox-marked-circle-outline",
        "register_type": "holding_registers",
    }


def test_build_select_mapping_shape() -> None:
    assert _build_select_mapping("mode", {"auto": 0, "manual": 1}) == {
        "icon": "mdi:format-list-bulleted",
        "translation_key": "mode",
        "states": {"auto": 0, "manual": 1},
        "register_type": "holding_registers",
    }
