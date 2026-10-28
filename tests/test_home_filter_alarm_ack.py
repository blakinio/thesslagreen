"""Regression coverage for the acknowledgement observed on Home firmware 3.11."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from custom_components.thessla_green_modbus.services.handlers_filter_alarms import (
    DIAGNOSTIC_REGISTERS,
    RESET_FILTER_ALARMS_SCHEMA,
    acknowledge_filter_alarms,
    register_filter_alarm_services,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


def coordinator(reads, firmware="3.11", family="airpack_home"):
    return SimpleNamespace(
        entry=SimpleNamespace(options={"device_family": family}),
        _device_client=SimpleNamespace(
            _write_lock=asyncio.Lock(), device_info={"firmware": firmware}
        ),
        _ensure_connection=AsyncMock(),
        _locked_read_holding_registers=AsyncMock(side_effect=reads),
        _locked_single_register_write=AsyncMock(return_value=(True, False)),
        _write_holding_multi=AsyncMock(return_value=(object(), True)),
        async_request_refresh=AsyncMock(),
    )


@pytest.mark.parametrize("firmware", ["3.11", "v3.11.0", " 3.11 "])
@pytest.mark.parametrize("code,address,name", [("S17", 8209, "s_17"), ("E252", 8444, "e_252")])
@pytest.mark.parametrize("method", ["single", "multiple"])
async def test_311_writes_ack_one_and_requires_state_zero(firmware, code, address, name, method):
    """The command value is 1, while the successful resulting state is 0."""
    device = coordinator([[1], [1], [0]], firmware)
    assert await acknowledge_filter_alarms(device, [code], method) == {name: 0}
    if method == "single":
        device._locked_single_register_write.assert_awaited_once_with(
            register_name=name, value=1, offset=0, refresh=False
        )
        device._write_holding_multi.assert_not_awaited()
    else:
        device._write_holding_multi.assert_awaited_once_with(address, [1], 1)
        device._locked_single_register_write.assert_not_awaited()
    device.async_request_refresh.assert_awaited_once()


@pytest.mark.parametrize("firmware", ["4.84", "3.10", "3.110", "Unknown", ""])
async def test_other_firmware_keeps_existing_ack_value(firmware):
    device = coordinator([[1], [1], [0]], firmware)
    await acknowledge_filter_alarms(device, ["S17"])
    assert device._locked_single_register_write.call_args.kwargs["value"] == 0


@pytest.mark.parametrize("method", ["single", "multiple"])
async def test_inactive_alarm_is_never_written(method):
    """Do not turn a write-one acknowledgement into a new alarm assertion."""
    device = coordinator([[1], [0], [0], [0], [0]])
    await acknowledge_filter_alarms(device, ["S17", "E252"], method)
    device._locked_single_register_write.assert_not_awaited()
    device._write_holding_multi.assert_not_awaited()


async def test_echoed_acknowledgement_without_clear_is_failure():
    device = coordinator([[1], [1], [1]])
    with pytest.raises(HomeAssistantError, match=r"after=\[1\]"):
        await acknowledge_filter_alarms(device, ["S17"])
    assert device._locked_single_register_write.await_count == 1
    device.async_request_refresh.assert_not_awaited()


@pytest.mark.parametrize("system", [1, 2])
async def test_acknowledgement_preserves_filter_system_and_deduplicates(system):
    device = coordinator([[system], [1], [0]])
    await acknowledge_filter_alarms(device, ["S17", "S17"])
    device._locked_single_register_write.assert_awaited_once()
    assert device._locked_single_register_write.call_args.kwargs["register_name"] == "s_17"
    assert [call.args[0] for call in device._locked_read_holding_registers.call_args_list] == [
        8191,
        8209,
        8209,
    ]


@pytest.mark.parametrize("reads", [[None], [[0]], [[9]], [[1], None], [[1], [2]]])
async def test_invalid_configuration_or_alarm_read_sends_no_write(reads):
    device = coordinator(reads)
    with pytest.raises(HomeAssistantError):
        await acknowledge_filter_alarms(device, ["S17"])
    device._locked_single_register_write.assert_not_awaited()
    device._write_holding_multi.assert_not_awaited()


@pytest.mark.parametrize("codes", [[], ["S10"], ["S17", "S30"]])
async def test_unrelated_alarms_are_rejected_before_io(codes):
    device = coordinator([])
    with pytest.raises(ServiceValidationError):
        await acknowledge_filter_alarms(device, codes)
    device._ensure_connection.assert_not_awaited()


async def test_airpack4_is_not_given_home_commands():
    device = coordinator([], family="airpack4")
    with pytest.raises(ServiceValidationError):
        await acknowledge_filter_alarms(device, ["S17"])
    device._ensure_connection.assert_not_awaited()


async def test_failed_write_is_not_retried_by_service():
    device = coordinator([[1], [1]])
    device._locked_single_register_write.return_value = (False, False)
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await acknowledge_filter_alarms(device, ["S17"])
    assert device._locked_single_register_write.await_count == 1


def test_schema_requires_physical_replacement_confirmation():
    with pytest.raises(vol.Invalid):
        RESET_FILTER_ALARMS_SCHEMA(
            {
                "entity_id": "climate.unit",
                "device_family": "airpack_home",
                "confirm_filters_replaced": False,
                "codes": ["S17"],
            }
        )


def handlers_for(devices):
    handlers = {}

    def register(_domain, name, handler, _schema, **_kwargs):
        handlers[name] = handler

    hass = SimpleNamespace(services=SimpleNamespace(async_register=register))
    deps = SimpleNamespace(
        domain="thessla_green_modbus", iter_target_coordinators=AsyncMock(return_value=devices)
    )
    register_filter_alarm_services(hass, deps)
    return handlers


@pytest.mark.parametrize("count", [0, 2])
async def test_service_requires_one_physical_device(count):
    devices = [(f"climate.unit_{index}", coordinator([])) for index in range(count)]
    handlers = handlers_for(devices)
    with pytest.raises(ServiceValidationError, match="exactly one"):
        await handlers["reset_filter_alarms"](
            SimpleNamespace(
                data={
                    "device_family": "airpack_home",
                    "confirm_filters_replaced": True,
                    "codes": ["S17"],
                }
            )
        )


async def test_diagnostics_reads_actual_registers_without_writes():
    device = coordinator([[1]] * len(DIAGNOSTIC_REGISTERS))
    handlers = handlers_for([("climate.unit", device)])
    result = await handlers["filter_alarm_diagnostics"](SimpleNamespace(data={}))
    assert result["writes_sent"] == 0
    assert result["registers"] == dict.fromkeys(DIAGNOSTIC_REGISTERS, 1)
    assert [call.args[0] for call in device._locked_read_holding_registers.call_args_list] == list(
        DIAGNOSTIC_REGISTERS.values()
    )
    device._locked_single_register_write.assert_not_awaited()
    device._write_holding_multi.assert_not_awaited()


async def test_unknown_write_method_rejected_before_io():
    device = coordinator([])
    with pytest.raises(ServiceValidationError, match="write function"):
        await acknowledge_filter_alarms(device, ["S17"], "unsupported")
    device._ensure_connection.assert_not_awaited()


async def test_service_success_and_confirmation_guards():
    device = coordinator([[1], [0], [0]])
    handlers = handlers_for([("climate.unit", device)])
    await handlers["reset_filter_alarms"](
        SimpleNamespace(
            data={
                "device_family": "airpack_home",
                "confirm_filters_replaced": True,
                "codes": ["S17"],
            }
        )
    )
    device.async_request_refresh.assert_awaited_once()
    with pytest.raises(ServiceValidationError, match="physical filter replacement"):
        await handlers["reset_filter_alarms"](SimpleNamespace(data={}))


async def test_diagnostics_rejects_multiple_devices():
    handlers = handlers_for([("climate.a", coordinator([])), ("climate.b", coordinator([]))])
    with pytest.raises(ServiceValidationError, match="exactly one"):
        await handlers["filter_alarm_diagnostics"](SimpleNamespace(data={}))
