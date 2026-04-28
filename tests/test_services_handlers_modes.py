# mypy: ignore-errors
"""Split tests from test_services_handlers.py."""


from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.modbus_exceptions import (
    ModbusException,
)
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
async def test_set_special_mode_basic(monkeypatch):
    """set_special_mode writes special_mode register and refreshes."""
    coord = _Coordinator()
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 0})
    await handler(call)

    coord.async_write_register.assert_called_once_with("special_mode", 1, refresh=False)
    coord.async_request_refresh.assert_awaited_once()

@pytest.mark.asyncio
async def test_set_special_mode_with_duration(monkeypatch):
    """set_special_mode writes duration register when available."""
    coord = _Coordinator()
    coord.available_registers = {"holding_registers": {"boost_duration"}}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 30})
    await handler(call)

    calls = coord.async_write_register.call_args_list
    assert any(c.args[0] == "special_mode" for c in calls)
    assert any(c.args[0] == "boost_duration" for c in calls)

@pytest.mark.asyncio
async def test_set_special_mode_write_failure(monkeypatch):
    """set_special_mode stops if write fails."""
    coord = _Coordinator(write_result=False)
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 0})
    await handler(call)

    coord.async_request_refresh.assert_not_awaited()

@pytest.mark.asyncio
async def test_set_special_mode_modbus_exception(monkeypatch):
    """_write_register logs error on ModbusException."""
    coord = _Coordinator()
    coord.async_write_register.side_effect = ModbusException("fail")
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 0})
    await handler(call)  # should not raise
    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_airflow_schedule
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_special_mode_duration_write_failure(monkeypatch):
    """set_special_mode continues when duration register write fails."""
    coord = _Coordinator()
    # First write (special_mode) succeeds; second (duration) fails
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    coord.available_registers = {"holding_registers": {"boost_duration"}}
    hass = _make_hass()
    handler = await _setup_and_get(hass, "set_special_mode", coord, monkeypatch)

    call = _make_call({"entity_id": ["climate.dev"], "mode": "boost", "duration": 30})
    await handler(call)

    coord.async_request_refresh.assert_not_awaited()


# ---------------------------------------------------------------------------
# set_airflow_schedule — specific step write failures (lines 439-440, 448-449, 459-460)
# ---------------------------------------------------------------------------

