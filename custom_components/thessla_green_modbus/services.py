"""Service handlers for the ThesslaGreen Modbus integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.util import dt as dt_util

from . import services_schema as _services_schema
from .const import DOMAIN, SPECIAL_FUNCTION_MAP
from .scanner import ThesslaGreenDeviceScanner
from .services_handlers import (
    ServiceHandlerDeps,
    register_data_services,
    register_maintenance_services,
    register_mode_services,
    register_parameter_services,
    register_schedule_services,
)
from .services_helpers import clamp_airflow_rate as _clamp_airflow_rate_impl
from .services_helpers import normalize_option as _normalize_option_impl
from .services_helpers import write_register as _write_register_impl
from .services_schema import (
    validate_bypass_temperature_range as _validate_bypass_temperature_range_impl,
)
from .services_schema import (
    validate_gwc_temperature_range as _validate_gwc_temperature_range_impl,
)
from .services_targets import (
    extract_entity_ids_with_extractor as _extract_entity_ids_impl,
)
from .services_targets import (
    get_coordinator_from_entity_id as _get_coordinator_from_entity_id_impl,
)
from .services_targets import iter_target_coordinators as _iter_target_coordinators_impl

if TYPE_CHECKING:
    from .coordinator import ThesslaGreenModbusCoordinator

_LOGGER = logging.getLogger(__name__)

# Re-export schema constants for compatibility with tests/tooling.
SET_SPECIAL_MODE_SCHEMA = _services_schema.SET_SPECIAL_MODE_SCHEMA
SET_AIRFLOW_SCHEDULE_SCHEMA = _services_schema.SET_AIRFLOW_SCHEDULE_SCHEMA
SET_LOG_LEVEL_SCHEMA = _services_schema.SET_LOG_LEVEL_SCHEMA


class _LogLevelManager:
    """Manage temporary log level changes for the integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._restore_level: int | None = None
        self._undo_callback: Callable[[], None] | None = None

    @staticmethod
    def _target_logger() -> logging.Logger:
        return logging.getLogger("custom_components.thessla_green_modbus")

    def set_level(self, level: int, duration: int) -> None:
        logger = self._target_logger()
        previous_level = logger.level
        logger.setLevel(level)
        _LOGGER.info("Set %s log level to %s", logger.name, logging.getLevelName(level))

        if self._undo_callback:
            self._undo_callback()
            self._undo_callback = None

        self._restore_level = previous_level
        if duration > 0:
            self._undo_callback = async_call_later(
                self.hass, duration, self._restore_level_callback
            )

    def _restore_level_callback(self, _now: Any) -> None:
        logger = self._target_logger()
        logger.setLevel(self._restore_level or logging.NOTSET)
        _LOGGER.info(
            "Restored %s log level to %s",
            logger.name,
            logging.getLevelName(self._restore_level or logging.NOTSET),
        )
        self._undo_callback = None


AIR_QUALITY_REGISTER_MAP = {
    "co2_low": "co2_threshold_low",
    "co2_medium": "co2_threshold_medium",
    "co2_high": "co2_threshold_high",
    "humidity_target": "humidity_target",
}

_DAY_TO_DEVICE_KEY = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


def _extract_entity_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Return entity IDs from a service call."""
    return _extract_entity_ids_impl(hass, call, extractor=async_extract_entity_ids)


def _iter_target_coordinators(hass: HomeAssistant, call: ServiceCall) -> list[tuple[str, Any]]:
    """Resolve entity IDs to coordinator instances, skipping missing ones."""
    return _iter_target_coordinators_impl(
        hass,
        call,
        coordinator_getter=_get_coordinator_from_entity_id,
    )


def _validate_bypass_temperature_range(data: dict[str, Any]) -> dict[str, Any]:
    """Validate bypass temperature range independently from voluptuous internals."""
    return _validate_bypass_temperature_range_impl(data)


def _validate_gwc_temperature_range(data: dict[str, Any]) -> dict[str, Any]:
    """Reject configurations where min_air_temperature >= max_air_temperature."""
    return _validate_gwc_temperature_range_impl(data)


def _normalize_option(value: str) -> str:
    """Convert translation keys to internal option values."""
    return _normalize_option_impl(value)


def _clamp_airflow_rate(coordinator: Any, airflow_rate: int) -> int:
    """Clamp airflow_rate to the coordinator's reported min/max percentages."""
    return _clamp_airflow_rate_impl(coordinator, airflow_rate)


async def _write_register(
    coordinator: ThesslaGreenModbusCoordinator,
    register: str,
    value: Any,
    entity_id: str,
    action: str,
) -> bool:
    """Write to a register with error handling."""
    return await _write_register_impl(coordinator, register, value, entity_id, action, _LOGGER)


def _handler_deps() -> ServiceHandlerDeps:
    return ServiceHandlerDeps(
        domain=DOMAIN,
        logger=_LOGGER,
        special_function_map=SPECIAL_FUNCTION_MAP,
        day_to_device_key=_DAY_TO_DEVICE_KEY,
        air_quality_register_map=AIR_QUALITY_REGISTER_MAP,
        iter_target_coordinators=_iter_target_coordinators,
        normalize_option=_normalize_option,
        clamp_airflow_rate=_clamp_airflow_rate,
        write_register=_write_register,
        create_log_level_manager=_LogLevelManager,
        dt_now=dt_util.now,
        scanner_create=ThesslaGreenDeviceScanner.create,
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for ThesslaGreen Modbus integration."""
    deps = _handler_deps()
    register_mode_services(hass, deps)
    register_schedule_services(hass, deps)
    register_parameter_services(hass, deps)
    register_maintenance_services(hass, deps)
    register_data_services(hass, deps)
    _LOGGER.info("ThesslaGreen Modbus services registered successfully")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services for ThesslaGreen Modbus integration."""
    services = [
        "set_special_mode",
        "set_mode",
        "set_intensity",
        "set_special_function",
        "set_airflow_schedule",
        "set_bypass_parameters",
        "set_gwc_parameters",
        "set_air_quality_thresholds",
        "set_temperature_curve",
        "reset_filters",
        "reset_settings",
        "start_pressure_test",
        "set_modbus_parameters",
        "set_device_name",
        "sync_time",
        "refresh_device_data",
        "get_unknown_registers",
        "scan_all_registers",
        "set_debug_logging",
    ]

    for service in services:
        hass.services.async_remove(DOMAIN, service)

    _LOGGER.info("ThesslaGreen Modbus services unloaded")


def _get_coordinator_from_entity_id(
    hass: HomeAssistant, entity_id: str
) -> ThesslaGreenModbusCoordinator | None:
    """Get coordinator from entity ID using entity registry."""
    return _get_coordinator_from_entity_id_impl(hass, entity_id)
