# mypy: ignore-errors
"""Tests for service helper mappings."""

from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import ANY, AsyncMock
from unittest.mock import call as call_obj

import pytest
from custom_components.thessla_green_modbus import services as services_module
from custom_components.thessla_green_modbus.services import AIR_QUALITY_REGISTER_MAP


def test_air_quality_register_map():
    """Verify correct mapping of air quality parameters to register names."""
    assert AIR_QUALITY_REGISTER_MAP["co2_low"] == "co2_threshold_low"
    assert AIR_QUALITY_REGISTER_MAP["co2_medium"] == "co2_threshold_medium"
    assert AIR_QUALITY_REGISTER_MAP["co2_high"] == "co2_threshold_high"
    assert AIR_QUALITY_REGISTER_MAP["humidity_target"] == "humidity_target"


def test_get_coordinator_from_entity_id_multiple_devices():
    """Ensure coordinator lookup maps entities to correct coordinators via runtime_data."""
    from unittest.mock import MagicMock

    hass = MagicMock()
    coord1 = object()
    coord2 = object()

    entry1 = SimpleNamespace(runtime_data=coord1)
    entry2 = SimpleNamespace(runtime_data=coord2)

    class DummyConfigEntries:
        _entries: ClassVar[dict[str, SimpleNamespace]] = {"entry1": entry1, "entry2": entry2}

        def async_get_entry(self, entry_id):
            return self._entries.get(entry_id)

    hass.config_entries = DummyConfigEntries()

    class DummyRegistry:
        def __init__(self, mapping):
            self._mapping = mapping

        def async_get(self, entity_id):
            return self._mapping.get(entity_id)

    hass.entity_registry = DummyRegistry(
        {
            "sensor.dev1": SimpleNamespace(config_entry_id="entry1"),
            "sensor.dev2": SimpleNamespace(config_entry_id="entry2"),
        }
    )

    assert services_module._get_coordinator_from_entity_id(hass, "sensor.dev1") is coord1
    assert services_module._get_coordinator_from_entity_id(hass, "sensor.dev2") is coord2


class Services:
    """Minimal service registry for tests."""

    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}

    def async_register(self, _domain, service, handler, _schema):  # pragma: no cover
        self.handlers[service] = handler


class DummyCoordinator:
    """Coordinator stub capturing offset writes."""

    def __init__(self) -> None:
        self.async_write_register = AsyncMock(return_value=True)
        self.effective_batch = 2

    async def async_request_refresh(self) -> None:  # pragma: no cover - stub
        pass


@pytest.mark.asyncio
async def test_set_device_name_uses_offsets(monkeypatch):
    """Service chunks multi-register writes with offsets."""

    hass = SimpleNamespace()
    hass.services = Services()
    coordinator = DummyCoordinator()

    monkeypatch.setattr(
        services_module,
        "_get_coordinator_from_entity_id",
        lambda _h, _e: coordinator,
    )
    monkeypatch.setattr(
        services_module,
        "async_extract_entity_ids",
        lambda _h, call: call.data["entity_id"],
    )
    monkeypatch.setattr(services_module, "ServiceCall", SimpleNamespace)

    await services_module.async_setup_services(hass)
    handler = hass.services.handlers["set_device_name"]

    call = SimpleNamespace(data={"entity_id": ["climate.dev"], "device_name": "ABCDEFGH"})

    await handler(call)

    coordinator.async_write_register.assert_has_calls(
        [
            call_obj("device_name", ANY, refresh=False, offset=0),
            call_obj("device_name", ANY, refresh=False, offset=2),
        ]
    )
