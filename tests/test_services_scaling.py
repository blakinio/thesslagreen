"""Tests for service helpers ensuring values are encoded when written."""

from datetime import time
from types import SimpleNamespace

import pytest

import custom_components.thessla_green_modbus.services as services
from custom_components.thessla_green_modbus import loader
from custom_components.thessla_green_modbus.registers.loader import (
    get_registers_by_function,
)

HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}


class DummyCoordinator:
    """Minimal coordinator stub capturing written values."""

    def __init__(self) -> None:
        self.slave_id = 1
        self.writes = []
        self.available_registers = {"holding_registers": set()}

    async def async_write_register(self, register_name, value, refresh=True) -> None:
        definition = loader.get_register_definition(register_name)
        encoded = definition.encode(value)
        address = HOLDING_REGISTERS[register_name]
        self.writes.append((address, encoded, self.slave_id))

    async def async_request_refresh(self) -> None:  # pragma: no cover - no behaviour
        pass


class Services:
    """Minimal service registry for tests."""

    def __init__(self) -> None:
        self.handlers = {}

    def async_register(self, domain, service, handler, schema):  # pragma: no cover
        self.handlers[service] = handler


@pytest.mark.asyncio
async def test_airflow_schedule_service_passes_user_values(monkeypatch):
    """Ensure set_airflow_schedule passes user values to coordinator."""

    hass = SimpleNamespace()
    hass.services = Services()
    coordinator = DummyCoordinator()

    monkeypatch.setattr(services, "_get_coordinator_from_entity_id", lambda h, e: coordinator)
    monkeypatch.setattr(
        services, "async_extract_entity_ids", lambda h, call: call.data["entity_id"]
    )

    await services.async_setup_services(hass)
    handler = hass.services.handlers["set_airflow_schedule"]

    call = SimpleNamespace(
        data={
            "entity_id": ["climate.device"],
            "day": "monday",
            "period": "1",
            "start_time": time(hour=6, minute=30),
            "end_time": time(hour=8, minute=0),
            "airflow_rate": 55,
            "temperature": 21.5,
        }
    )

    await handler(call)

    writes = coordinator.writes

    expected_start = loader.get_register_definition("schedule_monday_period1_start").encode("06:30")
    expected_end = loader.get_register_definition("schedule_monday_period1_end").encode("08:00")
    expected_flow = loader.get_register_definition("schedule_monday_period1_flow").encode(55)
    expected_temp = loader.get_register_definition("schedule_monday_period1_temp").encode(21.5)

    assert writes[0] == (
        HOLDING_REGISTERS["schedule_monday_period1_start"],
        expected_start,
        1,
    )  # nosec: B101
    assert writes[1] == (
        HOLDING_REGISTERS["schedule_monday_period1_end"],
        expected_end,
        1,
    )  # nosec: B101
    assert writes[2] == (
        HOLDING_REGISTERS["schedule_monday_period1_flow"],
        expected_flow,
        1,
    )  # nosec: B101
    assert writes[3] == (
        HOLDING_REGISTERS["schedule_monday_period1_temp"],
        expected_temp,
        1,
    )  # nosec: B101
