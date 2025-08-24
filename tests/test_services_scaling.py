"""Tests for service helpers ensuring values are encoded when written."""

from datetime import time
from types import SimpleNamespace

import pytest

import custom_components.thessla_green_modbus.services as services
from custom_components.thessla_green_modbus.registers.loader import (
    get_register_definition,
    get_registers_by_function,
)
from custom_components.thessla_green_modbus.const import MAX_BATCH_REGISTERS

HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}


class DummyCoordinator:
    """Minimal coordinator stub capturing written values."""

    def __init__(self, max_registers_per_request: int = MAX_BATCH_REGISTERS) -> None:
        self.slave_id = 1
        self.writes = []
        self.available_registers = {"holding_registers": set()}
        self.max_registers_per_request = max_registers_per_request
        self.effective_batch = min(max_registers_per_request, MAX_BATCH_REGISTERS)

    async def async_write_register(self, register_name, value, refresh=True) -> None:
        address = HOLDING_REGISTERS.get(register_name, 0)
        if isinstance(value, (list, tuple)):
            for offset in range(0, len(value), self.effective_batch):
                chunk = list(value)[offset : offset + self.effective_batch]
                self.writes.append((address + offset, chunk, self.slave_id))
        else:
            self.writes.append((address, value, self.slave_id))
        definition = get_register_definition(register_name)
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

    monkeypatch.setattr(services, "_get_coordinator_from_entity_id", lambda _h, e: coordinator)
    monkeypatch.setattr(
        services, "async_extract_entity_ids", lambda _h, call: call.data["entity_id"]
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

    assert writes[0] == (
        HOLDING_REGISTERS["schedule_monday_period1_start"],
        "06:30",
        1,
    )  # nosec: B101
    assert writes[1] == (
        HOLDING_REGISTERS["schedule_monday_period1_end"],
        "08:00",
        1,
    )  # nosec: B101
    assert writes[2] == (
        HOLDING_REGISTERS["schedule_monday_period1_flow"],
        55,
        1,
    )  # nosec: B101
    assert writes[3] == (
        HOLDING_REGISTERS["schedule_monday_period1_temp"],
        21.5,
        1,
    )  # nosec: B101


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "batch,expected_chunks", [(1, 8), (8, 1), (MAX_BATCH_REGISTERS, 1), (32, 1)]
)
async def test_set_device_name_chunking(monkeypatch, batch, expected_chunks):
    """set_device_name respects configured batch size."""
    hass = SimpleNamespace()
    hass.services = Services()
    coordinator = DummyCoordinator(batch)

    monkeypatch.setattr(services, "_get_coordinator_from_entity_id", lambda _h, e: coordinator)
    monkeypatch.setattr(
        services, "async_extract_entity_ids", lambda _h, call: call.data["entity_id"]
    )
    monkeypatch.setattr(services, "ServiceCall", SimpleNamespace)

    await services.async_setup_services(hass)
    handler = hass.services.handlers["set_device_name"]

    call = SimpleNamespace(
        data={"entity_id": ["climate.device"], "device_name": "ABCDEFGHIJKLMNOP"}
    )

    await handler(call)

    assert len(coordinator.writes) == expected_chunks
    for _addr, values, _ in coordinator.writes:
        if isinstance(values, list):
            assert len(values) <= coordinator.effective_batch
