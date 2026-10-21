"""Adversarial validation and failure paths for the manufacturer corrections.

Only HA and transport boundaries are mocked. No physical device is accessed.
"""

from __future__ import annotations

from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.const import SPECIAL_FUNCTION_MAP
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.coordinator import schedule as schedule_module
from custom_components.thessla_green_modbus.core.schedule_values import complete_schedule_value
from custom_components.thessla_green_modbus.core.write_path import encode_write_value
from custom_components.thessla_green_modbus.device_profile import (
    configured_device_family,
    validate_filter_command,
)
from custom_components.thessla_green_modbus.register_defs_cache import get_register_definitions
from custom_components.thessla_green_modbus.services.handlers_airing import register_airing_service
from custom_components.thessla_green_modbus.services.handlers_mode import register_mode_services
from custom_components.thessla_green_modbus.services.handlers_parameters import _run_parameter_steps
from custom_components.thessla_green_modbus.services.handlers_schedule import (
    register_schedule_services,
)
from custom_components.thessla_green_modbus.services.helpers import clamp_airflow_rate
from homeassistant.exceptions import ServiceValidationError
from pymodbus.exceptions import ConnectionException


def _coordinator(family="unspecified"):
    entry = MagicMock(options={"device_family": family}, data={}, entry_id="safety-test")
    coordinator = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(), host="localhost", port=502, slave_id=10, name="test", entry=entry
    )
    coordinator._ensure_connection = AsyncMock()
    coordinator._assert_write_connection_ready = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


def _service_setup(register, available=None):
    handlers = {}
    hass = SimpleNamespace(
        services=SimpleNamespace(
            async_register=lambda domain, name, handler, schema: handlers.update({name: handler})
        )
    )
    coordinator = SimpleNamespace(
        device_client=SimpleNamespace(
            available_registers={"holding_registers": set(available or [])}
        ),
        async_request_refresh=AsyncMock(),
    )
    deps = SimpleNamespace(
        domain="thessla_green_modbus",
        normalize_option=lambda value: value,
        day_to_device_key={"monday": "mon"},
        special_function_map=SPECIAL_FUNCTION_MAP,
        iter_target_coordinators=AsyncMock(return_value=[("climate.test", coordinator)]),
        write_register=AsyncMock(return_value=True),
        logger=MagicMock(),
    )
    register(hass, deps)
    return handlers, coordinator, deps


@pytest.mark.parametrize(
    "value,current,expected",
    [
        ({"airflow_pct": 30, "temp_c": 22.5}, None, {"airflow_pct": 30, "temp_c": 22.5}),
        ({"airflow": 40, "temp": 21}, None, {"airflow_pct": 40, "temp_c": 21}),
        ({"airflow_pct": 30}, {"temp_c": 19.5}, {"airflow_pct": 30, "temp_c": 19.5}),
    ],
)
def test_aatt_dict_preserves_explicit_or_fresh_temperature(value, current, expected):
    assert complete_schedule_value(value, current) == expected


@pytest.mark.parametrize(
    "value,current", [({}, {"temp_c": 20}), ({"airflow_pct": 30}, None), ({"temp_c": 22}, None)]
)
def test_incomplete_aatt_dictionary_is_rejected(value, current):
    with pytest.raises(ValueError, match="known temperature"):
        complete_schedule_value(value, current)


@pytest.mark.parametrize(
    "data,value,expected",
    [
        (None, 200, 150),
        ({}, -1, 0),
        ({"min_percentage": 20, "max_percentage": 80}, 5, 20),
        ({"min_percentage": 20, "max_percentage": 80}, 90, 80),
        ({"min_percentage": 20, "max_percentage": 80}, 50, 50),
        ({"min_percentage": "bad", "max_percentage": "bad"}, 200, 150),
        ({"min_percentage": [], "max_percentage": {}}, -10, 0),
        ({"min_percentage": -20, "max_percentage": 300}, 250, 150),
        ({"min_percentage": 40, "max_percentage": 20}, 10, 40),
    ],
)
def test_airflow_clamp_respects_limits_and_missing_data(data, value, expected):
    assert clamp_airflow_rate(SimpleNamespace(data=data), value) == expected


@pytest.mark.parametrize("value", [True, False, "17", None, [], 2.5])
def test_filter_command_rejects_nonintegral_inputs(value):
    with pytest.raises(ValueError, match="integer"):
        validate_filter_command("airpack4", value)


def test_unrecognized_family_does_not_guess_from_equipment():
    assert configured_device_family(SimpleNamespace()) == "unspecified"
    assert (
        configured_device_family(
            SimpleNamespace(entry=SimpleNamespace(options={"device_family": "400h"}))
        )
        == "unspecified"
    )


@pytest.mark.parametrize("value", [[1, True], [1, -1], [1, 65536], [1, "2"], [1, None]])
def test_raw_multiword_encoder_rejects_invalid_words_without_truncation(value):
    definition = SimpleNamespace(length=2)
    assert encode_write_value("test", definition, value, 0) == (None, None)


