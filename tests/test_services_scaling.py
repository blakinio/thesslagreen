"""Tests for service helpers ensuring values are scaled when written."""

from datetime import time
from types import SimpleNamespace

import pytest

from custom_components.thessla_green_modbus.const import HOLDING_REGISTERS
import custom_components.thessla_green_modbus.services as services
from custom_components.thessla_green_modbus.services import _scale_for_register


class DummyCoordinator:
    """Minimal coordinator stub capturing written values."""

    def __init__(self) -> None:
        self.slave_id = 1
        self.writes = []
        self.available_registers = {"holding_registers": set()}

    async def async_write_register(self, register_name, value) -> None:
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
async def test_temperature_curve_service_scaling(monkeypatch):
    """Ensure set_temperature_curve writes scaled values to Modbus."""

    hass = SimpleNamespace()
    hass.services = Services()
    coordinator = DummyCoordinator()

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

    writes = coordinator.writes
    expected_slope = _scale_for_register("heating_curve_slope", 2.5)
    expected_offset = _scale_for_register("heating_curve_offset", 1.0)
    expected_max = _scale_for_register("max_supply_temperature", 45.0)
    expected_min = _scale_for_register("min_supply_temperature", 20.0)

    assert writes[0] == (HOLDING_REGISTERS["heating_curve_slope"], expected_slope, 1)
    assert writes[1] == (HOLDING_REGISTERS["heating_curve_offset"], expected_offset, 1)
    assert writes[2] == (HOLDING_REGISTERS["max_supply_temperature"], expected_max, 1)
    assert writes[3] == (HOLDING_REGISTERS["min_supply_temperature"], expected_min, 1)


@pytest.mark.asyncio
async def test_bypass_parameters_service_scaling(monkeypatch):
    """Ensure set_bypass_parameters writes scaled values."""

    hass = SimpleNamespace()
    hass.services = Services()
    coordinator = DummyCoordinator()

    monkeypatch.setattr(
        services, "_get_coordinator_from_entity_id", lambda h, e: coordinator
    )
    monkeypatch.setattr(
        services, "async_extract_entity_ids", lambda h, call: call.data["entity_id"]
    )

    await services.async_setup_services(hass)
    handler = hass.services.handlers["set_bypass_parameters"]

    call = SimpleNamespace(
        data={
            "entity_id": ["climate.device"],
            "mode": "auto",
            "temperature_threshold": 20.5,
            "hysteresis": 2.5,
        }
    )

    await handler(call)

    writes = coordinator.writes
    expected_mode = _scale_for_register("bypass_mode", 0)
    expected_temp = _scale_for_register("bypass_temperature_threshold", 20.5)
    expected_hyst = _scale_for_register("bypass_hysteresis", 2.5)

    assert writes[0] == (HOLDING_REGISTERS["bypass_mode"], expected_mode, 1)
    assert writes[1] == (
        HOLDING_REGISTERS["bypass_temperature_threshold"],
        expected_temp,
        1,
    )
    assert writes[2] == (HOLDING_REGISTERS["bypass_hysteresis"], expected_hyst, 1)


@pytest.mark.asyncio
async def test_gwc_parameters_service_scaling(monkeypatch):
    """Ensure set_gwc_parameters writes scaled values."""

    hass = SimpleNamespace()
    hass.services = Services()
    coordinator = DummyCoordinator()

    monkeypatch.setattr(
        services, "_get_coordinator_from_entity_id", lambda h, e: coordinator
    )
    monkeypatch.setattr(
        services, "async_extract_entity_ids", lambda h, call: call.data["entity_id"]
    )

    await services.async_setup_services(hass)
    handler = hass.services.handlers["set_gwc_parameters"]

    call = SimpleNamespace(
        data={
            "entity_id": ["climate.device"],
            "mode": "auto",
            "temperature_threshold": 5.0,
            "hysteresis": 1.5,
        }
    )

    await handler(call)

    writes = coordinator.writes
    expected_mode = _scale_for_register("gwc_mode", 1)
    expected_temp = _scale_for_register("gwc_temperature_threshold", 5.0)
    expected_hyst = _scale_for_register("gwc_hysteresis", 1.5)

    assert writes[0] == (HOLDING_REGISTERS["gwc_mode"], expected_mode, 1)
    assert writes[1] == (
        HOLDING_REGISTERS["gwc_temperature_threshold"],
        expected_temp,
        1,
    )
    assert writes[2] == (HOLDING_REGISTERS["gwc_hysteresis"], expected_hyst, 1)


@pytest.mark.asyncio
async def test_airflow_schedule_service_scaling(monkeypatch):
    """Ensure set_airflow_schedule scales values before writing."""

    hass = SimpleNamespace()
    hass.services = Services()
    coordinator = DummyCoordinator()

    monkeypatch.setattr(
        services, "_get_coordinator_from_entity_id", lambda h, e: coordinator
    )
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
    expected_start = _scale_for_register("schedule_monday_period1_start", 630)
    expected_end = _scale_for_register("schedule_monday_period1_end", 800)
    expected_flow = _scale_for_register("schedule_monday_period1_flow", 55)
    expected_temp = _scale_for_register("schedule_monday_period1_temp", 21.5)

    assert writes[0] == (
        HOLDING_REGISTERS["schedule_monday_period1_start"],
        expected_start,
        1,
    )
    assert writes[1] == (
        HOLDING_REGISTERS["schedule_monday_period1_end"],
        expected_end,
        1,
    )
    assert writes[2] == (
        HOLDING_REGISTERS["schedule_monday_period1_flow"],
        expected_flow,
        1,
    )
    assert writes[3] == (
        HOLDING_REGISTERS["schedule_monday_period1_temp"],
        expected_temp,
        1,
    )

