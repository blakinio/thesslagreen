"""Direct tests for pure mapping-builder helper functions."""

from types import SimpleNamespace

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
    _is_unmappable_holding_register,
    _parse_info_states,
    _route_enum_or_min_max_mapping,
)
from custom_components.thessla_green_modbus.mappings._static_discrete import (
    _select_payload,
    _weekday_states,
)
from custom_components.thessla_green_modbus.mappings._static_sensors import (
    _diagnostic_sensor_payload,
)
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory


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


def test_is_unmappable_holding_register_checks_direct_and_binary_source() -> None:
    all_maps = ({"mapped_reg": {"translation_key": "mapped_reg"}}, {})
    binary = {"mapped_from_source": {"register": "source_reg", "bit": 1}}

    assert _is_unmappable_holding_register("mapped_reg", all_maps, binary) is True
    assert _is_unmappable_holding_register("source_reg", all_maps, binary) is True
    assert _is_unmappable_holding_register("free_reg", all_maps, binary) is False


def test_route_enum_or_min_max_mapping_routes_enum_to_switch() -> None:
    reg = SimpleNamespace(enum={0: "off", 1: "on"}, extra=None)
    sensor: dict[str, dict] = {}
    number: dict[str, dict] = {}
    binary: dict[str, dict] = {}
    switch: dict[str, dict] = {}
    select: dict[str, dict] = {}

    _route_enum_or_min_max_mapping(
        reg=reg,
        register="enum_switch_reg",
        access="RW",
        min_val=None,
        max_val=None,
        unit=None,
        info_text="",
        scale=1,
        step=1,
        switch_keys={"enum_switch_reg"},
        binary_keys={"enum_switch_reg"},
        select_keys=set(),
        number_keys=set(),
        sensor_mappings=sensor,
        number_mappings=number,
        binary_mappings=binary,
        switch_mappings=switch,
        select_mappings=select,
    )

    assert switch["enum_switch_reg"] == {
        "icon": "mdi:toggle-switch",
        "register": "enum_switch_reg",
        "register_type": "holding_registers",
        "category": None,
        "translation_key": "enum_switch_reg",
    }
    assert sensor == {}
    assert number == {}
    assert binary == {}
    assert select == {}


def test_route_enum_or_min_max_mapping_routes_min_max_to_number() -> None:
    reg = SimpleNamespace(enum=None, extra=None)
    sensor: dict[str, dict] = {}
    number: dict[str, dict] = {}
    binary: dict[str, dict] = {}
    switch: dict[str, dict] = {}
    select: dict[str, dict] = {}

    _route_enum_or_min_max_mapping(
        reg=reg,
        register="number_reg",
        access="RW",
        min_val=0,
        max_val=100,
        unit="%",
        info_text="",
        scale=1,
        step=5,
        switch_keys=set(),
        binary_keys=set(),
        select_keys=set(),
        number_keys={"number_reg"},
        sensor_mappings=sensor,
        number_mappings=number,
        binary_mappings=binary,
        switch_mappings=switch,
        select_mappings=select,
    )

    assert number["number_reg"] == {
        "unit": "%",
        "icon": "mdi:percent-outline",
        "min": 0,
        "max": 100,
        "step": 5,
        "scale": 1,
    }


def test_select_payload_shape() -> None:
    assert _select_payload("mdi:tune", "cfg_mode_1", {"auto": 0, "manual": 1}) == {
        "icon": "mdi:tune",
        "translation_key": "cfg_mode_1",
        "states": {"auto": 0, "manual": 1},
        "register_type": "holding_registers",
    }


def test_weekday_states_values() -> None:
    assert _weekday_states() == {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }


def test_diagnostic_sensor_payload_defaults_and_overrides() -> None:
    assert _diagnostic_sensor_payload("version_major") == {
        "translation_key": "version_major",
        "icon": "mdi:information",
        "register_type": "input_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    }
    assert _diagnostic_sensor_payload(
        "exp_version",
        icon="mdi:information-outline",
        register_type="holding_registers",
    ) == {
        "translation_key": "exp_version",
        "icon": "mdi:information-outline",
        "register_type": "holding_registers",
        "entity_category": EntityCategory.DIAGNOSTIC,
    }
