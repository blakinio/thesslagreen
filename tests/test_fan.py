"""Tests for ThesslaGreenFan entity."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus.fan import ThesslaGreenFan
from custom_components.thessla_green_modbus.modbus_exceptions import ConnectionException


def test_fan_creation_and_state(mock_coordinator):
    """Test creation and basic state reporting of fan entity."""
    mock_coordinator.data["supply_percentage"] = 50
    mock_coordinator.data["on_off_panel_mode"] = 1
    fan = ThesslaGreenFan(mock_coordinator)
    assert fan.speed_count == 10
    assert fan.is_on is True
    assert fan.percentage == 50

    mock_coordinator.data["supply_percentage"] = 0
    assert fan.is_on is False
    assert fan.percentage == 0


def test_flow_rate_uses_supply_flow_rate(mock_coordinator):
    """Ensure supply_flow_rate is used when other registers unavailable."""
    mock_coordinator.data.pop("supply_percentage", None)
    mock_coordinator.data["supply_flow_rate"] = 80
    fan = ThesslaGreenFan(mock_coordinator)
    assert fan._get_current_flow_rate() == 80.0
    assert fan.percentage == 80
    assert fan.is_on is True


def test_fan_turn_on_modbus_failure(mock_coordinator):
    """Ensure connection errors during turn on are raised."""
    fan = ThesslaGreenFan(mock_coordinator)
    mock_coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("fail"))
    with pytest.raises(ConnectionException):
        asyncio.run(fan.async_turn_on(percentage=40))


def test_fan_set_percentage_failure(mock_coordinator):
    """Ensure write failures surface as runtime errors."""
    mock_coordinator.data["mode"] = 1  # manual mode to force write
    fan = ThesslaGreenFan(mock_coordinator)
    mock_coordinator.async_write_register = AsyncMock(return_value=False)
    with pytest.raises(RuntimeError):
        asyncio.run(fan.async_set_percentage(60))


def test_fan_temporary_mode_uses_multi_write(mock_coordinator):
    """Temporary mode must use the 3-register airflow write block."""
    mock_coordinator.data["mode"] = 2
    mock_coordinator.async_write_temporary_airflow = AsyncMock(return_value=True)
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    mock_coordinator.async_request_refresh = AsyncMock()
    fan = ThesslaGreenFan(mock_coordinator)

    asyncio.run(fan.async_set_percentage(70))

    mock_coordinator.async_write_temporary_airflow.assert_awaited_once_with(70, refresh=False)
    mock_coordinator.async_write_register.assert_not_called()
    mock_coordinator.async_request_refresh.assert_awaited_once()


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


def test_fan_is_on_false_when_panel_mode_off(mock_coordinator):
    """is_on returns False immediately when on_off_panel_mode is 0 (line 103)."""
    mock_coordinator.data["on_off_panel_mode"] = 0
    mock_coordinator.data["supply_percentage"] = 50  # flow present but short-circuited
    fan = ThesslaGreenFan(mock_coordinator)
    assert fan.is_on is False  # nosec B101


def test_fan_is_on_none_when_no_flow_registers(mock_coordinator):
    """is_on returns None when no flow register is present in data (line 108)."""
    for key in [
        "supply_air_flow",
        "supply_flow_rate",
        "supply_percentage",
        "air_flow_rate_manual",
        "air_flow_rate_temporary_2",
    ]:
        mock_coordinator.data.pop(key, None)
    fan = ThesslaGreenFan(mock_coordinator)
    assert fan.is_on is None  # nosec B101


def test_fan_percentage_none_when_no_flow_registers(mock_coordinator):
    """percentage returns None when no flow register is present (line 117)."""
    for key in [
        "supply_air_flow",
        "supply_flow_rate",
        "supply_percentage",
        "air_flow_rate_manual",
        "air_flow_rate_temporary_2",
    ]:
        mock_coordinator.data.pop(key, None)
    fan = ThesslaGreenFan(mock_coordinator)
    assert fan.percentage is None  # nosec B101


def test_fan_get_current_flow_rate_none(mock_coordinator):
    """_get_current_flow_rate returns None when all flow registers absent (line 158)."""
    for key in [
        "supply_air_flow",
        "supply_flow_rate",
        "supply_percentage",
        "air_flow_rate_manual",
        "air_flow_rate_temporary_2",
    ]:
        mock_coordinator.data.pop(key, None)
    fan = ThesslaGreenFan(mock_coordinator)
    assert fan._get_current_flow_rate() is None  # nosec B101


def test_fan_percentage_limits_max_below_min(mock_coordinator):
    """When max_percentage < min_percentage, max_val is clamped to min_val (line 138)."""
    mock_coordinator.data["min_percentage"] = 80
    mock_coordinator.data["max_percentage"] = 20
    fan = ThesslaGreenFan(mock_coordinator)
    min_v, max_v = fan._percentage_limits()
    assert max_v == min_v == 80  # nosec B101


def test_fan_turn_off_success(mock_coordinator):
    """async_turn_off writes 0 to on_off_panel_mode when available (lines 188-193)."""
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    mock_coordinator.async_request_refresh = AsyncMock()
    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan.async_turn_off())
    mock_coordinator.async_write_register.assert_awaited_once()
    call_args = mock_coordinator.async_write_register.call_args
    assert call_args[0][0] == "on_off_panel_mode"  # nosec B101
    assert call_args[0][1] == 0  # nosec B101
    assert mock_coordinator.data["on_off_panel_mode"] == 0  # nosec B101


def test_fan_turn_off_via_airflow_register(mock_coordinator):
    """When on_off_panel_mode unavailable, turn off via air_flow_rate_manual (lines 194-204)."""
    mock_coordinator.data["mode"] = 1  # manual mode
    mock_coordinator.available_registers["holding_registers"].discard("on_off_panel_mode")
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    mock_coordinator.async_request_refresh = AsyncMock()
    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan.async_turn_off())
    mock_coordinator.async_write_register.assert_awaited_once()
    call_args = mock_coordinator.async_write_register.call_args
    assert call_args[0][0] == "air_flow_rate_manual"  # nosec B101
    assert call_args[0][1] == 0  # nosec B101


def test_fan_turn_off_exception_reraise(mock_coordinator):
    """async_turn_off re-raises ConnectionException (lines 208-210)."""
    mock_coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("fail"))
    fan = ThesslaGreenFan(mock_coordinator)
    with pytest.raises(ConnectionException):
        asyncio.run(fan.async_turn_off())


def test_fan_set_percentage_negative_rejected(mock_coordinator):
    """Negative percentage is rejected without writing anything (lines 215-217)."""
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan.async_set_percentage(-1))
    mock_coordinator.async_write_register.assert_not_called()


def test_fan_set_percentage_zero_calls_turn_off(mock_coordinator):
    """Percentage 0 triggers async_turn_off (lines 221-224)."""
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    mock_coordinator.async_request_refresh = AsyncMock()
    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan.async_set_percentage(0))
    # turn_off should have written 0 to on_off_panel_mode
    mock_coordinator.async_write_register.assert_awaited_once()
    assert mock_coordinator.async_write_register.call_args[0][1] == 0  # nosec B101


def test_fan_set_percentage_temporary_fail_raises(mock_coordinator):
    """Temporary airflow write failure raises RuntimeError (line 248)."""
    mock_coordinator.data["mode"] = 2  # temporary mode
    mock_coordinator.async_write_temporary_airflow = AsyncMock(return_value=False)
    fan = ThesslaGreenFan(mock_coordinator)
    with pytest.raises(RuntimeError):
        asyncio.run(fan.async_set_percentage(70))


def test_fan_set_percentage_auto_mode_uses_temporary_register(mock_coordinator, monkeypatch):
    """In auto mode with air_flow_rate_temporary_2 available, write to it (lines 251-255)."""
    from custom_components.thessla_green_modbus import fan as fan_module

    mock_coordinator.data["mode"] = 0  # auto mode
    mock_coordinator.available_registers["holding_registers"].add("air_flow_rate_temporary_2")
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    mock_coordinator.async_request_refresh = AsyncMock()

    original = fan_module.holding_registers()
    patched = {**original, "air_flow_rate_temporary_2": 999}
    monkeypatch.setattr(fan_module, "holding_registers", lambda: patched)

    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan.async_set_percentage(60))

    register_names = [c[0][0] for c in mock_coordinator.async_write_register.call_args_list]
    assert "air_flow_rate_temporary_2" in register_names  # nosec B101


def test_fan_get_current_mode_auto(mock_coordinator):
    """_get_current_mode returns 'auto' when mode register is 0 (line 268)."""
    mock_coordinator.data["mode"] = 0
    fan = ThesslaGreenFan(mock_coordinator)
    assert fan._get_current_mode() == "auto"  # nosec B101


def test_fan_get_current_mode_none_when_absent(mock_coordinator):
    """_get_current_mode returns None when mode key is absent (line 273)."""
    mock_coordinator.data.pop("mode", None)
    fan = ThesslaGreenFan(mock_coordinator)
    assert fan._get_current_mode() is None  # nosec B101


def test_fan_write_register_invalid_raises(mock_coordinator):
    """_write_register raises ValueError for unknown register names (line 278)."""
    fan = ThesslaGreenFan(mock_coordinator)
    with pytest.raises(ValueError):
        asyncio.run(fan._write_register("nonexistent_xyz_register_99", 1))


def test_fan_write_register_not_in_available_skips(mock_coordinator):
    """_write_register skips write when register not in available_registers (lines 281-283)."""
    mock_coordinator.available_registers["holding_registers"].discard("air_flow_rate_manual")
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    fan = ThesslaGreenFan(mock_coordinator)
    asyncio.run(fan._write_register("air_flow_rate_manual", 50))
    mock_coordinator.async_write_register.assert_not_called()
