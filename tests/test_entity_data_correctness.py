"""Tests verifying entity data correctness (native_value, device_class, is_on, etc.).

These tests verify that entities correctly read coordinator.data and expose the
right attributes — things that test_all_entity_creation.py does not check.
"""

from __future__ import annotations

import pytest
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS

from tests.helpers_entity_data_correctness import _make_sensor


class TestSensorNativeValue:
    """native_value reads coordinator.data and returns the right value."""

    def test_returns_float_from_coordinator(self, mock_coordinator):
        mock_coordinator.data = {"outside_temperature": 15.5}
        entity = _make_sensor(mock_coordinator, "outside_temperature")
        assert entity.native_value == 15.5

    def test_returns_integer_from_coordinator(self, mock_coordinator):
        mock_coordinator.data = {"supply_percentage": 50}
        entity = _make_sensor(mock_coordinator, "supply_percentage")
        _ = entity.native_value

    def test_returns_none_when_value_is_none(self, mock_coordinator):
        mock_coordinator.data = {"outside_temperature": None}
        entity = _make_sensor(mock_coordinator, "outside_temperature")
        assert entity.native_value is None

    def test_returns_none_when_key_missing(self, mock_coordinator):
        mock_coordinator.data = {}
        entity = _make_sensor(mock_coordinator, "outside_temperature")
        assert entity.native_value is None

    def test_returns_none_for_sensor_unavailable_sentinel(self, mock_coordinator):
        from custom_components.thessla_green_modbus.const import SENSOR_UNAVAILABLE

        mock_coordinator.data = {"outside_temperature": SENSOR_UNAVAILABLE}
        entity = _make_sensor(mock_coordinator, "outside_temperature")
        assert entity.native_value is None

    def test_returns_string_value_unchanged(self, mock_coordinator):
        mock_coordinator.data = {"exhaust_temperature": 18.2}
        entity = _make_sensor(mock_coordinator, "exhaust_temperature")
        assert entity.native_value == 18.2

    @pytest.mark.parametrize("minutes,expected", [(0, "00:00"), (60, "01:00"), (90, "01:30"), (1439, "23:59"), (120, "02:00")])
    def test_time_register_formats_minutes_as_hhmm(self, mock_coordinator, minutes, expected):
        mock_coordinator.data = {"schedule_summer_mon_1": minutes}
        entity = _make_sensor(mock_coordinator, "schedule_summer_mon_1", address=10)
        assert entity.native_value == expected

    def test_time_register_returns_none_for_none_value(self, mock_coordinator):
        mock_coordinator.data = {"schedule_summer_mon_1": None}
        entity = _make_sensor(mock_coordinator, "schedule_summer_mon_1", address=10)
        assert entity.native_value is None


class TestSensorAttributes:
    @pytest.mark.parametrize("register_name", ["outside_temperature", "supply_temperature", "exhaust_temperature"])
    def test_temperature_sensor_device_class(self, mock_coordinator, register_name):
        entity = _make_sensor(mock_coordinator, register_name)
        defn = ENTITY_MAPPINGS["sensor"][register_name]
        assert entity._attr_device_class == defn["device_class"]

    @pytest.mark.parametrize("register_name", ["outside_temperature", "supply_temperature", "exhaust_temperature"])
    def test_temperature_sensor_unit(self, mock_coordinator, register_name):
        entity = _make_sensor(mock_coordinator, register_name)
        defn = ENTITY_MAPPINGS["sensor"][register_name]
        assert entity._attr_native_unit_of_measurement == defn["unit"]

    @pytest.mark.parametrize("register_name", ["outside_temperature", "supply_temperature", "exhaust_temperature"])
    def test_temperature_sensor_state_class(self, mock_coordinator, register_name):
        entity = _make_sensor(mock_coordinator, register_name)
        defn = ENTITY_MAPPINGS["sensor"][register_name]
        assert entity._attr_state_class == defn.get("state_class")

    def test_all_sensors_have_translation_key(self, mock_coordinator):
        for name, defn in ENTITY_MAPPINGS["sensor"].items():
            assert "translation_key" in defn, f"Missing translation_key for sensor '{name}'"

    @pytest.mark.parametrize("register_name,defn", [(k, v) for k, v in ENTITY_MAPPINGS["sensor"].items() if v.get("device_class") is not None and not k.endswith("_percentage") and k not in ("supply_air_flow", "exhaust_air_flow", "supply_flow_rate", "exhaust_flow_rate")])
    def test_sensor_device_class_matches_mapping(self, mock_coordinator, register_name, defn):
        entity = _make_sensor(mock_coordinator, register_name)
        assert entity._attr_device_class == defn["device_class"]

    @pytest.mark.parametrize("register_name,defn", [(k, v) for k, v in ENTITY_MAPPINGS["sensor"].items() if v.get("unit") is not None and "percentage" not in k and k not in ("supply_air_flow", "exhaust_air_flow", "supply_flow_rate", "exhaust_flow_rate")])
    def test_sensor_unit_matches_mapping(self, mock_coordinator, register_name, defn):
        entity = _make_sensor(mock_coordinator, register_name)
        assert entity._attr_native_unit_of_measurement == defn["unit"]
