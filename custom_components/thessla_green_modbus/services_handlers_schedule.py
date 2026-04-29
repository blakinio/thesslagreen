"""Schedule-related service registration helpers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall

from .services_handler_deps import ServiceHandlerDeps
from .services_schema import SET_AIRFLOW_SCHEDULE_SCHEMA


def _resolve_schedule_temperature_byte(
    coordinator: object, setting_register: str, temperature: float | None
) -> int:
    if temperature is not None:
        return max(0, min(39, round((temperature - 16.0) * 2)))

    current = coordinator.data.get(setting_register) if coordinator.data else None
    return int(current) & 0xFF if isinstance(current, int) else 0


def register_schedule_services(hass: HomeAssistant, deps: ServiceHandlerDeps) -> None:
    """Register schedule-related services."""

    async def set_airflow_schedule(call: ServiceCall) -> None:
        day = deps.normalize_option(call.data["day"])
        period = int(deps.normalize_option(str(call.data["period"])))
        season = deps.normalize_option(call.data.get("season", "summer"))
        start_time = call.data["start_time"]
        end_time = call.data.get("end_time")
        airflow_rate = call.data["airflow_rate"]
        temperature = call.data.get("temperature")
        dow_key = deps.day_to_device_key[day]
        schedule_register = f"schedule_{season}_{dow_key}_{period}"
        setting_register = f"setting_{season}_{dow_key}_{period}"
        start_value = f"{start_time.hour:02d}:{start_time.minute:02d}"

        if end_time is not None:
            deps.logger.warning(
                "set_airflow_schedule: end_time is not writable on AirPack4 "
                "(slot end = next slot's start). Ignoring end_time=%s.",
                end_time,
            )

        for entity_id, coordinator in deps.iter_target_coordinators(hass, call):
            holding = coordinator.available_registers.get("holding_registers", set())
            if schedule_register not in holding or setting_register not in holding:
                deps.logger.error(
                    "set_airflow_schedule: %s or %s not available on %s — aborting",
                    schedule_register,
                    setting_register,
                    entity_id,
                )
                continue

            clamped_airflow = deps.clamp_airflow_rate(coordinator, airflow_rate)
            if not await deps.write_register(
                coordinator,
                schedule_register,
                start_value,
                entity_id,
                "set airflow schedule start",
            ):
                deps.logger.error("Failed to set schedule start for %s", entity_id)
                continue

            temp_byte = _resolve_schedule_temperature_byte(
                coordinator, setting_register, temperature
            )
            aatt_value = ((clamped_airflow & 0xFF) << 8) | (temp_byte & 0xFF)

            if not await deps.write_register(
                coordinator,
                setting_register,
                aatt_value,
                entity_id,
                "set airflow schedule AATT",
            ):
                deps.logger.error("Failed to set schedule AATT for %s", entity_id)
                continue

            await coordinator.async_request_refresh()
            deps.logger.info(
                "Set airflow schedule [%s %s slot %d] start=%s flow=%d%% on %s",
                season,
                dow_key,
                period,
                start_value,
                clamped_airflow,
                entity_id,
            )

    hass.services.async_register(
        deps.domain, "set_airflow_schedule", set_airflow_schedule, SET_AIRFLOW_SCHEDULE_SCHEMA
    )
    hass.services.async_register(
        deps.domain, "set_intensity", set_airflow_schedule, SET_AIRFLOW_SCHEDULE_SCHEMA
    )
