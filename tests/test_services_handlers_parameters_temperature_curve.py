# mypy: ignore-errors
"""Temperature curve parameter service handler tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.services import async_setup_services


class _Services:
    def __init__(self):
        self.handlers: dict = {}

    def async_register(self, _domain, service, handler, _schema):
        self.handlers[service] = handler

    def async_remove(self, _domain, service):
        return None


class _Coordinator:
    def __init__(self, write_result=True):
        self.async_write_register = AsyncMock(return_value=write_result)
        self.async_request_refresh = AsyncMock()
        self.available_registers = {
            "holding_registers": {r.name for r in get_registers_by_function("03")}
        }


def _make_hass():
    hass = SimpleNamespace()
    hass.services = _Services()
    hass.data = {}
    hass.bus = SimpleNamespace(async_fire=MagicMock())
    return hass


def _make_call(data: dict):
    return SimpleNamespace(data=data)


async def _setup_and_get(hass, service_name, coordinator, monkeypatch):
    from custom_components.thessla_green_modbus import services as svc_mod

    monkeypatch.setattr(svc_mod, "_get_coordinator_from_entity_id", lambda _h, _e: coordinator)
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda _h, c: c.data["entity_id"])
    await async_setup_services(hass)
    return hass.services.handlers[service_name]


@pytest.mark.asyncio
async def test_set_temperature_curve_basic(monkeypatch):
    coord = _Coordinator()
    handler = await _setup_and_get(_make_hass(), "set_temperature_curve", coord, monkeypatch)
    await handler(_make_call({"entity_id": ["climate.dev"], "slope": 2.5, "offset": 1.0}))
    written = {c.args[0]: c.args[1] for c in coord.async_write_register.call_args_list}
    assert written["heating_curve_slope"] == 2.5
    assert written["heating_curve_offset"] == 1.0
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_temperature_curve_with_supply_temps(monkeypatch):
    coord = _Coordinator()
    handler = await _setup_and_get(_make_hass(), "set_temperature_curve", coord, monkeypatch)
    await handler(
        _make_call(
            {
                "entity_id": ["climate.dev"],
                "slope": 1.5,
                "offset": 0.5,
                "max_supply_temp": 60.0,
                "min_supply_temp": 20.0,
            }
        )
    )
    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "max_supply_temperature" in written
    assert "min_supply_temperature" in written


@pytest.mark.asyncio
async def test_set_temperature_curve_write_failure(monkeypatch):
    coord = _Coordinator(write_result=False)
    handler = await _setup_and_get(_make_hass(), "set_temperature_curve", coord, monkeypatch)
    await handler(_make_call({"entity_id": ["climate.dev"], "slope": 2.0, "offset": 0.0}))
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_temperature_curve_offset_write_failure(monkeypatch):
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    handler = await _setup_and_get(_make_hass(), "set_temperature_curve", coord, monkeypatch)
    await handler(_make_call({"entity_id": ["climate.dev"], "slope": 2.0, "offset": 1.0}))
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_temperature_curve_max_supply_write_failure(monkeypatch):
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, True, False])
    handler = await _setup_and_get(_make_hass(), "set_temperature_curve", coord, monkeypatch)
    await handler(
        _make_call(
            {
                "entity_id": ["climate.dev"],
                "slope": 2.0,
                "offset": 1.0,
                "max_supply_temp": 60.0,
            }
        )
    )
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_temperature_curve_min_supply_write_failure(monkeypatch):
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, True, True, False])
    handler = await _setup_and_get(_make_hass(), "set_temperature_curve", coord, monkeypatch)
    await handler(
        _make_call(
            {
                "entity_id": ["climate.dev"],
                "slope": 2.0,
                "offset": 1.0,
                "max_supply_temp": 60.0,
                "min_supply_temp": 20.0,
            }
        )
    )
    coord.async_request_refresh.assert_not_awaited()
