"""Split coordinator coverage tests by behavior area."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator


def _make_coordinator(**kwargs) -> ThesslaGreenModbusCoordinator:
    hass = MagicMock()
    hass.async_add_executor_job = None
    return ThesslaGreenModbusCoordinator.from_params(
        hass=hass,
        host="192.168.1.1",
        port=502,
        slave_id=1,
        name="test",
        scan_interval=30,
        timeout=3,
        retry=2,
        **kwargs,
    )


def test_calculate_power_consumption_basic():
    """calculate_power_consumption returns float when dac_supply/exhaust provided."""
    coord = _make_coordinator()
    data = {"dac_supply": 5.0, "dac_exhaust": 5.0}
    result = coord.calculate_power_consumption(data)
    assert result is not None
    assert isinstance(result, float)
    assert result > 0

def test_calculate_power_consumption_with_heater_and_cooler():
    """Heater and cooler voltages contribute to power (lines 1876-1879)."""
    coord = _make_coordinator()
    data = {"dac_supply": 8.0, "dac_exhaust": 7.0, "dac_heater": 5.0, "dac_cooler": 3.0}
    result = coord.calculate_power_consumption(data)
    assert result is not None
    assert result > 0

def test_calculate_power_consumption_missing_keys_returns_none():
    """KeyError on missing dac_supply/exhaust returns None (lines 1861-1862)."""
    coord = _make_coordinator()
    result = coord.calculate_power_consumption({})
    assert result is None

def test_calculate_power_consumption_invalid_type_returns_none():
    """TypeError on non-numeric values returns None."""
    coord = _make_coordinator()
    result = coord.calculate_power_consumption({"dac_supply": "bad", "dac_exhaust": 5.0})
    assert result is None


# ---------------------------------------------------------------------------
# Group O — _post_process_data branches (lines 1883-1925)
# ---------------------------------------------------------------------------

def test_post_process_data_zero_division_error():
    """ZeroDivisionError when exhaust == outside is caught silently (lines 1894-1898)."""
    coord = _make_coordinator()
    data = {
        "outside_temperature": 20.0,
        "supply_temperature": 22.0,
        "exhaust_temperature": 20.0,  # Same as outside → ZeroDivisionError
    }
    result = coord._post_process_data(data)
    # Should not raise; calculated_efficiency is absent
    assert "calculated_efficiency" not in result

def test_post_process_data_efficiency_calculated():
    """Heat recovery efficiency is calculated when temperatures differ."""
    coord = _make_coordinator()
    data = {
        "outside_temperature": 0.0,
        "supply_temperature": 18.0,
        "exhaust_temperature": 20.0,
    }
    result = coord._post_process_data(data)
    assert "calculated_efficiency" in result
    assert 0 <= result["calculated_efficiency"] <= 100

def test_post_process_data_flow_balance():
    """Flow balance is calculated from supply and exhaust flow rates."""
    coord = _make_coordinator()
    data = {"supply_flow_rate": 100, "exhaust_flow_rate": 75}
    result = coord._post_process_data(data)
    assert result["flow_balance"] == 25
    assert result["flow_balance_status"] == "supply_dominant"

def test_post_process_data_flow_balance_exhaust_dominant():
    """Flow balance status is exhaust_dominant when exhaust > supply."""
    coord = _make_coordinator()
    data = {"supply_flow_rate": 80, "exhaust_flow_rate": 100}
    result = coord._post_process_data(data)
    assert result["flow_balance_status"] == "exhaust_dominant"

def test_post_process_data_flow_balance_balanced():
    """Flow balance status is balanced when diff < 10."""
    coord = _make_coordinator()
    data = {"supply_flow_rate": 100, "exhaust_flow_rate": 98}
    result = coord._post_process_data(data)
    assert result["flow_balance_status"] == "balanced"

def test_post_process_data_flow_balance_string_values():
    """flow_balance must not crash when register returns a string value."""
    coord = _make_coordinator()
    data = {"supply_flow_rate": "invalid", "exhaust_flow_rate": 75}
    result = coord._post_process_data(data)
    # Should silently skip — no crash, no flow_balance key
    assert "flow_balance" not in result

def test_post_process_data_power_calculation():
    """Power is estimated and energy accumulated when DAC values provided."""
    coord = _make_coordinator()
    data = {"dac_supply": 5.0, "dac_exhaust": 5.0}
    result = coord._post_process_data(data)
    assert "estimated_power" in result
    assert "total_energy" in result

def test_post_process_data_timezone_aware_timestamp():
    """Timezone-aware last timestamp is handled correctly (lines 1916-1919)."""
    coord = _make_coordinator()
    # Set a timezone-aware last timestamp
    coord._last_power_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    data = {"dac_supply": 3.0, "dac_exhaust": 3.0}
    result = coord._post_process_data(data)
    assert "estimated_power" in result


# ---------------------------------------------------------------------------
# Group R — async_write_temporary_* (lines 2320-2366)
# ---------------------------------------------------------------------------

def test_post_process_data_type_error_in_efficiency():
    """TypeError in efficiency calculation is caught (lines 1897-1898)."""
    coord = _make_coordinator()
    data = {
        "outside_temperature": "not_a_number",  # triggers TypeError
        "supply_temperature": 20.0,
        "exhaust_temperature": 25.0,
    }
    result = coord._post_process_data(data)
    assert "calculated_efficiency" not in result

def test_post_process_data_non_datetime_last_timestamp():
    """Non-datetime _last_power_timestamp → elapsed=0.0 (line 1914)."""
    coord = _make_coordinator()
    coord._last_power_timestamp = "not_a_datetime"
    data = {"dac_supply": 3.0, "dac_exhaust": 3.0}
    result = coord._post_process_data(data)
    assert "estimated_power" in result
    assert "total_energy" in result

def test_post_process_data_naive_now_aware_last_ts():
    """Naive _utcnow with aware last_ts → adds UTC tz to now (line 1919)."""
    coord = _make_coordinator()
    coord._last_power_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    # Patch _utcnow to return naive datetime
    with patch(
        "custom_components.thessla_green_modbus.coordinator.coordinator._utcnow",
        return_value=datetime(2024, 1, 1, 12, 0, 30),  # naive
    ):
        data = {"dac_supply": 3.0, "dac_exhaust": 3.0}
        result = coord._post_process_data(data)
    assert "estimated_power" in result

