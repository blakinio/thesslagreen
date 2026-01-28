import sys
from dataclasses import dataclass, field
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.thessla_green_modbus import async_setup_entry
from custom_components.thessla_green_modbus.const import (
    AIRFLOW_UNIT_M3H,
    AIRFLOW_UNIT_PERCENTAGE,
    CONF_AIRFLOW_UNIT,
    DOMAIN,
)
from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity


def _create_coordinator(
    *,
    serial: str | None,
    host: str,
    port: int,
    slave_id: int = 10,
):
    coordinator = MagicMock()
    coordinator.slave_id = slave_id
    coordinator.host = host
    coordinator.port = port
    coordinator.device_info = {"serial_number": serial} if serial else {}
    coordinator.get_device_info.return_value = coordinator.device_info
    return coordinator


def test_unique_id_uses_serial_prefix():
    """Unique ID should include the device serial when available."""

    coordinator = _create_coordinator(serial="SN123", host="192.0.2.10", port=502)

    entity = ThesslaGreenEntity(coordinator, "test", 1)
    assert entity.unique_id == "SN123_10_test_1"  # nosec


def test_unique_id_varies_with_address():
    """Different addresses produce different unique IDs."""

    coordinator = _create_coordinator(serial="SN123", host="192.0.2.10", port=502)

    entity = ThesslaGreenEntity(coordinator, "test", 1)
    assert entity.unique_id == "SN123_10_test_1"  # nosec
    entity = ThesslaGreenEntity(coordinator, "test", 2)
    assert entity.unique_id == "SN123_10_test_2"  # nosec


def test_unique_id_falls_back_to_host_and_port():
    """When serial is unavailable the host/port should form the prefix."""

    coordinator = _create_coordinator(serial=None, host="fd00:1:2::1", port=1502)

    entity = ThesslaGreenEntity(coordinator, "test", 1)
    assert entity.unique_id == "fd00-1-2-1-1502_10_test_1"  # nosec


def test_unique_id_not_changed_by_airflow_unit():
    """Changing airflow unit should not change unique_id."""

    coordinator = _create_coordinator(serial=None, host="192.0.2.5", port=502)
    coordinator.entry = MagicMock()
    coordinator.entry.options = {CONF_AIRFLOW_UNIT: AIRFLOW_UNIT_PERCENTAGE}

    entity = ThesslaGreenEntity(coordinator, "supply_flow_rate", 274)
    uid_percentage = entity.unique_id

    coordinator.entry.options[CONF_AIRFLOW_UNIT] = AIRFLOW_UNIT_M3H
    entity = ThesslaGreenEntity(coordinator, "supply_flow_rate", 274)
    uid_m3h = entity.unique_id

    assert uid_percentage == uid_m3h  # nosec


def test_unique_ids_distinct_for_same_slave_id_across_coordinators():
    """Coordinators with the same slave ID should still have unique IDs."""

    coordinator_one = _create_coordinator(serial=None, host="192.0.2.10", port=502, slave_id=7)
    coordinator_two = _create_coordinator(serial=None, host="192.0.2.11", port=502, slave_id=7)

    entity_one = ThesslaGreenEntity(coordinator_one, "test", 1)
    entity_two = ThesslaGreenEntity(coordinator_two, "test", 1)

    assert entity_one.unique_id != entity_two.unique_id  # nosec


@pytest.mark.asyncio
async def test_migrate_entity_unique_ids(hass):
    """Existing registry entries should migrate to new format."""

    @dataclass
    class DummyEntry:
        entity_id: str
        unique_id: str
        domain: str
        platform: str

    class FakeRegistry:
        def __init__(self):
            self.entities: dict[str, DummyEntry] = {}

        def async_get_entity_id(self, domain, platform, unique_id):
            for eid, entry in self.entities.items():
                if (
                    entry.domain == domain
                    and entry.platform == platform
                    and entry.unique_id == unique_id
                ):
                    return eid
            return None

        def async_update_entity(self, entity_id, *, new_unique_id):
            self.entities[entity_id].unique_id = new_unique_id

        def async_get(self, entity_id):
            return self.entities.get(entity_id)

    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_reload = AsyncMock()
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    hass.data = {}
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    host = "fd00:1:2::1"
    port = 502
    slave_id = 10

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

    registry = FakeRegistry()
    address = 274
    old_unique_id = f"{DOMAIN}_{host}_{port}_{slave_id}_supply_flow_rate"
    dummy_entry = DummyEntry("sensor.test", old_unique_id, "sensor", DOMAIN)
    registry.entities[dummy_entry.entity_id] = dummy_entry

    entity_registry_module = ModuleType("homeassistant.helpers.entity_registry")
    entity_registry_module.async_get = MagicMock(return_value=registry)
    entity_registry_module.async_entries_for_config_entry = MagicMock(
        return_value=list(registry.entities.values())
    )
    helpers_module = ModuleType("homeassistant.helpers")
    helpers_module.entity_registry = entity_registry_module
    homeassistant_module = ModuleType("homeassistant")
    homeassistant_module.helpers = helpers_module

    with (
        patch.dict(
            sys.modules,
            {
                "homeassistant": homeassistant_module,
                "homeassistant.helpers": helpers_module,
                "homeassistant.helpers.entity_registry": entity_registry_module,
            },
        ),
        patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator"
        ) as mock_coordinator_class,
    ):
        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.async_setup = AsyncMock(return_value=True)
        coordinator.host = host
        coordinator.port = port
        coordinator.slave_id = slave_id
        coordinator.device_info = {"serial_number": "ABC123"}
        coordinator.get_device_info.return_value = coordinator.device_info
        mock_coordinator_class.return_value = coordinator

        assert await async_setup_entry(hass, entry)  # nosec

    new_unique_id = f"ABC123_{slave_id}_supply_flow_rate_{address}"
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, new_unique_id)
    assert entity_id is not None  # nosec
    assert registry.entities[entity_id].unique_id == new_unique_id  # nosec


def test_unique_id_bit_suffix():
    """Bit-based entities should include bit position in unique_id."""
    coordinator = _create_coordinator(serial="SN123", host="192.0.2.5", port=502)

    entity = ThesslaGreenEntity(coordinator, "test", 5, bit=4)
    assert entity.unique_id == "SN123_10_test_5_bit4"  # nosec
