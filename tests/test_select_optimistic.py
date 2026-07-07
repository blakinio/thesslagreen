"""Optimistic UI state tests for ThesslaGreenSelect."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus import optimistic
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.schedule_helpers import TIME_SELECT_STATES
from custom_components.thessla_green_modbus.select import ThesslaGreenSelect
from homeassistant.exceptions import HomeAssistantError

_MODE_ADDR = 4208


def _make_mode_select(mock_coordinator, value=0):
    mock_coordinator.data["mode"] = value
    return ThesslaGreenSelect(
        mock_coordinator, "mode", _MODE_ADDR, ENTITY_MAPPINGS["select"]["mode"]
    )


def test_pending_current_option_after_select(mock_coordinator):
    """current_option shows the requested option immediately after a write."""
    select_entity = _make_mode_select(mock_coordinator, value=0)
    mock_coordinator.async_write_register = AsyncMock(return_value=True)

    assert select_entity.current_option == "auto"

    asyncio.run(select_entity.async_select_option("manual"))

    # Coordinator data still reads 0 but the GUI shows the requested option.
    assert mock_coordinator.data["mode"] == 0
    assert select_entity.current_option == "manual"


def test_pending_clears_when_raw_confirms(mock_coordinator):
    """A confirming raw coordinator value drops the optimistic option."""
    select_entity = _make_mode_select(mock_coordinator, value=0)
    mock_coordinator.async_write_register = AsyncMock(return_value=True)

    asyncio.run(select_entity.async_select_option("manual"))
    assert select_entity.current_option == "manual"

    mock_coordinator.data["mode"] = 1  # device confirms "manual"
    select_entity._clear_optimistic_if_confirmed()
    assert select_entity._optimistic.get_pending("mode") is None

    mock_coordinator.data["mode"] = 0
    assert select_entity.current_option == "auto"


def test_invalid_option_does_not_set_pending(mock_coordinator):
    """An invalid option raises and records no optimistic value."""
    select_entity = _make_mode_select(mock_coordinator, value=0)
    mock_coordinator.async_write_register = AsyncMock()

    with pytest.raises(HomeAssistantError):
        asyncio.run(select_entity.async_select_option("unsupported"))

    mock_coordinator.async_write_register.assert_not_awaited()
    assert select_entity._optimistic.get_pending("mode") is None
    assert select_entity.current_option == "auto"


def test_failed_write_does_not_set_pending(mock_coordinator):
    """A failed write raises and records no optimistic value."""
    select_entity = _make_mode_select(mock_coordinator, value=0)
    mock_coordinator.async_write_register = AsyncMock(return_value=False)

    with pytest.raises(HomeAssistantError):
        asyncio.run(select_entity.async_select_option("manual"))

    assert select_entity._optimistic.get_pending("mode") is None
    assert select_entity.current_option == "auto"


def test_pending_expires_after_ttl(mock_coordinator, monkeypatch):
    """Once the TTL elapses the optimistic option falls back to confirmed."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(optimistic, "monotonic", lambda: clock["now"])

    select_entity = _make_mode_select(mock_coordinator, value=0)
    mock_coordinator.async_write_register = AsyncMock(return_value=True)

    asyncio.run(select_entity.async_select_option("manual"))
    assert select_entity.current_option == "manual"

    clock["now"] += optimistic.DEFAULT_OPTIMISTIC_TTL + 1
    assert select_entity.current_option == "auto"


def test_schedule_time_select_excluded_from_optimistic(mock_coordinator):
    """Schedule/BCD-time selects never record optimistic state."""
    defn = {
        "translation_key": "schedule_summer_mon_1",
        "icon": "mdi:clock-outline",
        "register_type": "holding_registers",
        "states": TIME_SELECT_STATES,
    }
    mock_coordinator.data["schedule_summer_mon_1"] = "04:00"
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    entity = ThesslaGreenSelect(mock_coordinator, "schedule_summer_mon_1", 16, defn)

    assert entity._optimistic_enabled is False

    asyncio.run(entity.async_select_option("06:30"))

    # No optimistic value stored; current_option follows coordinator data only.
    assert entity._optimistic.get_pending("schedule_summer_mon_1") is None
    assert entity.current_option == "04:00"
