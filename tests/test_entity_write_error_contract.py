"""Regression tests for writable-entity failure semantics."""

from __future__ import annotations

from datetime import time as dt_time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.exceptions import HomeAssistantError

from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
from custom_components.thessla_green_modbus.time import ThesslaGreenTime


@pytest.mark.asyncio
async def test_climate_false_write_raises_home_assistant_error(mock_coordinator) -> None:
    """A rejected climate write must not complete as a successful action."""
    mock_coordinator.async_write_register = AsyncMock(return_value=False)
    mock_coordinator.async_request_refresh = AsyncMock()
    climate = ThesslaGreenClimate(mock_coordinator)

    with pytest.raises(HomeAssistantError):
        await climate.async_set_hvac_mode(HVACMode.OFF)

    mock_coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_climate_partial_mode_write_surfaces_failure(mock_coordinator) -> None:
    """Failure of the second write in a multi-register command is explicit."""
    mock_coordinator.async_write_register = AsyncMock(side_effect=[True, False])
    mock_coordinator.async_request_refresh = AsyncMock()
    climate = ThesslaGreenClimate(mock_coordinator)

    with pytest.raises(HomeAssistantError):
        await climate.async_set_hvac_mode(HVACMode.AUTO)

    assert mock_coordinator.async_write_register.await_count == 2
    mock_coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_time_false_write_raises_home_assistant_error(mock_coordinator) -> None:
    """A rejected BCD time write must surface to Home Assistant."""
    definition = {
        "translation_key": "test_time",
        "register_type": "holding_registers",
    }
    entity = ThesslaGreenTime(mock_coordinator, "schedule_summer_mon_1", 16, definition)
    mock_coordinator.async_write_register = AsyncMock(return_value=False)

    with pytest.raises(HomeAssistantError):
        await entity.async_set_value(dt_time(8, 30))


@pytest.mark.asyncio
async def test_setup_paths_do_not_request_per_entity_initial_update(monkeypatch) -> None:
    """Representative read/write platforms reuse coordinator initial data."""
    from custom_components.thessla_green_modbus import binary_sensor, sensor, time

    coordinator = SimpleNamespace(
        device_client=SimpleNamespace(
            capabilities=SimpleNamespace(),
            available_registers={
                "holding_registers": set(),
                "input_registers": set(),
                "coil_registers": set(),
                "discrete_inputs": set(),
                "calculated": set(),
            },
            force_full_register_list=False,
            get_register_map=lambda _kind: {},
            device_name="test",
        ),
        last_update_success=True,
        data={},
    )
    entry = SimpleNamespace(runtime_data=coordinator)
    hass = SimpleNamespace(config=SimpleNamespace(language="en"))

    monkeypatch.setattr(sensor, "SENSOR_DEFINITIONS", {})
    monkeypatch.setattr(binary_sensor, "BINARY_SENSOR_DEFINITIONS", {})
    monkeypatch.setattr(time, "ENTITY_MAPPINGS", {"time": {}})
    monkeypatch.setattr(
        sensor.translation,
        "async_get_translations",
        AsyncMock(return_value={}),
    )

    sensor_calls: list[tuple[list[object], bool]] = []
    binary_calls: list[tuple[list[object], bool]] = []
    time_calls: list[tuple[list[object], bool]] = []

    await sensor.async_setup_entry(
        hass, entry, lambda entities, update=False: sensor_calls.append((entities, update))
    )
    await binary_sensor.async_setup_entry(
        hass, entry, lambda entities, update=False: binary_calls.append((entities, update))
    )
    await time.async_setup_entry(
        hass, entry, lambda entities, update=False: time_calls.append((entities, update))
    )

    assert sensor_calls and sensor_calls[0][1] is False
    # No compatible binary/time mappings means no entities and therefore no
    # callback for those two minimal fixtures; production paths use False when
    # entities are present.
    assert binary_calls == []
    assert time_calls == []
