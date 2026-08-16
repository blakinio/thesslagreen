"""Optimistic UI state tests for ThesslaGreenClimate command fields."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus import optimistic
from custom_components.thessla_green_modbus.climate import ThesslaGreenClimate
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.exceptions import HomeAssistantError


def _make_climate(mock_coordinator, data):
    mock_coordinator.data = dict(data)
    mock_coordinator.device_client.capabilities.basic_control = True
    mock_coordinator.device_client.available_registers["holding_registers"].add(
        "supply_air_temperature_manual"
    )
    mock_coordinator.async_write_register = AsyncMock(return_value=True)
    mock_coordinator.async_request_refresh = AsyncMock()
    return ThesslaGreenClimate(mock_coordinator)


async def test_target_temperature_pending_before_refresh(mock_coordinator):
    """target_temperature shows requested value only while full refresh is in flight."""
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

    assert climate.target_temperature == 21.5
    assert mock_coordinator.data["required_temperature"] == 18.0

    release.set()
    await asyncio.wait_for(task, timeout=1)

    # The completed refresh is authoritative even when it confirms a value
    # different from the command; stale optimistic state must not mask it.
    assert climate._optimistic.get_pending("target_temperature") is None
    assert climate.target_temperature == 18.0

    mock_coordinator.data["required_temperature"] = 21.5
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

    assert climate.hvac_mode == HVACMode.AUTO
    assert climate._confirmed_hvac_mode() == HVACMode.OFF

    release.set()
    await asyncio.wait_for(task, timeout=1)

    assert climate._optimistic.get_pending("hvac_mode") is None
    assert climate.hvac_mode == HVACMode.OFF

    mock_coordinator.data["on_off_panel_mode"] = 1
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

    assert climate._optimistic.get_pending("fan_mode") is None
    assert climate.fan_mode == "30%"

    mock_coordinator.data["air_flow_rate_manual"] = 60
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

    assert climate._optimistic.get_pending("preset_mode") is None
    assert climate.preset_mode == "none"

    mock_coordinator.data["special_mode"] = 1
    assert climate.preset_mode == "boost"


def test_coordinator_update_reconciles_pending_state(mock_coordinator):
    """Coordinator callbacks clear matching optimistic values before parent handling."""
    climate = _make_climate(
        mock_coordinator, {"on_off_panel_mode": 1, "mode": 0, "required_temperature": 21.5}
    )
    climate._optimistic.set_pending("target_temperature", 21.5)

    with patch(
        "custom_components.thessla_green_modbus.climate.ThesslaGreenEntity._handle_coordinator_update"
    ) as parent_update:
        climate._handle_coordinator_update()

    assert climate._optimistic.get_pending("target_temperature") is None
    parent_update.assert_called_once()


async def test_optimistic_and_reconcile_push_ha_state_when_added(mock_coordinator):
    """Pending and confirmed transitions notify HA when the entity is attached."""
    climate = _make_climate(
        mock_coordinator, {"on_off_panel_mode": 1, "mode": 0, "required_temperature": 18.0}
    )
    climate.hass = Mock()
    climate.async_write_ha_state = Mock()

    climate._set_optimistic("target_temperature", 21.5)
    assert climate.target_temperature == 21.5

    await climate._refresh_and_reconcile("target_temperature")

    assert climate._optimistic.get_pending("target_temperature") is None
    assert climate.async_write_ha_state.call_count == 2


async def test_reapply_manual_setpoints_skips_invalid_or_unavailable_values(mock_coordinator):
    """Manual-mode recommit uses only discovered numeric setpoints."""
    climate = _make_climate(
        mock_coordinator,
        {
            "air_flow_rate_manual": "invalid",
            "supply_air_temperature_manual": 22.0,
        },
    )

    await climate._reapply_manual_setpoints()

    mock_coordinator.async_write_register.assert_awaited_once_with(
        "supply_air_temperature_manual",
        22.0,
        refresh=False,
        offset=0,
        targeted_readback=False,
    )


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
    assert climate.current_temperature == 20.0


def test_hvac_action_confirmed_only(mock_coordinator):
    """hvac_action is derived from confirmed status, not optimistic hvac_mode."""
    climate = _make_climate(mock_coordinator, {"on_off_panel_mode": 1, "mode": 0})
    climate._optimistic.set_pending("hvac_mode", HVACMode.OFF)
    assert climate.hvac_mode == HVACMode.OFF
    assert climate.hvac_action == HVACAction.IDLE


def test_failed_write_does_not_set_pending(mock_coordinator):
    """A rejected write raises and never records an optimistic command field."""
    climate = _make_climate(
        mock_coordinator, {"on_off_panel_mode": 1, "mode": 0, "required_temperature": 18.0}
    )
    mock_coordinator.async_write_register = AsyncMock(return_value=False)

    with pytest.raises(HomeAssistantError):
        asyncio.run(climate.async_set_temperature(**{ATTR_TEMPERATURE: 21.5}))

    assert climate._optimistic.get_pending("target_temperature") is None
    assert climate.target_temperature == 18.0
    mock_coordinator.async_request_refresh.assert_not_awaited()


def test_pending_expires_after_ttl(mock_coordinator, monkeypatch):
    """A pending command still self-expires if no confirming refresh completes."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(optimistic, "monotonic", lambda: clock["now"])

    climate = _make_climate(
        mock_coordinator, {"on_off_panel_mode": 1, "mode": 0, "required_temperature": 18.0}
    )
    climate._set_optimistic("target_temperature", 21.5)
    assert climate.target_temperature == 21.5

    clock["now"] += optimistic.DEFAULT_OPTIMISTIC_TTL + 1
    assert climate.target_temperature == 18.0
