# mypy: ignore-errors
"""Split tests from test_services_handlers.py."""


from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.services import (
    async_setup_services,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Services:
    """Minimal service registry."""

    def __init__(self):
        self.handlers: dict = {}
        self.removed: list = []

    def async_register(self, _domain, service, handler, _schema):
        self.handlers[service] = handler

    def async_remove(self, _domain, service):
        self.removed.append(service)


class _Coordinator:
    """Minimal coordinator stub."""

    def __init__(self, write_result=True):
        self.async_write_register = AsyncMock(return_value=write_result)
        self.async_request_refresh = AsyncMock()
        self.effective_batch = 2
        self.available_registers = {
            "holding_registers": {r.name for r in get_registers_by_function("03")}
        }
        self.data = {}
        self.host = "127.0.0.1"
        self.port = 502
        self.slave_id = 1
        self.timeout = 5
        self.retry = 3
        self.scan_uart_settings = False
        self.unknown_registers = {}
        self.scanned_registers = {}


def _make_hass(coordinator=None):
    """Return a hass stub with a service registry and optional coordinator."""
    hass = SimpleNamespace()
    hass.services = _Services()
    hass.data = {}
    hass.bus = SimpleNamespace(async_fire=MagicMock())
    if coordinator is not None:
        from custom_components.thessla_green_modbus.const import DOMAIN

        hass.data = {DOMAIN: {"entry1": coordinator}}
    return hass


def _make_call(data: dict):
    return SimpleNamespace(data=data)


async def _setup_and_get(hass, service_name, coordinator, monkeypatch):
    """Set up services and return the named handler with coordinator patched in."""
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coordinator)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda _h, c: c.data["entity_id"])
    await async_setup_services(hass)
    return hass.services.handlers[service_name]


# ---------------------------------------------------------------------------
# _LogLevelManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_airflow_schedule_basic(monkeypatch):
    """set_airflow_schedule writes schedule registers."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 75,
        }
    )
    await handler(call)

    coord.async_request_refresh.assert_awaited_once()
    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "schedule_summer_mon_1" in written
    assert "setting_summer_mon_1" in written
    assert not any(k.endswith("_period1_end") for k in written)

@pytest.mark.asyncio
async def test_set_airflow_schedule_with_temperature(monkeypatch):
    """set_airflow_schedule writes temp register when provided."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "friday",
            "period": 2,
            "start_time": start,
            "airflow_rate": 50,
            "temperature": 22.0,
        }
    )
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "schedule_summer_fri_2" in written
    assert "setting_summer_fri_2" in written

@pytest.mark.asyncio
async def test_set_airflow_schedule_clamp_rate(monkeypatch):
    """_clamp_airflow_rate applies min/max from coordinator data."""
    coord = _Coordinator()
    coord.data = {"min_percentage": 10, "max_percentage": 80}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 200,  # above max, should be clamped to 80
        }
    )
    await handler(call)

    setting_calls = [
        c for c in coord.async_write_register.call_args_list if c.args[0] == "setting_summer_mon_1"
    ]
    assert setting_calls
    assert setting_calls[0].args[1] == (80 << 8)

@pytest.mark.asyncio
async def test_set_airflow_schedule_write_failure(monkeypatch):
    """set_airflow_schedule aborts on write failure."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 50,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_bypass_parameters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_airflow_schedule_clamp_bad_min(monkeypatch):
    """_clamp_airflow_rate falls back to 0 when min_percentage is non-numeric."""
    coord = _Coordinator()
    coord.data = {"min_percentage": "bad", "max_percentage": 100}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 50,
        }
    )
    await handler(call)  # should not raise
    coord.async_request_refresh.assert_awaited_once()

@pytest.mark.asyncio
async def test_set_airflow_schedule_clamp_bad_max(monkeypatch):
    """_clamp_airflow_rate falls back to 150 when max_percentage is non-numeric."""
    coord = _Coordinator()
    coord.data = {"min_percentage": 10, "max_percentage": "bad"}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "tuesday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 80,
        }
    )
    await handler(call)  # should not raise
    coord.async_request_refresh.assert_awaited_once()

@pytest.mark.asyncio
async def test_set_airflow_schedule_clamp_inverted_bounds(monkeypatch):
    """_clamp_airflow_rate clamps when max < min (max is set to min)."""
    coord = _Coordinator()
    coord.data = {"min_percentage": 60, "max_percentage": 30}  # inverted
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "wednesday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 10,  # below both, should clamp to 60 (min==max after fix)
        }
    )
    await handler(call)

    setting_calls = [
        c for c in coord.async_write_register.call_args_list if c.args[0] == "setting_summer_wed_1"
    ]
    assert setting_calls
    assert setting_calls[0].args[1] == (60 << 8)


# ---------------------------------------------------------------------------
# set_special_mode — duration write failure (lines 361-366)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_airflow_schedule_setting_write_failure(monkeypatch):
    """set_airflow_schedule aborts when AATT setting write fails (2nd write)."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 1,
            "start_time": start,
            "airflow_rate": 50,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()

@pytest.mark.asyncio
async def test_set_airflow_schedule_start_write_failure(monkeypatch):
    """set_airflow_schedule aborts when start write fails (1st write)."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 2,
            "start_time": start,
            "airflow_rate": 50,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()

@pytest.mark.asyncio
async def test_set_airflow_schedule_temp_write_failure(monkeypatch):
    """set_airflow_schedule aborts when AATT write fails with temperature."""
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_airflow_schedule", coord, monkeypatch)

    start = SimpleNamespace(hour=8, minute=0)
    call = _make_call(
        {
            "entity_id": ["climate.dev"],
            "day": "monday",
            "period": 3,
            "start_time": start,
            "airflow_rate": 50,
            "temperature": 22.0,
        }
    )
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_bypass_parameters — min_temp write failure (lines 495-496)
# ---------------------------------------------------------------------------

