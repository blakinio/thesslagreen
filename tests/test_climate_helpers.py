"""Focused unit tests for climate helper functions."""

from custom_components.thessla_green_modbus import climate
from homeassistant.components.climate import HVACMode


def test_first_numeric_uses_first_match() -> None:
    data = {"required_temperature": "bad", "comfort_temperature": 21, "required_temp": 22}
    assert climate._first_numeric(data, climate.TEMPERATURE_KEYS) == 21.0


def test_hvac_mode_from_data_respects_panel_off() -> None:
    assert climate._hvac_mode_from_data({"on_off_panel_mode": 0, "mode": 1}) == HVACMode.OFF


def test_special_mode_from_preset_none() -> None:
    assert climate._special_mode_from_preset("none") == 0


def test_extra_state_attributes_defaults() -> None:
    attrs = climate._extra_state_attributes({})
    assert attrs["bypass_active"] is False
    assert attrs["gwc_active"] is False
    assert attrs["heating_active"] is False
