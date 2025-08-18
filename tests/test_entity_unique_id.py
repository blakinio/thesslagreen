from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.thessla_green_modbus import async_setup_entry
from custom_components.thessla_green_modbus.const import (
    DOMAIN,
    CONF_AIRFLOW_UNIT,
    AIRFLOW_UNIT_M3H,
    AIRFLOW_UNIT_PERCENTAGE,
)
from custom_components.thessla_green_modbus.entity import ThesslaGreenEntity


def test_unique_id_colon_replaced():
    """Entity unique_id should replace colons in host with dashes."""
    coordinator = MagicMock()
    coordinator.host = "fd00:1:2::1"
    coordinator.port = 502
    coordinator.slave_id = 10
    coordinator.get_device_info.return_value = {}

    entity = ThesslaGreenEntity(coordinator, "test")
    assert entity.unique_id == f"{DOMAIN}_fd00-1-2--1_502_10_test"  # nosec


def test_unique_id_not_changed_by_airflow_unit():
    """Changing airflow unit should not change unique_id."""
    coordinator = MagicMock()
    coordinator.host = "1.2.3.4"
    coordinator.port = 502
    coordinator.slave_id = 10
    coordinator.get_device_info.return_value = {}
    coordinator.entry = MagicMock()
    coordinator.entry.options = {CONF_AIRFLOW_UNIT: AIRFLOW_UNIT_PERCENTAGE}

    entity = ThesslaGreenEntity(coordinator, "supply_flow_rate")
    uid_percentage = entity.unique_id

    coordinator.entry.options[CONF_AIRFLOW_UNIT] = AIRFLOW_UNIT_M3H
    entity = ThesslaGreenEntity(coordinator, "supply_flow_rate")
    uid_m3h = entity.unique_id

    assert uid_percentage == uid_m3h  # nosec


@pytest.mark.asyncio
async def test_migrate_entity_unique_ids(hass):
    """Existing registry entries with colons should be migrated."""

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
    host = "fd00:1:2::1"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: host, CONF_PORT: 502, "slave_id": 10},
    )

    registry = FakeRegistry()
    old_unique_id = f"{DOMAIN}_{host}_502_10_sensor"
    dummy_entry = DummyEntry("sensor.test", old_unique_id, "sensor", DOMAIN)
    registry.entities[dummy_entry.entity_id] = dummy_entry

    with (
        patch(
            "custom_components.thessla_green_modbus.__init__.er.async_get",
            return_value=registry,
        ),
        patch(
            "custom_components.thessla_green_modbus.__init__.er.async_entries_for_config_entry",
            return_value=list(registry.entities.values()),
        ),
        patch(
            "custom_components.thessla_green_modbus.coordinator.ThesslaGreenModbusCoordinator"
        ) as mock_coordinator_class,
    ):
        coordinator = MagicMock()
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.async_setup = AsyncMock(return_value=True)
        mock_coordinator_class.return_value = coordinator

        assert await async_setup_entry(hass, entry)  # nosec

    new_unique_id = old_unique_id.replace(":", "-")
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, new_unique_id)
    assert entity_id is not None  # nosec
    assert registry.entities[entity_id].unique_id == new_unique_id  # nosec
