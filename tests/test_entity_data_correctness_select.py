from __future__ import annotations

import pytest
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect

from tests.helpers_entity_data_correctness import _make_select


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
        name = "mode"
        mock_coordinator.data[name] = 1
        entity = _make_select(mock_coordinator, name)
        assert entity.current_option == "manual"

    def test_current_option_first_value(self, mock_coordinator):
        name = "mode"
        mock_coordinator.data[name] = 0
        entity = _make_select(mock_coordinator, name)
        assert entity.current_option == "auto"

    def test_current_option_last_value(self, mock_coordinator):
        name = "mode"
        mock_coordinator.data[name] = 2
        entity = _make_select(mock_coordinator, name)
        assert entity.current_option == "temporary"

    def test_current_option_none_when_key_missing(self, mock_coordinator):
        name = "mode"
        mock_coordinator.data.pop(name, None)
        entity = _make_select(mock_coordinator, name)
        assert entity.current_option is None

    def test_current_option_none_for_unknown_value(self, mock_coordinator):
        name = "mode"
        mock_coordinator.data[name] = 999
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
