"""Maintenance service registration helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime as _dt

from homeassistant.core import HomeAssistant, ServiceCall

from .modbus_exceptions import ConnectionException, ModbusException
from .services_dispatch import (
    refresh_and_log_success,
    write_device_name_chunks,
    write_mapped_optional_register,
    write_register_batch,
)
from .services_handler_deps import ServiceHandlerDeps
from .services_schema import (
    RESET_FILTERS_SCHEMA,
    RESET_SETTINGS_SCHEMA,
    SET_DEVICE_NAME_SCHEMA,
    SET_MODBUS_PARAMETERS_SCHEMA,
    START_PRESSURE_TEST_SCHEMA,
    SYNC_TIME_SCHEMA,
)
from .services_validation import (
    filter_reset_value,
    iter_modbus_parameter_writes,
    normalize_modbus_options,
    pressure_test_payload,
    reset_settings_registers,
)


def _to_bcd(value: int) -> int:
    return ((value // 10) << 4) | (value % 10)


def _clock_payload(now: _dt) -> list[int]:
    reg_yymm = (_to_bcd(now.year % 100) << 8) | _to_bcd(now.month)
    reg_ddtt = (_to_bcd(now.day) << 8) | _to_bcd(now.weekday())
    reg_ggmm = (_to_bcd(now.hour) << 8) | _to_bcd(now.minute)
    reg_sscc = (_to_bcd(now.second) << 8) | 0x00
    return [reg_yymm, reg_ddtt, reg_ggmm, reg_sscc]


def _iter_targets(hass: HomeAssistant, call: ServiceCall, deps: ServiceHandlerDeps):
    """Yield targeted coordinators for maintenance service handlers."""
    yield from deps.iter_target_coordinators(hass, call)


def _maintenance_registrations():
    """Return registration rows for maintenance services."""
    return [
        ("reset_filters", RESET_FILTERS_SCHEMA),
        ("reset_settings", RESET_SETTINGS_SCHEMA),
        ("start_pressure_test", START_PRESSURE_TEST_SCHEMA),
        ("set_modbus_parameters", SET_MODBUS_PARAMETERS_SCHEMA),
        ("set_device_name", SET_DEVICE_NAME_SCHEMA),
        ("sync_time", SYNC_TIME_SCHEMA),
    ]


def _iter_maintenance_service_bindings(handlers: dict[str, object]):
    """Yield maintenance registration rows with bound handlers."""
    for service, schema in _maintenance_registrations():
        yield service, schema, handlers[service]


async def _run_for_targets(
    hass: HomeAssistant,
    call: ServiceCall,
    deps: ServiceHandlerDeps,
    action: Callable[[str, object], Awaitable[bool]],
) -> None:
    """Run a maintenance action for each targeted coordinator."""
    for entity_id, coordinator in _iter_targets(hass, call, deps):
        await action(entity_id, coordinator)


def register_maintenance_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register maintenance services."""

    async def reset_filters(call: ServiceCall) -> None:
        filter_value = filter_reset_value(deps.normalize_option, call.data["filter_type"])
        async def _reset_filters_for_target(entity_id: str, coordinator: object) -> bool:
            if not await deps.write_register(coordinator, "filter_change", filter_value, entity_id, "reset filters"):
                deps.logger.error("Failed to reset filters for %s", entity_id)
                return False
            await refresh_and_log_success(coordinator, deps.logger, "Reset filters for %s", entity_id)
            return True

        await _run_for_targets(hass, call, deps, _reset_filters_for_target)

    async def reset_settings(call: ServiceCall) -> None:
        reset_type = deps.normalize_option(call.data["reset_type"])
        registers = reset_settings_registers(reset_type)

        async def _reset_settings_for_target(entity_id: str, coordinator: object) -> bool:
            if not await write_register_batch(
                coordinator,
                registers,
                entity_id,
                "reset settings",
                deps.write_register,
                deps.logger,
                {
                    "hard_reset_settings": "Failed to reset user settings for %s",
                    "hard_reset_schedule": "Failed to reset schedule settings for %s",
                },
            ):
                return False
            await refresh_and_log_success(
                coordinator, deps.logger, "Reset settings (%s) for %s", reset_type, entity_id
            )
            return True

        await _run_for_targets(hass, call, deps, _reset_settings_for_target)

    async def start_pressure_test(call: ServiceCall) -> None:
        async def _start_pressure_test_for_target(entity_id: str, coordinator: object) -> bool:
            if not await write_register_batch(
                coordinator,
                pressure_test_payload(deps.dt_now()),
                entity_id,
                "start pressure test",
                deps.write_register,
                deps.logger,
                {
                    "pres_check_day_2": "Failed to start pressure test for %s",
                    "pres_check_time_2": "Failed to start pressure test for %s",
                },
            ):
                return False
            await refresh_and_log_success(coordinator, deps.logger, "Started pressure test for %s", entity_id)
            return True

        await _run_for_targets(hass, call, deps, _start_pressure_test_for_target)

    async def set_modbus_parameters(call: ServiceCall) -> None:
        port, baud_rate, parity, stop_bits = normalize_modbus_options(deps.normalize_option, call.data)

        async def _set_modbus_parameters_for_target(entity_id: str, coordinator: object) -> bool:
            writes = iter_modbus_parameter_writes(port, baud_rate, parity, stop_bits)
            for register_name, option_value, option_map, error_message in writes:
                if not await write_mapped_optional_register(
                    coordinator,
                    register_name,
                    option_value,
                    option_map,
                    entity_id,
                    "set Modbus parameters",
                    error_message,
                    deps.write_register,
                    deps.logger,
                ):
                    return False
            await refresh_and_log_success(coordinator, deps.logger, "Set Modbus parameters for %s", entity_id)
            return True

        await _run_for_targets(hass, call, deps, _set_modbus_parameters_for_target)

    async def set_device_name(call: ServiceCall) -> None:
        device_name = call.data["device_name"]
        async def _set_device_name_for_target(entity_id: str, coordinator: object) -> bool:
            try:
                if len(device_name) >= 16:
                    success = await coordinator.async_write_register("device_name", device_name, refresh=False)
                else:
                    success = await write_device_name_chunks(
                        coordinator,
                        device_name,
                        getattr(coordinator, "effective_batch", 2),
                    )
                if not success:
                    deps.logger.error("Failed to set device name for %s", entity_id)
                    return False
            except (ModbusException, ConnectionException) as err:
                deps.logger.error("Failed to set device name for %s: %s", entity_id, err)
                return False
            await refresh_and_log_success(
                coordinator, deps.logger, "Set device name to '%s' for %s", device_name, entity_id
            )
            return True

        await _run_for_targets(hass, call, deps, _set_device_name_for_target)

    async def sync_time(call: ServiceCall) -> None:
        async def _sync_time_for_target(entity_id: str, coordinator: object) -> bool:
            now = _dt.now()
            try:
                success = await coordinator.async_write_registers(
                    start_address=0,
                    values=_clock_payload(now),
                    refresh=False,
                )
                if success:
                    deps.logger.info("Synced device clock to %s for %s", now.strftime("%Y-%m-%d %H:%M:%S"), entity_id)
                else:
                    deps.logger.error("Failed to sync clock for %s", entity_id)
            except (ModbusException, ConnectionException) as err:
                deps.logger.error("Failed to sync clock for %s: %s", entity_id, err)
            return True

        await _run_for_targets(hass, call, deps, _sync_time_for_target)

    handlers = {
        "reset_filters": reset_filters,
        "reset_settings": reset_settings,
        "start_pressure_test": start_pressure_test,
        "set_modbus_parameters": set_modbus_parameters,
        "set_device_name": set_device_name,
        "sync_time": sync_time,
    }
    for service, schema, handler in _iter_maintenance_service_bindings(handlers):
        hass.services.async_register(deps.domain, service, handler, schema)
