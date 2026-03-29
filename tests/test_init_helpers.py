"""Tests for __init__.py helper functions: async_setup, _apply_log_level,
_async_cleanup_legacy_fan_entity, and _async_migrate_unique_ids."""

import asyncio
import contextlib
import logging
import sys
import types
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from custom_components.thessla_green_modbus.const import DOMAIN


@contextlib.contextmanager
def _patch_entity_registry(er_stub):
    """Temporarily replace entity_registry in both sys.modules and helpers attribute."""
    helpers_mod = sys.modules.get("homeassistant.helpers")
    original_attr = getattr(helpers_mod, "entity_registry", None) if helpers_mod else None
    original_mod = sys.modules.get("homeassistant.helpers.entity_registry")

    sys.modules["homeassistant.helpers.entity_registry"] = er_stub
    if helpers_mod is not None:
        helpers_mod.entity_registry = er_stub  # type: ignore[attr-defined]
    try:
        yield
    finally:
        if original_mod is not None:
            sys.modules["homeassistant.helpers.entity_registry"] = original_mod
        if helpers_mod is not None and original_attr is not None:
            helpers_mod.entity_registry = original_attr  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# async_setup (lines 122-123)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_setup_initialises_domain_data():
    """async_setup sets hass.data[DOMAIN] = {} if absent."""
    from custom_components.thessla_green_modbus import async_setup

    hass = MagicMock()
    hass.data = {}
    result = await async_setup(hass, {})
    assert result is True  # nosec B101
    assert DOMAIN in hass.data  # nosec B101


# ---------------------------------------------------------------------------
# _apply_log_level (lines 131-132)
# ---------------------------------------------------------------------------


def test_apply_log_level_sets_debug():
    """_apply_log_level('DEBUG') raises the logger to DEBUG."""
    from custom_components.thessla_green_modbus import _apply_log_level

    _apply_log_level("DEBUG")
    pkg = "custom_components.thessla_green_modbus"
    logger = logging.getLogger(pkg)
    assert logger.level == logging.DEBUG  # nosec B101


# ---------------------------------------------------------------------------
# _async_cleanup_legacy_fan_entity (lines 524-525)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_legacy_fan_entity_update_raises_then_removes():
    """When async_update_entity raises, async_remove is called (lines 524-525)."""
    from custom_components.thessla_green_modbus import (
        LEGACY_FAN_ENTITY_IDS,
        _async_cleanup_legacy_fan_entity,
    )

    class FakeRegistry:
        def __init__(self):
            self.removed = []
            self._entities = set(LEGACY_FAN_ENTITY_IDS)

        def async_get(self, entity_id):
            return entity_id if entity_id in self._entities else None

        def async_update_entity(self, entity_id, **kwargs):
            raise RuntimeError("update not allowed")

        def async_remove(self, entity_id):
            self.removed.append(entity_id)

    registry = FakeRegistry()
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.slave_id = 1

    er_stub = types.ModuleType("homeassistant.helpers.entity_registry")
    er_stub.async_get = lambda hass_obj: registry  # type: ignore[attr-defined]

    with _patch_entity_registry(er_stub):
        await _async_cleanup_legacy_fan_entity(hass, coordinator)

    assert len(registry.removed) == len(LEGACY_FAN_ENTITY_IDS)  # nosec B101


# ---------------------------------------------------------------------------
# _async_migrate_unique_ids — coroutine get_device_info (lines 549, 551)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migrate_unique_ids_coroutine_get_device_info():
    """When get_device_info returns a coroutine it is awaited (lines 549-551)."""
    from custom_components.thessla_green_modbus import _async_migrate_unique_ids

    @dataclass
    class FakeEntry:
        entry_id: str = "test_entry"
        data: dict = field(default_factory=dict)
        runtime_data: object = None

    async def coro_get_device_info():
        return {"serial_number": "CORTEST"}

    coordinator = MagicMock()
    del coordinator.device_info  # ensure attribute is absent
    coordinator.get_device_info = coro_get_device_info

    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry": coordinator}}
    entry = FakeEntry()
    entry.runtime_data = coordinator

    class FakeRegistry:
        def async_get(self, entity_id):
            return None

    er_stub = types.ModuleType("homeassistant.helpers.entity_registry")
    er_stub.async_get = lambda hass_obj: FakeRegistry()  # type: ignore[attr-defined]
    er_stub.async_entries_for_config_entry = lambda reg, eid: []  # type: ignore[attr-defined]

    with _patch_entity_registry(er_stub):
        await _async_migrate_unique_ids(hass, entry)
    # No exception → coroutine was awaited successfully


# ---------------------------------------------------------------------------
# _async_migrate_unique_ids — entries_for_config not callable (line 560)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migrate_unique_ids_entries_not_callable_returns_early():
    """When entries_for_config is not callable, function returns early (line 560)."""
    from custom_components.thessla_green_modbus import _async_migrate_unique_ids

    @dataclass
    class FakeEntry:
        entry_id: str = "test_entry"
        data: dict = field(default_factory=dict)
        runtime_data: object = None

    coordinator = MagicMock()
    coordinator.device_info = {"serial_number": "TESTSERIAL"}
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry": coordinator}}
    entry = FakeEntry()
    entry.runtime_data = coordinator

    class FakeRegistry:
        pass

    er_stub = types.ModuleType("homeassistant.helpers.entity_registry")
    er_stub.async_get = lambda hass_obj: FakeRegistry()  # type: ignore[attr-defined]
    # No async_entries_for_config_entry → getattr returns None → not callable

    with _patch_entity_registry(er_stub):
        await _async_migrate_unique_ids(hass, entry)
    # Early return — no crash


# ---------------------------------------------------------------------------
# _async_migrate_unique_ids — async_get returns None (line 563)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migrate_unique_ids_async_get_returns_none_skips():
    """When registry.async_get returns None for entry, skip it (line 563)."""
    from custom_components.thessla_green_modbus import _async_migrate_unique_ids

    @dataclass
    class FakeEntry:
        entry_id: str = "test_entry"
        data: dict = field(default_factory=dict)
        runtime_data: object = None

    @dataclass
    class FakeRegEntry:
        entity_id: str
        unique_id: str
        domain: str = "sensor"
        platform: str = "thessla_green_modbus"

    coordinator = MagicMock()
    coordinator.device_info = {"serial_number": "TESTSERIAL"}
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry": coordinator}}
    entry = FakeEntry()
    entry.runtime_data = coordinator

    reg_entry = FakeRegEntry(entity_id="sensor.test_xyz", unique_id="old_unique_id")
    get_call_count = [0]

    class FakeRegistry:
        def async_get(self, entity_id):
            get_call_count[0] += 1
            return None  # triggers the "skip" branch

        def async_update_entity(self, *args, **kwargs):
            pass

    er_stub = types.ModuleType("homeassistant.helpers.entity_registry")
    er_stub.async_get = lambda hass_obj: FakeRegistry()  # type: ignore[attr-defined]
    er_stub.async_entries_for_config_entry = lambda reg, eid: [reg_entry]  # type: ignore[attr-defined]

    with _patch_entity_registry(er_stub):
        await _async_migrate_unique_ids(hass, entry)

    assert get_call_count[0] >= 1  # nosec B101
