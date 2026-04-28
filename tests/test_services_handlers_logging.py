# mypy: ignore-errors
"""Split tests from test_services_handlers.py."""


from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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
async def test_log_level_manager_set_and_restore():
    """_LogLevelManager.set_level changes log level and schedules restore."""
    from custom_components.thessla_green_modbus.services import _LogLevelManager

    hass = SimpleNamespace()
    called_with = {}

    def fake_call_later(_h, delay, cb):
        called_with["delay"] = delay
        called_with["cb"] = cb
        return lambda: None

    with patch(
        "custom_components.thessla_green_modbus.services.async_call_later",
        side_effect=fake_call_later,
    ):
        mgr = _LogLevelManager(hass)
        mgr.set_level(logging.DEBUG, 60)

    assert called_with["delay"] == 60
    target = logging.getLogger("custom_components.thessla_green_modbus")
    assert target.level == logging.DEBUG

    # Restore callback fires
    mgr._restore_level_callback(None)
    assert mgr._undo_callback is None

@pytest.mark.asyncio
async def test_log_level_manager_cancel_previous():
    """Calling set_level twice cancels the previous undo callback."""
    from custom_components.thessla_green_modbus.services import _LogLevelManager

    hass = SimpleNamespace()
    cancelled = []

    def fake_call_later(_h, _d, _cb):
        undo = MagicMock(side_effect=lambda: cancelled.append(True))
        return undo

    with patch(
        "custom_components.thessla_green_modbus.services.async_call_later",
        side_effect=fake_call_later,
    ):
        mgr = _LogLevelManager(hass)
        mgr.set_level(logging.DEBUG, 60)
        mgr.set_level(logging.INFO, 120)

    assert len(cancelled) == 1  # first undo was called

@pytest.mark.asyncio
async def test_log_level_manager_zero_duration():
    """set_level with duration=0 does not schedule a restore."""
    from custom_components.thessla_green_modbus.services import _LogLevelManager

    hass = SimpleNamespace()
    with patch("custom_components.thessla_green_modbus.services.async_call_later") as mock_later:
        mgr = _LogLevelManager(hass)
        mgr.set_level(logging.DEBUG, 0)
    mock_later.assert_not_called()


# ---------------------------------------------------------------------------
# set_debug_logging
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_debug_logging(monkeypatch):
    """set_debug_logging invokes _LogLevelManager.set_level."""
    coord = _Coordinator()
    hass = _make_hass(coord)
    handler = await _setup_and_get(hass, "set_debug_logging", coord, monkeypatch)

    from custom_components.thessla_green_modbus.services import _LogLevelManager

    with patch.object(_LogLevelManager, "set_level") as mock_set:
        call = _make_call({"level": "debug", "duration": 300})
        await handler(call)
        mock_set.assert_called_once_with(logging.DEBUG, 300)


# ---------------------------------------------------------------------------
# set_special_mode
# ---------------------------------------------------------------------------

