"""Maintenance service registration helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime as _dt

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from pymodbus.exceptions import ConnectionException, ModbusException

from ..clock_sync import async_perform_clock_sync
from ..const import (
    CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
)
from .dispatch import (
    refresh_and_log_success,
    write_device_name_chunks,
    write_mapped_optional_register,
    write_register_batch,
)
from .handler_deps import ServiceHandlerDeps
from .schema import (
    RESET_FILTERS_SCHEMA,
    RESET_SETTINGS_SCHEMA,
    SET_DEVICE_NAME_SCHEMA,
    SET_MODBUS_PARAMETERS_SCHEMA,
    START_PRESSURE_TEST_SCHEMA,
    SYNC_DEVICE_CLOCK_SCHEMA,
    SYNC_TIME_SCHEMA,
)
from .validation import (
    filter_reset_value,
    iter_modbus_parameter_writes,
    normalize_modbus_options,
    pressure_test_payload,
    reset_settings_registers,
)

ServiceAction = Callable[[str, object], Awaitable[bool]]


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
        ("sync_device_clock", SYNC_DEVICE_CLOCK_SCHEMA),
    ]


def _iter_maintenance_service_bindings(handlers: dict[str, object]):
    """Yield maintenance registration rows with bound handlers."""
    for service, schema in _maintenance_registrations():
        yield service, schema, handlers[service]


def _maintenance_handlers(
    reset_filters: object,
    reset_settings: object,
    start_pressure_test: object,
    set_modbus_parameters: object,
    set_device_name: object,
    sync_time: object,
    sync_device_clock: object,
) -> dict[str, object]:
    """Return maintenance service handlers keyed by service name."""
    return {
        "reset_filters": reset_filters,
        "reset_settings": reset_settings,
        "start_pressure_test": start_pressure_test,
        "set_modbus_parameters": set_modbus_parameters,
        "set_device_name": set_device_name,
        "sync_time": sync_time,
        "sync_device_clock": sync_device_clock,
    }


async def _run_with_success_log(
    coordinator: object,
    deps: ServiceHandlerDeps,
    success_message: str,
    *args: object,
) -> bool:
    """Refresh and emit success message for a completed target action."""
    await refresh_and_log_success(coordinator, deps.logger, success_message, *args)
    return True


def _register_maintenance_service(
    hass: HomeAssistant,
    deps: ServiceHandlerDeps,
    service: str,
    schema: object,
    handler: object,
) -> None:
    """Register one maintenance service with schema."""
    hass.services.async_register(deps.domain, service, handler, schema)


def _register_maintenance_bindings(
    hass: HomeAssistant, deps: ServiceHandlerDeps, handlers: dict[str, object]
) -> None:
    """Finalize maintenance registration loop preserving order."""
    for service, schema, handler in _iter_maintenance_service_bindings(handlers):
        _register_maintenance_service(hass, deps, service, schema, handler)


async def _run_for_targets(
    hass: HomeAssistant,
    call: ServiceCall,
    deps: ServiceHandlerDeps,
    action: ServiceAction,
) -> None:
    """Run a maintenance action for each targeted coordinator."""
    for entity_id, coordinator in _iter_targets(hass, call, deps):
        await action(entity_id, coordinator)


async def _write_then_refresh(
    *,
    coordinator: object,
    entity_id: str,
    deps: ServiceHandlerDeps,
    success_message: str,
    success_args: tuple[object, ...],
    write_flow: Callable[[], Awaitable[bool]],
) -> bool:
    """Execute target write flow and common refresh/success logging."""
    if not await write_flow():
        return False
    return await _run_with_success_log(coordinator, deps, success_message, *success_args)


def _build_reset_filters_handler(hass: HomeAssistant, deps: ServiceHandlerDeps):
    async def reset_filters(call: ServiceCall) -> None:
        filter_value = filter_reset_value(deps.normalize_option, call.data["filter_type"])

        async def _reset_filters_for_target(entity_id: str, coordinator: object) -> bool:
            async def _write_flow() -> bool:
                if not await deps.write_register(
                    coordinator, "filter_change", filter_value, entity_id, "reset filters"
                ):
                    deps.logger.error("Failed to reset filters for %s", entity_id)
                    return False
                return True

            return await _write_then_refresh(
                coordinator=coordinator,
                entity_id=entity_id,
                deps=deps,
                success_message="Reset filters for %s",
                success_args=(entity_id,),
                write_flow=_write_flow,
            )

        await _run_for_targets(hass, call, deps, _reset_filters_for_target)

    return reset_filters


def _build_reset_settings_handler(hass: HomeAssistant, deps: ServiceHandlerDeps):
    async def reset_settings(call: ServiceCall) -> None:
        reset_type = deps.normalize_option(call.data["reset_type"])
        registers = reset_settings_registers(reset_type)

        async def _reset_settings_for_target(entity_id: str, coordinator: object) -> bool:
            return await _write_then_refresh(
                coordinator=coordinator,
                entity_id=entity_id,
                deps=deps,
                success_message="Reset settings (%s) for %s",
                success_args=(reset_type, entity_id),
                write_flow=lambda: write_register_batch(
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
                ),
            )

        await _run_for_targets(hass, call, deps, _reset_settings_for_target)

    return reset_settings


def _build_start_pressure_test_handler(hass: HomeAssistant, deps: ServiceHandlerDeps):
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
            return await _run_with_success_log(
                coordinator, deps, "Started pressure test for %s", entity_id
            )

        await _run_for_targets(hass, call, deps, _start_pressure_test_for_target)

    return start_pressure_test


def _build_set_modbus_parameters_handler(hass: HomeAssistant, deps: ServiceHandlerDeps):
    async def set_modbus_parameters(call: ServiceCall) -> None:
        port, baud_rate, parity, stop_bits = normalize_modbus_options(
            deps.normalize_option, call.data
        )

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
            return await _run_with_success_log(
                coordinator, deps, "Set Modbus parameters for %s", entity_id
            )

        await _run_for_targets(hass, call, deps, _set_modbus_parameters_for_target)

    return set_modbus_parameters


def _build_set_device_name_handler(hass: HomeAssistant, deps: ServiceHandlerDeps):
    async def set_device_name(call: ServiceCall) -> None:
        device_name = call.data["device_name"]

        async def _set_device_name_for_target(entity_id: str, coordinator: object) -> bool:
            try:
                if len(device_name) >= 16:
                    success = await coordinator.async_write_register(
                        "device_name", device_name, refresh=False, targeted_readback=False
                    )
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
            return await _run_with_success_log(
                coordinator, deps, "Set device name to '%s' for %s", device_name, entity_id
            )

        await _run_for_targets(hass, call, deps, _set_device_name_for_target)

    return set_device_name


def _build_sync_time_handler(hass: HomeAssistant, deps: ServiceHandlerDeps):
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
                    deps.logger.info(
                        "Synced device clock to %s for %s",
                        now.strftime("%Y-%m-%d %H:%M:%S"),
                        entity_id,
                    )
                else:
                    deps.logger.error("Failed to sync clock for %s", entity_id)
            except (ModbusException, ConnectionException) as err:
                deps.logger.error("Failed to sync clock for %s: %s", entity_id, err)
            return True

        await _run_for_targets(hass, call, deps, _sync_time_for_target)

    return sync_time


def _build_sync_device_clock_handler(hass: HomeAssistant, deps: ServiceHandlerDeps):
    async def sync_device_clock(call: ServiceCall) -> None:
        force = bool(call.data.get("force", False))

        async def _sync_device_clock_for_target(entity_id: str, coordinator: object) -> bool:
            opts = {}
            if hasattr(coordinator, "entry") and coordinator.entry is not None:
                opts = getattr(coordinator.entry, "options", {}) or {}
            max_drift = int(
                opts.get(
                    CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
                    DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
                )
            )
            try:
                ok = await async_perform_clock_sync(
                    coordinator,
                    force=force,
                    max_drift_seconds=max_drift,
                    logger=deps.logger,
                )
            except HomeAssistantError:
                raise
            except Exception as err:  # noqa: BLE001
                deps.logger.error("Clock sync failed for %s: %s", entity_id, err)
                return False
            if not ok:
                deps.logger.error("Failed to sync device clock for %s", entity_id)
                return False
            return True

        await _run_for_targets(hass, call, deps, _sync_device_clock_for_target)

    return sync_device_clock


def register_maintenance_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register maintenance services."""
    handlers = _maintenance_handlers(
        _build_reset_filters_handler(hass, deps),
        _build_reset_settings_handler(hass, deps),
        _build_start_pressure_test_handler(hass, deps),
        _build_set_modbus_parameters_handler(hass, deps),
        _build_set_device_name_handler(hass, deps),
        _build_sync_time_handler(hass, deps),
        _build_sync_device_clock_handler(hass, deps),
    )
    _register_maintenance_bindings(hass, deps, handlers)
