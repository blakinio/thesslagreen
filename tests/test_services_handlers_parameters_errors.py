# mypy: ignore-errors
"""Error-path and validation tests for parameter handlers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.registers.loader import get_registers_by_function
from custom_components.thessla_green_modbus.services import async_setup_services
from homeassistant.exceptions import HomeAssistantError


class _Services:
    def __init__(self):
        self.handlers: dict = {}

    def async_register(self, _domain, service, handler, _schema=None, supports_response=None):
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
        self.device_client = SimpleNamespace(available_registers=self.available_registers)


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
    monkeypatch.setattr(svc_mod, "async_extract_entity_ids", lambda c: c.data["entity_id"])
    await async_setup_services(hass)
    return hass.services.handlers[service_name]


@pytest.mark.asyncio
async def test_set_air_quality_thresholds_basic(monkeypatch):
    """Undocumented targets must not be presented as successful writes."""
    coord = _Coordinator()
    handler = await _setup_and_get(_make_hass(), "set_air_quality_thresholds", coord, monkeypatch)
    with pytest.raises(HomeAssistantError, match="Unsupported writable register"):
        await handler(
            _make_call(
                {
                    "entity_id": ["climate.dev"],
                    **{"co2_low": 600, "co2_medium": 900, "co2_high": 1200, "humidity_target": 50},
                }
            )
        )
    coord.async_write_register.assert_not_awaited()
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_air_quality_thresholds_partial(monkeypatch):
    """Undocumented targets must not be presented as successful writes."""
    coord = _Coordinator()
    handler = await _setup_and_get(_make_hass(), "set_air_quality_thresholds", coord, monkeypatch)
    with pytest.raises(HomeAssistantError, match="Unsupported writable register"):
        await handler(_make_call({"entity_id": ["climate.dev"], **{"co2_low": 600}}))
    coord.async_write_register.assert_not_awaited()
    coord.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_air_quality_thresholds_write_failure(monkeypatch):
    """Undocumented targets must not be presented as successful writes."""
    coord = _Coordinator()
    handler = await _setup_and_get(_make_hass(), "set_air_quality_thresholds", coord, monkeypatch)
    with pytest.raises(HomeAssistantError, match="Unsupported writable register"):
        await handler(
            _make_call({"entity_id": ["climate.dev"], **{"co2_low": 600, "co2_medium": 900}})
        )
    coord.async_write_register.assert_not_awaited()
    coord.async_request_refresh.assert_not_awaited()
