"""Reproductions for independent prompt-only review of commit 72ea775."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.thessla_green_modbus.coordinator import ThesslaGreenModbusCoordinator
from custom_components.thessla_green_modbus.coordinator import update as update_module
from custom_components.thessla_green_modbus.coordinator.schedule_service import (
    async_write_schedule_slot,
)
from custom_components.thessla_green_modbus.register_defs_cache import get_register_definitions
from custom_components.thessla_green_modbus.services.handlers_maintenance import (
    _build_start_pressure_test_handler,
)
from custom_components.thessla_green_modbus.utils import decode_aatt
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pymodbus.exceptions import ConnectionException


def _schedule_coordinator():
    coordinator = ThesslaGreenModbusCoordinator.from_params(
        hass=MagicMock(), host="localhost", port=502, slave_id=10, name="review"
    )
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_waiting_update_does_not_restart_after_shutdown(monkeypatch):
    lock = asyncio.Lock()
    await lock.acquire()
    client = SimpleNamespace(_write_lock=lock, _update_in_progress=False)
    coordinator = SimpleNamespace(
        device_client=client, data={"existing": True}, _shutting_down=False
    )
    update = AsyncMock()
    monkeypatch.setattr(update_module, "run_update_cycle", update)
    task = asyncio.create_task(update_module.async_update_data(coordinator))
    await asyncio.sleep(0)
    assert client._update_in_progress
    coordinator._shutting_down = True
    lock.release()
    assert await task == {"existing": True}
    update.assert_not_awaited()
    assert not client._update_in_progress


@pytest.mark.asyncio
@pytest.mark.parametrize("family", ["airpack_home", "airpack4"])
async def test_documented_home_and_ap4_afc_test_requires_equipment_confirmation(family):
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(options={"device_family": family}),
        device_client=SimpleNamespace(
            device_info={"firmware": "4.75"},
            available_registers={"holding_registers": {"configuration_mode"}},
        ),
        async_request_refresh=AsyncMock(),
    )
    deps = SimpleNamespace(
        iter_target_coordinators=AsyncMock(return_value=[("climate.test", coordinator)]),
        write_register=AsyncMock(return_value=True),
        logger=MagicMock(),
    )
    handler = _build_start_pressure_test_handler(object(), deps)
    with pytest.raises(ServiceValidationError):
        await handler(SimpleNamespace(data={"test_type": "afc_and_duct"}))
    deps.write_register.assert_not_awaited()
    await handler(SimpleNamespace(data={"test_type": "afc_and_duct", "confirm_equipment": True}))
    args = deps.write_register.await_args.args
    assert args[:3] == (coordinator, "configuration_mode", 65)
    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_family_cannot_start_afc_test():
    coordinator = SimpleNamespace(entry=SimpleNamespace(options={}))
    deps = SimpleNamespace(
        iter_target_coordinators=AsyncMock(return_value=[("climate.test", coordinator)]),
        write_register=AsyncMock(),
    )
    with pytest.raises(ServiceValidationError, match="profile"):
        await _build_start_pressure_test_handler(object(), deps)(
            SimpleNamespace(data={"test_type": "afc_and_duct", "confirm_equipment": True})
        )
    deps.write_register.assert_not_awaited()


@pytest.mark.parametrize(
    "raw", [0x0000, 0x092C, 0x652C, 0x962C, 0x1413, 0x145B, 0x8000, 0xFFFF, -1, 0x1142C, True]
)
def test_out_of_contract_aatt_is_not_a_plausible_setting(raw):
    assert decode_aatt(raw) is None
    assert get_register_definitions()["setting_summer_mon_1"].decode(raw) is None


@pytest.mark.parametrize("flow,temp", [(10, 10), (100, 45), (20, 22), (30, 22.5)])
def test_documented_aatt_boundaries_roundtrip(flow, temp):
    reg = get_register_definitions()["setting_summer_mon_1"]
    value = {"airflow_pct": flow, "temp_c": temp}
    assert reg.decode(reg.encode(value)) == value


@pytest.mark.asyncio
async def test_concurrent_slot_edits_cannot_mix_settings_and_time():
    coordinator = _schedule_coordinator()
    calls = []
    first_entered = asyncio.Event()
    release_first = asyncio.Event()

    async def write(*, register_name, value, offset, refresh):
        assert coordinator.device_client._write_lock.locked()
        calls.append((register_name, value))
        if len(calls) == 1:
            first_entered.set()
            await release_first.wait()
        await asyncio.sleep(0)
        return True, False

    coordinator._locked_single_register_write = write
    a = asyncio.create_task(
        async_write_schedule_slot(
            coordinator,
            "schedule_summer_mon_1",
            "08:00",
            "setting_summer_mon_1",
            {"airflow_pct": 20, "temp_c": 22},
        )
    )
    await first_entered.wait()
    b = asyncio.create_task(
        async_write_schedule_slot(
            coordinator,
            "schedule_summer_mon_1",
            "10:00",
            "setting_summer_mon_1",
            {"airflow_pct": 80, "temp_c": 24},
        )
    )
    await asyncio.sleep(0)
    assert len(calls) == 1
    release_first.set()
    await asyncio.gather(a, b)
    assert calls == [
        ("setting_summer_mon_1", {"airflow_pct": 20, "temp_c": 22}),
        ("schedule_summer_mon_1", "08:00"),
        ("setting_summer_mon_1", {"airflow_pct": 80, "temp_c": 24}),
        ("schedule_summer_mon_1", "10:00"),
    ]
    assert coordinator.async_request_refresh.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [False, ConnectionException("lost"), ValueError("invalid"), asyncio.CancelledError()]
)
async def test_partial_slot_change_is_reconciled_after_lock_release(failure):
    coordinator = _schedule_coordinator()

    async def refresh():
        assert not coordinator.device_client._write_lock.locked()

    coordinator.async_request_refresh = AsyncMock(side_effect=refresh)
    calls = []

    async def write(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return True, False
        if isinstance(failure, BaseException):
            raise failure
        return False, False

    coordinator._locked_single_register_write = write
    expected = (
        asyncio.CancelledError
        if isinstance(failure, asyncio.CancelledError)
        else HomeAssistantError
    )
    with pytest.raises(expected):
        await async_write_schedule_slot(
            coordinator,
            "schedule_summer_mon_1",
            "10:00",
            "setting_summer_mon_1",
            {"airflow_pct": 80, "temp_c": 24},
        )
    assert len(calls) == 2
    coordinator.async_request_refresh.assert_awaited_once()
    assert not coordinator.device_client._write_lock.locked()


@pytest.mark.asyncio
async def test_shutdown_rejects_slot_without_any_transport_or_refresh():
    coordinator = _schedule_coordinator()
    coordinator._shutting_down = True
    coordinator._locked_single_register_write = AsyncMock()
    with pytest.raises(HomeAssistantError, match="shutting down"):
        await async_write_schedule_slot(
            coordinator, "schedule_summer_mon_1", "disabled", "setting_summer_mon_1", None
        )
    coordinator._locked_single_register_write.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,setting,start",
    [
        ("mode", "setting_mode", "08:00"),
        ("schedule_summer_mon_1", "setting_winter_mon_1", "08:00"),
        ("schedule_invalid_mon_1", "setting_invalid_mon_1", "08:00"),
        ("schedule_summer_mon_1", "setting_summer_mon_1", "25:00"),
    ],
)
async def test_invalid_slot_preflight_has_no_writes(name, setting, start):
    coordinator = _schedule_coordinator()
    coordinator._locked_single_register_write = AsyncMock()
    with pytest.raises(ValueError):
        await async_write_schedule_slot(coordinator, name, start, setting, None)
    coordinator._locked_single_register_write.assert_not_awaited()
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("write_success", [True, False])
async def test_reconciliation_failure_cannot_mask_partial_failure(write_success):
    coordinator = _schedule_coordinator()
    coordinator._locked_single_register_write = AsyncMock(return_value=(write_success, False))
    coordinator.async_request_refresh = AsyncMock(side_effect=RuntimeError("refresh failed"))
    expected = RuntimeError if write_success else HomeAssistantError
    with pytest.raises(expected):
        await async_write_schedule_slot(
            coordinator, "schedule_summer_mon_1", "disabled", "setting_summer_mon_1", None
        )
    coordinator.async_request_refresh.assert_awaited_once()
