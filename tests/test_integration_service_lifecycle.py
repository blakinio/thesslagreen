"""Integration-level contract tests for service registration lifecycle."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.thessla_green_modbus import async_setup, async_unload_entry
from custom_components.thessla_green_modbus.const import DOMAIN


class _Services:
    def __init__(self) -> None:
        self.registered: set[tuple[str, str]] = set()

    def async_register(self, domain, service, handler, schema=None, supports_response=None):
        self.registered.add((domain, service))

    def async_remove(self, domain, service):
        self.registered.discard((domain, service))


@pytest.mark.asyncio
async def test_async_setup_registers_services_without_config_entry() -> None:
    """Service schemas exist independently of a loaded device/config entry."""
    hass = SimpleNamespace(
        services=_Services(),
        data={},
    )

    assert await async_setup(hass, {}) is True
    assert (DOMAIN, "set_special_mode") in hass.services.registered
    assert (DOMAIN, "scan_all_registers") in hass.services.registered


@pytest.mark.asyncio
async def test_config_entry_unload_does_not_remove_global_services(monkeypatch) -> None:
    """Unloading one device must not remove process-lifetime service actions."""
    services = _Services()
    services.registered.add((DOMAIN, "set_special_mode"))
    config_entries = SimpleNamespace(async_unload_platforms=AsyncMock(return_value=True))
    hass = SimpleNamespace(services=services, config_entries=config_entries)
    runtime = SimpleNamespace(async_shutdown=AsyncMock())
    entry = SimpleNamespace(runtime_data=runtime)

    monkeypatch.setattr(
        "custom_components.thessla_green_modbus._get_platforms", lambda: []
    )

    assert await async_unload_entry(hass, entry) is True
    assert (DOMAIN, "set_special_mode") in services.registered
    runtime.async_shutdown.assert_awaited_once()
