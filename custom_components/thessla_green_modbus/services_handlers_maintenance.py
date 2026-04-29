"""Maintenance service registration helpers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall

from .modbus_exceptions import ConnectionException, ModbusException
from .services_handler_deps import ServiceHandlerDeps
from .services_schema import (
    RESET_FILTERS_SCHEMA,
    RESET_SETTINGS_SCHEMA,
    SET_DEVICE_NAME_SCHEMA,
    SET_MODBUS_PARAMETERS_SCHEMA,
    START_PRESSURE_TEST_SCHEMA,
    SYNC_TIME_SCHEMA,
)

FILTER_TYPE_MAP = {"presostat": 1, "flat_filters": 2, "cleanpad": 3, "cleanpad_pure": 4}
BAUD_MAP = {
    "4800": 0,
    "9600": 1,
    "14400": 2,
    "19200": 3,
    "28800": 4,
    "38400": 5,
    "57600": 6,
    "76800": 7,
    "115200": 8,
}
PARITY_MAP = {"none": 0, "even": 1, "odd": 2}
STOP_MAP = {"1": 0, "2": 1}


def _normalize_modbus_options(deps: ServiceHandlerDeps, call: ServiceCall) -> tuple[str, str | None, str | None, str | None]:
    port = deps.normalize_option(call.data["port"])
    baud_rate = call.data.get("baud_rate")
    parity = call.data.get("parity")
    stop_bits = call.data.get("stop_bits")
    return (
        port,
        deps.normalize_option(baud_rate) if baud_rate else None,
        deps.normalize_option(parity) if parity else None,
        deps.normalize_option(stop_bits) if stop_bits else None,
    )


async def _write_device_name(coordinator: object, device_name: str, batch: int) -> bool:
    chars_per_batch = batch * 2
    for i in range(0, len(device_name), chars_per_batch):
        chunk = device_name[i : i + chars_per_batch]
        reg_offset = i // 2
        if not await coordinator.async_write_register("device_name", chunk, refresh=False, offset=reg_offset):
            return False
    return True




async def _refresh_and_log(
    coordinator: object, deps: ServiceHandlerDeps, message: str, *args: object
) -> None:
    await coordinator.async_request_refresh()
    deps.logger.info(message, *args)


def register_maintenance_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register maintenance services."""

    async def reset_filters(call: ServiceCall) -> None:
        filter_type = deps.normalize_option(call.data["filter_type"])
        filter_value = FILTER_TYPE_MAP[filter_type]

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            if not await deps.write_register(
                coordinator, "filter_change", filter_value, entity_id, "reset filters"
            ):
                deps.logger.error("Failed to reset filters for %s", entity_id)
                continue
            await _refresh_and_log(coordinator, deps, "Reset filters for %s", entity_id)

    async def reset_settings(call: ServiceCall) -> None:
        reset_type = deps.normalize_option(call.data["reset_type"])
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            if reset_type in ["user_settings", "all_settings"]:
                if not await deps.write_register(
                    coordinator, "hard_reset_settings", 1, entity_id, "reset settings"
                ):
                    deps.logger.error("Failed to reset user settings for %s", entity_id)
                    continue
            if reset_type in ["schedule_settings", "all_settings"]:
                if not await deps.write_register(
                    coordinator, "hard_reset_schedule", 1, entity_id, "reset settings"
                ):
                    deps.logger.error("Failed to reset schedule settings for %s", entity_id)
                    continue
            await _refresh_and_log(
                coordinator, deps, "Reset settings (%s) for %s", reset_type, entity_id
            )

    async def start_pressure_test(call: ServiceCall) -> None:
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            now = deps.dt_now()
            day_of_week = now.weekday()
            time_hhmm = now.hour * 100 + now.minute
            if not await deps.write_register(
                coordinator, "pres_check_day_2", day_of_week, entity_id, "start pressure test"
            ):
                deps.logger.error("Failed to start pressure test for %s", entity_id)
                continue
            if not await deps.write_register(
                coordinator, "pres_check_time_2", time_hhmm, entity_id, "start pressure test"
            ):
                deps.logger.error("Failed to start pressure test for %s", entity_id)
                continue
            await _refresh_and_log(coordinator, deps, "Started pressure test for %s", entity_id)

    async def set_modbus_parameters(call: ServiceCall) -> None:
        port, baud_rate, parity, stop_bits = _normalize_modbus_options(deps, call)

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            port_prefix = "uart_0" if port == "air_b" else "uart_1"
            if baud_rate:
                if not await deps.write_register(
                    coordinator,
                    f"{port_prefix}_baud",
                    BAUD_MAP[baud_rate],
                    entity_id,
                    "set Modbus parameters",
                ):
                    deps.logger.error("Failed to set baud rate for %s", entity_id)
                    continue
            if parity:
                if not await deps.write_register(
                    coordinator,
                    f"{port_prefix}_parity",
                    PARITY_MAP[parity],
                    entity_id,
                    "set Modbus parameters",
                ):
                    deps.logger.error("Failed to set parity for %s", entity_id)
                    continue
            if stop_bits:
                if not await deps.write_register(
                    coordinator,
                    f"{port_prefix}_stop",
                    STOP_MAP[stop_bits],
                    entity_id,
                    "set Modbus parameters",
                ):
                    deps.logger.error("Failed to set stop bits for %s", entity_id)
                    continue
            await _refresh_and_log(
                coordinator, deps, "Set Modbus parameters for %s", entity_id
            )

    async def set_device_name(call: ServiceCall) -> None:
        device_name = call.data["device_name"]
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            if len(device_name) >= 16:
                try:
                    if not await coordinator.async_write_register(
                        "device_name", device_name, refresh=False
                    ):
                        deps.logger.error("Failed to set device name for %s", entity_id)
                        continue
                except (ModbusException, ConnectionException) as err:
                    deps.logger.error("Failed to set device name for %s: %s", entity_id, err)
                    continue
            else:
                batch = getattr(coordinator, "effective_batch", 2)
                try:
                    if not await _write_device_name(coordinator, device_name, batch):
                        deps.logger.error("Failed to set device name for %s", entity_id)
                        continue
                except (ModbusException, ConnectionException) as err:
                    deps.logger.error("Failed to set device name for %s: %s", entity_id, err)
                    continue
            await _refresh_and_log(
                coordinator, deps, "Set device name to '%s' for %s", device_name, entity_id
            )

    async def sync_time(call: ServiceCall) -> None:
        from datetime import datetime as _dt

        def _to_bcd(value: int) -> int:
            return ((value // 10) << 4) | (value % 10)

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            now = _dt.now()
            reg_yymm = (_to_bcd(now.year % 100) << 8) | _to_bcd(now.month)
            reg_ddtt = (_to_bcd(now.day) << 8) | _to_bcd(now.weekday())
            reg_ggmm = (_to_bcd(now.hour) << 8) | _to_bcd(now.minute)
            reg_sscc = (_to_bcd(now.second) << 8) | 0x00
            try:
                success = await coordinator.async_write_registers(
                    start_address=0, values=[reg_yymm, reg_ddtt, reg_ggmm, reg_sscc], refresh=False
                )
                if success:
                    deps.logger.info(
                        "Synced device clock to %s for %s",
                        now.strftime("%Y-%m-%d %H:%M:%S"),
                        entity_id,
                    )
                else:
                    deps.logger.error("Failed to sync clock for %s", entity_id)
            except (ModbusException, ConnectionException) as err:
                deps.logger.error("Failed to sync clock for %s: %s", entity_id, err)

    hass.services.async_register(deps.domain, "reset_filters", reset_filters, RESET_FILTERS_SCHEMA)
    hass.services.async_register(
        deps.domain, "reset_settings", reset_settings, RESET_SETTINGS_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "start_pressure_test", start_pressure_test, START_PRESSURE_TEST_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "set_modbus_parameters", set_modbus_parameters, SET_MODBUS_PARAMETERS_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "set_device_name", set_device_name, SET_DEVICE_NAME_SCHEMA
    )
    hass.services.async_register(deps.domain, "sync_time", sync_time, SYNC_TIME_SCHEMA)
