"""Optimistic UI state tests for ThesslaGreenNumber."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus import optimistic
from custom_components.thessla_green_modbus.mappings import ENTITY_MAPPINGS
from custom_components.thessla_green_modbus.number import ThesslaGreenNumber

_REGISTER = "supply_air_temperature_manual"


def _make_number(mock_coordinator):
    mock_coordinator.data[_REGISTER] = 20
    entity_config = ENTITY_MAPPINGS["number"][_REGISTER]
    return ThesslaGreenNumber(mock_coordinator, _REGISTER, entity_config)


def test_pending_native_value_visible_after_write(mock_coordinator):
    """native_value shows the requested setpoint immediately after a write."""
    number = _make_number(mock_coordinator)
    mock_coordinator.async_write_register = AsyncMock(return_value=True)

    assert number.native_value == 20

    asyncio.run(number.async_set_native_value(22))

    # Coordinator data is still stale (no poll yet) but the GUI shows 22.
    assert mock_coordinator.data[_REGISTER] == 20
    assert number.native_value == 22


def test_pending_clears_when_coordinator_confirms(mock_coordinator):
    """A confirming coordinator update drops the optimistic value."""
    number = _make_number(mock_coordinator)
    mock_coordinator.async_write_register = AsyncMock(return_value=True)

    asyncio.run(number.async_set_native_value(22))
    assert number.native_value == 22

    # Device confirms the new value.
    mock_coordinator.data[_REGISTER] = 22
    number._clear_optimistic_if_confirmed()

    # From now on the confirmed device value drives the display.
    mock_coordinator.data[_REGISTER] = 21
    assert number.native_value == 21


def test_pending_expires_after_ttl(mock_coordinator, monkeypatch):
    """Once the TTL elapses the optimistic value falls back to confirmed."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(optimistic, "monotonic", lambda: clock["now"])

    number = _make_number(mock_coordinator)
    mock_coordinator.async_write_register = AsyncMock(return_value=True)

    asyncio.run(number.async_set_native_value(22))
    assert number.native_value == 22

    clock["now"] += optimistic.DEFAULT_OPTIMISTIC_TTL + 1
    assert number.native_value == 20  # confirmed device value


def test_failed_write_does_not_set_pending(mock_coordinator):
    """A failed write never records an optimistic value."""
    number = _make_number(mock_coordinator)
    mock_coordinator.async_write_register = AsyncMock(return_value=False)

    with pytest.raises(RuntimeError):
        asyncio.run(number.async_set_native_value(22))

    assert number.native_value == 20  # unchanged confirmed value


def test_pending_takes_over_then_confirmed(mock_coordinator):
    """Ordering: optimistic value is shown first, confirmed state takes over."""
    number = _make_number(mock_coordinator)
    mock_coordinator.async_write_register = AsyncMock(return_value=True)

    asyncio.run(number.async_set_native_value(22))
    assert number.native_value == 22  # optimistic

    mock_coordinator.data[_REGISTER] = 22
    number._clear_optimistic_if_confirmed()
    assert number.native_value == 22  # confirmed, pending cleared
    assert number._optimistic.get_pending(_REGISTER) is None