@pytest.mark.parametrize("offset", [-1, 2, 3])
def test_invalid_offset_is_rejected_before_encoder(offset):
    definition = SimpleNamespace(length=2, encode=MagicMock())
    assert encode_write_value("test", definition, 1, offset) == (None, None)
    definition.encode.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,available,message",
    [
        ({"schedule": "winter", "enabled": False}, [], "requires a day"),
        ({"schedule": "manual", "enabled": False}, [], "unavailable"),
    ],
)
async def test_airing_validation_never_writes(payload, available, message):
    handlers, coordinator, deps = _service_setup(register_airing_service, available)
    with pytest.raises(ServiceValidationError, match=message):
        await handlers["set_airing_schedule"](SimpleNamespace(data=payload))
    deps.write_register.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,message",
    [
        ({"mode": "eco"}, "Unsupported"),
        ({"mode": "hood", "duration": 3}, "No documented duration"),
    ],
)
async def test_undocumented_mode_and_duration_fail_before_write(payload, message):
    handlers, coordinator, deps = _service_setup(register_mode_services)
    with pytest.raises(ServiceValidationError, match=message):
        await handlers["set_special_mode"](SimpleNamespace(data=payload))
    deps.write_register.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra",
    [
        {"airflow_rate": 30},
        {"start_time": time(6, 30)},
        {"start_time": time(6, 30), "airflow_rate": 30, "temperature": 22.25},
        {"start_time": time(6, 30), "airflow_rate": 30, "temperature": float("nan")},
    ],
)
async def test_invalid_schedule_request_never_partially_activates(extra):
    handlers, coordinator, deps = _service_setup(
        register_schedule_services, get_register_definitions()
    )
    with pytest.raises(ServiceValidationError):
        await handlers["set_airflow_schedule"](
            SimpleNamespace(data={"day": "monday", "period": 1, **extra})
        )
    deps.write_register.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.parametrize(
    "family,value,accepted",
    [
        ("airpack_home", 1, True),
        ("airpack_home", 17, False),
        ("airpack4", 17, True),
        ("airpack4", 33, True),
        ("airpack4", 4, False),
        ("unspecified", 1, False),
    ],
)
def test_raw_filter_write_is_profile_gated_before_transport(family, value, accepted):
    coordinator = _coordinator(family)
    assert coordinator._validate_multi_register_write_request(8191, [value], False) is accepted
    coordinator._ensure_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_aatt_needs_no_preservation_read(monkeypatch):
    coordinator = _coordinator()
    coordinator._locked_read_holding_registers = AsyncMock()
    captured = []

    async def write(c, definition, plan, refresh):
        assert c.device_client._write_lock.locked()
        captured.append(plan.scalar_value)
        return True, False

    monkeypatch.setattr(schedule_module, "run_single_write_attempts", write)
    assert await coordinator.async_write_register(
        "setting_summer_mon_1",
        {"airflow_pct": 30, "temp_c": 22},
        refresh=False,
        targeted_readback=False,
    )
    assert captured == [0x1E2C]
    coordinator._locked_read_holding_registers.assert_not_awaited()


@pytest.mark.asyncio
async def test_readback_without_transport_reports_missing_data():
    coordinator = _coordinator()
    coordinator.device_client._transport = None
    coordinator.device_client.client = None
    async with coordinator.device_client._write_lock:
        assert await coordinator._locked_read_holding_registers(72, 1) is None


@pytest.mark.asyncio
async def test_write_readback_rejects_readonly_before_connection():
    coordinator = _coordinator()
    assert await coordinator.async_write_and_read_holding_registers(8190, [44], 1) == (False, None)
    coordinator._ensure_connection.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, ConnectionException("lost")])
async def test_write_readback_failure_does_not_read_or_report_success(monkeypatch, failure):
    coordinator = _coordinator()
    writer = (
        AsyncMock(side_effect=failure)
        if isinstance(failure, Exception)
        else AsyncMock(return_value=(False, False))
    )
    monkeypatch.setattr(schedule_module, "run_multi_register_write_attempts", writer)
    coordinator._locked_read_holding_registers = AsyncMock()
    assert await coordinator.async_write_and_read_holding_registers(
        4400, [2, 30, 1], 3, require_single_request=True
    ) == (False, None)
    coordinator._locked_read_holding_registers.assert_not_awaited()
    assert not coordinator.device_client._write_lock.locked()


@pytest.mark.asyncio
async def test_parameters_validate_all_values_before_first_write():
    _handlers, coordinator, deps = _service_setup(
        register_mode_services, ["bypass_off", "min_bypass_temperature"]
    )
    steps = [
        ("min_bypass_temperature", 10, False, "error %s"),
        ("bypass_off", 999, False, "error %s"),
    ]
    with pytest.raises(ServiceValidationError, match="Invalid value for bypass_off"):
        await _run_parameter_steps(
            object(), SimpleNamespace(data={}), deps, steps, "test", "test %s"
        )
    deps.write_register.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejected_parameter_write_does_not_refresh_or_log_success():
    _handlers, coordinator, deps = _service_setup(register_mode_services, ["bypass_off"])
    deps.write_register.return_value = False
    await _run_parameter_steps(
        object(),
        SimpleNamespace(data={}),
        deps,
        [("bypass_off", 0, False, "error %s")],
        "test",
        "success %s",
    )
    deps.write_register.assert_awaited_once()
    coordinator.async_request_refresh.assert_not_awaited()
    deps.logger.info.assert_not_called()
