"""Tests for service helpers ensuring values are scaled when written."""

from datetime import time
from types import SimpleNamespace

import pytest

import custom_components.thessla_green_modbus.services as services
from custom_components.thessla_green_modbus.services import _scale_for_register
from custom_components.thessla_green_modbus.schedule_helpers import time_to_bcd
from custom_components.thessla_green_modbus.const import HOLDING_REGISTERS



class DummyCoordinator:
    """Minimal coordinator stub capturing written values."""

    def __init__(self) -> None:
        self.slave_id = 1
        self.writes = []
        self.available_registers = {"holding_registers": set()}

    async def async_write_register(self, register_name, value, refresh=True) -> None:
        address = HOLDING_REGISTERS[register_name]
        self.writes.append((address, value, self.slave_id))

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
    expected_start = _scale_for_register(
        "schedule_monday_period1_start", time_to_bcd(time(hour=6, minute=30))
    )
    expected_end = _scale_for_register(
        "schedule_monday_period1_end", time_to_bcd(time(hour=8, minute=0))
    )
    expected_flow = _scale_for_register("schedule_monday_period1_flow", 55)
    expected_temp = _scale_for_register("schedule_monday_period1_temp", 21.5)

    assert writes[0] == (
        HOLDING_REGISTERS["schedule_monday_period1_start"],
        0x0630,
        1,
    )  # nosec: B101
    assert writes[1] == (
        HOLDING_REGISTERS["schedule_monday_period1_end"],
        0x0800,
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
