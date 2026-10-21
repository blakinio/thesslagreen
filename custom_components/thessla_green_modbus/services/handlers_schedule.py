"""Schedule-related service registration helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from ..coordinator.schedule_service import async_write_schedule_slot
from .handler_deps import ServiceHandlerDeps
from .handlers_airing import register_airing_service
from .schema import SET_AIRFLOW_SCHEDULE_SCHEMA


def _schedule_settings(flow: int, temperature: float | None) -> dict[str, Any]:
    """Validate AATT fields in user units; absent temperature is read under lock."""
    if not 10 <= flow <= 100:
        raise ServiceValidationError("Schedule airflow must be from 10 to 100 percent")
    if temperature is not None and (
        not 10 <= temperature <= 45 or not float(temperature * 2).is_integer()
    ):
        raise ServiceValidationError("Schedule temperature must be 10..45 C in 0.5 C steps")
    return {"airflow_pct": flow, "temp_c": temperature}


def register_schedule_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register schedule-related services."""
    register_airing_service(hass, deps)

    async def set_airflow_schedule(call: ServiceCall) -> None:
        day = deps.normalize_option(call.data["day"])
        period = int(deps.normalize_option(str(call.data["period"])))
        season = deps.normalize_option(call.data.get("season", "summer"))
        start_time = call.data.get("start_time")
        enabled = call.data.get("enabled", True)
        end_time = call.data.get("end_time")
        airflow_rate = call.data.get("airflow_rate")
        temperature = call.data.get("temperature")
        dow_key = deps.day_to_device_key[day]
        schedule_register = f"schedule_{season}_{dow_key}_{period}"
        setting_register = f"setting_{season}_{dow_key}_{period}"
        if enabled and (start_time is None or airflow_rate is None):
            raise ServiceValidationError(
                "start_time and airflow_rate are required when enabling a slot"
            )
        start_value = f"{start_time.hour:02d}:{start_time.minute:02d}" if enabled else "disabled"
        settings = _schedule_settings(airflow_rate, temperature) if enabled else None

        if end_time is not None:
            raise ServiceValidationError(
                "end_time cannot be written by AirPack4: a schedule slot ends "
                "when the next slot starts. Set the next slot's start_time instead."
            )

        for entity_id, coordinator in await deps.iter_target_coordinators(hass, call):
            holding = coordinator.device_client.available_registers.get("holding_registers", set())
            missing = {
                register
                for register in (schedule_register, setting_register)
                if register not in holding
            }
            if missing:
                raise ServiceValidationError(
                    f"{entity_id} does not expose required schedule registers: "
                    f"{', '.join(sorted(missing))}."
                )

            await async_write_schedule_slot(
                coordinator, schedule_register, start_value, setting_register, settings
            )
            deps.logger.info(
                "Set airflow schedule [%s %s slot %d] start=%s flow=%s%% on %s",
                season,
                dow_key,
                period,
                start_value,
                airflow_rate,
                entity_id,
            )

    hass.services.async_register(
        deps.domain, "set_airflow_schedule", set_airflow_schedule, SET_AIRFLOW_SCHEDULE_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "set_intensity", set_airflow_schedule, SET_AIRFLOW_SCHEDULE_SCHEMA
    )
