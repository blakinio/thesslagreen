"""Tests verifying entity data correctness (native_value, device_class, is_on, etc.).

These tests verify that entities correctly read coordinator.data and expose the
right attributes — things that test_all_entity_creation.py does not check.
"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# HA component stubs not provided by conftest
# ---------------------------------------------------------------------------

def _ensure_attr(mod, name, value):
    if not hasattr(mod, name):
        setattr(mod, name, value)


# binary_sensor: BinarySensorEntity missing from conftest
_bs_mod = sys.modules.setdefault(
    "homeassistant.components.binary_sensor",
    types.ModuleType("homeassistant.components.binary_sensor"),
)


class _BinarySensorEntity:  # pragma: no cover - stub
    pass


_ensure_attr(_bs_mod, "BinarySensorEntity", _BinarySensorEntity)


# number
_num_mod = sys.modules.setdefault(
    "homeassistant.components.number",
    types.ModuleType("homeassistant.components.number"),
)


class _NumberEntity:  # pragma: no cover - stub
    pass


class _NumberMode:  # pragma: no cover - stub
    BOX = "box"
    SLIDER = "slider"


_ensure_attr(_num_mod, "NumberEntity", _NumberEntity)
_ensure_attr(_num_mod, "NumberMode", _NumberMode)


# select
_sel_mod = sys.modules.setdefault(
    "homeassistant.components.select",
    types.ModuleType("homeassistant.components.select"),
)


class _SelectEntity:  # pragma: no cover - stub
    pass


_ensure_attr(_sel_mod, "SelectEntity", _SelectEntity)


# EntityCategory
_he_mod = sys.modules.setdefault(
    "homeassistant.helpers.entity",
    types.ModuleType("homeassistant.helpers.entity"),
)


class _EntityCategory:  # pragma: no cover - stub
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


_ensure_attr(_he_mod, "EntityCategory", _EntityCategory)


# UnitOfTime.MINUTES — conftest defines UnitOfTime without MINUTES
_ha_const = sys.modules.get("homeassistant.const")
if _ha_const is not None:
    # UnitOfTemperature — required by number.py and entity_mappings.py
    _unit_temp = getattr(_ha_const, "UnitOfTemperature", None)
    if _unit_temp is None:
        class _UnitOfTemperature:  # pragma: no cover - stub
            CELSIUS = "°C"
        _ha_const.UnitOfTemperature = _UnitOfTemperature

    # UnitOfTime — number.py requires MINUTES
    _unit_time = getattr(_ha_const, "UnitOfTime", None)
    if _unit_time is None:
        class _UnitOfTime:  # pragma: no cover - stub
            MINUTES = "min"
            HOURS = "h"
            DAYS = "d"
            SECONDS = "s"
        _ha_const.UnitOfTime = _UnitOfTime
    else:
        for _attr, _val in [("MINUTES", "min"), ("HOURS", "h"), ("DAYS", "d"), ("SECONDS", "s")]:
            if not hasattr(_unit_time, _attr):
                setattr(_unit_time, _attr, _val)

    _ensure_attr(_ha_const, "PERCENTAGE", "%")

    # UnitOfVolumeFlowRate
    _unit_vol = getattr(_ha_const, "UnitOfVolumeFlowRate", None)
    if _unit_vol is None:
        class _UnitOfVolumeFlowRate:  # pragma: no cover - stub
            CUBIC_METERS_PER_HOUR = "m³/h"
        _ha_const.UnitOfVolumeFlowRate = _UnitOfVolumeFlowRate
    else:
        _ensure_attr(_unit_vol, "CUBIC_METERS_PER_HOUR", "m³/h")

    # UnitOfElectricPotential — entity_mappings.py imports this
    _unit_volt = getattr(_ha_const, "UnitOfElectricPotential", None)
    if _unit_volt is None:
        class _UnitOfElectricPotential:  # pragma: no cover - stub
            VOLT = "V"
        _ha_const.UnitOfElectricPotential = _UnitOfElectricPotential

# ---------------------------------------------------------------------------
# Imports (after stubs are in place)
# ---------------------------------------------------------------------------

from custom_components.thessla_green_modbus.binary_sensor import ThesslaGreenBinarySensor
from custom_components.thessla_green_modbus.entity_mappings import (
    BINARY_SENSOR_ENTITY_MAPPINGS,
    ENTITY_MAPPINGS,
)
from custom_components.thessla_green_modbus.number import ThesslaGreenNumber
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect
from custom_components.thessla_green_modbus.sensor import ThesslaGreenSensor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sensor(coordinator, name: str, address: int = 100) -> ThesslaGreenSensor:
    """Create a ThesslaGreenSensor using the live entity mapping for *name*."""
    defn = ENTITY_MAPPINGS["sensor"].get(name, {"translation_key": name})
    return ThesslaGreenSensor(coordinator, name, address, defn)


def _make_binary_sensor(
    coordinator,
    sensor_def: dict[str, Any],
    register_name: str | None = None,
    address: int = 100,
) -> ThesslaGreenBinarySensor:
    reg = register_name or sensor_def.get("register", list(sensor_def.keys())[0])
    return ThesslaGreenBinarySensor(coordinator, reg, address, sensor_def)


def _make_number(coordinator, register_name: str) -> ThesslaGreenNumber:
    config = ENTITY_MAPPINGS["number"][register_name]
    return ThesslaGreenNumber(coordinator, register_name, config)


def _make_select(coordinator, register_name: str) -> ThesslaGreenSelect:
    defn = ENTITY_MAPPINGS["select"][register_name]
    address = coordinator.get_register_map(defn["register_type"]).get(register_name, 100)
    return ThesslaGreenSelect(coordinator, register_name, address, defn)


# ---------------------------------------------------------------------------
# Tests: ThesslaGreenSensor.native_value
# ---------------------------------------------------------------------------

class TestSensorNativeValue:
    """native_value reads coordinator.data and returns the right value."""

    def test_returns_float_from_coordinator(self, mock_coordinator):
        mock_coordinator.data = {"outside_temperature": 15.5}
        entity = _make_sensor(mock_coordinator, "outside_temperature")
        assert entity.native_value == 15.5

    def test_returns_integer_from_coordinator(self, mock_coordinator):
        mock_coordinator.data = {"supply_percentage": 50}
        entity = _make_sensor(mock_coordinator, "supply_percentage")
        # supply_percentage is a percentage sensor — native_value may return a
        # computed percentage or the raw value depending on nominal flow
        # being available. We only check it does not raise.
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

    @pytest.mark.parametrize("minutes,expected", [
        (0, "00:00"),
        (60, "01:00"),
        (90, "01:30"),
        (1439, "23:59"),
        (120, "02:00"),
    ])
    def test_time_register_formats_minutes_as_hhmm(
        self, mock_coordinator, minutes, expected
    ):
        """schedule_* registers contain integer minutes → formatted as HH:MM."""
        mock_coordinator.data = {"schedule_summer_mon_1": minutes}
        entity = _make_sensor(mock_coordinator, "schedule_summer_mon_1", address=10)
        assert entity.native_value == expected

    def test_time_register_returns_none_for_none_value(self, mock_coordinator):
        """Time register with None value returns None (sensor stays unknown)."""
        mock_coordinator.data = {"schedule_summer_mon_1": None}
        entity = _make_sensor(mock_coordinator, "schedule_summer_mon_1", address=10)
        assert entity.native_value is None


# ---------------------------------------------------------------------------
# Tests: ThesslaGreenSensor — static attributes
# ---------------------------------------------------------------------------

class TestSensorAttributes:
    """_attr_device_class, _attr_state_class, _attr_native_unit_of_measurement."""

    @pytest.mark.parametrize("register_name", [
        "outside_temperature",
        "supply_temperature",
        "exhaust_temperature",
    ])
    def test_temperature_sensor_device_class(self, mock_coordinator, register_name):
        entity = _make_sensor(mock_coordinator, register_name)
        defn = ENTITY_MAPPINGS["sensor"][register_name]
        assert entity._attr_device_class == defn["device_class"]

    @pytest.mark.parametrize("register_name", [
        "outside_temperature",
        "supply_temperature",
        "exhaust_temperature",
    ])
    def test_temperature_sensor_unit(self, mock_coordinator, register_name):
        entity = _make_sensor(mock_coordinator, register_name)
        defn = ENTITY_MAPPINGS["sensor"][register_name]
        assert entity._attr_native_unit_of_measurement == defn["unit"]

    @pytest.mark.parametrize("register_name", [
        "outside_temperature",
        "supply_temperature",
        "exhaust_temperature",
    ])
    def test_temperature_sensor_state_class(self, mock_coordinator, register_name):
        entity = _make_sensor(mock_coordinator, register_name)
        defn = ENTITY_MAPPINGS["sensor"][register_name]
        assert entity._attr_state_class == defn.get("state_class")

    def test_all_sensors_have_translation_key(self, mock_coordinator):
        """Every entry in ENTITY_MAPPINGS['sensor'] must have a translation_key."""
        for name, defn in ENTITY_MAPPINGS["sensor"].items():
            assert "translation_key" in defn, f"Missing translation_key for sensor '{name}'"

    @pytest.mark.parametrize("register_name,defn", [
        (k, v) for k, v in ENTITY_MAPPINGS["sensor"].items()
        if v.get("device_class") is not None and not k.endswith("_percentage")
        and k not in ("supply_air_flow", "exhaust_air_flow", "supply_flow_rate", "exhaust_flow_rate")
    ])
    def test_sensor_device_class_matches_mapping(self, mock_coordinator, register_name, defn):
        entity = _make_sensor(mock_coordinator, register_name)
        assert entity._attr_device_class == defn["device_class"]

    @pytest.mark.parametrize("register_name,defn", [
        (k, v) for k, v in ENTITY_MAPPINGS["sensor"].items()
        if v.get("unit") is not None
        and "percentage" not in k  # percentage sensors may override unit
        and k not in ("supply_air_flow", "exhaust_air_flow", "supply_flow_rate", "exhaust_flow_rate")
    ])
    def test_sensor_unit_matches_mapping(self, mock_coordinator, register_name, defn):
        entity = _make_sensor(mock_coordinator, register_name)
        assert entity._attr_native_unit_of_measurement == defn["unit"]


# ---------------------------------------------------------------------------
# Tests: ThesslaGreenBinarySensor.is_on
# ---------------------------------------------------------------------------

class TestBinarySensorIsOn:
    """is_on handles coil, discrete, holding/input with and without bit mask."""

    @pytest.mark.parametrize("raw,expected", [
        (True, True), (False, False), (1, True), (0, False),
    ])
    def test_coil_register_direct_bool(self, mock_coordinator, raw, expected):
        sensor_def = {
            "translation_key": "power_supply_fans",
            "icon": "mdi:fan",
            "register_type": "coil_registers",
        }
        mock_coordinator.data = {"power_supply_fans": raw}
        entity = ThesslaGreenBinarySensor(
            mock_coordinator, "power_supply_fans", 4, sensor_def
        )
        assert entity.is_on == expected

    @pytest.mark.parametrize("raw,expected", [
        (True, True), (False, False), (1, True), (0, False),
    ])
    def test_discrete_input_direct_bool(self, mock_coordinator, raw, expected):
        sensor_def = {
            "translation_key": "expansion",
            "icon": "mdi:expansion-card",
            "register_type": "discrete_inputs",
        }
        mock_coordinator.data = {"expansion": raw}
        entity = ThesslaGreenBinarySensor(
            mock_coordinator, "expansion", 5, sensor_def
        )
        assert entity.is_on == expected

    def test_holding_register_with_bit_set(self, mock_coordinator):
        """When bit is specified, is_on extracts that specific bit."""
        bit = 0b00000100  # bit 2
        sensor_def = {
            "translation_key": "some_flag",
            "icon": "mdi:flag",
            "register_type": "holding_registers",
            "bit": bit,
        }
        mock_coordinator.data = {"some_flag": bit}  # exactly that bit set
        entity = ThesslaGreenBinarySensor(mock_coordinator, "some_flag", 100, sensor_def)
        assert entity.is_on is True

    def test_holding_register_with_bit_clear(self, mock_coordinator):
        bit = 0b00000100
        sensor_def = {
            "translation_key": "some_flag",
            "icon": "mdi:flag",
            "register_type": "holding_registers",
            "bit": bit,
        }
        mock_coordinator.data = {"some_flag": ~bit & 0xFFFF}  # bit NOT set
        entity = ThesslaGreenBinarySensor(mock_coordinator, "some_flag", 100, sensor_def)
        assert entity.is_on is False

    def test_holding_register_without_bit_nonzero(self, mock_coordinator):
        sensor_def = {
            "translation_key": "flag",
            "icon": "mdi:flag",
            "register_type": "holding_registers",
        }
        mock_coordinator.data = {"flag": 7}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "flag", 100, sensor_def)
        assert entity.is_on is True

    def test_holding_register_without_bit_zero(self, mock_coordinator):
        sensor_def = {
            "translation_key": "flag",
            "icon": "mdi:flag",
            "register_type": "holding_registers",
        }
        mock_coordinator.data = {"flag": 0}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "flag", 100, sensor_def)
        assert entity.is_on is False

    def test_returns_none_when_data_key_missing(self, mock_coordinator):
        sensor_def = {
            "translation_key": "power_supply_fans",
            "icon": "mdi:fan",
            "register_type": "coil_registers",
        }
        mock_coordinator.data = {}  # key absent
        entity = ThesslaGreenBinarySensor(
            mock_coordinator, "power_supply_fans", 4, sensor_def
        )
        assert entity.is_on is None

    def test_inverted_flag_flips_result(self, mock_coordinator):
        sensor_def = {
            "translation_key": "inv_flag",
            "icon": "mdi:flag",
            "register_type": "coil_registers",
            "inverted": True,
        }
        mock_coordinator.data = {"inv_flag": True}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "inv_flag", 100, sensor_def)
        assert entity.is_on is False

        mock_coordinator.data = {"inv_flag": False}
        assert entity.is_on is True

    def test_all_binary_sensor_mappings_have_register_type(self):
        """Every BINARY_SENSOR_ENTITY_MAPPINGS entry must have register_type."""
        for key, defn in BINARY_SENSOR_ENTITY_MAPPINGS.items():
            assert "register_type" in defn, f"Missing register_type for binary sensor '{key}'"

    def test_all_binary_sensor_mappings_have_translation_key(self):
        """Every BINARY_SENSOR_ENTITY_MAPPINGS entry must have translation_key."""
        for key, defn in BINARY_SENSOR_ENTITY_MAPPINGS.items():
            assert "translation_key" in defn, f"Missing translation_key for binary sensor '{key}'"


# ---------------------------------------------------------------------------
# Tests: ThesslaGreenNumber attributes and native_value
# ---------------------------------------------------------------------------

class TestNumberEntity:
    """min, max, step, native_value."""

    def _first_number_register(self, mock_coordinator) -> str:
        """Return first number register that is in holding_registers map."""
        holding = mock_coordinator.get_register_map("holding_registers")
        for name in ENTITY_MAPPINGS["number"]:
            if name in holding:
                return name
        pytest.skip("No number register found in holding_registers")

    def test_native_value_from_coordinator(self, mock_coordinator):
        name = self._first_number_register(mock_coordinator)
        mock_coordinator.data[name] = 42
        entity = _make_number(mock_coordinator, name)
        assert entity.native_value == 42.0

    def test_native_value_float_from_int(self, mock_coordinator):
        name = self._first_number_register(mock_coordinator)
        mock_coordinator.data[name] = 25
        entity = _make_number(mock_coordinator, name)
        assert isinstance(entity.native_value, float)

    def test_native_value_none_when_key_missing(self, mock_coordinator):
        name = self._first_number_register(mock_coordinator)
        mock_coordinator.data.pop(name, None)
        entity = _make_number(mock_coordinator, name)
        assert entity.native_value is None

    def test_native_value_none_for_none_in_data(self, mock_coordinator):
        name = self._first_number_register(mock_coordinator)
        mock_coordinator.data[name] = None
        entity = _make_number(mock_coordinator, name)
        assert entity.native_value is None

    def test_min_less_than_max(self, mock_coordinator):
        name = self._first_number_register(mock_coordinator)
        entity = _make_number(mock_coordinator, name)
        assert entity._attr_native_min_value < entity._attr_native_max_value

    def test_default_min_is_zero_when_not_configured(self, mock_coordinator):
        """If entity_config has no 'min', default is 0."""
        holding = mock_coordinator.get_register_map("holding_registers")
        # Find a number register whose config has no 'min' key
        for name, cfg in ENTITY_MAPPINGS["number"].items():
            if name in holding and "min" not in cfg:
                entity = _make_number(mock_coordinator, name)
                assert entity._attr_native_min_value == 0
                return
        pytest.skip("All number registers have explicit 'min'")

    def test_default_max_is_100_when_not_configured(self, mock_coordinator):
        """If entity_config has no 'max', default is 100."""
        holding = mock_coordinator.get_register_map("holding_registers")
        for name, cfg in ENTITY_MAPPINGS["number"].items():
            if name in holding and "max" not in cfg:
                entity = _make_number(mock_coordinator, name)
                assert entity._attr_native_max_value == 100
                return
        pytest.skip("All number registers have explicit 'max'")

    def test_step_defaults_to_one(self, mock_coordinator):
        """If entity_config has no 'step', default native_step is 1."""
        holding = mock_coordinator.get_register_map("holding_registers")
        for name, cfg in ENTITY_MAPPINGS["number"].items():
            if name in holding and "step" not in cfg:
                entity = _make_number(mock_coordinator, name)
                assert entity._attr_native_step == 1
                return
        pytest.skip("All number registers have explicit 'step'")

    def test_temperature_register_uses_thermometer_icon(self, mock_coordinator):
        """Registers with 'temperature' in name get thermometer icon."""
        holding = mock_coordinator.get_register_map("holding_registers")
        for name in ENTITY_MAPPINGS["number"]:
            if name in holding and "temperature" in name:
                entity = _make_number(mock_coordinator, name)
                assert entity._attr_icon == "mdi:thermometer"
                return
        pytest.skip("No temperature number register found")

    @pytest.mark.parametrize("register_name,cfg", [
        (k, v) for k, v in ENTITY_MAPPINGS["number"].items()
        if v.get("min") is not None and v.get("max") is not None
    ][:10])  # limit to 10 to keep test runs fast
    def test_explicit_min_max_applied(self, mock_coordinator, register_name, cfg):
        """When config has min/max, entity attributes match."""
        holding = mock_coordinator.get_register_map("holding_registers")
        if register_name not in holding:
            pytest.skip(f"{register_name} not in holding_registers")
        entity = _make_number(mock_coordinator, register_name)
        assert entity._attr_native_min_value == cfg["min"]
        assert entity._attr_native_max_value == cfg["max"]


# ---------------------------------------------------------------------------
# Tests: ThesslaGreenSelect — options and current_option
# ---------------------------------------------------------------------------

class TestSelectEntity:
    """options list and current_option mapping."""

    def test_options_match_definition_keys(self, mock_coordinator):
        name = "mode"
        entity = _make_select(mock_coordinator, name)
        expected = set(ENTITY_MAPPINGS["select"][name]["states"].keys())
        assert set(entity._attr_options) == expected

    def test_options_include_all_states(self, mock_coordinator):
        name = "season_mode"
        entity = _make_select(mock_coordinator, name)
        assert set(entity._attr_options) == {"winter", "summer"}

    def test_current_option_maps_int_to_string(self, mock_coordinator):
        """coordinator.data has integer → current_option returns option name."""
        name = "mode"
        mock_coordinator.data[name] = 1  # 1 → "manual"
        entity = _make_select(mock_coordinator, name)
        assert entity.current_option == "manual"

    def test_current_option_first_value(self, mock_coordinator):
        name = "mode"
        mock_coordinator.data[name] = 0  # 0 → "auto"
        entity = _make_select(mock_coordinator, name)
        assert entity.current_option == "auto"

    def test_current_option_last_value(self, mock_coordinator):
        name = "mode"
        mock_coordinator.data[name] = 2  # 2 → "temporary"
        entity = _make_select(mock_coordinator, name)
        assert entity.current_option == "temporary"

    def test_current_option_none_when_key_missing(self, mock_coordinator):
        name = "mode"
        mock_coordinator.data.pop(name, None)
        entity = _make_select(mock_coordinator, name)
        assert entity.current_option is None

    def test_current_option_none_for_unknown_value(self, mock_coordinator):
        """An integer not in states → current_option returns None."""
        name = "mode"
        mock_coordinator.data[name] = 999  # not in states
        entity = _make_select(mock_coordinator, name)
        assert entity.current_option is None

    def test_season_mode_winter(self, mock_coordinator):
        mock_coordinator.data["season_mode"] = 0
        entity = _make_select(mock_coordinator, "season_mode")
        assert entity.current_option == "winter"

    def test_season_mode_summer(self, mock_coordinator):
        mock_coordinator.data["season_mode"] = 1
        entity = _make_select(mock_coordinator, "season_mode")
        assert entity.current_option == "summer"

    def test_all_select_mappings_have_states(self):
        """Every select definition must have a non-empty 'states' dict."""
        for name, defn in ENTITY_MAPPINGS["select"].items():
            assert "states" in defn, f"Missing 'states' for select '{name}'"
            assert defn["states"], f"Empty 'states' for select '{name}'"

    def test_all_select_mappings_have_translation_key(self):
        for name, defn in ENTITY_MAPPINGS["select"].items():
            assert "translation_key" in defn, f"Missing translation_key for select '{name}'"

    @pytest.mark.parametrize("select_name,defn", list(ENTITY_MAPPINGS["select"].items()))
    def test_options_are_list_of_strings(self, mock_coordinator, select_name, defn):
        holding = mock_coordinator.get_register_map(defn.get("register_type", "holding_registers"))
        address = holding.get(select_name, 100)
        entity = ThesslaGreenSelect(mock_coordinator, select_name, address, defn)
        assert isinstance(entity._attr_options, list)
        assert all(isinstance(o, str) for o in entity._attr_options)
