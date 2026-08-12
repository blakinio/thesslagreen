# mypy: ignore-errors
"""Exercise remaining maintenance service success and fail-closed branches."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from custom_components.thessla_green_modbus.services import handlers_maintenance as maintenance
from homeassistant.exceptions import HomeAssistantError
from pymodbus.exceptions import ConnectionException


def _deps(coordinator):
    return SimpleNamespace(
        domain="thessla_green_modbus",
        normalize_option=lambda value: value,
        iter_target_coordinators=AsyncMock(return_value=[("sensor.unit", coordinator)]),
        write_register=AsyncMock(return_value=True),
        logger=Mock(),
        dt_now=Mock(return_value=datetime(2026, 8, 12, 19, 30, 45)),
    )


def test_bcd_clock_payload_and_registration_helpers() -> None:
    assert maintenance._to_bcd(45) == 0x45
    payload = maintenance._clock_payload(datetime(2026, 8, 12, 19, 30, 45))
    assert payload == [0x2608, 0x1202, 0x1930, 0x4500]

    registrations = maintenance._maintenance_registrations()
    assert [service for service, _schema in registrations] == [
        "reset_filters",
        "reset_settings",
        "start_pressure_test",
        "set_modbus_parameters",
        "set_device_name",
        "sync_time",
        "sync_device_clock",
    ]
    handler = AsyncMock()
    handlers = maintenance._maintenance_handlers(
        handler, handler, handler, handler, handler, handler, handler
    )
    assert [
        service
        for service, _schema, _handler in maintenance._iter_maintenance_service_bindings(handlers)
    ] == [service for service, _schema in registrations]


@pytest.mark.asyncio
async def test_write_then_refresh_rejects_unconfirmed_write() -> None:
    coordinator = SimpleNamespace()
    deps = _deps(coordinator)
    with pytest.raises(HomeAssistantError, match="did not confirm maintenance action"):
        await maintenance._write_then_refresh(
            coordinator=coordinator,
            entity_id="sensor.unit",
            deps=deps,
            success_message="ok %s",
            success_args=("sensor.unit",),
            write_flow=AsyncMock(return_value=False),
        )


@pytest.mark.asyncio
async def test_reset_filters_success_and_write_failure() -> None:
    coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
    deps = _deps(coordinator)
    handler = maintenance._build_reset_filters_handler(object(), deps)
    with (
        patch.object(maintenance, "filter_reset_value", return_value=3),
        patch.object(maintenance, "refresh_and_log_success", new=AsyncMock()) as refresh,
    ):
        await handler(SimpleNamespace(data={"filter_type": "all"}))
    deps.write_register.assert_awaited_once_with(
        coordinator, "filter_change", 3, "sensor.unit", "reset filters"
    )
    refresh.assert_awaited_once()

    deps.write_register = AsyncMock(return_value=False)
    handler = maintenance._build_reset_filters_handler(object(), deps)
    with patch.object(maintenance, "filter_reset_value", return_value=3):
        with pytest.raises(HomeAssistantError, match="did not confirm maintenance action"):
            await handler(SimpleNamespace(data={"filter_type": "all"}))


@pytest.mark.asyncio
async def test_reset_settings_and_pressure_test_failure_paths() -> None:
    coordinator = SimpleNamespace()
    deps = _deps(coordinator)
    reset_handler = maintenance._build_reset_settings_handler(object(), deps)
    with (
        patch.object(maintenance, "reset_settings_registers", return_value=[("a", 1)]),
        patch.object(maintenance, "write_register_batch", new=AsyncMock(return_value=False)),
    ):
        with pytest.raises(HomeAssistantError, match="did not confirm maintenance action"):
            await reset_handler(SimpleNamespace(data={"reset_type": "hard"}))

    pressure_handler = maintenance._build_start_pressure_test_handler(object(), deps)
    with (
        patch.object(maintenance, "pressure_test_payload", return_value=[("x", 1)]),
        patch.object(maintenance, "write_register_batch", new=AsyncMock(return_value=False)),
    ):
        with pytest.raises(HomeAssistantError, match="did not confirm pressure test"):
            await pressure_handler(SimpleNamespace(data={}))


@pytest.mark.asyncio
async def test_modbus_parameter_mapping_failure_and_success() -> None:
    coordinator = SimpleNamespace()
    deps = _deps(coordinator)
    handler = maintenance._build_set_modbus_parameters_handler(object(), deps)
    call = SimpleNamespace(data={"port": 1})
    writes = [("uart_baud", "9600", {"9600": 1}, "error")]
    with (
        patch.object(maintenance, "normalize_modbus_options", return_value=(1, "9600", "none", 1)),
        patch.object(maintenance, "iter_modbus_parameter_writes", return_value=writes),
        patch.object(
            maintenance, "write_mapped_optional_register", new=AsyncMock(return_value=False)
        ),
    ):
        with pytest.raises(HomeAssistantError, match="did not confirm Modbus parameter"):
            await handler(call)

    with (
        patch.object(maintenance, "normalize_modbus_options", return_value=(1, "9600", "none", 1)),
        patch.object(maintenance, "iter_modbus_parameter_writes", return_value=writes),
        patch.object(
            maintenance, "write_mapped_optional_register", new=AsyncMock(return_value=True)
        ),
        patch.object(maintenance, "refresh_and_log_success", new=AsyncMock()) as refresh,
    ):
        await handler(call)
    refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_device_name_long_short_success_exception_and_unconfirmed() -> None:
    coordinator = SimpleNamespace(
        effective_batch=2,
        async_write_register=AsyncMock(return_value=True),
    )
    deps = _deps(coordinator)
    handler = maintenance._build_set_device_name_handler(object(), deps)
    with patch.object(maintenance, "refresh_and_log_success", new=AsyncMock()):
        await handler(SimpleNamespace(data={"device_name": "1234567890abcdef"}))
    coordinator.async_write_register.assert_awaited_once_with(
        "device_name", "1234567890abcdef", refresh=False, targeted_readback=False
    )

    coordinator.async_write_register.reset_mock()
    with (
        patch.object(
            maintenance, "write_device_name_chunks", new=AsyncMock(return_value=True)
        ) as chunks,
        patch.object(maintenance, "refresh_and_log_success", new=AsyncMock()),
    ):
        await handler(SimpleNamespace(data={"device_name": "short"}))
    chunks.assert_awaited_once_with(coordinator, "short", 2)

    coordinator.async_write_register = AsyncMock(side_effect=ConnectionException("offline"))
    handler = maintenance._build_set_device_name_handler(object(), deps)
    with pytest.raises(HomeAssistantError, match="Failed to set device name"):
        await handler(SimpleNamespace(data={"device_name": "1234567890abcdef"}))

    coordinator.async_write_register = AsyncMock(return_value=False)
    handler = maintenance._build_set_device_name_handler(object(), deps)
    with pytest.raises(HomeAssistantError, match="did not confirm device-name"):
        await handler(SimpleNamespace(data={"device_name": "1234567890abcdef"}))


@pytest.mark.asyncio
async def test_sync_time_success_exception_and_unconfirmed() -> None:
    coordinator = SimpleNamespace(async_write_registers=AsyncMock(return_value=True))
    deps = _deps(coordinator)
    handler = maintenance._build_sync_time_handler(object(), deps)
    fixed = datetime(2026, 8, 12, 19, 30, 45)
    with patch.object(maintenance, "_dt") as dt_cls:
        dt_cls.now.return_value = fixed
        await handler(SimpleNamespace(data={}))
    coordinator.async_write_registers.assert_awaited_once_with(
        start_address=0,
        values=maintenance._clock_payload(fixed),
        refresh=False,
    )

    coordinator.async_write_registers = AsyncMock(side_effect=ConnectionException("offline"))
    handler = maintenance._build_sync_time_handler(object(), deps)
    with pytest.raises(HomeAssistantError, match="Failed to sync clock"):
        await handler(SimpleNamespace(data={}))

    coordinator.async_write_registers = AsyncMock(return_value=False)
    handler = maintenance._build_sync_time_handler(object(), deps)
    with pytest.raises(HomeAssistantError, match="did not confirm clock synchronization"):
        await handler(SimpleNamespace(data={}))


@pytest.mark.asyncio
async def test_sync_device_clock_options_success_homeassistant_generic_and_false() -> None:
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(options={maintenance.CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS: 12})
    )
    deps = _deps(coordinator)
    handler = maintenance._build_sync_device_clock_handler(object(), deps)
    with patch.object(
        maintenance, "async_perform_clock_sync", new=AsyncMock(return_value=True)
    ) as sync:
        await handler(SimpleNamespace(data={"force": True}))
    sync.assert_awaited_once_with(coordinator, force=True, max_drift_seconds=12, logger=deps.logger)

    coordinator.entry = None
    handler = maintenance._build_sync_device_clock_handler(object(), deps)
    original = HomeAssistantError("already safe")
    with patch.object(maintenance, "async_perform_clock_sync", new=AsyncMock(side_effect=original)):
        with pytest.raises(HomeAssistantError) as exc_info:
            await handler(SimpleNamespace(data={}))
    assert exc_info.value is original

    with patch.object(
        maintenance, "async_perform_clock_sync", new=AsyncMock(side_effect=RuntimeError("boom"))
    ):
        with pytest.raises(HomeAssistantError, match="Clock synchronization failed"):
            await handler(SimpleNamespace(data={}))

    with patch.object(maintenance, "async_perform_clock_sync", new=AsyncMock(return_value=False)):
        with pytest.raises(HomeAssistantError, match="did not confirm clock synchronization"):
            await handler(SimpleNamespace(data={}))


def test_register_maintenance_services_binds_all_handlers_in_order() -> None:
    services = SimpleNamespace(async_register=Mock())
    hass = SimpleNamespace(services=services)
    deps = _deps(SimpleNamespace())
    maintenance.register_maintenance_services(hass, deps)
    assert [call.args[1] for call in services.async_register.call_args_list] == [
        service for service, _schema in maintenance._maintenance_registrations()
    ]
