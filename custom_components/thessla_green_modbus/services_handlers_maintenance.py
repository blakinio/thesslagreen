"""Maintenance service registration helpers."""

from __future__ import annotations

from datetime import datetime as _dt

from homeassistant.core import HomeAssistant, ServiceCall

from .modbus_exceptions import ConnectionException, ModbusException
from .services_dispatch import (
    refresh_and_log_success,
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
    FILTER_TYPE_MAP,
    iter_modbus_parameter_writes,
    normalize_modbus_options,
    reset_settings_registers,
)


async def _write_device_name(coordinator: object, device_name: str, batch: int) -> bool:
    chars_per_batch = batch * 2
    for i in range(0, len(device_name), chars_per_batch):
        chunk = device_name[i : i + chars_per_batch]
        reg_offset = i // 2
        if not await coordinator.async_write_register("device_name", chunk, refresh=False, offset=reg_offset):
            return False
    return True


def _to_bcd(value: int) -> int:
    return ((value // 10) << 4) | (value % 10)


def _clock_payload(now: _dt) -> list[int]:
    reg_yymm = (_to_bcd(now.year % 100) << 8) | _to_bcd(now.month)
    reg_ddtt = (_to_bcd(now.day) << 8) | _to_bcd(now.weekday())
    reg_ggmm = (_to_bcd(now.hour) << 8) | _to_bcd(now.minute)
    reg_sscc = (_to_bcd(now.second) << 8) | 0x00
    return [reg_yymm, reg_ddtt, reg_ggmm, reg_sscc]


def register_maintenance_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register maintenance services."""

    async def reset_filters(call: ServiceCall) -> None:
        filter_value = FILTER_TYPE_MAP[deps.normalize_option(call.data["filter_type"])]
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            if not await deps.write_register(coordinator, "filter_change", filter_value, entity_id, "reset filters"):
                deps.logger.error("Failed to reset filters for %s", entity_id)
                continue
            await refresh_and_log_success(coordinator, deps.logger, "Reset filters for %s", entity_id)

    async def reset_settings(call: ServiceCall) -> None:
        reset_type = deps.normalize_option(call.data["reset_type"])
        registers = reset_settings_registers(reset_type)

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
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
                continue
            await refresh_and_log_success(
                coordinator, deps.logger, "Reset settings (%s) for %s", reset_type, entity_id
            )

    async def start_pressure_test(call: ServiceCall) -> None:
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            now = deps.dt_now()
            day_of_week = now.weekday()
            time_hhmm = now.hour * 100 + now.minute
            if not await write_register_batch(
                coordinator,
                [("pres_check_day_2", day_of_week), ("pres_check_time_2", time_hhmm)],
                entity_id,
                "start pressure test",
                deps.write_register,
                deps.logger,
                {
                    "pres_check_day_2": "Failed to start pressure test for %s",
                    "pres_check_time_2": "Failed to start pressure test for %s",
                },
            ):
                continue
            await refresh_and_log_success(coordinator, deps.logger, "Started pressure test for %s", entity_id)

    async def set_modbus_parameters(call: ServiceCall) -> None:
        port, baud_rate, parity, stop_bits = normalize_modbus_options(deps.normalize_option, call.data)

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            writes = iter_modbus_parameter_writes(port, baud_rate, parity, stop_bits)
            failed = False
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
                    failed = True
                    break
            if failed:
                continue
            await refresh_and_log_success(coordinator, deps.logger, "Set Modbus parameters for %s", entity_id)

    async def set_device_name(call: ServiceCall) -> None:
        device_name = call.data["device_name"]
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            try:
                if len(device_name) >= 16:
                    success = await coordinator.async_write_register("device_name", device_name, refresh=False)
                else:
                    success = await _write_device_name(
                        coordinator,
                        device_name,
                        getattr(coordinator, "effective_batch", 2),
                    )
                if not success:
                    deps.logger.error("Failed to set device name for %s", entity_id)
                    continue
            except (ModbusException, ConnectionException) as err:
                deps.logger.error("Failed to set device name for %s: %s", entity_id, err)
                continue
            await refresh_and_log_success(
                coordinator, deps.logger, "Set device name to '%s' for %s", device_name, entity_id
            )

    async def sync_time(call: ServiceCall) -> None:
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
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

    registrations = [
        ("reset_filters", reset_filters, RESET_FILTERS_SCHEMA),
        ("reset_settings", reset_settings, RESET_SETTINGS_SCHEMA),
        ("start_pressure_test", start_pressure_test, START_PRESSURE_TEST_SCHEMA),
        ("set_modbus_parameters", set_modbus_parameters, SET_MODBUS_PARAMETERS_SCHEMA),
        ("set_device_name", set_device_name, SET_DEVICE_NAME_SCHEMA),
        ("sync_time", sync_time, SYNC_TIME_SCHEMA),
    ]
    for service, handler, schema in registrations:
        hass.services.async_register(deps.domain, service, handler, schema)
