"""Coordinator post-processing and power estimation tests."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)


@pytest.fixture
def coordinator():
    """Create a test coordinator."""
    hass = MagicMock()
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="localhost",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=10,
        retry=3,
    )


def test_post_process_data(coordinator):
    raw_data = {
        "outside_temperature": 100,
        "supply_temperature": 200,
        "exhaust_temperature": 250,
        "supply_flow_rate": 150,
        "exhaust_flow_rate": 140,
        "dac_supply": 5.0,
        "dac_exhaust": 4.0,
    }
    fake_now = datetime(2024, 1, 1, 12, 0, 0)
    coordinator._last_power_timestamp = fake_now - timedelta(hours=1)
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator.dt_util.utcnow",
        return_value=fake_now,
    ):
        processed_data = coordinator._post_process_data(raw_data)

    assert "calculated_efficiency" in processed_data
    assert isinstance(processed_data["calculated_efficiency"], int | float)
    assert 0 <= processed_data["calculated_efficiency"] <= 100
    assert processed_data["flow_balance"] == 10
    assert processed_data["flow_balance_status"] == "supply_dominant"
    assert processed_data["estimated_power"] > 0
    assert processed_data["total_energy"] > 0
    assert (
        processed_data["heat_recovery_efficiency"]
        == processed_data["calculated_efficiency"]
    )
    assert processed_data["heat_recovery_power"] >= 0
    assert processed_data["electrical_power"] == processed_data["estimated_power"]


def test_lookup_model_power_exact(coordinator):
    assert coordinator._lookup_model_power(300) == (105.0, 1150.0)
    assert coordinator._lookup_model_power(400) == (170.0, 1500.0)
    assert coordinator._lookup_model_power(420) == (94.0, 1449.0)
    assert coordinator._lookup_model_power(500) == (255.0, 1850.0)
    assert coordinator._lookup_model_power(550) == (345.0, 1950.0)


def test_lookup_model_power_within_tolerance(coordinator):
    assert coordinator._lookup_model_power(430) == (94.0, 1449.0)


def test_lookup_model_power_unknown(coordinator):
    assert coordinator._lookup_model_power(200) is None
    assert coordinator._lookup_model_power(700) is None


def test_calculate_power_model_aware(coordinator):
    power = coordinator.calculate_power_consumption(
        {
            "nominal_supply_air_flow": 420,
            "supply_flow_rate": 420,
            "exhaust_flow_rate": 420,
            "dac_heater": 0.0,
        }
    )
    assert power == pytest.approx(104.0, abs=0.5)


def test_calculate_power_partial_flow(coordinator):
    power = coordinator.calculate_power_consumption(
        {
            "nominal_supply_air_flow": 420,
            "supply_flow_rate": 210,
            "exhaust_flow_rate": 210,
            "dac_heater": 0.0,
        }
    )
    assert power == pytest.approx(21.75, abs=0.5)


def test_calculate_power_with_heater(coordinator):
    power = coordinator.calculate_power_consumption(
        {
            "nominal_supply_air_flow": 420,
            "supply_flow_rate": 420,
            "exhaust_flow_rate": 420,
            "dac_heater": 5.0,
        }
    )
    assert power == pytest.approx(828.5, abs=1.0)


def test_calculate_power_standby_always_included(coordinator):
    power = coordinator.calculate_power_consumption(
        {
            "nominal_supply_air_flow": 420,
            "supply_flow_rate": 0,
            "exhaust_flow_rate": 0,
            "dac_heater": 0.0,
        }
    )
    assert power == pytest.approx(10.0, abs=0.1)


def test_calculate_power_fallback_dac(coordinator):
    power = coordinator.calculate_power_consumption({"dac_supply": 10.0, "dac_exhaust": 10.0})
    assert power == pytest.approx(160.0, abs=1.0)


def test_calculate_power_fallback_missing_dac(coordinator):
    assert coordinator.calculate_power_consumption({}) is None
