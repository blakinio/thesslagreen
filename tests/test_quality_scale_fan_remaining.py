# mypy: ignore-errors
"""Exercise remaining fan lifecycle, optimistic-state, and write branches."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus import fan as fan_module
from custom_components.thessla_green_modbus.fan import ThesslaGreenFan
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pymodbus.exceptions import ConnectionException


@pytest.mark.asyncio
async def test_fan_setup_cancelled_add_retries_without_initial_state() -> None:
    coordinator = SimpleNamespace(
        device_client=SimpleNamespace(
            available_registers={"holding_registers": {"air_flow_rate_manual"}, "input_registers": set()}
        )
    )
    entry = SimpleNamespace(runtime_data=coordinator)
    add = Mock(side_effect=[asyncio.CancelledError(), None])
    await fan_module.async_setup_entry(SimpleNamespace(), entry, add)
    assert add.call_count == 2
    assert add.call_args_list[0].args[1] is True
    assert add.call_args_list[1].args[1] is False


@pytest.mark.asyncio
async def test_fan_setup_skips_when_no_control_registers() -> None:
    coordinator = SimpleNamespace(
        device_client=SimpleNamespace(
            available_registers={"holding_registers": set(), "input_registers": set()}
        )
    )
    add = Mock()
    await fan_module.async_setup_entry(
        SimpleNamespace(), SimpleNamespace(runtime_data=coordinator), add
    )
    add.assert_not_called()


def test_fan_pending_percentage_expiry_confirmation_and_ha_push(mock_coordinator) -> None:
    fan = ThesslaGreenFan(mock_coordinator)
    fan._pending_percentage = 70
    fan._pending_percentage_ts = 0.0
    with patch.object(fan_module, "monotonic", return_value=100.0):
        assert fan._pending_percentage_value() is None
    assert fan._pending_percentage is None

    fan._pending_percentage = 70
    mock_coordinator.data["exhaust_percentage"] = 71
    mock_coordinator.data.pop("supply_percentage", None)
    fan._clear_pending_if_confirmed()
    assert fan._pending_percentage is None

    fan._pending_percentage = 70
    mock_coordinator.data["exhaust_percentage"] = 90
    fan._clear_pending_if_confirmed()
    assert fan._pending_percentage == 70

    fan._pending_percentage = None
    fan._clear_pending_if_confirmed()

    state_write = Mock()
    fan.hass = SimpleNamespace()
    with patch.object(fan, "async_write_ha_state", state_write):
        fan._set_pending_percentage(55)
    state_write.assert_called_once()
    assert fan._pending_percentage == 55


def test_fan_status_and_mode_fallback_paths(mock_coordinator) -> None:
    fan = ThesslaGreenFan(mock_coordinator)
    mock_coordinator.data.pop("supply_percentage", None)
    mock_coordinator.data["exhaust_percentage"] = 44
    assert fan._confirmed_status_flow_rate() == 44.0

    mock_coordinator.data.pop("exhaust_percentage", None)
    mock_coordinator.data["mode"] = 2
    mock_coordinator.data["air_flow_rate_temporary_2"] = 66
    assert fan._get_current_flow_rate() == 66.0

    mock_coordinator.data.pop("air_flow_rate_temporary_2", None)
    mock_coordinator.data["air_flow_rate_manual"] = 33
    assert fan._get_current_flow_rate() == 33.0

    mock_coordinator.data["mode"] = 999
    assert fan._get_current_mode() is None


def test_fan_write_path_validation_shortcuts_and_auto_failure(mock_coordinator) -> None:
    fan = ThesslaGreenFan(mock_coordinator)
    fan._validate_percentage_write_path(0)
    mock_coordinator.data["mode"] = 2
    fan._validate_percentage_write_path(50)

    mock_coordinator.data["mode"] = 0
    mock_coordinator.device_client.available_registers["holding_registers"].discard(
        "air_flow_rate_temporary_2"
    )
    with pytest.raises(ServiceValidationError, match="unavailable"):
        fan._validate_percentage_write_path(50)


@pytest.mark.asyncio
async def test_fan_turn_on_negative_and_default_paths(mock_coordinator) -> None:
    fan = ThesslaGreenFan(mock_coordinator)
    with pytest.raises(ServiceValidationError, match="greater than or equal"):
        await fan.async_turn_on(percentage=-1)

    fan._validate_percentage_write_path = Mock()
    fan._is_writable_holding_register = Mock(return_value=False)
    fan.async_set_percentage = AsyncMock()
    await fan.async_turn_on()
    fan.async_set_percentage.assert_awaited_once_with(fan_module.FAN_DEFAULT_PERCENT)


@pytest.mark.asyncio
async def test_fan_temporary_write_exception_and_auto_unavailable(mock_coordinator) -> None:
    fan = ThesslaGreenFan(mock_coordinator)
    mock_coordinator.data["mode"] = 2
    mock_coordinator.async_write_temporary_airflow = AsyncMock(
        side_effect=ConnectionException("offline")
    )
    with pytest.raises(HomeAssistantError, match="temporary fan airflow"):
        await fan.async_set_percentage(70)

    mock_coordinator.data["mode"] = 0
    fan._is_writable_holding_register = Mock(return_value=False)
    with pytest.raises(ServiceValidationError, match="Temporary fan speed control"):
        await fan.async_set_percentage(70)


@pytest.mark.asyncio
async def test_fan_write_register_offset_exception_rejection_and_refresh(mock_coordinator) -> None:
    fan = ThesslaGreenFan(mock_coordinator)
    mock_coordinator.device_client.available_registers["holding_registers"].add(
        "air_flow_rate_manual"
    )

    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    mock_coordinator.async_request_refresh = AsyncMock()
    await fan._write_register("air_flow_rate_manual", 50, offset=2, refresh=True)
    mock_coordinator.async_write_register.assert_awaited_once_with(
        "air_flow_rate_manual", 50, refresh=False, targeted_readback=False, offset=2
    )
    mock_coordinator.async_request_refresh.assert_awaited_once()

    mock_coordinator.async_write_register = AsyncMock(side_effect=RuntimeError("fail"))
    with pytest.raises(HomeAssistantError, match="Failed to write fan register"):
        await fan._write_register("air_flow_rate_manual", 50)

    mock_coordinator.async_write_register = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await fan._write_register("air_flow_rate_manual", 50)


def test_fan_extra_attributes_all_optional_status_paths(mock_coordinator) -> None:
    now = datetime.now(UTC)
    mock_coordinator.data = {
        "supply_flow_rate": 100,
        "exhaust_flow_rate": 90,
        "supply_percentage": 50,
        "exhaust_percentage": 45,
        "mode": 1,
        "power_supply_fans": True,
        "boost_mode": True,
        "eco_mode": True,
        "on_off_panel_mode": 1,
    }
    mock_coordinator.device_client.statistics["last_successful_update"] = now
    fan = ThesslaGreenFan(mock_coordinator)
    attrs = fan.extra_state_attributes
    assert attrs["supply_flow"] == 100
    assert attrs["exhaust_flow"] == 90
    assert attrs["supply_percentage"] == 50
    assert attrs["exhaust_percentage"] == 45
    assert attrs["operating_mode"] == "manual"
    assert attrs["system_status"] == ["fans_powered", "boost_active", "eco_active"]
    assert attrs["last_updated"] == now.isoformat()
