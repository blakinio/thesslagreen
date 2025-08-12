"""Tests for service helpers ensuring values are scaled when written."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.thessla_green_modbus.coordinator import (
    ThesslaGreenModbusCoordinator,
)
from custom_components.thessla_green_modbus.const import (
    HOLDING_REGISTERS,
    REGISTER_MULTIPLIERS,
)
import custom_components.thessla_green_modbus.services as services


class DummyClient:
    """Simple Modbus client stub capturing written values."""

    def __init__(self):
        self.writes = []

    async def write_register(self, address, value, slave):
        self.writes.append((address, value, slave))

        class Response:
            def isError(self):
                return False

        return Response()


class Services:
    """Minimal service registry for tests."""

    def __init__(self):
        self.handlers = {}

    def async_register(self, domain, service, handler, schema):  # pragma: no cover
        self.handlers[service] = handler


@pytest.mark.asyncio
async def test_temperature_curve_service_scaling(monkeypatch):
    """Ensure set_temperature_curve writes scaled values to Modbus."""

    hass = SimpleNamespace()
    hass.services = Services()

    coordinator = ThesslaGreenModbusCoordinator(
        hass, "host", 502, 1, "dev", timedelta(seconds=1)
    )
    coordinator.client = DummyClient()
    coordinator._ensure_connection = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()

    # Patch service helpers to return our coordinator and entity IDs
    monkeypatch.setattr(
        services, "_get_coordinator_from_entity_id", lambda h, e: coordinator
    )
    monkeypatch.setattr(
        services, "async_extract_entity_ids", lambda h, call: call.data["entity_id"]
    )

    await services.async_setup_services(hass)
    handler = hass.services.handlers["set_temperature_curve"]

    call = SimpleNamespace(
        data={
            "entity_id": ["climate.device"],
            "slope": 2.5,
            "offset": 1.0,
            "max_supply_temp": 45.0,
            "min_supply_temp": 20.0,
        }
    )

    await handler(call)

    client_writes = coordinator.client.writes

    expected_slope = int(round(2.5 / REGISTER_MULTIPLIERS["heating_curve_slope"]))
    expected_offset = int(round(1.0 / REGISTER_MULTIPLIERS["heating_curve_offset"]))
    expected_max = int(round(45.0 / REGISTER_MULTIPLIERS["max_supply_temperature"]))
    expected_min = int(round(20.0 / REGISTER_MULTIPLIERS["min_supply_temperature"]))

    assert client_writes[0] == (
        HOLDING_REGISTERS["heating_curve_slope"],
        expected_slope,
        coordinator.slave_id,
    )
    assert client_writes[1] == (
        HOLDING_REGISTERS["heating_curve_offset"],
        expected_offset,
        coordinator.slave_id,
    )
    assert client_writes[2] == (
        HOLDING_REGISTERS["max_supply_temperature"],
        expected_max,
        coordinator.slave_id,
    )
    assert client_writes[3] == (
        HOLDING_REGISTERS["min_supply_temperature"],
        expected_min,
        coordinator.slave_id,
    )
