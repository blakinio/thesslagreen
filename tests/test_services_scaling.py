"""Tests for service helpers ensuring values are encoded when written."""

from datetime import time
from types import SimpleNamespace

import custom_components.thessla_green_modbus.services as services
import pytest
from custom_components.thessla_green_modbus.const import MAX_BATCH_REGISTERS
from custom_components.thessla_green_modbus.registers.loader import (
    get_register_definition,
    get_registers_by_function,
)

# Build a register map similar to what the coordinator exposes.
HOLDING_REGISTERS = {r.name: r.address for r in get_registers_by_function("03")}


class DummyCoordinator:
    """Minimal coordinator stub capturing written values."""

    def __init__(self, max_registers_per_request: int = MAX_BATCH_REGISTERS) -> None:
        self.slave_id = 1
        self.writes: list[tuple[int, object, int]] = []
        self.encoded: list[tuple[int, object, int]] = []
        self.available_registers = {"holding_registers": set()}
        self.max_registers_per_request = max_registers_per_request
        self.effective_batch = min(max_registers_per_request, MAX_BATCH_REGISTERS)

    async def async_write_register(self, register_name, value, refresh=True, *, offset=0) -> bool:
        address = HOLDING_REGISTERS.get(register_name, 0) + offset
        self.writes.append((address, value, self.slave_id))
        try:
            definition = get_register_definition(register_name)
            encoded = definition.encode(value)
            self.encoded.append((address, encoded, self.slave_id))
        except Exception:  # pragma: no cover - defensive
            pass
        return True

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
    coordinator.available_registers["holding_registers"].update(
        {"schedule_summer_mon_1", "setting_summer_mon_1"}
    )

    monkeypatch.setattr(services, "_get_coordinator_from_entity_id", lambda _h, e: coordinator)
    monkeypatch.setattr(
        services, "async_extract_entity_ids", lambda _h, call: call.data["entity_id"]
    )
    monkeypatch.setattr(services, "ServiceCall", SimpleNamespace)

    await services.async_setup_services(hass)
    handler = hass.services.handlers["set_airflow_schedule"]

    call = SimpleNamespace(
        data={
            "entity_id": ["climate.device"],
            "day": "monday",
            "period": 1,
            "start_time": time(hour=6, minute=30),
            "airflow_rate": 55,
            "temperature": 21.5,
        }
    )

    await handler(call)

    writes = coordinator.writes

    assert writes[0] == (
        HOLDING_REGISTERS["schedule_summer_mon_1"],
        "06:30",
        1,
    )  # nosec: B101
    assert writes[1] == (
        HOLDING_REGISTERS["setting_summer_mon_1"],
        14091,
        1,
    )  # nosec: B101


@pytest.mark.asyncio
@pytest.mark.parametrize("batch", [1, 8, MAX_BATCH_REGISTERS, 32])
async def test_set_device_name_passes_full_value(monkeypatch, batch):
    """set_device_name delegates encoding and chunking to coordinator."""
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

    assert len(coordinator.writes) == 1
    assert coordinator.writes[0][1] == "ABCDEFGHIJKLMNOP"


@pytest.mark.asyncio
async def test_write_register_scaling_and_endianness():
    """Values passed to the coordinator are encoded correctly."""

    coordinator = DummyCoordinator()

    await coordinator.async_write_register("required_temperature", 22.5)
    await coordinator.async_write_register("lock_pass", 16909060)

    assert coordinator.encoded[0] == (
        HOLDING_REGISTERS["required_temperature"],
        45,
        1,
    )  # nosec: B101
    assert coordinator.encoded[1] == (
        HOLDING_REGISTERS["lock_pass"],
        [772, 258],
        1,
    )  # nosec: B101


@pytest.mark.asyncio
async def test_write_register_fractional_resolution():
    """Non-integer resolutions are scaled exactly."""

    coordinator = DummyCoordinator()

    await coordinator.async_write_register("dac_supply", 2.44)

    assert coordinator.encoded[0] == (
        HOLDING_REGISTERS["dac_supply"],
        1000,
        1,
    )  # nosec: B101

    reg = get_register_definition("dac_supply")
    assert reg.decode(1000) == pytest.approx(2.44)
