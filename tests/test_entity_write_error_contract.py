"""Regression tests for writable-entity failure semantics."""

from __future__ import annotations

from datetime import time as dt_time
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
