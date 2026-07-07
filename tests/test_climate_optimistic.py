"""Optimistic UI state tests for ThesslaGreenClimate command fields."""

import asyncio
from unittest.mock import AsyncMock

from custom_components.thessla_green_modbus import optimistic
from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.const import ATTR_TEMPERATURE


def _make_climate(mock_coordinator, data):
    mock_coordinator.data = dict(data)
    mock_coordinator.device_client.capabilities.basic_control = True
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    mock_coordinator.async_request_refresh = AsyncMock()
    return ThesslaGreenClimate(mock_coordinator)


async def test_target_temperature_pending_before_refresh(mock_coordinator):
    """target_temperature shows the requested value while the refresh is blocked."""
    climate = _make_climate(
        mock_coordinator, {"on_off_panel_mode": 1, "mode": 0, "required_temperature": 18.0}
    )
    release = asyncio.Event()
    started = asyncio.Event()

    async def _blocking_refresh():
        started.set()
        await release.wait()

    mock_coordinator.async_request_refresh = AsyncMock(side_effect=_blocking_refresh)

    task = asyncio.create_task(climate.async_set_temperature(**{ATTR_TEMPERATURE: 21.5}))
    await asyncio.wait_for(started.wait(), timeout=1)

    # Write done, refresh still parked: GUI already shows the requested setpoint.
    assert climate.target_temperature == 21.5
    assert mock_coordinator.data["required_temperature"] == 18.0

    release.set()
    await asyncio.wait_for(task, timeout=1)

    # Confirmed device value takes over once it matches.
    mock_coordinator.data["required_temperature"] = 21.5
    climate._clear_optimistic_if_confirmed()
    assert climate._optimistic.get_pending("target_temperature") is None
    assert climate.target_temperature == 21.5


async def test_hvac_mode_pending_before_refresh(mock_coordinator):
    """hvac_mode shows the requested mode while the refresh is blocked."""
    climate = _make_climate(mock_coordinator, {"on_off_panel_mode": 0, "mode": 0})
    release = asyncio.Event()
    started = asyncio.Event()

    async def _blocking_refresh():
        started.set()
        await release.wait()

    mock_coordinator.async_request_refresh = AsyncMock(side_effect=_blocking_refresh)

    task = asyncio.create_task(climate.async_set_hvac_mode(HVACMode.AUTO))
    await asyncio.wait_for(started.wait(), timeout=1)

    # Confirmed data still reports OFF (panel off) but the GUI shows AUTO.
    assert climate.hvac_mode == HVACMode.AUTO
    assert climate._confirmed_hvac_mode() == HVACMode.OFF

    release.set()
    await asyncio.wait_for(task, timeout=1)

    mock_coordinator.data["on_off_panel_mode"] = 1
    climate._clear_optimistic_if_confirmed()
    assert climate._optimistic.get_pending("hvac_mode") is None
    assert climate.hvac_mode == HVACMode.AUTO


async def test_fan_mode_pending_before_refresh(mock_coordinator):
    """fan_mode shows the requested speed while the refresh is blocked."""
    climate = _make_climate(
        mock_coordinator, {"on_off_panel_mode": 1, "mode": 1, "air_flow_rate_manual": 30}
    )
    release = asyncio.Event()
    started = asyncio.Event()

    async def _blocking_refresh():
        started.set()
        await release.wait()

    mock_coordinator.async_request_refresh = AsyncMock(side_effect=_blocking_refresh)

    task = asyncio.create_task(climate.async_set_fan_mode("60%"))
    await asyncio.wait_for(started.wait(), timeout=1)

    assert climate.fan_mode == "60%"
    assert climate._confirmed_fan_mode() == "30%"

    release.set()
    await asyncio.wait_for(task, timeout=1)

    mock_coordinator.data["air_flow_rate_manual"] = 60
    climate._clear_optimistic_if_confirmed()
    assert climate._optimistic.get_pending("fan_mode") is None
    assert climate.fan_mode == "60%"


async def test_preset_mode_pending_before_refresh(mock_coordinator):
    """preset_mode shows the requested preset while the refresh is blocked."""
    climate = _make_climate(mock_coordinator, {"on_off_panel_mode": 1, "special_mode": 0})
    release = asyncio.Event()
    started = asyncio.Event()

    async def _blocking_refresh():
        started.set()
        await release.wait()

    mock_coordinator.async_request_refresh = AsyncMock(side_effect=_blocking_refresh)

    task = asyncio.create_task(climate.async_set_preset_mode("boost"))
    await asyncio.wait_for(started.wait(), timeout=1)

    assert climate.preset_mode == "boost"
    assert climate._confirmed_preset_mode() == "none"

    release.set()
    await asyncio.wait_for(task, timeout=1)

    mock_coordinator.data["special_mode"] = 1  # boost bit
    climate._clear_optimistic_if_confirmed()
    assert climate._optimistic.get_pending("preset_mode") is None
    assert climate.preset_mode == "boost"


def test_current_temperature_confirmed_only(mock_coordinator):
    """current_temperature never reflects optimistic command fields."""
    climate = _make_climate(
        mock_coordinator,
        {
            "on_off_panel_mode": 1,
            "mode": 0,
            "supply_temperature": 20.0,
            "required_temperature": 18.0,
        },
    )
    climate._optimistic.set_pending("target_temperature", 25.0)
    assert climate.current_temperature == 20.0  # measured, unaffected


def test_hvac_action_confirmed_only(mock_coordinator):
    """hvac_action is derived from confirmed status, not optimistic hvac_mode."""
    climate = _make_climate(mock_coordinator, {"on_off_panel_mode": 1, "mode": 0})
    # Optimistically claim OFF; hvac_action must still reflect confirmed state.
    climate._optimistic.set_pending("hvac_mode", HVACMode.OFF)
    assert climate.hvac_mode == HVACMode.OFF  # optimistic command field
    assert climate.hvac_action == HVACAction.IDLE  # confirmed-only


def test_failed_write_does_not_set_pending(mock_coordinator):
    """A failed write never records an optimistic command field."""
    climate = _make_climate(
        mock_coordinator, {"on_off_panel_mode": 1, "mode": 0, "required_temperature": 18.0}
    )
    mock_coordinator.async_write_register = AsyncMock(return_value=False)

    asyncio.run(climate.async_set_temperature(**{ATTR_TEMPERATURE: 21.5}))

    assert climate._optimistic.get_pending("target_temperature") is None
    assert climate.target_temperature == 18.0
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_pending_expires_after_ttl(mock_coordinator, monkeypatch):
    """Once the TTL elapses the optimistic command field falls back to confirmed."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(optimistic, "monotonic", lambda: clock["now"])

    climate = _make_climate(
        mock_coordinator, {"on_off_panel_mode": 1, "mode": 0, "required_temperature": 18.0}
    )
    asyncio.run(climate.async_set_temperature(**{ATTR_TEMPERATURE: 21.5}))
    assert climate.target_temperature == 21.5

    clock["now"] += optimistic.DEFAULT_OPTIMISTIC_TTL + 1
    assert climate.target_temperature == 18.0
