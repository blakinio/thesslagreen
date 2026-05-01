"""Focused tests for extracted static mapping groups."""

from custom_components.thessla_green_modbus.mappings._static_sensor_temperatures import (
    HOLDING_TEMPERATURE_SENSOR_MAPPINGS,
    INPUT_TEMPERATURE_SENSOR_MAPPINGS,
)
from custom_components.thessla_green_modbus.mappings._static_sensors import SENSOR_ENTITY_MAPPINGS


def test_input_temperature_group_keys_stable() -> None:
    assert set(INPUT_TEMPERATURE_SENSOR_MAPPINGS) == {
        "outside_temperature",
        "supply_temperature",
        "exhaust_temperature",
        "fpx_temperature",
        "duct_supply_temperature",
        "gwc_temperature",
        "ambient_temperature",
        "heating_temperature",
    }


def test_holding_temperature_group_keys_stable() -> None:
    assert set(HOLDING_TEMPERATURE_SENSOR_MAPPINGS) == {
        "supply_air_temperature_manual",
        "min_bypass_temperature",
        "air_temperature_summer_free_heating",
        "air_temperature_summer_free_cooling",
        "required_temperature",
    }


def test_extracted_group_payloads_match_exported_sensor_mappings() -> None:
    for key, payload in {
        **INPUT_TEMPERATURE_SENSOR_MAPPINGS,
        **HOLDING_TEMPERATURE_SENSOR_MAPPINGS,
    }.items():
        assert SENSOR_ENTITY_MAPPINGS[key] == payload
