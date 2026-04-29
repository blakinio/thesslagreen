# mypy: ignore-errors
"""GWC parameter service handler tests."""

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
async def test_set_gwc_parameters_basic(monkeypatch):
    coord = _Coordinator()
    handler = await _setup_and_get(_make_hass(), "set_gwc_parameters", coord, monkeypatch)
    await handler(_make_call({"entity_id": ["climate.dev"], "mode": "auto"}))
    coord.async_write_register.assert_called_once_with("gwc_mode", 1, refresh=False)
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_gwc_parameters_with_temps(monkeypatch):
    coord = _Coordinator()
    handler = await _setup_and_get(_make_hass(), "set_gwc_parameters", coord, monkeypatch)
    await handler(
        _make_call(
            {
                "entity_id": ["climate.dev"],
                "mode": "forced",
                "min_air_temperature": 5.0,
                "max_air_temperature": 35.0,
            }
        )
    )
    written = [c.args[0] for c in coord.async_write_register.call_args_list]
    assert "gwc_mode" in written
    assert "min_gwc_air_temperature" in written
    assert "max_gwc_air_temperature" in written


@pytest.mark.asyncio
async def test_set_gwc_parameters_write_failure(monkeypatch):
    coord = _Coordinator(write_result=False)
    handler = await _setup_and_get(_make_hass(), "set_gwc_parameters", coord, monkeypatch)
    await handler(_make_call({"entity_id": ["climate.dev"], "mode": "off"}))
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_gwc_parameters_min_temp_write_failure(monkeypatch):
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, False])
    handler = await _setup_and_get(_make_hass(), "set_gwc_parameters", coord, monkeypatch)
    await handler(
        _make_call(
            {
                "entity_id": ["climate.dev"],
                "mode": "auto",
                "min_air_temperature": 5.0,
            }
        )
    )
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_gwc_parameters_max_temp_write_failure(monkeypatch):
    coord = _Coordinator()
    coord.async_write_register = AsyncMock(side_effect=[True, True, False])
    handler = await _setup_and_get(_make_hass(), "set_gwc_parameters", coord, monkeypatch)
    await handler(
        _make_call(
            {
                "entity_id": ["climate.dev"],
                "mode": "auto",
                "min_air_temperature": 5.0,
                "max_air_temperature": 35.0,
            }
        )
    )
    coord.async_request_refresh.assert_not_awaited()


def test_gwc_schema_rejects_min_ge_max():
    from custom_components.thessla_green_modbus.services import _validate_gwc_temperature_range

    with pytest.raises(Exception, match="strictly less than"):
        _validate_gwc_temperature_range({"min_air_temperature": 20.0, "max_air_temperature": 20.0})
