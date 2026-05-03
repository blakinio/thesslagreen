from __future__ import annotations

import pytest
from custom_components.thessla_green_modbus.binary_sensor import ThesslaGreenBinarySensor
from custom_components.thessla_green_modbus.mappings import BINARY_SENSOR_ENTITY_MAPPINGS


class TestBinarySensorIsOn:
    @pytest.mark.parametrize("raw,expected", [(True, True), (False, False), (1, True), (0, False)])
    def test_coil_register_direct_bool(self, mock_coordinator, raw, expected):
        sensor_def = {"translation_key": "power_supply_fans", "icon": "mdi:fan", "register_type": "coil_registers"}
        mock_coordinator.data = {"power_supply_fans": raw}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "power_supply_fans", 4, sensor_def)
        assert entity.is_on == expected

    @pytest.mark.parametrize("raw,expected", [(True, True), (False, False), (1, True), (0, False)])
    def test_discrete_input_direct_bool(self, mock_coordinator, raw, expected):
        sensor_def = {"translation_key": "expansion", "icon": "mdi:expansion-card", "register_type": "discrete_inputs"}
        mock_coordinator.data = {"expansion": raw}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "expansion", 5, sensor_def)
        assert entity.is_on == expected

    def test_holding_register_with_bit_set(self, mock_coordinator):
        bit = 0b00000100
        sensor_def = {"translation_key": "some_flag", "icon": "mdi:flag", "register_type": "holding_registers", "bit": bit}
        mock_coordinator.data = {"some_flag": bit}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "some_flag", 100, sensor_def)
        assert entity.is_on is True

    def test_holding_register_with_bit_clear(self, mock_coordinator):
        bit = 0b00000100
        sensor_def = {"translation_key": "some_flag", "icon": "mdi:flag", "register_type": "holding_registers", "bit": bit}
        mock_coordinator.data = {"some_flag": ~bit & 0xFFFF}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "some_flag", 100, sensor_def)
        assert entity.is_on is False

    def test_holding_register_without_bit_nonzero(self, mock_coordinator):
        sensor_def = {"translation_key": "flag", "icon": "mdi:flag", "register_type": "holding_registers"}
        mock_coordinator.data = {"flag": 7}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "flag", 100, sensor_def)
        assert entity.is_on is True

    def test_holding_register_without_bit_zero(self, mock_coordinator):
        sensor_def = {"translation_key": "flag", "icon": "mdi:flag", "register_type": "holding_registers"}
        mock_coordinator.data = {"flag": 0}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "flag", 100, sensor_def)
        assert entity.is_on is False

    def test_returns_none_when_data_key_missing(self, mock_coordinator):
        sensor_def = {"translation_key": "power_supply_fans", "icon": "mdi:fan", "register_type": "coil_registers"}
        mock_coordinator.data = {}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "power_supply_fans", 4, sensor_def)
        assert entity.is_on is None

    def test_inverted_flag_flips_result(self, mock_coordinator):
        sensor_def = {"translation_key": "inv_flag", "icon": "mdi:flag", "register_type": "coil_registers", "inverted": True}
        mock_coordinator.data = {"inv_flag": True}
        entity = ThesslaGreenBinarySensor(mock_coordinator, "inv_flag", 100, sensor_def)
        assert entity.is_on is False
        mock_coordinator.data = {"inv_flag": False}
        assert entity.is_on is True

    def test_all_binary_sensor_mappings_have_register_type(self):
        for key, defn in BINARY_SENSOR_ENTITY_MAPPINGS.items():
            assert "register_type" in defn, f"Missing register_type for binary sensor '{key}'"

    def test_all_binary_sensor_mappings_have_translation_key(self):
        for key, defn in BINARY_SENSOR_ENTITY_MAPPINGS.items():
            assert "translation_key" in defn, f"Missing translation_key for binary sensor '{key}'"
