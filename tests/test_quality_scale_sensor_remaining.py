# mypy: ignore-errors
"""Exercise remaining sensor setup, conversion, and aggregate-state branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from custom_components.thessla_green_modbus import sensor as sensor_module
from custom_components.thessla_green_modbus.sensor import (
    ThesslaGreenActiveErrorsSensor,
    ThesslaGreenErrorCodesSensor,
    ThesslaGreenSensor,
    ThesslaGreenSerialNumberSensor,
)
from custom_components.thessla_green_modbus.utils import TIME_REGISTER_PREFIXES
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory


def test_error_status_description_fallback_and_preferred_description() -> None:
    with patch.object(sensor_module, "get_register_definition", side_effect=KeyError("missing")):
        assert sensor_module._error_status_description("e_7") == "e_7"

    definition = SimpleNamespace(description_en="English", description="Fallback")
    with patch.object(sensor_module, "get_register_definition", return_value=definition):
        assert sensor_module._error_status_description("e_7") == "English"


@pytest.mark.asyncio
async def test_sensor_setup_capability_calculated_missing_address_and_serial_paths(mock_coordinator) -> None:
    definitions = {
        "blocked_temp": {
            "register_type": "input_registers",
            "device_class": SensorDeviceClass.TEMPERATURE,
            "translation_key": "blocked_temp",
        },
        "calc": {
            "register_type": "calculated",
            "translation_key": "calc",
        },
        "missing_address": {
            "register_type": "input_registers",
            "translation_key": "missing_address",
        },
        "serial_number": {
            "register_type": "input_registers",
            "translation_key": "serial_number",
        },
        "unavailable_temp": {
            "register_type": "input_registers",
            "device_class": SensorDeviceClass.TEMPERATURE,
            "translation_key": "unavailable_temp",
        },
    }
    mock_coordinator.device_client.available_registers = {
        "input_registers": {"missing_address", "serial_number", "e_7"},
        "holding_registers": {"e_7"},
        "calculated": {"calc"},
    }
    maps = {
        "input_registers": {"missing_address": None, "serial_number": 5},
        "holding_registers": {"e_7": 7},
    }
    mock_coordinator.device_client.get_register_map = lambda kind: maps.get(kind, {})
    mock_coordinator.device_client.force_full_register_list = False
    add = Mock()

    def reason(name, _capabilities):
        return "blocked" if name == "blocked_temp" else None

    with (
        patch.object(sensor_module, "SENSOR_DEFINITIONS", definitions),
        patch.object(sensor_module, "capability_block_reason", side_effect=reason),
    ):
        await sensor_module.async_setup_entry(
            SimpleNamespace(), SimpleNamespace(runtime_data=mock_coordinator), add
        )

    entities = add.call_args.args[0]
    assert any(isinstance(entity, ThesslaGreenSensor) and entity._register_name == "calc" for entity in entities)
    assert any(isinstance(entity, ThesslaGreenSerialNumberSensor) for entity in entities)
    assert any(isinstance(entity, ThesslaGreenErrorCodesSensor) for entity in entities)
    assert any(isinstance(entity, ThesslaGreenActiveErrorsSensor) for entity in entities)
    assert not any(getattr(entity, "_register_name", None) == "missing_address" for entity in entities)


def test_sensor_constructor_category_and_precision_paths(mock_coordinator) -> None:
    sensor = ThesslaGreenSensor(
        mock_coordinator,
        "custom",
        1,
        {
            "register_type": "input_registers",
            "translation_key": "custom",
            "entity_category": "not-a-category",
            "suggested_display_precision": 2,
        },
    )
    assert sensor._attr_entity_category == "not-a-category"
    assert sensor._attr_suggested_display_precision == 2

    diagnostic = ThesslaGreenSensor(
        mock_coordinator,
        "diag",
        2,
        {
            "register_type": "input_registers",
            "translation_key": "diag",
            "entity_category": EntityCategory.DIAGNOSTIC.value,
        },
    )
    assert diagnostic._attr_entity_category is EntityCategory.DIAGNOSTIC
    assert diagnostic._attr_entity_registry_enabled_default is False


def test_sensor_native_value_time_percentage_mapping_and_unavailable(mock_coordinator) -> None:
    prefix = TIME_REGISTER_PREFIXES[0]
    time_key = f"{prefix}quality_scale"
    timed = ThesslaGreenSensor(
        mock_coordinator, time_key, 1,
        {"register_type": "holding_registers", "translation_key": time_key},
    )
    mock_coordinator.data[time_key] = 125
    assert timed.native_value == "02:05"
    mock_coordinator.data[time_key] = "08:15"
    assert timed.native_value == "08:15"
    mock_coordinator.data[time_key] = None
    assert timed.native_value is None
    assert timed.available is True

    mock_coordinator.entry = SimpleNamespace(options={sensor_module.CONF_AIRFLOW_UNIT: sensor_module.AIRFLOW_UNIT_PERCENTAGE})
    percent = ThesslaGreenSensor(
        mock_coordinator,
        "supply_flow_rate",
        2,
        {"register_type": "input_registers", "translation_key": "supply_flow_rate", "unit": "m³/h"},
    )
    mock_coordinator.data["supply_flow_rate"] = 200
    mock_coordinator.data["nominal_supply_air_flow"] = 400
    assert percent.native_value == 50
    mock_coordinator.data["nominal_supply_air_flow"] = 0
    assert percent.native_value is None
    assert percent.available is False

    mapped = ThesslaGreenSensor(
        mock_coordinator,
        "mapped",
        3,
        {"register_type": "input_registers", "translation_key": "mapped", "value_map": {1: "on"}},
    )
    mock_coordinator.data["mapped"] = 1
    assert mapped.native_value == "on"
    mock_coordinator.data["mapped"] = 2
    assert mapped.native_value == 2


def test_sensor_availability_extra_attributes_and_nominal_exhaust(mock_coordinator) -> None:
    sensor = ThesslaGreenSensor(
        mock_coordinator,
        "outside_temperature",
        1,
        {"register_type": "input_registers", "translation_key": "outside_temperature"},
    )
    mock_coordinator.last_update_success = False
    assert sensor.available is False
    mock_coordinator.last_update_success = True
    mock_coordinator.device_client.offline_state = True
    assert sensor.available is False
    mock_coordinator.device_client.offline_state = False
    mock_coordinator.data["outside_temperature"] = sensor_module.SENSOR_UNAVAILABLE
    assert sensor.available is False
    mock_coordinator.data["outside_temperature"] = None
    assert sensor.available is False

    mock_coordinator.device_client.device_scan_result = {"scan": True}
    assert sensor.extra_state_attributes == {
        "register_name": "outside_temperature",
        "register_type": "input_registers",
    }
    mock_coordinator.device_client.device_scan_result = None
    assert sensor.extra_state_attributes == {}

    mock_coordinator.entry = None
    exhaust = ThesslaGreenSensor(
        mock_coordinator,
        "exhaust_flow_rate",
        2,
        {"register_type": "input_registers", "translation_key": "exhaust_flow_rate"},
    )
    assert exhaust._get_airflow_unit() == sensor_module.DEFAULT_AIRFLOW_UNIT
    mock_coordinator.data["nominal_exhaust_air_flow"] = 350
    assert exhaust._get_nominal_flow() == 350


def test_serial_number_sensor_native_and_availability_states(mock_coordinator) -> None:
    sensor = ThesslaGreenSerialNumberSensor(
        mock_coordinator,
        "serial_number",
        1,
        {"register_type": "input_registers", "translation_key": "serial_number"},
    )
    mock_coordinator.device_client.device_info = {}
    assert sensor.native_value is None
    assert sensor.available is False
    mock_coordinator.device_client.device_info = {"serial_number": "Unknown"}
    assert sensor.native_value is None
    assert sensor.available is False
    mock_coordinator.device_client.device_info = {"serial_number": "ABC"}
    assert sensor.native_value == "ABC"
    assert sensor.available is True
    mock_coordinator.last_update_success = False
    assert sensor.available is False
    mock_coordinator.last_update_success = True
    mock_coordinator.device_client.offline_state = True
    assert sensor.available is False


def test_error_code_aggregate_sensors_cover_empty_active_and_descriptions(mock_coordinator) -> None:
    mock_coordinator.device_client.offline_state = False
    mock_coordinator.last_update_success = True
    mock_coordinator.data = {"e_7": 1, "s_2": 1, "normal": 1}

    aggregate = ThesslaGreenErrorCodesSensor(mock_coordinator)
    assert aggregate.available is True
    assert aggregate.native_value == "E7, S2"
    assert aggregate.extra_state_attributes == {"active_errors": ["e_7", "s_2"]}

    active = ThesslaGreenActiveErrorsSensor(mock_coordinator)
    assert active.available is True
    assert active.native_value == "E7, S2"
    with patch.object(sensor_module, "_error_status_description", side_effect=lambda key: f"desc:{key}"):
        attrs = active.extra_state_attributes
    assert attrs["codes"] == ["E7", "S2"]
    assert attrs["errors"] == {"E7": "desc:e_7", "S2": "desc:s_2"}

    mock_coordinator.data = {}
    assert aggregate.native_value is None
    assert aggregate.extra_state_attributes == {}
    assert active.native_value == "none"
    assert active.extra_state_attributes == {}

    mock_coordinator.last_update_success = False
    assert active.native_value is None
    assert active.available is False
