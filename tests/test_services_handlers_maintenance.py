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
async def test_reset_filters_basic(monkeypatch):
    """reset_filters writes filter_change register."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_filters", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "filter_type": "flat_filters"})
    await handler(call)

    coord.async_write_register.assert_called_once_with("filter_change", 2, refresh=False)
    coord.async_request_refresh.assert_awaited_once()

@pytest.mark.asyncio
async def test_reset_filters_write_failure(monkeypatch):
    """reset_filters aborts when write fails."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_filters", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "filter_type": "presostat"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# reset_settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_settings_user(monkeypatch):
    """reset_settings(user_settings) writes hard_reset_settings."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "user_settings"})
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "hard_reset_settings" in written
    assert "hard_reset_schedule" not in written
    coord.async_request_refresh.assert_awaited_once()

@pytest.mark.asyncio
async def test_reset_settings_schedule(monkeypatch):
    """reset_settings(schedule_settings) writes hard_reset_schedule."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "schedule_settings"})
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "hard_reset_settings" not in written
    assert "hard_reset_schedule" in written

@pytest.mark.asyncio
async def test_reset_settings_all(monkeypatch):
    """reset_settings(all_settings) writes both reset registers."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "all_settings"})
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "hard_reset_settings" in written
    assert "hard_reset_schedule" in written


# ---------------------------------------------------------------------------
# start_pressure_test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_pressure_test_basic(monkeypatch):
    """start_pressure_test writes day and time registers."""
    import datetime

    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "start_pressure_test", coord, monkeypatch)

    fake_now = datetime.datetime(2024, 3, 11, 14, 30)  # Monday, 14:30
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(
        svc_mod, "dt_util", type("DT", (), {"now": staticmethod(lambda: fake_now)})()
    )

    call = _make_call({"entity_id": ["climate.dev"]})
    await handler(call)

    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "pres_check_day_2" in written
    assert "pres_check_time_2" in written
    coord.async_request_refresh.assert_awaited_once()

@pytest.mark.asyncio
async def test_start_pressure_test_write_failure(monkeypatch):
    """start_pressure_test aborts when day write fails."""
    import datetime

    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "start_pressure_test", coord, monkeypatch)

    fake_now = datetime.datetime(2024, 3, 11, 14, 30)
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(
        svc_mod, "dt_util", type("DT", (), {"now": staticmethod(lambda: fake_now)})()
    )

    call = _make_call({"entity_id": ["climate.dev"]})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_modbus_parameters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_settings_user_write_failure(monkeypatch):
    """reset_settings(user_settings) aborts on write failure."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "user_settings"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()

@pytest.mark.asyncio
async def test_reset_settings_schedule_write_failure(monkeypatch):
    """reset_settings(schedule_settings) aborts on write failure."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "schedule_settings"})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()

@pytest.mark.asyncio
async def test_reset_settings_all_first_write_failure(monkeypatch):
    """reset_settings(all_settings) aborts when user settings write fails."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "reset_settings", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "reset_type": "all_settings"})
    await handler(call)
    # Only one write attempted (user settings failed)
    assert coord.async_write_register.call_count == 1
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# start_pressure_test — time write failure (lines 722-723)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_pressure_test_time_write_failure(monkeypatch):
    """start_pressure_test aborts when pres_check_time write fails (2nd write)."""
    import datetime

    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    hass = _make_hass()
    handler = await _setup_and_get(hass, "start_pressure_test", coord, monkeypatch)

    fake_now = datetime.datetime(2024, 3, 11, 14, 30)
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(
        svc_mod, "dt_util", type("DT", (), {"now": staticmethod(lambda: fake_now)})()
    )

    call = _make_call({"entity_id": ["climate.dev"]})
    await handler(call)
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_modbus_parameters — parity/stop write failures (lines 779-780, 790-791)
# ---------------------------------------------------------------------------

