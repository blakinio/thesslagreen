# mypy: ignore-errors
"""Exercise remaining climate state, validation, and write branches."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate, async_setup_entry
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from homeassistant import const
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pymodbus.exceptions import ConnectionException


def _make_climate(data=None):
    coordinator = ThesslaGreenModbusCoordinator.from_params(
        SimpleNamespace(), "host", 502, 10, "dev", timedelta(seconds=30)
    )
    coordinator.data = dict(data or {})
    coordinator.last_update_success = True
    coordinator.async_write_register = AsyncMock(return_value=True)
    coordinator.async_write_temporary_temperature = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()
    coordinator.device_client.available_registers = {
        "holding_registers": set(),
        "input_registers": set(),
        "coil_registers": set(),
        "discrete_inputs": set(),
        "calculated": set(),
    }
    return ThesslaGreenClimate(coordinator), coordinator


@pytest.mark.asyncio
async def test_climate_setup_skips_unsupported_capability() -> None:
    coordinator = SimpleNamespace(
        device_client=SimpleNamespace(
            capabilities=SimpleNamespace(basic_control=False), device_name="unit"
        )
    )
    add_entities = Mock()
    await async_setup_entry(
        SimpleNamespace(), SimpleNamespace(runtime_data=coordinator), add_entities
    )
    add_entities.assert_not_called()


def test_climate_confirmed_and_optimistic_state_properties() -> None:
    climate, coordinator = _make_climate(
        {
            "ambient_temperature": 21,
            "required_temperature": 22,
            "on_off_panel_mode": 1,
            "mode": 0,
            "air_flow_rate_temporary_2": 34,
            "special_mode": 1,
        }
    )
    assert climate.current_temperature == 21.0
    assert climate.target_temperature == 22.0
    assert climate.hvac_mode == HVACMode.AUTO
    assert climate.fan_mode == "30%"
    assert climate.preset_mode == "boost"

    climate._optimistic.set_pending("target_temperature", 23.5)
    climate._optimistic.set_pending("hvac_mode", HVACMode.FAN_ONLY)
    climate._optimistic.set_pending("fan_mode", "70%")
    climate._optimistic.set_pending("preset_mode", "eco")
    assert climate.target_temperature == 23.5
    assert climate.hvac_mode == HVACMode.FAN_ONLY
    assert climate.fan_mode == "70%"
    assert climate.preset_mode == "eco"

    coordinator.data = {"min_percentage": 0, "max_percentage": -1}
    climate._optimistic = type(climate._optimistic)()
    assert climate._confirmed_fan_mode() is None
    # Percentage limits are normalized fail-safe to a non-negative singleton.
    assert climate.fan_modes == ["0%"]


def test_climate_hvac_action_all_runtime_states() -> None:
    climate, coordinator = _make_climate({"on_off_panel_mode": 0})
    assert climate.hvac_action == HVACAction.OFF

    coordinator.data = {"on_off_panel_mode": 1, "heating_cable": True}
    assert climate.hvac_action == HVACAction.HEATING
    coordinator.data = {"on_off_panel_mode": 1, "bypass": True}
    assert climate.hvac_action == HVACAction.COOLING
    coordinator.data = {"on_off_panel_mode": 1, "power_supply_fans": True}
    assert climate.hvac_action == HVACAction.FAN
    coordinator.data = {"on_off_panel_mode": 1}
    assert climate.hvac_action == HVACAction.IDLE


def test_climate_extra_attributes_include_optional_values() -> None:
    climate, _coordinator = _make_climate(
        {
            "bypass": True,
            "gwc": True,
            "heating_cable": True,
            "outside_temperature": 5,
            "humidity_indoor": 42,
        }
    )
    attrs = climate.extra_state_attributes
    assert attrs["bypass_active"] is True
    assert attrs["gwc_active"] is True
    assert attrs["heating_active"] is True
    assert attrs["outside_temperature"] == 5
    assert attrs["humidity"] == 42


@pytest.mark.asyncio
async def test_climate_write_compatibility_error_and_rejection_paths() -> None:
    climate, coordinator = _make_climate()
    coordinator.async_write_register = AsyncMock(side_effect=[TypeError("old signature"), True])
    await climate._write_register("required_temperature", 21, refresh=False)
    assert coordinator.async_write_register.await_count == 2

    coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("offline"))
    with pytest.raises(HomeAssistantError, match="Failed to write"):
        await climate._write_register("required_temperature", 21)

    coordinator.async_write_register = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await climate._write_register("required_temperature", 21)

    coordinator.async_write_register = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await climate._write_register("required_temperature", 21)


@pytest.mark.asyncio
async def test_climate_hvac_mode_validation_and_off_path() -> None:
    climate, coordinator = _make_climate()
    with pytest.raises(ServiceValidationError, match="Unsupported HVAC mode"):
        await climate.async_set_hvac_mode(HVACMode.HEAT)

    await climate.async_set_hvac_mode(HVACMode.OFF)
    coordinator.async_write_register.assert_awaited_with(
        "on_off_panel_mode", 0, refresh=False, offset=0, targeted_readback=False
    )
    coordinator.async_request_refresh.assert_awaited()


@pytest.mark.asyncio
async def test_climate_temperature_validation_and_temporary_failures() -> None:
    climate, coordinator = _make_climate({"mode": 2})
    await climate.async_set_temperature()
    coordinator.async_write_temporary_temperature.assert_not_awaited()

    with pytest.raises(ServiceValidationError, match="between"):
        await climate.async_set_temperature(**{const.ATTR_TEMPERATURE: 50})

    coordinator.async_write_temporary_temperature = AsyncMock(
        side_effect=ConnectionException("offline")
    )
    with pytest.raises(HomeAssistantError, match="temporary target"):
        await climate.async_set_temperature(**{const.ATTR_TEMPERATURE: 22})

    coordinator.async_write_temporary_temperature = AsyncMock(return_value=False)
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await climate.async_set_temperature(**{const.ATTR_TEMPERATURE: 22})

    coordinator.async_write_temporary_temperature = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await climate.async_set_temperature(**{const.ATTR_TEMPERATURE: 22})


@pytest.mark.asyncio
async def test_climate_temperature_writes_required_when_comfort_not_in_register_map() -> None:
    climate, coordinator = _make_climate({"mode": 0})
    coordinator.device_client.available_registers["holding_registers"].update(
        {"comfort_temperature", "required_temperature"}
    )
    await climate.async_set_temperature(**{const.ATTR_TEMPERATURE: 21.5})
    names = [call.args[0] for call in coordinator.async_write_register.await_args_list]
    # Availability alone must not invent a register absent from the canonical map.
    assert names == ["required_temperature"]


@pytest.mark.asyncio
async def test_climate_fan_and_preset_validation_and_commands() -> None:
    climate, _coordinator = _make_climate({"min_percentage": 20, "max_percentage": 80})
    with pytest.raises(ServiceValidationError, match="Invalid fan mode"):
        await climate.async_set_fan_mode("invalid")
    with pytest.raises(ServiceValidationError, match="between"):
        await climate.async_set_fan_mode("90%")

    await climate.async_set_fan_mode("40%")
    assert climate.fan_mode == "40%"

    with pytest.raises(ServiceValidationError, match="Unsupported preset"):
        await climate.async_set_preset_mode("invalid")
    await climate.async_set_preset_mode("none")
    assert climate.preset_mode == "none"


@pytest.mark.asyncio
async def test_climate_turn_on_off_and_availability() -> None:
    climate, coordinator = _make_climate({"mode": 99, "on_off_panel_mode": 1})
    assert climate.available is True
    await climate.async_turn_on()
    assert climate.hvac_mode == HVACMode.AUTO
    await climate.async_turn_off()
    assert climate.hvac_mode == HVACMode.OFF

    coordinator.last_update_success = False
    assert climate.available is False
    coordinator.last_update_success = True
    coordinator.data = {}
    assert climate.available is False
