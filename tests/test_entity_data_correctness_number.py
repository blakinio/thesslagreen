from __future__ import annotations

import pytest
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS

from tests.helpers_entity_data_correctness import _make_number


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
        holding = mock_coordinator.get_register_map("holding_registers")
        for name, cfg in ENTITY_MAPPINGS["number"].items():
            if name in holding and "min" not in cfg:
                entity = _make_number(mock_coordinator, name)
                assert entity._attr_native_min_value == 0
                return
        pytest.skip("All number registers have explicit 'min'")

    def test_default_max_is_100_when_not_configured(self, mock_coordinator):
        holding = mock_coordinator.get_register_map("holding_registers")
        for name, cfg in ENTITY_MAPPINGS["number"].items():
            if name in holding and "max" not in cfg:
                entity = _make_number(mock_coordinator, name)
                assert entity._attr_native_max_value == 100
                return
        pytest.skip("All number registers have explicit 'max'")

    def test_step_defaults_to_one(self, mock_coordinator):
        holding = mock_coordinator.get_register_map("holding_registers")
        for name, cfg in ENTITY_MAPPINGS["number"].items():
            if name in holding and "step" not in cfg:
                entity = _make_number(mock_coordinator, name)
                assert entity._attr_native_step == 1
                return
        pytest.skip("All number registers have explicit 'step'")

    def test_temperature_register_uses_thermometer_icon(self, mock_coordinator):
        holding = mock_coordinator.get_register_map("holding_registers")
        for name in ENTITY_MAPPINGS["number"]:
            if name in holding and "temperature" in name:
                entity = _make_number(mock_coordinator, name)
                assert entity._attr_icon == "mdi:thermometer"
                return
        pytest.skip("No temperature number register found")

    @pytest.mark.parametrize(
        "register_name,cfg",
        [
            (k, v)
            for k, v in ENTITY_MAPPINGS["number"].items()
            if v.get("min") is not None and v.get("max") is not None
        ][:10],
    )
    def test_explicit_min_max_applied(self, mock_coordinator, register_name, cfg):
        holding = mock_coordinator.get_register_map("holding_registers")
        if register_name not in holding:
            pytest.skip(f"{register_name} not in holding_registers")
        entity = _make_number(mock_coordinator, register_name)
        assert entity._attr_native_min_value == cfg["min"]
        assert entity._attr_native_max_value == cfg["max"]
