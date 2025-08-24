from dataclasses import dataclass, field
import logging
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.thessla_green_modbus import async_setup_entry
from custom_components.thessla_green_modbus.const import DOMAIN


@pytest.mark.asyncio
async def test_legacy_fan_entity_migrated(hass, caplog):
    """Legacy number entity should be migrated to fan entity."""
    host = "fd00:1:2::1"
    port = 502
    slave_id = 5

    @dataclass
    class SimpleConfigEntry:
        domain: str
        data: dict
        options: dict = field(default_factory=dict)
        title: str = ""
        entry_id: str = "1"

        def add_update_listener(self, listener):
            self._listener = listener
            return listener

        def async_on_unload(self, func):
            return None

    entry = SimpleConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: host, CONF_PORT: port, "slave_id": slave_id},
    )

    @dataclass
    class DummyEntry:
        entity_id: str
        unique_id: str
        domain: str
        platform: str

    class FakeRegistry:
        def __init__(self) -> None:
            self.entities: dict[str, DummyEntry] = {}

        def async_get(self, entity_id: str):
            return self.entities.get(entity_id)

        def async_remove(self, entity_id: str) -> None:
            self.entities.pop(entity_id, None)

        def async_update_entity(self, entity_id: str, *, new_entity_id=None, new_unique_id=None):
            entry = self.entities.pop(entity_id)
            entry.entity_id = new_entity_id or entity_id
            entry.unique_id = new_unique_id or entry.unique_id
            self.entities[entry.entity_id] = entry

    registry = FakeRegistry()
    unique_host = host.replace(":", "-")
    old_entity_id = "number.rekuperator_predkosc"
    old_unique_id = f"{DOMAIN}_{unique_host}_{port}_{slave_id}_air_flow_rate_manual"
    registry.entities[old_entity_id] = DummyEntry(old_entity_id, old_unique_id, "number", DOMAIN)

    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_reload = AsyncMock()
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    hass.data = {DOMAIN: {"existing": object()}}

    dummy_module = types.ModuleType("coordinator")
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_setup = AsyncMock(return_value=True)
    coordinator.host = host
    coordinator.port = port
    coordinator.slave_id = slave_id
    coordinator.device_info = {"serial_number": "ABC123"}
    dummy_module.ThesslaGreenModbusCoordinator = MagicMock(return_value=coordinator)

    with (
        patch(
            "custom_components.thessla_green_modbus.__init__.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.thessla_green_modbus.__init__.er.async_entries_for_config_entry",
            return_value=list(registry.entities.values()),
            create=True,
        ),
        patch.dict(
            sys.modules,
            {"custom_components.thessla_green_modbus.coordinator": dummy_module},
        ),
        caplog.at_level(logging.WARNING),
    ):
        assert await async_setup_entry(hass, entry)  # nosec

    new_entity_id = "fan.rekuperator_fan"
    new_unique_id = f"{DOMAIN}_{slave_id}_0"
    assert registry.async_get(new_entity_id)  # nosec
    assert registry.entities[new_entity_id].unique_id == new_unique_id  # nosec
    assert old_entity_id not in registry.entities  # nosec
    assert "Legacy fan entity detected" in caplog.text  # nosec
