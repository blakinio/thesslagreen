"""Optimistic UI state tests for ThesslaGreenSwitch."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from custom_components.thessla_green_modbus import optimistic
from custom_components.thessla_green_modbus.switch import ThesslaGreenSwitch

_COIL_CFG = {
    "register": "bypass",
    "register_type": "coil_registers",
    "translation_key": "bypass",
    "icon": "mdi:pipe-leak",
}
_BIT_CFG = {
    "register": "bypass",
    "register_type": "holding_registers",
    "translation_key": "bypass_bit",
    "bit": 4,
}
_SPECIAL_CFG = {
    "register": "special_mode",
    "register_type": "holding_registers",
    "translation_key": "special_mode_boost",
    "bit": 2,
}


def test_pending_is_on_after_turn_on(mock_coordinator):
    """is_on reflects the requested ON state immediately after a write."""
    mock_coordinator.data["bypass"] = 0
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    switch = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, _COIL_CFG)

    assert switch.is_on is False

    asyncio.run(switch.async_turn_on())

    # Coordinator data still reads 0 (no poll yet) but the GUI shows ON.
    assert mock_coordinator.data["bypass"] == 0
    assert switch.is_on is True


def test_pending_is_on_after_turn_off(mock_coordinator):
    """is_on reflects the requested OFF state immediately after a write."""
    mock_coordinator.data["bypass"] = 1
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    switch = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, _COIL_CFG)

    assert switch.is_on is True

    asyncio.run(switch.async_turn_off())

    assert mock_coordinator.data["bypass"] == 1
    assert switch.is_on is False


def test_bit_switch_pending_raw_value(mock_coordinator):
    """A bit switch records the merged raw value and evaluates the bit."""
    mock_coordinator.data["bypass"] = 0b0010  # other bit set, target bit (4) clear
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    switch = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, _BIT_CFG)

    assert switch.is_on is False

    asyncio.run(switch.async_turn_on())

    # Pending raw value is current | bit → bit 4 set.
    assert switch._optimistic.get_pending("bypass") == 0b0110
    assert switch.is_on is True


def test_special_mode_pending_raw_value(mock_coordinator):
    """special_mode stores the raw value so equality evaluation is correct."""
    mock_coordinator.data["special_mode"] = 0
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    switch = ThesslaGreenSwitch(mock_coordinator, "special_mode_boost", 4097, _SPECIAL_CFG)

    assert switch.is_on is False

    asyncio.run(switch.async_turn_on())
    assert switch._optimistic.get_pending("special_mode") == 2
    assert switch.is_on is True

    asyncio.run(switch.async_turn_off())
    assert switch._optimistic.get_pending("special_mode") == 0
    assert switch.is_on is False


def test_failed_write_does_not_set_pending(mock_coordinator):
    """A failed write never records an optimistic value."""
    mock_coordinator.data["bypass"] = 0
    mock_coordinator.async_write_register = AsyncMock(return_value=False)
    switch = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, _COIL_CFG)

    with pytest.raises(RuntimeError):
        asyncio.run(switch.async_turn_on())

    assert switch._optimistic.get_pending("bypass") is None
    assert switch.is_on is False


def test_pending_clears_on_confirmed_update(mock_coordinator):
    """A confirming coordinator update drops the optimistic value."""
    mock_coordinator.data["bypass"] = 0
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    switch = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, _COIL_CFG)

    asyncio.run(switch.async_turn_on())
    assert switch.is_on is True

    mock_coordinator.data["bypass"] = 1
    switch._clear_optimistic_if_confirmed()
    assert switch._optimistic.get_pending("bypass") is None

    # Confirmed device state now drives the display.
    mock_coordinator.data["bypass"] = 0
    assert switch.is_on is False


def test_pending_expires_after_ttl(mock_coordinator, monkeypatch):
    """Once the TTL elapses the optimistic value falls back to confirmed."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(optimistic, "monotonic", lambda: clock["now"])

    mock_coordinator.data["bypass"] = 0
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    switch = ThesslaGreenSwitch(mock_coordinator, "bypass", 9, _COIL_CFG)

    asyncio.run(switch.async_turn_on())
    assert switch.is_on is True

    clock["now"] += optimistic.DEFAULT_OPTIMISTIC_TTL + 1
    assert switch.is_on is False  # confirmed device state
