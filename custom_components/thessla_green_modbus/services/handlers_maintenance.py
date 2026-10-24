"""Maintenance service registration helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from datetime import datetime as _dt
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pymodbus.exceptions import ConnectionException, ModbusException

from ..clock_sync import async_perform_clock_sync
from ..const import (
    CONF_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
    DEFAULT_SYNC_DEVICE_CLOCK_MAX_DRIFT_SECONDS,
)
from ..device_profile import configured_device_family
from .dispatch import (
    refresh_and_log_success,
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
    reset_settings_registers,
)

type ServiceAction = Callable[[str, Any], Awaitable[bool]]
type ServiceHandler = Callable[[ServiceCall], Awaitable[None]]
_DEVICE_ERRORS = (ModbusException, ConnectionException, TimeoutError, OSError)


def _to_bcd(value: int) -> int:
    return ((value // 10) << 4) | (value % 10)


def _clock_payload(now: _dt) -> list[int]:
    reg_yymm = (_to_bcd(now.year % 100) << 8) | _to_bcd(now.month)
    reg_ddtt = (_to_bcd(now.day) << 8) | _to_bcd(now.weekday())
    reg_ggmm = (_to_bcd(now.hour) << 8) | _to_bcd(now.minute)
    reg_sscc = (_to_bcd(now.second) << 8) | 0x00
    return [reg_yymm, reg_ddtt, reg_ggmm, reg_sscc]


async def _iter_targets(
    hass: HomeAssistant, call: ServiceCall, deps: ServiceHandlerDeps
) -> list[tuple[str, object]]:
    """Resolve targeted coordinators for maintenance service handlers."""
    return await deps.iter_target_coordinators(hass, call)


def _maintenance_registrations() -> list[tuple[str, Any]]:
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


def _iter_maintenance_service_bindings(
    handlers: dict[str, ServiceHandler],
) -> Iterator[tuple[str, Any, ServiceHandler]]:
    """Yield maintenance registration rows with bound handlers."""
    for service, schema in _maintenance_registrations():
        yield service, schema, handlers[service]


def _maintenance_handlers(
    reset_filters: ServiceHandler,
    reset_settings: ServiceHandler,
    start_pressure_test: ServiceHandler,
    set_modbus_parameters: ServiceHandler,
    set_device_name: ServiceHandler,
    sync_time: ServiceHandler,
    sync_device_clock: ServiceHandler,
) -> dict[str, ServiceHandler]:
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
    coordinator: Any,
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
    schema: Any,
    handler: ServiceHandler,
) -> None:
    """Register one maintenance service with schema."""
    hass.services.async_register(deps.domain, service, handler, schema)


def _register_maintenance_bindings(
    hass: HomeAssistant, deps: ServiceHandlerDeps, handlers: dict[str, ServiceHandler]
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
    for entity_id, coordinator in await _iter_targets(hass, call, deps):
        await action(entity_id, coordinator)


async def _write_then_refresh(
    *,
    coordinator: Any,
    entity_id: str,
    deps: ServiceHandlerDeps,
    success_message: str,
    success_args: tuple[object, ...],
    write_flow: Callable[[], Awaitable[bool]],
) -> bool:
    """Execute target write flow and common refresh/success logging."""
    if not await write_flow():
        raise HomeAssistantError(f"Device did not confirm maintenance action for {entity_id}.")
    return await _run_with_success_log(coordinator, deps, success_message, *success_args)


def _filter_replacement_commands(
    coordinator: Any, data: dict[str, Any], deps: ServiceHandlerDeps
) -> list[int]:
    """Separate Home type selection from AirPack4 per-side replacement commands."""
    family = configured_device_family(coordinator)
    if family == "airpack_home":
        current = (coordinator.data or {}).get("filter_change")
        if current not in (2, 3, 4):
            raise ServiceValidationError(
                "Home presostat needs no filter replacement write; inspect the filters, do not disable the presostat"
            )
        value = filter_reset_value(deps.normalize_option, data.get("filter_type", ""))
        if value != current:
            raise ServiceValidationError(
                "Replacement must preserve Home's existing filter type; changing the filter system is a separate service operation"
            )
        return [value]
    if family == "airpack4":
        direction = data.get("direction")
        if (
            direction not in ("supply", "exhaust", "both")
            or data.get("confirm_without_afc") is not True
        ):
            raise ServiceValidationError(
                "AirPack4 replacement requires direction and confirmation that each selected side has no AFC"
            )
        return {"supply": [17], "exhaust": [33], "both": [17, 33]}[direction]
    raise ServiceValidationError(
        "Select AirPack Home or AirPack4 in integration options before recording filter replacement"
    )


def _build_reset_filters_handler(hass: HomeAssistant, deps: ServiceHandlerDeps) -> ServiceHandler:
    async def reset_filters(call: ServiceCall) -> None:
        async def _reset_filters_for_target(entity_id: str, coordinator: Any) -> bool:
            commands = _filter_replacement_commands(coordinator, call.data, deps)

            async def _write_flow() -> bool:
                return await write_register_batch(
                    coordinator,
                    [("filter_change", value) for value in commands],
                    entity_id,
                    "record filter replacement",
                    deps.write_register,
                    deps.logger,
                    {"filter_change": "Failed to record filter replacement for %s"},
                )

            return await _write_then_refresh(
                coordinator=coordinator,
                entity_id=entity_id,
                deps=deps,
                success_message="Recorded filter replacement for %s",
                success_args=(entity_id,),
                write_flow=_write_flow,
            )

        await _run_for_targets(hass, call, deps, _reset_filters_for_target)

    return reset_filters


def _build_reset_settings_handler(hass: HomeAssistant, deps: ServiceHandlerDeps) -> ServiceHandler:
    async def reset_settings(call: ServiceCall) -> None:
        reset_type = deps.normalize_option(call.data["reset_type"])
        registers = reset_settings_registers(reset_type)

        async def _reset_settings_for_target(entity_id: str, coordinator: Any) -> bool:
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


def _build_start_pressure_test_handler(
    hass: HomeAssistant, deps: ServiceHandlerDeps
) -> ServiceHandler:
    async def start_pressure_test(call: ServiceCall) -> None:
        test_type = call.data.get("test_type")
        if (
            test_type not in ("duct_filter", "afc_and_duct")
            or call.data.get("confirm_equipment") is not True
        ):
            raise ServiceValidationError(
                "Choose the documented pressure-test procedure and confirm installed equipment; this does not reschedule the weekly test"
            )

        async def _start_pressure_test_for_target(entity_id: str, coordinator: Any) -> bool:
            if test_type == "afc_and_duct" and configured_device_family(coordinator) not in (
                "airpack_home",
                "airpack4",
            ):
                raise ServiceValidationError(
                    "Select the documented Home or AirPack4 profile before an AFC test"
                )
            if "configuration_mode" not in coordinator.device_client.available_registers.get(
                "holding_registers", set()
            ):
                raise ServiceValidationError("Pressure-test command is unavailable on this device")
            if not await deps.write_register(
                coordinator,
                "configuration_mode",
                47 if test_type == "duct_filter" else 65,
                entity_id,
                "start pressure test",
            ):
                raise HomeAssistantError("Device did not confirm pressure test start")
            return await _run_with_success_log(
                coordinator, deps, "Started pressure test for %s", entity_id
            )

        await _run_for_targets(hass, call, deps, _start_pressure_test_for_target)

    return start_pressure_test


def _build_set_modbus_parameters_handler(
    hass: HomeAssistant, deps: ServiceHandlerDeps
) -> ServiceHandler:
    async def set_modbus_parameters(call: ServiceCall) -> None:
        port, baud_rate, parity, stop_bits = normalize_modbus_options(
            deps.normalize_option, call.data
        )

        async def _set_modbus_parameters_for_target(entity_id: str, coordinator: Any) -> bool:
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
                    raise HomeAssistantError(
                        f"Device did not confirm Modbus parameter update for {entity_id}."
                    )
            return await _run_with_success_log(
                coordinator, deps, "Set Modbus parameters for %s", entity_id
            )

        await _run_for_targets(hass, call, deps, _set_modbus_parameters_for_target)

    return set_modbus_parameters


def _build_set_device_name_handler(hass: HomeAssistant, deps: ServiceHandlerDeps) -> ServiceHandler:
    async def set_device_name(call: ServiceCall) -> None:
        device_name = call.data["device_name"]

        async def _set_device_name_for_target(entity_id: str, coordinator: Any) -> bool:
            try:
                # Encode the whole NUL-padded name once; the coordinator splits
                # the 8-word payload into effective-batch FC16 chunks.
                success = await coordinator.async_write_register(
                    "device_name", device_name, refresh=False, targeted_readback=False
                )
            except _DEVICE_ERRORS as err:
                deps.logger.error("Failed to set device name for %s: %s", entity_id, err)
                raise HomeAssistantError(
                    f"Failed to set device name for {entity_id}: {err}"
                ) from err

            if not success:
                deps.logger.error("Failed to set device name for %s", entity_id)
                raise HomeAssistantError(
                    f"Device did not confirm device-name update for {entity_id}."
                )
            return await _run_with_success_log(
                coordinator, deps, "Set device name to '%s' for %s", device_name, entity_id
            )

        await _run_for_targets(hass, call, deps, _set_device_name_for_target)

    return set_device_name


def _build_sync_time_handler(hass: HomeAssistant, deps: ServiceHandlerDeps) -> ServiceHandler:
    async def sync_time(call: ServiceCall) -> None:
        async def _sync_time_for_target(entity_id: str, coordinator: Any) -> bool:
            now = _dt.now()
            try:
                success = await coordinator.async_write_registers(
                    start_address=0,
                    values=_clock_payload(now),
                    refresh=False,
                    require_single_request=True,
                )
            except _DEVICE_ERRORS as err:
                deps.logger.error("Failed to sync clock for %s: %s", entity_id, err)
                raise HomeAssistantError(f"Failed to sync clock for {entity_id}: {err}") from err

            if not success:
                deps.logger.error("Failed to sync clock for %s", entity_id)
                raise HomeAssistantError(
                    f"Device did not confirm clock synchronization for {entity_id}."
                )

            deps.logger.info(
                "Synced device clock to %s for %s",
                now.strftime("%Y-%m-%d %H:%M:%S"),
                entity_id,
            )
            return True

        await _run_for_targets(hass, call, deps, _sync_time_for_target)

    return sync_time


def _build_sync_device_clock_handler(
    hass: HomeAssistant, deps: ServiceHandlerDeps
) -> ServiceHandler:
    async def sync_device_clock(call: ServiceCall) -> None:
        force = bool(call.data.get("force", False))

        async def _sync_device_clock_for_target(entity_id: str, coordinator: Any) -> bool:
            opts: dict[str, Any] = {}
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
            except Exception as err:
                deps.logger.error("Clock sync failed for %s: %s", entity_id, err)
                raise HomeAssistantError(
                    f"Clock synchronization failed for {entity_id}: {err}"
                ) from err
            if not ok:
                deps.logger.error("Failed to sync device clock for %s", entity_id)
                raise HomeAssistantError(
                    f"Device did not confirm clock synchronization for {entity_id}."
                )
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
