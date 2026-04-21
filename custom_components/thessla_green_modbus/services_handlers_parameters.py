"""Parameter/configuration service registration helpers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall

from .services_handler_deps import ServiceHandlerDeps
from .services_schema import (
    SET_AIR_QUALITY_THRESHOLDS_SCHEMA,
    SET_BYPASS_PARAMETERS_SCHEMA,
    SET_GWC_PARAMETERS_SCHEMA,
    SET_TEMPERATURE_CURVE_SCHEMA,
)


def register_parameter_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register parameter/configuration services."""

    async def set_bypass_parameters(call: ServiceCall) -> None:
        mode = deps.normalize_option(call.data["mode"])
        min_temperature = call.data.get("min_outdoor_temperature")
        mode_value = {"auto": 0, "open": 1, "closed": 2}[mode]

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            if not await deps.write_register(
                coordinator, "bypass_mode", mode_value, entity_id, "set bypass parameters"
            ):
                deps.logger.error("Failed to set bypass mode for %s", entity_id)
                continue
            if min_temperature is not None:
                if not await deps.write_register(
                    coordinator,
                    "min_bypass_temperature",
                    min_temperature,
                    entity_id,
                    "set bypass parameters",
                ):
                    deps.logger.error("Failed to set bypass min temperature for %s", entity_id)
                    continue
            await coordinator.async_request_refresh()
            deps.logger.info("Set bypass parameters for %s", entity_id)

    async def set_gwc_parameters(call: ServiceCall) -> None:
        mode = deps.normalize_option(call.data["mode"])
        min_air_temperature = call.data.get("min_air_temperature")
        max_air_temperature = call.data.get("max_air_temperature")
        mode_value = {"off": 0, "auto": 1, "forced": 2}[mode]

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            if not await deps.write_register(
                coordinator, "gwc_mode", mode_value, entity_id, "set GWC parameters"
            ):
                deps.logger.error("Failed to set GWC mode for %s", entity_id)
                continue
            if min_air_temperature is not None:
                if not await deps.write_register(
                    coordinator,
                    "min_gwc_air_temperature",
                    min_air_temperature,
                    entity_id,
                    "set GWC parameters",
                ):
                    deps.logger.error("Failed to set GWC min air temperature for %s", entity_id)
                    continue
            if max_air_temperature is not None:
                if not await deps.write_register(
                    coordinator,
                    "max_gwc_air_temperature",
                    max_air_temperature,
                    entity_id,
                    "set GWC parameters",
                ):
                    deps.logger.error("Failed to set GWC max air temperature for %s", entity_id)
                    continue
            await coordinator.async_request_refresh()
            deps.logger.info("Set GWC parameters for %s", entity_id)

    async def set_air_quality_thresholds(call: ServiceCall) -> None:
        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            success = True
            for param in ["co2_low", "co2_medium", "co2_high", "humidity_target"]:
                value = call.data.get(param)
                if value is not None:
                    register_name = deps.air_quality_register_map[param]
                    if not await deps.write_register(
                        coordinator,
                        register_name,
                        value,
                        entity_id,
                        "set air quality thresholds",
                    ):
                        deps.logger.error("Failed to set %s for %s", param, entity_id)
                        success = False
                        break
            if not success:
                continue
            await coordinator.async_request_refresh()
            deps.logger.info("Set air quality thresholds for %s", entity_id)

    async def set_temperature_curve(call: ServiceCall) -> None:
        slope = call.data["slope"]
        offset = call.data["offset"]
        max_supply_temp = call.data.get("max_supply_temp")
        min_supply_temp = call.data.get("min_supply_temp")

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            if not await deps.write_register(
                coordinator, "heating_curve_slope", slope, entity_id, "set temperature curve"
            ):
                deps.logger.error("Failed to set heating curve slope for %s", entity_id)
                continue
            if not await deps.write_register(
                coordinator, "heating_curve_offset", offset, entity_id, "set temperature curve"
            ):
                deps.logger.error("Failed to set heating curve offset for %s", entity_id)
                continue
            if max_supply_temp is not None:
                if not await deps.write_register(
                    coordinator,
                    "max_supply_temperature",
                    max_supply_temp,
                    entity_id,
                    "set temperature curve",
                ):
                    deps.logger.error("Failed to set max supply temperature for %s", entity_id)
                    continue
            if min_supply_temp is not None:
                if not await deps.write_register(
                    coordinator,
                    "min_supply_temperature",
                    min_supply_temp,
                    entity_id,
                    "set temperature curve",
                ):
                    deps.logger.error("Failed to set min supply temperature for %s", entity_id)
                    continue
            await coordinator.async_request_refresh()
            deps.logger.info("Set temperature curve for %s", entity_id)

    hass.services.async_register(
        deps.domain, "set_bypass_parameters", set_bypass_parameters, SET_BYPASS_PARAMETERS_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "set_gwc_parameters", set_gwc_parameters, SET_GWC_PARAMETERS_SCHEMA
    )
    hass.services.async_register(
        deps.domain,
        "set_air_quality_thresholds",
        set_air_quality_thresholds,
        SET_AIR_QUALITY_THRESHOLDS_SCHEMA,
    )
    hass.services.async_register(
        deps.domain, "set_temperature_curve", set_temperature_curve, SET_TEMPERATURE_CURVE_SCHEMA
    )
