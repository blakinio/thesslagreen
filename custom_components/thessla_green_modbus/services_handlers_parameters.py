"""Parameter/configuration service registration helpers."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .services_dispatch import refresh_and_log_success, write_register_steps
from .services_handler_deps import ServiceHandlerDeps
from .services_schema import (
    SET_AIR_QUALITY_THRESHOLDS_SCHEMA,
    SET_BYPASS_PARAMETERS_SCHEMA,
    SET_GWC_PARAMETERS_SCHEMA,
    SET_TEMPERATURE_CURVE_SCHEMA,
)
from .services_validation import BYPASS_MODE_MAP, GWC_MODE_MAP

WriteStep = tuple[str, object | None, bool, str]
ServiceHandler = Callable[[ServiceCall], object]
Registration = tuple[str, ServiceHandler, vol.Schema]


def _build_step_handler(
    hass: HomeAssistant,
    deps: ServiceHandlerDeps,
    *,
    context: str,
    success_log: str,
    step_builder: Callable[[ServiceCall], Sequence[WriteStep]],
) -> ServiceHandler:
    """Create a parameter handler based on write steps."""

    async def _handler(call: ServiceCall) -> None:
        steps = step_builder(call)
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            if not await write_register_steps(
                coordinator,
                steps,
                entity_id,
                context,
                deps.write_register,
                deps.logger,
            ):
                continue
            await refresh_and_log_success(coordinator, deps.logger, success_log, entity_id)

    return _handler


def _parameter_registrations(
    hass: HomeAssistant, deps: ServiceHandlerDeps
) -> tuple[Registration, ...]:
    """Build parameter service registrations with handlers and schemas."""
    set_bypass_parameters = _build_step_handler(
        hass,
        deps,
        context="set bypass parameters",
        success_log="Set bypass parameters for %s",
        step_builder=lambda call: [
            (
                "bypass_mode",
                BYPASS_MODE_MAP[deps.normalize_option(call.data["mode"])],
                False,
                "Failed to set bypass mode for %s",
            ),
            (
                "min_bypass_temperature",
                call.data.get("min_outdoor_temperature"),
                True,
                "Failed to set bypass min temperature for %s",
            ),
        ],
    )
    set_gwc_parameters = _build_step_handler(
        hass,
        deps,
        context="set GWC parameters",
        success_log="Set GWC parameters for %s",
        step_builder=lambda call: [
            ("gwc_mode", GWC_MODE_MAP[deps.normalize_option(call.data["mode"])], False, "Failed to set GWC mode for %s"),
            (
                "min_gwc_air_temperature",
                call.data.get("min_air_temperature"),
                True,
                "Failed to set GWC min air temperature for %s",
            ),
            (
                "max_gwc_air_temperature",
                call.data.get("max_air_temperature"),
                True,
                "Failed to set GWC max air temperature for %s",
            ),
        ],
    )

    async def set_air_quality_thresholds(call: ServiceCall) -> None:
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            success = True
            for param in ["co2_low", "co2_medium", "co2_high", "humidity_target"]:
                value = call.data.get(param)
                if value is not None and not await deps.write_register(coordinator, deps.air_quality_register_map[param], value, entity_id, "set air quality thresholds"):
                    deps.logger.error("Failed to set %s for %s", param, entity_id)
                    success = False
                    break
            if success:
                await refresh_and_log_success(coordinator, deps.logger, "Set air quality thresholds for %s", entity_id)

    set_temperature_curve = _build_step_handler(
        hass,
        deps,
        context="set temperature curve",
        success_log="Set temperature curve for %s",
        step_builder=lambda call: [
            ("heating_curve_slope", call.data["slope"], False, "Failed to set heating curve slope for %s"),
            ("heating_curve_offset", call.data["offset"], False, "Failed to set heating curve offset for %s"),
            (
                "max_supply_temperature",
                call.data.get("max_supply_temp"),
                True,
                "Failed to set max supply temperature for %s",
            ),
            (
                "min_supply_temperature",
                call.data.get("min_supply_temp"),
                True,
                "Failed to set min supply temperature for %s",
            ),
        ],
    )

    return (
        ("set_bypass_parameters", set_bypass_parameters, SET_BYPASS_PARAMETERS_SCHEMA),
        ("set_gwc_parameters", set_gwc_parameters, SET_GWC_PARAMETERS_SCHEMA),
        ("set_air_quality_thresholds", set_air_quality_thresholds, SET_AIR_QUALITY_THRESHOLDS_SCHEMA),
        ("set_temperature_curve", set_temperature_curve, SET_TEMPERATURE_CURVE_SCHEMA),
    )


def register_parameter_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register parameter/configuration services."""
    for service_name, handler, schema in _parameter_registrations(hass, deps):
        hass.services.async_register(deps.domain, service_name, handler, schema)
