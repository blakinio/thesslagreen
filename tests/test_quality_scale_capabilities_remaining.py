# mypy: ignore-errors
"""Exercise remaining capability and derived-metric fallbacks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from custom_components.thessla_green_modbus.core.capabilities_mixin import (
    _clamp_percentage,
    _coerce_bypass_open,
    _CoordinatorCapabilitiesMixin,
    _flow_balance_status,
    _normalise_capability_flag,
)


def _owner():
    owner = _CoordinatorCapabilitiesMixin()
    owner.device_client = SimpleNamespace(device_info={})
    owner.device_info = {}
    return owner


def test_capability_pure_helpers_and_disabled_apply() -> None:
    assert _clamp_percentage(-5) == 0
    assert _clamp_percentage(105) == 100
    assert _flow_balance_status(0) == "balanced"
    assert _flow_balance_status(20) == "supply_dominant"
    assert _flow_balance_status(-20) == "exhaust_dominant"
    assert _coerce_bypass_open(1) is True
    assert _coerce_bypass_open(0) is False
    assert _normalise_capability_flag(None) is False
    assert _normalise_capability_flag(1) is True

    data = {}
    owner = _owner()
    assert owner._apply_capability_result(data, "x", 1, False) is False
    assert data == {}
    assert owner._apply_capability_result(data, "x", 1, True) is True
    assert data["x"] == 1


def test_efficiency_early_returns_flow_paths_and_error_fallbacks() -> None:
    owner = _owner()
    assert owner._calculate_heat_recovery_efficiency({"bypass_mode": 1}) is None
    assert owner._calculate_heat_recovery_efficiency({}) is None
    assert owner._calculate_heat_recovery_efficiency(
        {"outside_temperature": 10, "supply_temperature": 15, "exhaust_temperature": 14}
    ) is None
    assert owner._calculate_heat_recovery_efficiency(
        {
            "outside_temperature": 0,
            "supply_temperature": 10,
            "exhaust_temperature": 20,
            "supply_flow_rate": 0,
            "exhaust_flow_rate": 10,
        }
    ) == 50

    data = {
        "outside_temperature": "bad",
        "supply_temperature": 10,
        "exhaust_temperature": 20,
        "supply_flow_rate": "bad",
        "exhaust_flow_rate": 10,
    }
    owner._apply_post_process_derived_values(data)
    assert "calculated_efficiency" not in data

    data = {"supply_flow_rate": "bad", "outside_temperature": 0, "supply_temperature": 10}
    owner._apply_post_process_derived_values(data)
    assert "heat_recovery_power" not in data

    data = {"supply_flow_rate": "bad", "exhaust_flow_rate": 10}
    owner._apply_post_process_derived_values(data)
    assert "flow_balance" not in data


def test_device_clock_missing_invalid_and_valid_paths() -> None:
    owner = _owner()
    assert owner._decode_device_clock({}) is None
    assert owner._decode_device_clock(
        {"date_time": 0x2600, "date_time_ddtt": 0x0000, "date_time_ggmm": 0x2500, "date_time_sscc": 0}
    ) is None
    assert owner._decode_device_clock(
        {"date_time": 0x2608, "date_time_ddtt": 0x1200, "date_time_ggmm": 0x1930, "date_time_sscc": 0x4500}
    ) == "2026-08-12T19:30:45"


def test_model_lookup_power_flow_fallback_and_dac_paths() -> None:
    owner = _owner()
    assert owner._lookup_model_power(300) is not None
    assert owner._lookup_model_power(999) is None

    assert owner.calculate_power_consumption(
        {
            "nominal_supply_air_flow": 300,
            "supply_flow_rate": 150,
            "exhaust_flow_rate": 150,
            "dac_heater": 5,
        }
    ) is not None

    assert owner.calculate_power_consumption(
        {
            "nominal_supply_air_flow": "bad",
            "supply_flow_rate": 100,
            "exhaust_flow_rate": 100,
            "dac_supply": 5,
            "dac_exhaust": 5,
            "dac_heater": 5,
            "dac_cooler": 5,
        }
    ) is not None
    assert owner.calculate_power_consumption({}) is None


def test_post_process_serial_power_and_clock_exception_paths() -> None:
    owner = _owner()
    owner.device_client.device_info = {"serial_number": "ABC"}
    data = {"dac_supply": 0, "dac_exhaust": 0}
    with patch.object(owner, "_decode_device_clock", side_effect=TypeError("bad clock")):
        result = owner._post_process_data(data)
    assert result["serial_number"] == "ABC"
    assert result["electrical_power"] == 0.0
    assert "device_clock" not in result

    owner.device_client.device_info = {"serial_number": "Unknown"}
    data = {}
    owner._apply_serial_number_state(data)
    assert "serial_number" not in data
